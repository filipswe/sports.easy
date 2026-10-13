# Data providers and live setup

Documentation reviewed on **13 October 2026**. Prices and entitlement details can change. The application buys nothing and makes no provider calls on a page visit.

| Feed | Actual integration | Coverage / history | Quota and cost observed | Important limits |
|---|---|---|---|---|
| API-Football v3 | `/fixtures` for the configured league, current and previous season; FT regulation scores, fixtures, status, teams, venue | Initial league ID 39, Premier League. Check `/leagues` coverage and available seasons in your account before enabling | Free: 100 requests/day, limited seasons. Pro: $19/month, 7,500/day. Ultra $29/75,000; Mega $39/150,000 | Endpoint availability does not prove every field is covered. No xG, injury or lineup integration in this MVP. Source update time is unavailable in the fixture payload, so only fetch time is stored |
| The Odds API v4 | `/sports/soccer_epl/odds`, `h2h,totals`, one configured bookmaker (`ODDS_BOOKMAKER_KEY=pinnacle`), decimal odds; only totals line 2.5 retained | The selected bookmaker must cover the requested event. Paid historical endpoint exists but is **not integrated** | Free: 500 credits/month; 20K: $30/month; 100K: $59/month. Two markets × one region cost two credits per successful odds request | No claim of continuous freshness. Main event endpoint is used; BTTS requires a separate per-event market integration and remains demo-only |
| Demo adapters | Deterministic synthetic fixture history, future fixtures and two synthetic bookmakers | Premier League team-name examples, not the real schedule or official results | No network or paid account | No real accuracy, profit, form, quotes or predictions. Initial anchor persists; seeding again does not refresh ages |

Sources: [API-Football pricing](https://www.api-football.com/pricing), [v3 documentation](https://www.api-football.com/documentation-v3), [The Odds API plans](https://the-odds-api.com/), [v4 API documentation](https://the-odds-api.com/liveapi/guides/v4/), [market list](https://the-odds-api.com/sports-odds-data/betting-markets.html). Dynamic API-Football reference content was not fully readable in the browser extraction; integration needs an entitlement-backed smoke test before public live use.

## Cadence and budgets

The shipped worker polls every **four hours**, with local budgets of 80 football requests and 12 odds credits per UTC day. Six runs/day × two market credits = 12; approximately 360–372 monthly odds credits before retries. Retry reservations count against local budgets even when the provider does not charge, intentionally conservatively. These settings fit a limited research demo, not continuous pricing.

All supported quotes become stale after 600 seconds of **provider source update age**, independently of fetch time. The default deliberately leaves most prices stale between low-budget polls. For a funded account, set `POLL_SECONDS` and budgets together. Two markets every five minutes would consume about 576 credits/day (~17,280 per 30 days) before retries; confirm provider update cadence and quota before selecting it. Do not imply a fetch creates a newer upstream quote.

The dedicated published update-interval page could not be retrieved during this build. Its exact per-market cadence has **not** been verified and is not hardcoded as a provider guarantee. Quota response headers, failures and unmatched events are available to an authenticated administrator. The worker has fixed URL hosts, 15-second HTTP timeouts, at most three attempts, exponential delay and jitter. HTTP 429 stops that run. PostgreSQL advisory locking and unique scheduling buckets prevent overlapping scheduled jobs. A failed run retries in the next bucket; there is no large queue system.

## Enable live data

1. Create provider accounts yourself. Verify EPL current/previous-season coverage, your intended bookmaker region (`uk`, `eu`, `us`, `au`), 90-minute market rules and account quotas.
2. Review [API-Football terms](https://www.api-football.com/terms) and [The Odds API terms](https://the-odds-api.com/terms-and-conditions.html). API-Football permits app use but prohibits unauthorized resale and can restrict rights. The Odds API currently expressly permits storing/retaining data and displaying it in analytical applications, but prohibits redistribution as a standalone raw-data product. Confirm your specific deployment; this application's endpoints are for its UI, not a resale feed.
3. Use a separate live database. Set `APP_DATA_MODE=live`, `API_FOOTBALL_KEY`, `ODDS_API_KEY`, `LIVE_RETENTION_APPROVED=true`, league/season/sport mapping and region. Configure secure cookies, HTTPS, SMTP and a strong secret. Do not put keys in browser variables or git.
4. Run migrations, then `python -m app.cli ingest` from `backend`, or start the worker. Inspect protected `/api/admin/status` using a locally promoted, verified account.
5. Confirm fixtures and quotes with the source accounts. The model requires 40 league results and eight per team. Unknown or ambiguous team mappings are rejected; add reviewed aliases through `provider_mappings` (provider `the-odds-api`, entity_type `team`, external_id exact source team name, entity_id canonical team UUID). No fuzzy matching is used. Kickoff tolerance is 15 minutes and home/away direction and competition sport key must agree.
6. Keep the baseline labeled unvalidated until genuine evaluation supports a stronger claim. Imported past results use **first observed availability**, so an initial bulk fetch cannot magically support an earlier backtest.

Missing keys or unapproved retention yields an explicit unavailable job. Live mode never reads demo rows. Match status is updated independently of odds availability; there is no silent demo fallback. Additional leagues require deliberate configuration and verified provider/model coverage; use an isolated database when changing the configured league. No historical data scraping or unauthorized data bundle is included.

## Single-source product flow

The matchday interface uses one sportsbook source. The Odds API lists Pinnacle in its EU coverage, and the documented `bookmakers` parameter overrides `regions`. This does not provide a Pinnacle account connection or bet placement. Market prices remain subject to feed availability. The existing adapter retrieves 1X2 and 2.5 total quotes; BTTS and expanded goal lines need per-event market integration for live prices. See [bookmaker coverage](https://the-odds-api.com/sports-odds-data/bookmaker-apis.html), [request parameters](https://the-odds-api.com/liveapi/guides/v4/) and [market catalog](https://the-odds-api.com/sports-odds-data/betting-markets.html).

Club crest assets use the API-Sports media host, with local sample club files for the current fixtures. Display/retention rights and club identity accuracy need to be covered by the deployment operator's agreement.
