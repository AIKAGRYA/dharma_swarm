# Label Taxonomy and Gold-Label Plan

Role: active report / training-readiness plan

## Label Taxonomy

Gold labels:

- `valid_receipt`: receipt has typed fields, traceable artifact refs, truthful status, and no hidden authority jump.
- `unsupported_claim`: claim is not backed by cited evidence, external proof, tests, or artifact hashes.
- `weak_completion`: output sounds complete but misses a required artifact, command, test, receipt, or proof boundary.
- `bad_route`: route/provider/agent choice violates capability, cost, privacy, authority, or freshness constraints.
- `privacy_violation`: raw secret, private body, credential, path, account id, provider payload, or sensitive material leaks.
- `good_next_action`: proposed next step is concrete, scoped, feasible, and improves evidence or loop closure.
- `needs_external_verification`: internal receipts are insufficient and an external check, hidden holdout, live test, or operator evidence is required.
- `real_completion`: current evidence proves the scoped requirement is satisfied with no required work remaining.

Secondary weak-label fields:

- `provider_success`
- `provider_failure_class`
- `route_selected`
- `route_success`
- `semantic_receipt_verdict`
- `test_pass`
- `forge_closeout`
- `privacy_redaction_required`
- `external_evidence_present`

## Gold Set Size

Target: 500 to 1,000 items.

Initial split:

- 150 receipt-validity items
- 150 unsupported or weak-completion items
- 100 route/provider decision items
- 100 privacy and redaction boundary items
- 100 evidence sufficiency and external-verification items
- 50 downstream next-action ranking items
- 50 real-completion positive controls

If starting at 500 items, keep the same proportions and double later.

## Sampling Plan

Use stratified sampling over:

- record type
- source surface
- timestamp bucket
- provider/model family
- pass/fail outcome
- route success/failure
- privacy risk
- external evidence present/absent

Hard anti-leakage rule:

- Gold labels for hidden holdout items must not be written into agent-readable training paths.
- Public docs may describe taxonomy and aggregate counts only.

## Labeling Instructions

For each item, labelers receive:

- task or claim summary, redacted;
- candidate output or receipt summary, redacted;
- evidence refs and hashes;
- deterministic check outputs if available;
- route/provider metadata;
- privacy tags;
- source surface and timestamp bucket.

Labelers must answer:

1. Is the claim supported by evidence?
2. Is completion actually proven?
3. Is any required evidence missing?
4. Is there privacy or authority risk?
5. Is the selected route appropriate?
6. What next action is required?
7. What label(s) apply?
8. Confidence: 0.0 to 1.0.

## Adjudication

Rules:

- Two independent labels per gold item.
- Conflict on `privacy_violation`, `real_completion`, or `unsupported_claim` requires adjudication.
- Privacy conflict defaults to violation until cleared.
- Completion conflict defaults to not complete until evidence is added.
- Route conflict defaults to `revise` or `escalate`, not `approve`.

Adjudicated record must include:

- `gold_labels`
- `label_source`
- `labeler_id_hashes`
- `adjudicator_id_hash`
- `adjudication_state`
- `rationale_refs`
- `evidence_refs`

## Training Use

Use labels for:

- multi-label classification;
- pairwise ranking of candidate outputs/actions;
- calibration targets;
- privacy/safety recall;
- active-learning disagreement selection.

Do not use labels to:

- auto-approve public claims;
- mutate routing policy directly;
- update Forge/DGM/archive fitness.
