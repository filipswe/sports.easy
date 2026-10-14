"""Match browsing and server-verified parlay research, without invented bookmaker prices."""

import math
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from .config import settings
from .crests import team_logo
from .db import get_db, now, utc
from .leagues import BY_ID, EUROPEAN_COMPETITIONS
from .model import market_probabilities
from .models import (
    Bookmaker,
    Competition,
    Fixture,
    IngestionRun,
    Prediction,
    Quote,
    QuoteObservation,
    Team,
)
from .picks import recommendation_rows
from .reasons import pick_reason
from .research import all_rows, recorded_price_usable, require_fixture

router = APIRouter(prefix="/api", tags=["matchday"])


def logo(team):
    return team_logo(team)


def poisson(rate, n):
    return math.exp(-rate) * rate**n / math.factorial(n)


def under(rate, line):
    return sum(poisson(rate, n) for n in range(math.floor(line) + 1))


def markets(prediction):
    if not prediction:
        return []
    p, factors = prediction.probabilities, prediction.factors
    h, a = factors["home_rate"], factors["away_rate"]
    result = []

    def add(key, name, group, probs):
        result.append({"key": key, "name": name, "group": group, "outcomes": probs})

    add("1x2", "Match result · 1X2", "Popular", p["1x2"])
    add("btts", "Both teams to score", "Popular", p["btts"])
    for line in [n + 0.5 for n in range(10)]:
        u = under(h + a, line)
        add(
            "totals" if line == 2.5 else f"totals_{line}",
            f"Under/over goals · {line}",
            "Goals",
            {"over": 1 - u, "under": u},
        )
    add(
        "double_chance",
        "Double chance",
        "Popular",
        {
            "1x": p["1x2"]["home"] + p["1x2"]["draw"],
            "x2": p["1x2"]["draw"] + p["1x2"]["away"],
            "12": p["1x2"]["home"] + p["1x2"]["away"],
        },
    )
    for side, rate in [("home", h), ("away", a)]:
        for line in [0.5, 1.5, 2.5]:
            u = under(rate, line)
            add(
                f"{side}_goals_{line}",
                f"{side.title()} team goals · {line}",
                "Team goals",
                {"over": 1 - u, "under": u},
            )
    half = factors.get("first_half")
    for line in [0.5, 1.5, 2.5]:
        u = under(half["home_rate"] + half["away_rate"], line) if half else None
        add(
            f"half_totals_{line}",
            f"First-half goals · {line}",
            "First half",
            {"over": 1 - u, "under": u} if u is not None else {},
        )
    scores = {f"{hg}-{ag}": poisson(h, hg) * poisson(a, ag) for hg in range(5) for ag in range(5)}
    scores["other"] = max(0, 1 - sum(scores.values()))
    add("correct_score", "Correct score", "Score", scores)
    return result


def current_quotes(db, fixture_id=None, markets_filter=None):
    seen, result = set(), []
    query = (
        select(Quote, Fixture, Bookmaker, Competition)
        .join(Fixture, Quote.fixture_id == Fixture.id)
        .join(Bookmaker, Quote.bookmaker_id == Bookmaker.id)
        .join(Competition, Fixture.competition_id == Competition.id)
        .where(
            Quote.mode == settings.app_data_mode,
            Fixture.mode == settings.app_data_mode,
            Fixture.status == "scheduled",
            Fixture.kickoff > now(),
            Bookmaker.region == settings.odds_region,
        )
    )
    if fixture_id:
        query = query.where(Fixture.id == fixture_id)
    if markets_filter is not None:
        query = query.where(Quote.market.in_(markets_filter))
    if settings.app_data_mode == "demo":
        query = query.where(Bookmaker.name == "Demo Sportsbook")
    else:
        query = query.where(
            Bookmaker.provider_id == f"live:{settings.odds_region}:{settings.odds_bookmaker_key}"
        )
    records = list(db.execute(query))
    if not records:
        return []
    ids = [q.id for q, _, _, _ in records]
    observations = {}
    for observation in db.scalars(
        select(QuoteObservation)
        .where(QuoteObservation.quote_id.in_(ids))
        .order_by(QuoteObservation.observed_at.desc())
    ):
        observations.setdefault(observation.quote_id, observation)
    published = {row["quote_id"]: row for row in all_rows(db, quote_ids=ids, unique_quotes=True)}
    team_ids = {
        team_id for _, fixture, _, _ in records for team_id in (fixture.home_id, fixture.away_id)
    }
    teams = {team.id: team for team in db.scalars(select(Team).where(Team.id.in_(team_ids)))}
    at = now()
    latest_sweep = db.scalar(
        select(IngestionRun.created_at)
        .where(
            IngestionRun.provider
            == f"odds-refresh:{settings.odds_region}:{settings.odds_bookmaker_key}",
            IngestionRun.status == "complete",
        )
        .order_by(IngestionRun.created_at.desc())
    )
    detail_sweeps = {}
    for run in db.scalars(
        select(IngestionRun)
        .where(IngestionRun.provider == "odds-detail-refresh", IngestionRun.status == "complete")
        .order_by(IngestionRun.created_at.desc())
    ):
        if (
            run.detail.get("bookmaker") == settings.odds_bookmaker_key
            and run.detail.get("region") == settings.odds_region
        ):
            detail_sweeps.setdefault(run.detail.get("fixture_id"), utc(run.created_at))
    records.sort(
        key=lambda record: (
            utc(
                observations[record[0].id].observed_at
                if record[0].id in observations
                else record[0].fetched_at
            ),
            utc(record[0].fetched_at),
            record[0].id,
        ),
        reverse=True,
    )
    for q, f, book, comp in records:
        expected = (
            "demo:" + settings.odds_region + ":demo"
            if settings.app_data_mode == "demo"
            else f"live:{settings.odds_region}:{settings.odds_bookmaker_key}"
        )
        if settings.app_data_mode == "demo":
            if book.name != "Demo Sportsbook":
                continue
        elif book.provider_id != expected:
            continue
        key = (q.fixture_id, q.market, q.outcome)
        if key in seen:
            continue
        seen.add(key)
        observation = observations.get(q.id)
        observed_at = observation.observed_at if observation else q.fetched_at
        if settings.app_data_mode == "live":
            verified_kickoff = (
                observation.fixture_kickoff
                if observation
                else published.get(q.id, {}).get("kickoff")
            )
            if verified_kickoff is None or utc(verified_kickoff) != utc(f.kickoff):
                continue
        if (
            settings.app_data_mode == "live"
            and latest_sweep
            and q.market in {"1x2", "totals"}
            and utc(observed_at) < utc(latest_sweep)
        ):
            continue
        age = (at - utc(observed_at)).total_seconds()
        if (
            settings.app_data_mode == "live"
            and q.market not in {"1x2", "totals"}
            and q.fixture_id in detail_sweeps
            and utc(observed_at) < detail_sweeps[q.fixture_id]
        ):
            continue
        if settings.app_data_mode == "live" and (
            q.source_updated_at is None or not 0 <= age <= min(settings.odds_poll_seconds, 259200)
        ):
            continue
        if comp.provider_id.split(":")[1] in {str(c.id) for c in EUROPEAN_COMPETITIONS} and utc(
            f.kickoff
        ) > at + timedelta(days=14):
            continue
        home, away = teams[f.home_id], teams[f.away_id]
        row = published.get(
            q.id,
            {
                "id": None,
                "quote_id": q.id,
                "fixture_id": f.id,
                "home": home.name,
                "away": away.name,
                "home_logo": logo(home),
                "away_logo": logo(away),
                "competition_id": comp.id,
                "competition": comp.name,
                "kickoff": utc(f.kickoff),
                "market": q.market,
                "outcome": q.outcome,
                "probability": None,
                "odds": float(q.price),
                "bookmaker": book.name,
                "bookmaker_id": book.id,
                "region": book.region,
                "mode": f.mode,
                "stale": True,
                "fetched_at": utc(q.fetched_at),
                "source_updated_at": q.source_updated_at,
            },
        )
        result.append({**row, "observed_at": utc(observed_at)})
    return result


def match_context(db, fixtures):
    ids = [fixture.id for fixture in fixtures]
    team_ids = {team_id for fixture in fixtures for team_id in (fixture.home_id, fixture.away_id)}
    predictions = {}
    for prediction in db.scalars(
        select(Prediction)
        .where(Prediction.fixture_id.in_(ids), Prediction.mode == settings.app_data_mode)
        .order_by(Prediction.generated_at.desc())
    ):
        predictions.setdefault(prediction.fixture_id, prediction)
    return {
        "predictions": predictions,
        "teams": {team.id: team for team in db.scalars(select(Team).where(Team.id.in_(team_ids)))},
        "competitions": {
            comp.id: comp
            for comp in db.scalars(
                select(Competition).where(Competition.id.in_({f.competition_id for f in fixtures}))
            )
        },
    }


def match_row(
    db, f, quotes, include_markets=True, context=None, market_key="all", include_unpriced=False
):
    prediction = (
        context["predictions"].get(f.id)
        if context is not None
        else db.scalar(
            select(Prediction)
            .where(Prediction.fixture_id == f.id, Prediction.mode == f.mode)
            .order_by(Prediction.generated_at.desc())
        )
    )
    if prediction and utc(prediction.fixture_kickoff) != utc(f.kickoff):
        prediction = None
    home, away = (
        (context["teams"][f.home_id], context["teams"][f.away_id])
        if context is not None
        else (db.get(Team, f.home_id), db.get(Team, f.away_id))
    )
    catalog = markets(prediction) if include_markets else []
    fixture_quotes = [quote for quote in quotes if quote["fixture_id"] == f.id]
    if include_markets:
        for key in dict.fromkeys(quote["market"] for quote in fixture_quotes):
            probabilities = market_probabilities(prediction, key) if prediction else {}
            quoted = {quote["outcome"] for quote in fixture_quotes if quote["market"] == key}
            entry = next((market for market in catalog if market["key"] == key), None)
            if entry is None:
                name = {
                    "1x2": "Match result · 1X2",
                    "btts": "Both teams to score",
                    "double_chance": "Double chance",
                }.get(key)
                if name is None:
                    line = "2.5" if key == "totals" else key.rsplit("_", 1)[-1]
                    name = (
                        ("First-half goals" if key.startswith("half_") else "Under/over goals")
                        + " · "
                        + line
                    )
                entry = {
                    "key": key,
                    "name": name,
                    "group": "First half"
                    if key.startswith("half_")
                    else "Goals"
                    if key.startswith("totals")
                    else "Popular",
                    "outcomes": {},
                }
                catalog.append(entry)
            if not entry["outcomes"]:
                entry["outcomes"] = {
                    outcome: probabilities.get(outcome)
                    for outcome in (
                        "home",
                        "draw",
                        "away",
                        "yes",
                        "no",
                        "1x",
                        "x2",
                        "12",
                        "over",
                        "under",
                    )
                    if outcome in quoted
                }
    if market_key != "all":
        catalog = [market for market in catalog if market["key"] == market_key]
    for market in catalog:
        market["picks"] = []
        alternatives = market.pop("outcomes")
        for outcome, probability in alternatives.items():
            prices = [
                q
                for q in quotes
                if q["fixture_id"] == f.id
                and q["market"] == market["key"]
                and q["outcome"] == outcome
            ]
            prices.sort(key=lambda q: (q["stale"], -q["odds"]))
            best = prices[0] if prices else None
            if f.mode == "live" and best is None and not include_unpriced:
                continue
            market["picks"].append(
                {
                    "fixture_id": f.id,
                    "market": market["key"],
                    "outcome": outcome,
                    "probability": probability,
                    "analysis": pick_reason(
                        prediction,
                        market["key"],
                        outcome,
                        probability,
                        home.name,
                        away.name,
                        alternatives,
                    )
                    if prediction and probability is not None
                    else {
                        "summary": "This price comes from the sportsbook. More verified match history is needed before the model can assess this selection.",
                        "heading": "Bookmaker price",
                        "model_favors": False,
                        "signals": [],
                        "caution": "Bookmaker odds are a price, not a model prediction.",
                    },
                    "odds": best["odds"] if best else None,
                    "bookmaker": best["bookmaker"] if best else None,
                    "stale": best["stale"] if best else False,
                    "publication_id": best["id"] if best else None,
                    "prices": [
                        {
                            "bookmaker": q["bookmaker"],
                            "odds": q["odds"],
                            "stale": q["stale"],
                            "updated_at": q["source_updated_at"],
                        }
                        for q in prices
                    ],
                }
            )
    return {
        "id": f.id,
        "home": home.name,
        "away": away.name,
        "home_logo": logo(home),
        "away_logo": logo(away),
        "competition": (
            context["competitions"][f.competition_id]
            if context is not None
            else db.get(Competition, f.competition_id)
        ).name,
        "competition_id": f.competition_id,
        "kickoff": utc(f.kickoff),
        "status": f.status,
        "mode": f.mode,
        "markets": [market for market in catalog if market["picks"]],
        "prediction_id": prediction.id if prediction else None,
    }


@router.get("/matchday")
def matchday(
    team: str = Query("", max_length=80),
    period: str = Query("week", pattern="^(today|tomorrow|week|fortnight)$"),
    league: str = "",
    summary: bool = False,
    market: str = Query(
        "all", pattern=r"^(all|1x2|btts|totals|totals_[0-9]\.5|half_totals_[0-9]\.5|double_chance)$"
    ),
    db=Depends(get_db),
):
    at = now()
    day = at.replace(hour=0, minute=0, second=0, microsecond=0)
    start = day + timedelta(days=1) if period == "tomorrow" else at
    end = (
        day + timedelta(days=2 if period == "tomorrow" else 1)
        if period not in {"week", "fortnight"}
        else at + timedelta(days=14 if period == "fortnight" else 7)
    )
    allowed = [
        c.id
        for c in db.scalars(select(Competition))
        if c.mode == settings.app_data_mode
        and c.provider_id.split(":")[1] in {str(i) for i in BY_ID}
    ]
    query = (
        select(Fixture)
        .where(
            Fixture.mode == settings.app_data_mode,
            Fixture.competition_id.in_(allowed),
            Fixture.status == "scheduled",
            Fixture.kickoff >= start,
            Fixture.kickoff < end,
        )
        .order_by(Fixture.kickoff)
    )
    if league:
        query = query.where(Fixture.competition_id == league)
    quotes = current_quotes(
        db,
        markets_filter=("1x2", "btts", "totals")
        if summary
        else (market,)
        if market != "all"
        else None,
    )
    priced = {q["fixture_id"] for q in quotes}
    fixtures = [
        f
        for f in db.scalars(query)
        if settings.app_data_mode == "demo"
        or (
            f.id in priced
            and (
                summary
                or market == "all"
                or any(
                    quote["fixture_id"] == f.id and quote["market"] == market for quote in quotes
                )
            )
        )
    ]
    context = match_context(db, fixtures)
    items = [
        match_row(db, f, quotes, include_markets=not summary, context=context, market_key=market)
        for f in fixtures
    ]
    return {
        "items": [r for r in items if team.casefold() in (r["home"] + " " + r["away"]).casefold()],
        "mode": settings.app_data_mode,
    }


@router.get("/matchday/{fixture_id}")
def match_markets(fixture_id: str, db=Depends(get_db)):
    return match_row(db, require_fixture(db, fixture_id), current_quotes(db, fixture_id))


@router.get("/recommendations")
def recommendations(db=Depends(get_db)):
    return {
        "items": recommendation_rows(db, upcoming=True),
        "mode": settings.app_data_mode,
        "window_hours": 24,
        "order": "kickoff",
    }


class Leg(BaseModel):
    fixture_id: str = Field(max_length=36)
    market: str = Field(max_length=32)
    outcome: str = Field(max_length=16)
    user_odds: float | None = Field(None, gt=1, le=1000, allow_inf_nan=False)


class ParlayInput(BaseModel):
    legs: list[Leg] = Field(min_length=1, max_length=8)


def parlay_summary(legs):
    probability = (
        math.prod(x["probability"] for x in legs)
        if all(x["probability"] is not None for x in legs)
        else None
    )
    common = set(p["bookmaker"] for p in legs[0]["prices"])
    for leg in legs[1:]:
        common &= {p["bookmaker"] for p in leg["prices"]}
    prices = []
    for book in sorted(common):
        qs = [next(p for p in leg["prices"] if p["bookmaker"] == book) for leg in legs]
        prices.append(
            {
                "bookmaker": book,
                "odds": math.prod(q["odds"] for q in qs),
                "stale": any(q["stale"] for q in qs),
            }
        )
    prices.sort(key=lambda p: (p["stale"], -p["odds"]))
    entered = all(leg.get("user_odds") is not None for leg in legs)
    combined = (
        math.prod(leg["user_odds"] for leg in legs)
        if entered
        else prices[0]["odds"]
        if prices
        else None
    )
    return {
        "legs": legs,
        "probability": probability,
        "failure_probability": 1 - probability if probability is not None else None,
        "confidence": "Estimate unavailable"
        if probability is None
        else "More likely to win than lose"
        if probability > 0.5
        else "Estimated chance of all picks winning",
        "combined_odds": combined,
        "prices": prices,
        "odds_basis": "Your entered prices"
        if entered
        else prices[0]["bookmaker"]
        if prices
        else "No common bookmaker",
        "approximation": "Combined chance assumes independent match outcomes. All picks must win.",
        "mode": settings.app_data_mode,
    }


@router.post("/parlays/analyze")
def analyze(body: ParlayInput, db=Depends(get_db)):
    ids, teams, legs = set(), set(), []
    quotes = current_quotes(db)
    for leg in body.legs:
        f = require_fixture(db, leg.fixture_id)
        if f.id in ids:
            raise HTTPException(
                422, "Choose one pick per match. Same-match combinations need a joint model."
            )
        if {f.home_id, f.away_id} & teams:
            raise HTTPException(422, "Choose matches with different clubs for this parlay.")
        if f.status != "scheduled" or utc(f.kickoff) <= now():
            raise HTTPException(
                409, "A match has started or is unavailable. Remove it and try again."
            )
        ids.add(f.id)
        teams.update([f.home_id, f.away_id])
        match = match_row(db, f, quotes, include_unpriced=True)
        pick = next(
            (
                p
                for m in match["markets"]
                if m["key"] == leg.market
                for p in m["picks"]
                if p["outcome"] == leg.outcome
            ),
            None,
        )
        if pick is None:
            raise HTTPException(422, "This market does not have a supported model estimate.")
        legs.append(
            {
                **pick,
                "home": match["home"],
                "away": match["away"],
                "home_logo": match["home_logo"],
                "away_logo": match["away_logo"],
                "kickoff": match["kickoff"],
                "user_odds": leg.user_odds,
            }
        )
    return parlay_summary(legs)


@router.get("/parlays/suggestions")
def suggestions(
    legs: int = Query(3, ge=2, le=5),
    min_odds: float = Query(1.01, ge=1.01, le=1000),
    max_odds: float = Query(20, ge=1.01, le=1000),
    db=Depends(get_db),
):
    if min_odds > max_odds:
        raise HTTPException(422, "Minimum odds must be below maximum odds.")
    rows = [
        r
        for r in current_quotes(db, markets_filter=("1x2", "btts", "totals"))
        if r["probability"] is not None and recorded_price_usable(r)
    ]
    # Search up to 18 earliest fixtures and all priced outcomes per bookmaker/fixture.
    fixture_ids = list(
        dict.fromkeys(r["fixture_id"] for r in sorted(rows, key=lambda r: r["kickoff"]))
    )[:18]
    teams = {i: {db.get(Fixture, i).home_id, db.get(Fixture, i).away_id} for i in fixture_ids}
    results = {}
    books = sorted({r["bookmaker"] for r in rows})
    for book in books:
        groups = {}
        for i in fixture_ids:
            options = sorted(
                [r for r in rows if r["fixture_id"] == i and r["bookmaker"] == book],
                key=lambda r: -r["probability"],
            )
            groups[i] = options
        # Bounded beam keeps the highest estimated chances in price buckets, avoiding exponential search.
        beam = [([], 1.0, 1.0, set())]
        for _ in range(legs):
            candidates = []
            for selected, price, probability, used in beam:
                last = fixture_ids.index(selected[-1]["fixture_id"]) if selected else -1
                for i in fixture_ids[last + 1 :]:
                    if used & teams[i]:
                        continue
                    for row in groups[i]:
                        new_price = price * row["odds"]
                        if new_price <= max_odds:
                            candidates.append(
                                (
                                    selected + [row],
                                    new_price,
                                    probability * row["probability"],
                                    used | teams[i],
                                )
                            )
            buckets = {}
            for candidate in sorted(candidates, key=lambda c: -c[2]):
                key = (round(math.log(candidate[1]) * 20), candidate[0][-1]["fixture_id"])
                buckets.setdefault(key, [])
                if len(buckets[key]) < 8:
                    buckets[key].append(candidate)
            beam = [c for group in buckets.values() for c in group][:5000]
        for selected, price, probability, _ in beam:
            if min_odds <= price <= max_odds:
                key = tuple((r["fixture_id"], r["market"], r["outcome"]) for r in selected)
                if key not in results or results[key]["combined_odds"] < price:
                    selected_legs = [
                        {
                            **r,
                            "prices": [{"bookmaker": book, "odds": r["odds"], "stale": r["stale"]}],
                        }
                        for r in selected
                    ]
                    results[key] = parlay_summary(selected_legs)
    ranked = sorted(results.values(), key=lambda r: -r["probability"])
    diversified, signatures = [], []
    for r in ranked:
        signature = {(leg["fixture_id"], leg["market"], leg["outcome"]) for leg in r["legs"]}
        if any(len(signature & old) >= legs - 1 for old in signatures):
            continue
        diversified.append(r)
        signatures.append(signature)
        if len(diversified) == 3:
            break
    return {
        "items": diversified,
        "mode": settings.app_data_mode,
        "searched_fixtures": len(fixture_ids),
        "search": "Highest model chances found in the available price range; one pick per match, no repeated clubs.",
    }
