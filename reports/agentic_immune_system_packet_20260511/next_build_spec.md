# Next Build Spec: ProofArtifact Contract

Date: 2026-05-11
Status: draft build direction, not yet a sealed Build Protocol packet

Telos: Make the first proof artifact causally visible to the swarm without creating a parallel runtime.

## Problem

The session produced a coherent artifact concept:

```text
ProofArtifact
```

But the current runtime does not yet have a first-class contract that binds:

- claim register,
- evidence refs,
- gate results,
- witness refs,
- SABP submission status,
- Outcome / ValueEvent / Contribution,
- opportunity board feedback,
- sealed Build Protocol improvement packet.

Without this, the "Agentic Era Immune System" artifact can become another document rather than a causal event.

## Minimal Slice

Do not add a large new subsystem.

First slice:

1. keep the packet in `reports/agentic_immune_system_packet_20260511/`,
2. use `proof_artifact_contract.json` as the operational schema draft,
3. add a future adapter that can validate this contract and emit:
   - a Build Protocol spec,
   - a SABP submission payload,
   - or an Outcome projection.

## Acceptance Criteria

- The artifact has an ID.
- Every central claim has a tier.
- Every evidence item has a path or external source label.
- Human boundary decisions are explicit.
- Public membrane state is represented.
- Internal feedback state is represented.
- The contract can be rendered into a Build Protocol spec without inventing a second packet format.

## Forbidden In This Slice

- No new orchestrator.
- No new dashboard.
- No live self-modification.
- No direct write to `~/.dharma` runtime state from this report packet.
- No claim that the artifact is public, canonized, or production-ready before witness/challenge.

## First Implementation Target

Likely future file:

```text
tools/build_protocol/proof_artifact_to_spec.py
```

Job:

```text
proof_artifact_contract.json
  -> Pilot-00 compatible markdown spec
  -> dharma-build plan
  -> dharma-build seal
  -> dharma-build shadow-apply
```

This keeps the new object inside the existing build spine.

