"""Bounded additional bookmaker markets, fetched only on requested match views."""

import threading
from contextlib import contextmanager
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, text

from .config import settings
from .db import get_db, now, utc
from .ingestion import store_odds
from .leagues import BY_ID
from .matchday import matchday
from .models import Competition, IngestionRun, Job, ProviderMapping
from .providers import ProviderClient, ProviderUnavailable, TheOddsAPI, fingerprint
from .research import require_fixture

router = APIRouter(prefix="/api/prices", tags=["prices"])
local_lock = threading.Lock()
DETAIL_MARKETS = "alternate_totals,btts,double_chance,alternate_totals_h1"


@contextmanager
def provider_lock(db):
    if db.bind.dialect.name == "postgresql":
        with db.bind.connect() as connection:
            acquired = connection.scalar(text("SELECT pg_try_advisory_lock(719482)"))
            try:
                yield acquired
            finally:
                if acquired:
                    connection.execute(text("SELECT pg_advisory_unlock(719482)"))
    else:
        acquired = local_lock.acquire(blocking=False)
        try:
            yield acquired
        finally:
            if acquired:
                local_lock.release()


class RefreshInput(BaseModel):
    fixture_id: str | None = Field(None, min_length=1, max_length=36)
    period: Literal["today", "tomorrow", "week", "fortnight"] = "week"
    league: str = Field("", max_length=36)
    team: str = Field("", max_length=80)
    more: bool = False


def detail_key(fixture):
    return "odds-detail:" + fingerprint(
        [fixture.id, utc(fixture.kickoff), settings.odds_region, settings.odds_bookmaker_key]
    )


def detail_cached(db, fixture, at):
    job = db.scalar(select(Job).where(Job.key == detail_key(fixture)))
    return bool(
        job
        and job.status == "complete"
        and job.finished_at
        and 0
        <= (at - utc(job.finished_at)).total_seconds()
        < min(settings.odds_poll_seconds, 259200)
    )


def discover_events(db, fixtures):
    groups = {}
    for fixture in fixtures:
        if fixture.provider_id.startswith("the-odds-api:"):
            continue
        mapping = db.scalar(
            select(ProviderMapping).where(
                ProviderMapping.provider == "the-odds-api",
                ProviderMapping.entity_type == "fixture",
                ProviderMapping.entity_id == fixture.id,
            )
        )
        if mapping is None:
            competition = db.get(Competition, fixture.competition_id)
            league = BY_ID.get(int(competition.provider_id.split(":")[1]))
            if league:
                groups[league.id] = league
    client = ProviderClient(db, "the-odds-api-events", settings.odds_event_daily_budget)
    for league in groups.values():
        data = client.get(
            f"https://api.the-odds-api.com/v4/sports/{league.sport}/events",
            {"apiKey": settings.odds_api_key, "dateFormat": "iso"},
        )
        if not isinstance(data, list):
            raise ProviderUnavailable("Invalid event discovery response")
        store_odds(db, data)
        db.commit()


@router.post("/refresh")
def refresh(body: RefreshInput, db=Depends(get_db)):
    if settings.app_data_mode != "live":
        return {"status": "sample", "fetched_matches": 0}
    if not settings.live_retention_approved:
        raise HTTPException(409, "Live prices have not been enabled for this installation.")
    if body.fixture_id:
        fixture = require_fixture(db, body.fixture_id)
        if fixture.status != "scheduled" or not now() < utc(fixture.kickoff) <= now() + timedelta(
            days=14
        ):
            raise HTTPException(409, "Choose an upcoming match within the next fourteen days.")
        fixtures = [fixture]
    else:
        rows = matchday(
            team=body.team,
            period=body.period,
            league=body.league,
            summary=True,
            market="all",
            db=db,
        )["items"]
        fixtures = [require_fixture(db, row["id"]) for row in rows]
        fixtures = (
            [f for f in fixtures if not detail_cached(db, f, now())][:6]
            if body.more
            else fixtures[:6]
        )
    fetched, cached = 0, 0
    with provider_lock(db) as acquired:
        if not acquired:
            return {"status": "busy", "fetched_matches": 0}
        try:
            discover_events(db, fixtures)
            adapter = TheOddsAPI(db)
            for fixture in fixtures:
                if detail_cached(db, fixture, now()):
                    cached += 1
                    continue
                competition = db.get(Competition, fixture.competition_id)
                league = BY_ID.get(int(competition.provider_id.split(":")[1]))
                mapping = db.scalar(
                    select(ProviderMapping).where(
                        ProviderMapping.provider == "the-odds-api",
                        ProviderMapping.entity_type == "fixture",
                        ProviderMapping.entity_id == fixture.id,
                    )
                )
                event_id = (
                    fixture.provider_id.split(":", 1)[1]
                    if fixture.provider_id.startswith("the-odds-api:")
                    else mapping.external_id
                    if mapping
                    else None
                )
                if not league or not event_id:
                    continue
                data = adapter.client.get(
                    f"https://api.the-odds-api.com/v4/sports/{league.sport}/events/{event_id}/odds",
                    {
                        "apiKey": settings.odds_api_key,
                        "regions": settings.odds_region,
                        "bookmakers": settings.odds_bookmaker_key,
                        "markets": DETAIL_MARKETS,
                        "oddsFormat": "decimal",
                        "dateFormat": "iso",
                    },
                    cost=4,
                )
                if (
                    not isinstance(data, dict)
                    or data.get("id") != event_id
                    or data.get("sport_key") != league.sport
                ):
                    raise ProviderUnavailable("Bookmaker returned a different match")
                observed = now()
                rejected = store_odds(db, [data], fetched=observed, observed=True)
                if rejected:
                    raise ProviderUnavailable("Bookmaker match identity changed")
                job = db.scalar(select(Job).where(Job.key == detail_key(fixture)))
                if job is None:
                    job = Job(key=detail_key(fixture))
                    db.add(job)
                job.status, job.finished_at, job.detail = (
                    "complete",
                    observed,
                    {"fixture_id": fixture.id},
                )
                db.add(
                    IngestionRun(
                        provider="odds-detail-refresh",
                        status="complete",
                        created_at=observed,
                        detail={
                            "fixture_id": fixture.id,
                            "bookmaker": settings.odds_bookmaker_key,
                            "region": settings.odds_region,
                        },
                    )
                )
                db.commit()
                fetched += 1
        except ProviderUnavailable:
            db.rollback()
            return {"status": "limited", "fetched_matches": fetched, "cached_matches": cached}
    return {"status": "ready", "fetched_matches": fetched, "cached_matches": cached}
