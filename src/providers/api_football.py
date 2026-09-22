import os

import httpx


class ProviderNotConfigured(RuntimeError):
    pass


class ProviderError(RuntimeError):
    pass


class APIFootballClient:
    base_url = "https://v3.football.api-sports.io"

    def __init__(self, api_key: str | None = None, timeout: float = 12.0):
        self.api_key = api_key or os.getenv("API_FOOTBALL_KEY")
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _get(self, path: str, params: dict | None = None) -> dict:
        if not self.api_key:
            raise ProviderNotConfigured("Configura API_FOOTBALL_KEY para consultar API-Football.")

        try:
            response = httpx.get(
                f"{self.base_url}/{path.lstrip('/')}",
                params=params,
                headers={
                    "x-apisports-key": self.api_key,
                    "Accept": "application/json",
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"API-Football no respondió correctamente: {exc}") from exc

        payload = response.json()
        errors = payload.get("errors")
        if errors:
            raise ProviderError(f"API-Football devolvió errores: {errors}")
        return payload

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
