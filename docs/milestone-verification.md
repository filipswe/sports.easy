# Production-readiness milestone verification

Validated locally on 14 October 2026, against baseline `5485aa6` on feature branch `feat/production-readiness`.

- Backend: **94 tests passed**; Ruff lint and formatting passed. One upstream Starlette/httpx test-client deprecation warning remains.
- Web: ESLint, TypeScript and the Next production build passed.
- Chromium: **6 end-to-end tests passed**, including homepage analyst inputs/fallback, recommended-pick chronology, form/first-half markets, custom/suggested parlays, save/reopen, accounts, Performance and desktop/mobile navigation. The chat mobile screenshot was visually inspected; no horizontal overflow.
- Disposable PostgreSQL 17.11: migration through `007_observations`, persisted demo seed, SQL immutability for publications/recommendations/quote observations, worker advisory locking, duplicate-job handling and six concurrent chat reservations (exactly one permitted) passed. The temporary container was removed.
- Dependency audits: npm and pip-audit reported **no known vulnerabilities** for the pinned dependency manifests.
- Credential scan: 169 tracked/prospective files checked against configured provider/session/database secrets; no matches. `.env` remains ignored. No credentials were staged.
- Isolated real-data preview: 3,504 domestic fixture records ingested; **141 priced upcoming matches**, all eight competitions represented and chronological. Champions League 9, Europa League 18 and Conference League 17 priced matches were inside the 14-day window. Counts/prices are a point-in-time observation, not an expected fixed catalog size.
- Groq: account/model availability verified. One grounded application request with strict structured output returned HTTP 200 and `source=ai`; invalid output/provider failures have deterministic fallback coverage. No unrestricted generated statistics enter the UI.

## Independent review

A dedicated read-only reviewer completed two rounds. Round one found stale prices surviving kickoff changes, optional European outages blocking domestic settlement, inaccurate custom-parlay ranking wording and incomplete counter-retention wording. All were fixed, covered by relevant regression checks and confirmed resolved in round two. No remaining serious findings were identified. There were no additional review/fix rounds.

## Remaining release requirements

The readiness command on this workstation reports PostgreSQL persistence for native configuration, HTTPS/secure cookies, SMTP, operator/support contact and the old 12-credit daily budget as configuration blockers. The isolated preview overrides its own budget to 20. No existing `.env` cadence or Docker deployment was changed. Existing Docker database/services remain on their current version.

Public launch also needs operator-specific policies/provider/logo permissions, restored-backup and staging checks, edge rate limiting/monitoring and real prospective model validation. European markets currently have real prices but no unsupported model estimates; unknown club logos use initials. See [production-readiness.md](production-readiness.md).

The real preview and test servers were stopped. No deploy, main merge, force-push, paid purchase or existing database migration was performed.
