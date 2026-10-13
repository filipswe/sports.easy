"""Walk-forward holdout evaluation; never reconstruct historical returns from current prices."""

import math

from sqlalchemy import select

from .config import settings
from .db import utc
from .model import VERSION, outcome_won, predict
from .models import EvaluationRun, Fixture


def metrics(observations):
    if not observations:
        return {"sample_size": 0, "brier": None, "log_loss": None, "calibration": []}
    bins = []
    for low in range(10):
        group = [
            (p, y)
            for p, y in observations
            if low / 10 <= p < (low + 1) / 10 or (low == 9 and p == 1)
        ]
        if group:
            bins.append(
                {
                    "lower": low / 10,
                    "count": len(group),
                    "estimated": sum(p for p, _ in group) / len(group),
                    "observed": sum(y for _, y in group) / len(group),
                }
            )
    return {
        "sample_size": len(observations),
        "brier": sum((p - y) ** 2 for p, y in observations) / len(observations),
        "log_loss": -sum(
            y * math.log(max(1e-12, p)) + (1 - y) * math.log(max(1e-12, 1 - p))
            for p, y in observations
        )
        / len(observations),
        "calibration": bins,
    }


def evaluate(db):
    matches = list(
        db.scalars(
            select(Fixture)
            .where(Fixture.mode == settings.app_data_mode, Fixture.status == "finished")
            .order_by(Fixture.kickoff)
        )
    )
    n = len(matches)
    train_end, validation_end = int(n * 0.6), int(n * 0.8)
    reports = {}
    for label, start, end in [
        ("validation", train_end, validation_end),
        ("test", validation_end, n),
    ]:
        observations = {"1x2": [], "totals": [], "btts": []}
        baseline = {"1x2": [], "totals": [], "btts": []}
        predicted_matches = 0
        for i in range(start, end):
            f = matches[i]
            cutoff = utc(f.kickoff)
            result = predict(matches[:i], f.home_id, f.away_id, cutoff)
            if not result:
                continue
            predicted_matches += 1
            past = [
                x
                for x in matches[:i]
                if x.result_available_at and utc(x.result_available_at) < cutoff
            ]
            for market, outcomes in result["probabilities"].items():
                for outcome, p in outcomes.items():
                    y = int(outcome_won(market, outcome, f.home_goals, f.away_goals))
                    frequency = (
                        1
                        + sum(
                            outcome_won(market, outcome, x.home_goals, x.away_goals) for x in past
                        )
                    ) / (len(past) + len(outcomes))
                    observations[market].append((p, y))
                    baseline[market].append((frequency, y))
        reports[label] = {
            "fixtures": predicted_matches,
            "markets": {m: metrics(v) for m, v in observations.items()},
            "historical_frequency_baseline": {m: metrics(v) for m, v in baseline.items()},
        }
    report = {
        "kind": "synthetic demonstration"
        if settings.app_data_mode == "demo"
        else "chronological backtest",
        "league": settings.league_name,
        "history_count": n,
        "split": "60% initial train / 20% validation / 20% test",
        "method": "Expanding past-only training; fixed hyperparameters; no fitted calibration. Binary outcome-averaged scores.",
        "bookmaker_baseline": None,
        "roi": None,
        "reports": reports,
        "limitation": "Live results first observed after historical kickoff are excluded; archival availability is required for a genuine backtest.",
    }
    db.add(EvaluationRun(mode=settings.app_data_mode, model_id=VERSION, report=report))
    db.commit()
    return report
