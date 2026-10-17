# Loading and preview fix verification

Corrections validated on 14 October 2026, following the original production-readiness milestone.

## Confirmed failures and fixes

GitHub's backend/secret jobs passed on `b205f35`, while four Chromium tests timed out waiting for data. The browser traces showed 3–5-second API requests, cancelled duplicate requests and loading placeholders. The homepage match selector requested the complete market catalog: the reproduced 60-match sample response was 3,090,591 bytes.

The fix loads publication teams/competitions with one joined query, limits archive reads to the actual recommended publications, loads match context in batches and requests only fixture summaries for chat or the selected market for browsing. Regression checks enforce at most 14 listing queries, a selector payload below 60 KB for the 60-match sample, and preservation of the complete match-detail catalog. Calculations, recorded recommendations and original archived prices are unchanged.

No preview process was listening at 3101 when this repair began; the user's requested address was therefore unavailable. The corrected live preview is started separately from Docker. It retains a private ignored `.preview/` cache, skips successful fixture refreshes for 24 hours, respects the independent three-day odds schedule and keeps serving stored data during provider quota/outages. Initialization bugs remain errors rather than being disguised as provider outages. The browser proxy receives no configured provider/AI/database credentials.

## Validation

- **103 backend tests passed**, including bounded query/payload checks, archive/model invariants and seven preview-cache cases.
- **6 Chromium tests passed** with CI settings, without increasing assertion timeouts.
- Ruff checks/formatting for backend and scripts, ESLint, TypeScript, Next production build and diff/credential scans passed.
- GitHub's previously failing `web` checks passed on loading-fix commit `c2dac94` for both push and PR workflows. Latest-head checks are inspected separately after pushing the startup correction.
- Real live preview: homepage showed five recommended picks; All matches loaded 92 priced matches in the next week; a selected match detail loaded and Groq returned AI-selected analysis. Chromium reported no page errors.
- Concurrent live requests to meta/recommendations/summary/result-market endpoints returned HTTP 200 in approximately 0.21–0.28 seconds locally. The 14-day live selector payload was 54,445 bytes. These timings describe this workstation, not a production load-test guarantee.
- The live cache had mode 0600 and reported refresh not due. A real restart reused it instead of making a fresh provider sweep.

These corrections received self-review and relevant automated regression checks. The original milestone's two dedicated review rounds are recorded in milestone-verification.md; no additional independent review round is claimed.

No main merge, deployment, existing Docker restart or main-database migration was performed. Public-launch requirements and European/model/logo limitations remain in production-readiness.md.
