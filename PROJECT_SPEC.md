# sports.easy project specification

Consolidated on 14 October 2026 from the original attached brief and the current milestone. This file was absent from the repository before this milestone.

## Product

An adult football research application with a bright, accessible interface, real single-bookmaker prices, chronological match browsing, model recommendations, specific explanations, custom/suggested parlays, accounts and an immutable performance archive. The brand is sports.easy; the slogan is “Betting made easy.”

## Current milestone

- Browse only upcoming matches with a genuine supported quote in live mode; sample prices remain explicitly labelled in demo mode.
- Use all eight competitions: top five domestic leagues and European competitions within 14 days. Feature the earliest Europe/Belgrade calendar matchday and roll forward after kickoff/settlement. When verified history is absent, a separately labelled market baseline may use complete real 1X2 prices.
- Preserve statistical probabilities and independent-match parlay multiplication. Friendly confidence wording must match the actual estimate; never inflate percentages or claim certainty.
- Replace the homepage odds-multiplication illustration with a pick-analysis chat. AI commentary must use stored match facts and model estimates, acknowledge missing inputs and never create prices/probabilities. Without an AI credential, provide a clearly identified data-backed fallback.
- Retain “Current odds” public labels without update timestamps. Keep source timestamps and freshness checks internally.
- Refresh odds every three days with quota guards; refresh domestic status/results every four hours and official European results through quota-bound regulation-safe checks. Run the worker with the preview; open pages refresh cached data every minute.
- Prepare a reviewable production candidate, dependency/security checks, setup/preview documentation, concrete release blockers and a concise product backlog.

## Invariants

- Never substitute synthetic records in live mode or fabricate unavailable history, logos, injuries, lineups, xG or model confidence.
- Preserve existing accounts and immutable predictions, quotes, recommendations and settlement revisions.
- Require CSRF/Origin verification, protected account access, private server credentials, bounded provider requests and conservative budgets.
- Public production requires HTTPS, secure cookies, SMTP, PostgreSQL, reviewed provider/display rights and operator-specific policy/contact configuration. A working local build alone is not a production deployment.
- No bet placement, payment processing, wallets or sportsbook-account access.

## Delivery

Use a feature branch, relevant tests/lint/types/build/audits, a dedicated reviewer with no more than two review/fix rounds, milestone-only commits and a draft PR when GitHub authentication permits. Do not merge, deploy, force-push, purchase services or commit secrets. Preview must be isolated from the running main installation and its database.
