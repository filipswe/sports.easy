from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from app.config import settings
from app.db import now, utc
from app.european_predictions import publish_european_predictions
from app.european_results import apply_scores, refresh_european_results, regulation_verified
from app.ingestion import store_odds, upsert_european_events
from app.matchday import current_quotes, match_row
from app.model import market_probabilities
from app.models import Fixture, IngestionRun, Prediction, Publication, Recommendation, Settlement
from app.picks import featured_window, publish_recommendations, recommendation_rows
from app.providers import ProviderClient
from sqlalchemy import select


def european(db, monkeypatch, kickoff=None):
    monkeypatch.setattr(settings, "app_data_mode", "live")
    monkeypatch.setattr(settings, "live_retention_approved", True)
    monkeypatch.setattr(settings, "odds_region", "eu")
    monkeypatch.setattr(settings, "odds_bookmaker_key", "pinnacle")
    event = {
        "id": "current-cup",
        "sport_key": "soccer_uefa_champs_league",
        "commence_time": (kickoff or now() + timedelta(hours=1)).isoformat(),
        "home_team": "Feyenoord",
        "away_team": "Como 1907",
        "bookmakers": [
            {
                "key": "pinnacle",
                "title": "Pinnacle",
                "last_update": now().isoformat(),
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Feyenoord", "price": 3.5},
                            {"name": "Draw", "price": 4},
                            {"name": "Como 1907", "price": 2},
                        ],
                    }
                ],
            }
        ],
    }
    upsert_european_events(db, [event], now())
    store_odds(db, [event], observed=True)
    db.commit()
    f = db.scalar(select(Fixture).where(Fixture.provider_id == "the-odds-api:current-cup"))
    return f, event


def test_european_baseline_uses_complete_real_prices_without_invented_goal_rates(db, monkeypatch):
    fixture, _ = european(db, monkeypatch)
    publish_european_predictions(db)
    db.commit()
    prediction = db.scalar(select(Prediction).where(Prediction.fixture_id == fixture.id))
    assert sum(prediction.probabilities["1x2"].values()) == pytest.approx(1)
    assert prediction.probabilities["1x2"]["away"] == pytest.approx(
        (1 / 2) / (1 / 3.5 + 1 / 4 + 1 / 2)
    )
    assert "home_rate" not in prediction.factors
    assert market_probabilities(prediction, "totals_1.5") == {}
    assert sum(market_probabilities(prediction, "double_chance").values()) == pytest.approx(2)
    rows = current_quotes(db, fixture.id)
    match = match_row(db, fixture, rows)
    assert "market-based estimate" in match["markets"][0]["picks"][0]["analysis"]["summary"]
    ids = set(db.scalars(select(Publication.id)))
    publish_european_predictions(db)
    db.commit()
    assert set(db.scalars(select(Publication.id))) == ids


def test_earliest_calendar_day_europe_precedes_weekend_and_rolls_over(db, monkeypatch):
    fixture, _ = european(db, monkeypatch)
    publish_recommendations(db)
    db.commit()
    rows = recommendation_rows(db, upcoming=True)
    assert rows and {r["fixture_id"] for r in rows} == {fixture.id}
    assert rows[0]["probability_basis"] == "Market-based chance"
    archive = recommendation_rows(db)
    fixture.status, fixture.home_goals, fixture.away_goals = "finished", 0, 1
    db.commit()
    from app.ingestion import settle

    settle(db)
    publish_recommendations(db)
    db.commit()
    assert not recommendation_rows(db, upcoming=True)
    assert recommendation_rows(db)[0]["recommendation_id"] == archive[0]["recommendation_id"]
    assert recommendation_rows(db)[0]["result"] == "won"


def test_featured_window_ends_at_belgrade_midnight(db, monkeypatch):
    import app.picks as picks

    start = datetime(2026, 10, 14, 18, tzinfo=UTC)
    monkeypatch.setattr(
        picks,
        "eligible_rows",
        lambda *args, **kwargs: [{"kickoff": start}, {"kickoff": start + timedelta(hours=5)}],
    )
    rows, first, end = featured_window(db)
    assert rows == [{"kickoff": start}] and first == start
    assert end == datetime(2026, 10, 14, 22, tzinfo=UTC)


def test_score_identity_phase_and_corrections_are_verified(db, monkeypatch):
    fixture, event = european(db, monkeypatch)
    publish_recommendations(db)
    db.commit()
    at = utc(fixture.kickoff) + timedelta(hours=3)
    record = {
        **event,
        "commence_time": fixture.kickoff.isoformat(),
        "completed": True,
        "last_update": at.isoformat(),
        "scores": [{"name": "Feyenoord", "score": "0"}, {"name": "Como 1907", "score": "1"}],
    }
    assert apply_scores(db, [{**record, "home_team": "Wrong club"}], 2, [fixture], at) == 0
    assert (
        apply_scores(
            db, [{**record, "scores": [{"name": "Feyenoord", "score": "0"}]}], 2, [fixture], at
        )
        == 0
    )
    assert apply_scores(db, [record], 2, [fixture], at) == 1
    db.commit()
    recommendation = db.scalar(
        select(Recommendation).where(Recommendation.fixture_id == fixture.id)
    )
    first = db.scalar(
        select(Settlement).where(Settlement.publication_id == recommendation.publication_id)
    )
    assert first.result == "won"
    correction = {
        **record,
        "last_update": (at + timedelta(seconds=10)).isoformat(),
        "scores": [{"name": "Feyenoord", "score": "2"}, {"name": "Como 1907", "score": "1"}],
    }
    apply_scores(db, [correction], 2, [fixture], at + timedelta(seconds=10))
    db.commit()
    last = db.scalar(
        select(Settlement)
        .where(Settlement.publication_id == recommendation.publication_id)
        .order_by(Settlement.recorded_at.desc())
    )
    assert last.result == "lost" and last.supersedes_id == first.id
    assert not regulation_verified(SimpleNamespace(kickoff=datetime(2027, 2, 20, tzinfo=UTC)), 2)
    assert not regulation_verified(SimpleNamespace(kickoff=datetime(2027, 10, 14, tzinfo=UTC)), 2)


def test_score_poll_is_cached_and_reserves_real_cost(db, monkeypatch):
    fixture, event = european(db, monkeypatch)
    publish_recommendations(db)
    db.commit()
    import app.european_results as results

    monkeypatch.setattr(results, "now", lambda: utc(fixture.kickoff) + timedelta(hours=3))
    calls = []

    def get(self, url, params, cost=1):
        calls.append((url, cost))
        return []

    monkeypatch.setattr(ProviderClient, "get", get)
    refresh_european_results(db)
    refresh_european_results(db)
    assert len(calls) == 1 and calls[0][1] == 2
    assert db.scalar(select(IngestionRun).where(IngestionRun.provider == "european-results:2"))


def test_current_assessment_changes_but_original_official_record_does_not(db, monkeypatch):
    fixture, event = european(db, monkeypatch)
    publish_recommendations(db)
    db.commit()
    original = recommendation_rows(db)[0]
    event["bookmakers"][0]["last_update"] = now().isoformat()
    event["bookmakers"][0]["markets"][0]["outcomes"] = [
        {"name": "Feyenoord", "price": 4},
        {"name": "Draw", "price": 5},
        {"name": "Como 1907", "price": 1.6},
    ]
    store_odds(db, [event], observed=True)
    db.commit()
    publish_recommendations(db)
    db.commit()
    current = recommendation_rows(db, upcoming=True)[0]
    archive = recommendation_rows(db)[0]
    assert current["recommendation_id"] == original["recommendation_id"]
    assert current["probability"] != original["probability"]
    assert current["odds"] == 1.6
    assert archive["probability"] == original["probability"] and archive["odds"] == original["odds"]
    assert "58%" in current["reason"]
