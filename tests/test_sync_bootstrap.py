from sqlmodel import Session, select

from src import database
from src.sync.bootstrap import prepare
from src.sync.models import SyncControl, SyncJob, SyncScope


def test_pilot_preparation_is_idempotent_and_does_not_activate_work(client):
    with Session(database.engine) as session:
        assert len(prepare(session)) == 3
        session.commit()
        scope = session.exec(select(SyncScope).where(SyncScope.kind == "archive")).one()
        scope.name = "Mi archivo revisado"
        scope.selector = {**scope.selector, "team_ids": {"Llaneros FC": 20}}
        session.add(scope)
        session.commit()
        assert prepare(session) == []
        session.commit()
        assert session.get(SyncControl, 1).mode == "paused"
        assert all(row.mode == "paused" for row in session.exec(select(SyncScope)).all())
        assert session.exec(select(SyncJob)).all() == []
        assert session.get(SyncScope, scope.id).name == "Mi archivo revisado"
