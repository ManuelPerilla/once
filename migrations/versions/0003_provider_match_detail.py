"""Añade procedencia por fila y snapshots normalizados del proveedor."""

from alembic import op
import sqlalchemy as sa


revision = "0003_provider_match_detail"
down_revision = "0002_football_context"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("estadisticaspartido", sa.Column("source", sa.String(), nullable=True))
    op.add_column("eventopartido", sa.Column("source", sa.String(), nullable=True))
    op.add_column("alineacionpartido", sa.Column("source", sa.String(), nullable=True))

    op.create_table(
        "providersnapshot",
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("local_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "entity_type",
            "local_id",
            "kind",
            name="uq_provider_snapshot_latest",
        ),
    )


def downgrade() -> None:
    op.drop_table("providersnapshot")
    op.drop_column("alineacionpartido", "source")
    op.drop_column("eventopartido", "source")
    op.drop_column("estadisticaspartido", "source")
