# Memory Coverage Counts Receipt

Run: `venturecell-operator-os-autoresearch-20260602T141038Z`
Status: live packet, not final until the true 8-hour contract is closed
Mission: `20260602-venturecell-operator-os-autoresearch-8h`
ds-goal progress receipt: `r-3e318b30d3694ffa`
Current scoped HEAD before this packet: `1779aa6c feat(operator-os): count gap triage lanes`

## Loop 37 Receipt

Hypothesis:

If the MemoryKernel coverage packet exposes root and maintenance counts, future
agents can route local recall maintenance without reading every root row or
claiming complete coverage.

Patch:

- Added `root_count`, `truncated_root_count`, `untruncated_root_count`, and
  `local_maintenance_target_count` to `memory_kernel_coverage_packet.json`.
- Added `complete_coverage_claimed: false` to prevent count fields from being
  interpreted as a coverage certificate.
- Added `memory_coverage_truncated_root_count` to the artifact manifest for
  quick routing.
- Added focused assertions that coverage counts match the rendered arrays.

Evaluation:

- `./.venv/bin/python -m dharma_swarm.venture_cell.operator_os.cli --output-dir reports/venture_operator_os/venturecell-operator-os-autoresearch-20260602T141038Z`
  rendered successfully.
- `pytest -q tests/test_venture_cell_operator_os_projection.py` passed.
- `pytest -q tests/test_darshan_external_reader_gate.py tests/test_control_surface.py -k "GoReceiptRows or external_reader"`
  passed.
- `pytest -q tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_daily_operating_brief.py`
  passed.
- `./.venv/bin/python -m compileall -q dharma_swarm/venture_cell/operator_os`
  passed.
- `jq '{root_count, truncated_root_count, untruncated_root_count, local_maintenance_target_count, complete_coverage_claimed}' memory_kernel_coverage_packet.json`
  showed root `4`, truncated `2`, untruncated `2`, maintenance targets `2`,
  and `complete_coverage_claimed: false`.
- Scoped `git diff --check` passed.
- Complete ds-goal verification still failed only on the intentionally open
  reporter task.

Adversarial review:

- Coverage counts are selectors, not proof of complete MemoryKernel coverage.
- `truncated_root_count: 2` means staging and quarantine still need local
  maintenance.
- `complete_coverage_claimed: false` preserves the no-overclaim boundary.
- This does not promote trusted Chetana memory, clear Darshan GO, create
  accepted receipts, fake NATS/A2A ack proof, close reporter, publish, deploy,
  push, merge, spend, or contact external readers.

Keep / revert / queue:

Decision: keep.

Queued:

- Preserve coverage count/list parity in future memory coverage changes.
- Use truncated-root counts as local maintenance routing only.
