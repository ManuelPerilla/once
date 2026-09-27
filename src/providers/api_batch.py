"""Bounded progressive match enrichment: one request for at most twenty fixtures."""

import datetime as dt
from collections import defaultdict

from sqlalchemy import or_
from sqlmodel import Session, select

from src import database
from src.models import EstadoPartido, Partido, ProviderMapping, ProviderSnapshot
from src.providers import APIFootballClient, ProviderError
from src.providers.sync import _snapshot, sync_competition_fixtures, sync_match_detail
from src.sync.handlers import FetchResult
from src.sync.service import PermanentError, issue


def fixture_season_ids(session, scope):
    league, year = int(scope.selector["league_id"]), int(scope.selector["season"])
    return session.exec(
        select(ProviderMapping.local_id).where(
            ProviderMapping.provider == "api-football",
            ProviderMapping.entity_type == "season",
            ProviderMapping.external_id == str(year),
            or_(
                ProviderMapping.external_scope == f"league:{league}",
                ProviderMapping.external_scope.startswith(f"league:{league}:edition:"),
            ),
        )
    ).all()


def fixture_dependencies_ready(scope):
    """Do not spend a request while canonical fixtures are still waiting on quota."""
    with Session(database.engine) as session:
        seasons = fixture_season_ids(session, scope)
        return (
            bool(seasons)
            and session.exec(
                select(Partido.id)
                .join(
                    ProviderMapping,
                    (ProviderMapping.local_id == Partido.id)
                    & (ProviderMapping.provider == "api-football")
                    & (ProviderMapping.entity_type == "match"),
                )
                .where(Partido.temporada_id.in_(seasons))
                .limit(1)
            ).first()
            is not None
        )


class BatchDetailsHandler:
    @staticmethod
    def _batch_size():
        # The free subscription rejects the ids parameter even for a one-item list.
        # Unknown/stale access remains conservative; a single fixture includes details.
        from src.sync.service import _connection_snapshot, effective_api_limits

        with Session(database.engine) as session:
            status = _connection_snapshot(session, "status")
            capability = _connection_snapshot(session, "batch_capability")
            limits = effective_api_limits(session)
            if (
                status is None
                or (
                    capability is not None
                    and capability.payload.get("allowed") is False
                    and capability.payload.get("plan") == status.payload.get("plan")
                )
                or str(status.payload.get("plan", "")).lower() == "free"
                or limits[0] <= 100
            ):
                return 1
            return 20

    @staticmethod
    def _pending(scope):
        with Session(database.engine) as session:
            season_ids = fixture_season_ids(session, scope)
            if not season_ids:
                return []
            rows = session.exec(
                select(Partido, ProviderMapping.external_id)
                .join(
                    ProviderMapping,
                    (ProviderMapping.local_id == Partido.id)
                    & (ProviderMapping.provider == "api-football")
                    & (ProviderMapping.entity_type == "match"),
                )
                .outerjoin(
                    ProviderSnapshot,
                    (ProviderSnapshot.local_id == Partido.id)
                    & (ProviderSnapshot.provider == "api-football")
                    & (ProviderSnapshot.entity_type == "match")
                    & (ProviderSnapshot.kind == "detail_batch"),
                )
                .where(
                    Partido.temporada_id.in_(season_ids),
                    Partido.estado.in_([EstadoPartido.VIVO, EstadoPartido.FINALIZADO]),
                    or_(
                        ProviderSnapshot.id.is_(None),
                        Partido.estado == EstadoPartido.VIVO,
                        (Partido.fecha >= dt.datetime.now(dt.UTC) - dt.timedelta(days=2))
                        & (
                            ProviderSnapshot.fetched_at
                            < dt.datetime.now(dt.UTC) - dt.timedelta(hours=6)
                        ),
                    ),
                )
                .order_by(
                    (Partido.estado == EstadoPartido.VIVO).desc(),
                    ProviderSnapshot.fetched_at.asc().nulls_first(),
                    Partido.fecha.desc(),
                    Partido.id.desc(),
                )
                .limit(21)
            ).all()
            return [
                {
                    "match_id": row.id,
                    "fixture_id": int(external),
                    "live": row.estado == EstadoPartido.VIVO,
                }
                for row, external in rows
            ]

    def fetch(self, scope, context):
        from src.providers.automation import _fetch

        if not fixture_dependencies_ready(scope):
            return FetchResult({"waiting_dependencies": True, "selected": [], "response": []})
        pending = self._pending(scope)
        selected = pending[: self._batch_size()]
        if not selected:
            return FetchResult({"selected": [], "response": [], "more": False})

        def fetch(transport):
            client = APIFootballClient(transport=transport)
            selection = selected
            blocked_batch = False
            try:
                response = (
                    client.fixture(selection[0]["fixture_id"])
                    if len(selection) == 1
                    else client.fixture_batch([row["fixture_id"] for row in selection])
                )
            except ProviderError as exc:
                if exc.code != "plan" or len(selection) == 1:
                    raise
                selection, blocked_batch = selection[:1], True
                response = client.fixture(selection[0]["fixture_id"])
            return FetchResult(
                {
                    **response,
                    "selected": selection,
                    "more": len(pending) > len(selection),
                    "batch_restricted": blocked_batch,
                }
            )

        return _fetch(fetch, context)

    @staticmethod
    def next_interval(session, scope, payload, instant):
        if payload.get("waiting_dependencies"):
            return 300  # Recheck the local prerequisite; this performs no provider request.
        busy = payload.get("more") or any(row.get("live") for row in payload.get("selected", []))
        return max(scope.interval_seconds, 300 if busy else 86400)

    def apply(self, session, scope, payload, context):
        if payload.get("waiting_dependencies"):
            return {"changed": 0, "topics": [], "waiting_dependencies": True}
        if payload.get("batch_restricted"):
            from src.providers.automation import _snapshot as snapshot
            from src.sync.service import _connection_snapshot

            status = _connection_snapshot(session, "status")
            snapshot(
                session,
                "api-football",
                "connection",
                1,
                "batch_capability",
                {
                    "allowed": False,
                    "plan": status.payload.get("plan") if status else None,
                },
            )
        selected = {row["fixture_id"]: row["match_id"] for row in payload["selected"]}
        received, groups = {}, defaultdict(list)
        for row in payload.get("response", []):
            fixture_id = (row.get("fixture") or {}).get("id")
            if fixture_id not in selected or fixture_id in received:
                raise PermanentError("El lote incluye un partido no solicitado o repetido.")
            mapping = session.exec(
                select(ProviderMapping).where(
                    ProviderMapping.provider == "api-football",
                    ProviderMapping.entity_type == "match",
                    ProviderMapping.external_id == str(fixture_id),
                )
            ).first()
            if not mapping or mapping.local_id != selected[fixture_id]:
                raise PermanentError("La identidad de un partido cambió durante la consulta.")
            match = session.get(Partido, mapping.local_id)
            if not match:
                raise PermanentError("El partido seleccionado ya no existe.")
            received[fixture_id] = row
            groups[(match.competicion_id, match.temporada_id)].append(row)
        changed = 0
        for (competition_id, season_id), rows in groups.items():
            result = sync_competition_fixtures(
                session,
                competition_id,
                season_id,
                {"response": rows},
                commit=False,
                context=context,
            )
            changed += result["changed"]
        for fixture_id, match_id in selected.items():
            row = received.get(fixture_id)
            if row is None:
                issue(
                    session,
                    scope.id,
                    f"detail_missing:{fixture_id}",
                    f"La fuente no devolvió los detalles del partido {fixture_id}. Se conserva su información anterior.",
                )
            else:

                def response(key, observation=row):
                    data = observation.get(key)
                    return {"response": data if isinstance(data, list) else [], "_complete": False}

                result = sync_match_detail(
                    session,
                    match_id,
                    events_payload=response("events"),
                    lineups_payload=response("lineups"),
                    statistics_payload=response("statistics"),
                    commit=False,
                    context=context,
                )
                changed += result["changed"]
            _snapshot(
                session,
                entity_type="match",
                local_id=match_id,
                kind="detail_batch",
                payload={"received": row is not None, "fixture_id": fixture_id},
            )
        return {
            "changed": changed,
            "topics": ["matches"],
            "matches_checked": len(selected),
            "matches_received": len(received),
            "more": payload.get("more", False),
        }
