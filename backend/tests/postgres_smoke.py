"""Run explicitly against a migrated, disposable PostgreSQL database, never production."""

from concurrent.futures import ThreadPoolExecutor

from app.chat import reserve_chat
from app.db import SessionLocal, engine, now
from app.models import Fixture, Job, Publication, QuoteObservation, Recommendation
from app.worker import tick
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

assert engine.dialect.name == "postgresql"
with SessionLocal() as db:
    assert db.scalar(select(func.count()).select_from(Fixture)) == 1380
    for cls, table, column in [
        (Publication, "publications", "created_at"),
        (Recommendation, "recommendations", "created_at"),
        (QuoteObservation, "quote_observations", "observed_at"),
    ]:
        record = db.scalar(select(cls))
        assert record
        try:
            db.execute(
                text(f"UPDATE {table} SET {column} = now() WHERE id = :id"), {"id": record.id}
            )
            db.commit()
        except DBAPIError as error:
            assert "append-only" in str(error)
            db.rollback()
        else:
            raise AssertionError(f"Database immutability trigger failed: {table}")
with engine.connect() as first, engine.connect() as second:
    assert first.scalar(text("SELECT pg_try_advisory_lock(719482)"))
    assert not second.scalar(text("SELECT pg_try_advisory_lock(719482)"))
    first.execute(text("SELECT pg_advisory_unlock(719482)"))
tick()
with SessionLocal() as db:
    count = db.scalar(select(func.count()).select_from(Job))
tick()
with SessionLocal() as db:
    assert db.scalar(select(func.count()).select_from(Job)) == count
at = now()


def concurrent_reservation(actor):
    with SessionLocal() as db:
        return reserve_chat(db, str(actor), at)


with ThreadPoolExecutor(max_workers=6) as pool:
    assert sum(pool.map(concurrent_reservation, range(6))) == 1
print(
    "PostgreSQL: migrations, persisted seed, immutable SQL triggers, advisory lock, duplicate-job and concurrent chat quota checks passed"
)
