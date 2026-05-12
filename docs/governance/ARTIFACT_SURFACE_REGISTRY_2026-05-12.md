# Artifact Surface Registry - 2026-05-12

## Decision

`dharma_swarm.insight_brief` remains the canonical private daily brief.

`operator_brief` remains parked.

`Immune Mission X-Ray` is a wrapper packet, not another brief. It may consume
Repo X-Ray evidence, daily/operator projections, red-line checks, and
ProofArtifact closure, but it must not replace any of them.

## Surface Map

| Surface | Role | Status | Owns |
|---|---|---|---|
| Agent role briefings | prompt context | active prompt fuel | agent role identity and cognitive division of labor |
| Daily Insight Brief | daily private brief | canonical | ontology-cited Outcome projection for Dhyana |
| Operator Brief PR57 | daily private brief | parked | historical alternate operator-brief experiment |
| Daily Operating Brief | operator projection | projection | operating facts from AgentOps, Kaizen, burn, YDS, revenue |
| Repo X-Ray | static code diagnostic | active evidence surface | code risk, complexity, dependency, hotspot evidence |
| Immune Mission X-Ray | mission trust diagnostic | wrapper | claims, evidence tiers, correction, permission, rollback, next proof packet |
| ProofArtifact | causal closure packet | active contract | claim/evidence/gate/witness/challenge/correction/next-action binding |

## Non-Overlap Rules

1. Do not create a second canonical daily brief.
2. Do not unpark `operator_brief` without an explicit ontology contract decision.
3. Do not make Immune Mission X-Ray a dashboard, daemon, or persistent agent loop.
4. Do not treat Repo X-Ray as the whole product; it is code-risk evidence.
5. Do not treat ProofArtifact as a manifesto; it is the contract into Build Protocol.
6. Evolution remains shadow-only until a human approves a bounded implementation packet.

## Actual Wiring

```text
Immune Mission X-Ray
  -> repo_xray_evidence
  -> redline_preflight
  -> proof_artifact_contract
  -> proof_artifact_to_spec
  -> dharma-build plan/seal
  -> Darwin shadow apply
```

This is hardening, not expansion. The new layer names boundaries and composes
existing tools; it does not add a new source of truth.

## Code Authority

The executable registry lives at:

```text
dharma_swarm/artifact_surfaces.py
```

Focused tests:

```text
tests/test_artifact_surfaces.py
tests/test_immune_mission_xray.py
```
