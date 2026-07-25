# Operational Runbook — dharma_swarm

**Owner:** Operator  
**Last verified:** 2026-05-04  
**Purpose:** Procedural reference for launching, monitoring, and recovering the dharma_swarm runtime.

---

## 1. Prerequisites

- Python 3.11+ with `pip` or `uv`
- macOS (launchd) or Linux (systemd) for daemon mode
- Node.js 18+ and npm for the dashboard
- SQLite 3.35+ (ships with Python)

## 2. Install & Setup

```bash
cd ~/dharma_swarm
python3 -m pip install -e ".[dev]"
pre-commit install
```

Verify:

```bash
python3 -m pytest tests/ -q --co | tail -1    # should show test count
dgc status                                     # should print system status
```

## 3. Launching the Runtime

### 3a. Foreground (development)

```bash
dgc orchestrate-live
```

Runs the full orchestrator loop in the terminal. Ctrl-C to stop.

### 3b. Background daemon

```bash
dgc up --background
```

Check status:

```bash
dgc daemon-status
```

Stop:

```bash
dgc down
```

### 3c. make boot

```bash
make boot
```

Equivalent to `dgc up --background` with pre-flight checks (DB migrations, pre-commit install).

### 3d. launchd (macOS persistent)

Install the repo-managed plist:

```bash
make boot
```

The checked-in `com.dharma.swarm.plist` runs through
`scripts/load_runtime_env.sh`; do not hand-edit a launchd plist that sources
`.env` or `~/.dharma/agent_keys.env` directly. The source of truth for provider
secrets is `~/.dharma/agent_keys.env` via `dkeys`.

Rendered shape:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" ...>
<plist version="1.0">
<dict>
  <key>Label</key><string>com.dharma.swarm</string>
  <key>ProgramArguments</key>
  <array>
	    <string>/bin/bash</string>
	    <string>-c</string>
	    <string>cd /Users/dhyana/dharma_swarm &amp;&amp; source scripts/load_runtime_env.sh &amp;&amp; exec env TINY_ROUTER_BACKEND=heuristic dgc orchestrate-live</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>/tmp/dharma-swarm.log</string>
  <key>StandardErrorPath</key><string>/tmp/dharma-swarm.err</string>
  <key>WorkingDirectory</key><string>/Users/dhyana/dharma_swarm</string>
</dict>
</plist>
```

Manual load/unload:

```bash
launchctl load ~/Library/LaunchAgents/com.dharma.swarm.plist
launchctl unload ~/Library/LaunchAgents/com.dharma.swarm.plist
```

**Spine dispatch (D1, organism-rewire-2026-07):** the Docker `swarm` service sets
`DHARMA_SPINE_DISPATCH=1` standing. The launchd/Mac daemon does NOT inherit compose
env, so set it on the daemon host too — either add a `<key>EnvironmentVariables</key>`
dict to the plist (`<key>DHARMA_SPINE_DISPATCH</key><string>1</string>`) or run
`launchctl setenv DHARMA_SPINE_DISPATCH 1` before load (a repo `.env` also works when
launching via `make boot`). Confirm with `dgc spine tail` — receipts should appear.

### 3e. VPS deployment (organism-rewire-2026-07 item 4 — Mac demotes to dev seat)

The compose stack (`web` + `swarm` + `cron` + optional `litestream` sidecar,
persistent `dharma-state` volume, `swarm` service already carrying
`DHARMA_SPINE_DISPATCH=1` and `restart: unless-stopped`) is the deployment
unit. Two provisioning paths:

**Path A — phone flow (cloud-init, recommended).** Everything except the two
secret acts is unattended via `scripts/ops/vps_cloud_init.yaml`:

1. In the provider console (Hetzner CX22 / DO 4GB droplet; Ubuntu 24.04),
   create the server and paste the contents of `scripts/ops/vps_cloud_init.yaml`
   into the *user data / cloud-init* field. Add your SSH key. Boot.
2. Cloud-init installs docker+compose, 2G swap, ufw (ssh-only), litestream,
   and generates a READ-ONLY GitHub deploy key. It writes
   `/root/DHARMA_NEXT_STEPS.txt` containing the deploy pubkey.
3. Two operator acts (the only manual steps, doable from GitHub mobile + one
   ssh session): add the printed deploy key to the repo (Settings → Deploy
   keys, write access OFF), and create `/root/dharma.env` from `.env.example`
   with real provider keys — ANY ONE live lane from `.env.example` goes live
   (canonical lane registry: `dharma_swarm/api_keys.py`; e.g. KIMI, ZHIPU,
   OPENROUTER, ANTHROPIC, GROQ…); optional: `LITESTREAM_*`, `DEVIN_NATS_*`.
4. `bash /root/dharma_bootstrap.sh` — clones, builds,
   `docker compose --profile vps up -d`, waits for health, and prints the
   felt-proof `dgc spine tail`.

**Path B — manual (any Ubuntu box with docker):**

```bash
git clone https://github.com/AmitabhainArunachala/dharma_swarm && cd dharma_swarm
cp .env.example .env    # then fill: provider keys (dkeys export), DEVIN_NATS_PW if bridging AGNI
docker compose --profile vps up -d --build   # drop --profile vps to skip litestream
docker compose exec swarm dgc spine tail --limit 5   # felt-proof: receipts flowing
curl -s localhost:7433/health                        # daemon health
```

Notes:
- **NATS**: the AGNI hub (`wss://157.245.193.15:8443`, stream `DHARMA_A2A`) already
  runs on a VPS — this host connects OUT to it (set the `DEVIN_NATS_*` env vars);
  no local broker service is required unless mirroring the Mac-local `DHARMA_FLEET`.
  Do NOT co-locate this daemon on the AGNI hub box: the hub is fleet transport
  backbone; keeping the hot, evolving organism on its own host bounds blast radius.
- **State durability**: the `litestream` compose service (profile `vps`) replicates
  `dharma-state`'s `runtime.db` per `scripts/ops/litestream.yml` to any
  S3-compatible target (`LITESTREAM_*` env). Snapshot cadence matters more than
  realtime here — receipts are append-heavy.
- **Arena / forge evolution cycles run on THIS SAME HOST** (decision 2026-07-03):
  Arena v1 is zero-weight and API-token-bound, not CPU-bound, so a second box buys
  nothing yet. Co-tenancy rules: arena runs as its own compose service/profile with
  cpu/mem limits when it lands (Campaign 2); fitness evaluates ONLY clean
  `CANONICAL_ORIGIN_MAIN` checkouts, never this daemon's working state; arena state
  stays in its own directory; internal artifacts never touch archive fitness (One
  Wire). Split to a dedicated box only when arena saturates CPU or the R_V/GPU
  research lane starts (different machine class entirely).
- **First CLOSED_LIVE sequence** once up: quarantine historical dropoffs
  (`python3 scripts/runtime/dispatch_dropoff_quarantine.py --before <spine-fix-ts>`
  dry-run then `--execute`), give an agent work, watch `dgc spine tail --follow`,
  then promote Loop 1 on its live owner-surface criterion.
- **Verification from anywhere**: once up, `make organism-status` on any checkout pointing at
  the same state (or the cockpit `spine.pulse` row via the web service) shows Loop-1
  LIVE; the Mac daemon can then be unloaded (`make stop`) and kept as a dev mirror.
- **Not automated on purpose**: creating the server, the deploy key grant, and
  `.env` secrets are operator acts — no credentials in the repo, ever.

## 4. Health Checks

### Quick status

```bash
dgc status
dgc runtime-status
dgc mission-status
```

### Value events (operator brief output)

```bash
dgc value-events --since 2026-01-01
dgc value-events --since 2026-01-01 --json
```

### Trace Attractor (provenance projection)

```bash
dgc trace-attractor --trace-id trc_<hex> --json
```

### Guardian Crew report

Check `~/.dharma/guardian/GUARDIAN_REPORT.md` for the latest 4-hour cycle output.

## 5. Logs

### Runtime logs

```bash
tail -f /tmp/dharma-swarm.log      # stdout (launchd)
tail -f /tmp/dharma-swarm.err      # stderr (launchd)
```

### Witness logs

```bash
ls ~/.dharma/witness/
cat ~/.dharma/witness/<latest>.jsonl
```

### Stigmergy marks

```bash
dgc stigmergy
cat ~/.dharma/stigmergy/marks.jsonl | tail -20
```

### Trace history

```bash
ls ~/.dharma/traces/history/ | tail -20
```

## 6. Pre-Commit Hooks

```bash
pre-commit install           # one-time setup
pre-commit run --all-files   # manual full run
```

Hooks run on every commit. If a hook modifies files (e.g., formatting), stage the changes and commit again.

## 7. Dashboard

```bash
# API server
cd ~/dharma_swarm
uvicorn api.main:app --host 127.0.0.1 --port 8420 --reload

# Frontend
cd ~/dharma_swarm/dashboard
npm install
npm run dev
```

Dashboard reads from the same SQLite databases as the runtime. No separate data store.

## 8. Docker

```bash
docker build -t dharma-swarm .
docker run -v ~/.dharma:/root/.dharma dharma-swarm dgc orchestrate-live
```

**Caveats:**
- Mount `~/.dharma` to persist state across container restarts.
- SQLite WAL mode requires the volume to be on a local filesystem (not NFS).
- The dashboard runs as a separate container or on the host.

## 9. Database Maintenance

### Inspect runtime state

```bash
sqlite3 ~/.dharma/state/runtime.db ".tables"
sqlite3 ~/.dharma/state/runtime.db "SELECT count(*) FROM task_claims"
```

### Inspect telemetry

Telemetry tables share the runtime DB:

```bash
sqlite3 ~/.dharma/state/runtime.db "SELECT count(*) FROM economic_events"
```

### Backup

```bash
cp ~/.dharma/state/runtime.db ~/.dharma/state/runtime.db.bak
```

## 10. Recovery Procedures

### Corrupted SQLite database

```bash
sqlite3 ~/.dharma/state/runtime.db ".recover" | sqlite3 ~/.dharma/state/runtime_recovered.db
mv ~/.dharma/state/runtime.db ~/.dharma/state/runtime.db.corrupt
mv ~/.dharma/state/runtime_recovered.db ~/.dharma/state/runtime.db
```

### Stuck daemon

```bash
dgc down
# If that fails:
kill $(cat ~/.dharma/operator.pid)
dgc up --background
```

### Reset evolution archive

```bash
mv ~/.dharma/evolution/archive.jsonl ~/.dharma/evolution/archive.jsonl.bak
dgc orchestrate-live   # will rebuild from scratch
```

### Guardian Crew not running

The guardian crew runs as a concurrent loop inside `orchestrate-live`. If it stops producing reports, check:

```bash
grep -i "guardian" /tmp/dharma-swarm.log | tail -20
```

If the loop crashed, restart the daemon. Guardian findings are also written to `GUARDIAN_REPORT.md` in the repo root.
