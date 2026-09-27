from sqlmodel import Session

from src import database
from src.models import ProviderMapping


def test_manual_and_imported_matches_have_distinct_public_sources(authenticated, match_payload):
    match = authenticated.post("/partidos/", json=match_payload).json()
    path = f"/public/partidos/{match['id']}"
    assert authenticated.get(path).json()["data_source"]["provider"] == "manual"
    with Session(database.engine) as session:
        session.add(
            ProviderMapping(
                provider="api-football",
                entity_type="match",
                local_id=match["id"],
                external_id="verified-test-123",
            )
        )
        session.commit()
    assert authenticated.get(path).json()["data_source"]["provider"] == "api-football"
    page = authenticated.get("/public/partidos/page").json()
    assert page["items"][0]["data_source"]["provider"] == "api-football"
