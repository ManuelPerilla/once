"""Persist reviewed Wikidata import batches and their last result."""
from alembic import op
import sqlalchemy as sa

revision = "0004_catalog_imports"
down_revision = "0003_provider_match_detail"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "catalogimportbatch",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("collection", sa.String(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("last_result", sa.JSON(), nullable=True),
    )
    op.create_index("ix_catalogimportbatch_collection", "catalogimportbatch", ["collection"])


def downgrade():
    op.drop_index("ix_catalogimportbatch_collection", table_name="catalogimportbatch")
    op.drop_table("catalogimportbatch")
