from datetime import timedelta

import pytest
from app.config import settings
from app.db import now
from app.ingestion import ingest, settle
from app.models import Fixture, Prediction, Publication, Quote, Settlement
from app.providers import (
    APIFootball,
    ProviderClient,
    ProviderUnavailable,
    TheOddsAPI,
    match_fixture,
)
from app.research import Filters, search
from sqlalchemy import func, select


def test_ingestion_is_idempotent_and_does_not_reset_age(db):
    counts = [
        db.scalar(select(func.count()).select_from(cls))
        for cls in [Fixture, Prediction, Quote, Publication]
    ]
    first = db.scalar(select(Quote))
    stamp = first.fetched_at
    ingest(db)
    assert counts == [
        db.scalar(select(func.count()).select_from(cls))
        for cls in [Fixture, Prediction, Quote, Publication]
    ]
    assert first.fetched_at == stamp


def test_filter_validation_and_empty(client):
    for query in [
        "min_odds=3&max_odds=2",
        "min_probability=2",
        "min_odds=nan",
        "period=custom",
        "page_size=999",
        "start=2026-01-01T00:00:00Z",
    ]:
        assert client.get("/api/research?" + query).status_code == 422, query
    result = client.get("/api/research?min_odds=99&max_odds=100").json()
    assert result["total"] == 0 and result["items"] == []
    result = client.get("/api/research?target=2&tolerance=0.1").json()
    assert all(abs(x["odds"] - 2) <= 0.1 + 1e-9 for x in result["items"])


def test_stale_exclusion_and_kickoff(db, monkeypatch):
    monkeypatch.setattr("app.research.now", lambda: now() + timedelta(minutes=20))
    assert search(db, Filters())["total"] > 0
    assert search(db, Filters(sort="ev"))["total"] == 0
    assert search(db, Filters(positive_ev=True))["total"] == 0
    assert search(db, Filters(fresh_only=True))["total"] == 0
    fixture = db.scalar(select(Fixture).where(Fixture.status == "scheduled"))
    fixture.status = "postponed"
    db.commit()
    assert not any(
        x["fixture_id"] == fixture.id for x in search(db, Filters(page_size=48))["items"]
    )
    fixture.status = "scheduled"
    fixture.kickoff = now() - timedelta(seconds=1)
    db.commit()
    assert not any(
        x["fixture_id"] == fixture.id for x in search(db, Filters(page_size=48))["items"]
    )


def test_mapping_rejects_ambiguity(db):
    f = db.scalar(select(Fixture).where(Fixture.status == "scheduled"))
    e = {
        "home_team": "A",
        "away_team": "B",
        "sport_key": settings.odds_sport,
        "commence_time": f.kickoff.isoformat(),
    }
    names = {"a": f.home_id, "b": f.away_id}
    assert match_fixture(e, [f], names, {}) == f
    assert match_fixture(e, [f, f], names, {}) is None
    e["home_team"] = "Unreviewed alias"
    assert match_fixture(e, [f], names, {}) is None


def test_quota_and_missing_credentials(db, monkeypatch):
    with pytest.raises(ProviderUnavailable, match="budget"):
        ProviderClient(db, "test", 0).get("https://example.invalid", {})
    monkeypatch.setattr(settings, "api_football_key", "")
    monkeypatch.setattr(settings, "odds_api_key", "")
    with pytest.raises(ProviderUnavailable):
        APIFootball(db).fixtures()
    with pytest.raises(ProviderUnavailable):
        TheOddsAPI(db).odds()


def test_append_only(db):
    p = db.scalar(select(Prediction))
    p.quality = "Insufficient"
    with pytest.raises(ValueError, match="append-only"):
        db.commit()
    db.rollback()


def test_settlement_corrections_idempotent(db):
    f = db.scalar(select(Fixture).where(Fixture.status == "scheduled"))
    f.status = "finished"
    f.home_goals = 1
    f.away_goals = 0
    db.commit()
    settle(db)
    db.commit()
    count = db.scalar(select(func.count()).select_from(Settlement))
    assert count > 0
    settle(db)
    db.commit()
    assert db.scalar(select(func.count()).select_from(Settlement)) == count
    f.home_goals = 0
    f.away_goals = 1
    db.commit()
    settle(db)
    db.commit()
    assert db.scalar(select(func.count()).select_from(Settlement)) == 2 * count
    settle(db)
    db.commit()
    assert db.scalar(select(func.count()).select_from(Settlement)) == 2 * count
    assert db.scalar(select(Settlement).where(Settlement.supersedes_id.is_not(None)))


def test_mode_separation(db, monkeypatch):
    monkeypatch.setattr(settings, "app_data_mode", "live")
    assert search(db, Filters())["total"] == 0


def test_provider_timeout_retry_and_error_fallback(db, monkeypatch):
    import httpx

    calls = []

    class Broken:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, *args, **kwargs):
            calls.append(1)
            raise httpx.ReadTimeout("private provider URL must not escape")

    monkeypatch.setattr("app.providers.httpx.Client", Broken)
    monkeypatch.setattr("app.providers.time.sleep", lambda _: None)
    with pytest.raises(ProviderUnavailable, match="timeout"):
        ProviderClient(db, "failure-test", 3).get("https://fixed.example", {})
    assert len(calls) == 3


def test_changed_kickoff_requires_new_prediction(client, db):
    selection = client.get("/api/predictions").json()["items"][0]
    f = db.get(Fixture, selection["fixture_id"])
    f.kickoff = f.kickoff + timedelta(hours=1)
    db.commit()
    assert not any(r["fixture_id"] == f.id for r in search(db, Filters(page_size=48))["items"])


def test_no_future_results_influence_model(db):
    from app.model import predict

    fixtures = list(db.scalars(select(Fixture)))
    f = next(f for f in fixtures if f.status == "scheduled")
    cutoff = now()
    first = predict(fixtures, f.home_id, f.away_id, cutoff)
    f.status = "finished"
    f.home_goals = 20
    f.away_goals = 0
    f.result_available_at = cutoff + timedelta(days=1)
    second = predict(fixtures, f.home_id, f.away_id, cutoff)
    assert first == second


def test_target_finds_a_real_quote_even_if_another_book_is_higher(db):
    result = search(db, Filters(target=1.85, tolerance=0, market="totals"))
    assert result["total"] > 0
    assert all(r["odds"] == 1.85 for r in result["items"])
    assert all(r["bookmaker"] == "Demo Exchange" for r in result["items"])


def test_live_adapter_contract_reuses_quotes_for_new_prediction_versions(db, monkeypatch):
    from app.providers import DemoFootball, DemoOdds

    anchor = now()
    records = DemoFootball(anchor).fixtures()
    events = DemoOdds(records, anchor).odds()
    monkeypatch.setattr(settings, "app_data_mode", "live")
    monkeypatch.setattr(settings, "live_retention_approved", True)
    monkeypatch.setattr(APIFootball, "fixtures", lambda self: records)
    monkeypatch.setattr(TheOddsAPI, "odds", lambda self: events)
    monkeypatch.setattr(TheOddsAPI, "european_events", lambda self: [])
    monkeypatch.setattr(settings, "odds_bookmaker_key", "demo-exchange")
    ingest(db)
    quote_count = db.scalar(select(func.count()).select_from(Quote).where(Quote.mode == "live"))
    assert quote_count == 219  # Core markets plus the bounded sample of imported extended prices.
    old = db.scalar(select(Prediction).where(Prediction.mode == "live"))
    revision = Prediction(
        fixture_id=old.fixture_id,
        model_id=old.model_id,
        input_cutoff=now(),
        history_fetched_at=old.history_fetched_at,
        fixture_kickoff=old.fixture_kickoff,
        probabilities=old.probabilities,
        factors=old.factors,
        input_hash="reviewed-new-input-revision",
        quality=old.quality,
        mode="live",
    )
    db.add(revision)
    db.commit()
    ingest(db)
    assert (
        db.scalar(select(func.count()).select_from(Quote).where(Quote.mode == "live"))
        == quote_count
    )
    assert (
        db.scalar(
            select(func.count())
            .select_from(Publication)
            .where(Publication.prediction_id == revision.id)
        )
        == 7  # Includes the configured bookmaker's BTTS selections.
    )
    assert db.scalar(select(Publication).where(Publication.prediction_id == old.id)) is not None
