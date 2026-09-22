import datetime

from sqlmodel import Session, select

from src.models import (
    AlineacionPartido,
    Competicion,
    Equipo,
    EstadisticasPartido,
    EstadoPartido,
    Estadio,
    EventoPartido,
    Jugador,
    JugadorEquipo,
    Partido,
    ProviderMapping,
    ProviderSnapshot,
    Temporada,
)


PROVIDER = "api-football"
FINISHED_STATUSES = {"FT", "AET", "PEN", "AWD", "WO"}
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
    if value in FINISHED_STATUSES:
        return EstadoPartido.FINALIZADO
    if value in LIVE_STATUSES:
        return EstadoPartido.VIVO
    return EstadoPartido.PROGRAMADO


def _parse_date(value: str | None) -> datetime.datetime | None:
    if not value:
        return None
    return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))


def _replace_provider_rows(session: Session, model, match_id: int) -> None:
    rows = session.exec(
        select(model).where(
            model.partido_id == match_id,
            model.source == PROVIDER,
        )
    ).all()
    for row in rows:
        session.delete(row)


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
) -> Jugador | None:
    source = source or {}
    external_id = source.get("id")
    if external_id is None:
        return None

    mapping = _external_mapping(session, "player", external_id)
    player = session.get(Jugador, mapping.local_id) if mapping else None
    if player:
        if not player.posicion and position:
            player.posicion = position
            session.add(player)
        return player

    name = source.get("name") or source.get("firstname") or source.get("lastname")
    if not name:
        return None

    player = Jugador(nombre=name, posicion=position)
    session.add(player)
    session.flush()
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


def _ensure_roster_link(
    session: Session,
    *,
    player_id: int,
    team_id: int,
    number: int | None,
) -> None:
    link = session.exec(
        select(JugadorEquipo).where(
            JugadorEquipo.jugador_id == player_id,
            JugadorEquipo.equipo_id == team_id,
            JugadorEquipo.fecha_fin.is_(None),
        )
    ).first()
    if link:
        if number is not None:
            link.dorsal = number
            session.add(link)
        return

    session.add(
        JugadorEquipo(
            jugador_id=player_id,
            equipo_id=team_id,
            dorsal=number,
        )
    )


def _venue_for_fixture(session: Session, fixture: dict) -> Estadio | None:
    venue = fixture.get("fixture", {}).get("venue") or {}
    external_id = venue.get("id")
    mapped = _external_mapping(session, "venue", external_id)
    if mapped:
        return session.get(Estadio, mapped.local_id)

    name = venue.get("name")
    if not name:
        return None

    city = venue.get("city")
    existing = session.exec(
        select(Estadio).where(Estadio.nombre == name, Estadio.ciudad == city)
    ).first()
    if existing:
        stadium = existing
    else:
        stadium = Estadio(nombre=name, ciudad=city)
        session.add(stadium)
        session.flush()

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


def sync_competition_fixtures(
    session: Session,
    competition_id: int,
    season_id: int,
    fixtures_payload: dict,
) -> dict:
    competition = session.get(Competicion, competition_id)
    season = session.get(Temporada, season_id)
    if not competition:
        raise SyncConfigurationError("Competición local no encontrada.")
    if not season or season.competicion_id != competition_id:
        raise SyncConfigurationError("La temporada no pertenece a la competición indicada.")

    competition_mapping = _local_mapping(session, "competition", competition_id)
    season_mapping = _local_mapping(session, "season", season_id)
    if not competition_mapping:
        raise SyncConfigurationError("La competición no tiene mapping de API-Football.")
    if not season_mapping:
        raise SyncConfigurationError("La temporada no tiene mapping de API-Football.")

    created = 0
    updated = 0
    skipped = []

    for source in fixtures_payload.get("response", []):
        fixture = source.get("fixture") or {}
        teams = source.get("teams") or {}
        home_external = (teams.get("home") or {}).get("id")
        away_external = (teams.get("away") or {}).get("id")
        home_mapping = _external_mapping(session, "team", home_external)
        away_mapping = _external_mapping(session, "team", away_external)

        if not home_mapping or not away_mapping:
            skipped.append(
                {
                    "fixture_id": fixture.get("id"),
                    "home": (teams.get("home") or {}).get("name"),
                    "away": (teams.get("away") or {}).get("name"),
                    "reason": "team_mapping_missing",
                }
            )
            continue

        local_home = session.get(Equipo, home_mapping.local_id)
        local_away = session.get(Equipo, away_mapping.local_id)
        if not local_home or not local_away:
            skipped.append(
                {
                    "fixture_id": fixture.get("id"),
                    "reason": "mapped_team_missing_locally",
                }
            )
            continue

        fixture_id = fixture.get("id")
        match_mapping = _external_mapping(session, "match", fixture_id)
        match = session.get(Partido, match_mapping.local_id) if match_mapping else None
        is_new = match is None
        if is_new:
            match = Partido(
                competicion_id=competition_id,
                temporada_id=season_id,
                equipo_local_id=local_home.id,
                equipo_visitante_id=local_away.id,
                estado=EstadoPartido.PROGRAMADO,
            )
            session.add(match)
            session.flush()

        venue = _venue_for_fixture(session, source)
        status = _status((fixture.get("status") or {}).get("short"))
        goals = source.get("goals") or {}

        match.competicion_id = competition_id
        match.temporada_id = season_id
        match.equipo_local_id = local_home.id
        match.equipo_visitante_id = local_away.id
        match.estadio_id = venue.id if venue else None
        match.fecha = _parse_date(fixture.get("date"))
        match.jornada = (source.get("league") or {}).get("round")
        match.estado = status
        match.marcador_local = goals.get("home") or 0
        match.marcador_visitante = goals.get("away") or 0
        session.add(match)

        if fixture_id is not None:
            _snapshot(
                session,
                entity_type="match",
                local_id=match.id,
                kind="fixture",
                payload=source,
            )

        if is_new and fixture_id is not None:
            session.add(
                ProviderMapping(
                    provider=PROVIDER,
                    entity_type="match",
                    local_id=match.id,
                    external_id=str(fixture_id),
                    source_url=f"https://v3.football.api-sports.io/fixtures?id={fixture_id}",
                )
            )
            created += 1
        else:
            updated += 1

    session.commit()
    return {
        "provider": PROVIDER,
        "competition_id": competition_id,
        "season_id": season_id,
        "created": created,
        "updated": updated,
        "skipped": skipped,
    }


def _team_id_from_external(session: Session, external_id: int | str | None) -> int | None:
    mapping = _external_mapping(session, "team", external_id)
    return mapping.local_id if mapping else None


def _stat_value(statistics: list[dict], name: str):
    item = next((item for item in statistics if item.get("type") == name), None)
    value = item.get("value") if item else None
    if isinstance(value, str) and value.endswith("%"):
        try:
            return int(round(float(value[:-1])))
        except ValueError:
            return None
    return value


def sync_match_detail(
    session: Session,
    match_id: int,
    *,
    events_payload: dict,
    lineups_payload: dict,
    statistics_payload: dict,
) -> dict:
    match = session.get(Partido, match_id)
    if not match:
        raise SyncConfigurationError("Partido local no encontrado.")

    match_mapping = _local_mapping(session, "match", match_id)
    if not match_mapping:
        raise SyncConfigurationError("El partido no tiene mapping de API-Football.")

    _snapshot(
        session,
        entity_type="match",
        local_id=match_id,
        kind="events",
        payload=events_payload,
    )
    _snapshot(
        session,
        entity_type="match",
        local_id=match_id,
        kind="lineups",
        payload=lineups_payload,
    )
    _snapshot(
        session,
        entity_type="match",
        local_id=match_id,
        kind="statistics",
        payload=statistics_payload,
    )

    _replace_provider_rows(session, EventoPartido, match_id)
    _replace_provider_rows(session, AlineacionPartido, match_id)
    _replace_provider_rows(session, EstadisticasPartido, match_id)

    event_count = 0
    lineup_count = 0
    player_ids: set[int] = set()

    for source in events_payload.get("response", []):
        team_id = _team_id_from_external(session, (source.get("team") or {}).get("id"))
        player = _player_from_source(session, source.get("player"))
        assistant = _player_from_source(session, source.get("assist"))
        if player:
            player_ids.add(player.id)
        if assistant:
            player_ids.add(assistant.id)

        time = source.get("time") or {}
        session.add(
            EventoPartido(
                partido_id=match_id,
                source=PROVIDER,
                equipo_id=team_id,
                jugador_id=player.id if player else None,
                asistente_id=assistant.id if assistant else None,
                tipo=source.get("type") or "Evento",
                minuto=int(time.get("elapsed") or 0),
                adicional=int(time.get("extra") or 0),
                detalle=source.get("detail") or source.get("comments"),
            )
        )
        event_count += 1

    for team_source in lineups_payload.get("response", []):
        team_id = _team_id_from_external(session, (team_source.get("team") or {}).get("id"))
        if team_id not in (match.equipo_local_id, match.equipo_visitante_id):
            continue

        groups = [
            (True, team_source.get("startXI") or []),
            (False, team_source.get("substitutes") or []),
        ]
        order = 0
        for starter, entries in groups:
            for entry in entries:
                source = entry.get("player") or {}
                player = _player_from_source(
                    session,
                    source,
                    position=source.get("pos"),
                )
                if not player:
                    continue
                player_ids.add(player.id)
                number = source.get("number")
                session.add(
                    AlineacionPartido(
                        partido_id=match_id,
                        source=PROVIDER,
                        equipo_id=team_id,
                        jugador_id=player.id,
                        titular=starter,
                        posicion=source.get("pos"),
                        dorsal=number,
                        orden=order,
                    )
                )
                _ensure_roster_link(
                    session,
                    player_id=player.id,
                    team_id=team_id,
                    number=number,
                )
                order += 1
                lineup_count += 1

    team_statistics: dict[int, list[dict]] = {}
    for source in statistics_payload.get("response", []):
        team_id = _team_id_from_external(session, (source.get("team") or {}).get("id"))
        if team_id:
            team_statistics[team_id] = source.get("statistics") or []

    home_stats = team_statistics.get(match.equipo_local_id)
    away_stats = team_statistics.get(match.equipo_visitante_id)
    stats_created = False
    if home_stats is not None and away_stats is not None:
        home_possession = _stat_value(home_stats, "Ball Possession")
        away_possession = _stat_value(away_stats, "Ball Possession")
        home_shots = _stat_value(home_stats, "Shots on Goal")
        away_shots = _stat_value(away_stats, "Shots on Goal")

        if all(value is not None for value in (
            home_possession,
            away_possession,
            home_shots,
            away_shots,
        )):
            session.add(
                EstadisticasPartido(
                    partido_id=match_id,
                    source=PROVIDER,
                    posesion_local=int(home_possession),
                    posesion_visitante=int(away_possession),
                    tiros_puerta_local=int(home_shots),
                    tiros_puerta_visitante=int(away_shots),
                )
            )
            stats_created = True

    session.commit()
    return {
        "provider": PROVIDER,
        "match_id": match_id,
        "external_fixture_id": match_mapping.external_id,
        "events": event_count,
        "lineup_entries": lineup_count,
        "players_touched": len(player_ids),
        "statistics": stats_created,
    }
