"""Durable synchronization controls, quota, jobs and committed notifications."""

import sqlalchemy as sa
from alembic import op

revision = "0006_sync_engine"
down_revision = "0005_domain_automation"
branch_labels = None
depends_on = None


def upgrade():
    # Freeze this revision's schema: future model changes must use a new migration.
    def stamp(name, nullable=False):
        return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)

    op.create_table(
        "synccontrol",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("epoch", sa.Integer(), nullable=False),
        sa.Column("delivery_cursor", sa.Integer(), nullable=False),
        stamp("updated_at"),
    )
    op.execute(
        sa.text(
            "INSERT INTO synccontrol (id,mode,epoch,delivery_cursor,updated_at) VALUES (1,'paused',0,0,CURRENT_TIMESTAMP)"
        )
    )
    op.create_table(
        "syncscope",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("selector", sa.JSON(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("epoch", sa.Integer(), nullable=False),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("daily_limit", sa.Integer(), nullable=False),
        sa.Column("minute_limit", sa.Integer(), nullable=False),
        stamp("next_run_at"),
        stamp("last_checked_at", True),
        stamp("last_changed_at", True),
        stamp("created_at"),
        stamp("updated_at"),
    )
    op.create_index("ix_syncscope_provider", "syncscope", ["provider"])
    op.create_index("ix_syncscope_due", "syncscope", ["mode", "next_run_at"])
    op.create_table(
        "syncjob",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("scope_id", sa.String(), sa.ForeignKey("syncscope.id"), nullable=False),
        sa.Column("active_key", sa.String(), unique=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("global_epoch", sa.Integer(), nullable=False),
        sa.Column("scope_epoch", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("token", sa.Integer(), nullable=False),
        sa.Column("owner", sa.String()),
        stamp("lease_until", True),
        stamp("due_at"),
        stamp("created_at"),
        stamp("started_at", True),
        stamp("finished_at", True),
        sa.Column("error", sa.String()),
        sa.Column("result", sa.JSON()),
        sa.Column("observation_id", sa.String()),
    )
    op.create_index("ix_syncjob_scope_id", "syncjob", ["scope_id"])
    op.create_index("ix_syncjob_due", "syncjob", ["status", "due_at"])
    op.create_table(
        "syncbudget",
        sa.Column("provider", sa.String(), primary_key=True),
        sa.Column("day", sa.String(), nullable=False),
        sa.Column("minute", sa.String(), nullable=False),
        sa.Column("day_used", sa.Integer(), nullable=False),
        sa.Column("minute_used", sa.Integer(), nullable=False),
        sa.Column("day_limit", sa.Integer(), nullable=False),
        sa.Column("minute_limit", sa.Integer(), nullable=False),
        stamp("blocked_until", True),
    )
    op.create_table(
        "syncobservation",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("scope_id", sa.String(), sa.ForeignKey("syncscope.id"), nullable=False),
        sa.Column("digest", sa.String(), nullable=False),
        stamp("received_at"),
        stamp("last_seen_at"),
        sa.Column("complete", sa.Boolean(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.UniqueConstraint("scope_id", "digest", name="uq_syncobservation_content"),
    )
    op.create_index("ix_syncobservation_scope_id", "syncobservation", ["scope_id"])
    op.create_table(
        "syncissue",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("scope_id", sa.String(), sa.ForeignKey("syncscope.id"), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("occurrences", sa.Integer(), nullable=False),
        stamp("first_seen_at"),
        stamp("last_seen_at"),
        stamp("resolved_at", True),
        sa.Column("resolution", sa.String()),
        sa.UniqueConstraint("scope_id", "code", name="uq_syncissue_cause"),
    )
    op.create_index("ix_syncissue_scope_id", "syncissue", ["scope_id"])
    op.create_table(
        "synchistory",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("scope_id", sa.String()),
        sa.Column("job_id", sa.String()),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        stamp("created_at"),
    )
    op.create_index("ix_synchistory_scope_id", "synchistory", ["scope_id"])
    op.create_index("ix_synchistory_created", "synchistory", ["created_at"])
    op.create_table(
        "syncnotification",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("sequence", sa.Integer(), unique=True),
        sa.Column("topic", sa.String(), nullable=False),
        sa.Column("scope_id", sa.String()),
        sa.Column("payload", sa.JSON(), nullable=False),
        stamp("created_at"),
        stamp("delivered_at", True),
    )
    op.create_index("ix_syncnotification_pending", "syncnotification", ["sequence", "created_at"])
    op.create_table(
        "syncheartbeat",
        sa.Column("id", sa.String(), primary_key=True),
        stamp("last_seen_at"),
        sa.Column("owner", sa.String(), nullable=False),
    )


def downgrade():
    for name in (
        "syncheartbeat",
        "syncnotification",
        "synchistory",
        "syncissue",
        "syncobservation",
        "syncbudget",
        "syncjob",
        "syncscope",
        "synccontrol",
    ):
        op.drop_table(name)
