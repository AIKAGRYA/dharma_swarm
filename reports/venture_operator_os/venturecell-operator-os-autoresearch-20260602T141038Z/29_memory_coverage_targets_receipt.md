# Memory Coverage Targets Receipt

Run: `venturecell-operator-os-autoresearch-20260602T141038Z`
Status: live packet, not final until the true 8-hour contract is closed
Mission: `20260602-venturecell-operator-os-autoresearch-8h`
ds-goal progress receipt: `r-875b5bb0c3e8a17a`
Current scoped HEAD before this packet: `fd8e3453 feat(operator-os): harden go template requirements`

## Loop 30 Receipt

Hypothesis:

If the MemoryKernel coverage packet names the truncated roots as local
maintenance targets, future agents can pick a repair loop without mistaking
root coverage for complete recall or trusted Chetana promotion.

Patch:

- Added derived `truncated_roles` to `memory_kernel_coverage_packet.json`.
- Added derived `local_maintenance_targets` with root, tier, gap, and
  recommended local action.
- Added focused render-artifact assertions.

Evaluation:

- `pytest -q tests/test_venture_cell_operator_os_projection.py` passed.
- `pytest -q tests/test_darshan_external_reader_gate.py tests/test_control_surface.py -k "GoReceiptRows or external_reader"`
  passed.
- `pytest -q tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_daily_operating_brief.py`
  passed.
- `./.venv/bin/python -m compileall -q dharma_swarm/venture_cell/operator_os`
  passed.
- `jq '{truncated_roles, local_maintenance_targets}' memory_kernel_coverage_packet.json`
  showed staging and quarantine as local maintenance targets.

Adversarial review:

- Targets are selectors only; they do not resolve truncation.
- Memory eval remains report-local and read-only.
- `trusted_promotion_claimed` remains `false`.
- This does not clear Darshan GO, grant authority, prove live NATS/A2A ack,
  close reporter, or satisfy the 8-hour timebox.

Keep / revert / queue:

Decision: keep.

Queued:

- Future memory loops can add query-specific source packets or adjust local scan
  budget, but must preserve trusted-promotion gates.
