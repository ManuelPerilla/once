"""Bounded Commons metadata batches and validated, content-addressed local files."""

import hashlib
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from src.providers.api_football import ProviderError
from src.providers.wikidata import WikidataClient, _https_url, _media_statement, _plain


def _atomic_write(path, data):
    temporary = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_bytes(data)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _safe_style(value):
    allowed = {
        "fill",
        "fill-opacity",
        "fill-rule",
        "stroke",
        "stroke-width",
        "stroke-opacity",
        "stroke-linecap",
        "stroke-linejoin",
        "stroke-miterlimit",
        "stroke-dasharray",
        "stroke-dashoffset",
        "opacity",
        "stop-color",
        "stop-opacity",
        "clip-rule",
        "font-size",
        "font-weight",
        "font-family",
        "text-anchor",
        "display",
        "visibility",
    }
    safe = []
    for declaration in value.split(";"):
        key, separator, item = declaration.partition(":")
        if (
            separator
            and key.strip().lower() in allowed
            and re.fullmatch(r"[A-Za-z0-9#.,% ()_+\-/]+", item.strip())
            and not re.search(r"url|expression|import", item, re.I)
        ):
            safe.append(f"{key.strip().lower()}:{item.strip()}")
    return ";".join(safe)


def directory():
    return Path(os.getenv("ONCE_MEDIA_DIR", ".local/media")).resolve()


def batch_crests(entities, transport, headers):
    candidates = {}
    for qid, entity in entities.items():
        try:
            _, filename = _media_statement(entity, "crest")
            candidates[qid] = filename if filename.startswith("File:") else f"File:{filename}"
        except ProviderError:
            continue
    if not candidates:
        return {}
    response = transport(
        "https://commons.wikimedia.org/w/api.php",
        params={
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "prop": "imageinfo",
            "titles": "|".join(dict.fromkeys(candidates.values())),
            "iiprop": "url|size|mime|extmetadata",
            "iiurlwidth": 384,
            "maxlag": 5,
        },
        headers=headers,
        timeout=12,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        raise ProviderError("Commons está ocupado. Se reintentará el enriquecimiento.")
    pages = {page["title"]: page for page in payload.get("query", {}).get("pages", [])}
    aliases = {
        entry["from"]: entry["to"] for entry in payload.get("query", {}).get("normalized", [])
    }
    result = {}
    for qid, title in candidates.items():
        page = pages.get(aliases.get(title, title), {})
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}

        def value(key, meta=meta):
            return _plain((meta.get(key) or {}).get("value"))

        url = _https_url(info.get("url"), hosts={"upload.wikimedia.org"})
        license_name = value("LicenseShortName") or value("UsageTerms")
        if not url or not license_name or not str(info.get("mime", "")).startswith("image/"):
            continue
        result[qid] = {
            "qid": qid,
            "property": "P154",
            "filename": title.removeprefix("File:"),
            "source_url": f"https://commons.wikimedia.org/wiki/{quote(title.replace(' ', '_'), safe=':')}",
            "original_url": url,
            "license": license_name,
            "license_url": _https_url((meta.get("LicenseUrl") or {}).get("value")),
            "author": value("Artist"),
            "credit": value("Credit"),
            "mime_type": info.get("mime"),
            "width": info.get("width"),
            "height": info.get("height"),
        }
    return result


def cache_asset(media, transport):
    url = _https_url(media.get("original_url"), hosts={"upload.wikimedia.org"})
    if not url:
        raise ProviderError("El archivo no procede de Commons.", retryable=False)
    folder = directory()
    folder.mkdir(parents=True, exist_ok=True)
    index = folder / (hashlib.sha256(url.encode()).hexdigest() + ".json")
    if index.exists() and time.time() - index.stat().st_mtime < 86400:
        try:
            cached = json.loads(index.read_text(encoding="utf-8"))
            filename = cached["file"]
            if (
                re.fullmatch(r"[a-f0-9]{64}\.(png|jpg|gif|webp|svg)", filename)
                and (folder / filename).is_file()
            ):
                return {**media, "local_url": f"/api/assets/crests/{filename}"}
        except (ValueError, KeyError):
            pass
    response = transport(
        url, headers=WikidataClient().headers, timeout=12, max_bytes=5 * 1024 * 1024
    )
    response.raise_for_status()
    data = response.content
    if len(data) > 5 * 1024 * 1024:
        raise ProviderError("El escudo supera el tamaño permitido.", retryable=False)
    mime = response.headers.get("content-type", "").split(";")[0]
    extensions = {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/webp": "webp",
        "image/gif": "gif",
        "image/svg+xml": "svg",
    }
    if mime not in extensions:
        raise ProviderError("El archivo no es una imagen admitida.", retryable=False)
    if mime == "image/svg+xml":
        if re.search(rb"<!DOCTYPE|<!ENTITY", data, re.I):
            raise ProviderError("El SVG contiene declaraciones no admitidas.", retryable=False)
        try:
            root = ET.fromstring(data)
        except ET.ParseError as exc:
            raise ProviderError("El SVG está incompleto.", retryable=False) from exc
        if root.tag.split("}")[-1] != "svg":
            raise ProviderError("El archivo no es SVG.", retryable=False)
        allowed = {
            "svg",
            "g",
            "path",
            "rect",
            "circle",
            "ellipse",
            "line",
            "polyline",
            "polygon",
            "defs",
            "clipPath",
            "mask",
            "linearGradient",
            "radialGradient",
            "stop",
            "use",
            "title",
            "desc",
            "text",
            "tspan",
        }
        for parent in root.iter():
            for child in list(parent):
                if child.tag.split("}")[-1] not in allowed:
                    parent.remove(child)
            for key, value in list(parent.attrib.items()):
                name = key.split("}")[-1].lower()
                if name == "style":
                    parent.attrib[key] = _safe_style(value)
                    continue
                if (
                    name.startswith("on")
                    or (name == "href" and not value.startswith("#"))
                    or re.search(r"url\(\s*['\"]?(?!#)", value, re.I)
                ):
                    del parent.attrib[key]
        data = ET.tostring(root, encoding="utf-8")
    else:
        valid = (
            (mime == "image/png" and data.startswith(b"\x89PNG\r\n\x1a\n"))
            or (mime == "image/jpeg" and data.startswith(b"\xff\xd8\xff"))
            or (mime == "image/gif" and data.startswith((b"GIF87a", b"GIF89a")))
            or (mime == "image/webp" and data[:4] == b"RIFF" and data[8:12] == b"WEBP")
        )
        if not valid:
            raise ProviderError("El contenido no coincide con su tipo de imagen.", retryable=False)
    name = hashlib.sha256(data).hexdigest() + "." + extensions[mime]
    path = folder / name
    if not path.exists():
        _atomic_write(path, data)
    _atomic_write(index, json.dumps({"file": name}).encode())
    return {**media, "local_url": f"/api/assets/crests/{name}"}
