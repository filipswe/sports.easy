# Connect real fixtures and bookmaker odds for free

The free setup uses **football-data.org** for real fixtures/results and **The Odds API** for Pinnacle prices. API-Football's Free key can remain saved, but this setup does not use it because its current-season request was rejected. Credentials stay in the ignored `.env`, never GitHub or browser code.

1. Create a [football-data.org Free account](https://www.football-data.org/client/register). Its [free coverage](https://www.football-data.org/coverage) includes Premier League, La Liga, Serie A, Bundesliga and Ligue 1. Scores and schedules are delayed; this is a pre-match app. The token arrives by email. The account checked on 13 October 2026 accepted 2026 and 2025 Premier League matches, including halftime scores. Check each account's history entitlement rather than assuming it.
2. Get a free Starter key from [The Odds API](https://the-odds-api.com/). The verified account supplied Pinnacle Premier League 1X2 and total prices. A valid key does not guarantee every event or market has a price.
3. Retain the existing database password and private session secret. Set these entries in `.env`:

```dotenv
FOOTBALL_PROVIDER=football-data
FOOTBALL_DATA_KEY=your_free_football_data_token
ODDS_API_KEY=your_odds_key
APP_DATA_MODE=live
APP_ENV=development
PUBLIC_ORIGIN=http://localhost:3000
COOKIE_SECURE=false
ODDS_BOOKMAKER_KEY=pinnacle
ODDS_REGION=eu
POLL_SECONDS=86400
ODDS_POLL_SECONDS=259200
PROVIDER_DAILY_BUDGET=80
ODDS_DAILY_BUDGET=20
ODDS_MONTHLY_BUDGET=450
```

4. Review the [football-data.org registration terms](https://www.football-data.org/client/register) and [The Odds API terms](https://the-odds-api.com/terms-and-conditions.html), then set `LIVE_RETENTION_APPROVED=true` for the applicable deployment. The football feed requires attribution, included in the live footer. Stop displaying its data after account cancellation. Club graphics have separate ownership rights. The odds terms permit storage and analytical app display, but not raw-feed resale. The local setup review does not establish commercial publication rights to club graphics.
5. Recreate services to apply the environment and schema:

```sh
docker compose up --build -d
```

The worker handles ingestion. Do not run manual ingestion concurrently with it. Follow status with `docker compose logs -f worker`; Ctrl+C stops log-following without stopping the app. Restarting alone does not reload `.env`.

## Free allowance and price age

One eight-competition odds sweep reserves 16 credits: eight requests × two markets. Three-day refreshes use approximately 160–176 credits/month before retries, within the verified Starter allowance of 500. Daily and monthly guards reserve usage before every attempt, including failures. The monthly guard uses UTC calendar months; the provider's billing reset can differ, and its remaining quota still applies. Verification requests outside the worker also consume credits.

The public interface uses the label **Current odds** and omits price-age badges and update timestamps. Internally, prices retain the bookmaker's original update time and become stale after ten minutes. Daily refreshes are not continuous pricing. Three-day-feed recommendations and parlay suggestions can use real snapshots verified within 72 hours; faster feeds require fresh source timestamps. Current-value and positive-EV filters still reject stale prices. Stronger newly available picks can enter the five-pick shortlist; every earlier official recommendation retains its original price and probability in Performance. Custom parlays identify sportsbook or explicitly entered prices, while saved and historical records retain their original odds.

The football refresh uses ten requests: current and previous seasons across five leagues. Its local ten-request-per-minute cap protects the Free tier. A denied previous season can be skipped, but current-season denial is never hidden. The model abstains below 40 league results or eight results for a club. Missing halftime scores disable the separate first-half estimate.

Current live prices cover 1X2 and offered totals at 2.5. BTTS, first-half and other prices require a per-event integration and additional credits; unsupported prices remain blank. Model probabilities and entered odds are not bookmaker quotes.

## Accounts and existing records

Accounts, demo predictions and saved records remain stored. Live views exclude demo data; fixture and team identities have their own provider namespace. Switching an established live installation between football providers requires a separate database or reviewed identity migration.

Loopback development can show verification/reset links without SMTP, including with real football data. Public production requires SMTP, HTTPS, secure cookies and a private session secret. No bookmaker login or bet placement is used.

For an existing API-Football subscription, choose `FOOTBALL_PROVIDER=api-football` and configure `API_FOOTBALL_KEY`. Current/previous-season entitlement is still required. This free setup makes that subscription unnecessary.

## Current milestone overrides

Use `POLL_SECONDS=86400`, `ODDS_POLL_SECONDS=259200`, `ODDS_DAILY_BUDGET=20` and `ODDS_MONTHLY_BUDGET=450` for eight competitions. The earlier daily five-league budget guidance is superseded. Add the optional free Groq token as `GROQ_API_KEY` only in ignored `.env`. Follow [the isolated preview and release checklist](production-readiness.md) before updating an existing installation.
