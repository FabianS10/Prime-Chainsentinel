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
   CORS_ORIGINS=https://YOUR-SITE.netlify.app
   ```

   Use actual values. Configure the Netlify hostname in `CORS_ORIGINS`
   once assigned. This demo runs without built-in authentication.
   Avoid importing confidential files: the public API can be called directly.
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
5. Open Netlify directly (no login) and verify API requests, ZIP uploads,
   computations, and PDF downloads.

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


## D. Verify CORS for the login-free deployment

After both domains are live, set
`CORS_ORIGINS=https://prime-chainsentinel.netlify.app`
in Render, then use the read-only check:

```powershell
python scripts/check_cors.py https://prime-chainsentinel-api.onrender.com https://prime-chainsentinel.netlify.app
```

The test checks JSON requests, the upload/report preflight, the allowed
Netlify origin and expected public `200` responses. It does not upload
data or perform calculations. A successful response from the API does not
guarantee that Monte Carlo fits Render Free compute/memory constraints.

## E. Security of this public demonstration

This edition intentionally opens directly to the dashboard, with no login.
The API is also public: CORS restricts **which browser origins** can read
responses, but is not an authentication or access-control system. Anyone
can send requests directly to the Render URL, including import and
simulation requests. Never upload private, confidential or sensitive data.
For a future long-lived public deployment, add infrastructure-managed
access restrictions or a real authorization system without changing the
thesis prototype's research requirements.

The original simulation algorithms, ingestion rules, provenance contract,
and manual evidence import behavior remain unchanged.
