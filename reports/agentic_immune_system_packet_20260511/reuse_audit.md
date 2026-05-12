# Duplicate-First Reuse Audit

Date: 2026-05-11
Status: active guardrail for the Agentic Immune System packet

This file exists to prevent premature collapse into new names, new packet
formats, or duplicate organs. Every proposed wire starts with:

> Have we already done something similar?

## Reuse Decisions

| Proposed wire | Already done? | Evidence | Decision |
|---|---:|---|---|
| Proof artifact gate | Yes, partial | `dharma_swarm/jk_credibility_gates.py:283` defines `audit_proof_artifact`; `tests/test_jk_credibility_gates.py:154` covers clean, missing, and false-submission cases. | Reuse `audit_proof_artifact`. Do not create another proof-quality gate. If this packet needs auditing, wire it through this function or extend it narrowly. |
| Proof packet pattern | Yes | `reports/dgc_self_proving_packet_20260313/proof_packet.md` separates claims, evidence, proof boundaries, and false autonomy claims. | Treat this packet as a new domain instance of the existing proof-packet pattern, not a new framework. |
| Build spec adapter pattern | Yes | `tools/build_protocol/brief_to_spec.py:1` and `tools/build_protocol/opportunity_to_spec.py:1` render existing sources into the same Pilot-00 spec shape. `docs/architecture/WIRING_AND_LOOPS.md:41` explicitly says "No second packet format." | Any future `proof_artifact_to_spec` must be a thin sibling adapter into Pilot-00. Do not add another build packet shape. |
| Sealed improvement loop | Yes, partial/live-shadow | `docs/architecture/WIRING_AND_LOOPS.md:29` maps `ReviewPacket / ProofPacket seal -> DarwinEngine.apply_sealed_packet(shadow=True)`. `tools/build_protocol/cli.py` exposes `shadow-apply`. | Route improvements through existing Build Protocol and Darwin shadow apply. Do not invent a separate evolution lane. |
| Claim recording inside Dharma | Yes, partial | `dharma_swarm/telic_seam.py:237` records `Claim`; `dharma_swarm/telic_seam.py:283` records `Evidence`; `codex_skills/assert_claim/entry.py` is a CLI wrapper. | Use TelicSeam for internal claim/evidence memory. Do not create another local claim store. |
| Claim packet promotion in Agora | Yes | `dharmic-agora/scripts/scaffold_claim_packet.py:1` scaffolds claim packets; `dharmic-agora/scripts/validate_claim_packet.py:1` validates promotion thresholds; `dharmic-agora/agora/node_governance.py:320` evaluates stage readiness. | Export public or cross-node claims to Agora's existing claim packet schema. Do not create a Dharma-only venture claim schema. |
| Semantic Anekanta gate | Yes | `dharma_swarm/semantic_anekanta.py:1` implements deterministic Semantic Anekanta v0; `dharma_swarm/anekanta_gate.py:1` wraps it for compatibility. | Use this for many-sided grounding review. Do not create another "depth" or "multi-frame" gate. |
| Bhed Gnan / register risk gate | Yes | `dharma_swarm/bhed_gnan_gate.py:1` implements cheap register/substance checks; `dharma_swarm/bhed_gnan_monitor.py:1` records witness JSONL for resident-intelligence outputs. | Use the existing gate and monitor. New work should attach packet outputs to the monitor, not duplicate it. |
| SABP external membrane | Yes | `dharmic-agora/connectors/sabp_client.py:41` defines `SabpClient`; `dharmic-agora/connectors/sabp_cli.py:1` exposes post, evaluate, identity, DGC ingest, outcome, anti-scan, and Darwin admin commands. | Submit/evaluate through SABP client or CLI. Do not create a second Agora connector. |
| Outcome feedback | Yes, partial | `dharma_swarm/telic_seam.py:559` records `Outcome`; `dharma_swarm/telic_seam.py:646` records `ValueEvent`; `dharma_swarm/shakti_executive/feedback_writer.py` writes opportunity feedback. | Record packet results as TelicSeam outcomes/value events where possible. Do not store outcome truth only in markdown. |
| VentureCell type | Yes, type only | `dharma_swarm/ontology.py` defines `VentureCell`; `docs/architecture/WIRING_AND_LOOPS.md:78` says VentureCell polymorphism remains open. | Use VentureCell as ontology target, but do not build polymorphic VentureCell runtime yet. First prove one packet-to-outcome loop. |
| Memory authority | Yes, partial | MemoryKernel M1/M2 docs identify read facade and writer sentinel; MemoryKernel is not yet a full write gate. | Label authority in packet claims now. Do not assume MemoryKernel can safely govern every write yet. |

## Current Non-Duplicate Next Wires

The smallest safe next build moves are adapters into existing organs:

1. `proof_artifact -> audit_proof_artifact`
   - Input: `agentic_era_immune_system_dossier.md`
   - Output: existing `ArtifactAudit` JSON.
   - Why non-duplicate: it uses the existing credibility gate.

2. `claims_register -> TelicSeam Claim/Evidence`
   - Input: rows from `claims_register.md`.
   - Output: internal ontology `Claim` and `Evidence` objects.
   - Why non-duplicate: TelicSeam is already the claim/evidence write-through seam.

3. `claims_register -> Agora claim packet`
   - Input: selected public claim.
   - Output: Agora `claim.json` plus witness/red-team files using `scaffold_claim_packet.py`.
   - Why non-duplicate: Agora already owns public promotion governance.

4. `proof artifact -> Pilot-00 spec`
   - Input: this packet plus one human-approved build move.
   - Output: Pilot-00-compatible spec, like `brief_to_spec` and `opportunity_to_spec`.
   - Why non-duplicate: it reuses the existing Build Protocol parser and Darwin shadow path.

5. `packet result -> Outcome / ValueEvent / Contribution`
   - Input: audit result, claim validation, SABP response, and human acceptance.
   - Output: existing ontology metabolic objects.
   - Why non-duplicate: this closes the existing feedback loop instead of adding a report-only memory.

## Hard No List

Do not add these until the reuse path above is exhausted:

- a new packet format
- a new claim schema
- a new external membrane API
- a new semantic-depth gate
- a new outcome ledger
- a new VentureCell runtime abstraction
- a second self-improvement/evolution loop

## Open Questions Before Code

1. Which one claim from `claims_register.md` should be promoted into Agora first?
2. Should the first audit target be the dossier, the whole packet README, or a rendered combined artifact?
3. Is the first public boundary "internal proof only", "semi-public founder memo", or "Agora public submission"?
4. Should the first VentureCell label be `agentic_immune_system`, `venture_cell_proof_engine`, or stay unnamed until after one successful loop?
