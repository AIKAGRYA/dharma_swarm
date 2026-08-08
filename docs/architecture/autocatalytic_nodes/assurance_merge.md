---
title: Assurance and Merge Membrane
status: active_reference
authority: local_evidence
---

# Assurance and Merge Membrane

Producer: claim-evidence binding, Titanium CI truth, and Merge Master Mike form one fail-closed integration membrane. It binds `sovereign-safety-tcb-2026-07`, `repository-titanium-hardening-2026-07`, and `merge-master-mike-d4-2026-06`.

Contract: consume `proposed_change`; apply `assure_and_integrate`; emit `verified_release` to [Operator Experience](operator_experience.md).

Proof surfaces: [`check_claim_evidence_binding.py`](../../../scripts/governance/check_claim_evidence_binding.py), [`ci_truth.py`](../../../scripts/runtime/ci_truth.py), and [`pr_merge_control.py`](../../../scripts/runtime/pr_merge_control.py).

Current adapter projection: `assurance.ci_contract_fail_closed` loads the real CI truth contract and evaluates an empty evidence rollup. It emits `not_verified`; there is no exact candidate SHA, authentic CI rollup, clean-room receipt, merge, or release authority.

Promotion obligations:

- observe every required CI context on the exact candidate SHA;
- require the declared evidence grade and operator-ratified branch policy;
- retain an independent clean-room receipt for the release boundary.

Forbidden claim: local tests, a green subset, or merge eligibility is not an integrated release until the exact merge/effect receipt exists.

Operator page: `/dashboard/organism/assurance_merge`.
