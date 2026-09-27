import os
import re

import httpx


class ProviderNotConfigured(RuntimeError):
    pass


class ProviderError(RuntimeError):
    def __init__(
        self, message, *, retryable=True, retry_after=None, code=None, access_seasons=None
    ):
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = retry_after
        self.code = code
        self.access_seasons = access_seasons or []
        self.allowed_seasons = self.access_seasons or None


class APIFootballClient:
    base_url = "https://v3.football.api-sports.io"

    def __init__(self, api_key: str | None = None, timeout: float = 12.0, *, transport=None):
        self.api_key = api_key or os.getenv("API_FOOTBALL_KEY")
        self.timeout = timeout
        self.transport = transport

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _get(self, path: str, params: dict | None = None, *, object_response=False) -> dict:
        if not self.api_key:
            raise ProviderNotConfigured("Configura API_FOOTBALL_KEY para consultar API-Football.")

        try:
            response = (self.transport or httpx.get)(
                f"{self.base_url}/{path.lstrip('/')}",
                params=params,
                headers={
                    "x-apisports-key": self.api_key,
                    "Accept": "application/json",
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            raise ProviderError(
                f"API-Football respondió con estado {status}.",
                retryable=status in {429, 499} or status >= 500,
                retry_after=exc.response.headers.get("Retry-After"),
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError("No se pudo conectar con API-Football.") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderError("API-Football devolvió un formato no válido.") from exc
        if not isinstance(payload, dict):
            raise ProviderError("API-Football devolvió una respuesta incompleta.")
        errors = payload.get("errors")
        if errors:
            keys = {str(key).lower() for key in errors} if isinstance(errors, dict) else set()
            limited = bool(keys & {"ratelimit", "requests", "requestlimit"})
            # Extract only numeric access bounds; provider messages may echo credentials.
            details = str(errors).lower()
            season_range = re.search(r"\bfrom\s+(20\d{2})\s+to\s+(20\d{2})\b", details)
            seasons = []
            if season_range:
                first, last = map(int, season_range.groups())
                if 0 <= last - first <= 30:
                    seasons = list(range(first, last + 1))
            restricted = bool(keys & {"plan", "subscription"}) or bool(seasons)
            raise ProviderError(
                "API-Football pide esperar antes de volver a consultar."
                if limited
                else "Tu plan de API-Football no permite consultar esa temporada o función."
                if restricted
                else "API-Football rechazó la consulta. Revisa cobertura, credencial y cuota.",
                retryable=limited,
                retry_after=response.headers.get("Retry-After", "60") if limited else None,
                code="quota" if limited else "plan" if restricted else "request_rejected",
                access_seasons=seasons,
            )
        if not isinstance(payload.get("response"), dict if object_response else list):
            raise ProviderError("API-Football devolvió una respuesta incompleta.")
        return payload

    def status(self) -> dict:
        return self._get("status", object_response=True)

    def fixture_batch(self, fixture_ids: list[int]) -> dict:
        if not 1 <= len(fixture_ids) <= 20 or any(
            type(value) is not int or value <= 0 for value in fixture_ids
        ):
            raise ValueError("El lote debe incluir entre uno y veinte partidos válidos.")
        return self._get("fixtures", {"ids": "-".join(str(value) for value in fixture_ids)})

    def league(self, league_id: int, season: int | None = None) -> dict:
        params = {"id": league_id}
        if season is not None:
            params["season"] = season
        return self._get("leagues", params)

    def fixtures(self, league_id: int, season: int) -> dict:
        return self._get("fixtures", {"league": league_id, "season": season})

    def fixture(self, fixture_id: int) -> dict:
        return self._get("fixtures", {"id": fixture_id})

    def fixture_events(self, fixture_id: int) -> dict:
        return self._get("fixtures/events", {"fixture": fixture_id})

    def fixture_lineups(self, fixture_id: int) -> dict:
        return self._get("fixtures/lineups", {"fixture": fixture_id})

    def fixture_statistics(self, fixture_id: int) -> dict:
        return self._get("fixtures/statistics", {"fixture": fixture_id})

    def teams(self, league_id: int, season: int) -> dict:
        return self._get("teams", {"league": league_id, "season": season})

    def rounds(self, league_id: int, season: int) -> dict:
        return self._get("fixtures/rounds", {"league": league_id, "season": season})

    def leagues(self, country: str = "Colombia") -> dict:
        return self._get("leagues", {"country": country})

    def standings(self, league_id: int, season: int) -> dict:
        return self._get("standings", {"league": league_id, "season": season})
