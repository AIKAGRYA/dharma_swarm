# GO Template Requirements Receipt

Run: `venturecell-operator-os-autoresearch-20260602T141038Z`
Status: live packet, not final until the true 8-hour contract is closed
Mission: `20260602-venturecell-operator-os-autoresearch-8h`
ds-goal progress receipt: `r-a158aa9cb20d8ba4`
Current scoped HEAD before this packet: `011d8dd4 docs(operator-os): refresh timebox status`

## Loop 29 Receipt

Hypothesis:

If the Darshan GO receipt template exposes machine-readable acceptance
requirements, future agents are less likely to promote a draft template into an
accepted GO receipt without a real reader event.

Patch:

- Added `accepted_receipt_requirements` to the Darshan GO receipt template.
- Required accepted status, Darshan reader source, GO evidence schema, real
  source URL, real event UID, human-approved contact, and privacy redaction.
- Added focused test assertions for the in-memory gate packet and rendered
  template JSON.

Evaluation:

- `pytest -q tests/test_venture_cell_operator_os_projection.py` passed.
- `pytest -q tests/test_darshan_external_reader_gate.py tests/test_control_surface.py -k "GoReceiptRows or external_reader"`
  passed.
- `pytest -q tests/test_governed_work_admission.py tests/test_a2a_task_lifecycle.py tests/test_daily_operating_brief.py`
  passed.
- `./.venv/bin/python -m compileall -q dharma_swarm/venture_cell/operator_os`
  passed.
- `jq '.accepted_receipt_requirements' darshan_go_receipt_template.json`
  showed the expected prerequisite fields.

Adversarial review:

- Requirements are prerequisites, not acceptance.
- The template remains `draft_template_not_evidence` and `not_receipt: true`.
- Accepted Darshan GO receipts remain empty.
- This does not grant external authority, create liveness proof, promote
  trusted Chetana memory, close reporter, or satisfy the timebox.

Keep / revert / queue:

Decision: keep.

Queued:

- Continue to treat the template as local preparation only.
- Do not store any accepted GO receipt without a real countable external-reader
  event, human approval, and privacy redaction.
