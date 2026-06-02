# Loop 60 Darshan GO Template Gap Groups Receipt

Run: `venturecell-operator-os-autoresearch-20260602T141038Z`
Status: kept, non-final progress receipt
Mission: `20260602-venturecell-operator-os-autoresearch-8h`
ds-goal progress receipt: `r-f1d421f33b5fb379`
Current scoped HEAD before this packet: `2051da0f feat(operator-os): summarize go template coverage`

## Hypothesis

If the template requirement coverage gap is split into top-level and payload
field groups, future receipt review can see exactly which envelope fields and
which payload fields remain outside the non-evidence template constraints.

## Patch

- Added covered and uncovered template requirement field groups.
- Counted covered top-level, covered payload, uncovered top-level, and
  uncovered payload required fields.
- Mirrored the uncovered top-level and payload counts in the manifest.
- Added digest lines for the uncovered split.
- Added focused assertions for the `5/2` covered and `4/5` uncovered split.

## Evaluation

- `pytest -q tests/test_venture_cell_operator_os_projection.py` passed.
- `pytest -q tests/test_darshan_external_reader_gate.py tests/test_control_surface.py -k 'GoReceiptRows or external_reader'`
  passed with `11` tests and `74` deselected.
- `pytest -q tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_daily_operating_brief.py`
  passed with `31` tests.
- `./.venv/bin/python -m compileall -q dharma_swarm/venture_cell/operator_os`
  passed.
- Live render of
  `reports/venture_operator_os/venturecell-operator-os-autoresearch-20260602T141038Z`
  passed.
- `git diff --check -- dharma_swarm/venture_cell/operator_os tests/test_venture_cell_operator_os_projection.py reports/venture_operator_os/venturecell-operator-os-autoresearch-20260602T141038Z`
  passed.
- `./.venv/bin/python scripts/runtime/autonomy_spine.py verify --mission-id 20260602-venturecell-operator-os-autoresearch-8h --phase complete --json`
  exited `3` with only blocker
  `task_not_closed:20260602-venturecell-operator-os-autoresearch-8h-t05-reporter`.
- Live `darshan_go_unblock_packet.json` reports covered top-level `5`, covered
  payload `2`, uncovered top-level `4`, uncovered payload `5`, and accepted GO
  receipts `0`.

## Adversarial Review

- The split is review metadata only.
- It does not create a receipt body or accepted evidence.
- External authority remains blocked.
- Reporter remains open because the true 8-hour contract is not complete.

## Keep / Revert / Queue

Decision: keep.

Queued:

- Use the grouped gap only to guide local review.
- Continue without external authority or accepted-receipt fabrication.
- Re-run the full minimum verifier set before the scoped commit.
