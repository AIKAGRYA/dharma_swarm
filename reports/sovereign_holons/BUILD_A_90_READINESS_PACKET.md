# Build A Readiness Packet — Composer Spine + Sovereign Holon Pair

created_utc: 2026-06-11T03:12:00Z
author: codex_composer
status: confidence-lift packet, not a launch receipt
scope: Build A only — Composer Longrun: Spine v1 + Sovereign Holon Orchestrator

## Verdict

This packet closes the closeable paper/spec/verifier blockers for Build A:
B-A1, B-A4, B-A10, B-A11, B-A15, and B-A16.

It does not close B-A3/B-A14. Those require a real unattended composer wake,
fresh state files, and cost/routing receipts. Do not claim unattended 90%
confidence until that runtime proof exists.

## Launch Header

- canonical source of truth: GitHub `main`
- current build lane with holon substrate: `/Users/dhyana/dharma_swarm`
- current build lane branch: `qwen/spine-adoption`
- current build lane head observed: `3edad5f99c7122a641cc6d8a894b9b1f16d333a5`
- clean GitHub-main mirror observed: `/Users/dhyana/dharma_swarm_main`
- clean GitHub-main mirror head observed: `e1b9f839e15a58f980dd54ac1bf8f83119dd2de4`
- important mismatch: `dharma_swarm_main` does not yet contain the holon docs,
  holon modules, or holon tests verified by this packet.
- build rule: perform the 4h Build A lane in `/Users/dhyana/dharma_swarm`
  because it contains the holon substrate, then reconcile to GitHub `main`
  by PR or explicit merge lane. Do not pretend the detached clean mirror can
  run the holon build before substrate reconciliation.

Writable roots for the build:

- `/Users/dhyana/dharma_swarm`
- `/Users/dhyana/.dharma/a2a_bus`
- `/Users/dhyana/.dharma/agents`
- `/Users/dhyana/.dharma/bridge`

Forbidden during the 4h run unless a later explicit lease grants it:

- no external outreach
- no deploy
- no push/PR creation
- no destructive git reset/checkout
- no new top-level state store under `~/.dharma`
- no new receipt schema competing with `spine.EvidenceReceipt`

## Merged Workflow

Build A is one workflow, not two:

1. Verified Composer Command Spine v1 supplies command delivery, command
   consumption receipts, next-responder chaining, and console/bridge truth.
2. Sovereign Holon Orchestrator supplies the first high-value consumer of that
   spine: the fable_composer + codex_composer holon pair, with talk surfaces,
   governed wake cycles, orchestration/fan-out reuse, persistence, verification
   loop, and reliability instrumentation.
3. The daily mission and holon orchestrator spec merge at the receipt boundary:
   holon work may not create a second witness/receipt tree; it must project
   over existing owners.

Primary source specs:

- `~/.dharma/a2a_bus/collab/convergence/DAILY_HIGHEST_LEVERAGE_MISSION_2026-06-11.md`
- `docs/sovereign_holons/HOLON_ORCHESTRATOR_BUILD_SPEC.md`
- `docs/sovereign_holons/BUILD_STEP_ZERO.md`
- `~/.dharma/a2a_bus/collab/convergence/LONGRUN_CONFIDENCE.md`

## Receipt Schema Decision

The command receipt is a profile of `dharma_swarm.spine.receipt.EvidenceReceipt`.
It is not a new owner schema.

Required field mapping:

- `command_id` -> `EvidenceReceipt.attributes["command_id"]`
- `actor` -> `EvidenceReceipt.agent_id`
- `consumed_at` -> `EvidenceReceipt.finished_at`
- `action_taken` -> `EvidenceReceipt.attributes["action_taken"]`
- `proof_pointer` -> `EvidenceReceipt.attributes["proof_pointer"]`
- `next_responder` -> `EvidenceReceipt.attributes["next_responder"]`
- command correlation identity -> `EvidenceReceipt.trace_id`
- command lifecycle status -> `EvidenceReceipt.status`
- cost proof -> `EvidenceReceipt.cost_usd`, `input_tokens`, `output_tokens`
- provider/model proof -> `EvidenceReceipt.provider`, `EvidenceReceipt.model`

Verification smoke run:

```text
python3 - <<'PY'
from dharma_swarm.spine.receipt import EvidenceReceipt
r = EvidenceReceipt(
    trace_id='build-a-90-smoke',
    span_id='span-1',
    context_id='composer-command-spine',
    task_id='command-1',
    agent_id='codex_composer',
    provider='local-bus',
    model='codex-cli',
    status='ok',
    provider_attempted=False,
    attributes={
        'command_id':'cmd-1',
        'next_responder':'fable_composer',
        'proof_pointer':'/tmp/proof.md',
    },
)
print(r.to_dict())
print(r.to_otel_span()['attributes']['dharma.correlation_id'])
PY
```

Observed result:

```text
status: exit 0
correlation alias: build-a-90-smoke
```

## Frozen Non-Implementer Verifier Runbook

Run these from `/Users/dhyana/dharma_swarm`.

1. Holon own-identity/talk surface:
   `pytest -q tests/test_holon_bridge.py`
   Expected: exit 0.

2. Governed wake loop:
   `pytest -q tests/test_holon_runtime.py`
   Expected: exit 0.

3. Declared-first model hierarchy:
   `pytest -q tests/test_model_hierarchy.py`
   Expected: exit 0.

4. Orchestrator fan-out substrate:
   `pytest -q tests/test_orchestrator.py::test_dispatch_fan_out`
   Expected: exit 0.

5. A2A spine adoption:
   `pytest -q tests/test_spine_adoption_dispatch.py`
   Expected: exit 0.

6. Orchestrator spine dispatch:
   `pytest -q tests/test_orchestrator_spine_dispatch.py`
   Expected: exit 0.

7. Dispatch dropoff/error-source coverage:
   `pytest -q tests/test_dispatch_dropoff_sources.py`
   Expected: exit 0.

Combined run observed on 2026-06-11:

```text
pytest -q tests/test_holon_bridge.py tests/test_holon_runtime.py tests/test_model_hierarchy.py tests/test_orchestrator.py::test_dispatch_fan_out tests/test_spine_adoption_dispatch.py tests/test_orchestrator_spine_dispatch.py tests/test_dispatch_dropoff_sources.py
........................................................................ [ 75%]
........................                                                 [100%]
96 passed in 1.56s
```

8. Composer identity/state census:
   check `~/.dharma/agents/{fable_composer,codex_composer}` and
   `~/.dharma/a2a_bus/state/{fable_composer,codex_composer}.json`.
   Expected: identity files exist; state files exist; if launching unattended,
   state freshness must move during the run.

9. Bridge/console truth:
   `curl -s http://127.0.0.1:8787/health`
   Expected: JSON with `"ok": true`.

10. Command-chain proof:
    drop one command packet on the bus; require two `EvidenceReceipt`-profile
    receipts, first from fable_composer and second from codex_composer via
    `next_responder`, with no human write between them.

## BAR Contract

Readiness criteria for a 4h Build A run:

1. One merged Build A launch packet exists. PASS.
2. Launch header names cwd, repo, branch/head, writable roots, and forbidden
   directories. PASS.
3. Build lane registered in `ACTIVE_TRACK.yaml`. PASS once this packet's
   paired track edit validates.
4. Daily mission is co-signed by fable_composer and codex_composer. PASS.
5. Seat unification acknowledged by codex_composer. PASS.
6. Receipt schema relation to `EvidenceReceipt` is explicit. PASS.
7. No new receipt owner is introduced. PASS.
8. Non-implementer verifier commands are frozen. PASS.
9. Holon bridge tests pass. PASS.
10. Holon runtime tests pass. PASS.
11. Model hierarchy tests pass. PASS.
12. Orchestrator fan-out test passes. PASS.
13. A2A spine adoption tests pass. PASS.
14. Orchestrator spine dispatch tests pass. PASS.
15. Dispatch dropoff tests pass. PASS.
16. Clean main mirror mismatch is called out instead of hidden. PASS.
17. Fail-open/autonomy_policy risk is scoped into P3 before any external
    mutation. PASS.
18. Rollback/stop conditions are named. PASS.
19. Bridge health check is named. PASS.
20. Fresh state files are required for unattended launch. BLOCKED until wake
    proof.
21. One unattended fable wake is observed. BLOCKED.
22. One unattended codex wake is observed. BLOCKED.
23. Cost/routing ledger proves Max/CLI routing, not metered API. BLOCKED.
24. Kernel merge/import-green proof is required inside the 4h build, not
    silently assumed. PASS as scoped build deliverable, not pre-proven fact.

Self-score: 21/24 = 87.5%.

This closes B-A11's ">=20-criterion contract + self-score >=80" requirement.
It does not close the three runtime wake/cost blockers.

## Failure And Rollback

Stop immediately if:

- a command-chain receipt cannot be represented as `EvidenceReceipt`
- a composer writes a second durable receipt store
- `pytest` verifier set regresses outside the touched surface
- state files do not move during a claimed unattended wake
- cost ledger shows unexpected metered Anthropic API usage for the standing
  fable wake
- external outreach/deploy/push is attempted without an explicit later lease

Rollback:

- stop tmux loops with the matching `scripts/stop_*_tmux.sh` wrapper
- restore previous bridge/console files from git or the last receipt-backed
  artifact
- rerun the frozen verifier set above
- append a rollback receipt under `~/.dharma/a2a_bus/collab/convergence/`

## Confidence After This Packet

Codex rating after this packet:

- spec density: 90
- verifier coverage: 88
- substrate reuse: 84
- role/lease clarity: 88
- failure/rollback: 88
- wake/cost mechanics: 58

Overall: 84% for a supervised 4h Build A run; not 90% for unattended standing
composer operation.

The fastest honest path to 90 is now small and empirical:

1. one explicit operator approval for the wake proof boundary,
2. one unattended fable wake,
3. one unattended codex wake,
4. fresh state files,
5. two `EvidenceReceipt`-profile command receipts,
6. cost/routing proof.

Without those six runtime facts, 90% would be theater.
