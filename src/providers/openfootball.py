"""Bounded CC0 Colombian archives; never advertised as a live results source.

Source: https://github.com/openfootball/south-america (LICENSE.md: CC0-1.0).
The textual source labels identify records within this provider only. Existing
ONCE identities require an external mapping or an explicit reviewed selection.
"""

import datetime as dt
import hashlib
import re

import httpx
from sqlmodel import select

from src.audit.service import apply_source_changes, record_change
from src.football.entities import ENTITY_MODELS
from src.models import (
    Competicion,
    EntityRevision,
    Equipo,
    EstadoPartido,
    Fase,
    Grupo,
    Participacion,
    ParticipacionFase,
    ParticipacionGrupo,
    ParticipacionTemporada,
    Partido,
    ProviderMapping,
    TipoCompeticion,
    TipoEquipo,
)
from src.sync.handlers import FetchResult
from src.sync.service import PermanentError, RetryableError, issue

YEARS = (2023, 2024, 2025)
BASE_URL = "https://raw.githubusercontent.com/openfootball/south-america/master/colombia"
LICENSE_URL = "https://github.com/openfootball/south-america/blob/master/LICENSE.md"
# Exact labels reviewed against the Colombian club IDs in catalog/collections.py.
# This crosswalk applies only to the 2025 archive; it never creates Wikidata links
# or asserts current names/participation (La Equidad is a historical club label).
TEAM_QIDS_2025 = {
    "Deportes Tolima": "Q332532",
    "Atlético Nacional": "Q332605",
    "Millonarios": "Q391984",
    "América de Cali": "Q391987",
    "Deportivo Cali": "Q663400",
    "Santa Fe": "Q1424072",
    "Independiente Medellín": "Q332527",
    "Once Caldas": "Q47533",
    "Deportivo Pereira": "Q515178",
    "Atlético Bucaramanga": "Q757418",
    "Deportivo Pasto": "Q332858",
    "La Equidad": "Q332668",
    "Envigado FC": "Q332636",
    "Boyacá Chicó": "Q332863",
    "Águilas Doradas": "Q332833",
}
MAX_BYTES = 1024 * 1024
MONTHS = {
    name: index
    for index, name in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)
}
STAGE = re.compile(r"^▪ (Apertura|Clausura)( Playoffs)?, (Matchday (\d+)|Group ([A-Z])|Final)$")
DATE = re.compile(r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun) ([A-Z][a-z]{2}) (\d{1,2})(?: (\d{4}))?$")
SCORE = re.compile(
    r"^(\d+)-(\d+)(?: \(\d+-\d+(?:, \d+-\d+)?\))?(?:\s+\[(awarded|abandoned|cancelled|postponed|suspended)\])?$"
)
PENALTIES = re.compile(
    r"^(\d+)-(\d+) pen\.\s+(?:(\d+)-(\d+) a\.e\.t\.\s+)?\((\d+)-(\d+)(?:, \d+-\d+)?\)$"
)


def validate_selector(selector):
    value = dict(selector)
    try:
        year = int(value.get("season", 2025))
    except (TypeError, ValueError) as exc:
        raise ValueError("Elige un año del archivo abierto: 2023, 2024 o 2025.") from exc
    if year not in YEARS:
        raise ValueError("El archivo verificado contiene 2023–2025; no ofrece resultados actuales.")
    value["season"] = year
    if value.get("edition") not in (None, "Apertura", "Clausura"):
        raise ValueError("La edición debe ser Apertura o Clausura.")
    if value.get("timezone") not in (None, "America/Bogota"):
        raise ValueError(
            "Solo se admite confirmar la zona America/Bogota para este archivo colombiano."
        )
    for key in ("competition_id",):
        if value.get(key) is not None:
            try:
                value[key] = int(value[key])
                if value[key] <= 0:
                    raise ValueError
            except (ValueError, TypeError) as exc:
                raise ValueError("Elige una competición colombiana válida.") from exc
    teams = value.get("team_ids", {})
    if not isinstance(teams, dict) or len(teams) > 40:
        raise ValueError("Las identidades revisadas de equipos no son válidas.")
    for label, target in teams.items():
        if not isinstance(label, str) or not isinstance(target, int) or target <= 0:
            raise ValueError("Cada identidad revisada requiere el nombre externo y el ID local.")
    return value


def source_id(*parts):
    # Source label changes deliberately require review; no fuzzy canonical merges.
    return hashlib.sha256(
        "|".join(str(part).strip() for part in parts).encode("utf-8")
    ).hexdigest()[:32]


def parse_score(value):
    if not value:
        return None, None, "unknown", None
    penalty = PENALTIES.fullmatch(value)
    if penalty:
        home, away = penalty.group(3, 4) if penalty.group(3) else penalty.group(5, 6)
        return int(home), int(away), "penalties", [int(penalty[1]), int(penalty[2])]
    score = SCORE.fullmatch(value)
    if score:
        return int(score[1]), int(score[2]), score[3] or "finished", None
    if value in {"[abandoned]", "[cancelled]", "[postponed]", "[suspended]"}:
        return None, None, value[1:-1], None
    raise ValueError("Formato de marcador no reconocido; no se aplicó el archivo.")


def parse_archive(text, year):
    """Reject malformed/truncated files instead of silently skipping records."""
    if len(text.encode("utf-8")) > MAX_BYTES or year not in YEARS:
        raise ValueError("El archivo excede el alcance permitido.")
    lines = text.lstrip("\ufeff").splitlines()
    if not lines or lines[0].strip() != f"= Colombia Primera A {year}":
        raise ValueError("El archivo no corresponde al torneo y año seleccionados.")
    stage, date, expected, records, seen = None, None, None, [], set()
    for number, raw in enumerate(lines[1:], 2):
        line = raw.strip()
        if not line or line.startswith("#"):
            match = re.fullmatch(r"# Matches\s+(\d+)", line)
            if match:
                expected = int(match[1])
            continue
        heading = STAGE.fullmatch(line)
        if heading:
            stage = {
                "edition": heading[1],
                "phase": "Final"
                if heading[3] == "Final"
                else "Cuadrangulares"
                if heading[2]
                else "Todos contra todos",
                "round": heading[4],
                "group": heading[5],
                "source_stage": line[2:],
            }
            date = None
            continue
        day = DATE.fullmatch(line)
        if day:
            if day[4] and int(day[4]) != year:
                raise ValueError("Una fecha pertenece a otro año.")
            try:
                date = dt.date(year, MONTHS[day[2]], int(day[3]))
            except (ValueError, KeyError) as exc:
                raise ValueError("El archivo contiene una fecha no válida.") from exc
            if date.strftime("%a") != day[1]:
                # strftime weekday names depend on OS locale; use a fixed English table.
                if "Mon Tue Wed Thu Fri Sat Sun".split()[date.weekday()] != day[1]:
                    raise ValueError("La fecha y el día de la semana no coinciden.")
            continue
        if stage is None or date is None or " v " not in line:
            raise ValueError(f"No se reconoce la estructura de la línea {number}.")
        clock = re.match(r"^(\d{2}:\d{2})\s+", line)
        source_time = clock[1] if clock else None
        if source_time:
            dt.time.fromisoformat(source_time)
            line = line[clock.end() :]
        home, tail = re.split(r"\s+v\s+", line, maxsplit=1)
        away_parts = re.split(r"\s{2,}", tail, maxsplit=1)
        away, score_text = (
            away_parts[0].strip(),
            away_parts[1].strip() if len(away_parts) == 2 else "",
        )
        if not home or not away or home == away or len(home) > 120 or len(away) > 120:
            raise ValueError("El archivo contiene equipos inválidos.")
        score_home, score_away, status, penalties = parse_score(score_text)
        key = source_id(
            year, stage["edition"], stage["phase"], stage["group"], stage["round"], home, away
        )
        if key in seen:
            raise ValueError("El archivo repite la identidad de un partido.")
        seen.add(key)
        records.append(
            {
                **stage,
                "id": key,
                "home": home,
                "away": away,
                "date": date.isoformat(),
                "time": source_time,
                "score_home": score_home,
                "score_away": score_away,
                "status": status,
                "penalties": penalties,
                "source_result": score_text,
            }
        )
    if expected is None or expected != len(records) or not records or len(records) > 1000:
        raise ValueError(
            "El número de partidos no coincide con la cabecera; el archivo puede estar truncado."
        )
    missing = sum(row["score_home"] is None for row in records)
    return {
        "year": year,
        "source_url": f"{BASE_URL}/{year}_co1.txt",
        "license": "CC0-1.0",
        "license_url": LICENSE_URL,
        "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "historical": True,
        "coverage": {
            "matches": len(records),
            "missing_results": missing,
            "all_results_present": missing == 0,
            "editions": sorted({row["edition"] for row in records}),
            "live": False,
            "timezone_declared_by_source": False,
        },
        "fixtures": records,
    }


def _audit_created(session, kind, item, context, *, initialize=True):
    """Creation and source ownership are committed with the same canonical row."""
    values = item.model_dump(exclude={"id"})
    if initialize and kind in ENTITY_MODELS:
        apply_source_changes(
            session,
            kind,
            item,
            values,
            source="openfootball",
            observed_at=context.observed_at,
            actor=context.actor,
            run_id=context.job_id,
        )
    revision = session.get(EntityRevision, (kind, item.id))
    if revision is None:
        revision = EntityRevision(entity_type=kind, entity_id=item.id)
    revision.version += 1
    session.add(revision)
    record_change(
        session,
        entity_type=kind,
        entity_id=item.id,
        field="__entity__",
        before=None,
        after=values,
        action="source_create",
        actor=context.actor,
        reason="Ficha creada desde una identidad del archivo histórico abierto",
        version=revision.version,
        source="openfootball",
        run_id=context.job_id,
    )


def _audit_enrollment(session, team, relation, values, context):
    revision = session.get(EntityRevision, ("team", team.id))
    if revision is None:
        revision = EntityRevision(entity_type="team", entity_id=team.id)
    revision.version += 1
    session.add(revision)
    record_change(
        session,
        entity_type="team",
        entity_id=team.id,
        field=f"participation:{relation}",
        before=None,
        after=values,
        action="source_enrollment",
        actor=context.actor,
        reason="Participación acreditada por un partido del archivo histórico",
        version=revision.version,
        source="openfootball",
        run_id=context.job_id,
    )


class OpenFootballHandler:
    def fetch(self, scope, context):
        try:
            selector = validate_selector(scope.selector)
        except ValueError as exc:
            raise PermanentError(str(exc)) from exc
        url = f"{BASE_URL}/{selector['season']}_co1.txt"
        context.reserve_request("openfootball")
        try:
            with httpx.Client(timeout=15, follow_redirects=False) as client:
                with client.stream(
                    "GET", url, headers={"User-Agent": "ONCE/1.0 (open football archive)"}
                ) as response:
                    if response.status_code == 429 or response.status_code >= 500:
                        retry = response.headers.get("Retry-After", "60")
                        seconds = int(retry) if retry.isdigit() else 60
                        context.report_quota(provider="openfootball", retry_after=seconds)
                        raise RetryableError(
                            "El archivo abierto no está disponible temporalmente.", seconds
                        )
                    if response.status_code != 200:
                        raise PermanentError("No se encontró un archivo permitido para ese año.")
                    payload = bytearray()
                    for chunk in response.iter_bytes():
                        payload.extend(chunk)
                        if len(payload) > MAX_BYTES:
                            raise PermanentError("El archivo supera el tamaño permitido.")
            parsed = parse_archive(bytes(payload).decode("utf-8"), selector["season"])
        except httpx.HTTPError as exc:
            raise RetryableError("No se pudo descargar el archivo abierto.") from exc
        except (UnicodeDecodeError, ValueError) as exc:
            raise PermanentError(str(exc)) from exc
        return FetchResult(parsed)

    def apply(self, session, scope, payload, context):
        # Shared identity reconciliation handles explicit links and ambiguous candidates.
        from src.providers.automation import _identity, _mapped, _snapshot

        selector = validate_selector(scope.selector)
        if payload["year"] != selector["season"]:
            raise PermanentError("El archivo observado pertenece a otro año.")
        target = selector.get("competition_id")
        if not target:
            canonical = _mapped(session, "wikidata", "competition", "Q1033349")
            target = canonical.local_id if canonical else None
        existing = session.get(Competicion, target) if target else None
        if existing and (
            existing.pais != "Colombia" or existing.tipo != TipoCompeticion.LIGA_NACIONAL
        ):
            raise PermanentError("La competición seleccionada no es una liga colombiana.")
        values = {
            "nombre": existing.nombre if existing else "Primera A de Colombia",
            "pais": "Colombia",
            "tipo": TipoCompeticion.LIGA_NACIONAL,
        }
        if not existing:
            values["logo"] = ""
        competition, changed = _identity(
            session,
            scope,
            "competition",
            "colombia/primera-a",
            values,
            context=context,
            target_id=target,
        )
        if competition is None:
            return {"changed": 0, "topics": ["catalog"], "historical": True}
        selected = [
            row
            for row in payload["fixtures"]
            if not selector.get("edition") or row["edition"] == selector["edition"]
        ]
        if not selected:
            raise PermanentError("El archivo no contiene la edición seleccionada.")
        teams, seasons, phases, groups = {}, {}, {}, {}
        for label in sorted({row[side] for row in selected for side in ("home", "away")}):
            external = f"colombia/{source_id(label)}"
            reviewed = selector.get("team_ids", {}).get(label)
            qid = TEAM_QIDS_2025.get(label) if payload["year"] == 2025 else None
            canonical = _mapped(session, "wikidata", "team", qid) if qid else None
            linked = _mapped(session, "openfootball", "team", external)
            targets = {
                target
                for target in (
                    reviewed,
                    canonical.local_id if canonical else None,
                    linked.local_id if linked else None,
                )
                if target is not None
            }
            if len(targets) > 1:
                raise PermanentError(
                    f"Los vínculos de {label} apuntan a clubes diferentes. "
                    "Revisa la identidad seleccionada y sus identificadores externos."
                )
            target = next(iter(targets), None)
            existing = session.get(Equipo, target) if target else None
            if target and (
                not existing or existing.pais != "Colombia" or existing.tipo != TipoEquipo.CLUB
            ):
                raise PermanentError("Una identidad revisada no corresponde a un club colombiano.")
            values = {
                "nombre": existing.nombre if existing else label,
                "pais": "Colombia",
                "tipo": TipoEquipo.CLUB,
            }
            if not existing:
                values["logo"] = ""
            team, count = _identity(
                session, scope, "team", external, values, context=context, target_id=target
            )
            changed += count
            teams[label] = team
            if team:
                changed += _snapshot(
                    session,
                    "openfootball",
                    "team",
                    team.id,
                    f"archive-label:{payload['year']}:{source_id(label)}",
                    {
                        "source_label": label,
                        "year": payload["year"],
                        "wikidata_qid": qid if canonical else None,
                        "source_url": payload["source_url"],
                        "license": "CC0-1.0",
                        "historical": True,
                    },
                )
        for edition in sorted({row["edition"] for row in selected}):
            year = payload["year"]
            season, count = _identity(
                session,
                scope,
                "season",
                f"{year}/{edition}",
                {
                    "competicion_id": competition.id,
                    "nombre": f"{year} · {edition}",
                    "activa": False,
                },
                external_scope="colombia/primera-a",
                context=context,
            )
            changed += count
            seasons[edition] = season
        states = {
            "finished": EstadoPartido.FINALIZADO,
            "penalties": EstadoPartido.FINALIZADO,
            "awarded": EstadoPartido.ADJUDICADO,
            "abandoned": EstadoPartido.ABANDONADO,
            "cancelled": EstadoPartido.CANCELADO,
            "postponed": EstadoPartido.APLAZADO,
            "suspended": EstadoPartido.SUSPENDIDO,
            "unknown": EstadoPartido.DESCONOCIDO,
        }
        imported = 0
        for row in selected:
            season, home, away = seasons[row["edition"]], teams[row["home"]], teams[row["away"]]
            if not season or not home or not away:
                continue
            phase_key = (season.id, row["phase"])
            if phase_key not in phases:
                phase = session.exec(
                    select(Fase).where(Fase.temporada_id == season.id, Fase.nombre == row["phase"])
                ).first()
                if phase is None:
                    phase = Fase(
                        temporada_id=season.id,
                        nombre=row["phase"],
                        tipo="eliminatoria" if row["phase"] == "Final" else "liga",
                        orden={"Todos contra todos": 1, "Cuadrangulares": 2, "Final": 3}[
                            row["phase"]
                        ],
                    )
                    session.add(phase)
                    session.flush()
                    _audit_created(session, "stage", phase, context)
                    changed += 1
                phases[phase_key] = phase
            phase = phases[phase_key]
            group = None
            if row["group"]:
                group_key = (phase.id, row["group"])
                if group_key not in groups:
                    group = session.exec(
                        select(Grupo).where(Grupo.fase_id == phase.id, Grupo.nombre == row["group"])
                    ).first()
                    if group is None:
                        group = Grupo(fase_id=phase.id, nombre=row["group"])
                        session.add(group)
                        session.flush()
                        _audit_created(session, "group", group, context)
                        changed += 1
                    groups[group_key] = group
                group = groups[group_key]
            for team in (home, away):
                for model, keys, values in (
                    (
                        Participacion,
                        (team.id, competition.id),
                        {"equipo_id": team.id, "competicion_id": competition.id},
                    ),
                    (
                        ParticipacionTemporada,
                        (team.id, season.id),
                        {"equipo_id": team.id, "temporada_id": season.id, "source": "openfootball"},
                    ),
                    (
                        ParticipacionFase,
                        (team.id, phase.id),
                        {"equipo_id": team.id, "fase_id": phase.id, "source": "openfootball"},
                    ),
                ):
                    if not session.get(model, keys):
                        session.add(model(**values))
                        _audit_enrollment(session, team, model.__tablename__, values, context)
                        changed += 1
                if group and not session.get(ParticipacionGrupo, (team.id, group.id)):
                    values = {"equipo_id": team.id, "grupo_id": group.id, "source": "openfootball"}
                    session.add(ParticipacionGrupo(**values))
                    _audit_enrollment(session, team, "participaciongrupo", values, context)
                    changed += 1
            fields = {
                "competicion_id": competition.id,
                "temporada_id": season.id,
                "fase_id": phase.id,
                "grupo_id": group.id if group else None,
                "equipo_local_id": home.id,
                "equipo_visitante_id": away.id,
                "jornada": row["source_stage"],
                "estado": states[row["status"]],
                "estado_fuente": row["status"],
                "marcador_local": row["score_home"],
                "marcador_visitante": row["score_away"],
            }
            if selector.get("timezone") and row["time"]:
                fields["fecha"] = dt.datetime.fromisoformat(f"{row['date']}T{row['time']}:00-05:00")
            mapping = _mapped(session, "openfootball", "match", row["id"], "colombia/primera-a")
            match = session.get(Partido, mapping.local_id) if mapping else None
            created = match is None
            if mapping and match is None:
                issue(
                    session,
                    scope.id,
                    f"missing:match:{row['id']}",
                    "Un vínculo histórico apunta a un partido eliminado.",
                )
                continue
            if match is None:
                linked_here = select(ProviderMapping.local_id).where(
                    ProviderMapping.provider == "openfootball",
                    ProviderMapping.entity_type == "match",
                )
                candidate = session.exec(
                    select(Partido).where(
                        Partido.temporada_id == season.id,
                        Partido.fase_id == phase.id,
                        Partido.equipo_local_id == home.id,
                        Partido.equipo_visitante_id == away.id,
                        Partido.id.not_in(linked_here),
                    )
                ).first()
                if candidate:
                    issue(
                        session,
                        scope.id,
                        f"identity:match:{row['id']}",
                        "Ya existe un partido de estos equipos en la fase. Revisa su vínculo antes de importar otro.",
                    )
                    continue
                match = Partido(**fields)
                session.add(match)
                session.flush()
                session.add(
                    ProviderMapping(
                        provider="openfootball",
                        entity_type="match",
                        local_id=match.id,
                        external_id=row["id"],
                        external_scope="colombia/primera-a",
                        source_url=payload["source_url"],
                    )
                )
                changed += 1
            else:
                # Missing historical results must never erase later verified corrections.
                if row["score_home"] is None:
                    for name in ("marcador_local", "marcador_visitante", "estado", "estado_fuente"):
                        fields.pop(name, None)
            changed += len(
                apply_source_changes(
                    session,
                    "match",
                    match,
                    fields,
                    source="openfootball",
                    run_id=context.job_id,
                    observed_at=context.observed_at,
                )
            )
            if created:
                _audit_created(session, "match", match, context, initialize=False)
            _snapshot(
                session,
                "openfootball",
                "match",
                match.id,
                "archive",
                {
                    **row,
                    "source_url": payload["source_url"],
                    "license": "CC0-1.0",
                    "historical": True,
                    "timezone": selector.get("timezone"),
                },
            )
            imported += 1
        _snapshot(
            session,
            "openfootball",
            "competition",
            competition.id,
            f"coverage:{payload['year']}",
            {
                "coverage": payload["coverage"],
                "source_url": payload["source_url"],
                "license": "CC0-1.0",
                "content_hash": payload["content_hash"],
                "historical": True,
            },
        )
        if payload["coverage"]["missing_results"]:
            issue(
                session,
                scope.id,
                "archive_incomplete_results",
                f"Archivo histórico parcial: faltan {payload['coverage']['missing_results']} resultados. No es una fuente en vivo.",
            )
        return {
            "changed": changed,
            "topics": ["catalog", "matches"],
            "imported": imported,
            "historical": True,
            "coverage": payload["coverage"],
            "skipped": len(selected) - imported,
        }
