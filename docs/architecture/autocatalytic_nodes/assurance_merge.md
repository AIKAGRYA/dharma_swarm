---
title: Assurance and Merge Membrane
status: active_reference
authority: local_evidence
---

# Assurance and Merge Membrane

Producer: claim-evidence binding, CI truth, and merge control form one fail-closed integration membrane. It binds the active `organism-rewire-2026-07` substrate lane and `dharmagraph-engine-2026-07` execution lane; retired assurance tracks remain historical evidence rather than active authority.

Contract: consume `proposed_change`; apply `assure_and_integrate`; emit `verified_release` to [Operator Experience](operator_experience.md).

Proof surfaces: [`check_claim_evidence_binding.py`](../../../scripts/governance/check_claim_evidence_binding.py), [`ci_truth.py`](../../../scripts/runtime/ci_truth.py), and [`pr_merge_control.py`](../../../scripts/runtime/pr_merge_control.py).

Current adapter projection: `assurance.ci_contract_fail_closed` loads the real CI truth contract and evaluates an empty evidence rollup. It emits `not_verified`; there is no exact candidate SHA, authentic CI rollup, clean-room receipt, merge, or release authority.

Promotion obligations:

- observe every required CI context on the exact candidate SHA;
- require the declared evidence grade and operator-ratified branch policy;
- retain an independent clean-room receipt for the release boundary.

Forbidden claim: local tests, a green subset, or merge eligibility is not an integrated release until the exact merge/effect receipt exists.

Operator page: `/dashboard/organism/assurance_merge`.
