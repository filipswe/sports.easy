import math

import pytest
from app.db import now
from app.ingestion import settle
from app.matchday import markets
from app.models import Fixture, Prediction, Recommendation
from app.picks import publish_recommendations
from conftest import mutate
from sqlalchemy import select


def test_catalog_is_coherent_and_halves_use_recorded_data(client, db):
    response = client.get("/api/matchday")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 60
    assert all(m["home_logo"] and m["away_logo"] for m in items)
    assert {
        p["bookmaker"]
        for m in items
        for market in m["markets"]
        for p in market["picks"]
        if p["odds"]
    } == {"Demo Sportsbook"}
    catalog = {m["key"]: m["picks"] for m in items[0]["markets"]}
    for key in ["1x2", "btts", "totals", "half_totals_0.5", "home_goals_1.5", "correct_score"]:
        assert sum(p["probability"] for p in catalog[key]) == pytest.approx(1)
    assert catalog["totals_0.5"][0]["probability"] > catalog["totals_4.5"][0]["probability"]
    prediction = db.scalar(select(Prediction))
    assert prediction.factors["first_half"]["league_sample"] == 264
    # A v1 prediction, or a feed with no half-time scores, must not invent first-half probabilities.
    from types import SimpleNamespace

    missing = SimpleNamespace(
        probabilities=prediction.probabilities, factors={**prediction.factors, "first_half": None}
    )
    assert all(not m["outcomes"] for m in markets(missing) if m["group"] == "First half")


def test_official_picks_freeze_and_performance_counts_only_them(client, db):
    items = client.get("/api/recommendations").json()["items"]
    assert len(items) == 5
    assert len({p["fixture_id"] for p in items}) == 5
    assert [p["kickoff"] for p in items] == sorted(p["kickoff"] for p in items)
    from datetime import datetime, timedelta

    assert datetime.fromisoformat(items[-1]["kickoff"]) - datetime.fromisoformat(
        items[0]["kickoff"]
    ) < timedelta(hours=24)
    performance = client.get("/api/performance").json()
    assert performance["count"] == 5 and performance["settled"] == 0
    assert performance["win_rate"] is None
    original = {p["id"] for p in performance["archive"]}
    publish_recommendations(db)
    db.commit()
    assert {p["id"] for p in client.get("/api/performance").json()["archive"]} == original
    f = db.get(Fixture, items[0]["fixture_id"])
    f.status, f.home_goals, f.away_goals = "finished", 3, 1
    db.commit()
    settle(db)
    db.commit()
    performance = client.get("/api/performance").json()
    assert performance["count"] == 5 and performance["settled"] == 1
    assert {p["id"] for p in performance["archive"]} == original
    record = db.scalar(select(Recommendation))
    record.policy = "retroactive"
    with pytest.raises(ValueError, match="append-only"):
        db.commit()
    db.rollback()


def independent_legs(client):
    matches = client.get("/api/matchday").json()["items"]
    teams, legs = set(), []
    for m in matches:
        if {m["home"], m["away"]} & teams:
            continue
        teams.update([m["home"], m["away"]])
        legs.append({"fixture_id": m["id"], "market": "1x2", "outcome": "home"})
        if len(legs) == 3:
            return legs


def test_parlay_math_prices_and_untrusted_probabilities(client):
    legs = independent_legs(client)
    response = mutate(
        client,
        "/api/parlays/analyze",
        {"legs": [{**leg, "user_odds": 2, "probability": 1} for leg in legs]},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["combined_odds"] == 8
    assert 0 < result["probability"] < 1
    assert result["probability"] == pytest.approx(
        math.prod(leg["probability"] for leg in result["legs"])
    )
    assert result["failure_probability"] == pytest.approx(1 - result["probability"])
    assert result["odds_basis"] == "Your entered prices"


def test_reject_correlated_invalid_and_started_legs(client, db):
    legs = independent_legs(client)
    for body in [
        {"legs": []},
        {"legs": [legs[0], legs[0]]},
        {"legs": [{**legs[0], "market": "imaginary"}]},
        {"legs": [{**legs[0], "user_odds": -1}]},
    ]:
        assert mutate(client, "/api/parlays/analyze", body).status_code == 422
    matches = client.get("/api/matchday").json()["items"]
    first = matches[0]
    overlap = next(
        m for m in matches[1:] if {m["home"], m["away"]} & {first["home"], first["away"]}
    )
    assert (
        mutate(
            client,
            "/api/parlays/analyze",
            {"legs": [legs[0], {"fixture_id": overlap["id"], "market": "1x2", "outcome": "home"}]},
        ).status_code
        == 422
    )
    f = db.get(Fixture, legs[0]["fixture_id"])
    f.kickoff = now()
    db.commit()
    assert mutate(client, "/api/parlays/analyze", {"legs": legs}).status_code == 409


def test_unquoted_picks_are_analyzable_without_fake_prices(client):
    legs = [
        {**leg, "market": "correct_score", "outcome": "1-0"} for leg in independent_legs(client)
    ]
    response = mutate(client, "/api/parlays/analyze", {"legs": legs})
    assert response.status_code == 200
    data = response.json()
    assert data["combined_odds"] is None
    assert data["prices"] == []
    assert 0 < data["probability"] < 1


def test_suggestions_respect_range_and_do_not_invent_matching_odds(client):
    response = client.get("/api/parlays/suggestions?legs=3&min_odds=6&max_odds=12")
    assert response.status_code == 200
    data = response.json()["items"]
    assert data
    for item in data:
        assert len(item["legs"]) == 3
        assert len({p["fixture_id"] for p in item["legs"]}) == 3
        assert len({p[t] for p in item["legs"] for t in ["home", "away"]}) == 6
        assert 6 <= item["combined_odds"] <= 12
        assert item["combined_odds"] == pytest.approx(
            math.prod(leg["odds"] for leg in item["legs"])
        )
    high = client.get("/api/parlays/suggestions?legs=3&min_odds=50&max_odds=150").json()["items"]
    assert high and all(50 <= p["combined_odds"] <= 150 for p in high)
    assert (
        client.get("/api/parlays/suggestions?legs=2&min_odds=900&max_odds=950").json()["items"]
        == []
    )
    assert client.get("/api/parlays/suggestions?min_odds=10&max_odds=2").status_code == 422


def test_top_five_leagues_have_separate_histories_and_filters(client, db):
    from app.leagues import LEAGUES

    meta = client.get("/api/meta").json()
    assert {league["name"] for league in meta["leagues"]} == {league.name for league in LEAGUES}
    predictions = list(db.scalars(select(Prediction)))
    assert len(predictions) == 60
    assert all(p.factors["league_sample"] == 264 for p in predictions)
    assert all(p.factors["home_sample"] + p.factors["away_sample"] < 264 for p in predictions)
    for league in meta["leagues"]:
        items = client.get("/api/matchday?league=" + league["id"]).json()["items"]
        assert len(items) == 12
        assert all(m["competition"] == league["name"] for m in items)
    # Changing another league's results cannot change this league's prediction.
    from app.model import predict

    target = db.get(Fixture, predictions[0].fixture_id)
    history = list(
        db.scalars(select(Fixture).where(Fixture.competition_id == target.competition_id))
    )
    first = predict(history, target.home_id, target.away_id, now())
    other = db.scalar(
        select(Fixture).where(
            Fixture.competition_id != target.competition_id, Fixture.status == "finished"
        )
    )
    other.home_goals = 99
    second = predict(history, target.home_id, target.away_id, now())
    assert first["probabilities"] == second["probabilities"]


def test_featured_window_excludes_distant_published_picks_without_erasing_them(client, db):
    from datetime import timedelta

    from app.models import Publication, Quote
    from app.picks import recommendation_rows

    original = client.get("/api/recommendations").json()["items"]
    far = db.scalar(
        select(Fixture).where(Fixture.status == "scheduled").order_by(Fixture.kickoff.desc())
    )
    pub = db.scalar(
        select(Publication)
        .join(Quote, Publication.quote_id == Quote.id)
        .where(Quote.fixture_id == far.id)
    )
    db.add(Recommendation(fixture_id=far.id, publication_id=pub.id, policy="legacy-weekly"))
    db.commit()
    items = client.get("/api/recommendations").json()["items"]
    assert {r["id"] for r in items} == {r["id"] for r in original}
    assert far.id not in {r["fixture_id"] for r in items}
    assert far.id in {r["fixture_id"] for r in recommendation_rows(db)}
    # Advancing into another matchday picks the next window, preserving original records.
    at = now() + timedelta(days=2)
    from unittest.mock import patch

    with patch("app.research.now", return_value=at), patch("app.picks.now", return_value=at):
        publish_recommendations(db)
        db.commit()
        later = recommendation_rows(db, upcoming=True)
        assert later and all(r["kickoff"] > at for r in later)
        assert later[-1]["kickoff"] - later[0]["kickoff"] < timedelta(hours=24)
    assert all(db.get(Recommendation, r["recommendation_id"]) for r in original)


def test_all_market_explanations_are_specific_and_do_not_fake_support(client):
    matches = client.get("/api/matchday").json()["items"]
    match = matches[0]
    for market in match["markets"]:
        for pick in market["picks"]:
            analysis = pick["analysis"]
            assert analysis["summary"] and analysis["signals"]
            assert analysis["model_favors"] == (
                pick["probability"] >= max(p["probability"] for p in market["picks"]) - 1e-10
            )
            if market["group"] == "First half":
                assert "first half" in analysis["summary"]
                assert analysis["signals"][0]["label"] == "First-half expected goals"
            if market["key"] == "btts":
                assert any(s["label"] == "Chance of not scoring" for s in analysis["signals"])
    result_market = next(m for m in match["markets"] if m["key"] == "1x2")
    weak = min(result_market["picks"], key=lambda p: p["probability"])
    assert not weak["analysis"]["model_favors"]
    assert "leading result" in weak["analysis"]["summary"]
    assert {s["label"] for s in weak["analysis"]["signals"]} == {
        "Expected goals",
        match["home"] + " · last 5",
        match["away"] + " · last 5",
    }


def test_live_providers_request_every_top_five_league(db, monkeypatch):
    from app.config import settings
    from app.leagues import ALL_COMPETITIONS, LEAGUES
    from app.providers import APIFootball, TheOddsAPI

    monkeypatch.setattr(settings, "api_football_key", "test-only")
    monkeypatch.setattr(settings, "odds_api_key", "test-only")
    football = APIFootball(db)
    calls = []
    football.client.get = lambda url, params, headers: calls.append(params) or {"response": []}
    assert football.fixtures() == []
    assert {c["league"] for c in calls} == {league.id for league in LEAGUES}
    assert len(calls) == 10
    odds = TheOddsAPI(db)
    sports = []
    odds.client.get = lambda url, params, cost: sports.append(url.split("/")[-2]) or []
    assert odds.odds() == []
    assert set(sports) == {league.sport for league in ALL_COMPETITIONS}


def test_worker_refills_featured_vacancies_without_another_ingestion_job(db, monkeypatch):
    from app import worker
    from app.models import Job
    from app.picks import recommendation_rows
    from sqlalchemy import func
    from sqlalchemy.orm import sessionmaker

    monkeypatch.setattr(worker, "engine", db.bind)
    monkeypatch.setattr(worker, "SessionLocal", sessionmaker(bind=db.bind, expire_on_commit=False))
    worker.tick()
    count = db.scalar(select(func.count()).select_from(Job))
    before = recommendation_rows(db, upcoming=True)
    for row in before:
        db.get(Fixture, row["fixture_id"]).status = "postponed"
    db.commit()
    worker.tick()
    after = recommendation_rows(db, upcoming=True)
    assert len(after) == 5
    assert not {r["fixture_id"] for r in before} & {r["fixture_id"] for r in after}
    assert db.scalar(select(func.count()).select_from(Job)) == count
    assert all(db.get(Recommendation, r["recommendation_id"]) for r in before)


def test_stronger_new_pick_enters_shortlist_without_rewriting_old_records(db):
    import copy

    from app.models import Publication, Quote
    from app.picks import featured_window, publish_recommendations, recommendation_rows

    before = recommendation_rows(db, upcoming=True)
    recorded_fixtures = {r["fixture_id"] for r in before}
    rows, _, _ = featured_window(db)
    candidate = next(row for row in rows if row["fixture_id"] not in recorded_fixtures)
    old = db.get(Prediction, candidate["prediction_id"])
    probabilities = copy.deepcopy(old.probabilities)
    probabilities["1x2"] = {"home": 0.99, "draw": 0.005, "away": 0.005}
    revised = Prediction(
        fixture_id=old.fixture_id,
        model_id=old.model_id,
        input_cutoff=old.input_cutoff,
        history_fetched_at=old.history_fetched_at,
        fixture_kickoff=old.fixture_kickoff,
        probabilities=probabilities,
        factors=copy.deepcopy(old.factors),
        quality=old.quality,
        mode=old.mode,
        input_hash="stronger-current-input-regression",
    )
    db.add(revised)
    db.flush()
    quote = Quote(
        fixture_id=old.fixture_id,
        bookmaker_id=candidate["bookmaker_id"],
        market="1x2",
        outcome="home",
        price=1.03,
        snapshot_key="stronger-current-price-regression",
        mode=old.mode,
        source_updated_at=now(),
    )
    db.add(quote)
    db.flush()
    db.add(Publication(prediction_id=revised.id, quote_id=quote.id))
    db.commit()
    publish_recommendations(db)
    db.commit()
    after = recommendation_rows(db, upcoming=True)
    assert len(after) == 5
    assert any(r["fixture_id"] == old.fixture_id and r["probability"] == 0.99 for r in after)
    archive = {r["recommendation_id"]: r for r in recommendation_rows(db)}
    for original in before:
        retained = archive[original["recommendation_id"]]
        assert retained["id"] == original["id"]
        assert retained["probability"] == original["probability"]
        assert retained["odds"] == original["odds"]
