"""Official picks are frozen before kickoff, never reconstructed after the result."""

from datetime import timedelta

from sqlalchemy import select

from .config import settings
from .db import now, utc
from .models import Fixture, Recommendation, Settlement
from .research import all_rows


def publish_recommendations(db):
    at = now()
    recorded = list(db.scalars(select(Recommendation)))
    # Maintain a five-match shortlist. Fill vacancies only; never silently switch an official pick.
    active = [
        r
        for r in recorded
        if (f := db.get(Fixture, r.fixture_id)).mode == settings.app_data_mode
        and f.status == "scheduled"
        and utc(f.kickoff) > at
    ]
    available = 5 - len(active)
    if available <= 0:
        return
    seen = {r.fixture_id for r in recorded}
    from .matchday import current_quotes

    rows = current_quotes(db)
    latest = {}
    for row in rows:
        latest.setdefault(
            (row["fixture_id"], row["market"], row["outcome"], row["bookmaker_id"]), row
        )
    rows = [
        r
        for r in latest.values()
        if r["region"] == settings.odds_region
        and r["kickoff"] < at + timedelta(days=7)
        and (r["mode"] == "demo" or not r["stale"])
    ]
    for row in sorted(rows, key=lambda r: (-r["probability"], -r["odds"], r["kickoff"], r["id"])):
        if row["fixture_id"] in seen:
            continue
        seen.add(row["fixture_id"])
        db.add(Recommendation(fixture_id=row["fixture_id"], publication_id=row["id"]))
        available -= 1
        if not available:
            break
    db.flush()


def recommendation_rows(db, upcoming=False):
    publications = {r["id"]: r for r in all_rows(db, archive=True)}
    items = []
    for rec in db.scalars(select(Recommendation).order_by(Recommendation.created_at.desc())):
        row = publications.get(rec.publication_id)
        if not row:
            continue
        if upcoming and (
            row["status"] != "scheduled"
            or row["current_kickoff"] <= now()
            or row["current_kickoff"] != row["kickoff"]
        ):
            continue
        settlement = db.scalar(
            select(Settlement)
            .where(Settlement.publication_id == rec.publication_id)
            .order_by(Settlement.recorded_at.desc())
        )
        items.append(
            {
                **row,
                "recommended_at": utc(rec.created_at),
                "recommendation_id": rec.id,
                "result": settlement.result if settlement else "pending",
                "corrected": bool(settlement and settlement.supersedes_id),
            }
        )
    return sorted(items, key=lambda r: -r["probability"])[:5] if upcoming else items
