# Prime ChainSentinel: Netlify frontend + independent FastAPI backend

This is the **split-deployment** option for the existing thesis project.

- Public React/Vite dashboard: Netlify Free (`netlify.toml` at repo root)
- FastAPI: Oracle Always Free VM preferred; Render Free is a short-lived fallback.
- SQLite + uploaded MI300X evidence: backend persistent disk/volume.
- API authentication: shared demo credentials; login UI in the frontend.
- The backend should have a **stable HTTPS URL**; the Netlify frontend must
  know it at build time. Do not use a changing Cloudflare Quick Tunnel URL unless
  you are willing to update Netlify and redeploy whenever it changes.

## Step 1: backend first

Option A (recommended): run `Dockerfile.api` on an Oracle Always Free
Ampere A1 VM (if capacity is available). Allocate eligible persistent disk
and mount `/app/backend/storage` as a volume. Publish the API with a stable
HTTPS hostname (for example a free DuckDNS hostname behind Caddy, configured
with ports 80/443 and valid HTTPS). A stable Cloudflare named tunnel is also
possible with suitable DNS configuration. Do not use unencrypted public HTTP.

Option B (simple but fragile): deploy the root `Dockerfile.api` to a
**Render Free Web Service**. Set Dockerfile path to `./Dockerfile.api`.
Render provides a stable HTTPS service hostname. However, free services
spin down after 15 idle minutes, may need around a minute to resume,
have no persistent disk, and lose files **including SQLite and imported
evidence** on restarts. You will need to reimport the sample campaign and
rerun any simulations after restarts. This is a fallback, not the preferred
host for a defense.

Required backend environment variables:

```text
APP_ENV=production
MARKET_DATA_PROVIDER=yahoo
CORS_ORIGINS=https://YOUR-NETLIFY-SITE.netlify.app
PCS_DEMO_USERNAME=choose-an-username
PCS_DEMO_PASSWORD=choose-a-long-unique-password
```

On an Oracle VM with a mounted volume, set:

```text
PCS_DB_PATH=/app/backend/storage/evidence.db
```

Replace placeholders with the real URL/credentials. The Netlify URL must
be exact (scheme + hostname, no trailing slash) in `CORS_ORIGINS`.
You can add comma-separated additional approved frontend origins.
Never publish credentials in Git or a `VITE_*` variable.

Use a *single* Uvicorn worker and do not run multiple instances against
the same SQLite DB. Store all backend `storage` subdirectories persistently:
imports, reports, cache and database.

## Step 2: deploy frontend on Netlify

1. In https://app.netlify.com/, select **Add new project -> Import an
   existing project**. Connect the repository `FabianS10/Prime-Chainsentinel`.
2. Select the branch with the latest approved code (usually `main` after
   merging the deployment PR).
3. Netlify reads the root `netlify.toml` with these build values:

   ```text
   Base directory: frontend
   Build command: npm ci && npm run build
   Publish directory: dist (relative to frontend)
   ```

4. In project environment variables set:

   ```text
   VITE_API_BASE=https://YOUR-STABLE-HTTPS-BACKEND-HOST
   ```

   It is a public *address*, not a secret. The URL is embedded into the
   Vite bundle during `npm run build`, so update and redeploy if it changes.
5. Deploy Netlify. Copy its final `https://...netlify.app` hostname
   to the backend `CORS_ORIGINS` and restart/redeploy FastAPI.
6. Open the Netlify URL. The frontend checks the API and, if protected,
   displays its own username/password login form. Credentials remain in
   browser memory (not in localStorage) and are sent to the API on every
   request, including ZIP uploads and PDF report generation.

Important: do **not** work around CORS by putting Netlify's 26-second
proxy rewrite in front of Monte Carlo endpoints. Use the direct HTTPS
FastAPI URL with properly configured `CORS_ORIGINS`; proxy timeouts
can break long-running simulations and report generation.

## Step 3: end-to-end defense checks

1. Open backend `https://BACKEND/health`; confirm status `ok`.
2. Open Netlify from a different network; log in.
3. Import `sample_data/MI300X_Benchmarks.zip` using the frontend.
4. Open Hardware, GPU, Hash, Merkle, Blockchain, and Evidencia; confirm
   imported campaign, source identifiers, and **SURROGATE** warnings.
5. Verify SHA-256 and upstream/downstream provenance.
6. Fetch real Yahoo Finance market data; execute Monte Carlo and model
   comparison on the same observation series and export an actual PDF.
7. Restart the backend and verify that the evidence still exists on the
   persistent-host option. On Render Free, it **will not** persist.
8. Keep a local Docker backup, especially if any live Yahoo call is
   unavailable. Never claim synthetic data was actually fetched.
