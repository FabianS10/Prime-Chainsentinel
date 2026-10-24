# Prime ChainSentinel: Railway deployment

Single service: React and FastAPI share the same HTTPS origin. A Railway volume
preserves imported evidence, hashes, SQLite, market cache, and generated reports.
No AMD MI300X is needed at runtime to analyze previously imported campaigns.

## Deploy

1. Merge this pull request into `main`. Create a new Railway project from GitHub
   repository `FabianS10/Prime-Chainsentinel`. The root `Dockerfile` is
   autodetected.
2. In service **Variables**, set these variables in Railway (never in GitHub):

   ```text
   APP_ENV=production
   MARKET_DATA_PROVIDER=yahoo
   PCS_DEMO_USERNAME=<choose-a-username>
   PCS_DEMO_PASSWORD=<choose-a-long-random-password>
   ```

   The demo credentials protect all endpoints except `/health`. The frontend
   and API have the same origin, so do not set `VITE_API_BASE`.
3. Add a Railway persistent **Volume** to the service with **Mount Path**:

   ```text
   /app/backend/storage
   ```

   The database is at `/app/backend/storage/evidence.db`. Evidence imports,
   financial cache, and PDFs all use subdirectories of this folder.
   **Do not skip this step:** otherwise records can disappear on redeploy.
4. Use **Settings > Networking > Generate Domain** to get a public
   `https://...up.railway.app` URL. Optional healthcheck: `/health`.
5. Visit the public URL and sign in using your demo credentials. In
   **Evidencia**, upload `sample_data/MI300X_Benchmarks.zip` from the
   repository, then test GPU/Hash/Merkle, provenance verification, market
   queries, Monte Carlo, and PDF export.
6. Restart or redeploy once to verify that evidence survives. Configure regular
   volume backups for irreplaceable files.

## Security and limits

- This is a shared-password single-user thesis demo, **not** a multi-tenant app.
  The same database and evidence are visible to anyone with the demo password.
  Keep the password private and rotate it if exposed.
- Without both `PCS_DEMO_USERNAME` and `PCS_DEMO_PASSWORD` set, the
  existing endpoints remain available without authentication. **Configure
  both before generating or sharing the public domain.**
- Keep one service replica and one Uvicorn worker while using local SQLite.
- Yahoo Finance is external and may throttle or fail independently of hosting.
- Railway bills usage; review current price plan, volume size, and limits.
- The public repository was last updated on 2026-10-06 when inspected.
  If you have a newer verified local copy, sync it before deploying.
