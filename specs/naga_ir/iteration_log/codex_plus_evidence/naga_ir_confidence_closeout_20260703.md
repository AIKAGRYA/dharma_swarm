# NĀGA-IR Confidence Closeout

Generated at: 2026-07-03T16:08Z

Target: `specs/naga_ir/` PR #2 spec-only draft

Final confidence: 91/100 for PR #2 spec-only scope

## Scope

This closeout covers only the spec triple:

- `specs/naga_ir/core.md`
- `specs/naga_ir/receipt_wire.md`
- `specs/naga_ir/witness_mesh.md`

It does not claim implementation readiness, executable proof, receipt emission, SAB submission, titanium metadata, reconciler implementation, or full default decorrelated provider-council consensus.

## External blocker

The default council runner could not complete the required Ollama Cloud adversarial lane because the provider returned a weekly usage-limit 429. The persistent `palantir-pilot` witness was fresh and running. Therefore this closeout must be described as native six-agent plus adversarial review, not as a completed default external-provider council.

Failed provider-council artifact:

- `reports/agentops/decorrelated_review_council/20260703T154920Z-naga-ir-pr2-adversary-hold_blockers.json`
- `reports/agentops/decorrelated_review_council/20260703T154920Z-naga-ir-pr2-adversary-hold_blockers.md`

## Native agents

Adversarial lane:

- Initial score: 76/100, blocked on B1-B6.
- Re-score after patches: 89/100, blocked only on F1 authority key not binding claim content.
- Final re-score after `claim_hash` patch: 91/100, approved for PR #2 spec-only scope.

Defender lanes:

- Formal-methods defender: 89/100 before final patch, then 93/100 pass.
- Wire/security defender: 86/100 before final patch, then 92/100 pass.
- Mesh/distributed defender: 92/100 pass.
- Repo/governance defender: 92/100 pass.
- Philosophy/formal-boundary defender: 92/100 pass.
- PR-readiness defender: 91/100 pass.

## Resolved blockers

- B1 wire signature/hash contradiction: fixed with JCS signing input, hash URI grammar, signature object, signature policy, and non-canonical example label.
- B2 self-reported challenge absence: fixed with `challenge_base`, mesh-state query, and non-authoritative `challenge_state`.
- B3 authority matching: fixed with shared `canonical?`, evidence-aware authority matching, checked-refinement exception, and fragment version.
- B4 underdefined thresholds: fixed with `claim_strength`, class/strength admissibility tables, thresholded `Tested_by`, and `mutation_policy`.
- B5 mesh formality: fixed with join-semilattice merge model and CRDT scope limited to receipt-event convergence.
- B6 formal overclaim: fixed by marking coalgebra, type theory, bisimulation, and dharma/formal convergence as non-normative or target-only.
- F1 mutable `claim_id` key risk: fixed with `claim_hash` derived from the canonical claim object and included in `authority_key`.

## Local checks

Mechanical checks passed over `specs/naga_ir/`:

- no exclamation points;
- no markdown italic markers;
- no `sha256:...` placeholder hashes;
- no empty `signatures: []` example;
- no `not_measured` or canonical `not_claimed` threshold;
- all section headers are under six words.

Current-state repo facts preserved:

- `scripts/governance/assurance_boundary.py` is absent.
- `packages/telos-kernel/` is absent.
- `packages/telos-gatekeeper/` is present.
- `dharma_swarm/coalgebra.py` is present.
- `docs/telos-engine/01_SATTVA_VISION.md` is present.

## Final label

Truthful label: `91/100 PR #2 spec-only confidence`.

Do not round this to 95/100 or 100/100. Do not claim full external provider consensus until the quota-blocked council lanes can be rerun successfully.
