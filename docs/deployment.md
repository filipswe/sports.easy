# Deployment runbook (not deployed)

Nothing has been published or purchased. Begin with the Docker Compose stack locally. A serverless frontend host cannot keep the Python worker running indefinitely.

## Recommended small deployment

One TLS reverse proxy, a Next.js Node service, a single FastAPI process, one permanent worker and managed PostgreSQL. Route `/api/*` to FastAPI under the same public origin and all other paths to Next. If relying on Next's rewrite instead, build with the correct private `API_INTERNAL_URL` (rewrites are captured at build time). Never expose the database or unrestricted provider access to the internet.

A separate web host can serve Next.js if it supports the required same-origin proxy. The Python API and worker need a persistent service/container host; the worker has no public port. Provider calls run there, not in edge/browser code.

## Configuration and release

1. Set up a managed PostgreSQL database with TLS, a least-privilege application user, separate migration credentials where practical, private access and automated encrypted backups. Choose a region deliberately.
2. Create secrets in your deployment secret manager: strong unique `SESSION_SECRET` (at least 32 random characters), database URL and passwords, provider keys, SMTP credentials. Set `COOKIE_SECURE=true`, `PUBLIC_ORIGIN=https://your-real-host`, and `APP_ENV=production`. Do not use placeholder values. The brand does not imply domain ownership.
3. Configure SMTP and a verified sending domain. Live email auth refuses to return development verification links. Demo link-return mode is local-only and must never be exposed publicly.
4. Complete provider entitlement/rights review in `providers.md`. Set league/season, region and conservative budgets. Switch to `APP_DATA_MODE=live` in a separate database. Set `LIVE_RETENTION_APPROVED=true` only after review. Missing keys produce unavailable data, never demo replacement.
5. Run the test suite, audit dependencies, build pinned assets, scan images, and record image digests. Tagged Dockerfiles are pinned to patch versions; lock exact deployment digests in your hosting release configuration.
6. Pause the worker and take a backup. Run `alembic upgrade head` once. Start the API and check `/api/ready`, then worker, then web. Verify a single provider ingest and the protected status page. Review unmatched fixtures and quotas. Register/verify an operator account and promote it through the private CLI; there is no default admin.
7. Set TLS/HSTS and a ≤32 KiB request body limit at the edge. Configure a shared client-IP-aware edge rate limiter before multiple API processes; the application limiter is process-local and the Next proxy may collapse IPs. Configure CSP nonces if tightening the current inline policy. Preserve Origin headers. CORS remains disabled unless you explicitly implement an exact-origin cross-origin deployment.

## Backup and restore

Example local PostgreSQL backup (contains personal data; keep outside git):

```sh
docker compose exec -T db pg_dump -U sports -d sports_easy -Fc > /secure/backups/sports_easy.dump
```

Restore into a **new, empty database**, not the running production database:

```sh
createdb sports_easy_restore
pg_restore --no-owner --dbname=sports_easy_restore /secure/backups/sports_easy.dump
```

Use provider-specific managed database tooling where required. Test restoring and checking migration revision, foreign keys, publication counts, user login and saved snapshots. Encrypt backups, restrict access and document a retention/expiry policy. Account deletion removes active records, but backup expiry must be handled operationally. Do not delete published research selectively to improve performance figures.

## Observability and costs

Collect structured API/worker logs without request bodies, provider URLs containing keys, session cookies or reset links. Alert on failed/unavailable jobs, readiness failures, exhausted quota, missing source timestamps, unresolved fixtures and price age exceeding the configured limit. `/api/admin/status` shows recent runs, job states, configured budgets, credential presence, coverage and model version. `/api/meta` shows data fetch time. An external error-reporting vendor is not configured; connect one after choosing privacy-safe scrubbing rules.

Main cost drivers: web/API/worker compute, managed PostgreSQL/storage/backups, provider quotas/history entitlement and SMTP. No LLM billing exists in this MVP. Budget for API-Football's required seasons and odds credits based on the explicit formula in `providers.md`; do not assume free plans support near-kickoff continuous polling. Monitor append-only snapshot growth. The app intentionally does not auto-purchase or increase plans.

## Rollback

Keep the previous immutable images and configuration. Stop the worker first. Roll back application images if the schema is backward-compatible. Prefer a forward corrective migration over destructive down-migrations. If a restore is necessary, restore into a new database, validate it, and change the connection secret under maintenance; retain the old database for an audited reconciliation. Never overwrite published probabilities to repair a report. The initial migration downgrade drops tables and is appropriate only for disposable test databases.

## Before public release

Confirm provider retention/display permissions and bookmaker market rules; obtain jurisdiction-specific review of legal/age/privacy notices; verify SMTP, cross-user authorization, trusted proxy configuration, TLS, rate limits and backup restores; run real-provider contract tests; benchmark the latest-snapshot queries; validate genuine holdout performance before claims. No legal compliance or production-readiness certification is implied by the working portfolio demo.
