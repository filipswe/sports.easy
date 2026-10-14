from datetime import timedelta
from pathlib import Path

from app.club_metadata import backfill_crests
from app.config import settings
from app.crests import CLUB_CRESTS, provider_crest, safe_crest, team_logo
from app.db import now
from app.models import Fixture, IngestionRun, Team
from app.names import normalized_name
from app.providers import ProviderClient, ProviderUnavailable
from sqlalchemy import select


def test_reviewed_crests_are_safe_local_pngs_and_cover_unicode_names():
    public = Path(__file__).resolve().parents[2] / "web" / "public"
    for name, record in CLUB_CRESTS.items():
        assert safe_crest(record["source"]) == record["source"]
        assert record["asset"] == f"/clubs/api-team-{record['provider_id']}.png"
        data = (public / record["asset"].lstrip("/")).read_bytes()
        assert data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) < 512_000
        team = Team(name=name, provider_id="the-odds-api:" + name)
        assert team_logo(team) == record["asset"]
        assert provider_crest(name) == record["source"]
    assert normalized_name("Bodø/Glimt") == normalized_name("Bodo Glimt")
    assert normalized_name("Fenerbahçe") == normalized_name("Fenerbahce")


def test_optional_backfill_rejects_ambiguous_clubs_and_reuses_attempt_ledger(db, monkeypatch):
    monkeypatch.setattr(settings, "app_data_mode", "live")
    monkeypatch.setattr(settings, "live_retention_approved", True)
    monkeypatch.setattr(settings, "api_football_key", "test-only")
    fixture = db.scalar(select(Fixture).where(Fixture.status == "scheduled"))
    fixture.mode = "live"
    fixture.kickoff = now() + timedelta(days=1)
    home, away = db.get(Team, fixture.home_id), db.get(Team, fixture.away_id)
    for team in (home, away):
        team.name, team.provider_id, team.crest_url = "Ambiguous Club", "unknown:" + team.id, None
    db.commit()
    calls = []

    def lookup(self, url, params, headers):
        calls.append(params)
        return {
            "response": [
                {
                    "team": {
                        "name": "Ambiguous Club",
                        "logo": "https://media.api-sports.io/football/teams/1.png",
                    }
                }
            ]
            * 2
        }

    monkeypatch.setattr(ProviderClient, "get", lookup)
    backfill_crests(db)
    assert len(calls) == 2 and not home.crest_url and not away.crest_url
    assert (
        len(
            list(
                db.scalars(select(IngestionRun).where(IngestionRun.provider == "club-crest-lookup"))
            )
        )
        == 2
    )
    backfill_crests(db)
    assert len(calls) == 2


def test_optional_crest_outage_keeps_existing_data(db, monkeypatch):
    monkeypatch.setattr(settings, "app_data_mode", "live")
    monkeypatch.setattr(settings, "live_retention_approved", True)
    monkeypatch.setattr(settings, "api_football_key", "test-only")
    fixture = db.scalar(select(Fixture).where(Fixture.status == "scheduled"))
    fixture.mode = "live"
    home = db.get(Team, fixture.home_id)
    home.name, home.provider_id, home.crest_url = "Unknown Club", "unknown", None
    db.commit()

    def outage(*args, **kwargs):
        raise ProviderUnavailable("test outage")

    monkeypatch.setattr(ProviderClient, "get", outage)
    backfill_crests(db)
    assert not home.crest_url
    assert db.get(Fixture, fixture.id).status == "scheduled"
