from datetime import datetime, timedelta
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import aliased

from .config import settings
from .crests import team_logo
from .db import now, utc
from .model import likelihood, value
from .models import (
    Bookmaker,
    Competition,
    Fixture,
    Prediction,
    Publication,
    Quote,
    Team,
)
from .reasons import pick_reason


class Filters(BaseModel):
    min_odds: float = Field(1.01, ge=1.01, le=1000, allow_inf_nan=False)
    max_odds: float = Field(1000, ge=1.01, le=1000, allow_inf_nan=False)
    target: float | None = Field(None, ge=1.01, le=1000, allow_inf_nan=False)
    tolerance: float = Field(0.1, ge=0, le=10, allow_inf_nan=False)
    min_probability: float = Field(0, ge=0, le=1, allow_inf_nan=False)
    market: Literal["all", "1x2", "totals", "btts"] = "all"
    team: str = Field("", max_length=80)
    league: str = Field("", max_length=36)
    bookmaker: str = Field("", max_length=36)
    region: Literal["uk", "eu", "us", "au"] = "uk"
    period: Literal["today", "tomorrow", "week", "custom"] = "week"
    start: datetime | None = None
    end: datetime | None = None
    positive_ev: bool = False
    fresh_only: bool = False
    sort: Literal["kickoff", "probability", "odds", "ev", "freshness"] = "kickoff"
    page: int = Field(1, ge=1, le=10000)
    page_size: int = Field(12, ge=1, le=48)

    @model_validator(mode="after")
    def ranges(self):
        if self.min_odds > self.max_odds:
            raise ValueError("Minimum odds must not exceed maximum odds")
        if self.period == "custom" and (not self.start or not self.end):
            raise ValueError("Both custom dates are required")
        if bool(self.start) != bool(self.end):
            raise ValueError("Both date bounds are required")
        if any(t and t.tzinfo is None for t in [self.start, self.end]):
            raise ValueError("Dates must include a timezone")
        if (
            self.start
            and self.end
            and (self.end <= self.start or self.end - self.start > timedelta(days=31))
        ):
            raise ValueError("Date range must be positive and at most 31 days")
        return self


def quote_stale(quote, at=None):
    at = at or now()
    return (
        quote.source_updated_at is None
        or (at - utc(quote.source_updated_at)).total_seconds() > settings.quote_max_age_seconds
    )


def recorded_price_usable(row):
    """Daily free feeds can use recorded prices while retaining their outdated label."""
    if row["mode"] == "demo" or not row["stale"]:
        return True
    return (
        settings.odds_poll_seconds >= 86400
        and row["source_updated_at"] is not None
        and 0
        <= (now() - utc(row.get("observed_at", row["fetched_at"]))).total_seconds()
        <= min(settings.odds_poll_seconds, 259200)
    )


def publication_row(db, pub, prediction, quote, fixture, book, home, away, competition):
    p = prediction.probabilities[quote.market][quote.outcome]
    stale = quote_stale(quote)
    return {
        "id": pub.id,
        "fixture_id": fixture.id,
        "prediction_id": prediction.id,
        "quote_id": quote.id,
        "home": home.name,
        "away": away.name,
        "home_logo": team_logo(home),
        "away_logo": team_logo(away),
        "competition": competition.name,
        "competition_id": competition.id,
        "kickoff": utc(prediction.fixture_kickoff),
        "current_kickoff": utc(fixture.kickoff),
        "status": fixture.status,
        "market": quote.market,
        "outcome": quote.outcome,
        "odds": float(quote.price),
        "bookmaker": book.name,
        "bookmaker_id": book.id,
        "region": book.region,
        "probability": p,
        "likelihood": likelihood(p),
        **value(p, float(quote.price)),
        "quality": "Limited"
        if stale
        or prediction.mode == "demo"
        or (now() - utc(prediction.history_fetched_at)).total_seconds() > 86400
        or (now() - utc(fixture.fetched_at)).total_seconds() > 86400
        else prediction.quality,
        "stale": stale,
        "source_updated_at": utc(quote.source_updated_at) if quote.source_updated_at else None,
        "fetched_at": utc(quote.fetched_at),
        "generated_at": utc(prediction.generated_at),
        "input_cutoff": utc(prediction.input_cutoff),
        "model_version": prediction.model_id,
        "mode": prediction.mode,
        "quote_basis": "Best matching recorded quote in selected region",
        "analysis": pick_reason(
            prediction,
            quote.market,
            quote.outcome,
            p,
            home.name,
            away.name,
            prediction.probabilities[quote.market],
        ),
        "reason": pick_reason(
            prediction,
            quote.market,
            quote.outcome,
            p,
            home.name,
            away.name,
            prediction.probabilities[quote.market],
        )["summary"],
    }


def all_rows(
    db, fixture_id=None, archive=False, publication_ids=None, quote_ids=None, unique_quotes=False
):
    if (publication_ids is not None and not publication_ids) or (
        quote_ids is not None and not quote_ids
    ):
        return []
    home_team, away_team = aliased(Team), aliased(Team)
    query = (
        select(
            Publication, Prediction, Quote, Fixture, Bookmaker, home_team, away_team, Competition
        )
        .join(Prediction, Publication.prediction_id == Prediction.id)
        .join(Quote, Publication.quote_id == Quote.id)
        .join(Fixture, Quote.fixture_id == Fixture.id)
        .join(Bookmaker, Quote.bookmaker_id == Bookmaker.id)
        .join(home_team, Fixture.home_id == home_team.id)
        .join(away_team, Fixture.away_id == away_team.id)
        .join(Competition, Fixture.competition_id == Competition.id)
        .where(
            Prediction.mode == settings.app_data_mode,
            Quote.mode == settings.app_data_mode,
            Fixture.mode == settings.app_data_mode,
        )
    )
    if fixture_id:
        query = query.where(Fixture.id == fixture_id)
    if publication_ids is not None:
        query = query.where(Publication.id.in_(publication_ids))
    if quote_ids is not None:
        query = query.where(Quote.id.in_(quote_ids))
    if not archive:
        query = query.where(Fixture.status == "scheduled", Fixture.kickoff > now())
    query = query.order_by(Prediction.generated_at.desc(), Quote.fetched_at.desc())
    rows, seen = [], set()
    for pub, p, q, f, b, home, away, competition in db.execute(query):
        if not archive and utc(p.fixture_kickoff) != utc(f.kickoff):
            continue
        if unique_quotes and q.id in seen:
            continue
        seen.add(q.id)
        rows.append(
            publication_row(
                db,
                pub,
                p,
                q,
                f,
                b,
                home,
                away,
                competition,
            )
        )
    return rows


def search(db, filters):
    at = now()
    start, end = filters.start, filters.end
    if not start:
        day = at.replace(hour=0, minute=0, second=0, microsecond=0)
        start = day + timedelta(days=1) if filters.period == "tomorrow" else at
        end = day + timedelta(
            days=2 if filters.period == "tomorrow" else 1 if filters.period == "today" else 8
        )
    if filters.period == "week" and not filters.start:
        end = at + timedelta(days=7)
    current, seen = [], set()
    for row in all_rows(db):
        key = (row["fixture_id"], row["market"], row["outcome"], row["bookmaker_id"])
        if key in seen:
            continue
        seen.add(key)
        if row["region"] != filters.region or (
            filters.bookmaker and row["bookmaker_id"] != filters.bookmaker
        ):
            continue
        if not start <= row["kickoff"] < end:
            continue
        if filters.league and row["competition_id"] != filters.league:
            continue
        if filters.team.casefold() not in (row["home"] + " " + row["away"]).casefold():
            continue
        if filters.market != "all" and row["market"] != filters.market:
            continue
        if row["probability"] < filters.min_probability:
            continue
        # Current-value rankings cannot use stale quotes, even when stale browsing is enabled.
        if row["stale"] and (filters.fresh_only or filters.positive_ev or filters.sort == "ev"):
            continue
        if not filters.min_odds <= row["odds"] <= filters.max_odds:
            continue
        if (
            filters.target is not None
            and abs(row["odds"] - filters.target) > filters.tolerance + 1e-9
        ):
            continue
        if filters.positive_ev and row["estimated_ev"] <= 0:
            continue
        current.append(row)
    best = {}
    for row in current:
        key = (row["fixture_id"], row["market"], row["outcome"])
        prior = best.get(key)
        if prior is None or (not row["stale"], row["odds"]) > (not prior["stale"], prior["odds"]):
            best[key] = row
    rows = []
    for row in best.values():
        row["quote_basis"] = (
            "Selected bookmaker quote"
            if filters.bookmaker
            else "Best matching recorded quote in selected region"
        )
        rows.append(row)
    keys = {
        "kickoff": lambda r: r["kickoff"],
        "probability": lambda r: -r["probability"],
        "odds": lambda r: -r["odds"],
        "ev": lambda r: -r["estimated_ev"],
        "freshness": lambda r: (
            -(r["source_updated_at"].timestamp() if r["source_updated_at"] else 0)
        ),
    }
    rows.sort(key=lambda r: (keys[filters.sort](r), r["id"]))
    offset = (filters.page - 1) * filters.page_size
    return {
        "items": rows[offset : offset + filters.page_size],
        "total": len(rows),
        "page": filters.page,
        "page_size": filters.page_size,
        "mode": settings.app_data_mode,
        "ranking": filters.sort,
        "freshness_seconds": settings.quote_max_age_seconds,
    }


def require_fixture(db, fixture_id):
    fixture = db.get(Fixture, fixture_id)
    if not fixture or fixture.mode != settings.app_data_mode:
        raise HTTPException(404, "Match not found")
    return fixture
