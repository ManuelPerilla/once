"""Resolve published tables against fixture participants, never by array order."""

import re
from collections import defaultdict
from types import SimpleNamespace

from sqlmodel import select

from src.audit.service import record_change
from src.catalog.service import _key
from src.models import Fase, Grupo, ParticipacionGrupo, Partido, ProviderMapping
from src.providers import APIFootballClient
from src.providers.api_batch import fixture_dependencies_ready
from src.providers.sync import _source_apply
from src.sync.handlers import FetchResult
from src.sync.service import PermanentError, issue


def _components(matches):
    edges = defaultdict(set)
    for match in matches:
        edges[match.equipo_local_id].add(match.equipo_visitante_id)
        edges[match.equipo_visitante_id].add(match.equipo_local_id)
    remaining, groups = set(edges), []
    while remaining:
        todo, group = {min(remaining)}, set()
        while todo:
            team = todo.pop()
            group.add(team)
            todo.update(edges[team] - group)
        remaining -= group
        groups.append(group)
    return groups


class BatchStandingsHandler:
    def fetch(self, scope, context):
        from src.providers.automation import _fetch

        if not fixture_dependencies_ready(scope):
            return FetchResult({"waiting_dependencies": True, "response": []})
        return _fetch(
            lambda transport: FetchResult(
                APIFootballClient(transport=transport).standings(
                    int(scope.selector["league_id"]), int(scope.selector["season"])
                )
            ),
            context,
        )

    @staticmethod
    def next_interval(session, scope, payload, instant):
        if payload.get("waiting_dependencies"):
            return 300
        if not payload.get("response"):
            return max(scope.interval_seconds, 86400)
        # Published historical tables may receive corrections, but hourly polling
        # would exhaust a free account without improving the current match feed.
        cadence = 604800 if int(scope.selector["season"]) < instant.year else 3600
        return max(scope.interval_seconds, cadence)

    def apply(self, session, scope, payload, context):
        from src.providers.automation import StandingsHandler

        if payload.get("waiting_dependencies"):
            return {"changed": 0, "tables": 0, "topics": [], "waiting_dependencies": True}
        league_id, year = int(scope.selector["league_id"]), int(scope.selector["season"])
        rows = payload.get("response", [])
        if not rows:
            return {"changed": 0, "tables": 0, "topics": [], "pending_source": True}
        if len(rows) != 1:
            raise PermanentError("La fuente devolvió varias competiciones en una clasificación.")
        league = rows[0].get("league") or {}
        if league.get("id") != league_id or league.get("season") != year:
            raise PermanentError("La clasificación no corresponde a la competición y año elegidos.")
        seasons = session.exec(
            select(ProviderMapping).where(
                ProviderMapping.provider == "api-football",
                ProviderMapping.entity_type == "season",
                ProviderMapping.external_id == str(year),
                ProviderMapping.external_scope.startswith(f"league:{league_id}"),
            )
        ).all()
        # Exact namespace boundary: league:239 must never match league:2390.
        seasons = [
            row
            for row in seasons
            if row.external_scope == f"league:{league_id}"
            or row.external_scope.startswith(f"league:{league_id}:edition:")
        ]
        phases = session.exec(
            select(Fase).where(Fase.temporada_id.in_([row.local_id for row in seasons]))
        ).all()
        phase_matches = defaultdict(list)
        for match in session.exec(
            select(Partido).where(Partido.fase_id.in_([row.id for row in phases]))
        ):
            phase_matches[match.fase_id].append(match)
        components = {phase.id: _components(phase_matches[phase.id]) for phase in phases}
        team_links = {
            row.external_id: row.local_id
            for row in session.exec(
                select(ProviderMapping).where(
                    ProviderMapping.provider == "api-football",
                    ProviderMapping.entity_type == "team",
                    ProviderMapping.external_scope == "",
                )
            )
        }
        changed, imported, pending = 0, 0, 0
        tables = league.get("standings")
        if not isinstance(tables, list):
            raise PermanentError("La fuente devolvió una estructura de clasificación inválida.")
        for table_index, table in enumerate(tables):
            if (
                not isinstance(table, list)
                or not table
                or any(not isinstance(row, dict) for row in table)
            ):
                raise PermanentError("La fuente devolvió una tabla vacía o inválida.")
            labels = {str(row.get("group") or "").strip() for row in table}
            external = [str((row.get("team") or {}).get("id")) for row in table]
            local_ids = {team_links[value] for value in external if value in team_links}
            if len(labels) != 1 or len(local_ids) != len(table):
                issue(
                    session,
                    scope.id,
                    f"table_identity:{table_index}",
                    "Una tabla contiene equipos sin vínculo o grupos mezclados. Se conserva para revisión.",
                )
                pending += 1
                continue
            label = next(iter(labels))
            edition = re.search(r"\b(apertura|clausura|finalizacion)\b", _key(label))
            candidates = []
            for phase in phases:
                if edition and edition[1] not in _key(phase.nombre).split():
                    continue
                groups = components[phase.id]
                if local_ids in groups:
                    candidates.append((phase, len(groups) > 1))
            if len(candidates) != 1:
                issue(
                    session,
                    scope.id,
                    f"table_scope:{table_index}:{label}",
                    f"La tabla {label or table_index + 1} no tiene una fase inequívoca según sus partidos. Revisa la edición y el grupo.",
                )
                pending += 1
                continue
            phase, grouped = candidates[0]
            group_id = None
            if grouped:
                if not label:
                    pending += 1
                    issue(
                        session,
                        scope.id,
                        f"table_group:{table_index}",
                        "La tabla no publica el nombre de su grupo.",
                    )
                    continue
                group = session.exec(
                    select(Grupo).where(Grupo.fase_id == phase.id, Grupo.nombre == label)
                ).first()
                members = (
                    set(
                        session.exec(
                            select(ParticipacionGrupo.equipo_id).where(
                                ParticipacionGrupo.grupo_id == group.id
                            )
                        ).all()
                    )
                    if group
                    else set()
                )
                if members and members != local_ids:
                    pending += 1
                    issue(
                        session,
                        scope.id,
                        f"table_members:{phase.id}:{label}",
                        "Los participantes del grupo cambiaron. Revisa sus identidades antes de reemplazar la tabla.",
                    )
                    continue
                if group is None:
                    group = Grupo(fase_id=phase.id, nombre=label)
                    session.add(group)
                    session.flush()
                    record_change(
                        session,
                        entity_type="group",
                        entity_id=group.id,
                        field="__entity__",
                        before=None,
                        after=group.model_dump(),
                        action="source_create",
                        actor=context.actor,
                        reason="Grupo publicado, verificado contra los cruces de la fase",
                        version=1,
                        source="api-football",
                        run_id=context.job_id,
                    )
                    changed += 1
                group_id = group.id
                for team_id in local_ids - members:
                    session.add(
                        ParticipacionGrupo(
                            equipo_id=team_id, grupo_id=group.id, source="api-football"
                        )
                    )
                    record_change(
                        session,
                        entity_type="team",
                        entity_id=team_id,
                        field=f"participation:group:{group.id}",
                        before=None,
                        after={"group_id": group.id},
                        action="source_enrollment",
                        actor=context.actor,
                        reason="Participante publicado y verificado en los partidos del grupo",
                        version=0,
                        source="api-football",
                        run_id=context.job_id,
                    )
                    changed += 1
                for match in phase_matches[phase.id]:
                    if (
                        match.equipo_local_id in local_ids
                        and match.equipo_visitante_id in local_ids
                    ):
                        changed += len(
                            _source_apply(
                                session, "match", match, {"grupo_id": group.id}, context=context
                            )
                        )
            selected_scope = SimpleNamespace(**scope.model_dump())
            selected_scope.selector = {
                **scope.selector,
                "season_id": phase.temporada_id,
                "phase_id": phase.id,
                "group_id": group_id,
                "table_name": label,
            }
            result = StandingsHandler().apply(
                session,
                selected_scope,
                {"response": [{"league": {**league, "standings": [table]}}]},
                context,
            )
            changed += result["changed"]
            imported += 1
        return {
            "changed": changed,
            "tables": imported,
            "requires_review": pending,
            "topics": ["standings", "matches"] if changed else [],
        }
