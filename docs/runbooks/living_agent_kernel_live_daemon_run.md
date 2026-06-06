# Runbook — LivingAgentKernel LIVE daemon-service run (operator-gated)

## Status

OPERATOR-GATED. This procedure is **not** executed by any test, `/loop`,
`/schedule`, launchctl plist, or cron job in this build. It is a manual,
human-in-the-loop step. No automation in this repository invokes the prod
store at `~/.dharma/living_agent_kernel`.

## What this proves

`run_kernel_daemon_service` (`dharma_swarm/operator_core/living_agent_kernel_service.py`)
drains queued wakes through `run_daemon_cycle -> run_control_tick ->
run_next_wake -> lease_next_wake`, writing two durable ledgers under a real
file lock:

- `wake_ledger.jsonl` — hash-chained per-wake state transitions
- `daemon_cycles.jsonl` — hash-chained per-cycle heartbeat records

Ground truth verified before this build: the prod store
`~/.dharma/living_agent_kernel/` held `proof_ledger.jsonl` and `events/` but
**no** `wake_ledger.jsonl` and **no** `daemon_cycles.jsonl`, i.e.
`run_kernel_daemon_service` had never executed in a daemon context. The
automated E2E test (`tests/test_living_agent_kernel_daemon_e2e.py`) closes
that gap against a fresh TEST store. This runbook is the only path that
touches the real prod store, and only an operator runs it.

## Pre-flight (read-only)

```bash
# Confirm what currently exists in the prod store (no mutation).
ls -la ~/.dharma/living_agent_kernel/
# Expect proof_ledger.jsonl + events/, and BEFORE first run: no wake_ledger.jsonl / daemon_cycles.jsonl.
```

## The gated invocation (one bounded cycle, dry-review)

Provider stays the v1 read-only registry (`session_status`). No network, no
paid provider, no `--forever`.

```bash
export PYTHONPATH=/Users/dhyana/dharma_swarm_lak_e2e
cd /Users/dhyana/dharma_swarm_lak_e2e

python3 scripts/runtime/living_agent_kernel_service.py \
  --store-dir ~/.dharma/living_agent_kernel \
  --workspace-root /Users/dhyana/dharma_swarm_lak_e2e \
  --cycles 1 \
  --max-wakes 1 \
  --interval-seconds 0 \
  --json
```

- `--cycles 1` — exactly one bounded cycle, then exit.
- `--max-wakes 1` — drain at most one queued wake.
- `--interval-seconds 0` — no inter-cycle sleep (irrelevant at one cycle).
- `--json` — full result for dry-review; nothing is auto-acted upon.

If the store has no queued wake, the cycle status is `idle` and no wake is
mutated — this is the expected first-run shape, and it still creates an
empty-but-valid `daemon_cycles.jsonl` heartbeat row.

## Dry-review of output (before trusting anything)

```bash
# 1. The two ledgers now exist.
ls -la ~/.dharma/living_agent_kernel/wake_ledger.jsonl \
       ~/.dharma/living_agent_kernel/daemon_cycles.jsonl

# 2. Hash-chain integrity, loaded fresh from disk.
python3 - <<'PY'
from dharma_swarm.operator_core.living_agent_kernel import KernelRunStore
store = KernelRunStore("~/.dharma/living_agent_kernel")
print("wake_ledger:", store.verify_wake_ledger())
print("daemon_cycles:", store.verify_daemon_cycle_ledger())
print("cycles:", len(store.daemon_cycles()))
PY
```

Only after the operator has eyeballed the JSON payload and confirmed both
ledgers verify `(True, [])` should the result be treated as trustworthy.

## Hard prohibitions

- Do **not** pass `--forever`. The CLI refuses it (exit 3) unless the
  operator also passes `--allow-forever`; even then, no automation in this
  build is permitted to do so.
- Do **not** wire this into launchctl / cron / `/loop` / `/schedule`. It is a
  manual operator step by design (see CLAUDE.md track non-goals: "Install a
  default-off launchd/cron wrapper only after operator review of dry-run
  receipts.").
- Do **not** point the TEST suite at the prod store; the E2E test always uses
  a fresh `tmp_path` store.
