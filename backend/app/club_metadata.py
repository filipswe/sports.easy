"""Optional, quota-bound crest backfill; never guesses ambiguous club identities."""

from datetime import timedelta

from sqlalchemy import select

from .config import settings
from .crests import provider_crest, safe_crest, team_logo
from .db import now
from .models import Fixture, IngestionRun, Team
from .names import normalized_name
from .providers import ProviderClient, ProviderUnavailable


def backfill_crests(db):
    if settings.app_data_mode != "live" or not settings.live_retention_approved:
        return
    team_ids = {
        team_id
        for fixture in db.scalars(
            select(Fixture).where(
                Fixture.mode == "live",
                Fixture.status == "scheduled",
                Fixture.kickoff > now(),
                Fixture.kickoff <= now() + timedelta(days=14),
            )
        )
        for team_id in (fixture.home_id, fixture.away_id)
    }
    teams = list(db.scalars(select(Team).where(Team.id.in_(team_ids))))
    attempted = {
        run.detail.get("team_id")
        for run in db.scalars(
            select(IngestionRun).where(
                IngestionRun.provider == "club-crest-lookup",
                IngestionRun.created_at > now() - timedelta(days=7),
            )
        )
    }
    client = ProviderClient(db, "api-football", settings.provider_daily_budget, minute_budget=10)
    count = 0
    for team in teams:
        reviewed = provider_crest(team.name)
        if reviewed:
            team.crest_url = reviewed
            continue
        if team_logo(team) or team.id in attempted or count >= 4 or not settings.api_football_key:
            continue
        query = normalized_name(team.name)
        if len(query) < 3:
            continue
        try:
            data = client.get(
                "https://v3.football.api-sports.io/teams",
                {"search": query},
                {"x-apisports-key": settings.api_football_key},
            )
        except ProviderUnavailable:
            break  # Fixture/results processing remains independent of optional imagery.
        if not isinstance(data, dict) or not isinstance(data.get("response"), list):
            break
        candidates = [
            item["team"]
            for item in data.get("response", [])
            if isinstance(item, dict)
            and isinstance(item.get("team"), dict)
            and isinstance(item["team"].get("name"), str)
            and normalized_name(item["team"]["name"]) == normalized_name(team.name)
        ]
        crest = safe_crest(candidates[0].get("logo")) if len(candidates) == 1 else None
        if crest:
            team.crest_url = crest
        db.add(
            IngestionRun(
                provider="club-crest-lookup",
                status="matched" if crest else "unmatched",
                detail={"team_id": team.id},
            )
        )
        count += 1
    db.commit()
