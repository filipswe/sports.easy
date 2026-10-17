# Portfolio roadmap and learning guide

## What this project demonstrates

sports.easy is a personal football research project: a React/Next.js interface, a Python/FastAPI API, persistent SQL data, external provider integration, a statistical prediction model and an optional Groq chat integration. It does not place bets. Its probabilities have not been validated as profitable or calibrated against a substantial live sample.

The logo milestone caches the 171 teams inventoried on 14 October 2026 plus seven additional clubs reviewed on 17 October. All 180 team records in the refreshed local cache resolve to reviewed crests. It preserves reviewed club identities and provides provider-image and initials fallbacks. It does not promise coverage of every football club worldwide or automatically download every future team's logo.

## Demonstration status and next steps

The reviewed feature branch fixes the slow-ingestion odds timestamp bug and the managed-PostgreSQL idle-transaction lock bug. A local recording demonstrates real priced matches, loaded club logos, goal lines, analysis, parlay save/reload, Performance and a 390px layout. Controlled hosted email verification and reset passed. See the [demo package](demo/README.md), [validation evidence](resume-ready-verification.md) and [checklist](resume-readiness.md) for scope and exact code revisions. The recording is a reproducible local demonstration; permanent Vercel deployments are not automatically promoted by this work.

The chosen hosted refresh process is manual: run `scripts/run_beta.py refresh` before a demonstration and after results become available. It retains quota/cadence checks and a 20-minute timeout. The optional GitHub schedule remains disabled. Separate local and hosted databases do not share an account-wide provider quota ledger; avoid competing refreshers.

**Owner action remains:** rotate the provider keys previously shared in chat, save the replacements privately in `.env` and `.env.beta`, and update the backend hosting settings. Database-owner rotation and actual email delivery have been verified separately. Do not publish keys, passwords, reset tokens or credential-bearing connection strings.

Afterward, work through the learning guide below. Further product expansion is optional for a resume demonstration: measure calibration and comparison with a bookmaker baseline before making accuracy claims; optimize SQL after measuring bottlenecks; add injuries/lineups/xG only with an entitled feed; validate trusted hosted client identity before scaling rate limits. Payments, subscriptions and a custom domain are unnecessary for this personal project.

## Start with one request

Open All matches and inspect the browser's Network panel. A request follows this path:

```text
Browser → Next.js /api proxy → FastAPI route → SQLAlchemy → database
Browser ← JSON and rendered components ← API response ← stored records

Separate worker → football/odds providers → validated records → database
```

Reading a page uses stored data; it does not spend a provider request for every visitor. A worker refreshes that data separately. This separation makes the site faster and helps control free API quotas.

## Fundamentals, tied to this repository

| Technology or concept         | What it does here                                                                                                                                                       | Read or try                                                                                                                                                      |
| ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| HTML and CSS                  | HTML describes content; CSS controls layout, spacing, colors and responsive behavior. Tailwind is also included through PostCSS.                                        | Inspect `web/app/globals.css`; change one spacing rule locally and observe it.                                                                                   |
| JavaScript and TypeScript     | JavaScript runs application behavior. TypeScript catches mismatched shapes before execution; it does not validate arbitrary network input by itself.                    | Read `web/lib/api.ts`; find a response type and its request helper.                                                                                              |
| React                         | Components turn data into UI. Props are inputs; state remembers a component's changing values.                                                                          | Read `TeamBadge` and `TeamImage` in `web/components/ui.tsx`. Explain why an image failure changes state and why a new team resets it.                            |
| Next.js                       | Organizes React pages, builds the site, and proxies same-origin `/api` requests to Python. It includes server and browser execution environments.                       | Compare `web/app/page.tsx`, `web/app/predictions/page.tsx` and `web/next.config.ts`. Find `API_INTERNAL_URL`; it is server configuration.                        |
| HTTP, JSON and FastAPI        | The browser sends a method and URL; the backend validates input and returns a status plus structured data. JSON is the data format between them.                        | Read `backend/app/main.py`; open `/api/docs` and try a GET endpoint. Explain 200, 401, 403 and 404 using this app.                                               |
| Python and SQLAlchemy         | Python contains application logic. SQLAlchemy maps Python objects and queries to SQL tables and statements.                                                             | Read `backend/app/db.py`, then `backend/app/models.py`. Find a fixture's team references.                                                                        |
| SQL and PostgreSQL            | Tables persist records; keys identify rows and relationships. Transactions group changes into a consistent unit. Neon hosts the deployed PostgreSQL database.           | Trace Fixture → Prediction → Publication in `models.py`. Inspect records read-only with your private database settings. SQLite is the simpler local alternative. |
| Alembic                       | Versioned migrations change database structure without rebuilding application data from scratch.                                                                        | Read `backend/alembic/versions/`; compare a migration with the corresponding model.                                                                              |
| Providers and background jobs | Adapters translate third-party responses; the worker handles scheduling, retries, quotas and storage.                                                                   | Follow `backend/app/worker.py`, `ingestion.py` and `providers.py`. Explain why secrets stay on the server.                                                       |
| Statistical model and AI chat | The statistical code estimates outcome probabilities. Groq assists with grounded question analysis; it is not the probability calculation or a source of invented odds. | Read `backend/app/model.py`, `european_predictions.py`, `chat.py` and the model methodology document.                                                            |
| Tests and CI                  | Unit tests check isolated logic; browser tests exercise actual user flows. GitHub Actions runs repeatable checks on code changes.                                       | Read one `backend/tests/test_model.py` test and `web/tests/club-crests.spec.ts`, then `.github/workflows/ci.yml`.                                                |
| Git, Docker and hosting       | Git versions code. Docker supplies repeatable local service environments. Vercel hosts web/API code; Neon stores persistent data separately.                            | Read `compose.yaml` and `docs/vercel-beta.md`. Container service names work inside Docker; your computer uses published localhost ports.                         |

## A practical learning sequence

Work through one small change at a time: a CSS adjustment, a React component state change, a GET request, a read-only SQL query, a model test, then a complete browser regression. For each change, predict what should happen, run it, explain the result in your own words, and commit it. Use the README's isolated preview and disposable test databases rather than experimenting on hosted data.

You should eventually be able to explain: where a match comes from, where its odds are stored, why its probability differs from the odds, how a parlay is calculated, how a result settles an immutable recommendation, and what happens when a provider or image fails.

An accurate resume description after you understand and can demonstrate the implementation is: “Built a football research application with Next.js, React, TypeScript, FastAPI, SQLAlchemy and PostgreSQL; integrated external fixture/odds APIs, statistical predictions, grounded AI analysis, and automated backend/browser tests.” Describe your own contributions and AI assistance honestly; claim validated performance or production operation only when you have evidence.
