"""Añade contexto temporal, eventos, plantillas y trazabilidad de fuentes."""

from alembic import op
import sqlalchemy as sa


revision = "0002_football_context"
down_revision = "0001_legacy_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "temporada",
        sa.Column("competicion_id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("fecha_inicio", sa.Date(), nullable=True),
        sa.Column("fecha_fin", sa.Date(), nullable=True),
        sa.Column("activa", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["competicion_id"], ["competicion.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "fase",
        sa.Column("temporada_id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("tipo", sa.String(), nullable=False, server_default="jornada"),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["temporada_id"], ["temporada.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "estadio",
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("ciudad", sa.String(), nullable=True),
        sa.Column("pais", sa.String(), nullable=True),
        sa.Column("latitud", sa.Float(), nullable=True),
        sa.Column("longitud", sa.Float(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "jugador",
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("nombre_completo", sa.String(), nullable=True),
        sa.Column("posicion", sa.String(), nullable=True),
        sa.Column("nacionalidad", sa.String(), nullable=True),
        sa.Column("fecha_nacimiento", sa.Date(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "providermapping",
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("local_id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(), nullable=False),
        sa.Column("source_url", sa.String(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "entity_type",
            "external_id",
            name="uq_provider_mapping_external",
        ),
    )
    op.create_table(
        "mediaasset",
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("source_url", sa.String(), nullable=True),
        sa.Column("remote_id", sa.String(), nullable=True),
        sa.Column("author", sa.String(), nullable=True),
        sa.Column("license", sa.String(), nullable=True),
        sa.Column("license_url", sa.String(), nullable=True),
        sa.Column("credit", sa.String(), nullable=True),
        sa.Column("original_url", sa.String(), nullable=False),
        sa.Column("local_url", sa.String(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("mime_type", sa.String(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.add_column("partido", sa.Column("temporada_id", sa.Integer(), nullable=True))
    op.add_column("partido", sa.Column("fase_id", sa.Integer(), nullable=True))
    op.add_column("partido", sa.Column("estadio_id", sa.Integer(), nullable=True))
    op.add_column("partido", sa.Column("fecha", sa.DateTime(timezone=True), nullable=True))
    op.add_column("partido", sa.Column("jornada", sa.String(), nullable=True))
    op.create_foreign_key("fk_partido_temporada", "partido", "temporada", ["temporada_id"], ["id"])
    op.create_foreign_key("fk_partido_fase", "partido", "fase", ["fase_id"], ["id"])
    op.create_foreign_key("fk_partido_estadio", "partido", "estadio", ["estadio_id"], ["id"])
    op.create_index("ix_partido_fecha", "partido", ["fecha"])

    op.create_table(
        "jugadorequipo",
        sa.Column("jugador_id", sa.Integer(), nullable=False),
        sa.Column("equipo_id", sa.Integer(), nullable=False),
        sa.Column("fecha_inicio", sa.Date(), nullable=True),
        sa.Column("fecha_fin", sa.Date(), nullable=True),
        sa.Column("dorsal", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["equipo_id"], ["equipo.id"]),
        sa.ForeignKeyConstraint(["jugador_id"], ["jugador.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_jugadorequipo_equipo_id", "jugadorequipo", ["equipo_id"])
    op.create_index("ix_jugadorequipo_jugador_id", "jugadorequipo", ["jugador_id"])

    op.create_table(
        "eventopartido",
        sa.Column("partido_id", sa.Integer(), nullable=False),
        sa.Column("equipo_id", sa.Integer(), nullable=True),
        sa.Column("jugador_id", sa.Integer(), nullable=True),
        sa.Column("asistente_id", sa.Integer(), nullable=True),
        sa.Column("tipo", sa.String(), nullable=False),
        sa.Column("minuto", sa.Integer(), nullable=False),
        sa.Column("adicional", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("detalle", sa.String(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["asistente_id"], ["jugador.id"]),
        sa.ForeignKeyConstraint(["equipo_id"], ["equipo.id"]),
        sa.ForeignKeyConstraint(["jugador_id"], ["jugador.id"]),
        sa.ForeignKeyConstraint(["partido_id"], ["partido.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "alineacionpartido",
        sa.Column("partido_id", sa.Integer(), nullable=False),
        sa.Column("equipo_id", sa.Integer(), nullable=False),
        sa.Column("jugador_id", sa.Integer(), nullable=False),
        sa.Column("titular", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("posicion", sa.String(), nullable=True),
        sa.Column("dorsal", sa.Integer(), nullable=True),
        sa.Column("orden", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["equipo_id"], ["equipo.id"]),
        sa.ForeignKeyConstraint(["jugador_id"], ["jugador.id"]),
        sa.ForeignKeyConstraint(["partido_id"], ["partido.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("alineacionpartido")
    op.drop_table("eventopartido")
    op.drop_index("ix_jugadorequipo_jugador_id", table_name="jugadorequipo")
    op.drop_index("ix_jugadorequipo_equipo_id", table_name="jugadorequipo")
    op.drop_table("jugadorequipo")
    op.drop_index("ix_partido_fecha", table_name="partido")
    op.drop_constraint("fk_partido_estadio", "partido", type_="foreignkey")
    op.drop_constraint("fk_partido_fase", "partido", type_="foreignkey")
    op.drop_constraint("fk_partido_temporada", "partido", type_="foreignkey")
    op.drop_column("partido", "jornada")
    op.drop_column("partido", "fecha")
    op.drop_column("partido", "estadio_id")
    op.drop_column("partido", "fase_id")
    op.drop_column("partido", "temporada_id")
    op.drop_table("mediaasset")
    op.drop_table("providermapping")
    op.drop_table("jugador")
    op.drop_table("estadio")
    op.drop_table("fase")
    op.drop_table("temporada")
