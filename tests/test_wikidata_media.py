import copy

import httpx
import pytest

from src.providers import ProviderError, WikidataClient
from src.providers import wikidata as wikidata_module


def statement(filename, rank="normal"):
    return {"rank": rank, "mainsnak": {"datavalue": {"value": filename}}}


@pytest.fixture
def media_source(monkeypatch):
    wikidata_module._media_cache.clear()
    entity = {
        "labels": {"es": {"value": "Club de prueba"}},
        "claims": {
            "P154": [statement("Old.svg", "deprecated"), statement("Escudo de prueba.svg")],
            "P18": [statement("Team photo.jpg")],
        },
    }
    info = {
        "url": "https://upload.wikimedia.org/wikipedia/commons/a/ab/Badge.svg",
        "thumburl": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Badge.svg/384px-Badge.svg.png",
        "mime": "image/svg+xml",
        "width": 320,
        "height": 400,
        "extmetadata": {
            "Artist": {"value": '<a href="https://example.test">Club &amp; autor</a>'},
            "Credit": {"value": "<p>Club de prueba</p>"},
            "LicenseShortName": {"value": "CC BY-SA 4.0"},
            "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0/"},
            "AttributionRequired": {"value": "true"},
        },
    }
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        payload = (
            {"entities": {"Q123": copy.deepcopy(entity)}}
            if "EntityData" in url
            else {"query": {"pages": [{"imageinfo": [copy.deepcopy(info)]}]}}
        )
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", get)
    yield entity, info, calls
    wikidata_module._media_cache.clear()


def test_badge_preview_prefers_logo_sanitizes_metadata_and_reuses_bounded_cache(media_source):
    _entity, _info, calls = media_source
    client = WikidataClient()
    result = client.commons_media("q123", purpose="crest")
    assert result["filename"] == "Escudo de prueba.svg"
    assert result["property"] == "P154"
    assert result["entity_name"] == "Club de prueba"
    assert result["author"] == "Club & autor"
    assert result["can_use_as_logo"] is True
    assert "%20" not in result["source_url"]  # Commons uses underscores for spaces.
    assert calls[1][1]["params"]["titles"] == "File:Escudo de prueba.svg"
    assert calls[1][1]["params"]["iiurlwidth"] == 384
    result["filename"] = "Mutation must not affect cache"
    assert client.commons_media("Q123", purpose="crest")["filename"] == "Escudo de prueba.svg"
    assert len(calls) == 2


def test_badge_is_not_replaced_by_a_team_photograph(media_source):
    entity, _info, calls = media_source
    entity["claims"].pop("P154")
    with pytest.raises(ProviderError, match="no tiene un escudo"):
        WikidataClient().commons_media("Q123", purpose="crest")
    assert len(calls) == 1  # No speculative Commons search.
    assert WikidataClient().commons_media("Q123")["property"] == "P18"


def test_preferred_logo_wins_and_deprecated_logo_is_ignored(media_source):
    entity, _info, _calls = media_source
    entity["claims"]["P154"].append(statement("Current.svg", "preferred"))
    assert WikidataClient().commons_media("Q123", purpose="crest")["filename"] == "Current.svg"


def test_expired_media_cache_fetches_again(media_source, monkeypatch):
    _entity, _info, calls = media_source
    now = [1]
    monkeypatch.setattr(wikidata_module.time, "monotonic", lambda: now[0])
    WikidataClient().commons_media("Q123", purpose="crest")
    now[0] += wikidata_module.MEDIA_CACHE_SECONDS + 1
    WikidataClient().commons_media("Q123", purpose="crest")
    assert len(calls) == 4


def test_metadata_does_not_expose_executable_links_or_unlicensed_badge(media_source):
    _entity, info, _calls = media_source
    info["extmetadata"]["LicenseUrl"]["value"] = "javascript:alert(1)"
    info["extmetadata"].pop("LicenseShortName")
    info["thumburl"] = "https://other.example.test/fake.svg"
    result = WikidataClient().commons_media("Q123", purpose="crest")
    assert result["license_url"] is None
    assert result["thumbnail_url"] is None
    assert result["can_use_as_logo"] is False


def test_external_file_url_is_not_accepted_as_commons(media_source):
    _entity, info, _calls = media_source
    info["url"] = "https://other.example.test/fake.svg"
    with pytest.raises(ProviderError, match="imagen válida"):
        WikidataClient().commons_media("Q123", purpose="crest")


def test_commons_rate_limit_is_reported_without_retries(media_source, monkeypatch):
    calls = []
    monkeypatch.setattr(WikidataClient, "entity", lambda *_: media_source[0])

    def limited(url, **kwargs):
        calls.append(url)
        return httpx.Response(429, headers={"Retry-After": "60"}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", limited)
    with pytest.raises(ProviderError, match="pide esperar"):
        WikidataClient().commons_media("Q123", purpose="crest")
    assert len(calls) == 1 and not wikidata_module._media_cache


def badge_import(client, kind, entity_id, **params):
    return client.post(
        f"/providers/wikidata/import-media/{kind}/{entity_id}/Q123",
        params={"use_as_logo": True, "preview_filename": "Escudo de prueba.svg", **params},
    )


def test_preview_is_read_only_and_import_fills_empty_logo_with_attribution(
    authenticated, media_source
):
    conf = authenticated.post(
        "/confederaciones/", json={"nombre": "Confederación", "logo": ""}
    ).json()
    preview = authenticated.get("/providers/wikidata/preview/Q123/media?purpose=crest")
    assert preview.status_code == 200
    assert authenticated.get("/media/").json() == []
    assert authenticated.get("/providers/mappings/").json() == []

    def saved_conf():
        return next(
            item
            for item in authenticated.get("/confederaciones/").json()
            if item["id"] == conf["id"]
        )

    assert saved_conf()["logo"] == ""

    imported = badge_import(authenticated, "confederation", conf["id"])
    assert imported.status_code == 200, imported.text
    assert imported.json()["tipo"] == "escudo"
    assert saved_conf()["logo"] == preview.json()["original_url"]
    assert len(media_source[2]) == 2  # Confirmation reuses exactly the reviewed observation.
    again = badge_import(authenticated, "confederation", conf["id"])
    assert again.json()["id"] == imported.json()["id"]
    authenticated.post("/logout")
    public = authenticated.get("/public/crests/")
    assert public.status_code == 200
    assert public.json()[0]["author"] == "Club & autor"
    assert public.json()[0]["license"] == "CC BY-SA 4.0"
    assert len(public.json()) == 1


def test_badge_import_preserves_manual_logo_and_public_excludes_unused_assets(
    authenticated, catalog, media_source
):
    team = catalog["teams"][0]
    result = badge_import(authenticated, "team", team["id"])
    assert result.status_code == 200
    after = next(item for item in authenticated.get("/equipos/").json() if item["id"] == team["id"])
    assert after["logo"] == team["logo"]
    assert authenticated.get("/public/crests/").json() == []


@pytest.mark.parametrize("preview_filename", [None, "Different file.svg"])
def test_badge_import_requires_review_of_same_file(
    authenticated, catalog, media_source, preview_filename
):
    result = badge_import(
        authenticated, "team", catalog["teams"][0]["id"], preview_filename=preview_filename
    )
    assert result.status_code in {400, 409}
    assert authenticated.get("/media/").json() == []
    assert authenticated.get("/providers/mappings/").json() == []


def test_badge_import_requires_license_metadata(authenticated, catalog, media_source):
    media_source[1]["extmetadata"].pop("LicenseShortName")
    result = badge_import(authenticated, "team", catalog["teams"][0]["id"])
    assert result.status_code == 400
    assert authenticated.get("/media/").json() == []


def test_badge_import_cannot_change_existing_wikidata_identity(
    authenticated, catalog, media_source
):
    team = catalog["teams"][0]
    authenticated.post(
        "/providers/mappings/",
        json={
            "provider": "wikidata",
            "entity_type": "team",
            "local_id": team["id"],
            "external_id": "Q456",
        },
    )
    result = badge_import(authenticated, "team", team["id"])
    assert result.status_code == 409
    assert authenticated.get("/media/").json() == []
