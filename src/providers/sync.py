import datetime
import hashlib
import json
import re
from collections import Counter

from sqlmodel import Session, select

from src.audit.service import apply_source_changes, open_issue, record_change
from src.models import (
    AlineacionPartido,
    Competicion,
    EntityRevision,
    Estadio,
    EstadisticasPartido,
    EstadoPartido,
    EventoPartido,
    Fase,
    Jugador,
    ParticipacionFase,
    ParticipacionTemporada,
    Partido,
    ProviderMapping,
    ProviderSnapshot,
    Temporada,
)

PROVIDER = "api-football"
FINISHED_STATUSES = {"FT", "AET", "PEN"}
LIVE_STATUSES = {"1H", "HT", "2H", "ET", "BT", "P", "LIVE", "INT"}


class SyncConfigurationError(RuntimeError):
    pass


def _local_mapping(session: Session, entity_type: str, local_id: int) -> ProviderMapping | None:
    return session.exec(
        select(ProviderMapping).where(
            ProviderMapping.provider == PROVIDER,
            ProviderMapping.entity_type == entity_type,
            ProviderMapping.local_id == local_id,
        )
    ).first()


def _external_mapping(
    session: Session,
    entity_type: str,
    external_id: str | int | None,
) -> ProviderMapping | None:
    if external_id is None:
        return None
    return session.exec(
        select(ProviderMapping).where(
            ProviderMapping.provider == PROVIDER,
            ProviderMapping.entity_type == entity_type,
            ProviderMapping.external_id == str(external_id),
        )
    ).first()


def _status(value: str | None) -> EstadoPartido:
    if value in {"AWD", "WO"}:
        return EstadoPartido.ADJUDICADO
    if value in FINISHED_STATUSES:
        return EstadoPartido.FINALIZADO
    if value in LIVE_STATUSES:
        return EstadoPartido.VIVO
    return {
        "NS": EstadoPartido.PROGRAMADO,
        "TBD": EstadoPartido.PROGRAMADO,
        "PST": EstadoPartido.APLAZADO,
        "SUSP": EstadoPartido.SUSPENDIDO,
        "CANC": EstadoPartido.CANCELADO,
        "ABD": EstadoPartido.ABANDONADO,
    }.get(value, EstadoPartido.DESCONOCIDO)


def _parse_date(value: str | None) -> datetime.datetime | None:
    if not value:
        return None
    return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))


def _snapshot(
    session: Session,
    *,
    entity_type: str,
    local_id: int,
    kind: str,
    payload: dict,
) -> None:
    row = session.exec(
        select(ProviderSnapshot).where(
            ProviderSnapshot.provider == PROVIDER,
            ProviderSnapshot.entity_type == entity_type,
            ProviderSnapshot.local_id == local_id,
            ProviderSnapshot.kind == kind,
        )
    ).first()
    now = datetime.datetime.now(datetime.timezone.utc)
    if row:
        row.payload = payload
        row.fetched_at = now
    else:
        row = ProviderSnapshot(
            provider=PROVIDER,
            entity_type=entity_type,
            local_id=local_id,
            kind=kind,
            fetched_at=now,
            payload=payload,
        )
    session.add(row)


def _player_from_source(
    session: Session,
    source: dict | None,
    *,
    position: str | None = None,
    context=None,
) -> Jugador | None:
    source = source or {}
    external_id = source.get("id")
    if external_id is None:
        return None

    mapping = _external_mapping(session, "player", external_id)
    player = session.get(Jugador, mapping.local_id) if mapping else None
    if player:
        if not player.posicion and position:
            _source_apply(session, "player", player, {"posicion": position}, context=context)
        return player

    name = source.get("name") or source.get("firstname") or source.get("lastname")
    if not name:
        return None

    player = Jugador(nombre=name, posicion=position)
    session.add(player)
    session.flush()
    _record_created(session, "player", player, context=context)
    session.add(
        ProviderMapping(
            provider=PROVIDER,
            entity_type="player",
            local_id=player.id,
            external_id=str(external_id),
            source_url=f"https://v3.football.api-sports.io/players?id={external_id}",
        )
    )
    return player


def _venue_for_fixture(session: Session, fixture: dict, *, context=None) -> Estadio | None:
    venue = fixture.get("fixture", {}).get("venue") or {}
    external_id = venue.get("id")
    mapped = _external_mapping(session, "venue", external_id)
    if mapped:
        return session.get(Estadio, mapped.local_id)

    name = venue.get("name")
    if not name or external_id is None:
        return None

    city = venue.get("city")
    existing = session.exec(
        select(Estadio).where(Estadio.nombre == name, Estadio.ciudad == city)
    ).first()
    if existing:
        open_issue(
            session,
            key=f"identity:venue:{PROVIDER}:{external_id}",
            entity_type="venue",
            entity_id=existing.id,
            source=PROVIDER,
            reason="El estadio tiene un nombre parecido a una ficha existente. Confirma su vínculo.",
            proposed={"external_id": str(external_id), "candidate_id": existing.id},
        )
        return None
    stadium = Estadio(nombre=name, ciudad=city)
    session.add(stadium)
    session.flush()
    _record_created(session, "venue", stadium, context=context)

    if external_id is not None and not mapped:
        session.add(
            ProviderMapping(
                provider=PROVIDER,
                entity_type="venue",
                local_id=stadium.id,
                external_id=str(external_id),
            )
        )
    return stadium


def _rows(payload):
    if (
        not isinstance(payload, dict)
        or payload.get("errors")
        or not isinstance(payload.get("response"), list)
    ):
        raise SyncConfigurationError("La fuente devolvió una respuesta incompleta o con errores.")
    return payload["response"]


def _source_apply(session, kind, item, changes, *, context=None, observed_at=None):
    return apply_source_changes(
        session,
        kind,
        item,
        changes,
        source=PROVIDER,
        observed_at=observed_at or getattr(context, "observed_at", None),
        run_id=context.job_id if context else None,
    )


def _record_created(session, kind, item, *, context=None):
    values = item.model_dump(exclude={"id"})
    _source_apply(session, kind, item, values, context=context)
    revision = session.get(EntityRevision, (kind, item.id))
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
        actor="service:sync",
        reason="Ficha creada desde una identidad publicada por la fuente",
        version=revision.version,
        source=PROVIDER,
        run_id=context.job_id if context else None,
    )


def sync_competition_fixtures(
    session: Session,
    competition_id: int,
    season_id: int,
    fixtures_payload: dict,
    *,
    commit=True,
    context=None,
) -> dict:
    competition = session.get(Competicion, competition_id)
    season = session.get(Temporada, season_id)
    if not competition or not season or season.competicion_id != competition_id:
        raise SyncConfigurationError("La temporada no pertenece a la competición indicada.")
    competition_mapping = _local_mapping(session, "competition", competition_id)
    season_mapping = _local_mapping(session, "season", season_id)
    if not competition_mapping or not season_mapping:
        raise SyncConfigurationError("Conecta la competición y su temporada con la fuente.")
    rows = _rows(fixtures_payload)
    for row in rows:
        league = row.get("league") or {}
        if league.get("id") is not None and str(league["id"]) != competition_mapping.external_id:
            raise SyncConfigurationError("La respuesta contiene partidos de otra competición.")
        if league.get("season") is not None and str(league["season"]) != season_mapping.external_id:
            raise SyncConfigurationError("La respuesta contiene partidos de otro año.")
    mappings = session.exec(
        select(ProviderMapping).where(
            ProviderMapping.provider == PROVIDER, ProviderMapping.entity_type.in_(["team", "match"])
        )
    ).all()
    links = {(row.entity_type, row.external_id): row.local_id for row in mappings}
    created = updated = changed = 0
    skipped = []
    for source in rows:
        fixture, teams = source.get("fixture") or {}, source.get("teams") or {}
        fixture_id = fixture.get("id")
        home = links.get(("team", str((teams.get("home") or {}).get("id"))))
        away = links.get(("team", str((teams.get("away") or {}).get("id"))))
        if not fixture_id or not home or not away or home == away:
            skipped.append({"fixture_id": fixture_id, "reason": "team_mapping_missing"})
            continue
        match = (
            session.get(Partido, links.get(("match", str(fixture_id))))
            if ("match", str(fixture_id)) in links
            else None
        )
        is_new = match is None
        if match and (match.competicion_id != competition_id or match.temporada_id != season_id):
            skipped.append({"fixture_id": fixture_id, "reason": "edition_conflict"})
            continue
        if is_new:
            # A second source must not duplicate an already imported historical match.
            # Same participants can play several times, so a candidate is reviewed,
            # never merged using names or an assumed date/timezone.
            linked_matches = select(ProviderMapping.local_id).where(
                ProviderMapping.provider == PROVIDER,
                ProviderMapping.entity_type == "match",
            )
            candidate = session.exec(
                select(Partido)
                .where(
                    Partido.temporada_id == season_id,
                    Partido.equipo_local_id == home,
                    Partido.equipo_visitante_id == away,
                    Partido.id.not_in(linked_matches),
                )
                .limit(1)
            ).first()
            if candidate:
                open_issue(
                    session,
                    key=f"identity:match:{PROVIDER}:{fixture_id}",
                    entity_type="match",
                    entity_id=candidate.id,
                    source=PROVIDER,
                    reason="Otra fuente ya contiene un partido entre estos equipos en esta edición. Revisa su identidad antes de añadirlo.",
                    proposed={"external_id": str(fixture_id), "candidate_id": candidate.id},
                )
                skipped.append({"fixture_id": fixture_id, "reason": "match_identity_review"})
                continue
            match = Partido(
                competicion_id=competition_id,
                temporada_id=season_id,
                equipo_local_id=home,
                equipo_visitante_id=away,
                estado=EstadoPartido.PROGRAMADO,
            )
            session.add(match)
            session.flush()
            _record_created(session, "match", match, context=context)
            session.add(
                ProviderMapping(
                    provider=PROVIDER,
                    entity_type="match",
                    local_id=match.id,
                    external_id=str(fixture_id),
                )
            )
            links[("match", str(fixture_id))] = match.id
            created += 1
        else:
            updated += 1
        values = {
            "competicion_id": competition_id,
            "temporada_id": season_id,
            "equipo_local_id": home,
            "equipo_visitante_id": away,
        }
        if fixture.get("date"):
            values["fecha"] = _parse_date(fixture["date"])
        code = (fixture.get("status") or {}).get("short")
        if code:
            values.update(estado=_status(code), estado_fuente=code)
        venue = _venue_for_fixture(session, source, context=context)
        if venue:
            values["estadio_id"] = venue.id
        round_name = (source.get("league") or {}).get("round")
        if round_name:
            values["jornada"] = round_name
            # The published numeric suffix identifies a jornada, not a new phase.
            phase_name = re.sub(r" - [0-9]+$", "", round_name).strip()
            phase = session.exec(
                select(Fase).where(Fase.temporada_id == season_id, Fase.nombre == phase_name)
            ).first()
            if not phase:
                phase = Fase(temporada_id=season_id, nombre=phase_name, tipo="fase_publicada")
                session.add(phase)
                session.flush()
                _record_created(session, "stage", phase, context=context)
            values["fase_id"] = phase.id
        for source_field, local_field in (
            ("home", "marcador_local"),
            ("away", "marcador_visitante"),
        ):
            value = (source.get("goals") or {}).get(source_field)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                values[local_field] = value
        changed += len(_source_apply(session, "match", match, values, context=context))
        for team in (home, away):
            if not session.get(ParticipacionTemporada, (team, season_id)):
                session.add(
                    ParticipacionTemporada(equipo_id=team, temporada_id=season_id, source=PROVIDER)
                )
            if values.get("fase_id") and not session.get(
                ParticipacionFase, (team, values["fase_id"])
            ):
                session.add(
                    ParticipacionFase(equipo_id=team, fase_id=values["fase_id"], source=PROVIDER)
                )
        _snapshot(session, entity_type="match", local_id=match.id, kind="fixture", payload=source)
        session.flush()
    from src.football.projections import rebuild_season_standings

    rebuild_season_standings(session, season_id)
    if commit:
        session.commit()
    return {
        "provider": PROVIDER,
        "competition_id": competition_id,
        "season_id": season_id,
        "created": created,
        "updated": updated,
        "changed": changed + created,
        "skipped": skipped,
        "topics": ["matches", "standings"],
    }


def _team_id_from_external(session, external_id):
    row = _external_mapping(session, "team", external_id)
    return row.local_id if row else None


def _stat_value(statistics, name):
    item = next((item for item in statistics if item.get("type") == name), None)
    value = item.get("value") if item else None
    try:
        return int(round(float(value.rstrip("%")))) if isinstance(value, str) else value
    except ValueError:
        return None


def _reconcile(session, model, kind, match_id, values, *, complete=False, context=None):
    existing = session.exec(
        select(model).where(model.partido_id == match_id, model.source == PROVIDER)
    ).all()
    by_key = {row.source_key: row for row in existing if row.source_key}
    used, changed = set(), 0
    for data in values:
        key = data["source_key"]
        row = by_key.get(key)
        if row is None:
            # Adopt exact legacy data once without changing its canonical ID.
            row = next(
                (
                    old
                    for old in existing
                    if old.source_key is None
                    and old.id not in used
                    and all(getattr(old, k) == v for k, v in data.items() if k != "source_key")
                ),
                None,
            )
        if row is None:
            row = model(partido_id=match_id, source=PROVIDER, **data)
            session.add(row)
            session.flush()
            _record_created(session, kind, row, context=context)
            changed += 1
        else:
            changed += len(_source_apply(session, kind, row, data, context=context))
        used.add(row.id)
    # A complete HTTP page is not proof that a live feed contains every historical row.
    # Missing rows require review; only explicit corrections can remove canonical details.
    if complete and values:
        for row in existing:
            if row.id not in used:
                open_issue(
                    session,
                    key=f"missing:{PROVIDER}:{kind}:{row.id}",
                    entity_type=kind,
                    entity_id=row.id,
                    source=PROVIDER,
                    reason="La última respuesta no incluye este detalle. Se conserva hasta revisarlo.",
                    proposed={"missing_from_observation": True, "match_id": match_id},
                )
    return changed


def sync_match_detail(
    session: Session,
    match_id: int,
    *,
    events_payload: dict,
    lineups_payload: dict,
    statistics_payload: dict,
    commit=True,
    context=None,
) -> dict:
    match = session.get(Partido, match_id)
    mapping = _local_mapping(session, "match", match_id)
    if not match or not mapping:
        raise SyncConfigurationError("El partido no tiene un vínculo válido con API-Football.")
    events, lineups, statistics = map(_rows, (events_payload, lineups_payload, statistics_payload))
    players, event_values, lineup_values = set(), [], []
    occurrences = Counter()
    for source in events:
        team_id = _team_id_from_external(session, (source.get("team") or {}).get("id"))
        if team_id not in (match.equipo_local_id, match.equipo_visitante_id):
            continue
        player = _player_from_source(session, source.get("player"), context=context)
        assistant = _player_from_source(session, source.get("assist"), context=context)
        players.update(item.id for item in (player, assistant) if item)
        time = source.get("time") or {}
        elapsed, extra = time.get("elapsed"), time.get("extra") or 0
        if (
            not isinstance(elapsed, int)
            or not 0 <= elapsed <= 150
            or not isinstance(extra, int)
            or not 0 <= extra <= 30
        ):
            continue
        identity = {key: source.get(key) for key in ("time", "team", "player", "type")}
        digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        occurrences[digest] += 1
        event_values.append(
            {
                "source_key": f"{digest}:{occurrences[digest]}",
                "equipo_id": team_id,
                "jugador_id": player.id if player else None,
                "asistente_id": assistant.id if assistant else None,
                "tipo": source.get("type") or "Evento",
                "minuto": elapsed,
                "adicional": extra,
                "detalle": source.get("detail") or source.get("comments"),
            }
        )
    for team_source in lineups:
        team_id = _team_id_from_external(session, (team_source.get("team") or {}).get("id"))
        if team_id not in (match.equipo_local_id, match.equipo_visitante_id):
            continue
        for starter, entries in (
            (True, team_source.get("startXI") or []),
            (False, team_source.get("substitutes") or []),
        ):
            for order, entry in enumerate(entries):
                source = entry.get("player") or {}
                player = _player_from_source(
                    session, source, position=source.get("pos"), context=context
                )
                if not player:
                    continue
                players.add(player.id)
                number = source.get("number")
                lineup_values.append(
                    {
                        "source_key": f"{team_id}:{player.id}",
                        "equipo_id": team_id,
                        "jugador_id": player.id,
                        "titular": starter,
                        "posicion": source.get("pos"),
                        "dorsal": number if isinstance(number, int) and 0 <= number <= 99 else None,
                        "orden": order,
                    }
                )
    team_stats = {
        _team_id_from_external(session, (row.get("team") or {}).get("id")): row.get("statistics")
        or []
        for row in statistics
    }
    values = [
        _stat_value(team_stats.get(team, []), key)
        for key in ("Ball Possession", "Shots on Goal")
        for team in (match.equipo_local_id, match.equipo_visitante_id)
    ]
    stats_values = []
    if (
        all(isinstance(value, (int, float)) and value >= 0 for value in values)
        and max(values[:2]) <= 100
    ):
        stats_values = [
            {
                "source_key": "match",
                "posesion_local": int(values[0]),
                "posesion_visitante": int(values[1]),
                "tiros_puerta_local": int(values[2]),
                "tiros_puerta_visitante": int(values[3]),
            }
        ]
    changed = 0
    for model, kind, data, payload in (
        (EventoPartido, "event", event_values, events_payload),
        (AlineacionPartido, "lineup", lineup_values, lineups_payload),
        (EstadisticasPartido, "statistics", stats_values, statistics_payload),
    ):
        changed += _reconcile(
            session,
            model,
            kind,
            match_id,
            data,
            complete=payload.get("_complete") is True,
            context=context,
        )
        _snapshot(
            session,
            entity_type="match",
            local_id=match_id,
            kind={"event": "events", "lineup": "lineups"}.get(kind, kind),
            payload=payload,
        )
    if commit:
        session.commit()
    return {
        "provider": PROVIDER,
        "match_id": match_id,
        "external_fixture_id": mapping.external_id,
        "events": len(event_values),
        "lineup_entries": len(lineup_values),
        "players_touched": len(players),
        "statistics": bool(stats_values),
        "changed": changed,
        "topics": ["matches"],
    }
