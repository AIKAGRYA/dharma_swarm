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
  "unproven_claims": [],
  "next_safe_action": ""
}
```
