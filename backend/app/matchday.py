"""Match browsing and server-verified parlay research, without invented bookmaker prices."""

import math
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from .config import settings
from .db import get_db, now, utc
from .models import Competition, Fixture, Prediction, Team
from .picks import recommendation_rows
from .research import all_rows, require_fixture

router = APIRouter(prefix="/api", tags=["matchday"])

CLUBS = {
    "Arsenal": "arsenal",
    "Chelsea": "chelsea",
    "Liverpool": "liverpool",
    "Manchester City": "manchester-city",
    "Newcastle United": "newcastle-united",
    "Aston Villa": "aston-villa",
    "Tottenham Hotspur": "tottenham-hotspur",
    "Brighton": "brighton",
    "Manchester United": "manchester-united",
    "Everton": "everton",
    "Fulham": "fulham",
    "Brentford": "brentford",
}


def logo(team):
    if team.name in CLUBS:
        return "/clubs/" + CLUBS[team.name] + ".png"
    provider_id = team.provider_id.removeprefix("api-football:")
    return (
        f"https://media.api-sports.io/football/teams/{provider_id}.png"
        if provider_id.isdigit()
        else None
    )


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
    for line in [0.5, 1.5, 2.5, 3.5, 4.5]:
        u = under(h + a, line)
        add(
            "totals" if line == 2.5 else f"totals_{line}",
            f"Total goals · {line}",
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


def current_quotes(db, fixture_id=None):
    seen, result = set(), []
    for row in all_rows(db, fixture_id=fixture_id):
        key = (row["fixture_id"], row["market"], row["outcome"], row["bookmaker_id"])
        if key not in seen and row["region"] == settings.odds_region:
            result.append(row)
            seen.add(key)
    # One consistent source across every match and parlay. Existing archives stay untouched.
    names = sorted({r["bookmaker"] for r in result})
    preferred = (
        "Demo Sportsbook" if settings.app_data_mode == "demo" else settings.odds_bookmaker_key
    )
    book = next(
        (n for n in names if n.casefold() == preferred.casefold()), names[0] if names else None
    )
    return [r for r in result if r["bookmaker"] == book]


def match_row(db, f, quotes, include_markets=True):
    prediction = db.scalar(
        select(Prediction)
        .where(Prediction.fixture_id == f.id)
        .order_by(Prediction.generated_at.desc())
    )
    if prediction and utc(prediction.fixture_kickoff) != utc(f.kickoff):
        prediction = None
    home, away = db.get(Team, f.home_id), db.get(Team, f.away_id)
    catalog = markets(prediction) if include_markets else []
    for market in catalog:
        market["picks"] = []
        for outcome, probability in market.pop("outcomes").items():
            prices = [
                q
                for q in quotes
                if q["fixture_id"] == f.id
                and q["market"] == market["key"]
                and q["outcome"] == outcome
            ]
            prices.sort(key=lambda q: (q["stale"], -q["odds"]))
            best = prices[0] if prices else None
            market["picks"].append(
                {
                    "fixture_id": f.id,
                    "market": market["key"],
                    "outcome": outcome,
                    "probability": probability,
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
        "competition": db.get(Competition, f.competition_id).name,
        "competition_id": f.competition_id,
        "kickoff": utc(f.kickoff),
        "status": f.status,
        "mode": f.mode,
        "markets": catalog,
        "prediction_id": prediction.id if prediction else None,
    }


@router.get("/matchday")
def matchday(
    team: str = Query("", max_length=80),
    period: str = Query("week", pattern="^(today|tomorrow|week)$"),
    league: str = "",
    db=Depends(get_db),
):
    at = now()
    day = at.replace(hour=0, minute=0, second=0, microsecond=0)
    start = day + timedelta(days=1) if period == "tomorrow" else at
    end = (
        day + timedelta(days=2 if period == "tomorrow" else 1)
        if period != "week"
        else at + timedelta(days=7)
    )
    query = (
        select(Fixture)
        .where(
            Fixture.mode == settings.app_data_mode,
            Fixture.status == "scheduled",
            Fixture.kickoff >= start,
            Fixture.kickoff < end,
        )
        .order_by(Fixture.kickoff)
    )
    if league:
        query = query.where(Fixture.competition_id == league)
    quotes = current_quotes(db)
    items = [match_row(db, f, quotes) for f in db.scalars(query)]
    return {
        "items": [r for r in items if team.casefold() in (r["home"] + " " + r["away"]).casefold()],
        "mode": settings.app_data_mode,
    }


@router.get("/matchday/{fixture_id}")
def match_markets(fixture_id: str, db=Depends(get_db)):
    return match_row(db, require_fixture(db, fixture_id), current_quotes(db, fixture_id))


@router.get("/recommendations")
def recommendations(db=Depends(get_db)):
    return {"items": recommendation_rows(db, upcoming=True), "mode": settings.app_data_mode}


class Leg(BaseModel):
    fixture_id: str = Field(max_length=36)
    market: str = Field(max_length=32)
    outcome: str = Field(max_length=16)
    user_odds: float | None = Field(None, gt=1, le=1000, allow_inf_nan=False)


class ParlayInput(BaseModel):
    legs: list[Leg] = Field(min_length=1, max_length=8)


def parlay_summary(legs):
    probability = math.prod(x["probability"] for x in legs)
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
        "failure_probability": 1 - probability,
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
        match = match_row(db, f, quotes)
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
    rows = [r for r in current_quotes(db) if r["mode"] == "demo" or not r["stale"]]
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
