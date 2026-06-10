# Spine Adoption Narrative

**Track:** `runtime-truth-spine-adoption-2026-06` (ACTIVE_TRACK.yaml, v2 portfolio)
**Spine objective:** substrate-nativeness
**Status at writing (2026-06-11):** 5/7 completion criteria; the receipt path is
wired and test-proven; GATE 1 (operator-witnessed live receipt) not yet cleared.

## What the spine is

One blessed invocation path and one receipt per dispatch:

```
caller ──► invoke_agent(task, agent_id, context_id, routing, invoker)
                │
                ▼
        EvidenceReceipt  (exactly one per dispatch — not zero, not two)
                │
                ▼
        delegation_runs.receipt_json   (~/.dharma/state/runtime.db)
```

- `dharma_swarm/spine/invoke.py` — `invoke_agent()`, the one door.
- `dharma_swarm/spine/receipt.py` — `EvidenceReceipt`, the proof object
  (trace/span/task/agent identity, status, error source, latency, routing id).
- `dharma_swarm/spine/persistence.py` — `persist_receipt()` writes the receipt
  JSON onto the task's `delegation_runs` row; `ensure_receipt_column()` is the
  idempotent migration.

The doctrine line: **a dispatch that produced no receipt did not happen, and a
receipt that no operator can observe is not proof.** Receipts must land in a
store the operator can query without trusting any agent's claim.

## Adoption state (verified, not narrated)

| Surface | State | Mechanism |
|---|---|---|
| `a2a/a2a_bridge.py` | **Adopted (adapter)** | `submit_via_spine()` dispatches via `invoke_agent`; the legacy `A2AServer.submit()` runs *inside* the invoker so identity/idempotency/task-log behavior is unchanged. Production wiring of the trishula-inbox path is Slice 2 (allowlisted at `a2a_bridge.py:307`). |
| `orchestrator.py` | **Adopted (flag-gated)** | `_run_task_via_spine()` behind `DHARMA_SPINE_DISPATCH=1` (default OFF; flag-off path byte-identical). Emits exactly one receipt per dispatch **and persists it** to `delegation_runs.receipt_json` (fail-open: a persistence error logs a warning and never breaks dispatch). |
| `agent_runner.py` | **Not adopted** | Largest surface, migrated last by design. |

Known intentional bypasses are declared in
`scripts/governance/spine_bypass_report.py::_INTENTIONAL_BYPASS` (5 sites at
writing: trishula inbox, node_gateway ×2, a2a_client local dispatch,
nats_transport). The track completes when that dict drains to `{}`.

## How completion is measured (and why the criteria look like this)

`scripts/governance/check_track_status.py` evaluates the 7 criteria in
ACTIVE_TRACK.yaml. Two deserve explanation:

- `dispatch_emits_evidence_receipt` / `zero_dropoff_sources` point at named
  tests in `tests/test_spine_adoption_dispatch.py`. The tests are the real
  artifact: one counts actual `invoke_agent` traversals across repeated
  dispatches (exactly one distinct receipt each); the other asserts **no
  unaccounted bypass site exists** and that the declared allowlist has not
  rotted (every declared site must still match a scanned site exactly).
- `bypass_allowlist_empty` matches the literal drained form of
  `_INTENTIONAL_BYPASS` — it can only pass when the last bypass is migrated.

These are proxies. The non-proxy gate is below.

## GATE 1 — the operator-witnessed receipt

No agent may self-certify the spine. The gate clears only when the operator
*observes* a receipt land from a real dispatch:

```bash
dgc down
export DHARMA_SPINE_DISPATCH=1 && dgc up --background
bash scripts/governance/gate1_witness.sh --watch
```

The kit baselines `COUNT(receipt_json IS NOT NULL)` in `delegation_runs` and
prints the new receipt (run/task/agent/status + sha256) the moment the count
moves. History note: the first version of this gate watched a column nothing
wrote — the receipt existed only in memory. A divergence round caught it; the
persistence wire (orchestrator → `persist_receipt`) is what made the gate
falsifiable. That episode is the track's reason for existing, in miniature.

## Remaining work (honest queue)

1. **GATE 1** — operator witnesses the first live receipt (kit above).
2. **Slice 2** — wire `submit_via_spine` into the trishula-inbox path
   (`a2a_bridge.py:307`); sync→async bridging, dual-audit required.
3. **agent_runner.py** — migrate `run_task` through `invoke_agent`.
4. **Drain the allowlist** — node_gateway ×2, a2a_client, nats_transport
   (coordinate with the NATS lane owner), then trishula; dict reaches `{}`.
5. CI enforcement (allowlist-at-zero) once drained.

## Non-goals (track discipline)

No new spine sub-modules; no EvidenceReceipt schema changes; no NATS/Redis/gRPC
here (transport belongs to the NATS lane); no broad refactors of
`swarm.py` / `providers.py` / `SwarmManager`.
