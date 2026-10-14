# Production readiness milestone

Branch: `feat/production-readiness`. Baseline: `5485aa6`.

1. Filter match browsing by usable single-bookmaker quotes. Support quote-only markets with unavailable estimates instead of invented probabilities; keep archives immutable.
2. Add a 14-day European competition window, provider-backed fixture/result ingestion and independent three-day odds scheduling. Preserve domestic model separation and quota limits.
3. Add a homepage analyst chat with selected-match grounding, bounded history/output, persistent request budgets and an optional Groq adapter; remove the multiplication illustration. Improve parlay wording without changing calculations.
4. Harden release configuration and operational checks, update setup/preview documentation, and record production blockers and a short prioritized idea backlog.
5. Run backend/web/browser/PostgreSQL checks and production builds. Request an independent review, fix confirmed findings in at most two rounds, then commit/push this branch and open a draft PR.

Preview uses disposable SQLite data and separate local ports; the existing Docker installation remains untouched. Provider keys remain in ignored configuration. The Groq credential is configured only in ignored server configuration. AI chooses trusted evidence rather than generating unverified numbers. European markets initially have real quotes without unsupported model estimates.

Acceptance focuses on genuine prices, no out-of-window cup fixtures, correct/missing parlay estimates, grounded chat responses, authentication/CSRF, quota behavior, immutable archives and responsive keyboard-accessible UI.

Completed: priced browsing, European event coverage, separate odds cadence, grounded chat, release gates/runbook, isolated preview, checks and two independent review rounds. European estimates/unknown logos are explicitly unavailable rather than fabricated. Delivery continues with milestone-only commits, branch push and draft PR.
