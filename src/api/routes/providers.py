import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from src.api.dependencies import get_session, verificar_token
from src.api.persistence import save
from src.audit.service import record_change
from src.football.entities import ENTITY_MODELS
from src.models import (
    EntityRevision,
    MediaAsset,
    MediaAssetBase,
    MediaAssetRead,
    ProviderMapping,
    ProviderMappingBase,
    ProviderMappingRead,
    ProviderSnapshot,
    ProviderSnapshotRead,
    Temporada,
)
from src.providers import APIFootballClient, ProviderError, ProviderNotConfigured, WikidataClient
from src.providers.connection import diagnostic_scope
from src.providers.diagnostics import diagnostic_transport
from src.sync.models import SyncNotification, SyncScope
from src.sync.service import PermanentError, QuotaExhausted, SyncError, control, enqueue, history

router = APIRouter(dependencies=[Depends(verificar_token)])


def _audit_reference(session, entity_type, entity_id, *, field, before, after, action, reason):
    """Record an identity/media decision against the canonical entity version."""
    from src.security import get_auth_settings

    # Callers take the global synchronization lock before any entity locks.
    model = ENTITY_MODELS.get(entity_type)
    if model:
        session.exec(select(model).where(model.id == entity_id).with_for_update()).first()
    revision = session.get(EntityRevision, (entity_type, entity_id))
    if revision is None:
        revision = EntityRevision(entity_type=entity_type, entity_id=entity_id)
    else:
        session.refresh(revision)
    revision.version += 1
    session.add(revision)
    request = session.info.get("request")
    actor = (getattr(request.state, "actor", None) if request else None) or session.info.get(
        "actor"
    )
    record_change(
        session,
        entity_type=entity_type,
        entity_id=entity_id,
        field=field,
        before=before,
        after=after,
        action=action,
        actor=actor or get_auth_settings().admin_username,
        reason=reason,
        version=revision.version,
    )
    session.add(
        SyncNotification(
            topic="matches"
            if entity_type in {"match", "event", "lineup", "statistics"}
            else "catalog",
            payload={"entity_type": entity_type, "entity_id": entity_id},
        )
    )


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


def _api_football_preview(session, actor, call):
    if not APIFootballClient().configured:
        raise HTTPException(503, "Configura API_FOOTBALL_KEY para consultar API-Football.")
    control(session, lock=True)
    scope_id = diagnostic_scope(session).id
    history(session, actor, "provider_preview", scope_id)
    session.commit()
    try:
        with diagnostic_transport(scope_id, actor) as transport:
            return provider_response(lambda: call(APIFootballClient(transport=transport)))
    except QuotaExhausted as exc:
        raise HTTPException(
            429,
            "La fuente está en pausa por su cuota. Espera antes de volver a consultar.",
            headers={"Retry-After": str(max(1, int(exc.retry_after or 60)))},
        ) from exc
    except PermanentError as exc:
        raise HTTPException(502, str(exc)) from exc


@router.get("/providers/api-football/preview/league/{league_id}")
def preview_api_football_league(
    league_id: int,
    season: int | None = None,
    session: Session = Depends(get_session),
    actor=Depends(verificar_token),
):
    return _api_football_preview(session, actor, lambda client: client.league(league_id, season))


@router.get("/providers/api-football/preview/fixtures")
def preview_api_football_fixtures(
    league_id: int,
    season: int,
    session: Session = Depends(get_session),
    actor=Depends(verificar_token),
):
    return _api_football_preview(session, actor, lambda client: client.fixtures(league_id, season))


@router.get("/providers/api-football/preview/fixture/{fixture_id}")
def preview_api_football_fixture(
    fixture_id: int,
    session: Session = Depends(get_session),
    actor=Depends(verificar_token),
):
    return _api_football_preview(session, actor, lambda client: client.fixture(fixture_id))


@router.get("/providers/api-football/preview/teams")
def preview_api_football_teams(
    league_id: int,
    season: int,
    session: Session = Depends(get_session),
    actor=Depends(verificar_token),
):
    return _api_football_preview(session, actor, lambda client: client.teams(league_id, season))


@router.get("/providers/api-football/preview/rounds")
def preview_api_football_rounds(
    league_id: int,
    season: int,
    session: Session = Depends(get_session),
    actor=Depends(verificar_token),
):
    return _api_football_preview(session, actor, lambda client: client.rounds(league_id, season))


@router.get("/providers/wikidata/preview/{qid}")
def preview_wikidata_item(qid: str):
    try:
        return WikidataClient().entity(qid)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/providers/wikidata/preview/{qid}/media")
def preview_wikidata_media(qid: str, purpose: str = "image"):
    try:
        return WikidataClient().commons_media(qid, purpose=purpose)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post(
    "/providers/wikidata/import-media/{entity_type}/{local_id}/{qid}",
    response_model=MediaAssetRead,
)
def import_wikidata_media(
    entity_type: str,
    local_id: int,
    qid: str,
    use_as_logo: bool = False,
    preview_filename: str | None = None,
    session: Session = Depends(get_session),
):
    validar_entidad_generica(entity_type, local_id, session)
    if use_as_logo and entity_type not in {"team", "competition", "confederation"}:
        raise HTTPException(status_code=400, detail="Esta ficha no admite un escudo.")
    if use_as_logo and not preview_filename:
        raise HTTPException(
            status_code=400, detail="Primero busca el escudo y revisa su imagen y licencia."
        )

    try:
        client = WikidataClient()
        media = (
            client.commons_media(qid, purpose="crest") if use_as_logo else client.commons_media(qid)
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not media.get("original_url"):
        raise HTTPException(status_code=502, detail="Commons no devolvió una URL de archivo.")
    if preview_filename and preview_filename != media.get("filename"):
        raise HTTPException(
            status_code=409,
            detail="La imagen disponible cambió. Vuelve a buscarla y revisarla antes de guardar.",
        )
    if use_as_logo and (media.get("property") != "P154" or not media.get("license")):
        raise HTTPException(
            status_code=400, detail="No hay un escudo con licencia identificada para esta ficha."
        )

    control(session, lock=True)
    model = ENTITY_MODELS[entity_type]
    item = session.exec(select(model).where(model.id == local_id).with_for_update()).first()
    if not item:
        raise HTTPException(status_code=404, detail="Entidad local no encontrada")

    normalized_qid = qid.upper()
    other_mapping = session.exec(
        select(ProviderMapping).where(
            ProviderMapping.provider == "wikidata",
            ProviderMapping.entity_type == entity_type,
            ProviderMapping.local_id == local_id,
            ProviderMapping.external_id != normalized_qid,
        )
    ).first()
    if other_mapping:
        raise HTTPException(
            status_code=409,
            detail="Esta ficha ya está conectada a otra identidad de Wikidata. Revisa el vínculo.",
        )
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
        mapping = ProviderMapping(
            provider="wikidata",
            entity_type=entity_type,
            local_id=local_id,
            external_id=normalized_qid,
            source_url=f"https://www.wikidata.org/wiki/{normalized_qid}",
            verified_at=datetime.datetime.now(datetime.timezone.utc),
        )
        session.add(mapping)
        _audit_reference(
            session,
            entity_type,
            local_id,
            field="provider_mapping",
            before=None,
            after=mapping.model_dump(mode="json", exclude={"id"}),
            action="identity_link",
            reason="Vínculo confirmado al importar un recurso de Wikimedia Commons",
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
        "tipo": "escudo" if media.get("property") == "P154" else "imagen_principal",
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

    before_asset = asset.model_dump(mode="json") if asset else None
    asset_changed = asset is None or any(
        key != "verified_at" and getattr(asset, key) != value for key, value in values.items()
    )
    if asset:
        for key, value in values.items():
            setattr(asset, key, value)
    else:
        asset = MediaAsset(
            entity_type=entity_type,
            entity_id=local_id,
            **values,
        )
    if asset_changed:
        _audit_reference(
            session,
            entity_type,
            local_id,
            field="media",
            before=before_asset,
            after=asset.model_dump(mode="json", exclude={"id"}),
            action="media_import",
            reason="Recurso y atribución revisados desde la administración",
        )
    if use_as_logo and not item.logo.strip():
        item.logo = media["original_url"]
        session.add(item)
    return save(session, asset)


def _queue_sync(session, kind, selector, name):
    settings = control(session, lock=True)
    if settings.mode == "paused":
        raise HTTPException(
            409, "La automatización está pausada. Actívala en Datos antes de actualizar."
        )
    scope = next(
        (
            row
            for row in session.exec(
                select(SyncScope).where(
                    SyncScope.provider == "api-football", SyncScope.kind == kind
                )
            ).all()
            if row.selector == selector
        ),
        None,
    )
    if scope is None:
        scope = SyncScope(
            name=name,
            provider="api-football",
            kind=kind,
            selector=selector,
            mode="automatic",
            interval_seconds=86400,
        )
        session.add(scope)
        session.flush()
    try:
        job = enqueue(session, scope, actor=session.info.get("actor") or "administrator")
    except SyncError as exc:
        raise HTTPException(409, str(exc)) from exc
    session.commit()
    session.refresh(job)
    return {
        "queued": True,
        "job_id": job.id,
        "scope_id": scope.id,
        "status": job.status,
        "message": "Actualización en cola. Consulta su progreso en Automatización.",
    }


@router.post(
    "/providers/api-football/sync/competition/{competition_id}/season/{season_id}", status_code=202
)
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

    return _queue_sync(
        session,
        "fixtures",
        {
            "league_id": league_id,
            "season": season_year,
            "competition_id": competition_id,
            "season_id": season_id,
            "existing_only": True,
        },
        f"Partidos de la edición {season_id}",
    )


@router.post("/providers/api-football/sync/match/{match_id}", status_code=202)
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

    return _queue_sync(
        session,
        "detail",
        {"match_id": match_id, "fixture_id": fixture_id},
        f"Detalle del partido {match_id}",
    )


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
    control(session, lock=True)
    if (
        mapping_in.provider == "api-football"
        and mapping_in.entity_type == "season"
        and not mapping_in.external_scope
    ):
        season = session.get(Temporada, mapping_in.local_id)
        parent = session.exec(
            select(ProviderMapping).where(
                ProviderMapping.provider == "api-football",
                ProviderMapping.entity_type == "competition",
                ProviderMapping.local_id == season.competicion_id,
            )
        ).first()
        if not parent:
            raise HTTPException(400, "Conecta primero la competición con la fuente.")
        mapping_in.external_scope = f"league:{parent.external_id}"
    existing = session.exec(
        select(ProviderMapping).where(
            ProviderMapping.provider == mapping_in.provider,
            ProviderMapping.entity_type == mapping_in.entity_type,
            ProviderMapping.external_id == mapping_in.external_id,
            ProviderMapping.external_scope == mapping_in.external_scope,
        )
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Ese identificador externo ya está vinculado")

    mapping = ProviderMapping.model_validate(mapping_in)
    _audit_reference(
        session,
        mapping.entity_type,
        mapping.local_id,
        field="provider_mapping",
        before=None,
        after=mapping.model_dump(mode="json", exclude={"id"}),
        action="identity_link",
        reason="Vínculo confirmado desde administración",
    )
    return save(session, mapping)


@router.delete("/providers/mappings/{mapping_id}")
def eliminar_provider_mapping(mapping_id: int, session: Session = Depends(get_session)):
    settings = control(session, lock=True)
    if settings.mode != "paused":
        raise HTTPException(409, "Pausa la automatización antes de retirar una identidad externa.")
    mapping = session.exec(
        select(ProviderMapping).where(ProviderMapping.id == mapping_id).with_for_update()
    ).first()
    if mapping is None:
        raise HTTPException(404, "Vínculo no encontrado")
    _audit_reference(
        session,
        mapping.entity_type,
        mapping.local_id,
        field="provider_mapping",
        before=mapping.model_dump(mode="json"),
        after=None,
        action="identity_unlink",
        reason="Vínculo retirado desde administración; la ficha canónica se conserva",
    )
    session.delete(mapping)
    session.commit()
    return {"ok": True}


@router.get("/providers/mappings/", response_model=list[ProviderMappingRead])
def leer_provider_mappings(session: Session = Depends(get_session)):
    return session.exec(select(ProviderMapping)).all()


@router.post("/media/", response_model=MediaAssetRead)
def crear_media_asset(asset_in: MediaAssetBase, session: Session = Depends(get_session)):
    validar_entidad_generica(asset_in.entity_type, asset_in.entity_id, session)
    control(session, lock=True)
    asset = MediaAsset.model_validate(asset_in)
    _audit_reference(
        session,
        asset.entity_type,
        asset.entity_id,
        field="media",
        before=None,
        after=asset.model_dump(mode="json", exclude={"id"}),
        action="media_create",
        reason="Recurso visual registrado desde administración",
    )
    return save(session, asset)


@router.get("/media/", response_model=list[MediaAssetRead])
def leer_media_assets(session: Session = Depends(get_session)):
    return session.exec(select(MediaAsset)).all()
