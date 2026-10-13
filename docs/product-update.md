# Matchday product update

The main navigation is Home, All matches, Parlays, Performance and How it works. The light interface uses club crests, compact fixtures and a persistent parlay selection on this browser. The old Research Builder route redirects to All matches; its API remains for existing integrations.

## Recommended picks

The worker freezes up to five official recommendations, with one pick per fixture. Eligible priced outcomes are ranked by estimated model probability; the recorded pick stays unchanged. Live recommendations require fresh prices. The worker fills vacancies as matches finish or become unavailable. Performance counts only these official picks at their original publication and odds. Existing quotes, saved records, model versions and settlement revisions remain in the database.

## Markets and analysis

Model estimates cover 1X2, BTTS, totals at 0.5–4.5, double chance, team totals at 0.5–2.5, first-half totals at 0.5–2.5, and correct scores (0–4 each plus other scores). Full-time markets use a common score model. First-half goals use a separate fit to recorded half-time scores with the same minimum-history requirements. Missing half-time history produces no first-half estimates. Cards, corners, players and every Solcasino market are not implemented.

Bookmaker prices exist only where the feed supplies an accepted quote. Current sample data prices 1X2, totals 2.5 and BTTS. Expanded markets can be selected and analyzed; a dash indicates there is no quote. Entering a decimal price for every leg calculates a user-price total, labelled separately. Model probabilities are never used to invent sportsbook prices.

## Parlays

Users select one pick per match, up to eight matches. Different matches with a repeated club are rejected. The server verifies each selection, its current probability and fixture status. It multiplies independent-match probabilities and prices from one common source. This independence approximation is explicit. Suggested parlays search available priced outcomes within requested combined-odds bounds (2–5 legs), with bounded search across at most 18 fixtures. They are the strongest combinations found, not a claim of exhaustive optimization. Prices and outcomes may change.

Selections and up to 30 saved parlays use browser local storage. Saved single picks remain tied to an authenticated account in the database. Browser parlay saves do not sync between devices. Opening a saved parlay refreshes its analysis; fixtures that have started are rejected rather than reused as upcoming events.

## Single sportsbook feed

The product uses one odds source; multi-bookmaker comparison is removed from the user flow. `ODDS_BOOKMAKER_KEY=pinnacle` selects Pinnacle through The Odds API, whose `bookmakers` parameter takes precedence over its region filter. Real live use requires configured API-Football and The Odds API credentials and display/retention rights. Current live ingestion covers 1X2 and totals 2.5; additional market prices need the provider's per-event feed integration. Sample prices are labelled Demo Sportsbook throughout the matchday flow. The older audit/research endpoints preserve their original quote records.

## Club crests

The twelve sample clubs use local API-Sports crest PNGs. Additional API-Football club identities use that provider's corresponding crest URL. A text fallback handles image failures. Image display rights must be covered by the provider agreement before commercial operation. No club endorsement is implied.
