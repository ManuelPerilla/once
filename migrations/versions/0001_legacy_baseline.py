"""Baseline del esquema original de VÉRTICE."""

from alembic import op
import sqlalchemy as sa


revision = "0001_legacy_baseline"
down_revision = None
branch_labels = None
depends_on = None


estado_partido = sa.Enum("VIVO", "FINALIZADO", "PROGRAMADO", name="estadopartido")
tipo_competicion = sa.Enum(
    "LIGA_NACIONAL",
    "COPA_NACIONAL",
    "INTERNACIONAL_CLUBES",
    "INTERNACIONAL_SELECCIONES",
    name="tipocompeticion",
)
tipo_equipo = sa.Enum("CLUB", "SELECCION", name="tipoequipo")


def upgrade() -> None:
    op.create_table(
        "confederacion",
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("logo", sa.String(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nombre"),
    )
    op.create_index("ix_confederacion_nombre", "confederacion", ["nombre"])

    op.create_table(
        "competicion",
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("logo", sa.String(), nullable=False),
        sa.Column("tipo", tipo_competicion, nullable=False),
        sa.Column("pais", sa.String(), nullable=False),
        sa.Column("confederacion_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["confederacion_id"], ["confederacion.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "equipo",
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("logo", sa.String(), nullable=False),
        sa.Column("tipo", tipo_equipo, nullable=False),
        sa.Column("pais", sa.String(), nullable=False),
        sa.Column("confederacion_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["confederacion_id"], ["confederacion.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "participacion",
        sa.Column("equipo_id", sa.Integer(), nullable=False),
        sa.Column("competicion_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["competicion_id"], ["competicion.id"]),
        sa.ForeignKeyConstraint(["equipo_id"], ["equipo.id"]),
        sa.PrimaryKeyConstraint("equipo_id", "competicion_id"),
    )

    op.create_table(
        "partido",
        sa.Column("competicion_id", sa.Integer(), nullable=True),
        sa.Column("equipo_local_id", sa.Integer(), nullable=True),
        sa.Column("equipo_visitante_id", sa.Integer(), nullable=True),
        sa.Column("marcador_local", sa.Integer(), nullable=False),
        sa.Column("marcador_visitante", sa.Integer(), nullable=False),
        sa.Column("estado", estado_partido, nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["competicion_id"], ["competicion.id"]),
        sa.ForeignKeyConstraint(["equipo_local_id"], ["equipo.id"]),
        sa.ForeignKeyConstraint(["equipo_visitante_id"], ["equipo.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "estadisticaspartido",
        sa.Column("partido_id", sa.Integer(), nullable=False),
        sa.Column("posesion_local", sa.Integer(), nullable=False),
        sa.Column("posesion_visitante", sa.Integer(), nullable=False),
        sa.Column("tiros_puerta_local", sa.Integer(), nullable=False),
        sa.Column("tiros_puerta_visitante", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["partido_id"], ["partido.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("estadisticaspartido")
    op.drop_table("partido")
    op.drop_table("participacion")
    op.drop_table("equipo")
    op.drop_table("competicion")
    op.drop_index("ix_confederacion_nombre", table_name="confederacion")
    op.drop_table("confederacion")
    estado_partido.drop(op.get_bind(), checkfirst=True)
    tipo_equipo.drop(op.get_bind(), checkfirst=True)
    tipo_competicion.drop(op.get_bind(), checkfirst=True)
