"""Persistent controls and execution records; domain entities live elsewhere."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Column, Index, UniqueConstraint
from sqlmodel import Field, SQLModel

from src.datetime_type import UTCDateTime


def utcnow():
    return datetime.now(timezone.utc)


def identity():
    return str(uuid4())


def instant(*, nullable=False):
    return Column(UTCDateTime(), nullable=nullable)


class SyncControl(SQLModel, table=True):
    id: int = Field(default=1, primary_key=True)
    mode: str = "paused"
    epoch: int = 0
    delivery_cursor: int = 0
    updated_at: datetime = Field(default_factory=utcnow, sa_column=instant())


class SyncScope(SQLModel, table=True):
    id: str = Field(default_factory=identity, primary_key=True)
    name: str
    provider: str = Field(index=True)
    kind: str
    selector: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    mode: str = "paused"
    epoch: int = 0
    interval_seconds: int = 86400
    daily_limit: int = 100
    minute_limit: int = 10
    next_run_at: datetime = Field(default_factory=utcnow, sa_column=instant())
    last_checked_at: datetime | None = Field(default=None, sa_column=instant(nullable=True))
    last_changed_at: datetime | None = Field(default=None, sa_column=instant(nullable=True))
    created_at: datetime = Field(default_factory=utcnow, sa_column=instant())
    updated_at: datetime = Field(default_factory=utcnow, sa_column=instant())
    __table_args__ = (Index("ix_syncscope_due", "mode", "next_run_at"),)


class SyncJob(SQLModel, table=True):
    id: str = Field(default_factory=identity, primary_key=True)
    scope_id: str = Field(foreign_key="syncscope.id", index=True)
    # Released on completion; a unique key coalesces all pending polls per scope.
    active_key: str | None = Field(default=None, unique=True)
    status: str = "queued"
    global_epoch: int = 0
    scope_epoch: int = 0
    mode: str = "observe"
    attempts: int = 0
    max_attempts: int = 4
    token: int = 0
    owner: str | None = None
    lease_until: datetime | None = Field(default=None, sa_column=instant(nullable=True))
    due_at: datetime = Field(default_factory=utcnow, sa_column=instant())
    created_at: datetime = Field(default_factory=utcnow, sa_column=instant())
    started_at: datetime | None = Field(default=None, sa_column=instant(nullable=True))
    finished_at: datetime | None = Field(default=None, sa_column=instant(nullable=True))
    error: str | None = None
    result: dict | None = Field(default=None, sa_column=Column(JSON))
    observation_id: str | None = None
    __table_args__ = (Index("ix_syncjob_due", "status", "due_at"),)


class SyncBudget(SQLModel, table=True):
    provider: str = Field(primary_key=True)
    day: str = ""
    minute: str = ""
    day_used: int = 0
    minute_used: int = 0
    day_limit: int = 100
    minute_limit: int = 10
    blocked_until: datetime | None = Field(default=None, sa_column=instant(nullable=True))


class SyncObservation(SQLModel, table=True):
    id: str = Field(default_factory=identity, primary_key=True)
    scope_id: str = Field(foreign_key="syncscope.id", index=True)
    digest: str
    received_at: datetime = Field(default_factory=utcnow, sa_column=instant())
    last_seen_at: datetime = Field(default_factory=utcnow, sa_column=instant())
    complete: bool = True
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    __table_args__ = (UniqueConstraint("scope_id", "digest", name="uq_syncobservation_content"),)


class SyncIssue(SQLModel, table=True):
    id: str = Field(default_factory=identity, primary_key=True)
    scope_id: str = Field(foreign_key="syncscope.id", index=True)
    code: str
    message: str
    severity: str = "warning"
    status: str = "open"
    occurrences: int = 1
    first_seen_at: datetime = Field(default_factory=utcnow, sa_column=instant())
    last_seen_at: datetime = Field(default_factory=utcnow, sa_column=instant())
    resolved_at: datetime | None = Field(default=None, sa_column=instant(nullable=True))
    resolution: str | None = None
    __table_args__ = (UniqueConstraint("scope_id", "code", name="uq_syncissue_cause"),)


class SyncHistory(SQLModel, table=True):
    id: str = Field(default_factory=identity, primary_key=True)
    scope_id: str | None = Field(default=None, index=True)
    job_id: str | None = None
    actor: str
    action: str
    detail: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utcnow, sa_column=instant())
    __table_args__ = (Index("ix_synchistory_created", "created_at"),)


class SyncNotification(SQLModel, table=True):
    id: str = Field(default_factory=identity, primary_key=True)
    # Sequence is assigned by a serialized publisher only AFTER domain commit.
    sequence: int | None = Field(default=None, unique=True)
    topic: str
    scope_id: str | None = None
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utcnow, sa_column=instant())
    delivered_at: datetime | None = Field(default=None, sa_column=instant(nullable=True))
    __table_args__ = (Index("ix_syncnotification_pending", "sequence", "created_at"),)


class SyncHeartbeat(SQLModel, table=True):
    id: str = Field(default="worker", primary_key=True)
    last_seen_at: datetime = Field(default_factory=utcnow, sa_column=instant())
    owner: str
