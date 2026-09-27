"""Explicit account diagnostics and an idempotent Colombian setup.

Reading status never calls the provider. An administrator can explicitly check an
account even while imports are paused; these bounded requests share the same
budget as the worker. No credential or account identity enters a snapshot.
"""

import hashlib
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from src import database
from src.api.dependencies import get_session, verificar_token
from src.models import ProviderSnapshot
from src.providers.api_football import APIFootballClient, ProviderError
from src.providers.automation import _snapshot
from src.providers.diagnostics import diagnostic_transport
from src.sync.models import SyncScope
from src.sync.service import (
    PermanentError,
    QuotaExhausted,
    SyncEngine,
    control,
    history,
    now,
)

router = APIRouter(prefix="/providers/api-football", dependencies=[Depends(verificar_token)])
PROVIDER = "api-football"


def snapshot(session, kind):
    return session.exec(
        select(ProviderSnapshot).where(
            ProviderSnapshot.provider == PROVIDER,
            ProviderSnapshot.entity_type == "connection",
            ProviderSnapshot.local_id == 1,
            ProviderSnapshot.kind == kind,
        )
    ).first()


def credential_fingerprint():
    key = APIFootballClient().api_key
    return hashlib.sha256(key.encode()).hexdigest() if key else None


def current_state(session):
    fingerprint = credential_fingerprint()
    account_row = snapshot(session, "status")
    account = dict(account_row.payload) if account_row else {}
    same_key = account.pop("credential_fingerprint", None) == fingerprint and bool(fingerprint)
    if not same_key:
        account = {}
    coverage = snapshot(session, "coverage") if same_key else None
    scopes = session.exec(select(SyncScope).where(SyncScope.provider == PROVIDER)).all()
    return {
        "configured": bool(fingerprint),
        "state": "missing_key"
        if not fingerprint
        else "error"
        if account.get("last_error")
        else "connected"
        if account.get("active") is True
        else "unchecked",
        "checked_at": account.get("checked_at"),
        "last_error": account.pop("last_error", None),
        "account": account or None,
        "competitions": coverage.payload.get("competitions", []) if coverage else [],
        "profiles": [
            {
                "id": scope.id,
                "name": scope.name,
                "kind": scope.kind,
                "selector": scope.selector,
                "mode": scope.mode,
                "last_checked_at": scope.last_checked_at,
            }
            for scope in scopes
            if not scope.selector.get("connection_diagnostic")
        ],
        "global_mode": control(session).mode,
    }


@router.get("/connection")
def connection(session: Session = Depends(get_session)):
    result = current_state(session)
    session.commit()
    return result


def diagnostic_scope(session):
    scopes = session.exec(select(SyncScope).where(SyncScope.provider == PROVIDER)).all()
    scope = next((row for row in scopes if row.selector.get("connection_diagnostic")), None)
    if scope is None:
        if len(session.exec(select(SyncScope.id)).all()) >= 50:
            raise HTTPException(
                409, "Revisa los perfiles existentes antes de comprobar otra fuente."
            )
        scope = SyncScope(
            name="API-Football · comprobación de cuenta",
            provider=PROVIDER,
            kind="discovery",
            mode="paused",
            selector={"country": "Colombia", "connection_diagnostic": True},
        )
        session.add(scope)
        session.flush()
    return scope


def safe_account(payload, instant, fingerprint):
    raw = payload.get("response")
    if not isinstance(raw, dict):
        raise ProviderError("La fuente no devolvió el estado de la cuenta.", retryable=False)
    subscription, requests = raw.get("subscription") or {}, raw.get("requests") or {}
    if not isinstance(subscription, dict) or not isinstance(requests, dict):
        raise ProviderError("La fuente no confirmó los datos de la suscripción.", retryable=False)
    limit, used = requests.get("limit_day"), requests.get("current")
    if type(limit) is not int or limit < 1 or type(used) is not int or used < 0:
        raise ProviderError("La fuente no confirmó una cuota válida.", retryable=False)
    return {
        "plan": str(subscription.get("plan") or "Sin identificar")[:80],
        "active": subscription.get("active") is True,
        "requests_current": used,
        "requests_limit_day": limit,
        "minute_limit": 10,
        "checked_at": instant.isoformat(),
        "credential_fingerprint": fingerprint,
        "last_error": None
        if subscription.get("active") is True
        else "La suscripción no está activa.",
    }


def safe_coverage(payload):
    if (payload.get("paging") or {}).get("total", 1) > 1:
        raise ProviderError("La lista de competiciones llegó incompleta.", retryable=False)
    competitions = []
    for row in payload.get("response", []):
        if not isinstance(row, dict):
            raise ProviderError("La cobertura recibida no es válida.", retryable=False)
        league, country = row.get("league") or {}, row.get("country") or {}
        if not isinstance(league, dict) or not isinstance(country, dict):
            raise ProviderError("La cobertura recibida no es válida.", retryable=False)
        if country.get("name") != "Colombia" or type(league.get("id")) is not int:
            continue
        competitions.append(
            {
                "league_id": league["id"],
                "name": str(league.get("name") or league["id"])[:150],
                "type": league.get("type"),
                "country": "Colombia",
                "seasons": [
                    {
                        key: season.get(key)
                        for key in ("year", "current", "start", "end", "coverage")
                    }
                    for season in row.get("seasons", [])
                    if isinstance(season, dict) and type(season.get("year")) is int
                ],
            }
        )
    return competitions


def check_season_access(provider, competitions, account):
    """Published coverage is not account access: probe one current season."""
    candidates = [
        (row["league_id"], season["year"])
        for row in competitions
        for season in row["seasons"]
        if season.get("current") is True
    ]
    if not candidates:
        return
    league, year = candidates[0]
    account["access_checked_at"] = account["checked_at"]
    account["access_probe"] = {"league_id": league, "season": year}
    try:
        provider.fixtures(league, year)
    except ProviderError as exc:
        if getattr(exc, "code", None) != "plan":
            raise
        account["current_access"] = False
        account["allowed_seasons"] = getattr(exc, "allowed_seasons", None)
    else:
        account["current_access"] = True
        account["allowed_seasons"] = None


@router.post("/check")
def check_connection(actor=Depends(verificar_token), session: Session = Depends(get_session)):
    fingerprint = credential_fingerprint()
    if not fingerprint:
        raise HTTPException(409, "Guarda API_FOOTBALL_KEY en .env y actualiza los contenedores.")
    control(session, lock=True)
    instant = now(session)
    lease = snapshot(session, "check")
    retry_at = datetime.fromisoformat(lease.payload["retry_at"]) if lease else None
    if retry_at and retry_at > instant:
        raise HTTPException(429, "Espera un minuto antes de volver a comprobar la cuenta.")
    scope_id = diagnostic_scope(session).id
    _snapshot(
        session,
        PROVIDER,
        "connection",
        1,
        "check",
        {"retry_at": (instant + timedelta(seconds=90)).isoformat()},
    )
    history(session, actor, "provider_connection_check", scope_id)
    session.commit()

    engine = SyncEngine(database.engine)
    account, competitions, error = None, None, None
    try:
        with diagnostic_transport(scope_id, actor) as transport:
            provider = APIFootballClient(transport=transport)
            account = safe_account(provider.status(), instant, fingerprint)
            engine.report_quota(
                scope_id,
                provider=PROVIDER,
                limit_day=account["requests_limit_day"],
                remaining_day=max(0, account["requests_limit_day"] - account["requests_current"]),
                finalize_request=False,
            )
            if account["active"]:
                competitions = safe_coverage(provider.leagues("Colombia"))
                check_season_access(provider, competitions, account)
    except QuotaExhausted:
        error = "No hay presupuesto disponible para comprobar la fuente. Revisa el consumo y la próxima disponibilidad."
    except (ProviderError, PermanentError, httpx.HTTPError):
        error = "No se pudo comprobar la cuenta o su cobertura. Revisa la clave, la suscripción y la cuota en API-Football."
    if account is None:
        account = {"checked_at": instant.isoformat(), "credential_fingerprint": fingerprint}
    if error:
        account["last_error"] = error
    control(session, lock=True)
    quota = snapshot(session, "quota")
    minute_limit = (quota.payload if quota else {}).get("limit_minute")
    if type(minute_limit) is int and minute_limit > 0:
        account["minute_limit"] = minute_limit
    _snapshot(session, PROVIDER, "connection", 1, "status", account)
    if competitions is not None:
        _snapshot(session, PROVIDER, "connection", 1, "coverage", {"competitions": competitions})
    else:
        _snapshot(session, PROVIDER, "connection", 1, "coverage", {"competitions": []})
    session.commit()
    return current_state(session)


class Selection(BaseModel):
    league_id: int = Field(gt=0)
    season: int = Field(ge=1900, le=2200)


class PrepareInput(BaseModel):
    selections: list[Selection] = Field(min_length=1, max_length=10)
    include_details: bool = True


@router.post("/prepare")
def prepare_colombia(
    payload: PrepareInput, actor=Depends(verificar_token), session: Session = Depends(get_session)
):
    control(session, lock=True)
    state = current_state(session)
    if state["state"] != "connected":
        raise HTTPException(409, "Comprueba la cuenta antes de preparar sus importaciones.")
    checked = datetime.fromisoformat(state["checked_at"])
    if now(session) - checked > timedelta(days=1):
        raise HTTPException(409, "Vuelve a comprobar la conexión para actualizar la cobertura.")
    advertised = {
        (row["league_id"], season["year"]): (row, season)
        for row in state["competitions"]
        for season in row["seasons"]
    }
    for selection in payload.selections:
        allowed = (state.get("account") or {}).get("allowed_seasons")
        if allowed and selection.season not in allowed:
            raise HTTPException(
                422, "Tu plan no permite esa temporada. Elige uno de los años habilitados."
            )
        if (selection.league_id, selection.season) not in advertised:
            raise HTTPException(
                422, "La competición y temporada no figuran en la cobertura comprobada."
            )
    scopes = session.exec(select(SyncScope)).all()
    ids, created = [], []
    for selection in payload.selections:
        league, season = advertised[(selection.league_id, selection.season)]
        kinds = ["fixtures"]
        coverage = (season.get("coverage") or {}).get("fixtures") or {}
        if (season.get("coverage") or {}).get("standings") is True:
            kinds.append("standings_batch")
        if payload.include_details and any(
            coverage.get(key) is True for key in ("events", "lineups", "statistics_fixtures")
        ):
            kinds.append("details_batch")
        for kind in kinds:
            scope = next(
                (
                    row
                    for row in scopes
                    if row.provider == PROVIDER
                    and row.kind == kind
                    and row.selector.get("league_id") == selection.league_id
                    and row.selector.get("season") == selection.season
                    and not row.selector.get("round_prefix")
                ),
                None,
            )
            if scope is None:
                if len(scopes) >= 50:
                    raise HTTPException(
                        409, "El límite de perfiles está completo. Revisa los existentes."
                    )
                scope = SyncScope(
                    name=f"{league['name']} · {selection.season} · { {'fixtures': 'Calendario', 'standings_batch': 'Clasificaciones', 'details_batch': 'Detalles de partidos'}[kind] }"[
                        :120
                    ],
                    provider=PROVIDER,
                    kind=kind,
                    mode="paused",
                    interval_seconds=3600 if kind == "fixtures" else 300,
                    selector={
                        "league_id": selection.league_id,
                        "season": selection.season,
                        "coverage_status": "access_unverified",
                        "coverage": coverage,
                    },
                )
                session.add(scope)
                session.flush()
                scopes.append(scope)
                created.append(scope.id)
                history(
                    session,
                    actor,
                    "scope_prepared",
                    scope.id,
                    reason="Selección de cobertura colombiana; el acceso a la temporada se verifica al importar.",
                )
            if scope.id not in ids:
                ids.append(scope.id)
    session.commit()
    return {"scope_ids": ids, "created": len(created), "connection": current_state(session)}
