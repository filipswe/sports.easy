# sports.easy

**Betting made easy.** A football match centre with a bright interface, recommended picks, match analysis and a parlay builder.

New installations start with labelled sample data. The [free live setup](docs/live-setup.md) combines football-data.org fixtures/results with Pinnacle prices from The Odds API. The public interface labels these **Current odds**; fixtures/results refresh every four hours, odds refresh every three days, and price-age checks remain on the server. Probabilities are model estimates, and no profitable track record is claimed.

## What works

- Light responsive Home, All matches, match analysis, Parlays, Performance and How it works pages, with club crests and simple navigation.
- Up to five recommendations for the soonest Europe/Belgrade calendar matchday across European competitions and the top five leagues, displayed by kickoff. European games without history use a labelled market-based estimate from complete real 1X2 prices. Performance follows these exact picks and their original odds, including losses and settlement corrections.
- Priced upcoming fixtures only in live mode, plus Champions League, Europa League and Conference League within 14 days; team search, dates and league filters; match stats, last-five form, previous meetings, and specific reasons for the model's view of every chosen outcome. All matches remain in kickoff order.
- Model estimates for 1X2, BTTS, several goal lines, first-half goals when history supports them, double chance, team goals and correct scores. Quotes are shown only when available; live Pinnacle detail quotes support BTTS, double chance, full-time and first-half half-goal lines (0.5–9.5 where quoted). Sample detail prices remain clearly labelled.
- Custom parlays, model suggestions within combined-odds ranges, combined probability and odds, user-entered prices and browser saves. One selection per match; repeated clubs are excluded.
- One configured sportsbook source (`ODDS_BOOKMAKER_KEY=pinnacle` for live ingestion). No bookmaker comparison UI. Missing prices are shown as a dash.
- FastAPI/SQLAlchemy persistence, PostgreSQL Docker deployment, Alembic migrations and a native SQLite development option.
- Accounts, verified registration, password resets, preferences and authenticated saved picks. Append-only model, quote, official recommendation and settlement records.
- Homepage match analyst with optional Groq AI evidence selection and labelled data-backed answers.
- Provider adapters, quotas, retry/backoff, independent odds cadence and a worker with PostgreSQL advisory locking.

See [product details and coverage](docs/product-update.md) for current market, data and storage limits.

Club logos are cached for all 171 teams inventoried in the live beta on 14 October 2026, with seven additional reviewed clubs added on 17 October; every one of the 180 team records in the current local live cache resolves to a reviewed crest. Every shared badge tries the reviewed local image, then its supplied provider image, then the club's initials. Newly added teams can use provider images immediately; see the [crest catalog and source notes](web/public/clubs/README.md) before adding more cached assets.

This is a personal portfolio project. The [portfolio roadmap and learning guide](docs/portfolio-guide.md) distinguishes remaining work from optional expansion and walks through the actual technologies and request flow.

## Isolated milestone preview

From this checkout, run `.venv/bin/python scripts/preview.py` and open **http://127.0.0.1:3101**. Add `--live --ai` to use the ignored provider/Groq credentials with a separate cached database under ignored `.preview/`. The preview starts a production UI and isolated worker for updates/settlements; add `--dev` for hot reload. Live restarts reuse recent data; sample previews use a new temporary database. Keep the terminal running while browsing; Ctrl+C stops the preview. Your existing Docker services and data remain untouched. See [production candidate, configuration and launch requirements](docs/production-readiness.md) for exact limitations and remaining launch work. [Milestone validation results](docs/milestone-verification.md) record the checks and independent review.

## Quick start: Docker Compose

For the planned free non-commercial cloud beta, use the [Vercel/Neon setup](docs/vercel-beta.md). It keeps local databases separate, uses private `.env.beta` configuration and requires hosting/email/owner settings before deployment. Run `.venv/bin/python scripts/check_beta.py` to see missing settings without printing credentials or connecting to services.

Prerequisites: Docker Desktop/Engine with Compose. No provider accounts are needed for demo mode.

```sh
cp .env.example .env
```

For this workspace, a local ignored `.env` has already been created with generated local secrets. For a fresh clone, edit `.env`: set a unique `POSTGRES_PASSWORD` (URL-safe characters for the supplied URL composition), and replace `SESSION_SECRET` with a locally generated random value of at least 32 characters. Keep `APP_DATA_MODE=demo`, `APP_ENV=development` and `COOKIE_SECURE=false` for local HTTP.

```sh
docker compose up --build -d
docker compose logs -f worker
```

Migrations run once before API/worker startup. The worker seeds the demo on its first run. Open **http://localhost:3000**. API docs: **http://localhost:8000/api/docs**. Stop log-following with Ctrl+C.

Optional synthetic evaluation:

```sh
docker compose exec api python -m app.cli evaluate
```

Open `/performance` → Historical model evaluation. The recorded scores are labeled synthetic, not actual predictive validation.

```sh
docker compose down
```

This preserves the database volume. Do not add `--volumes` unless you intentionally want to erase the local data.

## Native local development (no Docker required)

Use **Node 24** and **Python 3.13**. The default shell on the original workstation had Node 16/Python 3.9; suitable installed binaries were `/usr/local/bin/node` and `/opt/anaconda3/bin/python`. Select the correct runtimes before installing. Supported runtime patch versions are pinned in Dockerfiles; local tests used the installed Python 3.13.9 runtime.

From the repository root:

```sh
python3.13 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
npm ci --prefix web
cp .env.example .env
```

For native development, keep `DATABASE_URL=sqlite:///./sports.db`. Change `API_INTERNAL_URL` in your web shell to `http://127.0.0.1:8000` (the backend `.env` value is not used by Next unless exported). Set `PUBLIC_ORIGIN` to the exact browser origin, normally `http://localhost:3000`.

Terminal 1:

```sh
cd backend
../.venv/bin/alembic upgrade head
../.venv/bin/python -m app.cli seed
../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Terminal 2:

```sh
cd web
API_INTERNAL_URL=http://127.0.0.1:8000 npm run dev
```

Optional terminal 3, run **one** worker with SQLite:

```sh
cd backend
../.venv/bin/python -m app.worker
```

The browser talks only to `/api` on the web origin; Next proxies it to FastAPI. No API key enters a browser bundle.

## Try the complete flow

1. Open Home and browse **Our recommended picks**. The status bar identifies sample data while providers are disconnected.
2. Open **All matches**, search for a team and select a date or market. Choose **Under/over goals** or **First-half goals**, then select a goal line for its corresponding prices. Live views hide unpriced selections. Tap an outcome to add it to your parlay.
3. Open a match for the model's view, quoted markets, form, stats and previous meetings. Choosing another outcome updates its analysis. On the homepage, ask a question such as “What are the odds for Arsenal’s next game?”; no match selector is required. Follow-up questions remember the last identified game.
4. Open **Parlays**, review your selections, enter your own decimal odds if needed, or ask for model suggestions within a combined-odds range. Save and reopen a parlay on this browser.
5. Create and verify a test account to save individual picks. Local email mode provides a verification link. Saved picks keep their original publication and price.
6. Visit **Performance** to follow only the official recommended picks. Pending records are excluded from wins and simulated returns.

Demo prices age normally and become stale after ten minutes. Stale prices are browsable, but fresh-only and current-value rankings exclude them. Refreshing a page or running `seed` again does **not** change their upstream timestamp. The initial upcoming fixtures eventually pass kickoff and disappear. To create an entirely new demo, point `DATABASE_URL` at a new empty SQLite database or a separate PostgreSQL database, migrate, and seed. Existing saved records should not be silently reset.

## Tests and checks

From the repository root:

```sh
.venv/bin/ruff check backend
.venv/bin/ruff format --check backend
.venv/bin/pytest -q
npm run lint --prefix web
npm run typecheck --prefix web
npm run build --prefix web
npm audit --prefix web --audit-level=high
.venv/bin/pip-audit -r backend/requirements.txt
```

Browser tests create a fresh isolated SQLite database in the system temporary directory, using API port 8100 and web port 3100. They start/stop their own servers. Use a disposable test database, never a production URL.

```sh
cd web
npx playwright install chromium
npm run test:e2e
```

On Linux CI: `npx playwright install --with-deps chromium`. Tests cover the match browsing, form and first-half markets, user-price parlay calculations, suggestions, save/reopen, register/verify/save, no-results/reset, protected admin access, mobile navigation and official-pick performance. Traces and screenshots go to ignored `web/test-results/`.

PostgreSQL-specific smoke check, after migrations and a demo seed, against a disposable database:

```sh
cd backend
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DISPOSABLE_DB PYTHONPATH=. ../.venv/bin/python tests/postgres_smoke.py
```

Checks database-level immutability, persisted seed, advisory lock exclusivity and duplicate-job protection. Never run the synthetic fixture-count assertion against an existing live database. CI runs unit tests, lint/format, TypeScript, build, browser flow, PostgreSQL migration/seed, dependency audits and secret scanning.

## Operations

```sh
# From backend, with the intended DATABASE_URL
../.venv/bin/python -m app.cli ingest
../.venv/bin/python -m app.cli evaluate
../.venv/bin/python -m app.cli promote-admin --email your-verified-account@example.com
```

The admin command requires an existing verified account and records an audit event. `/admin` exposes sanitized ingestion state; no credentials are shown. Ingestion/evaluation commands are private operator actions, not public HTTP routes. Do not run manual ingestion concurrently with the worker.

## Live credentials and limitations

Follow the [live signup and activation steps](docs/live-setup.md) to connect actual bookmaker prices.

Read [provider capability, cost and rights notes](docs/providers.md) before enabling live mode. Use the free football-data.org fixture credential (or an entitled API-Football account) and The Odds API credential, a selected region, reviewed display/retention rights, SMTP, HTTPS and a real deployment secret. No credentials are bundled, and live mode never substitutes synthetic data. The adapters have not been tested against paid accounts in this session.

Remaining limits: uncalibrated probabilities, no archival historical odds ingestion or proven real predictive performance, European estimates based on prices where verified history is absent, event-dependent market availability within the free quota, injuries/lineups/xG/standings feeds and payment/betting operations. Chat recognizes the match, requested market and follow-up context from free-form questions, then explains verified facts. Questions are not stored on the server. Dedicated model-input version storage, SQL-based large-archive ranking, trusted hosted proxy/client identity and production observability integration need further work before scale. Production request limits now use shared database counters. This MVP uses compact season/market/stat representations instead of building unnecessary unused tables. See the [architecture and actual controls](docs/architecture.md), [model methodology](docs/methodology.md), [deployment/rollback guide](docs/deployment.md) and [verification report](docs/verification.md).

## Troubleshooting

- **Node version error:** Next requires a modern runtime. `node --version` should be 24.x for this project. On the original workstation, `PATH=/usr/local/bin:$PATH npm …` selects it.
- **Docker daemon unavailable:** start Docker Desktop, then `docker info`. Native SQLite mode is available without Docker.
- **Port already in use:** stop your old process or change web/API ports, `API_INTERNAL_URL` and `PUBLIC_ORIGIN` together. Tests need 3100/8100.
- **Connection interrupted:** keep the preview terminal running and click **Try again** on All matches. Open match, homepage and performance lists also recover on their next successful one-minute refresh; a temporary failure no longer leaves an old error on screen.
- **Empty live results:** inspect `/admin`: credentials, retained-data approval, provider quota, identity mapping, requested line, season entitlement and minimum sample size can all prevent publication.
- **No demo EV results:** source prices are older than ten minutes; this is expected, not fixed by page refresh. Disable EV/fresh-only filtering to inspect stale records.
- **CSRF failure:** use exactly `PUBLIC_ORIGIN` in the browser. `localhost` and `127.0.0.1` are different origins. Cookies must be Secure only on HTTPS.
- **No verification email:** demo without SMTP returns a local link. Live/production requires SMTP. Test your domain configuration and delivery logs without logging tokens.
- **Turbopack socket failure:** scripts use Next's supported `--webpack` option on this workstation.
- **Expired demo fixtures:** start a new, separate demo database. Do not refresh or rewrite existing publication timestamps.
- **Database schema missing:** run `alembic upgrade head` from `backend` with the correct database URL before launching API or worker.

Legal/information text is a draft. Probabilities are estimates, football is uncertain, and returns are never guaranteed. Adults 18+ only; actual obligations depend on the deployment jurisdiction.
