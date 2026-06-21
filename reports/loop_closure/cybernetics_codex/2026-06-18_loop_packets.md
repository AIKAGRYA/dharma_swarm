# Cybernetics Codex Loop Packets

Generated from:

```bash
python3 scripts/governance/cybernetics_codex_audit.py --json
```

Observed at: `2026-06-18T16:49:32Z`
Runtime DB: `~/.dharma/state/runtime.db`

## Acceptance Rules

Loop closure requires sense -> interpret -> constrain -> act -> adapt on real
data, a receipt on the owning surface, and a replay command a fresh agent can
run. `delegation_runs.receipt_json` is the orchestrator/spine-dispatch witness
column only. A2A-surface success is proven through `runtime_receipts` and
idempotency records. Loop 1 additionally requires actual served provider/model
truth and zero `dispatch_dropoff` in the audited scope.

## Loop 1 Packet

Verdict: `CLOSED_IN_BOUNDED_REPLAY`; `PARTIAL_IN_ALL_HISTORY_AUDIT`

Bounded replay proof:

- report: `reports/loop_closure/cybernetics_codex/2026-06-18_loop1_bounded_spine_dispatch.json`
- command: `python3 scripts/loop1_closure_run.py --tasks 3 --agents 1 --provider ollama --timeout-per-task 180 --tick-sleep 1.0 --report reports/loop_closure/cybernetics_codex/2026-06-18_loop1_bounded_spine_dispatch.json`
- result: `LOOP1_CLOSED=yes`
- tasks: `3/3` completed
- dispatch_dropoff: `0`
- evidence receipts: `3` ok
- served provider/model truth: `3/3` completed delegation receipts, source `receipt_json`
- runtime tick errors: `0`

The standing all-history audit remains partial because historical runtime scope
still has `dispatch_dropoff=1428`. Do not erase that history; use bounded
`--since` or this replay report when evaluating the current closure lane.

Replay command for the next closure attempt:

```bash
python3 scripts/loop1_closure_run.py --tasks 3 --agents 1 --provider ollama --timeout-per-task 180 --tick-sleep 1.0 --report reports/loop_closure/cybernetics_codex/loop1_bounded_batch.json
```

Close only if the scoped audit shows:

- `dispatch_dropoff=0`
- at least one completed run or runtime receipt with served provider/model truth
- evidence receipts present from the spine path
- tick N output changes tick N+1 routing/adaptation evidence

## Loops 2-11 Packets

| # | Loop | Verdict | Owner surface | Replay command | Blocker |
|---|------|---------|---------------|----------------|---------|
| 2 | Organism Heartbeat | PARTIAL | loop supervisor state + runtime receipts | `python3 scripts/governance/cybernetics_codex_audit.py --json` | No dedicated closure receipt tying heartbeat decisions to later action/adaptation. |
| 3 | Evolution Loop / DarwinEngine | PARTIAL | `~/.dharma/evolution/archive.jsonl` | `python3 scripts/governance/cybernetics_codex_audit.py --json` | Archive activity exists, but external fitness authority is not proven and One Wire is below quorum. |
| 4 | Consolidation Loop / Memory | PARTIAL | runtime receipts + memory/consolidation artifacts | `python3 scripts/governance/cybernetics_codex_audit.py --json` | No dedicated closure receipt proving consolidated output changes later context. |
| 5 | Zeitgeist Scanner | PARTIAL | runtime receipts + gate pressure outputs | `python3 scripts/governance/cybernetics_codex_audit.py --json` | No dedicated closure receipt proving environmental sensing changes S3/S5 constraints. |
| 6 | Witness Auditor | PARTIAL | `runtime_receipts` + witness logs | `python3 scripts/governance/cybernetics_codex_audit.py --json` | Audit activity exists, but live Loop 1 action stream is not closure-proven. |
| 7 | Training Flywheel | PARTIAL | evolution archive + training/flywheel receipts | `python3 scripts/governance/cybernetics_codex_audit.py --json` | Training/adaptation authority is not closure-proven on live task outcomes. |
| 8 | Recognition Loop / eigenform | PARTIAL | evolution archive + recognition seed outputs | `python3 scripts/governance/cybernetics_codex_audit.py --json` | Recognition activity exists, but its effect on future context/routing is not receipted. |
| 9 | Conductors | PARTIAL | runtime receipts + conductor outputs | `python3 scripts/governance/cybernetics_codex_audit.py --json` | Runtime substrate is active, but conductor action/adaptation lacks a dedicated closure packet. |
| 10 | Context Agent | PARTIAL | runtime receipts + context bundles | `python3 scripts/governance/cybernetics_codex_audit.py --json` | Context activity is present, but no replayable receipt proves context updates change later task execution. |
| 11 | Replication Monitor | PARTIAL | runtime receipts + child-run records | `python3 scripts/governance/cybernetics_codex_audit.py --json` | Runtime substrate is active, but replication trigger/effect is not closure-proven. |

## Loops 12-13 Packets

Verdict: `BLOCKED`

Replay command:

```bash
python3 scripts/governance/cybernetics_codex_audit.py --json
```

Blocker: One Wire guardian quorum is `N=3/5, M=1/3`. These loops must remain
blocked until external acted receipts satisfy quorum and archive fitness risk is
cleared.

## SAB Shadow Wire

SAB submission is intentionally shadow-only unless explicitly enabled:

```python
from dharma_swarm.connectors.sab_client import post_run_shadow_hook

post_run_shadow_hook(
    run_id="run_id",
    agent_uid="cybernetics_codex",
    summary="Loop packet emitted",
    evidence={"audit": "cybernetics_codex.audit.v2"},
)
```

Live SAB submit requires `DHARMA_SAB_BRIDGE_ENABLED=1`, `author_id`, and an
external Ed25519 signature. The default path performs no network request.
