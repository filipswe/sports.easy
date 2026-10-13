# Model methodology

`backend/app/model.py` is the reference implementation. **The baseline is unvalidated.** Demo history is synthetic and cannot demonstrate real-world predictive skill.

For team i hosting j:

```text
log λ_home = intercept + home_advantage + attack[i] + defence[j]
log λ_away = intercept + attack[j] + defence[i]
weight(match) = exp(−log(2) × age_days / 180)
```

The fit minimizes weighted Poisson negative log likelihood with L2 penalties (10 on each team parameter, 3 on home advantage) through 180 gradient steps. Attack and opponent defence are jointly fitted, so opponent strength enters the baseline directly. Shrinkage moderates sparse teams; it does not justify predictions without history. At least 40 eligible league results and eight appearances per team are required. Log rates are bounded to [-3,2] for numerical stability; this is a baseline implementation choice, not a validated football law.

Only final regulation-time scores with kickoff **and first recorded result availability before the prediction cutoff** enter training. A future score or later-arriving corrected result cannot enter an earlier prediction. The initial live bulk import deliberately marks result availability at fetch time. Exact historical availability reconstruction is not implemented. The synthetic adapter records explicit synthetic availability two hours after its synthetic fixture.

Independent Poisson distributions are expanded until missing marginal tail mass is below 1e-12 (maximum 80 grid entries), then joint mass is normalized. 1X2, over/under 2.5 and BTTS are sums over this single grid. Their mutually exclusive outcomes sum to one. No-vig comparisons require complete same-source groups; a model's fair price is different from no-vig bookmaker probabilities.

## Evaluation

Run `python -m app.cli evaluate` from backend after ingestion. The first 60% of chronological data seeds training, the next 20% is validation, and the final 20% is test. Within validation/test, training expands using only eligible earlier records. Hyperparameters remain fixed; neither validation nor test outcomes select a calibration method. No fitted calibration is claimed.

Brier and log loss are **binary scores averaged over market outcomes**, not multiclass Brier sums. Calibration bins are [0,.1), …, [.9,1]. The report includes fixture counts and outcome sample sizes, market breakdowns, and an expanding historical outcome-frequency baseline with additive smoothing. These are one-league results. Calibration data remains exposed in the API. Correlated outcomes must not be interpreted as independent fixtures.

No historical odds are bundled. Accordingly there is no historical bookmaker baseline, historical ROI, or claim of beating prices. The official recommendation archive reports each recommended pick’s original quote, frozen before kickoff, and separates all demo records through mode constraints. Cancelled/abandoned fixtures are void under the research policy; postponed fixtures await a later verified result. Bookmaker settlement rules can differ.

## Limits

The independent-score assumption misses low-score dependence, red cards and tactical effects. Goal rates can drift. No xG, injury, lineup, travel, coaching or player features are used. Recent form shown on screen is contextual output derived from the same eligible results, not a separate hidden model. Missing or stale inputs reduce the published coverage-quality indicator; it is never an error bar.

Prediction objects are immutable. However, source fixture history is mutable and only the input hash, cutoff and fitted outputs are retained; storing full versioned training datasets for exact replay after corrections is still needed for a rigorous long-term model registry. The portfolio baseline should not be marketed as a validated betting system.

## Expanded markets and parlays

Version poisson-v1.1 fits a separate first-half model from recorded half-time scores. It uses the same past-only availability cutoff, regularization and minimum samples as the full-time fit. The three first-half goal lines are unavailable if those samples are missing. Extended full-time totals and team totals use analytic Poisson probabilities; correct scores include a remaining-score bucket so the distribution sums to one. Double-chance outcomes overlap and are not a mutually exclusive distribution.

Parlays use one selection per fixture and reject repeated clubs. Combined probability is the product of leg probabilities under the independence approximation, not a calibrated joint estimate. Prices are multiplied from one common sportsbook only, or from explicitly user-entered prices for every leg. Suggestions search priced outcomes with a bounded beam; the available source coverage and search bounds limit what can be returned. Expanded model estimates do not imply that those sportsbook prices exist.
