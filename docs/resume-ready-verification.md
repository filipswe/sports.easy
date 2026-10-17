# Resume demonstration validation

17 October 2026. Feature branch: `feat/resume-ready-demo`. Draft [PR #2](https://github.com/filipswe/sports.easy/pull/2) targets `feat/production-readiness`; it is a stacked review, not a merge to main or a production promotion.

## Changes and code revisions

- `680c3e6`: observe live odds at actual provider receipt, after slow fixture/model work. Preserve source timestamps and immutable prices; cover delayed ingestion and failed requests.
- `7be4653`: add a locked `refresh-prices` operator recovery and private `scripts/run_beta.py` wrapper with a 20-minute bound, preflight and no database-owner credential forwarding.
- `a7e796a`: hold PostgreSQL session advisory locks in AUTOCOMMIT mode. Neon closes transactions idle for five minutes; a lock connection must not leave a transaction idle during a long import. PostgreSQL regressions verify lock exclusivity and `xact_start IS NULL` for both worker and price-recovery locks.

## Checks

| Check | Result |
|---|---|
| Backend suite | 145 passed locally |
| Ruff lint and format | Backend and scripts passed |
| ESLint / TypeScript / Next production build | Passed |
| Playwright | Nine browser regressions passed |
| PostgreSQL | Disposable PostgreSQL 18 migrations, seed, SQL immutability, lock exclusivity, no idle lock transaction, duplicate-job and concurrent quota checks passed |
| Restore exercise | Backup of that synthetic disposable database restored into a second disposable database and smoke checks passed; this is not a restore of the hosted Neon database |
| Dependency audit | npm and pip-audit reported no known vulnerabilities at check time |
| Secret scan | Gitleaks 8.30.1, redacted full-history scan: no leaks found; configured private server secrets absent from the built browser JavaScript |
| Real-data walkthrough | 85 priced matches, 170 loaded visible team logos, goal lines, match analysis, three-match parlay save/reload, Performance and free-form chat passed; zero browser JavaScript errors |
| Mobile and artifacts | 390px view has no horizontal overflow; six screenshots inspected; 1440×1000 WebM playback decoded near its end |
| Hosted account email | Verification/reset mail actually delivered to the controlled project inbox; canonical links, single-use verification, login and reset session revocation passed; temporary account removed |
| Beta configuration | `scripts/run_beta.py readiness` reported no configuration blockers; this alone does not certify a release |

Browser regressions also cover empty searches, network failure/retry, initials fallback and account saves. They use isolated sample databases. The real-data capture uses the separate local live cache, not the hosted database. Counts change naturally as fixtures start and additional predictions are published.

GitHub backend, web and secret checks passed on code revision `a7e796a`, including PostgreSQL 17 in CI. Automatic Vercel preview checks also succeeded. GitHub checks and automatic Vercel previews run on pushed commits. Inspect the exact commit's [checks](https://github.com/filipswe/sports.easy/pull/2/checks) for current status; a successful preview is not proof that the permanent deployment runs that revision. The final documentation commit is separate from the code revisions above.

## Refresh, results and owner actions

The chosen personal-demo process is manual: `scripts/run_beta.py refresh`, before presenting the project and after results become available. The optional GitHub schedule stays disabled. Cadence checks avoid repeated full odds requests; explicit price recovery normally costs 16 credits and remains budget guarded. A timeout can leave a running job; after acquiring the exclusive lock, the next worker marks interrupted jobs failed and resumes using cached provider data where valid. Local and hosted databases do not share an account-wide quota ledger.

Hosted price recovery completed using the already-received 137-event provider response with its original receipt time, making no additional external odds requests. Unmatched events were skipped rather than fabricated. Both permanent API paths then returned HTTP 200 with 49 priced matches and six tracked picks, five settled and four wins. The sixth pick is newly published for a future match; it does not replace any original selection.

Five original hosted Champions League recommendations were settled from verified regulation scores, retaining their original publications: four won and one lost. Nine domestic fixtures with stored predictions were also checked. Repeated settlement and score-correction tests verify append-only revisions and unchanged original picks. See the [results table](resume-readiness.md#results-update-evidence). No new prediction was selected retrospectively to improve this record.

The exposed database-owner password was rotated privately and the separate restricted application role was verified afterward. Provider-key rotation remains **pending the owner**: the user confirmed replacements have not yet been saved. The four affected project settings are `API_FOOTBALL_KEY`, `FOOTBALL_DATA_KEY`, `ODDS_API_KEY` and `GROQ_API_KEY`; replacements belong in ignored `.env` / `.env.beta` and backend hosting settings. No credential values are included in this evidence.

## Limits and review scope

This is a personal portfolio demonstration, with uncalibrated estimates and a small forward-recorded result sample. Free-feed coverage and market availability vary; missing prices remain absent. European estimates can be market-based. Full model-input correction history, SQL optimization, trusted hosted client identity, extensive load tests and production monitoring remain optional future work before expanding scope. No paid service, merge, custom domain or production promotion was performed.

The first dedicated review found no confirmed issue in receipt timing, the recovery command or private runner. The second and final dedicated review found no confirmed issues in the PostgreSQL lock correction or demonstration documentation. Two review rounds were used. Owner-only credential replacement and the user's learning walkthrough cannot be represented as completed by code review.
