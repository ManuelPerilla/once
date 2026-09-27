import datetime
import uuid
from enum import Enum

from sqlalchemy import JSON, Column, DateTime, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from src.datetime_type import UTCDateTime


class EstadoPartido(str, Enum):
    VIVO = "en vivo"
    FINALIZADO = "finalizado"
    PROGRAMADO = "programado"


class TipoCompeticion(str, Enum):
    LIGA_NACIONAL = "liga_nacional"
    COPA_NACIONAL = "copa_nacional"
    INTERNACIONAL_CLUBES = "internacional_clubes"
    INTERNACIONAL_SELECCIONES = "internacional_selecciones"


class TipoEquipo(str, Enum):
    CLUB = "club"
    SELECCION = "seleccion"


class Participacion(SQLModel, table=True):
    equipo_id: int | None = Field(default=None, foreign_key="equipo.id", primary_key=True)
    competicion_id: int | None = Field(default=None, foreign_key="competicion.id", primary_key=True)


class ConfederacionBase(SQLModel):
    nombre: str = Field(index=True, unique=True)
    logo: str


class Confederacion(ConfederacionBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    competiciones: list["Competicion"] = Relationship(back_populates="confederacion")
    equipos: list["Equipo"] = Relationship(back_populates="confederacion")


class ConfederacionRead(ConfederacionBase):
    id: int


class CompeticionBase(SQLModel):
    nombre: str
    logo: str
    tipo: TipoCompeticion
    pais: str = Field(default="Internacional")
    confederacion_id: int | None = Field(default=None, foreign_key="confederacion.id")


class Competicion(CompeticionBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    confederacion: Confederacion | None = Relationship(back_populates="competiciones")
    equipos: list["Equipo"] = Relationship(back_populates="competiciones", link_model=Participacion)
    temporadas: list["Temporada"] = Relationship(back_populates="competicion")
    partidos: list["Partido"] = Relationship(back_populates="competicion_rel")


class CompeticionRead(CompeticionBase):
    id: int


class TemporadaBase(SQLModel):
    competicion_id: int = Field(foreign_key="competicion.id", gt=0)
    nombre: str
    fecha_inicio: datetime.date | None = None
    fecha_fin: datetime.date | None = None
    activa: bool = False


class Temporada(TemporadaBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    competicion: Competicion = Relationship(back_populates="temporadas")
    fases: list["Fase"] = Relationship(back_populates="temporada")
    partidos: list["Partido"] = Relationship(back_populates="temporada_rel")


class TemporadaRead(TemporadaBase):
    id: int


class CompeticionPublicRead(CompeticionRead):
    temporadas: list[TemporadaRead] = []


class FaseBase(SQLModel):
    temporada_id: int = Field(foreign_key="temporada.id", gt=0)
    nombre: str
    tipo: str = "jornada"
    orden: int = Field(default=0, ge=0)


class Fase(FaseBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    temporada: Temporada = Relationship(back_populates="fases")
    partidos: list["Partido"] = Relationship(back_populates="fase_rel")


class FaseRead(FaseBase):
    id: int


class EstadioBase(SQLModel):
    nombre: str
    ciudad: str | None = None
    pais: str | None = None
    latitud: float | None = Field(default=None, ge=-90, le=90)
    longitud: float | None = Field(default=None, ge=-180, le=180)


class Estadio(EstadioBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    partidos: list["Partido"] = Relationship(back_populates="estadio_rel")


class EstadioRead(EstadioBase):
    id: int


class EquipoBase(SQLModel):
    nombre: str
    logo: str
    tipo: TipoEquipo
    pais: str = Field(default="Internacional")
    confederacion_id: int | None = Field(default=None, foreign_key="confederacion.id")


class Equipo(EquipoBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    confederacion: Confederacion | None = Relationship(back_populates="equipos")
    competiciones: list[Competicion] = Relationship(
        back_populates="equipos", link_model=Participacion
    )
    partidos_local: list["Partido"] = Relationship(
        back_populates="equipo_local_rel",
        sa_relationship_kwargs={"foreign_keys": "Partido.equipo_local_id"},
    )
    partidos_visitante: list["Partido"] = Relationship(
        back_populates="equipo_visitante_rel",
        sa_relationship_kwargs={"foreign_keys": "Partido.equipo_visitante_id"},
    )


class EquipoRead(EquipoBase):
    id: int


class EquipoConCompeticionesRead(EquipoRead):
    competiciones: list[CompeticionRead] = []


class StandingRow(SQLModel):
    rank: int
    team: EquipoRead
    played: int
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int
    goal_difference: int
    points: int


class JugadorBase(SQLModel):
    nombre: str
    nombre_completo: str | None = None
    posicion: str | None = None
    nacionalidad: str | None = None
    fecha_nacimiento: datetime.date | None = None


class Jugador(JugadorBase, table=True):
    id: int | None = Field(default=None, primary_key=True)


class JugadorRead(JugadorBase):
    id: int


class JugadorEquipo(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    jugador_id: int = Field(foreign_key="jugador.id", index=True)
    equipo_id: int = Field(foreign_key="equipo.id", index=True)
    fecha_inicio: datetime.date | None = None
    fecha_fin: datetime.date | None = None
    dorsal: int | None = Field(default=None, ge=0, le=99)


class EstadisticasBase(SQLModel):
    partido_id: int = Field(foreign_key="partido.id", gt=0)
    source: str | None = None
    posesion_local: int = Field(ge=0, le=100)
    posesion_visitante: int = Field(ge=0, le=100)
    tiros_puerta_local: int = Field(ge=0)
    tiros_puerta_visitante: int = Field(ge=0)


class EstadisticasCreate(EstadisticasBase):
    pass


class EstadisticasPartido(EstadisticasBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    partido: "Partido" = Relationship(back_populates="estadisticas")


class PartidoBase(SQLModel):
    competicion_id: int | None = Field(default=None, foreign_key="competicion.id")
    temporada_id: int | None = Field(default=None, foreign_key="temporada.id")
    fase_id: int | None = Field(default=None, foreign_key="fase.id")
    estadio_id: int | None = Field(default=None, foreign_key="estadio.id")
    equipo_local_id: int | None = Field(default=None, foreign_key="equipo.id")
    equipo_visitante_id: int | None = Field(default=None, foreign_key="equipo.id")
    fecha: datetime.datetime | None = Field(
        default=None,
        sa_column=Column(UTCDateTime(), nullable=True, index=True),
    )
    jornada: str | None = None
    marcador_local: int = Field(default=0, ge=0)
    marcador_visitante: int = Field(default=0, ge=0)
    estado: EstadoPartido


class Partido(PartidoBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    competicion_rel: Competicion | None = Relationship(back_populates="partidos")
    temporada_rel: Temporada | None = Relationship(back_populates="partidos")
    fase_rel: Fase | None = Relationship(back_populates="partidos")
    estadio_rel: Estadio | None = Relationship(back_populates="partidos")
    equipo_local_rel: Equipo | None = Relationship(
        back_populates="partidos_local",
        sa_relationship_kwargs={"foreign_keys": "[Partido.equipo_local_id]"},
    )
    equipo_visitante_rel: Equipo | None = Relationship(
        back_populates="partidos_visitante",
        sa_relationship_kwargs={"foreign_keys": "[Partido.equipo_visitante_id]"},
    )
    estadisticas: list[EstadisticasPartido] = Relationship(
        back_populates="partido",
        cascade_delete=True,
    )
    eventos: list["EventoPartido"] = Relationship(back_populates="partido", cascade_delete=True)
    alineaciones: list["AlineacionPartido"] = Relationship(
        back_populates="partido", cascade_delete=True
    )


class PartidoCreate(PartidoBase):
    competicion_id: int = Field(gt=0)
    equipo_local_id: int = Field(gt=0)
    equipo_visitante_id: int = Field(gt=0)


class EventoPartidoBase(SQLModel):
    partido_id: int = Field(foreign_key="partido.id", gt=0)
    source: str | None = None
    equipo_id: int | None = Field(default=None, foreign_key="equipo.id")
    jugador_id: int | None = Field(default=None, foreign_key="jugador.id")
    asistente_id: int | None = Field(default=None, foreign_key="jugador.id")
    tipo: str
    minuto: int = Field(ge=0, le=150)
    adicional: int = Field(default=0, ge=0, le=30)
    detalle: str | None = None


class EventoPartido(EventoPartidoBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    partido: Partido = Relationship(back_populates="eventos")


class EventoPartidoRead(EventoPartidoBase):
    id: int


class AlineacionPartidoBase(SQLModel):
    partido_id: int = Field(foreign_key="partido.id", gt=0)
    source: str | None = None
    equipo_id: int = Field(foreign_key="equipo.id", gt=0)
    jugador_id: int = Field(foreign_key="jugador.id", gt=0)
    titular: bool = False
    posicion: str | None = None
    dorsal: int | None = Field(default=None, ge=0, le=99)
    orden: int | None = Field(default=None, ge=0)


class AlineacionPartido(AlineacionPartidoBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    partido: Partido = Relationship(back_populates="alineaciones")


class AlineacionPartidoRead(AlineacionPartidoBase):
    id: int


class PartidoReadDetail(SQLModel):
    id: int
    competicion_id: int | None
    temporada_id: int | None = None
    fase_id: int | None = None
    estadio_id: int | None = None
    equipo_local_id: int | None
    equipo_visitante_id: int | None
    fecha: datetime.datetime | None = None
    jornada: str | None = None
    marcador_local: int
    marcador_visitante: int
    estado: EstadoPartido
    competicion: CompeticionRead | None = None
    temporada: TemporadaRead | None = None
    fase: FaseRead | None = None
    estadio: EstadioRead | None = None
    equipo_local: EquipoRead | None = None
    equipo_visitante: EquipoRead | None = None


class PartidoConEstadisticasRead(PartidoReadDetail):
    estadisticas: list[EstadisticasPartido] = []
    eventos: list[EventoPartidoRead] = []
    alineaciones: list[AlineacionPartidoRead] = []


class ProviderMappingBase(SQLModel):
    provider: str
    entity_type: str
    local_id: int = Field(gt=0)
    external_id: str
    source_url: str | None = None
    verified_at: datetime.datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class ProviderMapping(ProviderMappingBase, table=True):
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "entity_type",
            "external_id",
            name="uq_provider_mapping_external",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)


class ProviderMappingRead(ProviderMappingBase):
    id: int


class ProviderSnapshotBase(SQLModel):
    provider: str
    entity_type: str
    local_id: int = Field(gt=0)
    kind: str
    fetched_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    payload: dict = Field(sa_column=Column(JSON, nullable=False))


class ProviderSnapshot(ProviderSnapshotBase, table=True):
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "entity_type",
            "local_id",
            "kind",
            name="uq_provider_snapshot_latest",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)


class ProviderSnapshotRead(ProviderSnapshotBase):
    id: int


class CatalogImportBatch(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    collection: str = Field(index=True)
    fetched_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(UTCDateTime(), nullable=False),
    )
    # Preserve the observations that the operator actually reviewed.
    payload: dict = Field(sa_column=Column(JSON, nullable=False))
    last_result: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))


class MediaAssetBase(SQLModel):
    entity_type: str
    entity_id: int = Field(gt=0)
    tipo: str
    source: str
    source_url: str | None = None
    remote_id: str | None = None
    author: str | None = None
    license: str | None = None
    license_url: str | None = None
    credit: str | None = None
    original_url: str
    local_url: str | None = None
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    mime_type: str | None = None
    verified_at: datetime.datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class MediaAsset(MediaAssetBase, table=True):
    id: int | None = Field(default=None, primary_key=True)


class MediaAssetRead(MediaAssetBase):
    id: int
