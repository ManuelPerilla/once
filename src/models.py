import datetime
import uuid
from enum import Enum

from sqlalchemy import JSON, CheckConstraint, Column, DateTime, Index, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from src.datetime_type import UTCDateTime


class EstadoPartido(str, Enum):
    VIVO = "en vivo"
    FINALIZADO = "finalizado"
    PROGRAMADO = "programado"
    APLAZADO = "aplazado"
    SUSPENDIDO = "suspendido"
    CANCELADO = "cancelado"
    ABANDONADO = "abandonado"
    ADJUDICADO = "adjudicado"
    DESCONOCIDO = "desconocido"


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


class Grupo(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("fase_id", "nombre", name="uq_grupo_fase_nombre"),)
    id: int | None = Field(default=None, primary_key=True)
    fase_id: int = Field(foreign_key="fase.id", index=True)
    nombre: str


class ParticipacionTemporada(SQLModel, table=True):
    equipo_id: int = Field(foreign_key="equipo.id", primary_key=True)
    temporada_id: int = Field(foreign_key="temporada.id", primary_key=True, index=True)
    source: str
    verified_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        sa_column=Column(UTCDateTime(), nullable=False),
    )


class ParticipacionGrupo(SQLModel, table=True):
    equipo_id: int = Field(foreign_key="equipo.id", primary_key=True)
    grupo_id: int = Field(foreign_key="grupo.id", primary_key=True, index=True)
    source: str = "unverified"


class ParticipacionFase(SQLModel, table=True):
    equipo_id: int = Field(foreign_key="equipo.id", primary_key=True)
    fase_id: int = Field(foreign_key="fase.id", primary_key=True, index=True)
    source: str = "unverified"


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


class PlantillaRead(SQLModel):
    id: int
    jugador_id: int
    equipo_id: int
    jugador_nombre: str
    equipo_nombre: str
    fecha_inicio: datetime.date | None = None
    fecha_fin: datetime.date | None = None
    dorsal: int | None = None


class PlantillaPage(SQLModel):
    items: list[PlantillaRead]
    total: int
    page: int
    page_size: int


class EstadisticasBase(SQLModel):
    partido_id: int = Field(foreign_key="partido.id", gt=0)
    source: str | None = None
    source_key: str | None = None
    posesion_local: int = Field(ge=0, le=100)
    posesion_visitante: int = Field(ge=0, le=100)
    tiros_puerta_local: int = Field(ge=0)
    tiros_puerta_visitante: int = Field(ge=0)


class EstadisticasCreate(EstadisticasBase):
    pass


class EstadisticasPartido(EstadisticasBase, table=True):
    __table_args__ = (
        UniqueConstraint("partido_id", "source", "source_key", name="uq_stats_source_key"),
        Index("ix_estadisticaspartido_partido", "partido_id"),
    )
    id: int | None = Field(default=None, primary_key=True)
    partido: "Partido" = Relationship(back_populates="estadisticas")


class PartidoBase(SQLModel):
    competicion_id: int | None = Field(default=None, foreign_key="competicion.id")
    temporada_id: int | None = Field(default=None, foreign_key="temporada.id")
    fase_id: int | None = Field(default=None, foreign_key="fase.id")
    grupo_id: int | None = Field(default=None, foreign_key="grupo.id")
    estadio_id: int | None = Field(default=None, foreign_key="estadio.id")
    equipo_local_id: int | None = Field(default=None, foreign_key="equipo.id")
    equipo_visitante_id: int | None = Field(default=None, foreign_key="equipo.id")
    fecha: datetime.datetime | None = Field(
        default=None,
        sa_column=Column(UTCDateTime(), nullable=True, index=True),
    )
    jornada: str | None = None
    marcador_local: int | None = Field(default=None, ge=0)
    marcador_visitante: int | None = Field(default=None, ge=0)
    estado: EstadoPartido
    estado_fuente: str | None = None


class Partido(PartidoBase, table=True):
    __table_args__ = (
        CheckConstraint("equipo_local_id != equipo_visitante_id", name="ck_partido_distinct_teams"),
        CheckConstraint("marcador_local >= 0", name="ck_partido_score_home"),
        CheckConstraint("marcador_visitante >= 0", name="ck_partido_score_away"),
        Index("ix_partido_contexto_fecha", "competicion_id", "temporada_id", "fecha", "id"),
        Index("ix_partido_tabla", "temporada_id", "fase_id", "grupo_id", "estado"),
    )
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
    source_key: str | None = None
    equipo_id: int | None = Field(default=None, foreign_key="equipo.id")
    jugador_id: int | None = Field(default=None, foreign_key="jugador.id")
    asistente_id: int | None = Field(default=None, foreign_key="jugador.id")
    tipo: str
    minuto: int = Field(ge=0, le=150)
    adicional: int = Field(default=0, ge=0, le=30)
    detalle: str | None = None


class EventoPartido(EventoPartidoBase, table=True):
    __table_args__ = (
        UniqueConstraint("partido_id", "source", "source_key", name="uq_event_source_key"),
        Index("ix_eventopartido_partido", "partido_id"),
    )
    id: int | None = Field(default=None, primary_key=True)
    partido: Partido = Relationship(back_populates="eventos")


class EventoPartidoRead(EventoPartidoBase):
    id: int


class AlineacionPartidoBase(SQLModel):
    partido_id: int = Field(foreign_key="partido.id", gt=0)
    source: str | None = None
    source_key: str | None = None
    equipo_id: int = Field(foreign_key="equipo.id", gt=0)
    jugador_id: int = Field(foreign_key="jugador.id", gt=0)
    titular: bool = False
    posicion: str | None = None
    dorsal: int | None = Field(default=None, ge=0, le=99)
    orden: int | None = Field(default=None, ge=0)


class AlineacionPartido(AlineacionPartidoBase, table=True):
    __table_args__ = (
        UniqueConstraint("partido_id", "source", "source_key", name="uq_lineup_source_key"),
        Index("ix_alineacionpartido_partido", "partido_id"),
    )
    id: int | None = Field(default=None, primary_key=True)
    partido: Partido = Relationship(back_populates="alineaciones")


class AlineacionPartidoRead(AlineacionPartidoBase):
    id: int


class PartidoReadDetail(SQLModel):
    id: int
    competicion_id: int | None
    temporada_id: int | None = None
    fase_id: int | None = None
    grupo_id: int | None = None
    estadio_id: int | None = None
    equipo_local_id: int | None
    equipo_visitante_id: int | None
    fecha: datetime.datetime | None = None
    jornada: str | None = None
    marcador_local: int | None
    marcador_visitante: int | None
    estado: EstadoPartido
    estado_fuente: str | None = None
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
    external_scope: str = ""
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
            "external_scope",
            name="uq_provider_mapping_external",
        ),
        Index("ix_provider_mapping_local", "provider", "entity_type", "local_id"),
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


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


class EntityRevision(SQLModel, table=True):
    entity_type: str = Field(primary_key=True)
    entity_id: int = Field(primary_key=True)
    version: int = 0


class FieldState(SQLModel, table=True):
    entity_type: str = Field(primary_key=True)
    entity_id: int = Field(primary_key=True)
    field: str = Field(primary_key=True)
    protected: bool = False
    source: str | None = None
    observed_at: datetime.datetime | None = Field(
        default=None, sa_column=Column(UTCDateTime(), nullable=True)
    )


class AuditChange(SQLModel, table=True):
    __table_args__ = (Index("ix_audit_entity_id", "entity_type", "entity_id", "id"),)
    id: int | None = Field(default=None, primary_key=True)
    entity_type: str
    entity_id: int
    field: str
    before: object | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    after: object | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    action: str
    actor: str
    reason: str
    source: str | None = None
    run_id: str | None = None
    version: int
    created_at: datetime.datetime = Field(
        default_factory=utcnow, sa_column=Column(UTCDateTime(), nullable=False)
    )


class DataIssue(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    key: str = Field(unique=True, index=True)
    entity_type: str
    entity_id: int
    field: str | None = None
    source: str
    reason: str
    status: str = Field(default="open", index=True)
    proposed: object | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    occurrences: int = 1
    created_at: datetime.datetime = Field(
        default_factory=utcnow, sa_column=Column(UTCDateTime(), nullable=False)
    )
    updated_at: datetime.datetime = Field(
        default_factory=utcnow, sa_column=Column(UTCDateTime(), nullable=False)
    )


class StandingRule(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("scope_key", "version", name="uq_standing_rule_version"),)
    id: int | None = Field(default=None, primary_key=True)
    scope_key: str = Field(index=True)
    temporada_id: int = Field(foreign_key="temporada.id")
    fase_id: int | None = Field(default=None, foreign_key="fase.id")
    grupo_id: int | None = Field(default=None, foreign_key="grupo.id")
    version: int
    name: str
    source_url: str
    # Only rules explicitly reviewed by an operator can publish a calculated table.
    verified: bool = False
    config: dict = Field(sa_column=Column(JSON, nullable=False))
    actor: str
    created_at: datetime.datetime = Field(
        default_factory=utcnow, sa_column=Column(UTCDateTime(), nullable=False)
    )


class StandingAdjustment(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    scope_key: str = Field(index=True)
    equipo_id: int = Field(foreign_key="equipo.id")
    points: int
    reason: str
    source_url: str
    actor: str
    created_at: datetime.datetime = Field(
        default_factory=utcnow, sa_column=Column(UTCDateTime(), nullable=False)
    )


class StandingProjection(SQLModel, table=True):
    scope_key: str = Field(primary_key=True)
    rule_id: int = Field(foreign_key="standingrule.id")
    input_hash: str
    rows: list = Field(sa_column=Column(JSON, nullable=False))
    updated_at: datetime.datetime = Field(
        default_factory=utcnow, sa_column=Column(UTCDateTime(), nullable=False)
    )


class OfficialStandingSnapshot(SQLModel, table=True):
    __table_args__ = (Index("ix_official_table_latest", "scope_key", "fetched_at"),)
    id: int | None = Field(default=None, primary_key=True)
    scope_key: str
    source: str
    source_url: str
    content_hash: str
    rows: list = Field(sa_column=Column(JSON, nullable=False))
    fetched_at: datetime.datetime = Field(
        default_factory=utcnow, sa_column=Column(UTCDateTime(), nullable=False)
    )
