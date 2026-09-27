"""Season identities, protected corrections and versioned standings."""

import sqlalchemy as sa
from alembic import op

revision = "0005_domain_automation"
down_revision = "0004_catalog_imports"
branch_labels = None
depends_on = None

NEW_STATES = ("APLAZADO", "SUSPENDIDO", "CANCELADO", "ABANDONADO", "ADJUDICADO", "DESCONOCIDO")


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for state in NEW_STATES:
            op.execute(f"ALTER TYPE estadopartido ADD VALUE IF NOT EXISTS '{state}'")
    with op.batch_alter_table("providermapping") as batch:
        batch.add_column(
            sa.Column("external_scope", sa.String(), nullable=False, server_default="")
        )
        batch.drop_constraint("uq_provider_mapping_external", type_="unique")
        batch.create_unique_constraint(
            "uq_provider_mapping_external",
            ["provider", "entity_type", "external_id", "external_scope"],
        )
        batch.create_index("ix_provider_mapping_local", ["provider", "entity_type", "local_id"])
    op.create_table(
        "grupo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fase_id", sa.Integer(), sa.ForeignKey("fase.id"), nullable=False),
        sa.Column("nombre", sa.String(), nullable=False),
        sa.UniqueConstraint("fase_id", "nombre", name="uq_grupo_fase_nombre"),
    )
    op.create_index("ix_grupo_fase_id", "grupo", ["fase_id"])
    for table, parent in (
        ("participaciontemporada", "temporada"),
        ("participacionfase", "fase"),
        ("participaciongrupo", "grupo"),
    ):
        columns = [
            sa.Column("equipo_id", sa.Integer(), sa.ForeignKey("equipo.id"), primary_key=True),
            sa.Column(
                f"{parent}_id", sa.Integer(), sa.ForeignKey(f"{parent}.id"), primary_key=True
            ),
        ]
        if parent == "temporada":
            columns += [
                sa.Column("source", sa.String(), nullable=False),
                sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
            ]
        else:
            columns += [
                sa.Column("source", sa.String(), nullable=False, server_default="unverified")
            ]
        op.create_table(table, *columns)
        op.create_index(f"ix_{table}_{parent}_id", table, [f"{parent}_id"])
    with op.batch_alter_table("partido") as batch:
        batch.add_column(sa.Column("grupo_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_partido_grupo", "grupo", ["grupo_id"], ["id"])
        batch.add_column(sa.Column("estado_fuente", sa.String(), nullable=True))
        for field in ("marcador_local", "marcador_visitante"):
            batch.alter_column(field, existing_type=sa.Integer(), nullable=True)
        batch.create_index(
            "ix_partido_contexto_fecha", ["competicion_id", "temporada_id", "fecha", "id"]
        )
        batch.create_index("ix_partido_tabla", ["temporada_id", "fase_id", "grupo_id", "estado"])
        batch.create_check_constraint(
            "ck_partido_distinct_teams", "equipo_local_id != equipo_visitante_id"
        )
        batch.create_check_constraint("ck_partido_score_home", "marcador_local >= 0")
        batch.create_check_constraint("ck_partido_score_away", "marcador_visitante >= 0")
    for table, key in (
        ("eventopartido", "event"),
        ("alineacionpartido", "lineup"),
        ("estadisticaspartido", "stats"),
    ):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("source_key", sa.String(), nullable=True))
            batch.create_unique_constraint(
                f"uq_{key}_source_key", ["partido_id", "source", "source_key"]
            )
            batch.create_index(f"ix_{table}_partido", ["partido_id"])
    _create_audit()
    _create_standings()
    _preserve_legacy(bind)
    if bind.dialect.name == "postgresql":
        op.execute(
            """CREATE FUNCTION once_audit_append_only() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Audit history is append-only'; END; $$"""
        )
        op.execute(
            "CREATE TRIGGER audit_append_only BEFORE UPDATE OR DELETE ON auditchange FOR EACH ROW EXECUTE FUNCTION once_audit_append_only()"
        )


def _create_audit():
    op.create_table(
        "entityrevision",
        sa.Column("entity_type", sa.String(), primary_key=True),
        sa.Column("entity_id", sa.Integer(), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
    )
    op.create_table(
        "fieldstate",
        sa.Column("entity_type", sa.String(), primary_key=True),
        sa.Column("entity_id", sa.Integer(), primary_key=True),
        sa.Column("field", sa.String(), primary_key=True),
        sa.Column("protected", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String()),
        sa.Column("observed_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "auditchange",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("field", sa.String(), nullable=False),
        sa.Column("before", sa.JSON()),
        sa.Column("after", sa.JSON()),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("source", sa.String()),
        sa.Column("run_id", sa.String()),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_entity_id", "auditchange", ["entity_type", "entity_id", "id"])
    op.create_table(
        "dataissue",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("field", sa.String()),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("proposed", sa.JSON()),
        sa.Column("occurrences", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_dataissue_key", "dataissue", ["key"], unique=True)
    op.create_index("ix_dataissue_status", "dataissue", ["status"])


def _create_standings():
    op.create_table(
        "standingrule",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scope_key", sa.String(), nullable=False),
        sa.Column("temporada_id", sa.Integer(), sa.ForeignKey("temporada.id"), nullable=False),
        sa.Column("fase_id", sa.Integer(), sa.ForeignKey("fase.id")),
        sa.Column("grupo_id", sa.Integer(), sa.ForeignKey("grupo.id")),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("source_url", sa.String(), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("scope_key", "version", name="uq_standing_rule_version"),
    )
    op.create_index("ix_standingrule_scope_key", "standingrule", ["scope_key"])
    op.create_table(
        "standingadjustment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scope_key", sa.String(), nullable=False),
        sa.Column("equipo_id", sa.Integer(), sa.ForeignKey("equipo.id"), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("source_url", sa.String(), nullable=False),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_standingadjustment_scope_key", "standingadjustment", ["scope_key"])
    op.create_table(
        "standingprojection",
        sa.Column("scope_key", sa.String(), primary_key=True),
        sa.Column("rule_id", sa.Integer(), sa.ForeignKey("standingrule.id"), nullable=False),
        sa.Column("input_hash", sa.String(), nullable=False),
        sa.Column("rows", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "officialstandingsnapshot",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scope_key", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("source_url", sa.String(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("rows", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_official_table_latest", "officialstandingsnapshot", ["scope_key", "fetched_at"]
    )


def _preserve_legacy(bind):
    import datetime

    now = datetime.datetime.now(datetime.timezone.utc)
    meta = sa.MetaData()
    meta.reflect(bind)
    states, revisions, issues = (
        meta.tables[name] for name in ("fieldstate", "entityrevision", "dataissue")
    )
    # Unknown provenance is protected. No participants are guessed from today's membership.
    for kind, table_name in (
        ("confederation", "confederacion"),
        ("competition", "competicion"),
        ("team", "equipo"),
        ("match", "partido"),
        ("season", "temporada"),
        ("stage", "fase"),
        ("venue", "estadio"),
        ("player", "jugador"),
        ("event", "eventopartido"),
        ("lineup", "alineacionpartido"),
        ("statistics", "estadisticaspartido"),
    ):
        table = meta.tables[table_name]
        for row in bind.execute(sa.select(table)).mappings():
            if kind in {"event", "lineup", "statistics"} and row["source"]:
                continue
            bind.execute(
                revisions.insert().values(entity_type=kind, entity_id=row["id"], version=0)
            )
            values = [
                dict(
                    entity_type=kind,
                    entity_id=row["id"],
                    field=field,
                    protected=True,
                    source="legacy:unverified",
                    observed_at=now,
                )
                for field, value in row.items()
                if field != "id" and value is not None and not (field == "logo" and value == "")
            ]
            if values:
                bind.execute(states.insert(), values)
    mappings, seasons = meta.tables["providermapping"], meta.tables["temporada"]
    query = (
        sa.select(mappings.c.id, mappings.c.provider, mappings.c.local_id, seasons.c.competicion_id)
        .join(seasons, mappings.c.local_id == seasons.c.id)
        .where(mappings.c.entity_type == "season")
    )
    for row in bind.execute(query).mappings():
        leagues = (
            bind.execute(
                sa.select(mappings.c.external_id).where(
                    mappings.c.provider == row["provider"],
                    mappings.c.entity_type == "competition",
                    mappings.c.local_id == row["competicion_id"],
                )
            )
            .scalars()
            .all()
        )
        scope = f"league:{leagues[0]}" if len(leagues) == 1 else f"legacy:season:{row['local_id']}"
        bind.execute(
            mappings.update().where(mappings.c.id == row["id"]).values(external_scope=scope)
        )
        if len(leagues) != 1:
            bind.execute(
                issues.insert().values(
                    key=f"legacy-season:{row['id']}",
                    entity_type="season",
                    entity_id=row["local_id"],
                    field=None,
                    source=row["provider"],
                    reason="La temporada heredada necesita identificar su competición externa.",
                    status="open",
                    proposed=None,
                    occurrences=1,
                    created_at=now,
                    updated_at=now,
                )
            )


def downgrade():
    # Loss of protections/history cannot be a safe automatic rollback.
    raise RuntimeError("Restore a verified pre-migration backup to roll back domain automation.")
