import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

RecordKind = Literal["imports", "links", "observations", "media"]
EntityKind = Literal[
    "confederation", "competition", "team", "match", "season", "stage", "venue", "player"
]


class ControlRecord(BaseModel):
    id: str
    kind: str
    title: str
    entity_type: str | None = None
    entity_id: int | None = None
    entity_name: str | None = None
    module: str | None = None
    provider: str | None = None
    recorded_at: dt.datetime | None = None
    status: str
    detail: str
    source_url: str | None = None
    metadata: dict = Field(default_factory=dict)


class ControlPage(BaseModel):
    items: list[ControlRecord]
    total: int
    page: int
    page_size: int


class QualityCheck(BaseModel):
    code: str
    label: str
    description: str
    count: int
    severity: Literal["review", "error"]
    module: str


class EntityOption(BaseModel):
    value: str
    label: str


class ControlSummary(BaseModel):
    counts: dict[str, int]
    checks: list[QualityCheck]
    providers: list[str]
    entity_types: list[EntityOption]
    scope_notes: list[str]
    checked_at: dt.datetime
