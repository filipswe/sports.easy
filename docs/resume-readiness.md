# Resume readiness checklist

Assessed on 17 October 2026. This is a personal portfolio project. You can already list it as a project in development, provided you understand the implementation and describe your own work accurately. The reproducible demonstration and refresh fixes are now prepared on `feat/resume-ready-demo`. Provider-key rotation remains an owner action; the learning walkthrough is intentionally deferred.

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

- [x] **Fix the odds observation timestamp issue.** Prices now use actual request receipt time. Delayed-ingestion and failure regressions pass; the real-data preview displays priced matches. The PostgreSQL lock also runs outside idle transactions. See [validation evidence](resume-ready-verification.md).
- [x] **Demonstrate repeatable result refresh.** The hosted results update below retained original publications. Settlement/repeated-run/correction regressions and PostgreSQL duplicate-job checks pass. This verifies manual operation and repeatable behavior, not an automatic cloud scheduler.
- [x] **Choose one refresh process.** Use the bounded manual `scripts/run_beta.py refresh` process, with existing cadence, lock and budget guards. The optional cloud schedule stays disabled. Run before a presentation; automatic freshness is not promised.
- [x] **Align the demonstration with the code.** [Screenshots and walkthrough](demo/README.md) record the isolated real-data preview from `a7e796a`. Automatic feature previews are allowed; permanent production deployments were not promoted.
- [x] **Run CI on that exact commit.** GitHub checks on code revision `a7e796a` passed backend tests/PostgreSQL/audit, web lint/types/build/browser tests and secret scanning. The final documentation commit has its own check run linked from the draft PR.
- [x] **Smoke-test the complete core path.** Recorded real-data flow passed with 85 priced matches, 170 loaded logos, goal lines, analysis, parlay save/reload, Performance, chat and mobile. Nine browser regressions also cover empty searches, network retry and initials fallback.
- [x] **Verify account email if showing accounts.** Controlled hosted verification/reset delivery, single-use verification, login and reset session revocation passed. The temporary account was removed; tokens remain private.
- [ ] **Owner: finish provider-key rotation.** Database-owner rotation is complete; private files remain ignored, full-history secret scanning and browser-bundle checks passed. The user confirmed the four provider replacements have not been saved yet. Replace them privately in `.env`, `.env.beta` and backend hosting settings. Never paste replacements into chat.
- [x] **Package the project.** Added six screenshots, a short playable WebM, the Docker sample-data setup, a Mermaid architecture diagram and explicit limitations. See the [demo package](demo/README.md).
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
