"""SSE cursors and slow-consumer recovery keep no SQL session per client."""

import asyncio

from src import database
from src.sync.events import ChangeHub


class Request:
    async def is_disconnected(self):
        return False


def hub(rows):
    channel = ChangeHub(None)
    channel.start = lambda: None
    channel.buffer.extend(rows)
    channel.cursor = rows[-1]["id"] if rows else 0
    channel.ready.set()
    return channel


def test_expired_or_future_cursor_requests_full_refresh():
    async def run(cursor):
        channel = hub([{"id": 50, "topic": "matches", "scope_id": "scope", "changed": 1}])
        stream = channel.stream(Request(), cursor, set())
        assert "retry:" in await anext(stream)
        event = await anext(stream)
        assert "event: reset" in event and "id: 50" in event
        await stream.aclose()
        assert channel.subscribers == 0

    asyncio.run(run(1))
    asyncio.run(run(100))


def test_topics_filter_events_without_losing_the_monotonic_cursor():
    async def run():
        channel = hub(
            [
                {"id": 1, "topic": "catalog", "scope_id": "scope", "changed": 1},
                {"id": 2, "topic": "matches", "scope_id": "scope", "changed": 1},
            ]
        )
        stream = channel.stream(Request(), 0, {"matches"})
        await anext(stream)
        event = await anext(stream)
        assert "id: 2" in event and '"topic":"matches"' in event
        await stream.aclose()

    asyncio.run(run())


def test_fresh_subscription_starts_at_current_state_and_buffer_is_bounded():
    async def run():
        channel = hub([{"id": value, "topic": "matches"} for value in range(1, 601)])
        assert len(channel.buffer) == 500
        stream = channel.stream(Request(), None, set())
        await anext(stream)
        assert "id: 600" in await anext(stream)
        await stream.aclose()

    asyncio.run(run())


def test_empty_outbox_poll_does_not_modify_the_control_record(client):
    from sqlalchemy import event

    statements = []

    def capture(connection, cursor, statement, parameters, context, many):
        statements.append(statement.upper())

    event.listen(database.engine, "before_cursor_execute", capture)
    try:
        assert ChangeHub(database.engine).poll() == []
    finally:
        event.remove(database.engine, "before_cursor_execute", capture)
    assert not any(statement.startswith(("UPDATE", "INSERT", "DELETE")) for statement in statements)
