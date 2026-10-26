# Prime ChainSentinel: Native Render (Python) + Netlify (React)

This is the minimal split-cloud configuration for a thesis demonstration.
**Docker is not required or used.** It does not change the simulation
engines, data ingestion, provenance contract, or historical evidence files.

## A. Backend on Render Free

1. Open https://dashboard.render.com and create a **Web Service** linked to
   `FabianS10/Prime-Chainsentinel`. Use the branch
   `deploy/render-native-netlify` until this PR has been merged.
2. Configure:

   | Setting | Value |
   |---|---|
   | Language | Python 3 |
   | Root Directory | `backend` |
   | Build Command | `pip install -r requirements.txt` |
   | Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1` |
   | Instance Type | Free |
   | Health Check | `/health` |

   The root `render.yaml` describes the same native Python configuration,
   and can alternatively be used as a Render Blueprint if desired.
3. Environment variables:

   ```text
   PYTHON_VERSION=3.11.11
   APP_ENV=production
   MARKET_DATA_PROVIDER=yahoo
   PCS_DEMO_USERNAME=<your-username>
   PCS_DEMO_PASSWORD=<unique-private-password>
   CORS_ORIGINS=https://YOUR-SITE.netlify.app
   ```

   Use actual values. Configure the Netlify hostname in `CORS_ORIGINS`
   once assigned. Keep the credentials exclusively in Render settings.
   Production mode refuses protected requests if either credential is missing.
4. Deploy, then confirm `https://YOUR-SERVICE.onrender.com/health`
   responds with a JSON status of `ok`.

**Important:** A fresh deployment has *no imported campaign*. Nothing
automatically loads the sample package. Render Free uses ephemeral filesystem
storage; all database records, imports and reports are lost whenever
the instance sleeps, restarts or redeploys.

## B. Frontend on Netlify Free

1. At https://app.netlify.com import the same GitHub repository and select
   branch `deploy/render-native-netlify` (or `main` after merge).
2. The root `netlify.toml` sets base `frontend`, build
   `npm ci && npm run build`, publish `dist`.
3. Configure this build variable before deploy:

   ```text
   VITE_API_BASE=https://YOUR-SERVICE.onrender.com
   ```

   Do not add `/api` to the end, and never put passwords in `VITE_*`
   variables. Changing this URL requires a new Netlify deployment.
4. Deploy Netlify and update Render's `CORS_ORIGINS` to the exact
   resulting `https://YOUR-SITE.netlify.app` URL. Redeploy/restart Render
   for the environment-variable change to take effect.
5. Open Netlify, log in with the shared demo credentials, and verify API
   requests, ZIP uploads, and PDF downloads.

## C. Evidence-driven defense rehearsal

1. Open **Evidencia** and import the *actual* MI300X experiment files you
   intend to discuss. The bundled `sample_data/MI300X_Benchmarks.zip` is a
   manually selectable **test package**, not auto-imported evidence.
2. Check import ID, package SHA-256, artifact hash verification, source
   labeling (including `SURROGATE`), hardware profile, GPU/hash/Merkle and
   blockchain views.
3. Use **Mercado** to fetch real observed series; then run Monte Carlo and
   model comparison against those same series.
4. Export and download a report PDF and verify it describes only executed
   stages. Test the exact parameter sizes for your defense: Render Free has
   limited memory/CPU and can unexpectedly restart.
5. Rehearse using the **real Netlify URL**, not localhost. Keep your laptop's
   working local installation and original evidence ZIP available as a
   fallback.
6. Free Render instances spin down after ~15 minutes of no inbound traffic,
   and local SQLite/imported files disappear. Import evidence shortly
   before the presentation, verify it is present, and do not assume it
   persists after a restart.

The original evidence and data-processing logic remain unchanged. No
sample results or Monte Carlo outputs are hardcoded in this deployment PR.


## D. Explicit cross-origin CORS diagnostic

After both domains are live and Render has the exact Netlify URL in
`CORS_ORIGINS`, run this from a local clone of the deployment branch:

```powershell
python scripts/check_cors.py https://YOUR-ACTUAL-API.onrender.com https://YOUR-ACTUAL-SITE.netlify.app
```

This verifies the browser's preflight for authenticated GET, ZIP-upload POST
and PDF-report POST, checks the unauthenticated 401 response carries the
correct CORS headers, and confirms unapproved origins are not allowed.
It **does not** require passwords or mutate the database.

If OPTIONS reports HTTP 400 or the allow-origin header is missing, verify
that Render `CORS_ORIGINS` is an exact match for the Netlify URL (scheme,
host, no trailing slash), and that the new Render settings were deployed.
An HTTP 401 *with* an allow-origin header means authentication is required,
not that CORS failed.

For a browser-level check: open the Netlify page, press F12, view Network,
and filter `api`. Select an OPTIONS request and inspect response headers.
Allowed origin should equal the Netlify site's URL, and authorization /
content-type should be allowed. Successful CORS does not prove the
Monte Carlo workload fits Render Free memory limits.
