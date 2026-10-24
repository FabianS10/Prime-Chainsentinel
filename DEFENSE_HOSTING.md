# Prime ChainSentinel — zero-cost, fully functional defense demo

The project is a React/Vite interface served by FastAPI, backed by a persistent
SQLite provenance store and local evidence files. GPU campaign results are
imported and reused; running the original MI300X is not required.

## Recommended reliability plan

- **If already available:** use an Oracle Cloud Always Free Ampere A1 VM,
  subject to allocation limits and regional capacity, with persistent boot/storage.
- **No cloud account/credits needed:** run the Docker Compose deployment
  on your own computer and expose it via a temporary Cloudflare Tunnel.
  Everyone with the HTTPS URL and demo credentials can interact with the
  real app while your machine and internet remain online.
- Do **not** use Render Free as the only host for a live evidence-heavy demo:
  it has an ephemeral filesystem and sleeps after inactivity.

## 1. Local Windows + free public HTTPS link

Requirements: Docker Desktop (running with Linux containers), Git, and the
current `cloudflared` command-line tool installed from
https://developers.cloudflare.com/tunnel/downloads/ .

A. Get the deployment branch (or, after merging the PR, use `main`):

```powershell
git clone --branch deploy/railway-single-service https://github.com/FabianS10/Prime-Chainsentinel.git
cd Prime-Chainsentinel
```

B. Configure a private demo password:

```powershell
Copy-Item .env.defense.example .env
notepad .env
```

Choose a strong unique `PCS_DEMO_PASSWORD`. The root `.env` is gitignored.
Do **not** commit it. This is one shared demo account, not user registration.

C. Build and run the real full-stack software:

```powershell
docker compose -f compose.defense.yaml up -d --build
docker compose -f compose.defense.yaml ps
curl.exe http://localhost:8000/health
```

Expected health includes `"status":"ok"`. Browse
http://localhost:8000 and enter the demo credentials.

D. Run an independent PowerShell terminal:

```powershell
cloudflared tunnel --url http://localhost:8000
```

Cloudflare prints a temporary `https://*.trycloudflare.com` URL.
Open it from a **different network/device** to confirm actual internet access.
The username/password protection is enabled within FastAPI. You can share
both credentials and the URL only with your examiners.

**Keep Docker Desktop, the PC, and cloudflared running** for the demonstration.
Cloudflare Quick Tunnels are for testing/demos, have no uptime guarantee,
and their URL changes after restarting the tunnel.

## 2. Load the original thesis evidence (once)

The Docker named volume `pcs-defense-storage` persists the database, stored
uploads, cache, and generated report files between container restarts.

1. Open **Evidencia** in the UI.
2. Import `sample_data/MI300X_Benchmarks.zip` from your checkout.
3. Check import ID, package SHA-256, campaign and active hardware profile.
4. Go to Hardware, GPU, Hash, Merkle, and Blockchain, verifying the correct
   evidence labels, including **SURROGATE** where required.
5. Execute Market, Monte Carlo, Model Comparison and export an actual PDF.
6. Confirm provenance relationships and artifact hash verification.
7. Restart *only* the Docker app and verify imports still appear:

```powershell
docker compose -f compose.defense.yaml restart
```

8. **Before the defense:** open the dashboard and re-run financial requests,
   as live Yahoo Finance access can fail or be rate-limited. Do not present
   synthetic fallback as observed measurements.

## 3. Stop, restart, and preserve data

```powershell
# Restart without rebuilding. Keeps all imported evidence.
docker compose -f compose.defense.yaml up -d

# Stop the containers. Keeps the named volume.
docker compose -f compose.defense.yaml down
```

**Never run** `docker compose down -v` or remove the
`pcs-defense-storage` Docker volume; that deletes the saved evidence.

Quick checks:

```powershell
docker compose -f compose.defense.yaml ps
docker compose -f compose.defense.yaml logs --tail 100 app
curl.exe http://localhost:8000/health
```

## 4. Cloud-hosted variant: Oracle Always Free

Provision an Always Free **Ampere A1** VM (for example 2 OCPU/12 GB),
subject to Oracle home-region quota and capacity. Install Docker Engine
and Compose on the VM and deploy this same Docker image with the persisted
volume. The A1 architecture is ARM64, so build the image *on the VM* rather
than transferring a Windows/AMD64 build. Do not expose the unencrypted
port 8000 to the internet. To publish a secure URL, use a configured
HTTPS reverse proxy plus DNS, or Cloudflare Tunnel. Quick Tunnels may be
used for temporary demos; a stable custom hostname requires additional
DNS/tunnel configuration.

Keep an independently verified laptop-based fallback. Oracle can reclaim
qualifying idle Always Free instances and regional capacity can be full.

## 5. Defense-day checks

- At least a day before: verify the public link using mobile data.
- Confirm all benchmark views and the SURROGATE classification, imports,
  provenance SHA-256 checks, market data, Monte Carlo, comparisons, and PDFs.
- Check volume persistence after an app restart.
- Keep a local `http://localhost:8000` browser tab as a fallback, even if
  the internet connection drops. Live market fetching needs external internet.
- Have the original `sample_data/MI300X_Benchmarks.zip` available locally.
- Avoid software updates, rebuilding, and Docker volume cleanup on defense day.

## Security reminder

The demo's shared HTTP Basic Authentication protects endpoints other than
`/health` only if **both** credential environment variables are set.
It is not multi-user authentication; anyone holding those credentials can
alter shared demo evidence. Keep them private and rotate afterward.

## What has and hasn't been tested

The code has been reviewed against the repository's routes and storage paths.
A complete container build and live public-tunnel test have **not** been
performed in ChatGPT; run the checks above on your actual computer.
