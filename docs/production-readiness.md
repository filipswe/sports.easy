# Production candidate and launch requirements

This milestone prepares a tested release candidate. It does not deploy the app or certify commercial readiness. Keep the existing installation on its current version until the feature branch is approved.

## Preview safely

Use Node 24 and the existing Python 3.13 virtual environment, then from the repository root:

```sh
.venv/bin/python scripts/preview.py
```

Open **http://127.0.0.1:3101**. This migrates/seeds a new temporary sample SQLite database and starts separate API/web services on 8101/3101. Ctrl+C stops them and removes their sample data. Live preview data is retained in ignored `.preview/`. It does not modify Docker, the existing database, accounts or Git branch. Ports must be free.

For actual data and Groq answers, with credentials already in ignored `.env`:

```sh
.venv/bin/python scripts/preview.py --live --ai
```

This uses the separate ignored `.preview/live-football-data.db` (or API-Football equivalent). It migrates only that preview database, reuses successful fixture refreshes for 24 hours, and retains the three-day odds schedule. Each initial eight-competition odds sweep costs 16 provider credits, with retry reservations subject to daily/monthly limits. Three European `/events` calls use a separate free request ledger. The preview does not start a polling worker. Live restarts reuse the cache rather than spending a new sweep every time. A provider quota/outage keeps the preview available with stored data and hides expired/unpriced matches. It never substitutes sample data in live mode.

## New behavior

Live All matches lists only scheduled future matches with supported prices from the configured bookmaker, verified within a maximum three-day cache. Unquoted outcomes are hidden in live views; missing model percentages are omitted. The most recent successful sweep supersedes unavailable prices; old snapshots remain immutable. Recommendations use current prices on upcoming cards; Performance retains the original recommended odds.

Champions League, Europa League and Conference League fixtures appear only within the next 14 days and when priced. The free European event adapter supplies no verified regulation-time history: these matches show real prices, omitted model percentages and an honest explanation when asked for a model assessment. They can be combined in custom parlays, with combined odds but no fabricated combined probability. They are excluded from model suggestions and the domestic recommended shortlist. All 63 clubs missing from the current European catalog now have reviewed cached crests. Future unknown clubs use bounded optional metadata lookup; ambiguous identities are not guessed.

Domestic model suggestions preserve multiplication of independent-match probabilities. “More likely to win than lose” appears only above 50%. Other suggestions rank available estimates within the requested price range. No percentages are inflated, calibrated certainty is not claimed, and no bets are placed.

Homepage chat uses Groq to select relevant verified evidence. Only the stored explanations, model numbers, form and bookmaker prices are rendered; unrestricted generated claims are not displayed. Invalid AI responses, outages and budget limits fall back to a labelled data-backed answer. The application does not store questions or a conversation transcript. Ask in your own words without choosing a match. A constrained router recognizes the club, opponent/date, market and goal line from upcoming priced fixtures; the browser retains the last match and two questions for follow-ups. Only the current question, up to two prior questions and bounded fixture metadata are sent to Groq. Questions are not stored in the database. A public operator must review provider processing and privacy terms.

## Configuration and deployment review

`ODDS_POLL_SECONDS=259200` refreshes odds every three days; `POLL_SECONDS=86400` refreshes domestic results and European event availability daily. Use `ODDS_DAILY_BUDGET=64`, `ODDS_EVENT_DAILY_BUDGET=32` for all eight competitions and retain `ODDS_MONTHLY_BUDGET=450`. Normal eight-competition sweeps use approximately 160–176 credits/month. Cached on-demand detailed markets cost up to four per event; retries consume budget too. The shared 450-credit monthly cap means expanded coverage is limited on the free plan. A 12-credit budget cannot complete a 16-credit sweep. The quotes are cached bookmaker prices and may differ when a user visits the sportsbook.

Optional chat uses `GROQ_API_KEY`, `GROQ_MODEL=openai/gpt-oss-20b`, `CHAT_DAILY_BUDGET=32`. Atomic database counters reserve one global AI call per minute, up to the daily budget, and five per visitor per hour. These conservative free-plan defaults protect shared quota; all additional requests still receive data-backed answers. No API key is exposed to the browser. Keep keys out of Git and rotate credentials through provider dashboards when needed.

Run configuration checks from `backend`:

```sh
../.venv/bin/python -m app.cli readiness
```

Production startup requires live mode, PostgreSQL, genuine provider credentials, retention approval, HTTPS/secure cookies, SMTP with a valid sender, a private session secret, a sufficient odds budget, a bounded cache, `OPERATOR_NAME` and `SUPPORT_EMAIL`. This is a configuration gate, not proof that the following launch work is complete:

- Configure hosting/TLS and reverse-proxy trusted addresses, request-size limits, edge rate limits and monitoring. Existing general API rate limiting is per process; chat budgets are shared in the database.
- Verify email registration/reset delivery and domain authentication. Local verification links are restricted to development on loopback origins.
- Set operator-specific privacy, terms, age/jurisdiction rules and provider/logo display rights. Current legal pages remain drafts. Obtain a policy review before public release.
- Exercise backup restoration and migration/rollback on staging PostgreSQL. Migrations must finish before API/worker start; retain append-only records. Run only one worker/manual ingestion at a time.
- Collect a real prospective results archive and measure calibration before claiming proven predictive performance. Free data cannot supply every requested market, lineup, injury or European estimate.
- Test real quota exhaustion, status corrections, SMTP failures and service alerts under the intended traffic/load. Full scans in the compact archive API need optimization before substantial scale.

No merge, deployment, paid subscription or main-database migration is part of this milestone.

## Prioritized product ideas

1. Pick watchlist with opt-in reminders before kickoff, using existing verified accounts.
2. Calibration reporting by league/market after sufficient prospective settled picks accumulate.
3. Licensed European match history, then supported cup recommendations.
4. Price movement notifications with a faster feed only when quota and user demand justify it.
5. An opt-in daily shortlist digest and localized explanations; no unsolicited messages.

Keep real data quality and a clear match/pick flow ahead of adding more panels.

## If port 3101 does not open

The preview is a local process, so keep its terminal open until finished. Start it with the command above and wait for `Preview ready`. Port 3000 remains the older Docker installation until an approved update. If ports 3101/8101 are occupied, use the running preview or stop that specific process first. A separate Next development server for this same checkout must also be stopped before preview/browser tests; do not stop the Docker site.
