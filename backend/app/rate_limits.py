"""Shared fixed-window limits for public API instances; no raw IPs are stored."""

import hashlib
import hmac
from datetime import timedelta

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .config import settings
from .models import UsageCounter


def reserve_request(db, actor, category, at, limit):
    digest = hmac.new(settings.session_secret.encode(), actor.encode(), hashlib.sha256).hexdigest()[
        :32
    ]
    window = int(at.timestamp()) // 60
    key = f"request:{category}:{digest}:{window}"
    insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
    statement = insert(UsageCounter).values(key=key, count=1, expires_at=at + timedelta(minutes=2))
    statement = statement.on_conflict_do_update(
        index_elements=[UsageCounter.key],
        set_={"count": UsageCounter.count + 1},
        where=UsageCounter.count < limit,
    ).returning(UsageCounter.count)
    count = db.scalar(statement) if limit > 0 else None
    if count is None:
        db.rollback()
        return False
    if count == 1:
        db.execute(delete(UsageCounter).where(UsageCounter.expires_at < at))
    db.commit()
    return True
