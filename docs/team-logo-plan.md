# Team logo coverage plan

1. Inventory all live teams and resolve only their recorded provider logo URLs or reviewed crest identities.
2. Cache validated PNGs for every current team and keep the backend/client catalogs consistent, preserving existing assets.
3. Prefer cached images, retry the provider image when needed, and reset failed-image state when the team changes.
4. Verify catalog/image coverage, browser fallback and shared UI usage; run relevant lint, types and build checks.
5. Review the change and commit it locally. A push now triggers Vercel deployments, so obtain approval before pushing under the existing no-deployment instruction.
