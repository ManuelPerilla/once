"""Adapters fetch outside transactions and apply inside the publication fence."""

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Protocol

from sqlmodel import Session

from .models import SyncScope


@dataclass
class FetchResult:
    payload: dict
    complete: bool = True


@dataclass
class JobContext:
    job_id: str
    scope_id: str
    token: int
    owner: str
    # Call immediately before EACH actual HTTP request, including retries.
    reserve_request: Callable[[str | None], None]
    # Feed observed quota and Retry-After back into the shared budget.
    report_quota: Callable[..., None]
    actor: str = "service:sync"
    observed_at: datetime | None = None


class Handler(Protocol):
    def fetch(self, scope: SyncScope, context: JobContext) -> FetchResult: ...

    def apply(self, session: Session, scope: SyncScope, payload: dict, context: JobContext) -> dict:
        """No network or commit here. Return changed count and optional public topics."""
        ...


REGISTRY: dict[tuple[str, str], Handler] = {}


def register(provider: str, kind: str, handler: Handler):
    REGISTRY[(provider, kind)] = handler


def register_default_handlers():
    from src.providers.automation import register_handlers

    register_handlers(REGISTRY)
