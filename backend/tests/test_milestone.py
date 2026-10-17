from datetime import timedelta

import httpx
import pytest
from app.chat import reserve_chat
from app.config import settings
from app.db import now
from app.ingestion import odds_refresh_due, store_odds, upsert_european_events
from app.matchday import current_quotes, match_row, parlay_summary
from app.models import Competition, Fixture, IngestionRun, Quote, QuoteObservation, UsageCounter
from conftest import mutate
from sqlalchemy import func, select


def test_chat_csrf_and_labelled_grounded_fallback(client, monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "")
    fixture = client.get("/api/matchday").json()["items"][0]["id"]
    body = {"fixture_id": fixture, "question": "What are the current odds?"}
    assert client.post("/api/chat", json=body).status_code == 403
    answer = mutate(client, "/api/chat", body).json()
    assert answer["source"] == "data" and "Demo Sportsbook" in answer["answer"]
    assert answer["mode"] == "demo"
    response = mutate(client, "/api/chat", {**body, "question": "x" * 601})
    assert response.status_code == 422
    assert mutate(client, "/api/chat", {**body, "fixture_id": "missing"}).status_code == 404


@pytest.mark.parametrize(
    "content,source",
    [
        ('{"focus":"risk","evidence_ids":["risk"]}', "ai"),
        ('{"focus":"risk","evidence_ids":["invented_100_percent"]}', "data"),
        ("not json", "data"),
    ],
)
def test_ai_can_only_select_existing_facts(client, monkeypatch, content, source):
    monkeypatch.setattr(settings, "groq_api_key", "test-only")

    def post(self, url, **kwargs):
        assert url == "https://api.groq.com/openai/v1/chat/completions"
        assert kwargs["json"]["max_completion_tokens"] <= 800
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={"choices": [{"message": {"content": content}}]},
        )

    monkeypatch.setattr(httpx.Client, "post", post)
    fixture = client.get("/api/matchday").json()["items"][0]["id"]
    answer = mutate(
        client, "/api/chat", {"fixture_id": fixture, "question": "What is the risk?"}
    ).json()
    assert answer["source"] == source
    assert "chance of losing" in answer["answer"]
    assert "invented_100_percent" not in answer["answer"]
    assert "test-only" not in str(answer)


def test_shared_chat_budget_reserves_before_calls_and_rolls_back_partial_attempts(db):
    at = now().replace(second=0, microsecond=0)
    assert reserve_chat(db, "actor", at)
    assert not reserve_chat(db, "different-actor", at)
    assert db.scalar(select(func.count()).select_from(UsageCounter)) == 3
    assert reserve_chat(db, "different-actor", at + timedelta(minutes=1))


def test_cup_real_quotes_nullable_estimates_and_window(db, monkeypatch):
    monkeypatch.setattr(settings, "app_data_mode", "live")
    monkeypatch.setattr(settings, "odds_bookmaker_key", "pinnacle")
    at = now()
    event = {
        "id": "verified-european-event",
        "sport_key": "soccer_uefa_europa_league",
        "commence_time": (at + timedelta(days=10)).isoformat(),
        "home_team": "Arsenal",
        "away_team": "Verified away club",
        "bookmakers": [
            {
                "key": "pinnacle",
                "title": "Pinnacle",
                "last_update": at.isoformat(),
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Arsenal", "price": 2},
                            {"name": "Draw", "price": 3},
                            {"name": "Verified away club", "price": 4},
                        ],
                    }
                ],
            }
        ],
    }
    outside = {**event, "id": "too-far", "commence_time": (at + timedelta(days=15)).isoformat()}
    upsert_european_events(db, [event, outside], at)
    assert store_odds(db, [event], fetched=at, observed=True) == 0
    db.commit()
    quotes = current_quotes(db)
    assert len(quotes) == 3 and all(q["probability"] is None for q in quotes)
    f = db.get(Fixture, quotes[0]["fixture_id"])
    row = match_row(db, f, quotes)
    pick = row["markets"][0]["picks"][0]
    assert pick["odds"] == 2 and pick["probability"] is None
    parlay = parlay_summary([pick])
    assert parlay["combined_odds"] == 2
    assert parlay["probability"] is None and parlay["failure_probability"] is None
    assert db.scalar(select(Fixture).where(Fixture.provider_id == "the-odds-api:too-far")) is None
    assert db.get(Competition, f.competition_id).name == "Europa League"
    # A successful replay records observation but never rewrites the original quote.
    original = db.scalar(select(Quote).where(Quote.fixture_id == f.id))
    stamp = original.fetched_at
    store_odds(db, [event], fetched=at + timedelta(minutes=1), observed=True)
    db.commit()
    assert original.fetched_at == stamp
    assert (
        db.scalar(
            select(func.count())
            .select_from(QuoteObservation)
            .join(Quote)
            .where(Quote.fixture_id == f.id)
        )
        == 6
    )
    upsert_european_events(db, [], at + timedelta(minutes=2))
    db.commit()
    assert not current_quotes(db)


def test_live_browser_hides_unquoted_matches_and_uses_only_selected_book(client, db, monkeypatch):
    fixture = db.scalar(select(Fixture).where(Fixture.status == "scheduled"))
    fixture.mode = "live"
    comp = db.get(Competition, fixture.competition_id)
    comp.mode = "live"
    # Quote assignment is explicit; unquoted fixtures cannot leak through the listing.
    from app.models import Bookmaker

    book = Bookmaker(
        provider_id=f"live:{settings.odds_region}:pinnacle",
        name="Pinnacle",
        region=settings.odds_region,
    )
    db.add(book)
    db.flush()
    quote = Quote(
        fixture_id=fixture.id,
        bookmaker_id=book.id,
        market="1x2",
        outcome="home",
        price=2,
        snapshot_key="real-contract",
        source_updated_at=now(),
        mode="live",
    )
    db.add(quote)
    db.flush()
    db.add(QuoteObservation(quote_id=quote.id, observed_at=now(), fixture_kickoff=fixture.kickoff))
    db.commit()
    monkeypatch.setattr(settings, "app_data_mode", "live")
    monkeypatch.setattr(settings, "odds_bookmaker_key", "pinnacle")
    items = client.get("/api/matchday").json()["items"]
    assert [item["id"] for item in items] == [fixture.id]
    fixture.kickoff = fixture.kickoff + timedelta(days=1)
    db.commit()
    assert client.get("/api/matchday").json()["items"] == []
    monkeypatch.setattr(settings, "odds_bookmaker_key", "missing-book")
    assert client.get("/api/matchday").json()["items"] == []


def test_odds_schedule_does_not_depend_on_fixture_poll(db, monkeypatch):
    at = now()
    monkeypatch.setattr(settings, "poll_seconds", 86400)
    monkeypatch.setattr(settings, "odds_poll_seconds", 259200)
    assert odds_refresh_due(db, at)
    db.add(
        IngestionRun(
            provider=f"odds-refresh:{settings.odds_region}:{settings.odds_bookmaker_key}",
            status="complete",
            created_at=at,
            detail={},
        )
    )
    db.commit()
    assert not odds_refresh_due(db, at + timedelta(days=2))
    assert odds_refresh_due(db, at + timedelta(days=3))


def test_european_outage_does_not_block_domestic_settlement(db, monkeypatch):
    from app.ingestion import ingest
    from app.models import Publication, Settlement
    from app.providers import DemoFootball, DemoOdds, FootballData, ProviderUnavailable, TheOddsAPI

    records = DemoFootball(now()).fixtures()
    events = DemoOdds(records, now()).odds()
    monkeypatch.setattr(settings, "app_data_mode", "live")
    monkeypatch.setattr(settings, "football_provider", "football-data")
    monkeypatch.setattr(settings, "live_retention_approved", True)
    monkeypatch.setattr(settings, "odds_bookmaker_key", "demo-exchange")
    monkeypatch.setattr(FootballData, "fixtures", lambda self: records)
    monkeypatch.setattr(TheOddsAPI, "odds", lambda self: events)
    monkeypatch.setattr(TheOddsAPI, "european_events", lambda self: [])
    ingest(db)
    publication = db.scalar(select(Publication).join(Quote).where(Quote.mode == "live"))
    fixture = db.get(Fixture, db.get(Quote, publication.quote_id).fixture_id)
    item = next(r for r in records if fixture.provider_id == "football-data:" + r["id"])
    item.update(status="finished", home_goals=3, away_goals=1)

    def unavailable(self):
        raise ProviderUnavailable("optional feed unavailable")

    monkeypatch.setattr(TheOddsAPI, "european_events", unavailable)
    ingest(db)
    assert (
        db.scalar(select(Settlement).where(Settlement.publication_id == publication.id)) is not None
    )
    assert (
        db.scalar(
            select(IngestionRun).where(
                IngestionRun.provider == "european-fixtures", IngestionRun.status == "unavailable"
            )
        )
        is not None
    )
