import os
import datetime
import hmac
from fastapi import FastAPI, Depends, HTTPException, status, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlmodel import Field, Session, select
from contextlib import asynccontextmanager
import jwt
from src.database import crear_tablas_db, engine
from src.security import get_auth_settings, verify_password
from src.providers.sync import SyncConfigurationError, sync_competition_fixtures, sync_match_detail
from src.providers import (
    APIFootballClient,
    ProviderError,
    ProviderNotConfigured,
    WikidataClient,
)


ALGORITHM = "HS256"


# ==========================================
# 1. MODELOS DE DOMINIO
# ==========================================
from src.models import (
    AlineacionPartido,
    AlineacionPartidoBase,
    AlineacionPartidoRead,
    Competicion,
    CompeticionBase,
    CompeticionPublicRead,
    CompeticionRead,
    Confederacion,
    ConfederacionBase,
    ConfederacionRead,
    Equipo,
    EquipoBase,
    EquipoConCompeticionesRead,
    EquipoRead,
    EstadisticasCreate,
    EstadisticasPartido,
    EstadoPartido,
    Estadio,
    EstadioBase,
    EstadioRead,
    EventoPartido,
    EventoPartidoBase,
    EventoPartidoRead,
    Fase,
    FaseBase,
    FaseRead,
    Jugador,
    JugadorBase,
    JugadorRead,
    MediaAsset,
    MediaAssetBase,
    MediaAssetRead,
    Partido,
    PartidoConEstadisticasRead,
    PartidoCreate,
    PartidoReadDetail,
    ProviderMapping,
    ProviderMappingBase,
    ProviderMappingRead,
    ProviderSnapshot,
    ProviderSnapshotRead,
    StandingRow,
    Temporada,
    TemporadaBase,
    TemporadaRead,
    TipoCompeticion,
    TipoEquipo,
)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=1024)


# ==========================================
# 4. CONFIGURACIÓN Y MIDDLEWARE (IMPORT LOCAL DE SEED)
# ==========================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    get_auth_settings()  # Fallar al arrancar si no se han configurado secretos.
    crear_tablas_db()
    # Importación local corregida apuntando a src.seed
    from src.seed import ejecutar_seed
    with Session(engine) as session:
        ejecutar_seed(session)
    yield


app = FastAPI(title="VÉRTICE API", lifespan=lifespan, root_path=os.getenv("ROOT_PATH", ""))

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)


def verificar_token(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = request.cookies.get("vertice_token")
    if not token and credentials:
        token = credentials.credentials

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado. Falta la cookie o el token de sesión.",
        )
    try:
        settings = get_auth_settings()
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[ALGORITHM],
            options={"require": ["sub", "exp"]},
        )
        if payload["sub"] != settings.admin_username:
            raise jwt.InvalidTokenError("Usuario no autorizado")
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado. Por favor, inicia sesión de nuevo.",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido.",
        )


def get_session():
    with Session(engine) as session:
        yield session


# ==========================================
# 5. ENDPOINTS DE AUTENTICACIÓN
# ==========================================
@app.post("/login")
def login(credentials: LoginRequest, response: Response):
    settings = get_auth_settings()
    password_ok = verify_password(credentials.password, settings.admin_password_hash)
    username_ok = hmac.compare_digest(
        credentials.username.encode("utf-8"), settings.admin_username.encode("utf-8")
    )
    if username_ok and password_ok:
        expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24)
        payload = {"sub": credentials.username, "exp": expire}
        token = jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)
        response.set_cookie(
            key="vertice_token", value=token, httponly=True,
            secure=settings.cookie_secure, samesite="lax", max_age=86400, path="/",
        )
        return {"ok": True, "mensaje": "Sesión iniciada correctamente"}
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales incorrectas")


@app.post("/logout")
def logout(response: Response):
    response.delete_cookie(
        key="vertice_token", path="/", httponly=True,
        secure=get_auth_settings().cookie_secure, samesite="lax",
    )
    return {"ok": True, "mensaje": "Sesión cerrada"}


# ==========================================
# 6. ENDPOINTS PÚBLICOS DE SOLO LECTURA
# ==========================================
def partido_publico(partido: Partido) -> PartidoConEstadisticasRead:
    return PartidoConEstadisticasRead(
        id=partido.id,
        competicion_id=partido.competicion_id,
        temporada_id=partido.temporada_id,
        fase_id=partido.fase_id,
        estadio_id=partido.estadio_id,
        equipo_local_id=partido.equipo_local_id,
        equipo_visitante_id=partido.equipo_visitante_id,
        fecha=partido.fecha,
        jornada=partido.jornada,
        marcador_local=partido.marcador_local,
        marcador_visitante=partido.marcador_visitante,
        estado=partido.estado,
        competicion=partido.competicion_rel,
        temporada=partido.temporada_rel,
        fase=partido.fase_rel,
        estadio=partido.estadio_rel,
        equipo_local=partido.equipo_local_rel,
        equipo_visitante=partido.equipo_visitante_rel,
        estadisticas=partido.estadisticas,
        eventos=partido.eventos,
        alineaciones=partido.alineaciones,
    )


@app.get("/public/competiciones/", response_model=list[CompeticionPublicRead])
def public_competiciones(session: Session = Depends(get_session)):
    return session.exec(select(Competicion)).all()


@app.get("/public/competiciones/{competition_id}/standings", response_model=list[StandingRow])
def public_standings(
    competition_id: int,
    season_id: int | None = None,
    session: Session = Depends(get_session),
):
    competition = session.get(Competicion, competition_id)
    if not competition:
        raise HTTPException(status_code=404, detail="Competición no encontrada")

    if season_id is not None:
        season = session.get(Temporada, season_id)
        if not season or season.competicion_id != competition_id:
            raise HTTPException(status_code=404, detail="Temporada no encontrada para esta competición")

    rows = {
        team.id: {
            "team": team,
            "played": 0,
            "won": 0,
            "drawn": 0,
            "lost": 0,
            "goals_for": 0,
            "goals_against": 0,
            "points": 0,
        }
        for team in competition.equipos
    }

    statement = select(Partido).where(
        Partido.competicion_id == competition_id,
        Partido.estado == EstadoPartido.FINALIZADO,
    )
    if season_id is not None:
        statement = statement.where(Partido.temporada_id == season_id)

    for match in session.exec(statement).all():
        if match.equipo_local_id not in rows or match.equipo_visitante_id not in rows:
            continue

        home = rows[match.equipo_local_id]
        away = rows[match.equipo_visitante_id]
        home["played"] += 1
        away["played"] += 1
        home["goals_for"] += match.marcador_local
        home["goals_against"] += match.marcador_visitante
        away["goals_for"] += match.marcador_visitante
        away["goals_against"] += match.marcador_local

        if match.marcador_local > match.marcador_visitante:
            home["won"] += 1
            home["points"] += 3
            away["lost"] += 1
        elif match.marcador_local < match.marcador_visitante:
            away["won"] += 1
            away["points"] += 3
            home["lost"] += 1
        else:
            home["drawn"] += 1
            away["drawn"] += 1
            home["points"] += 1
            away["points"] += 1

    ordered = sorted(
        rows.values(),
        key=lambda row: (
            row["points"],
            row["goals_for"] - row["goals_against"],
            row["goals_for"],
            row["team"].nombre,
        ),
        reverse=True,
    )

    return [
        StandingRow(
            rank=index,
            goal_difference=row["goals_for"] - row["goals_against"],
            **row,
        )
        for index, row in enumerate(ordered, start=1)
    ]


@app.get("/public/temporadas/", response_model=list[TemporadaRead])
def public_temporadas(session: Session = Depends(get_session)):
    return session.exec(select(Temporada)).all()


@app.get("/public/fases/", response_model=list[FaseRead])
def public_fases(session: Session = Depends(get_session)):
    return session.exec(select(Fase)).all()


@app.get("/public/estadios/", response_model=list[EstadioRead])
def public_estadios(session: Session = Depends(get_session)):
    return session.exec(select(Estadio)).all()


@app.get("/public/jugadores/", response_model=list[JugadorRead])
def public_jugadores(session: Session = Depends(get_session)):
    return session.exec(select(Jugador)).all()


@app.get("/public/equipos/", response_model=list[EquipoConCompeticionesRead])
def public_equipos(session: Session = Depends(get_session)):
    return session.exec(select(Equipo)).all()


@app.get("/public/partidos/", response_model=list[PartidoConEstadisticasRead])
def public_partidos(session: Session = Depends(get_session)):
    partidos = session.exec(select(Partido)).all()
    return [partido_publico(partido) for partido in partidos]


@app.get("/public/partidos/{partido_id}", response_model=PartidoConEstadisticasRead)
def public_detalle_partido(partido_id: int, session: Session = Depends(get_session)):
    partido = session.get(Partido, partido_id)
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    return partido_publico(partido)


@app.get("/public/media/{entity_type}/{entity_id}", response_model=list[MediaAssetRead])
def public_media(entity_type: str, entity_id: int, session: Session = Depends(get_session)):
    statement = select(MediaAsset).where(
        MediaAsset.entity_type == entity_type,
        MediaAsset.entity_id == entity_id,
    )
    return session.exec(statement).all()


# ==========================================
# 7. CONTEXTO FUTBOLÍSTICO Y PROCEDENCIA
# ==========================================
@app.post("/temporadas/", response_model=TemporadaRead)
def crear_temporada(
    temporada_in: TemporadaBase,
    session: Session = Depends(get_session),
    usuario: str = Depends(verificar_token),
):
    if not session.get(Competicion, temporada_in.competicion_id):
        raise HTTPException(status_code=404, detail="Competición no encontrada")
    temporada = Temporada.model_validate(temporada_in)
    session.add(temporada)
    session.commit()
    session.refresh(temporada)
    return temporada


@app.get("/temporadas/", response_model=list[TemporadaRead])
def leer_temporadas(
    session: Session = Depends(get_session),
    usuario: str = Depends(verificar_token),
):
    return session.exec(select(Temporada)).all()


@app.post("/fases/", response_model=FaseRead)
def crear_fase(
    fase_in: FaseBase,
    session: Session = Depends(get_session),
    usuario: str = Depends(verificar_token),
):
    if not session.get(Temporada, fase_in.temporada_id):
        raise HTTPException(status_code=404, detail="Temporada no encontrada")
    fase = Fase.model_validate(fase_in)
    session.add(fase)
    session.commit()
    session.refresh(fase)
    return fase


@app.get("/fases/", response_model=list[FaseRead])
def leer_fases(
    session: Session = Depends(get_session),
    usuario: str = Depends(verificar_token),
):
    return session.exec(select(Fase)).all()


@app.post("/estadios/", response_model=EstadioRead)
def crear_estadio(
    estadio_in: EstadioBase,
    session: Session = Depends(get_session),
    usuario: str = Depends(verificar_token),
):
    estadio = Estadio.model_validate(estadio_in)
    session.add(estadio)
    session.commit()
    session.refresh(estadio)
    return estadio


@app.get("/estadios/", response_model=list[EstadioRead])
def leer_estadios(
    session: Session = Depends(get_session),
    usuario: str = Depends(verificar_token),
):
    return session.exec(select(Estadio)).all()


@app.post("/jugadores/", response_model=JugadorRead)
def crear_jugador(
    jugador_in: JugadorBase,
    session: Session = Depends(get_session),
    usuario: str = Depends(verificar_token),
):
    jugador = Jugador.model_validate(jugador_in)
    session.add(jugador)
    session.commit()
    session.refresh(jugador)
    return jugador


@app.get("/jugadores/", response_model=list[JugadorRead])
def leer_jugadores(
    session: Session = Depends(get_session),
    usuario: str = Depends(verificar_token),
):
    return session.exec(select(Jugador)).all()


@app.post("/eventos/", response_model=EventoPartidoRead)
def crear_evento(
    evento_in: EventoPartidoBase,
    session: Session = Depends(get_session),
    usuario: str = Depends(verificar_token),
):
    partido = session.get(Partido, evento_in.partido_id)
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    if evento_in.equipo_id and not session.get(Equipo, evento_in.equipo_id):
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    if evento_in.jugador_id and not session.get(Jugador, evento_in.jugador_id):
        raise HTTPException(status_code=404, detail="Jugador no encontrado")
    if evento_in.asistente_id and not session.get(Jugador, evento_in.asistente_id):
        raise HTTPException(status_code=404, detail="Asistente no encontrado")
    if evento_in.equipo_id not in (None, partido.equipo_local_id, partido.equipo_visitante_id):
        raise HTTPException(status_code=400, detail="El equipo del evento no participa en el partido")

    evento = EventoPartido.model_validate(evento_in)
    session.add(evento)
    session.commit()
    session.refresh(evento)
    return evento


@app.post("/alineaciones/", response_model=AlineacionPartidoRead)
def crear_alineacion(
    alineacion_in: AlineacionPartidoBase,
    session: Session = Depends(get_session),
    usuario: str = Depends(verificar_token),
):
    partido = session.get(Partido, alineacion_in.partido_id)
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    if alineacion_in.equipo_id not in (partido.equipo_local_id, partido.equipo_visitante_id):
        raise HTTPException(status_code=400, detail="El equipo no participa en el partido")
    if not session.get(Jugador, alineacion_in.jugador_id):
        raise HTTPException(status_code=404, detail="Jugador no encontrado")

    alineacion = AlineacionPartido.model_validate(alineacion_in)
    session.add(alineacion)
    session.commit()
    session.refresh(alineacion)
    return alineacion


ENTITY_MODELS = {
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
            detail="entity_type no soportado. Usa competition, team, match, season, stage, venue o player.",
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


@app.get("/providers/api-football/status")
def api_football_status(usuario: str = Depends(verificar_token)):
    client = APIFootballClient()
    return {
        "provider": "api-football",
        "configured": client.configured,
        "base_url": client.base_url,
    }


@app.get("/providers/api-football/preview/league/{league_id}")
def preview_api_football_league(
    league_id: int,
    season: int | None = None,
    usuario: str = Depends(verificar_token),
):
    client = APIFootballClient()
    return provider_response(lambda: client.league(league_id, season))


@app.get("/providers/api-football/preview/fixtures")
def preview_api_football_fixtures(
    league_id: int,
    season: int,
    usuario: str = Depends(verificar_token),
):
    client = APIFootballClient()
    return provider_response(lambda: client.fixtures(league_id, season))


@app.get("/providers/api-football/preview/fixture/{fixture_id}")
def preview_api_football_fixture(
    fixture_id: int,
    usuario: str = Depends(verificar_token),
):
    client = APIFootballClient()
    return provider_response(lambda: client.fixture(fixture_id))


@app.get("/providers/api-football/preview/teams")
def preview_api_football_teams(
    league_id: int,
    season: int,
    usuario: str = Depends(verificar_token),
):
    client = APIFootballClient()
    return provider_response(lambda: client.teams(league_id, season))


@app.get("/providers/api-football/preview/rounds")
def preview_api_football_rounds(
    league_id: int,
    season: int,
    usuario: str = Depends(verificar_token),
):
    client = APIFootballClient()
    return provider_response(lambda: client.rounds(league_id, season))


@app.get("/providers/wikidata/preview/{qid}")
def preview_wikidata_item(
    qid: str,
    usuario: str = Depends(verificar_token),
):
    try:
        return WikidataClient().entity(qid)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/providers/wikidata/preview/{qid}/media")
def preview_wikidata_media(
    qid: str,
    usuario: str = Depends(verificar_token),
):
    try:
        return WikidataClient().commons_media(qid)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post(
    "/providers/wikidata/import-media/{entity_type}/{local_id}/{qid}",
    response_model=MediaAssetRead,
)
def import_wikidata_media(
    entity_type: str,
    local_id: int,
    qid: str,
    session: Session = Depends(get_session),
    usuario: str = Depends(verificar_token),
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
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return asset


@app.post("/providers/api-football/sync/competition/{competition_id}/season/{season_id}")
def sync_api_football_competition(
    competition_id: int,
    season_id: int,
    session: Session = Depends(get_session),
    usuario: str = Depends(verificar_token),
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


@app.post("/providers/api-football/sync/match/{match_id}")
def sync_api_football_match_detail(
    match_id: int,
    session: Session = Depends(get_session),
    usuario: str = Depends(verificar_token),
):
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


@app.get("/providers/snapshots/", response_model=list[ProviderSnapshotRead])
def leer_provider_snapshots(
    provider: str | None = None,
    entity_type: str | None = None,
    local_id: int | None = None,
    session: Session = Depends(get_session),
    usuario: str = Depends(verificar_token),
):
    statement = select(ProviderSnapshot)
    if provider:
        statement = statement.where(ProviderSnapshot.provider == provider)
    if entity_type:
        statement = statement.where(ProviderSnapshot.entity_type == entity_type)
    if local_id is not None:
        statement = statement.where(ProviderSnapshot.local_id == local_id)
    return session.exec(statement).all()


@app.post("/providers/mappings/", response_model=ProviderMappingRead)
def crear_provider_mapping(
    mapping_in: ProviderMappingBase,
    session: Session = Depends(get_session),
    usuario: str = Depends(verificar_token),
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
    session.add(mapping)
    session.commit()
    session.refresh(mapping)
    return mapping


@app.get("/providers/mappings/", response_model=list[ProviderMappingRead])
def leer_provider_mappings(
    session: Session = Depends(get_session),
    usuario: str = Depends(verificar_token),
):
    return session.exec(select(ProviderMapping)).all()


@app.post("/media/", response_model=MediaAssetRead)
def crear_media_asset(
    asset_in: MediaAssetBase,
    session: Session = Depends(get_session),
    usuario: str = Depends(verificar_token),
):
    validar_entidad_generica(asset_in.entity_type, asset_in.entity_id, session)
    asset = MediaAsset.model_validate(asset_in)
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return asset


@app.get("/media/", response_model=list[MediaAssetRead])
def leer_media_assets(
    session: Session = Depends(get_session),
    usuario: str = Depends(verificar_token),
):
    return session.exec(select(MediaAsset)).all()


# ==========================================
# 8. ENDPOINTS CONFEDERACIONES
# ==========================================


@app.post("/confederaciones/", response_model=ConfederacionRead)
def crear_confederacion(conf_in: ConfederacionBase, session: Session = Depends(get_session),
                        usuario: str = Depends(verificar_token)):
    conf_db = Confederacion.model_validate(conf_in)
    session.add(conf_db)
    session.commit()
    session.refresh(conf_db)
    return conf_db


@app.get("/confederaciones/", response_model=list[ConfederacionRead])
def leer_confederaciones(session: Session = Depends(get_session), usuario: str = Depends(verificar_token)):
    return session.exec(select(Confederacion)).all()


@app.put("/confederaciones/{id}", response_model=ConfederacionRead)
def editar_confederacion(id: int, conf_in: ConfederacionBase, session: Session = Depends(get_session),
                         usuario: str = Depends(verificar_token)):
    conf = session.get(Confederacion, id)
    if not conf:
        raise HTTPException(status_code=404, detail="Confederación no encontrada")
    for key, value in conf_in.model_dump().items():
        setattr(conf, key, value)
    session.add(conf)
    session.commit()
    session.refresh(conf)
    return conf


@app.delete("/confederaciones/{id}")
def eliminar_confederacion(id: int, session: Session = Depends(get_session), usuario: str = Depends(verificar_token)):
    conf = session.get(Confederacion, id)
    if not conf:
        raise HTTPException(status_code=404, detail="Confederación no encontrada")

    for c in conf.competiciones:
        c.confederacion_id = None
    for e in conf.equipos:
        e.confederacion_id = None

    session.delete(conf)
    session.commit()
    return {"ok": True, "mensaje": "Confederación eliminada. Datos asociados intactos y huérfanos."}


# ==========================================
# 9. ENDPOINTS COMPETICIONES (BLINDADAS)
# ==========================================
@app.post("/competiciones/", response_model=CompeticionRead)
def crear_competicion(comp_in: CompeticionBase, session: Session = Depends(get_session),
                      usuario: str = Depends(verificar_token)):
    if comp_in.tipo in [TipoCompeticion.LIGA_NACIONAL, TipoCompeticion.COPA_NACIONAL]:
        if not comp_in.pais or comp_in.pais.lower() == "internacional":
            raise HTTPException(status_code=400, detail="Ligas Nacionales deben tener un país específico.")
    else:
        comp_in.pais = "Internacional"

    comp_db = Competicion.model_validate(comp_in)
    session.add(comp_db)
    session.commit()
    session.refresh(comp_db)
    return comp_db


@app.get("/competiciones/", response_model=list[CompeticionRead])
def leer_competiciones(session: Session = Depends(get_session), usuario: str = Depends(verificar_token)):
    return session.exec(select(Competicion)).all()


@app.put("/competiciones/{id}", response_model=CompeticionRead)
def editar_competicion(id: int, comp_in: CompeticionBase, session: Session = Depends(get_session),
                       usuario: str = Depends(verificar_token)):
    comp = session.get(Competicion, id)
    if not comp:
        raise HTTPException(status_code=404, detail="Competición no encontrada")

    if comp_in.tipo in [TipoCompeticion.LIGA_NACIONAL, TipoCompeticion.COPA_NACIONAL]:
        if not comp_in.pais or comp_in.pais.lower() == "internacional":
            raise HTTPException(status_code=400, detail="Ligas Nacionales deben tener un país específico.")
    else:
        comp_in.pais = "Internacional"

    for equipo in comp.equipos:
        validar_compatibilidad(equipo, comp_in)

    for key, value in comp_in.model_dump().items():
        setattr(comp, key, value)
    session.add(comp)
    session.commit()
    session.refresh(comp)
    return comp


@app.delete("/competiciones/{id}")
def eliminar_competicion(id: int, session: Session = Depends(get_session), usuario: str = Depends(verificar_token)):
    comp = session.get(Competicion, id)
    if not comp:
        raise HTTPException(status_code=404, detail="Competición no encontrada")

    for p in comp.partidos:
        p.competicion_id = None

    session.delete(comp)
    session.commit()
    return {"ok": True, "mensaje": "Competición eliminada."}


# ==========================================
# 10. ENDPOINTS EQUIPOS (BLINDADOS)
# ==========================================
@app.post("/equipos/", response_model=EquipoRead)
def crear_equipo(equipo_in: EquipoBase, session: Session = Depends(get_session),
                 usuario: str = Depends(verificar_token)):
    if equipo_in.tipo == TipoEquipo.SELECCION:
        equipo_in.pais = equipo_in.nombre

    equipo_db = Equipo.model_validate(equipo_in)
    session.add(equipo_db)
    session.commit()
    session.refresh(equipo_db)
    return equipo_db


@app.get("/equipos/", response_model=list[EquipoConCompeticionesRead])
def leer_equipos(session: Session = Depends(get_session), usuario: str = Depends(verificar_token)):
    return session.exec(select(Equipo)).all()


@app.put("/equipos/{id}", response_model=EquipoRead)
def editar_equipo(id: int, eq_in: EquipoBase, session: Session = Depends(get_session),
                  usuario: str = Depends(verificar_token)):
    eq = session.get(Equipo, id)
    if not eq:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")

    if eq_in.tipo == TipoEquipo.SELECCION:
        eq_in.pais = eq_in.nombre

    for competicion in eq.competiciones:
        validar_compatibilidad(eq_in, competicion)

    for key, value in eq_in.model_dump().items():
        setattr(eq, key, value)
    session.add(eq)
    session.commit()
    session.refresh(eq)
    return eq


@app.delete("/equipos/{id}")
def eliminar_equipo(id: int, session: Session = Depends(get_session), usuario: str = Depends(verificar_token)):
    eq = session.get(Equipo, id)
    if not eq:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")

    for p in eq.partidos_local:
        p.equipo_local_id = None
    for p in eq.partidos_visitante:
        p.equipo_visitante_id = None

    session.delete(eq)
    session.commit()
    return {"ok": True, "mensaje": "Equipo eliminado."}


# Una única regla para matrículas, partidos y cambios de equipos/competiciones.
def validar_compatibilidad(equipo: EquipoBase, competicion: CompeticionBase):
    if competicion.tipo == TipoCompeticion.INTERNACIONAL_SELECCIONES and equipo.tipo != TipoEquipo.SELECCION:
        raise HTTPException(status_code=400, detail="A torneos de selecciones solo pueden entrar selecciones.")
    if competicion.tipo != TipoCompeticion.INTERNACIONAL_SELECCIONES and equipo.tipo == TipoEquipo.SELECCION:
        raise HTTPException(status_code=400, detail="Una selección no puede disputar torneos de clubes.")

    if competicion.tipo in [TipoCompeticion.LIGA_NACIONAL, TipoCompeticion.COPA_NACIONAL]:
        if equipo.pais != competicion.pais:
            raise HTTPException(status_code=400,
                                detail=f"Un equipo de {equipo.pais} no puede jugar en la liga de {competicion.pais}.")

    if competicion.confederacion_id and competicion.confederacion_id != equipo.confederacion_id:
        raise HTTPException(status_code=400, detail="El equipo no pertenece a la misma confederación del torneo.")


@app.post("/equipos/{equipo_id}/matricular/{competicion_id}")
def matricular_equipo(equipo_id: int, competicion_id: int, session: Session = Depends(get_session),
                      usuario: str = Depends(verificar_token)):
    equipo = session.get(Equipo, equipo_id)
    competicion = session.get(Competicion, competicion_id)
    if not equipo or not competicion:
        raise HTTPException(status_code=404, detail="Equipo o Competición no encontrados")
    validar_compatibilidad(equipo, competicion)

    if competicion in equipo.competiciones:
        return {"ok": False, "mensaje": f"El equipo {equipo.nombre} ya participa en {competicion.nombre}"}

    equipo.competiciones.append(competicion)
    session.add(equipo)
    session.commit()
    return {"ok": True, "mensaje": f"{equipo.nombre} matriculado exitosamente en {competicion.nombre}"}


# ==========================================
# 11. ENDPOINTS PARTIDOS REFACTORIZADOS
# ==========================================
def validar_contexto_partido(partido_in: PartidoCreate, comp: Competicion, session: Session) -> None:
    if partido_in.temporada_id:
        temporada = session.get(Temporada, partido_in.temporada_id)
        if not temporada:
            raise HTTPException(status_code=404, detail="Temporada no encontrada")
        if temporada.competicion_id != comp.id:
            raise HTTPException(status_code=400, detail="La temporada no pertenece a la competición")

    if partido_in.fase_id:
        fase = session.get(Fase, partido_in.fase_id)
        if not fase:
            raise HTTPException(status_code=404, detail="Fase no encontrada")
        if not partido_in.temporada_id or fase.temporada_id != partido_in.temporada_id:
            raise HTTPException(status_code=400, detail="La fase no pertenece a la temporada indicada")

    if partido_in.estadio_id and not session.get(Estadio, partido_in.estadio_id):
        raise HTTPException(status_code=404, detail="Estadio no encontrado")


@app.post("/partidos/", response_model=PartidoReadDetail)
def crear_partido(
    partido_in: PartidoCreate,
    session: Session = Depends(get_session),
    usuario: str = Depends(verificar_token),
):
    comp = session.get(Competicion, partido_in.competicion_id)
    local = session.get(Equipo, partido_in.equipo_local_id)
    visita = session.get(Equipo, partido_in.equipo_visitante_id)

    if not comp or not local or not visita:
        raise HTTPException(status_code=404, detail="Faltan datos de Competición o Equipos")
    if local.id == visita.id:
        raise HTTPException(status_code=400, detail="Un equipo no puede jugar contra sí mismo")

    validar_contexto_partido(partido_in, comp, session)

    for equipo in (local, visita):
        validar_compatibilidad(equipo, comp)
        if comp not in equipo.competiciones:
            raise HTTPException(
                status_code=400,
                detail=f"{equipo.nombre} no está matriculado en {comp.nombre}.",
            )

    partido_db = Partido.model_validate(partido_in)
    session.add(partido_db)
    session.commit()
    session.refresh(partido_db)
    return partido_publico(partido_db)


@app.get("/partidos/", response_model=list[PartidoReadDetail])
def leer_partidos(
    session: Session = Depends(get_session),
    usuario: str = Depends(verificar_token),
):
    partidos = session.exec(select(Partido)).all()
    return [partido_publico(partido) for partido in partidos]


@app.get("/partidos/{partido_id}", response_model=PartidoConEstadisticasRead)
def leer_detalle_partido(
    partido_id: int,
    session: Session = Depends(get_session),
    usuario: str = Depends(verificar_token),
):
    partido = session.get(Partido, partido_id)
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    return partido_publico(partido)


@app.post("/estadisticas/", response_model=EstadisticasPartido)
def crear_estadisticas(estadisticas: EstadisticasCreate, session: Session = Depends(get_session),
                       usuario: str = Depends(verificar_token)):
    if not session.get(Partido, estadisticas.partido_id):
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    estadisticas_db = EstadisticasPartido.model_validate(estadisticas)
    session.add(estadisticas_db)
    session.commit()
    session.refresh(estadisticas_db)
    return estadisticas_db


@app.delete("/partidos/{partido_id}")
def eliminar_partido(partido_id: int, session: Session = Depends(get_session), usuario: str = Depends(verificar_token)):
    partido = session.get(Partido, partido_id)
    if not partido:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    session.delete(partido)
    session.commit()
    return {"ok": True, "mensaje": f"Partido {partido_id} eliminado correctamente"}
