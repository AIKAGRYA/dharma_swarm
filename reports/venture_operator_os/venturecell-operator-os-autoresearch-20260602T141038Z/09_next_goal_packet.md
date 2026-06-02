# Next Goal Packet

Run: `venturecell-operator-os-autoresearch-20260602T141038Z`
Status: live draft, not final until the 8-hour contract is closed
Mission: `20260602-venturecell-operator-os-autoresearch-8h`
ds-goal progress receipt: `r-e5be506a66940367`
Current scoped HEAD before this packet: `b72f94ee feat(operator-os): add authority boundary packet`

This packet is the handoff for the next bounded AutoResearch loop. It must be
reviewed and updated in the final hour before reporter closure.

## Current Truth

- Operator OS status: `blocked_on_external_reader_gate`.
- Autonomy level: `L0_read_only_plan`.
- Score ledger: `93/100` live score, not final.
- ds-goal mission state: `open=1 claimed=0 completed=4 failed=0 blocked=0 total=5`.
- Reporter task: open by design.
- MemoryKernel strict eval: `pass` (`6/6`) from report-local staged sources.
- Darshan GO gate: `block_external_authority`, no accepted receipts.
- Darshan GO template: `draft_template_not_evidence`.
- Live verifier matrix: present, not final.
- Authority boundary: `local_read_only_external_blocked`.
- Residual risk register: present, not final.
- Last committed packet: authority boundary packet.

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

7. Final closeout only after true-time proof.

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
- `operator_os_projection.json`
- `operator_next_action_packet.json`
- `darshan_go_gate_packet.json`
- `darshan_go_receipt_template.json`
- `authority_boundary_packet.json`
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
