# Free non-commercial beta launch plan

Prepared 14 October 2026 on `feat/production-readiness`, extending the tested release candidate. The user chose Vercel Hobby and a free non-commercial beta. No hosting account, domain, operator identity or email delivery account is configured yet.

1. Prepare two Vercel projects (`web` for Next.js and `backend` for FastAPI), private environment instructions and hosted PostgreSQL configuration. Preserve the existing Docker installation and SQLite preview.
2. Adapt the API's request limiter and connection lifecycle for separate serverless instances. Keep identity, CSRF, provider budgets and immutable publications intact.
3. Add a bounded, one-shot worker command and a disabled-by-default GitHub Actions schedule. Use the existing worker's locking and cadence; document delayed scheduling and quota limits.
4. Run affected backend/browser tests, lint, types and a production build; self-review the follow-up in at most two rounds. Commit and push tested changes to the existing feature branch and update its draft PR.
5. Configure actual accounts, operator/contact details, sending credentials and provider permissions. Validate hosted email, database restoration and the complete account/pick flow before a separately approved public deployment.

The free setup is a limited beta, not an availability guarantee. Vercel Hobby must stay non-commercial. Its daily cron is insufficient for this app's four-hour feed cadence; GitHub schedules can be delayed and only run on the default branch. The proposed hourly refresh job must be explicitly enabled after approved code is on that branch. It does not reproduce the local worker's 30-second checks.

Sources: [Vercel FastAPI](https://vercel.com/docs/frameworks/backend/fastapi), [Vercel fair use](https://vercel.com/docs/limits/fair-use-guidelines), [Vercel cron limits](https://vercel.com/docs/cron-jobs/usage-and-pricing), [GitHub scheduling](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule), [Neon plans](https://neon.com/docs/introduction/plans).
