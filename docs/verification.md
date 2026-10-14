# Verification report

Latest feature-branch preview: **http://127.0.0.1:3101**. The existing Docker app on port 3000 is unchanged by this milestone. See the final section for current validation; earlier sections record prior releases.

Local verification on 13 October 2026, after the matchday redesign. Provider credentials have not been supplied; the running local app uses explicitly labelled sample fixtures and odds.

## Completed checks

- **56 backend tests passed.** Coverage includes original auth, ingestion, model and settlement checks plus official recommendation freezing, single-source prices, goal-market probability coherence, separate first-half estimation and abstention, parlay arithmetic (three user prices of 2.00 give 8.00), correlated/invalid/started-leg rejection, unquoted outcomes, and suggested-parlay price ranges. New regressions cover five-league provider requests, isolated model histories, league filters, chronological 24-hour featured windows, retention of distant historical picks, and reasons for every supported market.
- **Five Chromium end-to-end tests passed.** Covered recommendation browsing, club crests, selecting matches, user-entered parlay prices, browser save/reload/reopen, team search, first-half markets, chosen-pick analysis, recent form, previous meetings, empty searches, admin protection, model suggestions, official-pick performance, registration/verification/login/saved picks, desktop layout and six mobile routes at 390px.
- **PostgreSQL 17.11 verified.** The earlier disposable test applied migrations, seeded 276 fixtures, rejected SQL UPDATE on publications and official recommendations, verified advisory lock exclusion and prevented duplicate jobs. The five-league upgrade now persists 1,380 fixtures in the retained Docker database, including the original English records. The updated CI smoke check asserts the expanded seed count. The worker's scheduling key includes the model version so a model upgrade runs immediately in the current bucket.
- Ruff lint/format, ESLint, TypeScript and the Next.js production build passed. Docker production build also passed, including copied local club crest assets.
- Complete local Docker stack rebuilt and left **running**: database and API healthy, worker running, web accessible on `http://localhost:3000`. The previous release verified same-origin readiness, five recommended picks and the performance archive. The five-league update returned all five leagues, chronological featured picks with reasons spanning less than 24 hours, 58 still-upcoming fixtures at verification, new club crest HTTP 200, and nine total archived recommendations after filling the new window. The original database volume, demo timeline, accounts and saved records were retained.
- Earlier dependency audits on the unchanged dependency set reported no known Python vulnerabilities and zero npm vulnerabilities.
- Screenshots inspected: [Home desktop](screenshots/home-desktop.png), [Home mobile](screenshots/home-mobile.png), [All matches](screenshots/matches-desktop.png), [Match analysis](screenshots/match-desktop.png), [Parlays mobile](screenshots/parlays-mobile.png), [Performance](screenshots/performance-desktop.png). These use synthetic data and a development-tool badge.
- Current API schema exported to [openapi.json](openapi.json).

## GitHub validation

Changes are committed and pushed in tested stages to `filipswe/sports.easy` on `main`. The prior release’s final GitHub run passed all jobs. GitHub's web and secret scanning checks passed for the first application commit. The backend job failed at GitHub's service-container initialization before executing tests. The second commit replaces that initialization with explicit PostgreSQL startup and cleanup. All three checks passed on that commit: backend tests/PostgreSQL/audit, web lint/types/build/audit/browser tests, and secret scanning. The additional higher-odds parlay regression (50–150) passed in the six-test matchday suite.

## Boundaries

Real provider credentials, sportsbook execution rules, SMTP delivery, provider contracts, production TLS and a public deployment have not been verified. Sample records do not establish model accuracy. The market catalog is broader than the current quoted-market feed: unquoted estimates show no fabricated prices. Browser parlay saves are local to the device, while authenticated saved single picks use database persistence.

Tests use Chromium, not a complete cross-browser matrix. Automated tests and visual inspection do not constitute an accessibility or security certification. Starlette TestClient currently emits a harmless HTTPX transport deprecation warning.

## Handoff

Open `http://localhost:3000`; the updated Docker application is running. Future restarts use `docker compose up -d`. Rebuilding after source changes uses `docker compose up --build -d`. The disposable PostgreSQL test container was removed. The repository ignores credentials, local databases, dependencies, build output and test traces.

## Latest matchday update

The five-league implementation is in commit `ee22b3a`. Local checks passed: 56 backend tests, five browser workflows (including kickoff-order assertions and first-half explanation checks), Ruff, ESLint, TypeScript and production/Docker builds. All GitHub checks passed for implementation commit `ee22b3a`. A subsequent 11-test matchday run passed, including a new worker-refill regression, bringing the test catalog to 57 cases. The worker now refreshes shortlist vacancies between ingestion jobs without creating another ingestion job or erasing original recommendations. All live-provider checks remain mocked until credentials are configured.

## Free live-provider activation — 14 October 2026

The running local PostgreSQL/Docker app uses football-data.org Free fixtures/results and Pinnacle prices from The Odds API Starter. Current and previous seasons imported across all five leagues: 3,504 fixtures, including 2,039 regulation results. The model produced 455 supported future-fixture estimates. All 97 returned bookmaker events matched verified source identities and kickoff times after 39 explicit club-name aliases were reviewed. There are 325 genuine price snapshots for 1X2 and offered 2.5 totals. Unsupported markets remain unpriced.

The homepage displays five recommendations in a 24-hour window, ordered by kickoff. Stronger picks arriving through new coverage can enter the shortlist; earlier official records retain their original price and probability in Performance. Daily-feed suggestions can use a snapshot fetched within 24 hours, always retaining its source update time and outdated-price label. Current-value filters still reject stale quotes.

Final checks: 85 backend tests and five Chromium end-to-end tests passed; Ruff, web lint/typecheck and production Docker builds passed. Live-browser checks verified ten loaded featured club crests, 48 chronological matches, five league choices, real-price parlay analysis, real recent form, separately fitted first-half estimates and mobile layouts without overflow or runtime errors. The additive crest migration preserved existing accounts and sample records. Today's worker reserved ten odds units and did not repeat the bootstrap sweep. Provider keys were absent from UI responses and tracked files.

## Expanded markets and natural-language analyst — 14 October 2026

On `feat/production-readiness`, the additional-market implementation and crest coverage are committed in `4d12e9e` and `b88c96c`. The latest local suite passes 121 backend tests and seven Chromium workflows, Ruff, ESLint, TypeScript and the production web build. The affected 12 natural-language chat tests were rerun after correcting AI focus classification. The original milestone had two dedicated review rounds; these requested corrections were self-reviewed for source identity, price calculations, quota/cache behavior, half-time settlement, bounded chat input and secrets.

Actual isolated live verification: 141 priced fixtures within 14 days; all 184 team images on the seven-day match list loaded successfully, with no missing model-percentage labels. A six-event Pinnacle detail refresh returned six BTTS/double-chance matches, five first-half 1.5 matches, six full-time 3.5 matches, and offered 1.5/4.5 lines. Chromium verified working selections, line-specific prices and mobile width of 390 without overflow or runtime errors. Groq recognized Feyenoord vs Como from a free-form question and returned its actual over-3.5 quote. Unknown or unquoted selections are never given fabricated prices.

The free quota cannot populate every alternate line for every event. Missing European history still suppresses model estimates. The public launch requirements in `production-readiness.md` remain open; this milestone does not merge or deploy. Restart the isolated preview with `.venv/bin/python scripts/preview.py --live --ai`.

## Soonest matchday and continuous preview — 14 October 2026

Commit `7062bce` passes all six GitHub push/PR checks, including the 128-case backend suite, PostgreSQL smoke/audit and browser/build checks. The final UI also passes all seven local Chromium workflows, lint, types and production build. Affected European-result/cache tests were rerun after rejecting null timestamps and allowing newly eligible later kickoffs to refresh without waiting for the earlier group cache.

Live preview verification selected five Champions League picks for 14 October, ordered by kickoff, ahead of the later domestic weekend. Those forecasts are explicitly labelled market-based where verified history is missing. All-goal-line API returned every quoted full-time line in the current window (including 1.5, 2.5, 3.5 and 4.5 where offered). The preview now runs an isolated worker and the supported Next standalone production server; its production UI contains the Dark Reader lock tag.

These corrections were self-reviewed, with targeted source identity, complete-market normalization, immutable-record, timezone, null-response, quota/cache and settlement-correction checks. The preceding milestone had already used its two dedicated reviewer rounds. European automatic settlements require the reviewed league-phase dates; extra-time-ambiguous scores and missed results beyond the provider's three-day history stay pending. No merge or deployment was performed.

The subsequent connection-recovery correction clears stale error messages after a successful cached refresh on All matches, Home and Performance, and adds **Try again** to All matches. An eighth Chromium regression deliberately interrupts the initial request and a later refresh, then verifies manual retry and automatic recovery. It passed locally alongside lint, type checks and a rebuilt production preview. The live production browser recovered from a deliberately interrupted request and loaded 92 priced matches with no page exceptions. All six GitHub checks passed on `b343dc5` before this follow-up.

GitHub's parallel push run exposed a startup race in that new regression while the PR browser run passed. The test now loads the application metadata before navigating to the interrupted match list, keeping the Retry assertion independent of bootstrap refreshes. Three consecutive local repetitions passed, and lint/types passed again; application behavior is unchanged by this test-only stabilization.

The backend run later exposed another time-dependent test setup: adding an hour to a late fixture could move the stronger candidate into the next local calendar day. That regression now uses the earliest matchday kickoff. Backend/browser assertions permit fewer than five eligible picks while retaining the five-pick cap, ranking, chronology and immutable performance checks. All 18 affected backend tests and all eight Chromium workflows passed locally, alongside Ruff lint/format, ESLint and TypeScript. These changes only stabilize tests; the production preview's application build is unchanged.
