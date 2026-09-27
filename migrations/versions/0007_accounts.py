"""Named administrator accounts and token revocation."""

import sqlalchemy as sa
from alembic import op

revision = "0007_accounts"
down_revision = "0006_sync_engine"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "adminaccount",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("token_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_adminaccount_username", "adminaccount", ["username"], unique=True)


def downgrade():
    raise RuntimeError(
        "Restore a verified backup to roll back named accounts without losing access history."
    )
