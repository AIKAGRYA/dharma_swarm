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

Create `~/Library/LaunchAgents/com.dharma.swarm.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" ...>
<plist version="1.0">
<dict>
  <key>Label</key><string>com.dharma.swarm</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/local/bin/dgc</string>
    <string>orchestrate-live</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>/tmp/dharma-swarm.log</string>
  <key>StandardErrorPath</key><string>/tmp/dharma-swarm.err</string>
  <key>WorkingDirectory</key><string>/Users/dhyana/dharma_swarm</string>
</dict>
</plist>
```

Load/unload:

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
