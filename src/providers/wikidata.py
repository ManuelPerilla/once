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
            "Vertice/0.1 (https://github.com/MizunDev/vertice; football knowledge project)",
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

    def commons_media(self, qid: str) -> dict:
        entity = self.entity(qid)
        claims = entity.get("claims") or {}
        image_claims = claims.get("P18") or []
        if not image_claims:
            raise ProviderError("La entidad de Wikidata no tiene imagen P18.")

        filename = (
            image_claims[0]
            .get("mainsnak", {})
            .get("datavalue", {})
            .get("value")
        )
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
