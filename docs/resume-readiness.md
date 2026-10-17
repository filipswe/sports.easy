# Resume readiness checklist

Assessed on 17 October 2026. This is a personal portfolio project. You can already list it as a project in development, provided you understand the implementation and describe your own work accurately. A polished demonstration and a reliable refresh path are the main remaining steps before presenting it as a finished live project.

## Already demonstrated in the repository

- [x] React/Next.js interface with TypeScript, responsive styling, match browsing, analysis, saved picks and a parlay builder.
- [x] Python/FastAPI backend with typed requests and interactive API documentation.
- [x] SQLAlchemy persistence, Alembic migrations, local SQLite and deployed Neon PostgreSQL.
- [x] Real fixture/odds provider adapters, private server credentials, quotas and retry handling.
- [x] Statistical Poisson model, separate market-based European estimates, and optional grounded Groq analysis.
- [x] Immutable original predictions, prices, official recommendations and settlement corrections; losses remain in the archive.
- [x] Backend tests, browser regressions, lint, TypeScript, production builds and GitHub Actions checks.
- [x] Real cached club logos covering the current local dataset, with provider-image and initials fallbacks. These latest changes have not been promoted to the permanent website.

## Complete before calling the live demonstration finished

- [ ] **Fix the odds observation timestamp issue.** A slow ingestion run can reject newly fetched prices against the job's earlier start time. Add a slow-job regression and verify that fresh observations produce visible matches. See [the investigation and evidence](team-logo-verification.md).
- [ ] **Demonstrate repeatable result refresh.** Confirm a later completed match moves from pending to won/lost/void without rewriting the original pick. The manual hosted update below proves settlement once; it does not prove the scheduler runs automatically.
- [ ] **Choose one refresh process.** Configure and verify the scheduled workflow if the demo promises current data. Coordinate local/hosted quota usage and test timeout recovery. A documented manual refresh is acceptable for a clearly labelled personal demonstration.
- [ ] **Align the demonstration with the code.** Deliberately promote a reviewed commit or record a reproducible local demonstration. Record its SHA. A Git push can create a Vercel preview; it does not establish that the permanent website runs that commit.
- [ ] **Run CI on that exact commit.** Local checks and historical green checks are useful evidence; new unpushed commits do not have GitHub check results yet.
- [ ] **Smoke-test the complete core path.** Home → chronological matches → market/goal line → analysis → parlay → save/reopen → Performance. Include mobile, an empty result set and a failed network request. Verify actual image loading and that missing odds are never fabricated.
- [ ] **Verify account email if showing accounts.** Test a controlled registration, verification and password reset through the chosen deployment. SMTP authentication alone does not prove delivery. Keep delivery tokens private.
- [ ] **Rotate previously shared credentials.** Replace secrets shared in chat, keep local settings ignored, and confirm no secret appears in Git history, screenshots or the browser bundle. Update hosting secrets privately after rotation.
- [ ] **Package the project.** Add current screenshots, a short demo video/GIF, one clear setup path, an architecture diagram and a concise limitations section. A reviewer should be able to understand and run it without this conversation.
- [ ] **Be able to explain it yourself.** Trace one request through the UI/API/database; explain a schema relationship and migration, probability versus odds, parlay multiplication and its independence assumption, provider failures, authentication, and one meaningful test. Explain a bug you diagnosed and the tradeoff behind its fix. See the [learning guide](portfolio-guide.md).

## Optional expansion

- [ ] Add a larger versioned historical dataset, calibration plots and measured comparison with a bookmaker baseline. This becomes necessary before claiming predictive accuracy, profitability or an advantage over prices; five results are insufficient.
- [ ] Optimize database queries and ingestion time after measuring bottlenecks.
- [ ] Add richer data such as injuries, lineups and xG if an entitled feed supports them.
- [ ] Add monitoring, load tests, trusted hosted client identity and more extensive backup/restore exercises as the project's operational scope grows.
- [ ] Add a custom domain or further product features if they help the demonstration. Payments, subscriptions, monetization and additional leagues are optional.

## Results update evidence

The hosted database initially contained five official Champions League picks, all pending. A bounded verified-score refresh settled all five while retaining their original publications and prices. Four won and one lost. These are the originally recorded selections, not retrospective replacements chosen after seeing the scores.

| Match                            | Verified regulation score | Original pick      | Outcome |
| -------------------------------- | ------------------------- | ------------------ | ------- |
| Roma – Real Madrid               | 3–4                       | Real Madrid to win | Won     |
| Aston Villa – Fenerbahce         | 6–0                       | Aston Villa to win | Won     |
| Man City – PSG                   | 2–4                       | Man City to win    | Lost    |
| Real Betis – Porto               | 3–2                       | Real Betis to win  | Won     |
| ŠK Slovan Bratislava – Stuttgart | 0–3                       | Stuttgart to win   | Won     |

Source: the configured Odds API score endpoint, checked against recorded event IDs, teams, kickoff and the verified regulation-only competition phase. Read the public [Performance page](https://sports-easy-y6m1.vercel.app/performance). This small forward-recorded sample is not evidence of calibrated probabilities or future returns.

Both the backend and website Performance endpoints returned HTTP 200 with five tracked picks, five settled and four wins after this update. A separate five-league football-data.org refresh checked nine recent fixtures with stored predictions: all nine changed in the older hosted cache and two changed in the local cache. The local archive subsequently contained 13 wins, five losses and two pending picks; it is a separate database and is not the hosted track record. No missing score was invented, and no new retrospective official pick was created.

Validation: three targeted tests passed for score identity/corrections, cached score requests and preserving original official picks in Performance. The documentation received a dedicated review with no confirmed findings. No application code changed for this update.

## Suggested resume wording

“Developed a football research application using Next.js, React, TypeScript, FastAPI, SQLAlchemy and PostgreSQL; integrated fixture/odds APIs, statistical predictions and grounded AI analysis, with automated backend/browser tests and Docker-based local development.”

Use wording that matches your contribution and understanding, and be candid about AI assistance when discussing the work. Add deployment or performance claims only after verifying them. The strongest interview story is a feature you can explain, a real bug you fixed, and a test showing the intended behavior.
