# Spine Adoption Narrative

**Track:** `runtime-truth-spine-adoption-2026-06` (ACTIVE_TRACK.yaml, v2 portfolio)
**Spine objective:** substrate-nativeness
**Status at writing (2026-06-11):** 5/8 completion criteria; the receipt path is
wired and test-proven; GATE 1 (operator-witnessed live receipt) not yet cleared —
and is itself the 8th completion criterion, so the track cannot ship without it.

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

Surface split (two persistence regimes, one doctrine): the **orchestrator**
surface persists its receipt into `delegation_runs.receipt_json` (the column
GATE 1 watches); the **A2A** surface persists canonically via `RuntimeReceipt`
+ `IdempotencyRecord` and leaves `receipt_json` empty — an empty blob on an A2A
row is success, not failure (see `spine/persistence.py` and
`tests/test_spine_persistence_invariant.py` invariant 7).

## Adoption state (verified, not narrated)

| Surface | State | Mechanism |
|---|---|---|
| `a2a/spine_adapter.py` | **The one blessed A2A submit path** | `submit_task_via_spine()` (+ sync wrapper) dispatches via `invoke_agent`; the legacy `A2AServer.submit()` runs *inside* the invoker so identity/idempotency/task-log behavior is unchanged. This is the single `.submit()` call site the bypass scan blesses. |
| `a2a/a2a_bridge.py` | **Adopted (delegates)** | `submit_via_spine()` / `_submit_via_spine_sync()` delegate to the shared adapter; trishula-inbox ingest (Slice 2) dispatches through it. |
| `a2a/node_gateway.py` | **Adopted 2026-07-03** | Both submit endpoints (`POST /tasks`, `POST /a2a/tasks`) dispatch through `submit_task_via_spine` (one EvidenceReceipt per HTTP submit; pre-spine 500-on-internal-error contract preserved). |
| `a2a/a2a_client.py` | **Adopted 2026-07-03** | `_dispatch_local` dispatches through `submit_task_via_spine_sync` (one EvidenceReceipt per in-process delegation; `trc_` auto-trace contract preserved). |
| `a2a/nats_transport.py` | **Adopted 2026-07-03** | `consume_message` dispatches through `submit_task_via_spine` on top of its transport-level ExecutionIdentity/idempotency/ack-nack receipts (exception→nack contract preserved). |
| `orchestrator.py` | **Adopted (default-on)** | `_run_task_via_spine()`; `DHARMA_SPINE_DISPATCH` explicit false-like values opt out. Emits exactly one receipt per dispatch **and persists it** to `delegation_runs.receipt_json` (fail-open: a persistence error logs a warning and never breaks dispatch). |
| `agent_runner.py` | **Leaf by design** | `run_task` is the execution leaf invoked *inside* spine-wrapped callers (orchestrator / A2A adapter); it does not submit around the spine. |

The intentional-bypass allowlist
(`scripts/governance/spine_bypass_report.py::_INTENTIONAL_BYPASS`) **drained to
`{}` on 2026-07-03**. It is held at zero two ways: the `spine_bypass_entries`
quality-ratchet baseline is 0 (CI fails on any new entry), and the
`spine-ownership` uplift guard fails closed on any unknown site or any
allowlist entry above the ratchet baseline. The only sanctioned relief is a PR
that visibly raises the baseline with review
(ORGANISM_REWIRE_DOCTRINE_2026-07-02 §1).

## How completion is measured (and why the criteria look like this)

`scripts/governance/check_track_status.py` evaluates the 8 criteria in
ACTIVE_TRACK.yaml. Three deserve explanation:

- `dispatch_emits_evidence_receipt` / `zero_dropoff_sources` point at named
  tests in `tests/test_spine_adoption_dispatch.py`. The tests are the real
  artifact: one counts actual `invoke_agent` traversals across repeated
  dispatches (exactly one distinct receipt each); the other asserts **no
  unaccounted bypass site exists** and that the declared allowlist has not
  rotted (every declared site must still match a scanned site exactly).
- `bypass_allowlist_empty` matches the literal drained form of
  `_INTENTIONAL_BYPASS` — it can only pass when the last bypass is migrated.
- `gate1_witnessed` requires `reports/governance/GATE1_WITNESSED.md`, written
  only by `gate1_witness.sh --watch` at the moment the operator observes a live
  receipt land (freshness-guarded baseline; the receipt's sha16 is recorded and
  checkable against the DB). This wires the non-proxy gate into completion —
  the track cannot flip SHIPPABLE on file/test proxies alone. Known limitation,
  by design: `file_exists` can be hand-written, but the sha makes fabrication an
  auditable lie rather than a satisfied proxy.

The other seven are proxies. The non-proxy gate is below.

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

1. **GATE 1** — operator witnesses the first live receipt (kit above). This is
   the only remaining item; everything below it is done.
2. ~~Slice 2 — trishula-inbox path~~ (done 2026-07-02).
3. ~~agent_runner.py~~ — resolved architecturally: `run_task` is the leaf
   invoked inside spine-wrapped callers; no bypass submit path exists.
4. ~~Drain the allowlist~~ (done 2026-07-03 — node_gateway ×2, a2a_client,
   nats_transport all through `spine_adapter.submit_task_via_spine`; dict is `{}`).
5. ~~CI enforcement (allowlist-at-zero)~~ (done 2026-07-03 — ratchet baseline 0
   + `spine-ownership` uplift guard invariant 3).

## Non-goals (track discipline)

No new spine sub-modules; no EvidenceReceipt schema changes; no NATS/Redis/gRPC
here (transport belongs to the NATS lane); no broad refactors of
`swarm.py` / `providers.py` / `SwarmManager`.
