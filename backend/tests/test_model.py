import math
from datetime import timedelta
from types import SimpleNamespace

import pytest
from app.db import now
from app.model import (
    eligible_history,
    likelihood,
    no_vig,
    outcome_won,
    predict,
    score_distribution,
    value,
)


@pytest.mark.parametrize(
    "p,label",
    [
        (0, "Very low"),
        (0.299999, "Very low"),
        (0.3, "Low"),
        (0.4, "Below-even"),
        (0.5, "Slightly above-even"),
        (0.6, "Above-even"),
        (0.7, "Moderately high"),
        (0.8, "High"),
        (0.9, "Very high"),
        (1, "Very high"),
    ],
)
def test_boundaries(p, label):
    assert likelihood(p) == label + " estimated likelihood"


@pytest.mark.parametrize("p", [-0.1, 1.1, math.nan, math.inf])
def test_invalid_probability(p):
    with pytest.raises(ValueError):
        likelihood(p)


def test_price_math():
    result = value(0.55, 2)
    assert result["estimated_ev"] == pytest.approx(0.1)
    assert result["implied_probability"] == 0.5
    assert result["fair_odds"] == pytest.approx(1 / 0.55)
    assert result["failure_probability"] == pytest.approx(0.45)


@pytest.mark.parametrize("h,a", [(0.05, 0.05), (1.4, 1.1), (7.38, 7.38), (4, 0.2)])
def test_score_coherence(h, a):
    distributions, tail = score_distribution(h, a)
    assert 0 <= tail < 3e-12
    for values in distributions.values():
        assert sum(values.values()) == pytest.approx(1, abs=1e-10)
        assert all(math.isfinite(p) and 0 <= p <= 1 for p in values.values())


def test_cutoff_excludes_later_availability():
    at = now()
    f = SimpleNamespace(
        status="finished",
        home_goals=1,
        away_goals=0,
        kickoff=at - timedelta(days=1),
        result_available_at=at + timedelta(seconds=1),
    )
    assert eligible_history([f], at) == []
    assert predict([], "home", "away", at) is None


def test_no_vig_rejects_incomplete_and_mixed_groups():
    def q(o, b="a", snapshot="s"):
        return SimpleNamespace(
            outcome=o,
            price=3.2,
            bookmaker_id=b,
            fixture_id="f",
            snapshot_key=snapshot,
            market="1x2",
            source_updated_at=now(),
        )

    assert no_vig([q("home"), q("draw")], "1x2") is None
    assert no_vig([q("home"), q("draw"), q("away", "b")], "1x2") is None
    assert no_vig([q("home"), q("draw"), q("away", snapshot="other")], "1x2") is None
    assert sum(no_vig([q("home"), q("draw"), q("away")], "1x2").values()) == pytest.approx(1)


@pytest.mark.parametrize(
    "market,outcome,h,a,won",
    [
        ("1x2", "draw", 2, 2, True),
        ("1x2", "away", 1, 2, True),
        ("totals", "over", 2, 1, True),
        ("totals", "under", 1, 1, True),
        ("btts", "no", 0, 3, True),
        ("btts", "yes", 0, 0, False),
    ],
)
def test_settlement_rules(market, outcome, h, a, won):
    assert outcome_won(market, outcome, h, a) == won
