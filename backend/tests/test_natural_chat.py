import json
from datetime import timedelta

import httpx
import pytest
from app.chat import ChatInput
from app.chat_resolution import catalog_for, fallback_route, mentioned_matches
from app.config import settings
from app.db import now
from conftest import mutate


def test_natural_chat_resolves_pair_and_reuses_follow_up_context(client, db, monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "")
    row = catalog_for(db)[0]
    question = f"What are the odds for {row['home']} vs {row['away']}?"
    answer = mutate(client, "/api/chat", {"question": question}).json()
    assert answer["fixture_id"] == row["fixture_id"]
    assert answer["source"] == "data" and "Demo Sportsbook" in answer["answer"]
    follow = mutate(
        client,
        "/api/chat",
        {
            "question": "What is their recent form?",
            "context_fixture_id": answer["fixture_id"],
            "previous_questions": [question],
        },
    ).json()
    assert follow["fixture_id"] == row["fixture_id"]
    assert "latest verified results" in follow["answer"]
    unknown = mutate(
        client,
        "/api/chat",
        {
            "question": "What are the odds for Bolton vs Notts County?",
            "context_fixture_id": answer["fixture_id"],
        },
    ).json()
    assert unknown["fixture_id"] is None and "couldn't identify" in unknown["answer"]


def test_natural_chat_uses_exact_requested_goal_line_and_outcome(client, db, monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "")
    row = catalog_for(db)[0]
    body = {"question": f"Odds for over 1.5 in {row['home']} vs {row['away']}?"}
    answer = mutate(client, "/api/chat", body).json()
    assert "Over 1.5 goals" in answer["answer"]
    assert "Under" not in answer["answer"] and "2.5 goals" not in answer["answer"]
    answer = mutate(
        client,
        "/api/chat",
        {"question": f"Odds for first half over 1.5 in {row['home']} vs {row['away']}?"},
    ).json()
    assert "First half: Over 1.5 goals" in answer["answer"]


@pytest.mark.parametrize(
    "question,expected",
    [
        ("Explain BTTS", "both teams score"),
        ("What is double chance?", "home or draw"),
        ("What should I consider for a parlay?", "Every selection must win"),
    ],
)
def test_general_questions_do_not_require_a_match(client, monkeypatch, question, expected):
    monkeypatch.setattr(settings, "groq_api_key", "")
    answer = mutate(client, "/api/chat", {"question": question}).json()
    assert answer["fixture_id"] is None and expected in answer["answer"]


def test_unknown_dates_and_pairings_do_not_reuse_context(db):
    rows = catalog_for(db)
    row = rows[0]
    date = (now() + timedelta(days=30)).date().isoformat()
    body = ChatInput(
        question=f"Odds for {row['home']} on {date}?", context_fixture_id=row["fixture_id"]
    )
    assert fallback_route(db, body, rows).match_index == "none"
    assert mentioned_matches(db, "Arsenal vs Unknown Club", rows) == []
    body = ChatInput(
        question="What are the current odds for Unlisted Club?",
        context_fixture_id=row["fixture_id"],
    )
    assert fallback_route(db, body, rows).match_index == "none"


@pytest.mark.parametrize("invalid", ["wrong-game", "out-of-range", "malformed"])
def test_ai_cannot_substitute_an_unrelated_match_or_return_free_text(
    client, db, monkeypatch, invalid
):
    monkeypatch.setattr(settings, "groq_api_key", "test-only")
    rows = catalog_for(db)
    row = rows[0]
    other = next(
        i
        for i, item in enumerate(rows)
        if not {item["home"], item["away"]} & {row["home"], row["away"]}
    )
    route = {
        "match_index": str(other) if invalid == "wrong-game" else "99999",
        "focus": "price",
        "market": "1x2",
        "outcome": "auto",
        "line": "2.5",
    }

    def post(url, **kwargs):
        schema = kwargs["json"]["response_format"]["json_schema"]["schema"]
        assert schema["additionalProperties"] is False
        assert "none" in schema["properties"]["match_index"]["enum"]
        content = "100% guaranteed free text" if invalid == "malformed" else json.dumps(route)
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={"choices": [{"message": {"content": content}}]},
        )

    monkeypatch.setattr(httpx, "post", post)
    answer = mutate(
        client, "/api/chat", {"question": f"Current odds for {row['home']} vs {row['away']}?"}
    ).json()
    assert answer["source"] == "data" and answer["fixture_id"] == row["fixture_id"]
    assert "guaranteed" not in answer["answer"] and "test-only" not in str(answer)


def test_valid_ai_router_selects_stored_match_only(client, db, monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "test-only")
    row = catalog_for(db)[0]

    def post(url, **kwargs):
        route = {
            "match_index": "0",
            "focus": "summary",
            "market": "1x2",
            "outcome": "home",
            "line": "2.5",
        }
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={"choices": [{"message": {"content": json.dumps(route)}}]},
        )

    monkeypatch.setattr(httpx, "post", post)
    answer = mutate(
        client, "/api/chat", {"question": f"What are the odds for {row['home']} to win?"}
    ).json()
    assert answer["source"] == "ai" and answer["fixture_id"] == row["fixture_id"]
    assert row["home"] + " to win" in answer["answer"]
    assert "estimated" not in answer["answer"]
    assert row["away"] + " to win" not in answer["answer"]


def test_chat_history_is_bounded_and_private(client, monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "")
    assert (
        mutate(
            client, "/api/chat", {"question": "Explain BTTS", "previous_questions": ["x" * 601]}
        ).status_code
        == 422
    )
    assert (
        mutate(
            client, "/api/chat", {"question": "Explain BTTS", "previous_questions": ["a", "b", "c"]}
        ).status_code
        == 422
    )
    assert client.post("/api/chat", json={"question": "Explain BTTS"}).status_code == 403


def test_next_game_uses_earliest_priced_fixture_even_if_ai_selects_later(client, db, monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "test-only")
    rows = catalog_for(db)
    first = rows[0]
    later = next(
        i for i, row in enumerate(rows) if i and first["home"] in (row["home"], row["away"])
    )

    def post(url, **kwargs):
        route = {
            "match_index": str(later),
            "focus": "price",
            "market": "all",
            "outcome": "auto",
            "line": "2.5",
        }
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={"choices": [{"message": {"content": json.dumps(route)}}]},
        )

    monkeypatch.setattr(httpx, "post", post)
    answer = mutate(
        client, "/api/chat", {"question": f"Current odds for {first['home']}'s next game?"}
    ).json()
    assert answer["source"] == "ai" and answer["fixture_id"] == first["fixture_id"]
