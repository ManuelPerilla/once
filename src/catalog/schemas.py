from typing import Literal

from pydantic import BaseModel, Field


class ImportDecision(BaseModel):
    qid: str = Field(pattern=r"^Q[1-9][0-9]*$")
    action: Literal["create", "link", "skip"]
    local_id: int | None = Field(default=None, gt=0)
    expected_status: Literal["new", "review", "linked", "blocked"]


class ApplyCatalog(BaseModel):
    decisions: list[ImportDecision] = Field(min_length=1, max_length=50)
