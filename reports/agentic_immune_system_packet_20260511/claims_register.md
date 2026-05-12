# Claims Register

Date: 2026-05-11
Status: draft

This register separates proof from aspiration. No public version should collapse these tiers.

## Claim Tiers

| Tier | Meaning |
|---|---|
| Proven in code | Implemented in code and located by path. |
| Partial runtime | Exists and is wired in at least one direction, but loop is incomplete. |
| Credible design | Spec/docs align with code direction but implementation is incomplete. |
| Hypothesis | Plausible, needs evidence. |
| Vision | Aspirational, not yet a claim of present capability. |
| Blocked | Cannot be claimed until human review, data, or implementation exists. |

## Register

| Claim | Tier | Evidence | Public wording |
|---|---|---|---|
| Dharma has typed metabolic objects for execution outcomes and value feedback. | Proven in code | `dharma_swarm/ontology.py` defines `Outcome`, `ValueEvent`, `Contribution`, and metabolic links. | "The internal ontology includes typed objects for outcomes and value attribution." |
| VentureCell is a first-class ontology type. | Proven in code | `dharma_swarm/ontology.py` defines `VentureCell`. | "VentureCell exists as a typed ontology object." |
| VentureCell is a full runtime-generative organ. | Partial runtime | Ontology exists, but current notes show runtime polymorphism remains open. | "VentureCell is not yet fully runtime-generative." |
| Shakti feedback from outcomes is wired. | Partial runtime | `shakti_executive/feedback_writer.py`; `shakti_executive/inputs.py`; board delta not fully steering selection. | "Outcome feedback is partially wired into Shakti selection surfaces." |
| MemoryKernel is the memory organ. | Partial runtime | `memory_kernel/facade.py`, `atoms.py`, memory census docs. Read-only in M1. | "MemoryKernel currently classifies and reads memory authority; write governance is future work." |
| SABP/Dharmic Agora can submit, witness, challenge, canonize, and compost public artifacts. | Proven in code for local runtime | `/Users/dhyana/dharmic-agora/agora/app.py` routes; SABP docs. | "The local Agora runtime has submit, witness, challenge, canon, and compost paths." |
| SABP is fully converged into one authority model. | Partial runtime | `SAB_AUTHORITY_DB_PATH` seam and test exist; docs say dual-surface remains. | "Authority convergence has begun; full domain unification remains incomplete." |
| Darwin can shadow-ingest sealed Build Protocol packets. | Proven in code | `dharma_swarm/evolution.py:apply_sealed_packet`; `tools/build_protocol/cli.py`; tests. | "Sealed build packets can be evaluated and archived in Darwin shadow mode." |
| Autonomous code-change safety is already solved. | Blocked | Live apply remains gated by env/autonomy/HOLD; guarded shadow evaluation is the current supported statement. | Do not claim. |
| Dharma Swarm is the immune system for the agentic era. | Vision / category thesis | Strong architectural fit, but not market-proven. | "Dharma Swarm is being shaped toward an immune-system role for the agentic era." |
| Immune Mission X-Ray is the right first wedge. | Hypothesis | Strong synthesis from code/docs/external landscape; no buyer proof yet. | "The leading wedge candidate is Immune Mission X-Ray." |
| The system outperforms all multi-agent systems in the world. | Blocked | No benchmark. | Do not claim. Replace with benchmark plan. |
| The system can produce public proof artifacts stronger than generic multi-agent outputs. | Hypothesis | This packet is the first test. | "This packet is a first internal test of that standard." |
| R_V is standalone evidence for machine being or structural transfer. | Blocked | SABP R_V policy forbids standalone authority. | Do not claim. Use "experimental signal" only. |
| Spiritual telos can coexist with scientific rigor. | Hypothesis / operating principle | Vow docs + SABP correction/falsifiability architecture. | "The project explicitly tries to bind spiritual telos to falsifiable, witnessed process." |

## Required Corrections Before Public Use

- Replace any absolute superiority claim with benchmark language.
- Keep R_V as experimental metadata only.
- Do not imply current external customer readiness.
- Do not expose private memory, raw transcripts, or private repo paths without review.
- Label all billion-dollar/company claims as strategic hypothesis, not fact.
