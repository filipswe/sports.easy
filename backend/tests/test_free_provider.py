"""Free-feed contracts, real-data identity and conservative quota handling."""

import copy
from datetime import timedelta

import pytest
from app.config import settings
from app.crests import safe_crest, team_logo
from app.db import Base, now, utc
from app.ingestion import ingest, upsert_fixtures
from app.leagues import LEAGUES
from app.models import Fixture, IngestionRun, Team
from app.providers import (
    FOOTBALL_DATA_CODES,
    DemoFootball,
    DemoOdds,
    FootballData,
    ProviderClient,
    ProviderEntitlement,
    ProviderUnavailable,
    TheOddsAPI,
)
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


@pytest.fixture
def empty_db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
    engine.dispose()


def payload(league, season):
    return {
        "resultSet": {"count": 1},
        "matches": [
            {
                "id": 123,
                "competition": {"code": FOOTBALL_DATA_CODES[league.id]},
                "season": {"startDate": f"{season}-08-01"},
                "utcDate": f"{season}-09-01T14:00:00Z",
                "status": "FINISHED",
                "lastUpdated": f"{season}-09-01T16:30:00Z",
                "homeTeam": {
                    "id": 57,
                    "name": "Arsenal FC",
                    "shortName": "Arsenal",
                    "crest": "https://crests.football-data.org/57.png",
                },
                "awayTeam": {
                    "id": 61,
                    "name": "Chelsea FC",
                    "shortName": "Chelsea",
                    "crest": "https://crests.football-data.org/61.svg",
                },
                "score": {
                    "duration": "REGULAR",
                    "fullTime": {"home": 2, "away": 1},
                    "halfTime": {"home": 1, "away": 0},
                },
            }
        ],
    }


def test_free_feed_maps_all_leagues_and_preserves_halftime(empty_db, monkeypatch):
    monkeypatch.setattr(settings, "football_data_key", "private-test-token")
    provider, calls = FootballData(empty_db), []

    def get(url, params, headers):
        calls.append((url, params, headers))
        league = next(
            league
            for league in LEAGUES
            if url.endswith(f"/{FOOTBALL_DATA_CODES[league.id]}/matches")
        )
        return payload(league, params["season"])

    provider.client.get = get
    records = provider.fixtures()
    assert len(records) == 10
    assert {r["league_id"] for r in records} == {league.id for league in LEAGUES}
    assert {r["season"] for r in records} == {settings.season, settings.season - 1}
    assert all(r["home_half_goals"] == 1 and r["away_half_goals"] == 0 for r in records)
    assert all(c[0].startswith("https://api.football-data.org/v4/competitions/") for c in calls)
    assert all(c[2] == {"X-Auth-Token": "private-test-token"} for c in calls)


def test_free_previous_season_is_optional_but_current_is_required(empty_db, monkeypatch):
    monkeypatch.setattr(settings, "football_data_key", "private-test-token")
    provider = FootballData(empty_db)

    def get(url, params, headers):
        if params["season"] != settings.season:
            raise ProviderEntitlement("Account excludes previous season")
        return {"matches": [], "resultSet": {"count": 0}}

    provider.client.get = get
    assert provider.fixtures() == []
    assert len(list(empty_db.scalars(select(IngestionRun)))) == 5
    provider.client.get = lambda *args: (_ for _ in ()).throw(ProviderEntitlement("Current denied"))
    with pytest.raises(ProviderEntitlement, match="Current denied"):
        provider.fixtures()


def test_free_feed_refuses_extra_time_unknown_kickoffs_and_partial_history(empty_db):
    provider = FootballData(empty_db)
    data = payload(LEAGUES[0], settings.season)
    provider.client.get = lambda *args: data
    match = data["matches"][0]
    match["score"]["duration"] = "EXTRA_TIME"
    record = provider.league_fixtures(LEAGUES[0], settings.season)[0]
    assert record["status"] == "unconfirmed" and record["home_goals"] is None
    match["status"] = "SCHEDULED"
    assert provider.league_fixtures(LEAGUES[0], settings.season)[0]["status"] == "unconfirmed"
    data["resultSet"]["count"] = 2
    with pytest.raises(ProviderUnavailable, match="incomplete history"):
        provider.league_fixtures(LEAGUES[0], settings.season)


def test_free_feed_requires_its_own_key(empty_db, monkeypatch):
    monkeypatch.setattr(settings, "football_data_key", "")
    with pytest.raises(ProviderUnavailable, match="FOOTBALL_DATA_KEY"):
        FootballData(empty_db).fixtures()


def test_free_identity_and_first_observed_history_are_separate(empty_db, monkeypatch):
    record = DemoFootball(now()).fixtures()[0]
    record["home"]["crest"] = "https://crests.football-data.org/57.png"
    fetched = now()
    upsert_fixtures(empty_db, [record], "demo", fetched)
    monkeypatch.setattr(settings, "football_provider", "football-data")
    upsert_fixtures(empty_db, [copy.deepcopy(record)], "live", fetched)
    empty_db.commit()
    fixtures = list(empty_db.scalars(select(Fixture)))
    assert len(fixtures) == 2 and fixtures[0].home_id != fixtures[1].home_id
    live = next(f for f in fixtures if f.mode == "live")
    assert live.provider_id.startswith("football-data:")
    assert utc(live.result_available_at) == fetched
    assert team_logo(empty_db.get(Team, live.home_id)) == record["home"]["crest"]


def test_monthly_and_minute_limits_stop_before_network(empty_db):
    old = now() - timedelta(days=1)
    # Use today's date on the first day of a month, keeping the test valid across month boundaries.
    if old.month != now().month:
        old = now()
    empty_db.add(IngestionRun(provider="monthly", status="ok", detail={}, created_at=old))
    empty_db.add(IngestionRun(provider="minute", status="error", detail={}))
    empty_db.commit()
    with pytest.raises(ProviderUnavailable, match="monthly"):
        ProviderClient(empty_db, "monthly", 10, monthly_budget=1).get("https://unused.invalid", {})
    with pytest.raises(ProviderUnavailable, match="minute"):
        ProviderClient(empty_db, "minute", 10, minute_budget=1).get("https://unused.invalid", {})


def test_three_day_recorded_prices_expire_without_becoming_fresh(monkeypatch):
    from app.research import recorded_price_usable

    anchor = now()
    monkeypatch.setattr("app.research.now", lambda: anchor)
    row = {
        "mode": "live",
        "stale": True,
        "source_updated_at": anchor - timedelta(hours=2),
        "fetched_at": anchor - timedelta(hours=1),
    }
    monkeypatch.setattr(settings, "odds_poll_seconds", 259200)
    assert recorded_price_usable(row) and row["stale"]
    row["fetched_at"] = anchor - timedelta(hours=73)
    assert not recorded_price_usable(row)
    row["fetched_at"] = anchor - timedelta(hours=1)
    row["source_updated_at"] = None
    assert not recorded_price_usable(row)
    row["source_updated_at"] = anchor - timedelta(hours=2)
    monkeypatch.setattr(settings, "odds_poll_seconds", 14400)
    assert not recorded_price_usable(row)


@pytest.mark.parametrize(
    "url",
    [
        "https://attacker.invalid/57.png",
        "https://crests.football-data.org.attacker.invalid/57.svg",
        "https://private@crests.football-data.org/57.png",
        "https://crests.football-data.org/57.png?private=value",
    ],
)
def test_crest_urls_exclude_arbitrary_hosts_and_credentials(url):
    assert safe_crest(url) is None


def test_reviewed_aliases_use_provider_identity_and_refuse_conflicts(empty_db):
    from app.models import ProviderMapping
    from app.team_aliases import install_football_data_aliases

    source = Team(name="Man City", provider_id="football-data:65")
    other = Team(name="Man City", provider_id="api-football:65")
    empty_db.add_all([source, other])
    empty_db.flush()
    assert install_football_data_aliases(empty_db) == 1
    mapping = empty_db.scalar(select(ProviderMapping))
    assert mapping.external_id == "Manchester City" and mapping.entity_id == source.id
    assert install_football_data_aliases(empty_db) == 0
    mapping.entity_id = other.id
    empty_db.flush()
    with pytest.raises(ProviderUnavailable, match="conflicts"):
        install_football_data_aliases(empty_db)


def test_live_league_picker_shows_current_seasons_once(empty_db, monkeypatch):
    from app.main import meta
    from app.models import Competition

    monkeypatch.setattr(settings, "app_data_mode", "live")
    monkeypatch.setattr(settings, "football_provider", "football-data")
    for league in LEAGUES:
        for season in (2025, 2026):
            empty_db.add(
                Competition(
                    name=league.name,
                    season=season,
                    mode="live",
                    provider_id=f"football-data:{league.id}:{season}",
                )
            )
    empty_db.add(
        Competition(name="Other feed", season=2026, mode="live", provider_id="api-football:39:2026")
    )
    empty_db.commit()
    choices = meta(empty_db)["leagues"]
    assert len(choices) == 5 and all(c["season"] == 2026 for c in choices)
    assert {c["name"] for c in choices} == {league.name for league in LEAGUES}
    assert len(list(empty_db.scalars(select(Competition)))) == 11


def test_daily_shortlist_retains_original_prices_when_they_age(empty_db, monkeypatch):
    from app.picks import publish_recommendations, recommendation_rows

    anchor = now()
    records = DemoFootball(anchor).fixtures()
    events = DemoOdds(records, anchor).odds()
    monkeypatch.setattr(settings, "app_data_mode", "live")
    monkeypatch.setattr(settings, "football_provider", "football-data")
    monkeypatch.setattr(settings, "live_retention_approved", True)
    monkeypatch.setattr(FootballData, "fixtures", lambda self: records)
    monkeypatch.setattr(TheOddsAPI, "odds", lambda self: events)
    monkeypatch.setattr(TheOddsAPI, "european_events", lambda self: [])
    monkeypatch.setattr(settings, "odds_bookmaker_key", "demo-exchange")
    ingest(empty_db)
    before = recommendation_rows(empty_db, upcoming=True)
    assert len(before) == 3
    monkeypatch.setattr("app.research.now", lambda: anchor + timedelta(minutes=30))
    after = recommendation_rows(empty_db, upcoming=True)
    assert [r["id"] for r in after] == [r["id"] for r in before]
    assert all(r["stale"] for r in after)
    publish_recommendations(empty_db)
    assert len(recommendation_rows(empty_db)) == len(before)
