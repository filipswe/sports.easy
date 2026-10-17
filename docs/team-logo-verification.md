# Team logo verification — 17 October 2026

Branch: `fix/team-logo-coverage`, based on `7606d14`. No deployment or push performed for this milestone.

## Coverage and behavior

- Added 117 real provider PNGs: 110 missing from the original 171-team hosted inventory, plus seven clubs discovered in the refreshed isolated local cache.
- All 180 current local team records resolve to reviewed crests. All 180 backend catalog entries agree with the client catalog and reference existing PNGs. Unicode-normalized names have no catalog collisions.
- All reviewed images passed signature/dimension checks and full Sharp decoding. Provider URLs and identities are recorded; additional country/name alias checks have primary identity references in the catalog.
- The shared badge tries the local cache, the supplied provider image, and finally initials. A changed club/source resets a previous image failure.

## Checks

- Ruff lint and format checks passed for backend and scripts.
- Full backend suite: 140 passed and one assertion expected the old remote image URL. Corrected that assertion to verify retained source metadata and the new cached display URL; all 17 affected provider/crest tests then passed. The entire suite was not repeated after this assertion-only correction.
- ESLint and TypeScript passed. Production Next build passed, including the final seven additions.
- All nine Playwright browser regressions passed using installed Chrome and isolated SQLite/API/web servers. Includes simulated local-image failure, provider recovery, initials fallback and recovery after team/source changes. The later seven image/catalog additions passed the affected backend and full-decode checks.
- npm audit and pip-audit reported no known vulnerabilities in the installed dependency locks.
- Dedicated reviewer completed two rounds; the missing Feyenoord/LASK client mappings were fixed in round one. Round two found no remaining issues. The seven later data-only crest additions and final documentation updates were self-reviewed.

## Remaining limitation discovered during live smoke check

The local production preview starts at `http://127.0.0.1:3101`, but its live match list currently returns no rows. Its recorded 17 October odds sweep contains 141 events, while quotes and observations still end on 14 October. A manual browser check waiting for visible fixture rows therefore timed out; live visual logo coverage was not verified.

The ingestion code captures its shared fetch time before model processing and rejects upstream quote timestamps more than one minute later than that time. The recorded long job is consistent with new prices being discarded by this check. This is a pre-existing refresh issue, not fixed by the logo milestone; investigate it and add a slow-ingestion regression next. Do not extend stale-price limits, fabricate prices or rewrite immutable quotes to hide it. The portfolio roadmap records this as a priority.

GitHub checks for this new branch have not run because it has not been pushed. Vercel's automatic deployment on Git push requires resolving the existing no-deployment instruction before pushing.
