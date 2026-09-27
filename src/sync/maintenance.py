"""Bounded retention of operational data; canonical data and audit are never pruned."""

import os
from datetime import timedelta

from sqlmodel import Session, select

from src.sync.models import SyncJob, SyncNotification, SyncObservation
from src.sync.service import now


def cleanup(engine, *, limit=500):
    days = max(7, int(os.getenv("SYNC_RETENTION_DAYS", "30")))
    with Session(engine) as session:
        cutoff = now(session) - timedelta(days=days)
        finished = session.exec(
            select(SyncJob)
            .where(
                SyncJob.status.in_(["succeeded", "observed", "cancelled", "failed"]),
                SyncJob.finished_at < cutoff,
            )
            .order_by(SyncJob.finished_at)
            .limit(limit)
        ).all()
        for row in finished:
            session.delete(row)
        session.flush()
        referenced = select(SyncJob.observation_id).where(SyncJob.observation_id.is_not(None))
        observations = session.exec(
            select(SyncObservation)
            .where(SyncObservation.last_seen_at < cutoff, ~SyncObservation.id.in_(referenced))
            .order_by(SyncObservation.last_seen_at)
            .limit(limit)
        ).all()
        for row in observations:
            session.delete(row)
        delivered = session.exec(
            select(SyncNotification)
            .where(SyncNotification.delivered_at < now(session) - timedelta(days=7))
            .order_by(SyncNotification.delivered_at)
            .limit(limit)
        ).all()
        for row in delivered:
            session.delete(row)
        session.commit()
        return {
            "jobs": len(finished),
            "observations": len(observations),
            "notifications": len(delivered),
        }
