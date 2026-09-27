"""Named administrator accounts and revocable role assignments."""

from datetime import datetime

from sqlalchemy import Column
from sqlmodel import Field, SQLModel

from src.datetime_type import UTCDateTime
from src.models import utcnow


class AdminAccount(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    display_name: str
    role: str = "auditor"
    password_hash: str
    active: bool = True
    token_version: int = 1
    created_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(UTCDateTime(), nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=utcnow, sa_column=Column(UTCDateTime(), nullable=False)
    )
