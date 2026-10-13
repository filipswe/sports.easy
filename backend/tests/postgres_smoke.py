"""Run explicitly against a migrated, disposable PostgreSQL database, never production."""

from app.db import SessionLocal, engine
from app.models import Fixture, Job, Publication, Recommendation
from app.worker import tick
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

assert engine.dialect.name == "postgresql"
with SessionLocal() as db:
    assert db.scalar(select(func.count()).select_from(Fixture)) == 1380
    for cls, table in [(Publication, "publications"), (Recommendation, "recommendations")]:
        record = db.scalar(select(cls))
        assert record
        try:
            db.execute(
                text(f"UPDATE {table} SET created_at = now() WHERE id = :id"), {"id": record.id}
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
print(
    "PostgreSQL: migrations, persisted seed, immutable SQL trigger, advisory lock and duplicate-job checks passed"
)
