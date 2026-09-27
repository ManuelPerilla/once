"""One bounded publisher per API process, never a SQL connection per browser."""

import asyncio
import json
import time
from collections import deque

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from src import database

from .models import SyncNotification
from .service import SyncEngine

router = APIRouter(tags=["Cambios públicos"])
ALLOWED_TOPICS = {"catalog", "matches", "standings", "media", "history"}


class ChangeHub:
    def __init__(self, engine):
        self.engine = engine
        self.buffer = deque(maxlen=500)
        self.cursor = 0
        self.subscribers = 0
        self.task = None
        self.condition = asyncio.Condition()
        self.ready = asyncio.Event()
        self.idle_at = None

    def poll(self):
        SyncEngine(self.engine).deliver()
        with Session(self.engine) as session:
            statement = select(SyncNotification).where(SyncNotification.sequence.is_not(None))
            if self.cursor:
                rows = session.exec(
                    statement.where(SyncNotification.sequence > self.cursor)
                    .order_by(SyncNotification.sequence)
                    .limit(500)
                ).all()
            else:
                rows = list(
                    reversed(
                        session.exec(
                            statement.order_by(SyncNotification.sequence.desc()).limit(500)
                        ).all()
                    )
                )
            return [
                {
                    "id": row.sequence,
                    "topic": row.topic,
                    "scope_id": row.scope_id,
                    "changed": row.payload.get("changed", 0),
                }
                for row in rows
            ]

    async def run(self):
        try:
            while True:
                try:
                    rows = await asyncio.to_thread(self.poll)
                    async with self.condition:
                        advanced = False
                        for row in rows:
                            if row["id"] > self.cursor:
                                self.buffer.append(row)
                                self.cursor = row["id"]
                                advanced = True
                        self.ready.set()
                        if advanced:
                            self.condition.notify_all()
                except Exception:
                    # A database outage doesn't produce a hot reconnect loop.
                    await asyncio.sleep(3)
                if self.subscribers == 0:
                    self.idle_at = self.idle_at or time.monotonic()
                    if time.monotonic() - self.idle_at > 30:
                        return
                else:
                    self.idle_at = None
                await asyncio.sleep(1)
        finally:
            self.task = None

    def start(self):
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self.run())

    async def stream(self, request, cursor, topics):
        self.subscribers += 1
        self.start()
        try:
            try:
                await asyncio.wait_for(self.ready.wait(), timeout=10)
            except asyncio.TimeoutError:
                yield 'retry: 5000\nevent: reset\ndata: {"reason":"temporarily_unavailable"}\n\n'
                return
            yield "retry: 3000\n\n"
            if cursor is None:
                cursor = self.cursor
                yield f"id: {cursor}\nevent: ready\ndata: {{}}\n\n"
            heartbeat_due = time.monotonic() + 15
            while not await request.is_disconnected():
                first = self.buffer[0]["id"] if self.buffer else self.cursor
                if cursor > self.cursor or cursor < first - 1:
                    cursor = self.cursor
                    yield f'id: {cursor}\nevent: reset\ndata: {{"reason":"refresh_required"}}\n\n'
                for row in tuple(self.buffer):
                    if row["id"] <= cursor:
                        continue
                    cursor = row["id"]
                    if not topics or row["topic"] in topics:
                        yield f"id: {cursor}\nevent: change\ndata: {json.dumps(row, separators=(',', ':'))}\n\n"
                try:
                    async with self.condition:
                        await asyncio.wait_for(
                            self.condition.wait(),
                            timeout=max(0.01, heartbeat_due - time.monotonic()),
                        )
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
                    heartbeat_due = time.monotonic() + 15
        finally:
            self.subscribers -= 1


@router.get("/public/changes")
async def changes(request: Request, topics: str = "", after: int | None = None):
    chosen = set(filter(None, topics.split(",")))
    if chosen - ALLOWED_TOPICS:
        raise HTTPException(422, "Tipo de actualización desconocido.")
    header = request.headers.get("last-event-id")
    try:
        cursor = int(header) if header else after
        if cursor is not None and cursor < 0:
            raise ValueError
    except ValueError as exc:
        raise HTTPException(422, "Cursor de actualización inválido.") from exc
    hub = getattr(request.app.state, "change_hub", None)
    if hub is None or hub.engine is not database.engine:
        hub = request.app.state.change_hub = ChangeHub(database.engine)
    if hub.subscribers >= 64:
        raise HTTPException(
            503,
            "Se alcanzó el límite de conexiones de actualización.",
            headers={"Retry-After": "15"},
        )
    return StreamingResponse(
        hub.stream(request, cursor, chosen),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
