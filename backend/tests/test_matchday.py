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
    assert len(items) == 12
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
    assert [p["probability"] for p in items] == sorted(
        [p["probability"] for p in items], reverse=True
    )
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
        {**leg, "market": "half_totals_0.5", "outcome": "over"} for leg in independent_legs(client)
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
    assert (
        client.get("/api/parlays/suggestions?legs=2&min_odds=900&max_odds=950").json()["items"]
        == []
    )
    assert client.get("/api/parlays/suggestions?min_odds=10&max_odds=2").status_code == 422
