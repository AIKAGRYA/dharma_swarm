# Next Goal Packet

Run: `venturecell-operator-os-autoresearch-20260602T141038Z`
Status: live draft, not final until the 8-hour contract is closed
Mission: `20260602-venturecell-operator-os-autoresearch-8h`
ds-goal progress receipt: `r-ade5bb8b586492b3`
Current scoped HEAD before this packet: `cbfb5d57 feat(operator-os): clarify completion guard policy`

This packet is the handoff for the next bounded AutoResearch loop. It must be
reviewed and updated in the final hour before reporter closure.

## Current Truth

- Operator OS status: `blocked_on_external_reader_gate`.
- Autonomy level: `L0_read_only_plan`.
- Score ledger: `100/100` live score, not final.
- ds-goal mission state: `open=1 claimed=0 completed=4 failed=0 blocked=0 total=5`.
- Reporter task: open by design.
- MemoryKernel strict eval: `pass` (`6/6`) from report-local staged sources.
- Darshan GO gate: `block_external_authority`, no accepted receipts.
- Darshan GO template: `draft_template_not_evidence`.
- Darshan GO template accepted-receipt requirements: present, not evidence.
- Live verifier matrix: present, not final.
- Authority boundary: `local_read_only_external_blocked`.
- Residual risk register: present, not final.
- Artifact manifest: present, not authority.
- Periodic onboard: pass, with optional credential warnings.
- Operator OS action ack proof: false for NATS and A2A.
- Manifest receipt inventory: present.
- Gap triage packet: `external_blocked_with_local_followups`, with external
  reader as non-local blocker and MemoryKernel truncation as local maintenance.
- Memory coverage packet: present; staging and quarantine roots are truncated,
  trusted and report-local roots are not truncated.
- Memory coverage targets: staging and quarantine are the current local
  maintenance targets.
- Digest canvas summary: present; Markdown caps repeated rows while JSON
  projection preserves full canvas data.
- Completion guard packet: `keep_reporter_open`, `not_final: true`.
- Completion guard reporter policy: terminal receipt and complete verifier pass
  required.
- Periodic onboard refresh: latest `make onboard` and toolbelt pass, with NATS
  liveness treated as repo-wide substrate context only.
- Timebox status: elapsed `10982s`, remaining `17818s`; mission not complete.
- Manifest receipt summary: manifest has receipt count and latest receipt path,
  but remains `not_final: true`.
- Manifest inventory scope: scope/name/non-final markers present; navigation
  only.
- Stable admission render: volatile admission id/time redacted; decision
  evidence remains visible.
- Timebox refresh: current clock still below 8 hours.
- Three-hour timebox proof: current clock still below 8 hours.
- Last committed packet: completion guard policy.

## Next Goal

Continue the same true 8-hour AutoResearch mission until final elapsed-time and
artifact requirements are proven. The next loop should choose one of these
bounded targets:

1. Final-window adversarial audit update.

   `06_adversary_audit.md` exists as a live draft. Re-review it only in the
   final window and keep attacking:

   - false 8-hour completion claims;
   - MemoryKernel false green claims;
   - fake GO receipt or external-reader claims;
   - fake NATS/A2A liveness;
   - Chetana trusted-promotion shortcuts;
   - broad repo dirt accidentally included in commits;
   - final reporter closure before proof.

2. MemoryKernel pass preservation under gates.

   The current eval passes from report-local staged sources. Preserve that
   boundary and rerun:

   ```bash
   pytest -q tests/test_venture_cell_operator_os_projection.py
   ./.venv/bin/python -m dharma_swarm.venture_cell.operator_os.cli --output-dir reports/venture_operator_os/venturecell-operator-os-autoresearch-20260602T141038Z
   ```

   If strict evals regress, keep the packet partial and queue repair. Do not
   promote trusted memory to make the eval green.

3. Darshan GO template hardening.

   `darshan_go_receipt_template.json` now exists. If this area is touched
   again, keep it explicitly non-evidence and test that it cannot be confused
   with accepted GO receipts.

4. Verifier matrix preservation.

   `12_live_verifier_matrix.md` now exists. Future loops should update it after
   any code, artifact, or verification change, but still keep it non-final
   until the true final window.

5. Authority boundary preservation.

   `authority_boundary_packet.json` now exists. Future loops should keep it
   derived from existing gates and must not use it as a grant of external
   authority.

6. Residual risk register maintenance.

   `14_residual_risk_register.md` now exists. Update it after any meaningful
   state change and before final reporter closure.

7. Artifact manifest maintenance.

   `operator_os_artifact_manifest.json` now exists. Future render changes
   should keep it current and non-authoritative.

8. Periodic onboard refresh.

   `16_periodic_onboard_receipt.md` now exists. Refresh onboarding/toolbelt
   evidence periodically, but do not treat repo-wide NATS liveness as
   mission-specific authority proof.

9. Liveness field discipline.

   Keep authority liveness fields action-specific. Repo-wide substrate health
   must not be renamed into mission authority proof.

10. Manifest receipt inventory.

   `operator_os_artifact_manifest.json` now lists receipt paths. Use it as an
   index, not as proof that the receipts are final.

11. Gap triage preservation.

   `operator_gap_triage_packet.json` now separates external-authority gaps from
   locally actionable maintenance gaps. Use it to pick local loops, but do not
   treat it as a gate-clearance or authority artifact.

12. Memory coverage maintenance.

   `memory_kernel_coverage_packet.json` now identifies root-level scan caps.
   If another local memory loop is chosen, target staging/quarantine retrieval
   or query-specific coverage while preserving `trusted_promotion_claimed:
   false`.

13. Digest scanability preservation.

   `operator_os_digest.md` now caps repeated canvas lane details. Treat that as
   presentation only; use `operator_os_projection.json` for full evidence.

14. Completion guard preservation.

   `operator_completion_guard_packet.json` now makes false-final blockers
   machine-readable. Do not close the reporter while it says
   `keep_reporter_open`.

15. Periodic onboard refresh.

   `23_periodic_onboard_refresh_receipt.md` records current environment facts.
   Use it as context only; do not use repo-wide NATS liveness as Operator OS
   action authority.

16. Timebox status refresh.

   `24_timebox_status_receipt.md` records current elapsed and remaining time.
   Refresh it before any final-window work.

17. Manifest receipt summary preservation.

   Use `receipt_count` and `latest_receipt_path` for navigation only. They are
   not terminal closure evidence.

18. Stable admission render preservation.

   Preserve volatile field redaction unless the underlying admission policy
   changes. Do not redact decisions or blockers.

19. Final closeout only after true-time proof.

   When elapsed time is actually in the final window, update:

   - `06_adversary_audit.md`
   - `07_score_history.md`
   - `08_metabolization_packet.md`
   - `09_next_goal_packet.md`

   Then run the minimum verification set and only then consider closing the
   reporter task with a terminal receipt.

## Required Verification For The Next Loop

Always include at least:

```bash
./.venv/bin/python scripts/runtime/autonomy_spine.py brief --mission-id 20260602-venturecell-operator-os-autoresearch-8h
pytest -q tests/test_venture_cell_operator_os_projection.py
pytest -q tests/test_darshan_external_reader_gate.py tests/test_control_surface.py -k 'GoReceiptRows or external_reader'
pytest -q tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_daily_operating_brief.py
./.venv/bin/python -m compileall -q dharma_swarm/venture_cell/operator_os
./.venv/bin/python -m dharma_swarm.venture_cell.operator_os.cli --output-dir reports/venture_operator_os/venturecell-operator-os-autoresearch-20260602T141038Z
```

If the loop only changes a report packet, also run scoped `git diff --check`.

## Do Not Do

- Do not close the reporter task until the full 8-hour contract is proven.
- Do not record terminal `completed` status for progress-only evidence.
- Do not push, merge, publish, deploy, spend, contact external readers, mutate
  credentials, or claim live external authority.
- Do not fake GO receipts.
- Do not claim NATS/A2A live work unless action-specific ack proof exists.
- Do not promote Chetana atoms to trusted without existing gates.
- Do not use `git add -A`.
- Do not include unrelated staged work in a scoped packet.

## Evidence To Read First

- `00_opening_truth.md`
- `01_program_kernel_receipt.md`
- `02_memorykernel_eval_receipt.md`
- `03_operator_surface_receipt.md`
- `04_goal_truth_receipt.md`
- `05_go_gate_receipt.md`
- `06_memorykernel_repair_receipt.md`
- `07_score_history.md`
- `08_metabolization_packet.md`
- `10_memorykernel_report_source_packet.md`
- `11_go_receipt_template_receipt.md`
- `12_live_verifier_matrix.md`
- `13_authority_boundary_receipt.md`
- `14_residual_risk_register.md`
- `15_artifact_manifest_receipt.md`
- `16_periodic_onboard_receipt.md`
- `17_liveness_key_disambiguation_receipt.md`
- `18_receipt_inventory_manifest_receipt.md`
- `19_gap_triage_packet_receipt.md`
- `20_memory_kernel_coverage_receipt.md`
- `21_digest_canvas_summary_receipt.md`
- `22_completion_guard_receipt.md`
- `23_periodic_onboard_refresh_receipt.md`
- `24_timebox_status_receipt.md`
- `25_manifest_receipt_summary_receipt.md`
- `26_stable_admission_render_receipt.md`
- `27_timebox_refresh_receipt.md`
- `28_go_template_requirements_receipt.md`
- `29_memory_coverage_targets_receipt.md`
- `30_manifest_inventory_scope_receipt.md`
- `31_completion_guard_policy_receipt.md`
- `32_timebox_three_hour_receipt.md`
- `operator_os_projection.json`
- `operator_completion_guard_packet.json`
- `operator_next_action_packet.json`
- `memory_kernel_coverage_packet.json`
- `operator_gap_triage_packet.json`
- `darshan_go_gate_packet.json`
- `darshan_go_receipt_template.json`
- `authority_boundary_packet.json`
- `operator_os_artifact_manifest.json`
- `memory_kernel_query_eval.json`
- `memory_kernel_repair_packet.json`

## Success Criteria For Final Closeout

Final closeout is proven only when:

- true elapsed time satisfies the contract or a documented hard blocker exists;
- required final artifacts are present and updated;
- minimum verification commands pass or scoped failures are documented with
  precise external reasons;
- complete verifier no longer fails after reporter closure;
- final ds-goal receipt points to the final artifact set;
- no hard boundary was violated.

## Loop 09 Receipt

Hypothesis:

If the next-goal packet is written before final closure, future turns can
continue the original 8-hour objective from concrete evidence instead of
conversation memory.

Patch:

- Added this live `09_next_goal_packet.md`.
- Preserved the remaining final requirements and hard boundaries.
- Identified the next safe loop targets.

Evaluation:

- `docs/plans/2026-06-02-venturecell-operator-os-autoresearch-8h-goal.md`
  was inspected for required final artifacts and minimum verification.
- `git log --oneline -n 10` verified the scoped commit chain.
- `./.venv/bin/python scripts/runtime/autonomy_spine.py brief --mission-id 20260602-venturecell-operator-os-autoresearch-8h`
  proved reporter remains open.

Adversarial review:

- This packet is marked live draft, not final.
- It does not claim MemoryKernel, Darshan GO, or 8-hour completion.
- It explicitly forbids reporter closure before final proof.

Keep / revert / queue:

Decision: keep.

Queued:

- Final adversarial audit update.
- Final update of score, metabolization, and next-goal packets.
- True-time proof and final reporter closure only after verification.
