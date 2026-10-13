# Verification report

Local verification on 13 October 2026, after the matchday redesign. Provider credentials have not been supplied; the running local app uses explicitly labelled sample fixtures and odds.

## Completed checks

- **52 backend tests passed.** Coverage includes original auth, ingestion, model and settlement checks plus official recommendation freezing, single-source prices, goal-market probability coherence, separate first-half estimation and abstention, parlay arithmetic (three user prices of 2.00 give 8.00), correlated/invalid/started-leg rejection, unquoted outcomes, and suggested-parlay price ranges.
- **Five Chromium end-to-end tests passed.** Covered recommendation browsing, club crests, selecting matches, user-entered parlay prices, browser save/reload/reopen, team search, first-half markets, chosen-pick analysis, recent form, previous meetings, empty searches, admin protection, model suggestions, official-pick performance, registration/verification/login/saved picks, desktop layout and six mobile routes at 390px.
- **PostgreSQL 17.11 verified in a disposable container.** All migrations applied, 276 synthetic fixtures seeded, SQL UPDATE rejected on both publications and official recommendations, advisory lock exclusion verified, and repeated scheduling produced no duplicate job. The worker's scheduling key includes the model version so a model upgrade runs immediately in the current bucket.
- Ruff lint/format, ESLint, TypeScript and the Next.js production build passed. Docker production build also passed, including copied local club crest assets.
- Complete local Docker stack rebuilt and left **running**: database and API healthy, worker running, web accessible on `http://localhost:3000`. Same-origin readiness, five recommended picks, upcoming match data and the five-pick performance archive were verified. The original database volume, demo timeline, accounts and saved records were retained.
- Earlier dependency audits on the unchanged dependency set reported no known Python vulnerabilities and zero npm vulnerabilities.
- Screenshots inspected: [Home desktop](screenshots/home-desktop.png), [Home mobile](screenshots/home-mobile.png), [All matches](screenshots/matches-desktop.png), [Match analysis](screenshots/match-desktop.png), [Parlays mobile](screenshots/parlays-mobile.png), [Performance](screenshots/performance-desktop.png). These use synthetic data and a development-tool badge.
- Current API schema exported to [openapi.json](openapi.json).

## GitHub validation

The application was committed and pushed to `filipswe/sports.easy` on `main`. GitHub's web and secret scanning checks passed for the first application commit. The backend job failed at GitHub's service-container initialization before executing tests. The second commit replaces that initialization with explicit PostgreSQL startup and cleanup. All three checks passed on that commit: backend tests/PostgreSQL/audit, web lint/types/build/audit/browser tests, and secret scanning. The additional higher-odds parlay regression (50–150) passed in the six-test matchday suite.

## Boundaries

Real provider credentials, sportsbook execution rules, SMTP delivery, provider contracts, production TLS and a public deployment have not been verified. Sample records do not establish model accuracy. The market catalog is broader than the current quoted-market feed: unquoted estimates show no fabricated prices. Browser parlay saves are local to the device, while authenticated saved single picks use database persistence.

Tests use Chromium, not a complete cross-browser matrix. Automated tests and visual inspection do not constitute an accessibility or security certification. Starlette TestClient currently emits a harmless HTTPX transport deprecation warning.

## Handoff

Open `http://localhost:3000`; the updated Docker application is running. Future restarts use `docker compose up -d`. Rebuilding after source changes uses `docker compose up --build -d`. The disposable PostgreSQL test container was removed. The repository ignores credentials, local databases, dependencies, build output and test traces.
