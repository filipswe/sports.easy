# Loading and CI correction

1. Inspect the failed GitHub logs/traces and reproduce startup without modifying the existing Docker installation.
2. Remove repeated per-row database reads and send lightweight match data to browsing/chat selectors; preserve original archived picks and all detail markets.
3. Make live preview restarts reuse a separate ignored cache, respect refresh intervals and handle provider failures clearly.
4. Add regression checks for bounded query counts, payloads and preview initialization. Run backend/web/browser/build checks, self-review, commit and push corrections to PR #1, and verify the new GitHub run.

Evidence: backend/secrets jobs passed. Four browser checks failed after five seconds while requests were still loading; traces show API requests taking approximately 3–5 seconds and the match selector transferring all match markets. No preview was running at 3101; 3000 continued serving the existing Docker build.
