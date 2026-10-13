"""Provider calls are worker-only. URLs are fixed; responses are data, never instructions."""

import hashlib
import random
import time
from datetime import timedelta
from typing import Protocol

import httpx
from sqlalchemy import func, select

from .config import settings
from .db import now, utc
from .leagues import BY_ID, BY_SPORT, LEAGUES
from .models import IngestionRun


class ProviderUnavailable(Exception):
    pass


class FootballDataProvider(Protocol):
    def fixtures(self) -> list[dict]: ...


class OddsProvider(Protocol):
    def odds(self) -> list[dict]: ...


def parse_time(text):
    from datetime import datetime

    return utc(datetime.fromisoformat(text.replace("Z", "+00:00")))


class ProviderClient:
    def __init__(self, db, provider, budget):
        self.db, self.provider, self.budget = db, provider, budget

    def get(self, url, params, headers=None, cost=1):
        since = now().replace(hour=0, minute=0, second=0, microsecond=0)
        used = (
            self.db.scalar(
                select(func.count())
                .select_from(IngestionRun)
                .where(IngestionRun.provider == self.provider, IngestionRun.created_at >= since)
            )
            or 0
        )
        # Reserve worst-case quota units before each attempt; persists even when ingestion fails.
        if used + cost > self.budget:
            raise ProviderUnavailable("Local daily quota budget exhausted")
        for attempt in range(3):
            if used + cost > self.budget:
                raise ProviderUnavailable("Local daily quota budget exhausted")
            reservations = [
                IngestionRun(provider=self.provider, status="request", detail={})
                for _ in range(cost)
            ]
            self.db.add_all(reservations)
            self.db.commit()
            used += cost
            try:
                with httpx.Client(timeout=15, follow_redirects=False) as client:
                    response = client.get(url, params=params, headers=headers)
                reservations[0].detail = {
                    "http_status": response.status_code,
                    "remaining": response.headers.get("x-requests-remaining")
                    or response.headers.get("x-ratelimit-requests-remaining"),
                }
                reservations[0].status = "ok" if response.is_success else "error"
                self.db.commit()
                if response.status_code == 429:
                    raise ProviderUnavailable("Provider quota exhausted; retry next scheduled job")
                if response.status_code >= 500:
                    raise httpx.TransportError("Provider unavailable")
                if not response.is_success:
                    raise ProviderUnavailable(
                        "Provider rejected request; inspect account entitlement"
                    )
                data = response.json()
                if isinstance(data, dict) and data.get("errors"):
                    raise ProviderUnavailable(
                        "Provider reported an API error; inspect quota/entitlements"
                    )
                return data
            except (httpx.TransportError, ValueError):
                reservations[0].status = "error"
                self.db.commit()
                if attempt == 2:
                    raise ProviderUnavailable("Provider timeout or invalid response") from None
                time.sleep(2**attempt + random.random())
        raise ProviderUnavailable("Provider unavailable")


class APIFootball:
    def __init__(self, db):
        self.client = ProviderClient(db, "api-football", settings.provider_daily_budget)

    def fixtures(self):
        if not settings.api_football_key:
            raise ProviderUnavailable("API_FOOTBALL_KEY is missing; live fixtures unavailable")
        result = []
        for league in LEAGUES:
            result.extend(self.league_fixtures(league))
        return result

    def league_fixtures(self, league):
        result = []
        for season in [settings.season - 1, settings.season]:
            data = self.client.get(
                "https://v3.football.api-sports.io/fixtures",
                {"league": league.id, "season": season},
                {"x-apisports-key": settings.api_football_key},
            )
            if data.get("paging", {}).get("total", 1) > 1:
                raise ProviderUnavailable("Unexpected pagination; refuse partial history")
            for item in data.get("response", []):
                f, teams = item["fixture"], item["teams"]
                short = f["status"]["short"]
                status = {
                    "NS": "scheduled",
                    "FT": "finished",
                    "PST": "postponed",
                    "CANC": "cancelled",
                    "ABD": "abandoned",
                    "TBD": "unconfirmed",
                }.get(short, "started")
                # FT only: extra time/penalties intentionally cannot settle regulation markets here.
                result.append(
                    {
                        "id": str(f["id"]),
                        "home": teams["home"],
                        "away": teams["away"],
                        "kickoff": parse_time(f["date"]),
                        "status": status,
                        "venue": f.get("venue", {}).get("name"),
                        "home_goals": item.get("score", {}).get("fulltime", {}).get("home"),
                        "away_goals": item.get("score", {}).get("fulltime", {}).get("away"),
                        "home_half_goals": item.get("score", {}).get("halftime", {}).get("home"),
                        "away_half_goals": item.get("score", {}).get("halftime", {}).get("away"),
                        "league_id": league.id,
                        "league_name": league.name,
                        "season": season,
                    }
                )
        return result


class TheOddsAPI:
    def __init__(self, db):
        self.client = ProviderClient(db, "the-odds-api", settings.odds_daily_budget)

    def odds(self):
        if not settings.odds_api_key:
            raise ProviderUnavailable("ODDS_API_KEY is missing; live quotes unavailable")
        events = []
        for league in LEAGUES:
            events.extend(
                self.client.get(
                    f"https://api.the-odds-api.com/v4/sports/{league.sport}/odds",
                    {
                        "apiKey": settings.odds_api_key,
                        "regions": settings.odds_region,
                        "bookmakers": settings.odds_bookmaker_key,
                        "markets": "h2h,totals",
                        "oddsFormat": "decimal",
                        "dateFormat": "iso",
                    },
                    cost=2,
                )
            )
        return events


TEAM_NAMES = [
    "Arsenal",
    "Chelsea",
    "Liverpool",
    "Manchester City",
    "Newcastle United",
    "Aston Villa",
    "Tottenham Hotspur",
    "Brighton",
    "Manchester United",
    "Everton",
    "Fulham",
    "Brentford",
]


class DemoFootball:
    """Seeded synthetic matches, anchored once on first ingestion. Never genuine history."""

    def __init__(self, anchor, league_id=39):
        self.anchor = anchor
        self.league = BY_ID[league_id]

    def fixtures(self):
        league = self.league
        names = [name for name, _ in league.clubs]
        # Preserve all existing English IDs and results; other leagues have distinct IDs/seeds.
        suffix = "" if league.id == 39 else f"{league.id}-"
        team_offset = 0 if league.id == 39 else league.id * 100
        rng = random.Random(1947 if league.id == 39 else 1947 + league.id)
        result = []
        for i in range(264):
            h = i % 12
            a = (h + 1 + (i // 12) % 11) % 12
            result.append(
                {
                    "id": f"{suffix}history-{i}",
                    "home": {"id": team_offset + h, "name": names[h]},
                    "away": {"id": team_offset + a, "name": names[a]},
                    "kickoff": self.anchor - timedelta(days=280 - i),
                    "status": "finished",
                    "venue": None,
                    "home_goals": rng.choices(range(5), [15, 35, 28, 16, 6])[0],
                    "away_goals": rng.choices(range(5), [28, 35, 23, 10, 4])[0],
                    "season": self.anchor.year,
                    "league_id": league.id,
                    "league_name": league.name,
                }
            )
        for i in range(12):
            h, a = i, (i + 5) % 12
            result.append(
                {
                    "id": f"{suffix}upcoming-{i}",
                    "home": {"id": team_offset + h, "name": names[h]},
                    "away": {"id": team_offset + a, "name": names[a]},
                    "kickoff": self.anchor
                    + timedelta(
                        hours=4
                        + i * 11
                        + (0 if league.id == 39 else list(BY_ID).index(league.id) * 0.75)
                    ),
                    "status": "scheduled",
                    "venue": "Demo stadium",
                    "home_goals": None,
                    "away_goals": None,
                    "season": self.anchor.year,
                    "league_id": league.id,
                    "league_name": league.name,
                }
            )
        for f in result:
            half_rng = random.Random("half:" + f["id"])
            for side in ["home", "away"]:
                goals = f[side + "_goals"]
                f[side + "_half_goals"] = (
                    sum(half_rng.random() < 0.45 for _ in range(goals))
                    if goals is not None
                    else None
                )
        return result


class DemoOdds:
    def __init__(self, fixtures, anchor):
        self.fixtures, self.anchor = fixtures, anchor

    def odds(self):
        events = []
        for i, f in enumerate(self.fixtures):
            if f["status"] != "scheduled":
                continue
            books = []
            for j, name in enumerate(["Demo Exchange", "Demo Sportsbook"]):
                # Prices are fixed synthetic provider quotes, independent of model/target filters.
                home = [1.72, 2.25, 1.91, 1.48, 2.65, 3.15][i % 6] + j * 0.06
                books.append(
                    {
                        "key": name.lower().replace(" ", "-"),
                        "title": name,
                        "last_update": (self.anchor - timedelta(minutes=2 + j)).isoformat(),
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": f["home"]["name"], "price": home},
                                    {"name": "Draw", "price": 3.6 + j * 0.1},
                                    {
                                        "name": f["away"]["name"],
                                        "price": round(1 / (1.07 - 1 / home - 1 / 3.6), 2),
                                    },
                                ],
                            },
                            {
                                "key": "totals",
                                "outcomes": [
                                    {"name": "Over", "point": 2.5, "price": 1.85 + j * 0.08},
                                    {"name": "Under", "point": 2.5, "price": 2.05 - j * 0.04},
                                ],
                            },
                            {
                                "key": "btts",
                                "outcomes": [
                                    {"name": "Yes", "price": 1.78 + j * 0.07},
                                    {"name": "No", "price": 2.1 - j * 0.06},
                                ],
                            },
                        ],
                    }
                )
            events.append(
                {
                    "id": f["id"],
                    "sport_key": BY_ID[f.get("league_id", 39)].sport,
                    "home_team": f["home"]["name"],
                    "away_team": f["away"]["name"],
                    "commence_time": f["kickoff"].isoformat(),
                    "bookmakers": books,
                }
            )
        return events


def match_fixture(event, fixtures, names, aliases):
    """Exact reviewed identity or canonical name only; no fuzzy guesses. Reject ambiguity."""

    def identify(name):
        return aliases.get(name.casefold()) or names.get(name.casefold())

    home, away = identify(event["home_team"]), identify(event["away_team"])
    league = BY_SPORT.get(event.get("sport_key"))
    if not home or not away or league is None:
        return None
    kickoff = parse_time(event["commence_time"])
    candidates = [
        f
        for f in fixtures
        if f.home_id == home
        and f.away_id == away
        and abs((utc(f.kickoff) - kickoff).total_seconds()) <= 900
    ]
    return candidates[0] if len(candidates) == 1 else None


def fingerprint(data):
    import json

    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()
