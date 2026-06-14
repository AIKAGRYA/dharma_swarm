# Daemon Versioning & Soak Runbook (v0.0.1)

Status: SCAFFOLD on branch `daemon-versioning/v0.0.1`. The SAFE artifacts are
built and tested. The HOT-PATH edits below are DESIGN-ONLY patch-plans —
operator sign-off + `dual-audit` required before any of them leave the worktree.

## What this adds

The DGM evolution archive (`~/.dharma/evolution/archive.jsonl`, ~11.5k entries)
stays the single source of truth. v0.0.1 only teaches the system to:

1. Stamp a **version identity** (`build_id = __version__ + git_short_sha`,
   e.g. `0.1.0+9c76b2106`).
2. **Project** per-version metrics out of the existing truth stores (archive +
   `runtime.db:delegation_runs`) into `~/.dharma/evolution/version_metrics/<build_id>.json`.
3. **Recommend** PROMOTE_CANDIDATE / HOLD / REJECT from VERIFIED metrics only.
4. **Soak** a candidate on a single VPS host and pull verdicts back to the Mac.

Zero new databases. Zero new authority surfaces. Two-key promotion.

## Verified-vs-heuristic honesty rule (load-bearing)

ONLY externally-grounded metrics gate promotion:
- `correctness_mean` — real pytest pass_rate from `test_results.pass_rate`.
- `gate_allow_rate` — telos gate outcomes (`gates_failed`).
- `rollback_rate` — DiffApplier rollbacks (`rollback_reason`).
- `receipt_ok_rate` / `cost_usd_per_applied` / `latency_ms_*` — from
  `delegation_runs.receipt_json` (`status`, `cost_usd`, `latency_ms`).

The heuristic dims (`dharmic_alignment`, `elegance`, `swabhaav_alignment`) are
recorded for MAP-Elites diversity and carry **zero** promotion authority.

**Cost caveat (verified at runtime):** the sampled `receipt_json.cost_usd` is
`null` for the free-model fleet. When cost is unobserved the gate degrades the
cost ceiling to non-gating and leans on latency/success — this is intentional,
and surfaced in the verdict reasons.

## Promote / Hold / Reject rule (fail-closed, priority order)

1. **REJECT** — circuit-breaker trips > 0, OR rollback_rate > 0.20, OR a gate
   BLOCK on an applied entry, OR merkle chain fails.
2. **HOLD** — `n < 50` OR `soak_hours < 12` OR no incumbent. (Inconclusive is
   never a REJECT.)
3. **REJECT** — candidate verifiably worse on correctness or receipt_ok_rate
   (CI-accounted, Wald 95%).
4. **PROMOTE_CANDIDATE** — all verified metrics ≥ incumbent within margin AND
   cost ≤ incumbent×1.25 AND gate_allow_rate ≥ 0.80 AND receipt_ok_rate ≥ 0.85
   AND soak met. Flags `ready_for_promotion`; holds for the human.
5. Otherwise **HOLD**.

No code path auto-flips a running daemon from this file. `verdict` is advisory.

## Daily soak flow (local SAFE legs)

```bash
# 1. copy the live truth stores (NEVER read the live db directly)
cp ~/.dharma/state/runtime.db /tmp/copy_runtime.db
cp ~/.dharma/evolution/archive.jsonl /tmp/copy_archive.jsonl

# 2. project the per-version tracking file
python3 scripts/runtime/version_metrics_rollup.py \
  --archive /tmp/copy_archive.jsonl --runtime-db /tmp/copy_runtime.db \
  --build-id "$(python3 -c 'from dharma_swarm.versioning.daemon_version import daemon_version;print(daemon_version())')" \
  --out ~/.dharma/evolution/version_metrics/$BUILD_ID.json

# 3. characterize the live /health timeout (read-only)
python3 scripts/runtime/health_probe_timing.py --out /tmp/health_timing.json

# 4. register the free worker fleet for attribution
python3 scripts/governance/register_worker_model.py --all
```

The gate (`VersionPromotionGate.compare`) then reads two version files and emits
a verdict. `request_promotion()` writes `PENDING_APPROVAL.json` only.

## VPS soak topology — honest

- **No Kubernetes.** Single host, `docker compose -f deploy/daemon/compose.daemon.yml`
  with `restart: unless-stopped`. The container is disposable; `~/.dharma` is a
  named volume so the archive survives version swaps.
- **Bali NAT → Mac is the hub.** VPSes cannot reach the Mac. The Mac initiates
  ALL transport: `rsync vps:~/.dharma/evolution/version_metrics/ → Mac`. The VPS
  never pushes. `scripts/runtime/soak_harness.sh --dry-run` prints the exact
  command sequence (default is dry-run; `--execute` to run for real).
- **Optional NATS verdict transport.** `agni wss:8443` JetStream
  (`~/.dharma/nats/a2a.sh`) is the one NAT-traversing channel and may carry live
  verdicts — transport only, never authority.

## Image build

```bash
BUILD_ID=0.1.0+9c76b2106
docker build --build-arg BUILD_ID=$BUILD_ID --build-arg BUILD_SHA=9c76b2106 \
  -t dharma-daemon:$BUILD_ID -f deploy/daemon/Dockerfile .
docker run -d -p 7433:7433 dharma-daemon:$BUILD_ID
curl -fm1 localhost:7433/health   # depends on H1+H2 landing first
```

---

## HOT-PATH PATCH-PLAN (DESIGN ONLY — operator + dual-audit gated)

The live checkout is on `telos-ai-seed-v0-from-sandbox` with ~109 uncommitted
files. **Never touch that branch, those files, or the running process.** Apply
these only from a fresh worktree off origin/main, behind operator sign-off.

### H1 — `/health` timeout fix (`swarm_health_api.py`, handler ~lines 159–185)

Root cause: `/health` (line ~174) calls `_runtime_dispatch_status()` and the
shared collectors do synchronous `read_text()` of a growing JSONL on the shared
asyncio event loop. One slow read starves all connections, hanging even the
cheap probe. Three coordinated edits:

- Split **liveness `/health`** to constants only:
  `{status, pid, uptime, **version_stamp()}` — ZERO I/O / collectors.
- Move collectors to a degradable **`/ready`** and keep **`/metrics`**, both
  wrapping body build in
  `asyncio.wait_for(asyncio.to_thread(_build_body, path), timeout=2.0)` →
  `503 {"status":"degraded"}` on slow, never hang.
- Verifier: `curl -m1 /health` returns 200 <100ms while a 50k-line synthetic
  archive is appended in a loop; pytest monkeypatches a collector to
  `sleep(10)` and asserts `/ready` returns 503 within 2.5s while `/health`
  stays <100ms.

### H2 — version self-report (`swarm_health_api.py:173`)

Replace `"version": "dharma_swarm"` with `**version_stamp()` (from
`dharma_swarm.versioning.daemon_version`). Minimum hot-path touch so the
liveness probe carries the real `build_id`. Bundles with H1 (same handler).
**A5 Docker healthcheck depends on H1+H2 landing first.**

### H3 — version tagging in the live insert path (`runtime_state.py` delegation_runs insert)

Write `"daemon_version": build_id` into `delegation_runs.metadata_json` at run
creation, and `daemon_version` into each new `ArchiveEntry`'s free-form field.
**No schema migration** — `metadata_json` (col 13) already exists. Chosen over
amending the frozen `EvidenceReceipt` (which has `agent_card_version` but no
`daemon_version`) to honor the spine-adoption frozen-schema non-goal. Coordinate
with @AmitabhainArunachala if a receipt amendment is ever preferred.

### H4 — daemon version switch (the actual promotion)

Two-key: `promote_gate.request_promotion()` writes `PENDING_APPROVAL.json`; the
operator runs `scripts/governance/promote_daemon_version.py --approve <build_id>`
which (in a future gated commit) performs the launchd plist swap / image re-tag.
Today that script is a NO-OP stub that only prints the plan. Mirrors
`chetana.promote`'s staged→human pattern.

### H5 — VPS deploy / soak run

Building the image, `docker compose up -d` on a VPS, and running the soak loop
are all operator-initiated per the topology above. Mac-pulls-only. Nothing runs
automatically.
