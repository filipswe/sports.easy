"""Short, market-specific explanations derived only from saved model inputs."""

import math


def pick_reason(prediction, market, outcome, probability, home, away, alternatives):
    factors = prediction.factors
    h, a = factors["home_rate"], factors["away_rate"]
    leading = max(alternatives, key=alternatives.get)
    favors = probability >= max(alternatives.values()) - 1e-10
    signals = [{"label": "Expected goals", "value": f"{home} {h:.1f} · {away} {a:.1f}"}]
    for side, name in [("home", home), ("away", away)]:
        recent = factors.get("recent_" + side)
        if recent and recent["matches"]:
            signals.append(
                {
                    "label": f"{name} · last {recent['matches']}",
                    "value": f"{recent['wins']} wins · {recent['scored']} scored · {recent['conceded']} conceded",
                }
            )
    if market == "1x2":
        if outcome == "draw":
            summary = f"The teams are projected to score {h:.1f} and {a:.1f} goals. The score model puts a draw at {probability:.0%}, reflecting how often those goal ranges finish level."
        else:
            name, rate, opponent, other = (
                (home, h, away, a) if outcome == "home" else (away, a, home, h)
            )
            comparison = "higher" if rate > other else "lower" if rate < other else "similar"
            summary = f"{name}'s projected {rate:.1f} goals are {comparison} than {opponent}'s {other:.1f}. Those attack and defence estimates put a {name} win at {probability:.0%}."
        if not favors:
            preferred = {"home": f"{home} to win", "away": f"{away} to win", "draw": "a draw"}[
                leading
            ]
            summary += f" The model's leading result is {preferred}, rather than this selection."
    elif market == "btts":
        zero_h, zero_a = math.exp(-h), math.exp(-a)
        signals.append(
            {
                "label": "Chance of not scoring",
                "value": f"{home} {zero_h:.0%} · {away} {zero_a:.0%}",
            }
        )
        summary = (
            f"Both teams have scoring potential in the goal model: {h:.1f} expected goals for {home} and {a:.1f} for {away}. The chance of both scoring is {probability:.0%}."
            if outcome == "yes"
            else f"The model gives {home} a {zero_h:.0%} chance of not scoring and {away} a {zero_a:.0%} chance. At least one blank is estimated at {probability:.0%}."
        )
    elif market == "double_chance":
        labels = {
            "1x": f"{home} winning or drawing",
            "x2": f"{away} winning or drawing",
            "12": "either team winning",
        }
        summary = f"This pick combines the score model's probabilities of {labels[outcome]}, giving {probability:.0%}. It loses in the remaining {1 - probability:.0%} of modeled results."
    elif market == "correct_score":
        if outcome == "other":
            summary = f"Scores outside the displayed 0–4 grid make up {probability:.0%} of the model's distribution, based on expected goals of {h:.1f} and {a:.1f}."
        else:
            hg, ag = outcome.split("-")
            summary = f"Expected goals of {h:.1f} for {home} and {a:.1f} for {away} give a {hg}–{ag} score a {probability:.0%} chance. A likely exact score can still be individually unlikely."
    else:
        line = 2.5 if market == "totals" else float(market.split("_")[-1])
        prefix, expected = "the match", h + a
        if market.startswith("half_"):
            half = factors.get("first_half")
            if not half:
                return None
            expected = half["home_rate"] + half["away_rate"]
            prefix = "the first half"
            signals[0] = {
                "label": "First-half expected goals",
                "value": f"{home} {half['home_rate']:.1f} · {away} {half['away_rate']:.1f}",
            }
            signals = [signals[0]]  # Full-time form is not presented as half-time evidence.
        elif market.startswith("home_"):
            expected, prefix = h, home
        elif market.startswith("away_"):
            expected, prefix = a, away
        summary = f"The model expects {expected:.1f} goals from {prefix}. Summing the possible goal counts gives {outcome} {line:g} goals a {probability:.0%} chance."
    if market != "1x2" and not favors:
        summary += " Another outcome in this market has a higher model chance."
    return {
        "summary": summary,
        "signals": signals,
        "model_favors": favors,
        "heading": "Why the model favors this pick"
        if favors
        else "Why the model is less convinced",
        "caution": "Based on past goals and opponents. Injuries and confirmed lineups are not included.",
    }
