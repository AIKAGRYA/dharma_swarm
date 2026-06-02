# Completion Guard Policy Receipt

Run: `venturecell-operator-os-autoresearch-20260602T141038Z`
Status: live packet, not final until the true 8-hour contract is closed
Mission: `20260602-venturecell-operator-os-autoresearch-8h`
ds-goal progress receipt: `r-43933ac6a5701ece`
Current scoped HEAD before this packet: `4b8d06ce feat(operator-os): mark manifest inventory scope`

## Loop 32 Receipt

Hypothesis:

If the completion guard packet makes reporter closure policy explicit, future
agents are less likely to treat a live `100/100` score or green checks as a
terminal reporter receipt.

Patch:

- Added `reporter_task_must_remain_open`.
- Added `terminal_reporter_receipt_required`.
- Added `complete_verifier_expected_blocker`.
- Added `reporter_closure_policy`.
- Added focused render-artifact assertions.

Evaluation:

- `pytest -q tests/test_venture_cell_operator_os_projection.py` passed.
- `pytest -q tests/test_darshan_external_reader_gate.py tests/test_control_surface.py -k "GoReceiptRows or external_reader"`
  passed.
- `pytest -q tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_daily_operating_brief.py`
  passed.
- `./.venv/bin/python -m compileall -q dharma_swarm/venture_cell/operator_os`
  passed.
- `jq '{reporter_task_must_remain_open, terminal_reporter_receipt_required, complete_verifier_expected_blocker}' operator_completion_guard_packet.json`
  showed the expected guard fields.

Adversarial review:

- Reporter policy is a checklist, not closure.
- The reporter task remains open.
- Complete verification remains expected to fail until terminal reporter
  closure is legitimately recorded.
- This does not satisfy true elapsed-time proof, Darshan GO, external
  authority, NATS/A2A liveness, or trusted Chetana promotion.

Keep / revert / queue:

Decision: keep.

Queued:

- Keep reporter open until true-time proof, final artifact review, terminal
  reporter receipt, and complete verifier pass exist.
