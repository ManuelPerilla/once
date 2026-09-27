import html
import os
import re
import time
from collections import OrderedDict
from copy import deepcopy
from threading import RLock
from urllib.parse import quote, urlsplit

import httpx

from .api_football import ProviderError

QID_PATTERN = re.compile(r"^Q[1-9][0-9]*$", re.IGNORECASE)
TAG_PATTERN = re.compile(r"<[^>]+>")
MEDIA_CACHE_SECONDS = 24 * 60 * 60
MEDIA_CACHE_SIZE = 128
_media_cache: OrderedDict[tuple[str, str], tuple[float, dict]] = OrderedDict()
_media_lock = RLock()


def _plain(value: str | None) -> str | None:
    if not value:
        return None
    return html.unescape(TAG_PATTERN.sub("", value)).strip() or None


def _https_url(value: str | None, *, hosts: set[str] | None = None) -> str | None:
    """Only expose usable HTTPS links, never HTML/JS supplied in metadata."""
    if not isinstance(value, str):
        return None
    value = html.unescape(value).strip()
    if value.startswith("//"):
        value = f"https:{value}"
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme == "https"
            and parsed.hostname
            and not parsed.username
            and not parsed.password
            and parsed.port in (None, 443)
            and (hosts is None or parsed.hostname in hosts)
        ):
            return value
    except ValueError:
        pass
    return None


def _media_statement(entity: dict, purpose: str) -> tuple[str, str]:
    """A team photograph is not a badge; deprecated statements are not candidates."""
    properties = ("P154",) if purpose == "crest" else ("P154", "P18")
    for prop in properties:
        candidates = sorted(
            (entity.get("claims") or {}).get(prop) or [],
            key=lambda claim: claim.get("rank") != "preferred",
        )
        for claim in candidates:
            if claim.get("rank") == "deprecated":
                continue
            value = (claim.get("mainsnak", {}).get("datavalue") or {}).get("value")
            if isinstance(value, str) and value.strip() and not any(c in value for c in "|\r\n"):
                return prop, value.strip()
    if purpose == "crest":
        raise ProviderError(
            "Esta ficha no tiene un escudo disponible en Wikimedia Commons. "
            "Puedes conservar las iniciales o añadir una imagen propia."
        )
    raise ProviderError("Esta ficha no tiene una imagen disponible en Wikimedia Commons.")


class WikidataClient:
    base_url = "https://www.wikidata.org/wiki/Special:EntityData"
    commons_api = "https://commons.wikimedia.org/w/api.php"

    def __init__(self, timeout: float = 12.0, *, transport=None):
        self.timeout = timeout
        self.transport = transport
        self.user_agent = os.getenv(
            "WIKIDATA_USER_AGENT",
            "ONCE/0.2 (personal local football catalog)",
        )

    @property
    def headers(self) -> dict:
        return {
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }

    def entity(self, qid: str) -> dict:
        normalized = qid.upper()
        if not QID_PATTERN.fullmatch(normalized):
            raise ValueError("El identificador de Wikidata debe tener formato Q123.")

        try:
            response = (self.transport or httpx.get)(
                f"{self.base_url}/{normalized}.json",
                headers=self.headers,
                timeout=self.timeout,
            )
            if response.status_code == 429:
                raise ProviderError(
                    "Wikidata pide reducir las consultas. Espera antes de volver a intentar."
                )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError(
                "Wikidata no respondió correctamente. Inténtalo más tarde."
            ) from exc

        if not isinstance(payload, dict) or not isinstance(payload.get("entities"), dict):
            raise ProviderError("Wikidata devolvió una respuesta no válida.")
        entity = payload.get("entities", {}).get(normalized)
        if not isinstance(entity, dict) or not entity or "missing" in entity:
            raise ProviderError("Wikidata no devolvió la entidad solicitada.")
        return entity

    def entities(self, qids: list[str], *, interactive: bool = False) -> dict:
        """Read a bounded batch in one request, including statement references.

        Cache belongs to the ingestion service, not to the public page lifecycle.
        Do not retry a 429/maxlag response immediately or silently omit records.
        """
        ids = list(dict.fromkeys(qid.upper() for qid in qids))
        if not ids or len(ids) > 50 or any(not QID_PATTERN.fullmatch(qid) for qid in ids):
            raise ValueError("Solicita entre 1 y 50 identificadores válidos de Wikidata.")
        params = {
            "action": "wbgetentities",
            "format": "json",
            "ids": "|".join(ids),
            "languages": "es|en",
            "props": "labels|aliases|descriptions|claims|info",
        }
        # Wikimedia permits interactive requests to omit maxlag. Background jobs
        # retain it: https://www.mediawiki.org/wiki/Manual:Maxlag_parameter
        if not interactive:
            params["maxlag"] = 5
        try:
            response = (self.transport or httpx.get)(
                "https://www.wikidata.org/w/api.php",
                params=params,
                headers=self.headers,
                timeout=self.timeout,
            )
            if response.status_code == 429:
                raise ProviderError(
                    "Wikidata pide reducir las consultas. Espera antes de volver a intentar."
                )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError(
                "No se pudo obtener el catálogo de Wikidata. Inténtalo más tarde."
            ) from exc
        if not isinstance(payload, dict):
            raise ProviderError("Wikidata devolvió una respuesta no válida.")
        if isinstance(payload.get("error"), dict) and payload["error"].get("code") == "maxlag":
            raise ProviderError(
                "Wikidata está actualizando sus réplicas y pide esperar. No se modificó el catálogo; inténtalo más tarde."
            )
        if payload.get("error") or not isinstance(payload.get("entities"), dict):
            raise ProviderError("Wikidata no pudo completar la consulta. Inténtalo más tarde.")
        return payload["entities"]

    def commons_media(self, qid: str, *, purpose: str = "image") -> dict:
        """Resolve one reviewed asset, with a bounded per-process metadata cache.

        Serializing misses avoids concurrent requests for the same file. This is
        an explicit admin operation; public pages only read saved MediaAssets.
        """
        normalized = qid.upper()
        if not QID_PATTERN.fullmatch(normalized) or purpose not in {"image", "crest"}:
            raise ValueError("Usa una ficha Q123 y elige imagen o escudo.")
        key = (normalized, purpose)
        with _media_lock:
            cached = _media_cache.get(key)
            if cached and time.monotonic() - cached[0] < MEDIA_CACHE_SECONDS:
                _media_cache.move_to_end(key)
                return deepcopy(cached[1])
            media = self._fetch_commons_media(normalized, purpose)
            _media_cache[key] = (time.monotonic(), media)
            _media_cache.move_to_end(key)
            while len(_media_cache) > MEDIA_CACHE_SIZE:
                _media_cache.popitem(last=False)
            return deepcopy(media)

    def _fetch_commons_media(self, qid: str, purpose: str) -> dict:
        entity = self.entity(qid)
        prop, filename = _media_statement(entity, purpose)

        title = filename if str(filename).startswith("File:") else f"File:{filename}"
        params = {
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "prop": "imageinfo",
            "titles": title,
            "iiprop": "url|size|mime|extmetadata",
            "iiurlwidth": 384,
            "iiextmetadatafilter": (
                "Artist|Credit|LicenseShortName|LicenseUrl|UsageTerms|"
                "AttributionRequired|ImageDescription"
            ),
            "iiextmetadatalanguage": "es",
        }

        try:
            response = (self.transport or httpx.get)(
                self.commons_api,
                params=params,
                headers=self.headers,
                timeout=self.timeout,
            )
            if response.status_code == 429:
                raise ProviderError(
                    "Wikimedia Commons pide esperar antes de consultar más imágenes. "
                    "No se ha guardado ningún cambio."
                )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError(
                "No se pudo consultar Wikimedia Commons. Inténtalo más tarde."
            ) from exc

        if not isinstance(payload, dict) or payload.get("error"):
            raise ProviderError("Wikimedia Commons no pudo completar la consulta.")
        pages = (payload.get("query") or {}).get("pages", [])
        if not isinstance(pages, list):
            raise ProviderError("Wikimedia Commons devolvió una respuesta no válida.")
        info = (pages[0].get("imageinfo") or [None])[0] if pages else None
        if not info:
            raise ProviderError("Commons no devolvió metadatos para la imagen.")

        metadata = info.get("extmetadata") or {}

        def metadata_value(key: str) -> str | None:
            raw = (metadata.get(key) or {}).get("value")
            return _plain(raw)

        original_url = _https_url(info.get("url"), hosts={"upload.wikimedia.org"})
        if not original_url or not (info.get("mime") or "").startswith("image/"):
            raise ProviderError("Commons no devolvió una imagen válida para mostrar.")
        license_name = metadata_value("LicenseShortName") or metadata_value("UsageTerms")
        labels = entity.get("labels") or {}
        return {
            "qid": qid.upper(),
            "entity_name": (labels.get("es") or labels.get("en") or {}).get("value", qid),
            "property": prop,
            "filename": filename,
            "source_url": f"https://commons.wikimedia.org/wiki/{quote(title.replace(' ', '_'), safe=':')}",
            "original_url": original_url,
            "thumbnail_url": _https_url(
                info.get("thumburl"), hosts={"upload.wikimedia.org", "thumb.wikimedia.org"}
            ),
            "width": info.get("width"),
            "height": info.get("height"),
            "mime_type": info.get("mime"),
            "author": metadata_value("Artist"),
            "credit": metadata_value("Credit"),
            "license": license_name,
            "license_url": _https_url((metadata.get("LicenseUrl") or {}).get("value")),
            "description": metadata_value("ImageDescription"),
            "attribution_required": metadata_value("AttributionRequired"),
            "can_use_as_logo": prop == "P154" and bool(license_name),
        }
