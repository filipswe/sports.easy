"""Chronological matchday shortlist, retaining every original official recommendation."""

from datetime import timedelta

from sqlalchemy import select

from .config import settings
from .db import now, utc
from .leagues import BY_ID
from .models import Competition, Recommendation, Settlement
from .research import all_rows, recorded_price_usable

POLICY = "top-five-leagues-24h-v3"


def eligible_rows(db, fresh_only=False):
    from .matchday import current_quotes

    competitions = {
        c.id
        for c in db.scalars(select(Competition))
        if c.mode == settings.app_data_mode
        and c.provider_id.split(":")[1] in {str(i) for i in BY_ID}
    }
    return [
        r
        for r in current_quotes(db)
        if r["competition_id"] in competitions
        and (not fresh_only or r["mode"] == "demo" or not r["stale"])
    ]


def featured_window(db, fresh_only=False):
    rows = eligible_rows(db, fresh_only=fresh_only)
    if not rows:
        return [], None, None
    start = min(r["kickoff"] for r in rows)
    end = start + timedelta(hours=24)
    return [r for r in rows if start <= r["kickoff"] < end], start, end


def publish_recommendations(db):
    # Daily free feeds use actual snapshots fetched within 24h, explicitly labelled
    # outdated when applicable. Faster feeds still require fresh source timestamps.
    rows, start, end = featured_window(db)
    rows = [row for row in rows if recorded_price_usable(row)]
    if not rows:
        return
    recorded = {r.fixture_id for r in db.scalars(select(Recommendation))}
    seen, selected = set(), 0
    for row in sorted(rows, key=lambda r: (-r["probability"], -r["odds"], r["kickoff"], r["id"])):
        if row["fixture_id"] in seen:
            continue
        seen.add(row["fixture_id"])
        if row["fixture_id"] not in recorded:
            db.add(
                Recommendation(
                    fixture_id=row["fixture_id"], publication_id=row["id"], policy=POLICY
                )
            )
        selected += 1
        if selected == 5:
            break
    db.flush()


def recommendation_rows(db, upcoming=False):
    publications = {r["id"]: r for r in all_rows(db, archive=True)}
    window_rows, start, end = featured_window(db) if upcoming else ([], None, None)
    eligible_fixtures = {r["fixture_id"] for r in window_rows}
    items = []
    for rec in db.scalars(select(Recommendation).order_by(Recommendation.created_at.desc())):
        row = publications.get(rec.publication_id)
        if not row:
            continue
        if upcoming and (
            row["fixture_id"] not in eligible_fixtures
            or row["status"] != "scheduled"
            or row["current_kickoff"] <= now()
            or row["current_kickoff"] != row["kickoff"]
            or not start <= row["kickoff"] < end
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
    if upcoming:
        # New source coverage can introduce stronger picks. Earlier official picks
        # remain immutable in Performance instead of occupying the shortlist forever.
        strongest = sorted(
            items, key=lambda r: (-r["probability"], -r["odds"], r["kickoff"], r["id"])
        )[:5]
        return sorted(strongest, key=lambda r: (r["kickoff"], r["id"]))
    return items
