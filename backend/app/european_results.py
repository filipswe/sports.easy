"""Quota-bound score refresh for official European picks; no guessed regulation scores."""

from datetime import date, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from .config import settings
from .db import now, utc
from .ingestion import settle
from .leagues import BY_ID
from .models import Competition, Fixture, IngestionRun, ProviderMapping, Recommendation, Team
from .providers import ProviderClient, ProviderUnavailable, parse_time

# Reviewed UEFA 2026/27 league-phase dates. Those matches cannot use extra time.
# Outside these windows the score feed lacks a regulation/extra-time distinction;
# leave the record pending until a provider with that distinction is integrated.
LEAGUE_PHASE = {
    2: (date(2026, 9, 8), date(2027, 1, 27)),
    3: (date(2026, 9, 16), date(2027, 1, 28)),
    848: (date(2026, 10, 15), date(2026, 12, 17)),
}


def regulation_verified(fixture, league_id):
    bounds = LEAGUE_PHASE.get(league_id)
    return bool(
        bounds
        and bounds[0]
        <= utc(fixture.kickoff).astimezone(ZoneInfo("Europe/Belgrade")).date()
        <= bounds[1]
    )


def apply_scores(db, records, league_id, fixtures, at):
    by_provider = {f.provider_id.removeprefix("the-odds-api:"): f for f in fixtures}
    aliases = {
        m.external_id.casefold(): m.entity_id
        for m in db.scalars(
            select(ProviderMapping).where(
                ProviderMapping.provider == "the-odds-api", ProviderMapping.entity_type == "team"
            )
        )
    }
    updated = 0
    for item in records:
        if not isinstance(item, dict):
            continue
        f = by_provider.get(item.get("id"))
        if (
            not f
            or item.get("sport_key") != BY_ID[league_id].sport
            or not regulation_verified(f, league_id)
        ):
            continue
        try:
            kickoff = parse_time(item["commence_time"])
            source_time = parse_time(item["last_update"])
        except (KeyError, TypeError, ValueError):
            continue
        if (
            abs((kickoff - utc(f.kickoff)).total_seconds()) > 900
            or source_time > at + timedelta(minutes=1)
            or source_time < utc(f.kickoff)
            or (f.provider_updated_at and source_time < utc(f.provider_updated_at))
        ):
            continue
        names = [item.get("home_team"), item.get("away_team")]
        if not all(
            isinstance(name, str)
            and (
                name.casefold() == db.get(Team, team_id).name.casefold()
                or aliases.get(name.casefold()) == team_id
            )
            for name, team_id in zip(names, (f.home_id, f.away_id), strict=True)
        ):
            continue
        scores = item.get("scores")
        if item.get("completed") is not True or not isinstance(scores, list) or len(scores) != 2:
            continue
        values = {s.get("name"): s.get("score") for s in scores if isinstance(s, dict)}
        if set(values) != set(names) or not all(
            isinstance(values[name], str)
            and values[name].isdigit()
            and 0 <= int(values[name]) <= 30
            for name in names
        ):
            continue
        f.status, f.home_goals, f.away_goals = (
            "finished",
            int(values[names[0]]),
            int(values[names[1]]),
        )
        f.provider_updated_at, f.fetched_at = source_time, at
        f.result_available_at = f.result_available_at or at
        updated += 1
    db.flush()
    settle(db)
    return updated


def refresh_european_results(db):
    if settings.app_data_mode != "live" or not settings.live_retention_approved:
        return
    at = now()
    fixtures = list(
        db.scalars(
            select(Fixture)
            .join(Recommendation)
            .where(
                Fixture.mode == "live",
                Fixture.provider_id.startswith("the-odds-api:"),
                Fixture.kickoff < at - timedelta(hours=2),
                Fixture.kickoff > at - timedelta(days=3),
            )
        )
    )
    groups = {}
    for fixture in fixtures:
        competition = db.get(Competition, fixture.competition_id)
        league_id = int(competition.provider_id.split(":")[1])
        if regulation_verified(fixture, league_id):
            groups.setdefault(league_id, []).append(fixture)
    client = ProviderClient(
        db, "the-odds-api", settings.odds_daily_budget, monthly_budget=settings.odds_monthly_budget
    )
    for league_id, group in groups.items():
        scope = f"european-results:{league_id}"
        previous = db.scalar(
            select(IngestionRun)
            .where(IngestionRun.provider == scope)
            .order_by(IngestionRun.created_at.desc())
        )
        interval = 86400 if all(f.status == "finished" for f in group) else 21600
        if previous and (at - utc(previous.created_at)).total_seconds() < interval:
            continue
        try:
            records = client.get(
                f"https://api.the-odds-api.com/v4/sports/{BY_ID[league_id].sport}/scores",
                {
                    "apiKey": settings.odds_api_key,
                    "daysFrom": 3,
                    "eventIds": ",".join(f.provider_id.split(":", 1)[1] for f in group),
                    "dateFormat": "iso",
                },
                cost=2,
            )
            if not isinstance(records, list):
                raise ProviderUnavailable("Invalid European scores response")
            count = apply_scores(db, records, league_id, group, at)
            db.add(
                IngestionRun(
                    provider=scope, status="complete", detail={"updated": count}, created_at=at
                )
            )
            db.commit()
        except ProviderUnavailable:
            db.rollback()
            db.add(IngestionRun(provider=scope, status="limited", detail={}, created_at=at))
            db.commit()
