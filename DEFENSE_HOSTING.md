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

Use this for an independent 24/7 cloud host if Oracle allocates an Always Free
Ampere A1 instance. Current free allowance: 2 OCPUs / 12 GB RAM and eligible
persistent boot/block storage in the account's home region. Oracle may reclaim
an idle instance, and regional A1 capacity is not guaranteed.

1. In https://cloud.oracle.com/, create an Always Free **VM.Standard.A1.Flex**
   (Ubuntu ARM64, 2 OCPUs and 12 GB RAM, Always Free-eligible boot storage).
   Save its private SSH key and public IP address. Never exceed Always Free
   quotas. Only inbound SSH from your own IP is needed for setup; **do not
   expose port 8000 or the SQLite file to the public Internet**.
2. SSH into the VM (Ubuntu's default username is often `ubuntu`, but follow
   the image's displayed connection details):

   ```bash
   ssh -i /path/to/oci-key ubuntu@YOUR_VM_PUBLIC_IP
   ```

3. Install Git and Docker Engine with Compose using the official Docker
   Ubuntu instructions:
   https://docs.docker.com/engine/install/ubuntu/
   Confirm with `sudo docker compose version`.
4. Clone this prepared branch:

   ```bash
   git clone --branch deploy/railway-single-service https://github.com/FabianS10/Prime-Chainsentinel.git
   cd Prime-Chainsentinel
   cp .env.defense.example .env
   nano .env
   ```

   Set a strong private password and close the editor. The `.env` file is
   gitignored; it must remain only on the VM.
5. Start the FastAPI/React app and a Cloudflare Quick Tunnel **inside Docker**:

   ```bash
   sudo docker compose -f compose.oracle.yaml up -d --build
   sudo docker compose -f compose.oracle.yaml ps
   sudo docker compose -f compose.oracle.yaml logs tunnel --tail 80
   ```

   Find the `https://*.trycloudflare.com` link in the tunnel logs. Visit it
   and log in with the credentials you set. This creates public HTTPS
   **without** requiring a domain, opening port 8000 or keeping your laptop
   switched on. The public URL is **temporary** and changes if the quick
   tunnel is replaced; Cloudflare does not guarantee Quick Tunnel uptime.
6. Import `sample_data/MI300X_Benchmarks.zip` into **Evidencia** through
   your browser. Confirm that `sudo docker compose -f compose.oracle.yaml
   restart app` does not delete imports.
7. Perform the browser-based defense rehearsal and keep the separate
   laptop-hosted option ready.

For logs:
```bash
sudo docker compose -f compose.oracle.yaml logs --tail 100 app
sudo docker compose -f compose.oracle.yaml logs --tail 100 tunnel
```

**Important:** If you need a stable custom hostname, replace the temporary
Cloudflare Quick Tunnel with a named tunnel plus DNS/custom domain, and
configure your access controls. Do not market this Quick Tunnel as guaranteed
production hosting.

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
