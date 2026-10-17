"""One small worker, PostgreSQL advisory lock + unique scheduling buckets."""

import fcntl
import json
import os
import time

from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError

from .club_metadata import backfill_crests
from .config import settings
from .db import SessionLocal, engine, now, utc
from .european_results import refresh_european_results
from .ingestion import ingest, settle
from .model import VERSION
from .models import AuthSession, AuthToken, IngestionRun, Job, UsageCounter
from .picks import publish_recommendations
from .providers import ProviderUnavailable


def tick():
    descriptor = None
    if (
        engine.dialect.name != "postgresql"
        and engine.url.database
        and engine.url.database != ":memory:"
    ):
        descriptor = os.open(engine.url.database + ".provider.lock", os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(descriptor)
            return {"status": "busy"}
    try:
        # Dedicated connection holds a session-level lock through all ingestion commits.
        with engine.connect() as lock:
            postgres = engine.dialect.name == "postgresql"
            if postgres:
                lock = lock.execution_options(isolation_level="AUTOCOMMIT")
            if postgres and not lock.scalar(text("SELECT pg_try_advisory_lock(719482)")):
                return {"status": "busy"}
            try:
                with SessionLocal() as db:
                    db.execute(delete(AuthToken).where(AuthToken.expires_at < now()))
                    db.execute(delete(AuthSession).where(AuthSession.expires_at < now()))
                    db.execute(delete(UsageCounter).where(UsageCounter.expires_at < now()))
                    db.commit()
                    slot = int(now().timestamp()) // max(60, settings.poll_seconds)
                    job = Job(
                        key=f"{settings.app_data_mode}:{settings.football_provider}:{VERSION}:top5-24h-v2:{slot}",
                        status="running",
                    )
                    db.add(job)
                    try:
                        db.commit()
                    except IntegrityError:
                        db.rollback()
                        # Refresh the near-term shortlist every tick without another provider request.
                        refresh_european_results(db)
                        settle(db)
                        backfill_crests(db)
                        publish_recommendations(db)
                        db.commit()
                        return {"status": "cached"}
                    # A previous running job after obtaining the exclusive lock was interrupted.
                    for old in db.scalars(
                        select(Job).where(Job.status == "running", Job.id != job.id)
                    ):
                        old.status, old.detail = (
                            "failed",
                            {"message": "Worker interrupted; recovered on next scheduled run"},
                        )
                    db.commit()
                    try:
                        latest = db.scalar(
                            select(IngestionRun)
                            .where(
                                IngestionRun.provider == "live", IngestionRun.status == "complete"
                            )
                            .order_by(IngestionRun.created_at.desc())
                        )
                        if (
                            settings.app_data_mode == "live"
                            and latest
                            and (now() - utc(latest.created_at)).total_seconds()
                            < settings.poll_seconds
                        ):
                            job.detail = {"status": "cached"}
                        else:
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
                    refresh_european_results(db)
                    settle(db)
                    backfill_crests(db)
                    publish_recommendations(db)
                    db.commit()
                    print(
                        json.dumps({"event": "ingestion", "job": job.id, "status": job.status}),
                        flush=True,
                    )
                    return {"status": job.status, "job_id": job.id}
            finally:
                if postgres:
                    lock.execute(text("SELECT pg_advisory_unlock(719482)"))

    finally:
        if descriptor is not None:
            os.close(descriptor)


if __name__ == "__main__":
    while True:
        tick()
        time.sleep(30)
