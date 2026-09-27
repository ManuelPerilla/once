"""Concurrent reservations use real independent connections, including SQLite."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlmodel import SQLModel, create_engine

from src.sync.models import SyncScope
from src.sync.service import QuotaExhausted, SyncEngine, enqueue, set_global_mode


def test_concurrent_requests_cannot_exceed_shared_budget(tmp_path):
    connection = create_engine(
        f"sqlite:///{(tmp_path / 'quota.db').as_posix()}", connect_args={"timeout": 15}
    )
    SQLModel.metadata.create_all(connection)
    engine = SyncEngine(connection)
    with engine.transaction() as session:
        set_global_mode(session, "automatic", "tester")
        scope = SyncScope(
            name="Cuota", provider="test", kind="fixtures", mode="automatic", daily_limit=1
        )
        session.add(scope)
        session.flush()
        enqueue(session, scope)
    context = engine.claim("worker")
    barrier = Barrier(2)

    def reserve():
        barrier.wait(timeout=5)
        try:
            context.reserve_request()
            return "reserved"
        except QuotaExhausted:
            return "limited"

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            calls = [pool.submit(reserve), pool.submit(reserve)]
            assert sorted(call.result(timeout=20) for call in calls) == ["limited", "reserved"]
    finally:
        connection.dispose()
