# Prime ChainSentinel — Render Free API + Netlify Free UI

Use this for a **live, single-user thesis demonstration**. A free Render
instance does NOT persist runtime files, so the bundled original benchmark ZIP
is automatically reimported when a new empty instance starts (opt-in flag).
Any financial simulations or evidence uploaded after startup are ephemeral
and are not restored after a restart/spin-down.

## 1. Deploy the FastAPI backend to Render

The proposed deployment is in branch `deploy/railway-single-service` of
https://github.com/FabianS10/Prime-Chainsentinel (PR #1). Either merge the
PR into main, or select the deployment branch when creating the service.

In https://dashboard.render.com choose **New > Web Service** and connect
the GitHub repository, then configure:

| Setting | Value |
| --- | --- |
| Name | prime-chainsentinel-api (or an available name) |
| Branch | deploy/railway-single-service until merged |
| Language/Runtime | Docker |
| Dockerfile path | ./Dockerfile.api |
| Docker context | repository root |
| Compute | Free |
| Health check path | /health |

Alternatively, after merging the PR, Render **New > Blueprint** can read the
root `render.yaml` to create the free service with the same settings.

Add these **backend** environment variables (Render -> Environment):

```text
APP_ENV=production
MARKET_DATA_PROVIDER=yahoo
PCS_DEMO_SEED_SAMPLE=true
PCS_DEMO_USERNAME=<pick-a-username>
PCS_DEMO_PASSWORD=<pick-a-strong-unique-password>
CORS_ORIGINS=https://YOUR-REAL-NETLIFY-SITE.netlify.app
```

The CORS origin must match your eventual Netlify hostname **exactly**.
If you don't have that hostname yet, create the Render service with a
temporary value and update it once Netlify assigns the real URL.
Store passwords only in Render's secret environment variables. Do **not**
add them to `VITE_*` variables or commit an `.env` file.

After deploy, open:

```text
https://YOUR-RENDER-SERVICE.onrender.com/health
```

It should return JSON with `"status":"ok"`.
The original `sample_data/MI300X_Benchmarks.zip` is copied into the
Docker image; when `PCS_DEMO_SEED_SAMPLE=true` and the SQLite database
has no imports, the standard ingestion path validates, classifies and
registers the **original bytes and SHA-256** before accepting requests.
Any validation errors remain recorded and logged. If an import exists,
the startup process does **not** overwrite it.

## 2. Deploy React to Netlify

In https://app.netlify.com select **Add new project > Import an existing
project**, connect the same repository, and select the same deployment
branch (or merged main).

The root `netlify.toml` already specifies:

```text
base: frontend
build command: npm ci && npm run build
publish: dist (relative to base)
```

Before building, add a **frontend build** environment variable:

```text
VITE_API_BASE=https://YOUR-RENDER-SERVICE.onrender.com
```

Use the actual Render hostname, without a trailing slash and without `/api`.

Once Netlify assigns the real HTTPS `*.netlify.app` hostname, update
Render's `CORS_ORIGINS` with that exact URL and redeploy. A changed Netlify
hostname means another Render CORS environment update. Changing
`VITE_API_BASE` on Netlify requires a new Netlify build.

The frontend automatically displays a login screen when Render requires
demo credentials. The user/pass values stay in browser memory rather than
being embedded into Netlify's static build.

## 3. Verify BEFORE the defense

1. `https://YOUR-RENDER-SERVICE.onrender.com/health` returns `status=ok`.
2. Open Netlify from a separate device or mobile data connection.
3. Enter the demo username/password. Confirm the overview loads.
4. Open **Evidencia** and inspect the restored campaign, its SHA-256,
   classification, provenance, and result count.
5. Test Hardware, GPU, Hash, Merkle and Blockchain. Confirm SURROGATE is
   explicitly labeled, not presented as GPU-native cryptographic hashing.
6. In Mercado, fetch an actual market series. Run a small Monte Carlo job
   and model comparison with the **same** market series, then generate
   and download a real PDF.
7. Test larger thesis-defense parameter sets one at a time. Render Free
   has 512 MB RAM and 0.1 CPU; insufficient resources may cause timeouts
   or a 137/out-of-memory restart. Do not represent an unexecuted test
   as completed.
8. Inspect Render logs for `Restored thesis demo evidence`. A fresh
   instance may auto-restore the campaign, but **financial results,
   imported custom evidence and report files are not persisted**.
9. Rehearse from the actual Netlify URL, including the login screen,
   network requests, validation behavior, error recovery and PDF export.

Read-only smoke check from your clone:

```bash
python scripts/defense_smoke_test.py --backend-only --base https://YOUR-RENDER-SERVICE.onrender.com
```

Requires local `PCS_DEMO_USERNAME` and `PCS_DEMO_PASSWORD` stored in a
root `.env`, never committed. `--market` also checks Yahoo retrieval.

## Defense-day procedure

- Open the Render `/health` page a few minutes beforehand and verify the
  restored evidence. Free web services can take around a minute to wake.
- Do not edit or redeploy the repository during the presentation.
- Keep the URL, demo password (privately), evidence original ZIP and local
  Docker fallback available.
- Keep any financial calculations already in progress/visible in the same
  session; a service restart or spin-down wipes those results.
- A free Render service can restart **at any time** or spin down after
  15 minutes without inbound traffic. This cannot be eliminated on Free.
- Render Free storage is ephemeral, and the restore is only for the bundled
  sample ZIP. Persistent databases require a different host or paid storage.
