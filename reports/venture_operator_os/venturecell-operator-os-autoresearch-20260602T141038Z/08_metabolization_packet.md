# Metabolization Packet

Run: `venturecell-operator-os-autoresearch-20260602T141038Z`
Status: live packet, not final until the 8-hour contract is closed
Mission: `20260602-venturecell-operator-os-autoresearch-8h`
ds-goal progress receipt: `r-b73f8ef857f710fd`
Current scoped HEAD: `0b7d74dc docs(operator-os): add live score history`

This packet captures durable learning from the run so far. It must be reviewed
and updated during final closeout before the reporter task is closed.

## Durable Learnings

1. MemoryKernel usefulness cannot be inferred from index size.

   Evidence:

   - `memory_kernel_query_eval.json` reports `partial` with `0/6` passing.
   - `memory_kernel_repair_packet.json` queues six repair items with missing
     terms and source refs.

   Metabolized rule:

   - Future agents must treat MemoryKernel recall as query-eval based. They may
     use the current memory packets as read-only context, but they must not
     mark recall solved until strict query evals pass without trusted promotion
     claims.

2. Operator clarity improves when blocked state is rendered as packets, not
   scattered prose.

   Evidence:

   - `operator_next_action_packet.json` holds owner, blockers, forbidden
     actions, autonomy level, and next governed action.
   - `darshan_go_gate_packet.json` holds the exact GO receipt source/schema,
     blocked departments, blocked actions, and expected local artifacts.

   Metabolized rule:

   - New Operator OS surfaces should derive packet-shaped handoffs from existing
     gates and receipts instead of creating new control planes.

3. ds-goal progress must be distinguishable from task completion.

   Evidence:

   - `scripts/runtime/autonomy_spine.py progress` appends non-closing receipts.
   - Complete verification still fails on the open reporter task.
   - Current mission counts remain `open=1 claimed=0 completed=4 failed=0 blocked=0 total=5`.

   Metabolized rule:

   - Use `progress` receipts for loop evidence. Use terminal `record` receipts
     only when the full task is truly closed.

4. Darshan remains externally gated.

   Evidence:

   - `darshan_go_gate_packet.json` reports `decision: block_external_authority`.
   - Accepted receipts are empty.
   - Operator OS remains `blocked_on_external_reader_gate` and
     `L0_read_only_plan`.

   Metabolized rule:

   - Growth, communications, publishing, and external operator handoff stay
     blocked until a real accepted privacy-redacted external-reader GO evidence
     receipt is linked to `decision_delta.json`.

5. Final score is not final just because the interim target passed `80/100`.

   Evidence:

   - `07_score_history.md` records progression from `66/100` to `84/100`.
   - The goal clock has not reached a true 8-hour completion window.
   - Required final artifacts still need final review/update.

   Metabolized rule:

   - Score must remain a live ledger until the final adversarial audit,
     metabolization update, next-goal packet, and reporter closure are complete.

## Committed Packets

| Commit | Packet | Durable effect |
|---|---|---|
| `6f9648c0` | `01_program_kernel_receipt.md` | AutoResearch program kernel and MemoryKernel query API |
| `61941001` | `02_memorykernel_eval_receipt.md` | six-query MemoryKernel eval artifact, strict false-green blocker |
| `b0533624` | `03_operator_surface_receipt.md` | next-action packet for owner/blocker/authority handoff |
| `a03e0e09` | `04_goal_truth_receipt.md` | non-closing ds-goal progress receipts |
| `9e5f326e` | `05_go_gate_receipt.md` | Darshan GO gate packet |
| `bf2d237b` | `06_memorykernel_repair_receipt.md` | MemoryKernel repair packet |
| `0b7d74dc` | `07_score_history.md` | live score ledger |

## Current Read-Only Artifacts

- `operator_os_projection.json`
- `operator_os_digest.md`
- `memory_kernel_index.json`
- `memory_kernel_query_eval.json`
- `operator_next_action_packet.json`
- `darshan_go_gate_packet.json`
- `memory_kernel_repair_packet.json`
- `07_score_history.md`

## Do Not Metabolize As Done

These facts are explicitly not complete:

- MemoryKernel strict evals are not passing.
- Darshan external-reader GO gate is not passing.
- Reporter task is not closed.
- The final adversarial audit is not written.
- The final next-goal packet is not written.
- The true 8-hour elapsed-time requirement is not proven.
- No push, merge, publish, deploy, outreach, spend, or live external authority
  action has been performed.

## Future-Agent Start Packet

Start here:

1. Read `docs/plans/2026-06-02-venturecell-operator-os-autoresearch-8h-goal.md`.
2. Read `docs/plans/venturecell_operator_os_autoresearch_program.md`.
3. Read `07_score_history.md`.
4. Inspect `operator_os_projection.json`, `memory_kernel_query_eval.json`,
   `memory_kernel_repair_packet.json`, and `darshan_go_gate_packet.json`.
5. Run:

   ```bash
   ./.venv/bin/python scripts/runtime/autonomy_spine.py brief --mission-id 20260602-venturecell-operator-os-autoresearch-8h
   pytest -q tests/test_venture_cell_operator_os_projection.py
   pytest -q tests/test_darshan_external_reader_gate.py tests/test_control_surface.py -k 'GoReceiptRows or external_reader'
   pytest -q tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_daily_operating_brief.py
   ```

6. Continue with another bounded loop. Do not close the reporter lane until the
   true 8-hour contract is proven.

## Loop 08 Receipt

Hypothesis:

If run learnings are metabolized before final closeout, future agents can start
from durable artifacts and current blockers rather than conversation memory.

Patch:

- Added this live metabolization packet.
- Mapped each committed loop to its durable effect.
- Captured the explicit facts that must not be treated as done.

Evaluation:

- `make onboard` proved current HEAD and mission reconciliation.
- `./.venv/bin/python scripts/runtime/autonomy_spine.py brief --mission-id 20260602-venturecell-operator-os-autoresearch-8h`
  proved reporter remains open.
- `git diff --check -- reports/venture_operator_os/venturecell-operator-os-autoresearch-20260602T141038Z/08_metabolization_packet.md`
  passed.

Adversarial review:

- This packet is marked live, not final.
- It names unresolved blockers directly.
- It does not claim external action, Chetana promotion, or final mission
  completion.

Keep / revert / queue:

Decision: keep.

Queued:

- Update this file during final closeout.
- Write `06_adversary_audit.md` as the final adversarial audit when the run is
  actually in the final window.
- Write `09_next_goal_packet.md`.
- Close reporter only after final verification proves the full objective.
