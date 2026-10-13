# Connect actual bookmaker odds

The existing `.env` currently has neither provider key. The site will continue to show labelled demo data until live mode is configured; no real price is claimed without a provider quote.

1. Create an account at [API-Football](https://dashboard.api-football.com/register). Copy the dashboard API key. Confirm your plan covers the current and previous season for Premier League, La Liga, Serie A, Bundesliga and Ligue 1. The [free plan](https://www.api-football.com/pricing) has limited seasons; Pro is listed at $19/month. A key alone does not establish current-season access.
2. Get a key through [The Odds API](https://the-odds-api.com/), using its **Get Access / Starter** signup or [account dashboard](https://dash.the-odds-api.com/). Starter currently has 500 credits/month. This is suitable for initial connection testing; repeated five-league refreshes need a larger allowance. Confirm Pinnacle coverage for your account before upgrading.
3. Edit the project's ignored `.env`, retaining the existing random `SESSION_SECRET` and database password. Add the real keys and change these entries:

```dotenv
API_FOOTBALL_KEY=your_dashboard_key
ODDS_API_KEY=your_odds_key
APP_DATA_MODE=live
APP_ENV=development
PUBLIC_ORIGIN=http://localhost:3000
COOKIE_SECURE=false
ODDS_BOOKMAKER_KEY=pinnacle
ODDS_REGION=eu
```

Keep credentials out of GitHub and chat. `COOKIE_SECURE=false` is accepted only for the loopback development setup; a public production deployment still requires HTTPS and secure cookies.

The ingestion gate `LIVE_RETENTION_APPROVED=true` must reflect review of your account's display/storage terms. Provider terms: [API-Football](https://www.api-football.com/terms) and [The Odds API](https://the-odds-api.com/terms-and-conditions.html). Leave the gate false until that review is complete.

4. Recreate the services so the updated environment is applied (a restart alone does not reload `.env`):

```sh
docker compose up --build -d
```

The worker performs ingestion. Follow its status with `docker compose logs -f worker` and stop log-following with Ctrl+C. Do not run concurrent manual ingestion. No bet placement or bookmaker account access is used.

5. Verify the live-mode feed before using its prices. Provider error/entitlement limits, unmatched club names, missing history or market coverage can cause empty results; they are not replaced with synthetic fixtures or prices. The first five-league odds sweep reserves 10 credits; football history requests two seasons for each league. The current budget limits the number of sweeps and prices may age between them.

Current priced live coverage is 1X2 and offered totals at 2.5. BTTS, first-half and additional market prices require the provider's per-event market integration. Model estimates and manually entered odds do not qualify as verified bookmaker quotes.

Existing demo records and accounts remain stored, but live requests are isolated from demo fixtures, quotes and recommendations. Public deployments also require SMTP delivery for account verification/reset.
