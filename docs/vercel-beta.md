# Vercel Hobby beta setup

This is the approved **free, non-commercial beta** hosting plan. The application has not been published. The new Neon database was initialized at the user's explicit request. The existing Docker installation and `127.0.0.1:3101` preview are separate.

## Accounts to create

1. [Vercel](https://vercel.com/signup), using Hobby. Keep the beta free of advertising, paid services and affiliate monetization. Use the supplied `.vercel.app` domain initially; a purchased domain is optional.
2. [Neon](https://console.neon.tech/signup), using Free PostgreSQL. Create a separate beta project in **AWS Europe Central 1 (Frankfurt)**; both Vercel projects are configured for matching region `fra1`. Enable only Postgres; object storage, Functions, AI gateway and Neon Auth are unnecessary for this application. Use the **direct** TLS connection for the API and worker, because the existing worker uses session-level advisory locks. Plain `postgresql://` provider URIs are accepted and normalized to the installed Psycopg driver internally. Copy the URI, not a complete `psql` command, and keep it private.
3. An email sender and support inbox. A dedicated Gmail account with two-step verification and an app password can support a small beta if that account permits app passwords. Use `smtp.gmail.com`, port 587, STARTTLS, the account address as `SMTP_USER`/`SMTP_FROM`, and the app password as `SMTP_PASSWORD`. Google applies sender limits; real delivery must be verified. A verified sending domain and dedicated transactional service are preferable when moving beyond the beta.

“Operator name” identifies the person or business running the site; sports.easy is the product brand. The owner must choose the public operator identity and contact address. Blank values remain launch blockers. Product legal pages are drafts and do not establish an operator's legal status.

## Private configuration

Use ignored `.env.beta`, based on `.env.beta.example`. It is separate from the running local `.env`. The prepared local file contains a newly generated session secret, privately copied provider keys and the new Neon application connection. The canonical website origin, Gmail app password and operator identity remain unconfigured. No credentials are committed.

The newly created Neon database has been initialized through `007_observations`. A restricted `sports_easy_beta_app` role is configured privately as `DATABASE_URL`; it can use application tables but cannot create schema objects or update the migration revision. Owner credentials are retained only as local `MIGRATION_DATABASE_URL`. Do not copy the migration credential to Vercel or the refresh runner. Future migrations use that owner credential privately; application hosts use the restricted role.

The chosen public support address is `sportseasycontact@gmail.com`. Proposed Gmail sender settings are saved privately; its app password, operator identity and canonical hosted origin are still required. No email has been sent.

Run from the repository root:

```sh
.venv/bin/python scripts/check_beta.py
```

This reports blocker names without connecting or showing secret values. Before approval, fill `DATABASE_URL`, `PUBLIC_ORIGIN`, `OPERATOR_NAME`, `SUPPORT_EMAIL` and SMTP settings. `PUBLIC_ORIGIN` must be the exact permanent frontend HTTPS origin, without a trailing slash. The database URI must contain `sslmode=require`, `verify-ca` or `verify-full`.

Review football-data.org, The Odds API, Groq processing/privacy and crest publication rights for this actual public project. Set `LIVE_RETENTION_APPROVED=true` only after that review; the private preview's prior approval is not copied automatically.

## Projects to configure after deployment approval

Create two projects from this repository's approved release commit. Keep stable production URLs; automatically generated preview URLs need isolated data/configuration and are not the beta's canonical account origin.

| Project | Root directory | Framework | Environment |
|---|---|---|---|
| Website | `web` | Next.js, Node 24 | Only `API_INTERNAL_URL=https://<permanent-backend-host>` is needed from this setup |
| API | `backend` | FastAPI, Python 3.13 | The private beta settings above |

Vercel detects `backend/app/main.py`. `backend/vercel.json` allows up to 300 seconds with Fluid compute and explicitly includes the reviewed crest catalog. The application never launches its permanent worker in a function. The website proxies `/api/*` to the configured backend, preserving the browser's same-origin account flow; the backend `PUBLIC_ORIGIN` remains the **website** origin. API/provider/database/session/email secrets belong only in API/GitHub environment settings, never in `NEXT_PUBLIC_*` variables or the frontend project.

The website deliberately fails a Vercel build when the backend origin is missing or unsafe, instead of publishing a page that calls localhost. The API uses no idle SQLAlchemy connection pool on Vercel. Production request budgets are atomic in PostgreSQL and survive instance restarts; short-lived keys contain a keyed IP digest, not a raw IP. The limiter uses the platform-supplied ASGI peer and does not trust arbitrary forwarded headers. The hosted proxy/peer behavior must be verified; multiple visitors may share a conservative budget until a reviewed platform-specific client-IP configuration is validated.

Initial migrations were applied once to the verified empty Neon database. Future migrations use the separate owner credential before starting the API. Do not put migrations or ingestion in the Vercel build command, and do not restore/replace the running local databases.

## Background refresh

`.github/workflows/beta-refresh.yml` is disabled unless the repository variable `ENABLE_BETA_REFRESH=true` is explicitly set. It uses the GitHub environment `beta`, a concurrency group and a 20-minute execution cap. The workflow has an hourly schedule at minute 17 and a manual trigger; schedules only work after the workflow is on the repository's default branch. No merge is performed by this preparation.

Create these GitHub environment secrets privately: `BETA_DATABASE_URL`, `BETA_SESSION_SECRET`, `BETA_FOOTBALL_DATA_KEY`, `BETA_API_FOOTBALL_KEY` when optional logo lookup is used, `BETA_ODDS_API_KEY`, `BETA_SMTP_USER`, `BETA_SMTP_PASSWORD`.

Create these variables: `BETA_PUBLIC_ORIGIN`, `BETA_RETENTION_APPROVED`, `BETA_OPERATOR_NAME`, `BETA_SUPPORT_EMAIL`, `BETA_SMTP_HOST`, `BETA_SMTP_FROM`. The database/session/provider values must match the API project. Migrations must be complete before enabling the job.

The runner calls `python -m app.cli refresh` from `backend`, exits, and reports failure when ingestion is unavailable or fails. It reuses the existing database lock, four-hour fixture/results cadence, three-day odds cadence and quota guards. It does not create an externally callable ingestion endpoint.

Before enabling the hosted refresh, stop redundant local refreshers using the same provider account. Quota ledgers are shared across processes using one database, but independent preview/Docker/beta databases do not share an account-wide ledger. Keep the existing local installation preserved; coordinate which worker is active before the hosted release.

This hourly beta schedule does not match the local worker's 30-second checks. GitHub can delay or drop scheduled jobs and disables inactive public-repository schedules after 60 days. Settlements may therefore lag; the interface never substitutes results. Monitor failures and current coverage. GitHub runner allowances depend on repository visibility/account, and Neon/Vercel free limits can suspend service. Do not silently upgrade or incur paid usage.

## Hosted validation before opening the beta

- Verify PostgreSQL migrations and restoration into a separate disposable database, then actual readiness through the website proxy.
- Verify the permanent frontend origin, HTTPS, secure session cookies and rejection of wrong-origin mutations.
- Test registration, email verification, login, reset, account deletion and saved picks with the chosen sender. No local verification links may appear in public responses.
- Verify provider keys are absent from browser assets/responses, real prices and model/source labels, all team images, chat fallback, mobile navigation and the existing European settlement limitations.
- Run one explicit refresh, check quotas/identity mapping, then enable the schedule. Check trusted peer/IP behavior and shared request limits on the real hosting path.
- Configure monitoring that respects free allowances, backup handling and privacy/contact text. Do not claim validated predictive accuracy.

Sources checked 14 October 2026: [Vercel fair use](https://vercel.com/docs/limits/fair-use-guidelines), [FastAPI support](https://vercel.com/docs/frameworks/backend/fastapi), [Fluid limits](https://vercel.com/docs/functions/limitations), [daily Hobby cron](https://vercel.com/docs/cron-jobs/usage-and-pricing), [Neon Free limits](https://neon.com/docs/introduction/plans), [GitHub schedules](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule), [Google app passwords](https://support.google.com/mail/answer/185833), [Gmail sender limits](https://support.google.com/mail/answer/22839).
