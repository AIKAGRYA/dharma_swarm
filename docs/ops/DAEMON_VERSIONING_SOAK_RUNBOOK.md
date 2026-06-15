# Daemon Versioning & Soak Runbook (v0.0.2 candidate)

Status: REVIEW WORKTREE on branch `daemon-lane-upgrade-20260616`. This branch
imports the v0.0.1 scaffold from `daemon-versioning/v0.0.1`, adds runtime
provenance from `honest-spine-v2`, and implements the safe local hot-path legs
H1-H3. H4-H5 remain operator-gated: this branch does not restart launchd,
systemd, Docker, or the VPS daemon.

## What this adds

The DGM evolution archive (`~/.dharma/evolution/archive.jsonl`, ~11.5k entries)
stays the single source of truth. This lane teaches the system to:

1. Stamp a **version identity** (`build_id = __version__ + git_short_sha`,
   e.g. `0.1.0+9c76b2106`). Local dirty worktrees report `.dirty`, e.g.
   `0.1.0+9c76b2106.dirty`, so a candidate cannot masquerade as clean HEAD.
2. **Project** per-version metrics out of the existing truth stores (archive +
   `runtime.db:delegation_runs`) into `~/.dharma/evolution/version_metrics/<build_id>.json`.
3. **Recommend** PROMOTE_CANDIDATE / HOLD / REJECT from VERIFIED metrics only.
4. **Soak** a candidate on a single VPS host and pull verdicts back to the Mac.
5. **Report runtime provenance** in `make onboard`: which live code-bearing
   process is executing which worktree/branch/commit/dirt.

Zero new databases. Zero new authority surfaces. Two-key promotion.

## Current implementation status

- **Implemented locally:** version package, promote gate, metrics rollup,
  dry-run soak harness, Docker/compose scaffold, runtime provenance probe,
  versioned `/health`, degradable `/ready` and `/metrics`,
  `delegation_runs.metadata_json.daemon_version`, and
  `ArchiveEntry.daemon_version`.
- **Still gated:** promotion execution, launchd/systemd swap, VPS Docker deploy,
  and any long-running daemon restart.
- **Current clean candidate identity:** compute from the committed checkout with
  `python3 -c 'from dharma_swarm.versioning.daemon_version import daemon_version; print(daemon_version())'`.
- **Promotion evidence right now:** local rollup for the committed clean
  candidate has `n_entries=0`, `n_runs=0`, `soak_hours=0.0`.
  Promotion gate verdict is `HOLD` with reason `n=0 < N_MIN(50)`.

## Relationship to Forge / Hydra benchmarks

This is not the Forge Reality Arena Hydra itself. Forge/Hydra is a bounded
benchmark/evaluation mission pattern; it should not become standing autonomy
without a separate lease. This daemon-versioning lane is the substrate Forge can
use later: if a Forge benchmark runner becomes long-lived, it should report this
same `build_id`, provenance, per-version metrics, and promote/hold verdict.
Today, this branch upgrades the daemon lane machinery, not the Forge benchmark
surface.

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

**No implicit history borrowing:** a build id with no tagged candidate data must
not borrow untagged historical runtime rows unless an explicit timestamp window
is supplied. New daemon candidates fail closed as `HOLD` until they create their
own tagged evidence.

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
BUILD_SHA=9c76b2106
BUILD_TAG=0.1.0.9c76b2106   # Docker-safe projection; BUILD_ID stays canonical
docker build --build-arg BUILD_ID=$BUILD_ID --build-arg BUILD_SHA=$BUILD_SHA \
  -t dharma-daemon:$BUILD_TAG -f deploy/daemon/Dockerfile .
docker run -d -p 7433:7433 dharma-daemon:$BUILD_TAG
curl -fm1 localhost:7433/health
```

---

## HOT-PATH STATUS

The live checkout is still separate from this review worktree. `make onboard`
must be trusted over prose: it reports live code-bearing processes and whether
they are dirty or behind. Do not restart or repoint a live process from this
branch without explicit operator approval.

### H1 — `/health` timeout fix (`swarm_health_api.py`, handler ~lines 159–185)

Status: **implemented locally**.

- Split **liveness `/health`** to constants only:
  `{status, pid, uptime, **version_stamp(), runtime_dispatch}` — no collectors.
- Move collectors to a degradable **`/ready`** and keep **`/metrics`**, both
  wrapping body build in `asyncio.wait_for(asyncio.to_thread(...), timeout=2.0)` →
  `503 {"status":"degraded"}` on slow, never hang.
- Verifier: `tests/test_swarm_health_api.py` monkeypatches a collector failure
  and asserts `/metrics` preserves `503 Service Unavailable`.

### H2 — version self-report (`swarm_health_api.py:173`)

Status: **implemented locally**. `/health` now carries `build_id`,
`daemon_version`, `git_sha`, `started_at`, and `pid`; the old static
`"version": "dharma_swarm"` field is gone.

### H3 — version tagging in the live insert path (`runtime_state.py` delegation_runs insert)

Status: **implemented locally**.

Write `"daemon_version": build_id` into `delegation_runs.metadata_json` at run
creation, and `daemon_version` into each new `ArchiveEntry`. No runtime DB
schema migration is required; `metadata_json` already exists. Archive entries
received an additive optional field with backward-compatible defaults.

### H4 — daemon version switch (the actual promotion)

Status: **gated / no-op**.

Two-key: `promote_gate.request_promotion()` writes `PENDING_APPROVAL.json`; the
operator runs `scripts/governance/promote_daemon_version.py --approve <build_id>`
which (in a future gated commit) performs the launchd plist swap / image re-tag.
Today that script is a NO-OP stub that only prints the plan. Mirrors
`chetana.promote`'s staged→human pattern.

### H5 — VPS deploy / soak run

Status: **gated / dry-run only unless operator passes `--execute`**.

Building the image, `docker compose up -d` on a VPS, and running the soak loop
are all operator-initiated per the topology above. Mac-pulls-only. Nothing runs
automatically.
