from datetime import timedelta

import pytest
from app.config import settings
from app.db import now
from app.ingestion import settle, store_odds
from app.matchday import current_quotes
from app.model import market_probabilities, no_vig, outcome_won
from app.models import Competition, Fixture, Prediction, Publication, Quote, Settlement, Team
from app.providers import ProviderClient
from conftest import mutate
from sqlalchemy import select


def live_event(db, monkeypatch):
    monkeypatch.setattr(settings, "app_data_mode", "live")
    monkeypatch.setattr(settings, "live_retention_approved", True)
    monkeypatch.setattr(settings, "odds_bookmaker_key", "pinnacle")
    fixture = db.scalar(select(Fixture).where(Fixture.status == "scheduled"))
    fixture.mode, fixture.provider_id = "live", "the-odds-api:verified-detail"
    comp = db.get(Competition, fixture.competition_id)
    comp.mode, comp.provider_id = "live", "the-odds-api:2:2026"
    db.commit()
    event = {
        "id": "verified-detail",
        "sport_key": "soccer_uefa_champs_league",
        "commence_time": fixture.kickoff.isoformat(),
        "home_team": db.get(Team, fixture.home_id).name,
        "away_team": db.get(Team, fixture.away_id).name,
    }
    event["bookmakers"] = [
        {
            "key": "pinnacle",
            "title": "Pinnacle",
            "last_update": now().isoformat(),
            "markets": [
                {
                    "key": "alternate_totals",
                    "outcomes": [
                        {"name": "Over", "point": 1.5, "price": 1.4},
                        {"name": "Under", "point": 1.5, "price": 3},
                        {"name": "Over", "point": 3.5, "price": 2.9},
                        {"name": "Under", "point": 3.5, "price": 1.4},
                        {"name": "Over", "point": 3.25, "price": 2.2},
                    ],
                },
                {
                    "key": "btts",
                    "outcomes": [{"name": "Yes", "price": 1.6}, {"name": "No", "price": 2.1}],
                },
                {
                    "key": "double_chance",
                    "outcomes": [
                        {"name": event["home_team"] + " or Draw", "price": 1.3},
                        {"name": event["away_team"] + " or Draw", "price": 1.8},
                        {"name": event["home_team"] + " or " + event["away_team"], "price": 1.2},
                    ],
                },
            ],
        }
    ]
    return fixture, event


def test_real_extended_outcomes_keep_lines_and_prices_and_abstain_on_missing_model(db, monkeypatch):
    fixture, event = live_event(db, monkeypatch)
    assert store_odds(db, [event], observed=True) == 0
    db.commit()
    rows = current_quotes(db, fixture.id)
    assert len(rows) == 9
    assert {r["market"] for r in rows} == {"totals_1.5", "totals_3.5", "btts", "double_chance"}
    assert all(row["probability"] is None for row in rows)
    assert (
        next(r for r in rows if r["market"] == "totals_1.5" and r["outcome"] == "over")["odds"]
        == 1.4
    )
    assert {r["outcome"] for r in rows if r["market"] == "double_chance"} == {"1x", "x2", "12"}
    swapped = {**event, "home_team": event["away_team"], "away_team": event["home_team"]}
    assert store_odds(db, [swapped], observed=True) == 1
    assert (
        no_vig(
            list(db.scalars(select(Quote).where(Quote.market == "double_chance"))), "double_chance"
        )
        is None
    )


def test_detail_prices_are_csrf_protected_cached_and_not_invalidated_by_base_sweeps(
    client, db, monkeypatch
):
    fixture, event = live_event(db, monkeypatch)
    calls = []
    monkeypatch.setattr(
        ProviderClient, "get", lambda self, url, params, cost=1: calls.append((url, cost)) or event
    )
    assert client.post("/api/prices/refresh", json={"fixture_id": fixture.id}).status_code == 403
    first = mutate(client, "/api/prices/refresh", {"fixture_id": fixture.id})
    assert first.status_code == 200 and first.json()["fetched_matches"] == 1
    second = mutate(client, "/api/prices/refresh", {"fixture_id": fixture.id})
    assert second.json()["cached_matches"] == 1 and len(calls) == 1
    assert calls[0][1] == 4
    from app.models import IngestionRun

    db.add(
        IngestionRun(
            provider=f"odds-refresh:{settings.odds_region}:pinnacle",
            status="complete",
            created_at=now() + timedelta(seconds=1),
            detail={},
        )
    )
    db.commit()
    assert len(current_quotes(db, fixture.id)) == 9


def test_first_half_settlements_wait_for_half_scores_and_revise_corrections(db):
    record = db.execute(
        select(Publication, Quote)
        .join(Quote)
        .where(Quote.market == "half_totals_1.5", Quote.outcome == "under")
    ).first()
    publication, quote = record
    fixture = db.get(Fixture, quote.fixture_id)
    fixture.status, fixture.home_goals, fixture.away_goals = "finished", 3, 1
    fixture.home_half_goals = fixture.away_half_goals = None
    db.commit()
    settle(db)
    db.commit()
    assert db.scalar(select(Settlement).where(Settlement.publication_id == publication.id)) is None
    fixture.home_half_goals, fixture.away_half_goals = 1, 0
    db.commit()
    settle(db)
    db.commit()
    first = db.scalar(select(Settlement).where(Settlement.publication_id == publication.id))
    assert first.result == "won"
    fixture.home_half_goals = 2
    db.commit()
    settle(db)
    db.commit()
    last = db.scalar(
        select(Settlement)
        .where(Settlement.publication_id == publication.id)
        .order_by(Settlement.recorded_at.desc())
    )
    assert last.result == "lost" and last.supersedes_id == first.id


def test_derived_probabilities_and_goal_line_settlement_are_coherent(db):
    prediction = db.scalar(select(Prediction))
    for line in (0.5, 1.5, 3.5, 4.5, 9.5):
        probabilities = market_probabilities(prediction, f"totals_{line}")
        assert sum(probabilities.values()) == pytest.approx(1)
        assert outcome_won(f"totals_{line}", "over", 2, 1) is (3 > line)
    assert sum(market_probabilities(prediction, "double_chance").values()) == pytest.approx(2)
    assert market_probabilities(prediction, "totals_3.25") == {}
