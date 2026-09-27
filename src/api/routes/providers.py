import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from src.api.dependencies import get_session, verificar_token
from src.api.persistence import save
from src.models import (
    Competicion,
    Confederacion,
    Equipo,
    Estadio,
    Fase,
    Jugador,
    MediaAsset,
    MediaAssetBase,
    MediaAssetRead,
    Partido,
    ProviderMapping,
    ProviderMappingBase,
    ProviderMappingRead,
    ProviderSnapshot,
    ProviderSnapshotRead,
    Temporada,
)
from src.providers import APIFootballClient, ProviderError, ProviderNotConfigured, WikidataClient
from src.providers.sync import SyncConfigurationError, sync_competition_fixtures, sync_match_detail

router = APIRouter(dependencies=[Depends(verificar_token)])

ENTITY_MODELS = {
    "confederation": Confederacion,
    "competition": Competicion,
    "team": Equipo,
    "match": Partido,
    "season": Temporada,
    "stage": Fase,
    "venue": Estadio,
    "player": Jugador,
}


def validar_entidad_generica(entity_type: str, local_id: int, session: Session) -> None:
    model = ENTITY_MODELS.get(entity_type)
    if not model:
        raise HTTPException(
            status_code=400,
            detail="entity_type no soportado. Usa confederation, competition, team, match, season, stage, venue o player.",
        )
    if not session.get(model, local_id):
        raise HTTPException(status_code=404, detail="Entidad local no encontrada")


def provider_response(callable_):
    try:
        return callable_()
    except ProviderNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/providers/api-football/status")
def api_football_status():
    client = APIFootballClient()
    return {
        "provider": "api-football",
        "configured": client.configured,
        "base_url": client.base_url,
    }


@router.get("/providers/api-football/preview/league/{league_id}")
def preview_api_football_league(league_id: int, season: int | None = None):
    client = APIFootballClient()
    return provider_response(lambda: client.league(league_id, season))


@router.get("/providers/api-football/preview/fixtures")
def preview_api_football_fixtures(league_id: int, season: int):
    client = APIFootballClient()
    return provider_response(lambda: client.fixtures(league_id, season))


@router.get("/providers/api-football/preview/fixture/{fixture_id}")
def preview_api_football_fixture(fixture_id: int):
    client = APIFootballClient()
    return provider_response(lambda: client.fixture(fixture_id))


@router.get("/providers/api-football/preview/teams")
def preview_api_football_teams(league_id: int, season: int):
    client = APIFootballClient()
    return provider_response(lambda: client.teams(league_id, season))


@router.get("/providers/api-football/preview/rounds")
def preview_api_football_rounds(league_id: int, season: int):
    client = APIFootballClient()
    return provider_response(lambda: client.rounds(league_id, season))


@router.get("/providers/wikidata/preview/{qid}")
def preview_wikidata_item(qid: str):
    try:
        return WikidataClient().entity(qid)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/providers/wikidata/preview/{qid}/media")
def preview_wikidata_media(qid: str):
    try:
        return WikidataClient().commons_media(qid)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post(
    "/providers/wikidata/import-media/{entity_type}/{local_id}/{qid}",
    response_model=MediaAssetRead,
)
def import_wikidata_media(
    entity_type: str, local_id: int, qid: str, session: Session = Depends(get_session)
):
    validar_entidad_generica(entity_type, local_id, session)

    try:
        media = WikidataClient().commons_media(qid)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not media.get("original_url"):
        raise HTTPException(status_code=502, detail="Commons no devolvió una URL de archivo.")

    normalized_qid = qid.upper()
    mapping = session.exec(
        select(ProviderMapping).where(
            ProviderMapping.provider == "wikidata",
            ProviderMapping.entity_type == entity_type,
            ProviderMapping.external_id == normalized_qid,
        )
    ).first()
    if mapping and mapping.local_id != local_id:
        raise HTTPException(
            status_code=409,
            detail="Ese QID de Wikidata ya está vinculado a otra entidad local.",
        )
    if not mapping:
        session.add(
            ProviderMapping(
                provider="wikidata",
                entity_type=entity_type,
                local_id=local_id,
                external_id=normalized_qid,
                source_url=f"https://www.wikidata.org/wiki/{normalized_qid}",
                verified_at=datetime.datetime.now(datetime.timezone.utc),
            )
        )

    asset = session.exec(
        select(MediaAsset).where(
            MediaAsset.entity_type == entity_type,
            MediaAsset.entity_id == local_id,
            MediaAsset.source == "wikimedia-commons",
            MediaAsset.remote_id == media.get("filename"),
        )
    ).first()
    values = {
        "tipo": "imagen_principal",
        "source": "wikimedia-commons",
        "source_url": media.get("source_url"),
        "remote_id": media.get("filename"),
        "author": media.get("author"),
        "license": media.get("license"),
        "license_url": media.get("license_url"),
        "credit": media.get("credit"),
        "original_url": media["original_url"],
        "width": media.get("width"),
        "height": media.get("height"),
        "mime_type": media.get("mime_type"),
        "verified_at": datetime.datetime.now(datetime.timezone.utc),
    }

    if asset:
        for key, value in values.items():
            setattr(asset, key, value)
    else:
        asset = MediaAsset(
            entity_type=entity_type,
            entity_id=local_id,
            **values,
        )
    return save(session, asset)


@router.post("/providers/api-football/sync/competition/{competition_id}/season/{season_id}")
def sync_api_football_competition(
    competition_id: int, season_id: int, session: Session = Depends(get_session)
):
    competition_mapping = session.exec(
        select(ProviderMapping).where(
            ProviderMapping.provider == "api-football",
            ProviderMapping.entity_type == "competition",
            ProviderMapping.local_id == competition_id,
        )
    ).first()
    season_mapping = session.exec(
        select(ProviderMapping).where(
            ProviderMapping.provider == "api-football",
            ProviderMapping.entity_type == "season",
            ProviderMapping.local_id == season_id,
        )
    ).first()

    if not competition_mapping or not season_mapping:
        raise HTTPException(
            status_code=400,
            detail="Mapea primero la competición y la temporada con API-Football.",
        )

    try:
        league_id = int(competition_mapping.external_id)
        season_year = int(season_mapping.external_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Los mappings de competición y temporada deben usar IDs/años numéricos.",
        ) from exc

    client = APIFootballClient()
    payload = provider_response(lambda: client.fixtures(league_id, season_year))

    try:
        return sync_competition_fixtures(
            session,
            competition_id,
            season_id,
            payload,
        )
    except SyncConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/providers/api-football/sync/match/{match_id}")
def sync_api_football_match_detail(match_id: int, session: Session = Depends(get_session)):
    mapping = session.exec(
        select(ProviderMapping).where(
            ProviderMapping.provider == "api-football",
            ProviderMapping.entity_type == "match",
            ProviderMapping.local_id == match_id,
        )
    ).first()
    if not mapping:
        raise HTTPException(
            status_code=400,
            detail="El partido no tiene mapping de API-Football.",
        )

    try:
        fixture_id = int(mapping.external_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="El mapping del partido debe usar un fixture ID numérico.",
        ) from exc

    client = APIFootballClient()
    events_payload = provider_response(lambda: client.fixture_events(fixture_id))
    lineups_payload = provider_response(lambda: client.fixture_lineups(fixture_id))
    statistics_payload = provider_response(lambda: client.fixture_statistics(fixture_id))

    try:
        return sync_match_detail(
            session,
            match_id,
            events_payload=events_payload,
            lineups_payload=lineups_payload,
            statistics_payload=statistics_payload,
        )
    except SyncConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/providers/snapshots/", response_model=list[ProviderSnapshotRead])
def leer_provider_snapshots(
    provider: str | None = None,
    entity_type: str | None = None,
    local_id: int | None = None,
    session: Session = Depends(get_session),
):
    statement = select(ProviderSnapshot)
    if provider:
        statement = statement.where(ProviderSnapshot.provider == provider)
    if entity_type:
        statement = statement.where(ProviderSnapshot.entity_type == entity_type)
    if local_id is not None:
        statement = statement.where(ProviderSnapshot.local_id == local_id)
    return session.exec(statement).all()


@router.post("/providers/mappings/", response_model=ProviderMappingRead)
def crear_provider_mapping(
    mapping_in: ProviderMappingBase, session: Session = Depends(get_session)
):
    validar_entidad_generica(mapping_in.entity_type, mapping_in.local_id, session)
    existing = session.exec(
        select(ProviderMapping).where(
            ProviderMapping.provider == mapping_in.provider,
            ProviderMapping.entity_type == mapping_in.entity_type,
            ProviderMapping.external_id == mapping_in.external_id,
        )
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Ese identificador externo ya está vinculado")

    mapping = ProviderMapping.model_validate(mapping_in)
    return save(session, mapping)


@router.get("/providers/mappings/", response_model=list[ProviderMappingRead])
def leer_provider_mappings(session: Session = Depends(get_session)):
    return session.exec(select(ProviderMapping)).all()


@router.post("/media/", response_model=MediaAssetRead)
def crear_media_asset(asset_in: MediaAssetBase, session: Session = Depends(get_session)):
    validar_entidad_generica(asset_in.entity_type, asset_in.entity_id, session)
    asset = MediaAsset.model_validate(asset_in)
    return save(session, asset)


@router.get("/media/", response_model=list[MediaAssetRead])
def leer_media_assets(session: Session = Depends(get_session)):
    return session.exec(select(MediaAsset)).all()
