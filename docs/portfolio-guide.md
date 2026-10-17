# Portfolio roadmap and learning guide

## What this project demonstrates

sports.easy is a personal football research project: a React/Next.js interface, a Python/FastAPI API, persistent SQL data, external provider integration, a statistical prediction model and an optional Groq chat integration. It does not place bets. Its probabilities have not been validated as profitable or calibrated against a substantial live sample.

The logo milestone caches the 171 teams inventoried on 14 October 2026 plus seven additional clubs reviewed on 17 October. All 180 team records in the refreshed local cache resolve to reviewed crests. It preserves reviewed club identities and provides provider-image and initials fallbacks. It does not promise coverage of every football club worldwide or automatically download every future team's logo.

## Remaining work, in priority order

These are follow-up tasks, not claims of completed hosted verification. Local changes must be committed, reviewed and deliberately deployed before the website contains them.

1. **Finish one reproducible hosted demonstration.** Align the website and backend with the reviewed commit; verify browsing, goal lines, analysis, parlays and logo loading on the permanent website URL. The backend root can return JSON 404; its documentation lives at `/api/docs`.
2. **Fix and verify data refresh and recovery.** On 17 October the local live cache had a completed 141-event odds sweep but no quote observations newer than 14 October, so the live match list was empty. Investigate the ingestion timestamp: `ingest()` captures `fetched` before lengthy model work, while `store_odds()` rejects a market timestamp more than one minute after that value. A slow job can therefore reject newly received prices. Use a separately defined odds observation time, retain source timestamps and immutable originals, and add a slow-job regression before claiming the fix. Then confirm one complete scheduled ingestion and settlement run, provider quota handling, and recovery after a timeout. The initial cold Neon import exceeded a ten-minute operator timeout and needed its remaining stages resumed. The optional GitHub refresh workflow is gated off until its environment/secrets are configured and it is deliberately enabled; scheduled workflows also need to exist on the default branch. Avoid competing local and hosted refreshers.
3. **Verify account email if accounts remain in the demo.** Exercise registration, verification and password reset with a controlled test account. SMTP authentication alone does not prove mail arrives. Never publish verification/reset tokens or private settings.
4. **Keep CI green and make the project reproducible.** Retain backend tests, browser regressions, types, lint, production builds and secret checks. Add a concise demo video, current screenshots and a short explanation of design choices. Record the exact commit demonstrated.
5. **Measure the model honestly.** Accumulate immutable live predictions and settled outcomes. Evaluate calibration (whether estimated 70% events occur roughly 70% of the time), Brier score, log loss and comparison with a bookmaker baseline. Separate synthetic tests from real evidence. Never inflate confidence to improve presentation.
6. **Secure credentials and basic recovery.** Rotate any credentials previously shared in chat, keep them in ignored private configuration or hosting secrets, and document a backup/restore exercise. Validate hosted client identity before relying on per-user IP rate limits: proxy requests may share a budget today.

For a resume demonstration, more leagues, payments, subscriptions, a custom domain, an expensive monitoring platform and additional AI providers are optional. Richer historical input snapshots, SQL query optimization, injuries/lineups/xG and extensive load testing become useful when they answer a measured need. Keep existing security checks even for personal use.

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
