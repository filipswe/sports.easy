# Football and odds providers

Provider documentation reviewed on **14 October 2026**. The preferred local setup is free; the [activation guide](live-setup.md) contains exact settings. Base feeds run in the worker. Expanded market views request bounded, cached detail prices through the backend.

| Provider | Integration | Free limits and coverage | App limits |
|---|---|---|---|
| football-data.org v4 | `/competitions/{code}/matches` for current and previous seasons; regulation results, halftime results when present, kickoff/status, teams and supplied crests | Top five leagues included; delayed scores/schedules; 10 calls/minute. Current and previous EPL seasons were verified on the configured Free account | Previous-season denial is optional; current-season denial fails explicitly. Insufficient club history suppresses estimates. No injuries, lineups or xG integration |
| The Odds API v4 | `/sports/{sport}/odds` for eight competitions, one bookmaker (`pinnacle`), plus `/events/{id}/odds` for additional markets | Verified Starter account supplied real Pinnacle EPL prices; 500 credits/month | Retains 1X2, BTTS, double chance and half-goal full-time/first-half lines; detailed markets verified on a Champions League event. Availability varies by event; no whole/quarter Asian lines |
| API-Football v3 | Existing `/fixtures` adapter for two seasons per league; choose `FOOTBALL_PROVIDER=api-football` | Free 100 requests/day, limited seasons. Configured Free account rejected season 2026 | Free `/teams?search=...` verified for current missing club crests; optional alternate fixtures provider still requires season entitlement |
| Demo | Deterministic synthetic five-league history, future fixtures and prices | No network or account | Explicit sample labels. Not real results, prices, form or predictive validation |

Sources: [football-data.org pricing](https://www.football-data.org/pricing), [coverage](https://www.football-data.org/coverage), [match reference](https://docs.football-data.org/general/v4/match.html), [competition reference](https://docs.football-data.org/general/v4/competition.html), [rate limits/null values](https://docs.football-data.org/general/v4/policies.html), [The Odds API reference](https://the-odds-api.com/liveapi/guides/v4/), [market catalog](https://the-odds-api.com/sports-odds-data/betting-markets.html), [API-Football pricing](https://www.api-football.com/pricing).

## Refreshes and quota

Free settings use `POLL_SECONDS=14400`, `ODDS_POLL_SECONDS=259200`, `ODDS_DAILY_BUDGET=64`, `ODDS_EVENT_DAILY_BUDGET=32` and a UTC calendar-month odds budget of 450. Each eight-competition base sweep reserves 16 credits, approximately 160–176/month. A detail request reserves up to five credits per event, caches for three days and serves batches of up to six. Detail requests, retries and verification calls use the remaining allowance. Reservations persist before requests and failed attempts count conservatively. The provider's own billing reset can differ from the calendar guard.

Football requests reserve 10 calls for two seasons across five leagues; the adapter caps itself at ten requests per minute. No current-season access is assumed from a valid key. Earlier history can be unavailable on an account, so the model needs sufficient accessible results before offering a pick.

The public odds label is **Current odds**, with no update timestamps or price-age badges. Backend timestamps and stale-price flags remain intact: age is measured from the bookmaker's source update time, not fetch time, with a 600-second freshness threshold. Three-day-feed recommendations and parlay suggestions can use real snapshots verified within 72 hours. Faster feeds require fresh quotes. Current-value and positive-EV filters always exclude stale prices. Stronger picks arriving through new coverage can enter the shortlist; earlier publications, prices and probabilities remain unchanged in Performance. Pricing is not continuous and there is no hardcoded guarantee about upstream update cadence.

Fixed hosts, 15-second timeouts, up to three attempts and backoff apply. A 429 stops that job. PostgreSQL advisory locking and scheduling buckets prevent overlapping jobs. Changing the football provider uses a separate job key. Sanitized request status/quota and unmatched-event counts remain available to administrators.

## Source identity, history and display

The internal five-league catalog maps API-Football IDs 39/140/135/78/61 to football-data.org PL/PD/SA/BL1/FL1 and The Odds API sport keys. Source team/fixture IDs are namespaced, preserving demo records and avoiding accidental identity reuse. Only exact canonical names or reviewed provider aliases match prices, with a 15-minute kickoff tolerance, competition and home/away direction checks. Unknown or ambiguous matches are rejected rather than guessed.

The initial Pinnacle sweep exposed 39 club-name differences. `backend/app/team_aliases.py` records those exact names against club IDs checked using the football-data.org current-season team endpoints. Installation requires that source identity to exist and refuses to overwrite a conflicting mapping. New names remain unmatched until reviewed. Importing an already fetched odds snapshot after review preserves its original source and fetch timestamps and consumes no additional provider credits.

Imported past results become available at first observation, preventing a bulk import from pretending to support an earlier backtest. Only verified regulation results train/settle markets; extra-time totals and unconfirmed kickoff times are excluded. First-half estimates use recorded halftime results separately. The baseline remains unvalidated until real out-of-sample records support stronger claims.

Review [football-data.org terms](https://www.football-data.org/client/register) and [The Odds API terms](https://the-odds-api.com/terms-and-conditions.html) before enabling the retention gate. The live footer provides required football-data.org attribution. Its data must cease being referenced after account cancellation. Logos have separate intellectual-property ownership; a feed token does not grant public commercial publication rights. Crest URLs are limited to the football providers' asset hosts. The Odds API permits analytical display and data retention but prohibits raw-data resale.

Live mode does not substitute demo fixtures, prices, history or recommendations. Unquoted live outcomes are hidden.

Reviewed club identities and asset sources are recorded in `backend/app/club_crests.json`; 63 missing European crests are cached locally. Optional future API-Football lookup requires a unique exact normalized name and an allowed provider asset host. Public commercial crest rights still require operator review. Changing an established live installation's football provider needs an isolated database or reviewed identity migration.
