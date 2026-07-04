# NAGA-IR Round 1 Grounding Findings

## Initial blockers

- `python3 scripts/governance/naga_repo_grounding_check.py` exited 1 with `NAGA-GROUND-ASSURANCE-ABSENT specs/naga_ir/core.md:116`: `scripts/governance/assurance_boundary.py` is verified present on origin/main, not absent. [confidence: 100/100]
- `python3 scripts/governance/naga_spec_constraint_check.py` exited 1 with `NAGA-CONSTRAINT-TCB specs/naga_ir/core.md:116`: the `packages/telos-kernel/` mention lacked a nearby `<= 5000 LOC` TCB ceiling. [confidence: 100/100]

## Corrections applied

- `core.md / Local integration` now says origin/main contains `scripts/governance/assurance_boundary.py`, plus `dharma_swarm/coalgebra.py`, `docs/telos-engine/01_SATTVA_VISION.md`, and `packages/telos-gatekeeper/`. [confidence: 99/100]
- The assurance-boundary sentence now states `assurance_boundary_report.v1`, AB-01, AB-02, AB-03, AB-04, AB-05, and exit codes 0, 1, and 2. [confidence: 98/100]
- `packages/telos-kernel/` is now future-only and constrained to `<= 5000 LOC` for TCB verifier logic. [confidence: 98/100]
- `core.md / Non-normative coalgebra` now references lowercase `bisimilar(...)` and explicitly distinguishes the future receipt reconciler functor from the existing evolution coalgebra functor. [confidence: 97/100]
- `core.md / Rollout` now says current `dharma_swarm/connectors/sab_client.py` exports `SABContribution` packets, not NAGA receipts, and that full receipt export is future PR #4 work. [confidence: 98/100]
- `core.md / Wire reference` now includes `schema_version` and `receipt_id`, matching the 15-field wire contract. [confidence: 96/100]
- `witness_mesh.md / Non-normative bisim` now avoids implementation claims about the repo `bisimilar(...)` helper and bounds authority-equivalence to finite snapshots, fixed challenge base, bounded horizon, and diagnostic observation instants. [confidence: 94/100]

## Final grounding result

- `python3 scripts/governance/naga_repo_grounding_check.py` exited 0 with `naga-repo-grounding: clean`. [confidence: 100/100]
- `python3 scripts/governance/naga_spec_constraint_check.py` exited 0 with `naga-spec-constraint: clean`. [confidence: 100/100]
