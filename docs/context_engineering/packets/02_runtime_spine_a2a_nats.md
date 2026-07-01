# Packet 02: Runtime Spine, A2A, And NATS

Packet ID: `ctx.runtime-spine-a2a-nats`

Use when touching dispatch, `invoke_agent`, A2A bridges, NATS contact modules,
runtime truth packets, receipts, or cross-agent delivery claims.

Do not use for generic agent identity or tmux liveness. Use
`ctx.persistent-agent-holons` for that.

## Authority Model

- Intent owners: runtime-truth tracks in `docs/governance/ACTIVE_TRACK.yaml`
- Surface owners: `dharma_swarm/spine/**`, `dharma_swarm/a2a/**`,
  `dharma_swarm/operator_core/**`, `docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md`
- State owners: runtime DB, A2A queues, NATS state, domain reply receipts
- Proof owners: `EvidenceReceipt`, `RuntimeReceipt`, A2A task receipts,
  inbox bridge receipts, transport verifier output

Core invariant: transport liveness, task persistence, semantic reply, and final
completion are different closure layers. Do not collapse them.

## Mission

Make agent work flow through the runtime spine and cross-agent transport without
creating duplicate truth stores. A successful change strengthens the path from
request -> dispatch -> receipt -> task lifecycle -> semantic response.

## Vision Anchors

- `foundations/THE_ORGANISM.md`: runtime as coherent organism action, not
  message theater.
- `docs/vision_maps/NORTH_STAR.md`: why transport must serve real closure.
- `docs/architecture/SPINE_ADOPTION_NARRATIVE.md`: target runtime-spine
  adoption state.
- `docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md`: NATS substrate contract and
  design vision.
- `reports/swarm_genome/2026-06-11/SYNTHESIS.md`: where runtime spine sits in
  the full organism.

## Current Reality Anchors

- Run `make onboard` for current runtime-truth track status.
- `docs/governance/ACTIVE_TRACK.yaml`: runtime-truth, NATS, spine-adoption, and
  A2A cloud bridge lanes.
- `reports/governance/active_track_evidence.md`: latest rendered gate evidence.
- `reports/governance/runtime_truth_nats_council_evidence_2026-07-01.md`:
  current independent NATS review evidence.
- `reports/a2a/**`: A2A receipts and domain reply artifacts.

## Dense Docs

- `reports/a2a/A2A_MASTER_SPEC_WORKING_STATE_20260617.md`: A2A working-state
  spec.
- `docs/architecture/A2A_CLOUD_BRIDGE.md`: cloud-agent bridge design.
- `reports/governance/runtime_truth_nats_closeout_packet_2026-07-01.md`:
  latest dense NATS closeout.
- `reports/agentops/decorrelated_review_council/**`: independent runtime-truth
  council evidence.

## Work-Lane Anchors

- `runtime-truth-nats-2026-06`: fresh broker evidence and transport truth.
- `runtime-truth-spine-adoption-2026-06`: dispatch adoption and zero-bypass
  enforcement.
- `runtime-truth-reconciliation-2026-06`: receipt equivalence and projection
  truth.
- `a2a-cloud-agent-bridge-2026-06`: cloud contact through the same substrate.

## Evidence Boundary

- Canonical owner: spine/A2A/operator-core code, NATS spec, runtime DB, and
  receipt schemas.
- Projection: rendered reports, dashboards, and council summaries.
- Transient recall: prior anecdotes about liveness only justify a fresh probe.
- Forbidden-to-cite: transport liveness as semantic completion, stale receipts
  as fresh proof, secrets, or unredacted endpoint credentials.

## Future-Agent Review Hooks

- Before acting, name the closure layer: transport, dispatch, persistence,
  semantic reply, or completion.
- Before claiming complete, cite fresh proof for each layer separately.
- If evolving this packet, request a five-lane multi-agent/model review when
  practical; otherwise record the skip or failure reason in a handoff receipt.

## First Reads

L0 Safety:

- `make onboard`
- `docs/governance/ACTIVE_TRACK.yaml`

L1 Route:

- runtime-truth-reconciliation, runtime-truth-nats, runtime-truth-spine-adoption,
  and a2a-cloud-agent-bridge track blocks
- `docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md`

L2 Owners:

- `dharma_swarm/spine/`
- `dharma_swarm/a2a/`
- `dharma_swarm/operator_core/`
- `dharma_swarm/runtime_state.py`
- `scripts/runtime/codex_composer_semantic_responder.py`

L3 Evidence:

- `reports/a2a/**`
- `reports/governance/runtime_truth_*`
- `reports/governance/runtime_spine_*`
- `reports/agentops/semantic_receipts/**`

L4 Search:

- `rg -n "invoke_agent|EvidenceReceipt|RuntimeReceipt|correlation_id|trace_id" dharma_swarm tests scripts`
- `rg -n "NATS|a2a|inbox_bridge|domain_reply|semantic_receipt" docs reports scripts dharma_swarm`

L5 Seat:

- Use `codex_composer` as operational context only after receipt and health
  evidence are loaded.

## Live Probes

Read-only or narrow probes:

```bash
make onboard
python3 scripts/governance/orientation_graph.py --json
python3 scripts/governance/check_track_status.py
```

When changing spine/A2A behavior, run the narrowest relevant tests:

```bash
pytest tests/test_spine_persistence_invariant.py
pytest tests/test_codex_composer_semantic_responder.py
pytest tests/test_a2a_inbox_bridge_tmux_scripts.py
```

If probing NATS or live bridges, label the probe as live-state evidence, not
semantic completion proof.

## Retrieval Contract

- Query: "A2A single persistence invariant runtime receipt"
  Source family: tests plus `dharma_swarm/operator_core/**`.
  Use for preventing double receipts.
- Query: "semantic responder domain reply receipts"
  Source family: `scripts/runtime/codex_composer_semantic_responder.py`,
  `reports/a2a/**`.
  Use for semantic-response proof.
- Query: "NATS substrate master spec transport contact"
  Source family: NATS spec and `dharma_swarm/a2a/*nats*`.
  Use for transport-layer changes.

## Operating Loop

1. Orient with `make onboard` and the relevant active track.
2. Identify the closure layer being changed.
3. Read the owner module and its tests before broad search.
4. Make the smallest change at the owner boundary.
5. Run targeted tests.
6. Record which receipt type proves the change.
7. If live contact was not tested, say so directly.

## Guardrails

- Do not create a new daemon, broker, receipt system, or truth store.
- Do not use NATS port openness as semantic contact proof.
- Do not use tmux session existence as A2A completion proof.
- Do not mint multiple runtime receipts for the same A2A path.
- Do not weaken spine or transport tests to make claims pass.
- Do not expose private agent memory or tool internals across A2A; A2A agents
  collaborate through declared capabilities and exchanged artifacts.

## Context Budget

- Tiny: `make onboard`, active-track blocks, this packet.
- Standard: tiny plus NATS spec, spine receipt modules, A2A contact module, one
  latest receipt directory.
- Deep: standard plus responder script, runtime truth reports, task lifecycle
  tests, and domain reply artifacts.

## Done Criteria

Complete means:

- closure layer is named;
- owner module and tests are read;
- no new authority surface is introduced;
- targeted tests or live receipts prove the claim;
- handoff names the exact receipt or test file.

## Agent Prompt Block

```text
You are working in Dharma Swarm using context packet ctx.runtime-spine-a2a-nats.
Separate closure layers: transport, dispatch, persistence, semantic reply, and
completion. Start with make onboard and ACTIVE_TRACK.yaml. Read the owner module
and tests for the layer you touch. Do not create a new truth store or receipt
system. Verify with targeted tests or fresh receipts, and label any untested live
claim as unproven.
```

## Handoff Receipt Shape

```json
{
  "packet_id": "ctx.runtime-spine-a2a-nats",
  "closure_layer": "transport|dispatch|persistence|semantic_reply|completion",
  "owner_files": [],
  "receipt_types": [],
  "commands_run": [],
  "fresh_live_evidence": [],
  "tests": [],
  "claims_with_citations": [],
  "claims_not_made": [],
  "unproven_claims": [],
  "next_packet": "",
  "residual_risk": "",
  "next_safe_action": "",
  "next_step": ""
}
```
