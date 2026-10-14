"""Regularized time-weighted Poisson regression. No LLM or prices in the model."""

import math
from collections import Counter

from .db import utc

VERSION = "poisson-v1.2"
MIN_TEAM_MATCHES = 8
MIN_LEAGUE_MATCHES = 40
MARKETS = {"1x2": ["home", "draw", "away"], "totals": ["over", "under"], "btts": ["yes", "no"]}
BANDS = [
    (0.9, "Very high"),
    (0.8, "High"),
    (0.7, "Moderately high"),
    (0.6, "Above-even"),
    (0.5, "Slightly above-even"),
    (0.4, "Below-even"),
    (0.3, "Low"),
    (0, "Very low"),
]


def likelihood(p):
    if not math.isfinite(p) or not 0 <= p <= 1:
        raise ValueError("Probability must be finite and between zero and one")
    return next(label + " estimated likelihood" for floor, label in BANDS if p >= floor)


def value(p, odds):
    if not math.isfinite(odds) or odds <= 1:
        raise ValueError("Decimal odds must exceed 1")
    likelihood(p)
    return {
        "implied_probability": 1 / odds,
        "fair_odds": 1 / p if p else None,
        "estimated_ev": p * odds - 1,
        "failure_probability": 1 - p,
    }


def market_probabilities(prediction, market):
    if market in prediction.probabilities:
        return prediction.probabilities[market]
    if market == "double_chance":
        p = prediction.probabilities["1x2"]
        return {
            "1x": p["home"] + p["draw"],
            "x2": p["away"] + p["draw"],
            "12": p["home"] + p["away"],
        }
    if prediction.factors.get("basis") == "market":
        return {}
    if market.startswith(("totals_", "half_totals_")):
        try:
            line = float(market.rsplit("_", 1)[1])
        except ValueError:
            return {}
        if line not in {n + 0.5 for n in range(10)}:
            return {}
        factors = (
            prediction.factors.get("first_half")
            if market.startswith("half_")
            else prediction.factors
        )
        if not factors:
            return {}
        rate = factors["home_rate"] + factors["away_rate"]
        under = sum(
            math.exp(-rate) * rate**n / math.factorial(n) for n in range(math.floor(line) + 1)
        )
        return {"over": 1 - under, "under": under}
    return {}


def no_vig(quotes, market):
    """Only a complete, single bookmaker/snapshot/fixture/market is admissible."""
    outcomes = MARKETS.get(
        market, ["over", "under"] if market.startswith(("totals_", "half_totals_")) else []
    )
    if not outcomes or len(quotes) != len(outcomes) or {q.outcome for q in quotes} != set(outcomes):
        return None
    if len({(q.bookmaker_id, q.fixture_id, q.snapshot_key, q.market) for q in quotes}) != 1:
        return None
    if any(q.market != market or q.source_updated_at is None for q in quotes):
        return None
    total = sum(1 / float(q.price) for q in quotes)
    return {q.outcome: (1 / float(q.price)) / total for q in quotes}


def score_distribution(home_rate, away_rate):
    def poisson(rate):
        probs = [math.exp(-rate)]
        for k in range(1, 80):
            probs.append(probs[-1] * rate / k)
            if k > rate and 1 - sum(probs) < 1e-12:
                break
        return probs

    hp, ap = poisson(home_rate), poisson(away_rate)
    mass = sum(hp) * sum(ap)
    out = dict.fromkeys(["home", "draw", "away", "over", "under", "yes", "no"], 0.0)
    for h, ph in enumerate(hp):
        for a, pa in enumerate(ap):
            p = ph * pa / mass
            out["home" if h > a else "away" if a > h else "draw"] += p
            out["over" if h + a > 2 else "under"] += p
            out["yes" if h > 0 and a > 0 else "no"] += p
    return {m: {o: out[o] for o in outcomes} for m, outcomes in MARKETS.items()}, 1 - mass


def eligible_history(fixtures, cutoff):
    return [
        f
        for f in fixtures
        if f.status == "finished"
        and f.home_goals is not None
        and f.away_goals is not None
        and f.result_available_at is not None
        and utc(f.kickoff) < cutoff
        and utc(f.result_available_at) < cutoff
    ]


def predict(fixtures, home, away, cutoff, first_half=False, strength_cache=None):
    history = eligible_history(fixtures, cutoff)
    counts = Counter(t for f in history for t in (f.home_id, f.away_id))
    if len(history) < MIN_LEAGUE_MATCHES or min(counts[home], counts[away]) < MIN_TEAM_MATCHES:
        return None
    cache_key = (
        first_half,
        cutoff,
        tuple((f.home_id, f.away_id, f.home_goals, f.away_goals, utc(f.kickoff)) for f in history),
    )
    cached = strength_cache.get(cache_key) if strength_cache is not None else None
    if cached is not None:
        attack, defense, intercept, advantage = cached
    else:
        teams = list(counts)
        attack, defense = dict.fromkeys(teams, 0.0), dict.fromkeys(teams, 0.0)
        intercept, advantage = math.log(1.25), math.log(1.15)
        samples = [
            (f, math.exp(-math.log(2) * (cutoff - utc(f.kickoff)).days / 180)) for f in history
        ]
        total_weight = sum(w for _, w in samples)
        # L2 penalty = ten weighted pseudo-observations per team: shrink sparse teams to league mean.
        for _ in range(180):
            ga, gd = {t: 10 * attack[t] for t in teams}, {t: 10 * defense[t] for t in teams}
            gi, gh = 0.0, 3 * advantage
            for f, w in samples:
                lh = math.exp(
                    max(-3, min(2, intercept + advantage + attack[f.home_id] + defense[f.away_id]))
                )
                la = math.exp(max(-3, min(2, intercept + attack[f.away_id] + defense[f.home_id])))
                eh, ea = w * (lh - f.home_goals), w * (la - f.away_goals)
                ga[f.home_id] += eh
                gd[f.away_id] += eh
                ga[f.away_id] += ea
                gd[f.home_id] += ea
                gi += eh + ea
                gh += eh
            step = 0.12 / total_weight
            for t in teams:
                attack[t] -= step * ga[t]
                defense[t] -= step * gd[t]
            intercept -= step * gi
            advantage -= step * gh
        if strength_cache is not None:
            strength_cache[cache_key] = (attack, defense, intercept, advantage)
    home_rate = math.exp(max(-3, min(2, intercept + advantage + attack[home] + defense[away])))
    away_rate = math.exp(max(-3, min(2, intercept + attack[away] + defense[home])))
    probs, tail = score_distribution(home_rate, away_rate)
    half_factors = None
    if not first_half:
        from types import SimpleNamespace

        halves = [
            SimpleNamespace(
                home_id=f.home_id,
                away_id=f.away_id,
                home_goals=f.home_half_goals,
                away_goals=f.away_half_goals,
                kickoff=f.kickoff,
                status=f.status,
                result_available_at=f.result_available_at,
            )
            for f in history
            if getattr(f, "home_half_goals", None) is not None
            and getattr(f, "away_half_goals", None) is not None
        ]
        half_prediction = predict(
            halves, home, away, cutoff, first_half=True, strength_cache=strength_cache
        )
        half_factors = half_prediction["factors"] if half_prediction else None

    def recent_stats(team):
        rows = sorted(
            (f for f in history if team in (f.home_id, f.away_id)),
            key=lambda f: utc(f.kickoff),
            reverse=True,
        )[:5]
        scored = [f.home_goals if f.home_id == team else f.away_goals for f in rows]
        conceded = [f.away_goals if f.home_id == team else f.home_goals for f in rows]
        return {
            "matches": len(rows),
            "scored": sum(scored),
            "conceded": sum(conceded),
            "wins": sum(h > a for h, a in zip(scored, conceded)),
            "clean_sheets": sum(a == 0 for a in conceded),
        }

    return {
        "probabilities": probs,
        "factors": {
            "first_half": half_factors,
            "recent_home": recent_stats(home),
            "recent_away": recent_stats(away),
            "home_rate": home_rate,
            "away_rate": away_rate,
            "home_sample": counts[home],
            "away_sample": counts[away],
            "league_sample": len(history),
            "tail_mass": tail,
            "home_advantage": math.exp(advantage),
            "half_life_days": 180,
            "missing": ["injuries", "lineups", "xG"],
            "inputs": "historical regulation-time goals only",
        },
        "quality": "Good" if min(counts[home], counts[away]) >= 20 else "Limited",
    }


def outcome_won(market, outcome, h, a):
    if market == "double_chance":
        return {"1x": h >= a, "x2": a >= h, "12": h != a}[outcome]
    if market.startswith(("totals_", "half_totals_")):
        line = float(market.rsplit("_", 1)[1])
        return (h + a > line) if outcome == "over" else (h + a < line)
    actual = {
        "1x2": "home" if h > a else "away" if a > h else "draw",
        "totals": "over" if h + a > 2 else "under",
        "btts": "yes" if h and a else "no",
    }
    return actual[market] == outcome
