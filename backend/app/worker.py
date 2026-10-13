"""One small worker, PostgreSQL advisory lock + unique scheduling buckets."""

import json
import time

from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError

from .config import settings
from .db import SessionLocal, engine, now
from .ingestion import ingest
from .model import VERSION
from .models import AuthSession, AuthToken, Job
from .providers import ProviderUnavailable


def tick():
    # Dedicated connection holds a session-level lock through all ingestion commits.
    with engine.connect() as lock:
        postgres = engine.dialect.name == "postgresql"
        if postgres and not lock.scalar(text("SELECT pg_try_advisory_lock(719482)")):
            return
        try:
            with SessionLocal() as db:
                db.execute(delete(AuthToken).where(AuthToken.expires_at < now()))
                db.execute(delete(AuthSession).where(AuthSession.expires_at < now()))
                db.commit()
                slot = int(now().timestamp()) // max(60, settings.poll_seconds)
                job = Job(key=f"{settings.app_data_mode}:{VERSION}:{slot}", status="running")
                db.add(job)
                try:
                    db.commit()
                except IntegrityError:
                    db.rollback()
                    return
                # A previous running job after obtaining the exclusive lock was interrupted.
                for old in db.scalars(select(Job).where(Job.status == "running", Job.id != job.id)):
                    old.status, old.detail = (
                        "failed",
                        {"message": "Worker interrupted; recovered on next scheduled run"},
                    )
                db.commit()
                try:
                    job.detail = ingest(db)
                    job.status = "complete"
                except ProviderUnavailable as exc:
                    db.rollback()
                    job.status, job.detail = "unavailable", {"message": str(exc)}
                except Exception:
                    db.rollback()
                    job.status, job.detail = (
                        "failed",
                        {"message": "Ingestion failed; inspect sanitized service logs"},
                    )
                job.finished_at = now()
                db.commit()
                print(
                    json.dumps({"event": "ingestion", "job": job.id, "status": job.status}),
                    flush=True,
                )
        finally:
            if postgres:
                lock.execute(text("SELECT pg_advisory_unlock(719482)"))


if __name__ == "__main__":
    while True:
        tick()
        time.sleep(30)
