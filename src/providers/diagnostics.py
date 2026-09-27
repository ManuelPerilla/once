"""Bounded explicit reads share the worker's quota without activating imports."""

from contextlib import contextmanager

import httpx
from sqlmodel import Session

from src import database
from src.providers.automation import Transport
from src.sync.handlers import JobContext
from src.sync.models import SyncScope
from src.sync.service import PermanentError, SyncEngine, control, reserve_provider_request


@contextmanager
def diagnostic_transport(scope_id, actor):
    def reserve(provider):
        with Session(database.engine) as session:
            control(session, lock=True)
            scope = session.get(SyncScope, scope_id)
            if scope is None:
                raise PermanentError("El perfil de consulta cambió. Vuelve a comprobar la fuente.")
            reserve_provider_request(session, provider, scope)
            session.commit()

    engine = SyncEngine(database.engine)
    context = JobContext(
        "manual-diagnostic",
        scope_id,
        0,
        actor,
        reserve,
        lambda **values: engine.report_quota(scope_id, **values),
    )
    with httpx.Client(
        follow_redirects=False, limits=httpx.Limits(max_connections=2, max_keepalive_connections=2)
    ) as client:
        yield Transport(context, client)
