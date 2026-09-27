"""Cross-connection invariants that require PostgreSQL's real transaction locks."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event

import pytest
from sqlmodel import Session, select

from src import database
from src.sync.handlers import FetchResult
from src.sync.models import SyncControl, SyncHistory, SyncJob, SyncNotification, SyncScope
from src.sync.service import QuotaExhausted, SyncEngine, enqueue, set_global_mode


@pytest.fixture
def postgres(client):
    if database.engine.dialect.name != "postgresql":
        pytest.skip("Requires TEST_DATABASE_URL pointing to disposable PostgreSQL")
    engine = SyncEngine(database.engine)
    with engine.transaction() as session:
        set_global_mode(session, "automatic", "tester")
        scope = SyncScope(
            name="PG concurrency", provider="test", kind="fixtures", mode="automatic", daily_limit=1
        )
        session.add(scope)
        session.flush()
        enqueue(session, scope)
    return engine


def test_postgres_pause_waits_for_already_publishing_batch(postgres):
    context = postgres.claim("worker")
    applying, release, attempting, paused = Event(), Event(), Event(), Event()

    class Handler:
        def apply(self, session, scope, payload, context):
            applying.set()
            assert release.wait(5)
            session.add(SyncHistory(actor="service:test", action="domain_commit", detail={}))
            return {"changed": 1}

    def pause():
        attempting.set()
        with postgres.transaction() as session:
            set_global_mode(session, "paused", "operator")
        paused.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        publication = pool.submit(
            postgres.publish, context, FetchResult({"valid": True}), Handler()
        )
        assert applying.wait(5)
        pausing = pool.submit(pause)
        assert attempting.wait(5)
        try:
            assert not paused.wait(0.1)
        finally:
            release.set()
        publication.result(timeout=5)
        pausing.result(timeout=5)
    with Session(postgres.engine) as session:
        assert (
            session.get(SyncJob, context.job_id).finished_at
            <= session.get(SyncControl, 1).updated_at
        )
        assert session.exec(
            select(SyncHistory).where(SyncHistory.action == "domain_commit")
        ).first()


def test_postgres_concurrent_reservations_share_one_atomic_budget(postgres):
    context, barrier = postgres.claim("worker"), Barrier(2)

    def reserve():
        barrier.wait(timeout=5)
        try:
            context.reserve_request()
            return "reserved"
        except QuotaExhausted:
            return "limited"

    with ThreadPoolExecutor(max_workers=2) as pool:
        tasks = [pool.submit(reserve), pool.submit(reserve)]
        assert sorted(task.result(timeout=5) for task in tasks) == ["limited", "reserved"]


def test_postgres_outbox_delivers_reverse_commit_order_without_losing_cursor(postgres):
    with Session(postgres.engine) as earlier:
        first_started = SyncNotification(topic="catalog")
        earlier.add(first_started)
        earlier.flush()
        with postgres.transaction() as later:
            first_committed = SyncNotification(topic="matches")
            later.add(first_committed)
            committed_id = first_committed.id
        assert postgres.deliver() == 1
        earlier.commit()
        started_id = first_started.id
    assert postgres.deliver() == 1
    with Session(postgres.engine) as session:
        assert session.get(SyncNotification, committed_id).sequence == 1
        assert session.get(SyncNotification, started_id).sequence == 2
