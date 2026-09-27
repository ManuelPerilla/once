import html
import os
import re

import httpx

from .api_football import ProviderError

QID_PATTERN = re.compile(r"^Q[1-9][0-9]*$", re.IGNORECASE)
TAG_PATTERN = re.compile(r"<[^>]+>")


def _plain(value: str | None) -> str | None:
    if not value:
        return None
    return html.unescape(TAG_PATTERN.sub("", value)).strip() or None


class WikidataClient:
    base_url = "https://www.wikidata.org/wiki/Special:EntityData"
    commons_api = "https://commons.wikimedia.org/w/api.php"

    def __init__(self, timeout: float = 12.0):
        self.timeout = timeout
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
        if not QID_PATTERN.match(normalized):
            raise ValueError("El identificador de Wikidata debe tener formato Q123.")

        try:
            response = httpx.get(
                f"{self.base_url}/{normalized}.json",
                headers=self.headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"Wikidata no respondió correctamente: {exc}") from exc

        payload = response.json()
        entity = payload.get("entities", {}).get(normalized)
        if not entity or "missing" in entity:
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
            response = httpx.get(
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

    def commons_media(self, qid: str) -> dict:
        entity = self.entity(qid)
        claims = entity.get("claims") or {}
        image_claims = claims.get("P18") or []
        if not image_claims:
            raise ProviderError("La entidad de Wikidata no tiene imagen P18.")

        filename = image_claims[0].get("mainsnak", {}).get("datavalue", {}).get("value")
        if not filename:
            raise ProviderError("Wikidata devolvió una imagen P18 sin nombre de archivo.")

        title = filename if str(filename).startswith("File:") else f"File:{filename}"
        params = {
            "action": "query",
            "format": "json",
            "formatversion": 2,
            "prop": "imageinfo",
            "titles": title,
            "iiprop": "url|size|mime|extmetadata",
            "iiextmetadatafilter": (
                "Artist|Credit|LicenseShortName|LicenseUrl|UsageTerms|"
                "AttributionRequired|ImageDescription"
            ),
            "iiextmetadatalanguage": "es",
        }

        try:
            response = httpx.get(
                self.commons_api,
                params=params,
                headers=self.headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"Wikimedia Commons no respondió correctamente: {exc}") from exc

        pages = response.json().get("query", {}).get("pages", [])
        info = (pages[0].get("imageinfo") or [None])[0] if pages else None
        if not info:
            raise ProviderError("Commons no devolvió metadatos para la imagen.")

        metadata = info.get("extmetadata") or {}

        def metadata_value(key: str) -> str | None:
            raw = (metadata.get(key) or {}).get("value")
            return _plain(raw)

        return {
            "qid": qid.upper(),
            "filename": filename,
            "source_url": f"https://commons.wikimedia.org/wiki/{title.replace(' ', '_')}",
            "original_url": info.get("url"),
            "width": info.get("width"),
            "height": info.get("height"),
            "mime_type": info.get("mime"),
            "author": metadata_value("Artist"),
            "credit": metadata_value("Credit"),
            "license": metadata_value("LicenseShortName") or metadata_value("UsageTerms"),
            "license_url": (metadata.get("LicenseUrl") or {}).get("value"),
            "description": metadata_value("ImageDescription"),
            "attribution_required": metadata_value("AttributionRequired"),
        }
