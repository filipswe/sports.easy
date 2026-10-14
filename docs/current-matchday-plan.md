# Current matchday, complete goal-line browsing and continuous preview

Continue `feat/production-readiness` / draft PR #1. Preserve Docker, existing accounts, private keys and immutable records.

1. Expand featured eligibility to all eight competitions and choose the earliest Europe/Belgrade calendar matchday. Add a clearly identified odds-based baseline for European events without sufficient history; retain original official picks in Performance while showing current assessments before kickoff.
2. Show all genuinely quoted full-time/first-half goal lines together, with a specific-line filter. Include the primary first-half market in cached detail requests; preserve source identity, separate line prices and quota guards.
3. Run a quota-bound worker with the isolated preview. Refresh domestic results more often, update European results through verified score coverage and preserve ambiguous results as pending. Refill the next matchday after games start/settle; periodically refresh open UI views.
4. Address the extension-induced hydration interruption using a production preview and a Dark Reader opt-out for the bright app. Verify without suppressing genuine hydration bugs.
5. Regression tests, lint/types/build, self-review (up to two rounds), focused commits/pushes, README/PR update and final GitHub verification. No merge or deployment.
