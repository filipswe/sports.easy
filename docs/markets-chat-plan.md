# Markets, crests and natural-language analyst

Continue on `feat/production-readiness` / PR #1. Preserve the running Docker installation, private keys and immutable published records.

1. Support imported Pinnacle BTTS, double chance, alternate half-goal lines and first-half totals. Extend prediction/settlement helpers coherently; fetch detail odds on demand with bounded, cached, serialized provider requests and existing quotas.
2. Rename the browsing tab to Under/over goals, add a goal-line selector, show only genuinely priced live outcomes/matches for the chosen market, and omit missing model percentages rather than display Unavailable.
3. Verify and fill all current club crests through provider club metadata, with reusable reviewed aliases and bounded future backfill.
4. Replace the chat match dropdown with free-form questions. Resolve clubs/matches from current fixtures and context through a constrained AI router plus deterministic fallback; ask a concise follow-up for ambiguous references. Render grounded match/pick facts only.
5. Add relevant regression/browser checks, lint/types/build, self-review, README/coverage updates and focused commits/pushes. Verify GitHub checks and restart the isolated live preview on 3101.

Free-tier limits: additional markets cost per event/returned market. Cache repeated requests, limit batches and preserve monthly/daily quotas; never fabricate missing prices or model probabilities. No paid service, main merge or deployment is authorized.
