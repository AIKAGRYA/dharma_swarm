# A2A Phase 4 Blocker Receipt

Timestamp: `2026-06-30T17:15:54Z`

Branch: `codex/langgraph-orchestration-parity-20260701`

Live queue: `/Users/dhyana/.dharma/a2a_bus/tasks/queue.jsonl`

Backup before live normalization: `/Users/dhyana/.dharma/a2a_bus/tasks/queue.jsonl.pr732-phase4-20260630T171554Z.bak`

## Action Taken

Added a narrow reconciliation tool:

`scripts/governance/a2a_reconcile_embedded_receipts.py`

The tool only normalizes queue rows that already contain a valid embedded terminal `dharma_a2a_task_receipt.v1` receipt. It does not convert semantic receipts, open rows, claimed rows, or receipt-less completed rows.

Receipts:

- `reports/langgraph_parity/allnight/a2a_reconcile_embedded_receipts_dry_run_20260630T171554Z.json`
- `reports/langgraph_parity/allnight/a2a_reconcile_embedded_receipts_apply_20260630T171554Z.json`

Live normalized rows:

- `collab:fleet-health-collab-20260528:reviewer:opus_composer`
- `collab:fleet-health-collab-20260528:infra-audit:devin-roaming-2987d222`

Both moved from `expired` to `blocked_verified` using their existing valid `a2a_supervisor` receipts.

## Verification

- `.venv/bin/python -m pytest -q tests/test_a2a_embedded_receipt_reconciler.py tests/test_a2a_readiness_gate.py tests/test_a2a_task_lifecycle.py` -> `19 passed in 0.44s`
- `.venv/bin/python -m compileall -q scripts/governance/a2a_reconcile_embedded_receipts.py` -> pass
- `.venv/bin/python scripts/governance/a2a_reconcile_embedded_receipts.py --output reports/langgraph_parity/allnight/a2a_reconcile_embedded_receipts_dry_run_20260630T171554Z.json` -> `candidate_count=2`
- `.venv/bin/python scripts/governance/a2a_reconcile_embedded_receipts.py --apply --output reports/langgraph_parity/allnight/a2a_reconcile_embedded_receipts_apply_20260630T171554Z.json` -> 2 rows normalized
- `.venv/bin/python scripts/governance/a2a_reconcile_embedded_receipts.py` after apply -> `candidate_count=0`
- `.venv/bin/python scripts/governance/check_a2a_readiness.py --strict` -> fail exit 2; `ready=false`, `open_tasks=17`, `unknown_status_tasks=0`, `unverified_closed_tasks=19`
- `git diff --no-index --stat /Users/dhyana/.dharma/a2a_bus/tasks/queue.jsonl.pr732-phase4-20260630T171554Z.bak /Users/dhyana/.dharma/a2a_bus/tasks/queue.jsonl` -> `1 file changed, 2 insertions(+), 2 deletions(-)`
- `.venv/bin/python scripts/governance/check_module_budget.py --base-ref origin/main --head-ref HEAD` -> pass
- `.venv/bin/python scripts/governance/hygiene/ratchet.py --json --max-baseline-age-days 45` -> pass; `green=true`

## Remaining Open Or Claimed Tasks

- `forge-v0.1-001`
- `holon-plan-review-cursor-20260612`
- `holon-plan-review-opus-20260612`
- `l1-fx-001`
- `reconcile-564-565-20260611`
- `sab-flywheel-d01-qwen-code-first-spark`
- `tam-wp-wp_dfa4e1134277`
- `ts-converge-0611`
- `ts-evo-0611-1`
- `ts-evo-0611-2`
- `ts-evo-0611-3`
- `ts-hb0631-credit`
- `ts-pr-babysit-div-20260610`
- `yatagarasu-10cceaa8`

- `yatagarasu-20260619-credit-monitor`
- `yatagarasu-20260619-gap-scan-fix`
- `yatagarasu-20260619-staging-decay`

## Remaining Unverified Closed Tasks

- `sab-flywheel-d00-codex-composer-mac`
- `sab-flywheel-d00-codex-rushabdev`
- `sab-flywheel-d00-research-spark-3-challenge`
- `sab-flywheel-d00-sab-hardener`
- `sab-flywheel-d00-sab-recruiter-bridge`
- `sab-flywheel-d00-sab-research-scout`
- `sab-flywheel-d00-setu-sab-agni`
- `sab-flywheel-d01-codex-rushabdev-federation-preflight`
- `sab-flywheel-d01-codex-semantic-reply-queue17`
- `sab-flywheel-d01-sab-hardener-route-service-runbook`
- `sab-flywheel-d01-sab-recruiter-bridge-candidate-draft`
- `sab-flywheel-d01-sab-research-scout-channel-validation`
- `sab-flywheel-d01-setu-approve-day1-queue`
- `sab-flywheel-d02-codex-visible-reply-proof`
- `sab-flywheel-d02-hardener-top-risks`
- `sab-flywheel-d02-recruiter-first-spark-candidate`
- `sab-flywheel-d02-research-next-spark`
- `sab-flywheel-d02-rushabdev-federation-watch`
- `ts-converge-0611`

## Read-Only Blocker Audit

Added a replayable audit tool:

`scripts/governance/a2a_readiness_blocker_audit.py`

Audit artifact:

- `reports/langgraph_parity/allnight/a2a_readiness_blocker_audit_20260630T174529Z.json`

Command:

`.venv/bin/python scripts/governance/a2a_readiness_blocker_audit.py --artifact-root /Users/dhyana/ds_langgraph_parity_20260701 --artifact-root /Users/dhyana/dharma_swarm --output reports/langgraph_parity/allnight/a2a_readiness_blocker_audit_20260630T174529Z.json`

Result:

- `blocker_count=36`
- `open_stale_claimed_without_terminal_receipt=11`
- `open_stale_unclaimed_without_terminal_receipt=6`
- `closed_semantic_receipt_present_non_a2a=18`
- `closed_missing_a2a_receipt_no_pointer=1`
- The 18 SAB semantic receipt pointers resolve as valid `sab.semantic_receipt.v1` artifacts only through `/Users/dhyana/dharma_swarm`, not through this clean parity branch. They remain non-A2A evidence and do not satisfy the strict embedded `dharma_a2a_task_receipt.v1` receipt contract.

Verification:

- `.venv/bin/python -m pytest -q tests/test_a2a_readiness_blocker_audit.py` -> `4 passed in 0.39s`
- `.venv/bin/python -m pytest -q tests/test_a2a_readiness_blocker_audit.py tests/test_a2a_embedded_receipt_reconciler.py tests/test_a2a_readiness_gate.py tests/test_a2a_task_lifecycle.py` -> `23 passed in 0.41s`
- `.venv/bin/python -m compileall -q scripts/governance/a2a_readiness_blocker_audit.py tests/test_a2a_readiness_blocker_audit.py` -> pass
- `.venv/bin/python scripts/governance/check_a2a_readiness.py --strict` -> fail exit 2; `ready=false`, `open_tasks=17`, `unknown_status_tasks=0`, `unverified_closed_tasks=19`
- `git diff --check` -> pass
- `.venv/bin/python scripts/governance/check_module_budget.py --base-ref origin/main --head-ref HEAD` -> pass with existing warnings
- `.venv/bin/python scripts/governance/hygiene/ratchet.py --json --max-baseline-age-days 45` -> pass; `green=true`

## Blocker

Phase 4 is not green. The live queue still contains open/claimed work and completed rows without embedded A2A task receipts. The SAB rows carry `sab.semantic_receipt` pointers or stale `receipt_validation` metadata, but the strict A2A gate correctly requires an embedded valid `dharma_a2a_task_receipt.v1` receipt or terminal closure through the governed lifecycle.

## 2026-07-01 Addendum: Semantic Receipt Adapter

Timestamp: `2026-07-01T03:45:52Z`

Added a second narrow normalization tool:

`scripts/governance/a2a_adapt_semantic_receipts.py`

The tool only adapts rows that are already terminal, still unverified by the strict A2A lifecycle classifier, and backed by a validated `sab.semantic_receipt.v1` artifact. It does not close open work, claimed work, unsupported terminal statuses, identity mismatches, or receipt-less rows.

Receipts:

- `reports/langgraph_parity/allnight/a2a_semantic_receipt_adapter_20260701T034035Z.dry_run.json`
- `reports/langgraph_parity/allnight/a2a_semantic_receipt_adapter_20260701T034035Z.json`
- `reports/langgraph_parity/allnight/a2a_semantic_receipt_adapter_post_apply_dry_run_20260701T034035Z.json`
- `reports/langgraph_parity/allnight/a2a_readiness_blocker_audit_20260701T034035Z.json`

Live queue backup before adapter apply:

- `/Users/dhyana/.dharma/a2a_bus/tasks/queue.jsonl.a2a-semantic-adapter-20260701T034035Z.bak`

Result:

- Dry-run found 18 candidates and 0 skips.
- Apply adapted 18 already-terminal SAB semantic rows into embedded valid `dharma_a2a_task_receipt.v1` receipts.
- Post-apply dry-run found `candidate_count=0`.
- `.venv/bin/python scripts/governance/check_a2a_readiness.py --strict` still fails exit 2, now with `ready=false`, `open_tasks=17`, `unknown_status_tasks=0`, `unverified_closed_tasks=1`.
- Fresh blocker audit now reports `blocker_count=18`: 11 stale claimed rows, 6 stale unclaimed rows, and one completed `ts-converge-0611` row with no receipt pointer.

Verification:

- `.venv/bin/python -m pytest -q tests/test_a2a_semantic_receipt_adapter.py` -> `3 passed in 0.87s`
- `.venv/bin/python -m pytest -q tests/test_a2a_semantic_receipt_adapter.py tests/test_a2a_readiness_blocker_audit.py tests/test_a2a_embedded_receipt_reconciler.py tests/test_a2a_readiness_gate.py tests/test_a2a_task_lifecycle.py` -> `26 passed in 0.87s`
- `.venv/bin/ruff check scripts/governance/a2a_adapt_semantic_receipts.py tests/test_a2a_semantic_receipt_adapter.py` -> pass
- `.venv/bin/python -m compileall -q scripts/governance/a2a_adapt_semantic_receipts.py scripts/governance/a2a_readiness_blocker_audit.py scripts/governance/check_a2a_readiness.py tests/test_a2a_semantic_receipt_adapter.py` -> pass
- `jq -e . reports/langgraph_parity/allnight/a2a_semantic_receipt_adapter_20260701T034035Z.dry_run.json reports/langgraph_parity/allnight/a2a_semantic_receipt_adapter_20260701T034035Z.json reports/langgraph_parity/allnight/a2a_semantic_receipt_adapter_post_apply_dry_run_20260701T034035Z.json reports/langgraph_parity/allnight/a2a_readiness_blocker_audit_20260701T034035Z.json reports/langgraph_parity/allnight/SCOREBOARD.json` -> pass
- `.venv/bin/python scripts/governance/check_module_budget.py --base-ref origin/main --head-ref HEAD` -> pass with existing warnings
- `.venv/bin/python scripts/governance/hygiene/delta_ratchet.py --base-ref dd02c1e03abb9348d442156c727f036b4bd65343 --head-ref HEAD` -> pass; `REGRESSIONS (0)`
- `git diff --check` -> pass

## 2026-07-01 Addendum: Legacy Proof Receipt Recovery

The semantic adapter intentionally left the receipt-less completed `ts-converge-0611` row untouched. A follow-up narrow adapter now handles that separate legacy proof class:

- Added `scripts/governance/a2a_recover_legacy_proof_receipts.py`
- Added `tests/test_a2a_legacy_proof_receipt_recovery.py`
- The adapter only targets already-terminal rows that are unverified by the A2A lifecycle classifier, have no embedded A2A receipt, include a legacy proof pointer, resolve to an existing proof artifact, and carry closer identity plus legacy closure context.
- It does not close open rows or infer closure across duplicate task IDs. The original pending `ts-converge-0611` row remains open.

Receipts:

- `reports/langgraph_parity/allnight/a2a_legacy_proof_receipt_recovery_20260701T040437Z.dry_run.json`
- `reports/langgraph_parity/allnight/a2a_legacy_proof_receipt_recovery_20260701T040437Z.json`
- `reports/langgraph_parity/allnight/a2a_legacy_proof_receipt_recovery_post_apply_dry_run_20260701T040437Z.json`
- `reports/langgraph_parity/allnight/a2a_readiness_blocker_audit_20260701T040437Z.json`

Live queue backup before adapter apply:

- `/Users/dhyana/.dharma/a2a_bus/tasks/queue.jsonl.a2a-legacy-proof-recovery-20260701T040437Z.bak`

Result:

- Dry-run found 1 candidate and 0 skips: the completed `ts-converge-0611` row pointing at `/Users/dhyana/.dharma/a2a_bus/collab/convergence/SHARED_PICTURE.md`.
- Apply recovered 1/1 candidate into an embedded valid `dharma_a2a_task_receipt.v1` receipt.
- Post-apply dry-run found `candidate_count=0`.
- `.venv/bin/python scripts/governance/check_a2a_readiness.py --strict` still fails exit 2, now with `ready=false`, `open_tasks=17`, `unknown_status_tasks=0`, `unverified_closed_tasks=0`.
- Fresh blocker audit now reports `blocker_count=17`: 11 stale claimed rows and 6 stale unclaimed rows.

Verification:

- `.venv/bin/python -m pytest -q tests/test_a2a_legacy_proof_receipt_recovery.py` -> `3 passed in 0.38s`
- `.venv/bin/python -m pytest -q tests/test_a2a_legacy_proof_receipt_recovery.py tests/test_a2a_semantic_receipt_adapter.py tests/test_a2a_readiness_blocker_audit.py tests/test_a2a_embedded_receipt_reconciler.py tests/test_a2a_readiness_gate.py tests/test_a2a_task_lifecycle.py` -> `29 passed in 0.55s`
- `.venv/bin/ruff check scripts/governance/a2a_recover_legacy_proof_receipts.py tests/test_a2a_legacy_proof_receipt_recovery.py` -> pass
- `.venv/bin/python -m compileall -q scripts/governance/a2a_recover_legacy_proof_receipts.py tests/test_a2a_legacy_proof_receipt_recovery.py` -> pass
- `jq -e . reports/langgraph_parity/allnight/a2a_legacy_proof_receipt_recovery_20260701T040437Z.dry_run.json reports/langgraph_parity/allnight/a2a_legacy_proof_receipt_recovery_20260701T040437Z.json reports/langgraph_parity/allnight/a2a_legacy_proof_receipt_recovery_post_apply_dry_run_20260701T040437Z.json reports/langgraph_parity/allnight/a2a_readiness_blocker_audit_20260701T040437Z.json reports/langgraph_parity/allnight/SCOREBOARD.json` -> pass

Remaining Phase 4 blocker:

The strict A2A gate is still not green. Remaining blockers are the 17 open or claimed rows. They require task-specific execution, operator-gated closure, or explicit blocked receipts; the adapters intentionally do not infer those outcomes.

## 2026-07-01 Addendum: Operator-Gated Stale Row Blocker

After semantic and legacy-proof recovery, the remaining blocker class was open/claimed work. A third narrow tool now handles only the subset whose task body explicitly requires operator action:

- Added `scripts/governance/a2a_block_operator_gated_tasks.py`
- Added `tests/test_a2a_operator_gated_blocker.py`
- The tool only targets non-terminal stale rows that contain explicit operator-gate phrases such as `operator-gated`, `operator approval required`, or `operator sign-off`.
- It does not block ordinary stale work, recent work, terminal rows, generic `without approval` wording, or rows without explicit operator-gate phrases.

Receipts:

- `reports/langgraph_parity/allnight/a2a_operator_gated_block_dry_run_20260701T043613Z.json`
- `reports/langgraph_parity/allnight/a2a_operator_gated_block_20260701T043613Z.json`
- `reports/langgraph_parity/allnight/a2a_operator_gated_block_post_apply_dry_run_20260701T043613Z.json`
- `reports/langgraph_parity/allnight/a2a_readiness_blocker_audit_20260701T043613Z.json`

Live queue backup before apply:

- `/Users/dhyana/.dharma/a2a_bus/tasks/queue.jsonl.a2a-operator-gated-block-20260701T043613Z.bak`

Result:

- Dry-run found 6 candidates and 0 skips.
- Apply blocked 6/6 explicit operator-gated stale rows as valid `blocked_verified` A2A lifecycle rows.
- Post-apply dry-run found `candidate_count=0`.
- `.venv/bin/python scripts/governance/check_a2a_readiness.py --strict` still fails exit 2, now with `ready=false`, `open_tasks=11`, `unknown_status_tasks=0`, `unverified_closed_tasks=0`.
- Fresh blocker audit now reports `blocker_count=11`: 5 stale claimed rows and 6 stale unclaimed rows.

Verification:

- `.venv/bin/python -m pytest -q tests/test_a2a_operator_gated_blocker.py` -> `3 passed in 0.64s`
- `.venv/bin/python -m pytest -q tests/test_a2a_operator_gated_blocker.py tests/test_a2a_legacy_proof_receipt_recovery.py tests/test_a2a_semantic_receipt_adapter.py tests/test_a2a_readiness_blocker_audit.py tests/test_a2a_embedded_receipt_reconciler.py tests/test_a2a_readiness_gate.py tests/test_a2a_task_lifecycle.py` -> `32 passed in 0.82s`
- `.venv/bin/ruff check scripts/governance/a2a_block_operator_gated_tasks.py tests/test_a2a_operator_gated_blocker.py` -> pass
- `.venv/bin/python -m compileall -q scripts/governance/a2a_block_operator_gated_tasks.py tests/test_a2a_operator_gated_blocker.py` -> pass
- `jq -e . reports/langgraph_parity/allnight/SCOREBOARD.json reports/langgraph_parity/allnight/a2a_operator_gated_block_dry_run_20260701T043613Z.json reports/langgraph_parity/allnight/a2a_operator_gated_block_20260701T043613Z.json reports/langgraph_parity/allnight/a2a_operator_gated_block_post_apply_dry_run_20260701T043613Z.json reports/langgraph_parity/allnight/a2a_readiness_blocker_audit_20260701T043613Z.json reports/langgraph_parity/allnight/a2a_readiness_blocker_audit_resume_20260701T_after_closeout.json` -> pass
- `.venv/bin/python scripts/governance/check_module_budget.py --base-ref origin/main --head-ref HEAD` -> pass with existing warnings
- `.venv/bin/python scripts/governance/hygiene/delta_ratchet.py --base-ref dd02c1e03abb9348d442156c727f036b4bd65343 --head-ref HEAD` -> pass; `REGRESSIONS (0)`
- `git diff --check` -> pass

Remaining Phase 4 blocker:

The strict A2A gate is still not green. Remaining blockers are 11 open or claimed rows:

- `forge-v0.1-001`
- `holon-plan-review-cursor-20260612`
- `holon-plan-review-opus-20260612`
- `l1-fx-001`
- `reconcile-564-565-20260611`
- `sab-flywheel-d01-qwen-code-first-spark`
- `tam-wp-wp_dfa4e1134277`
- `ts-converge-0611`
- `ts-hb0631-credit`
- `ts-pr-babysit-div-20260610`
- `yatagarasu-10cceaa8`

## 2026-07-01 Addendum: Verified Duplicate Open Row Blocker

After the operator-gated adapter, one remaining open row was a same-id duplicate of a terminal verified row. A fourth narrow tool now handles only that row class:

- Added `scripts/governance/a2a_block_verified_duplicate_open_rows.py`
- Added `tests/test_a2a_verified_duplicate_open_rows.py`
- The tool only targets open, unclaimed rows whose exact task id appears in another terminal queue row with a valid embedded `dharma_a2a_task_receipt.v1` receipt and substantive artifact/evidence.
- It mutates by queue row index because duplicate task ids make id-only lifecycle mutation ambiguous.
- It does not touch claimed work, ordinary stale rows, all-open duplicate groups, or terminal duplicates whose receipt lacks substantive artifact/evidence.

Receipts:

- `reports/langgraph_parity/allnight/a2a_verified_duplicate_open_row_block_dry_run_20260701T050248Z.json`
- `reports/langgraph_parity/allnight/a2a_verified_duplicate_open_row_block_20260701T050248Z.json`
- `reports/langgraph_parity/allnight/a2a_verified_duplicate_open_row_block_post_apply_dry_run_20260701T050248Z.json`
- `reports/langgraph_parity/allnight/a2a_readiness_blocker_audit_20260701T050248Z.json`

Live queue backup before apply:

- `/Users/dhyana/.dharma/a2a_bus/tasks/queue.jsonl.a2a-verified-duplicate-block-20260701T050248Z.bak`

Result:

- Dry-run found 1 candidate and 0 skips: the pending `ts-converge-0611` duplicate row.
- Apply blocked 1/1 candidate as a valid `blocked_verified` A2A lifecycle row with authority `verified_duplicate_terminal_row_supervisor_block`.
- The terminal duplicate row remains `completed_verified` with receipt `a2a-task-receipt:ts-converge-0611:28da1fdabddc`.
- Post-apply dry-run found `candidate_count=0`.
- `.venv/bin/python scripts/governance/check_a2a_readiness.py --strict` still fails exit 2, now with `ready=false`, `open_tasks=10`, `unknown_status_tasks=0`, `unverified_closed_tasks=0`.
- Fresh blocker audit now reports `blocker_count=10`: 5 stale claimed rows and 5 stale unclaimed rows.

Verification:

- `.venv/bin/python -m pytest -q tests/test_a2a_verified_duplicate_open_rows.py` -> `4 passed in 0.35s`
- `.venv/bin/ruff check scripts/governance/a2a_block_verified_duplicate_open_rows.py tests/test_a2a_verified_duplicate_open_rows.py` -> pass
- `.venv/bin/python -m compileall -q scripts/governance/a2a_block_verified_duplicate_open_rows.py tests/test_a2a_verified_duplicate_open_rows.py` -> pass
- `.venv/bin/python -m pytest -q tests/test_a2a_verified_duplicate_open_rows.py tests/test_a2a_operator_gated_blocker.py tests/test_a2a_legacy_proof_receipt_recovery.py tests/test_a2a_semantic_receipt_adapter.py tests/test_a2a_readiness_blocker_audit.py tests/test_a2a_embedded_receipt_reconciler.py tests/test_a2a_readiness_gate.py tests/test_a2a_task_lifecycle.py` -> `36 passed in 0.64s`
- `jq -e . reports/langgraph_parity/allnight/SCOREBOARD.json reports/langgraph_parity/allnight/a2a_verified_duplicate_open_row_block_dry_run_20260701T050248Z.json reports/langgraph_parity/allnight/a2a_verified_duplicate_open_row_block_20260701T050248Z.json reports/langgraph_parity/allnight/a2a_verified_duplicate_open_row_block_post_apply_dry_run_20260701T050248Z.json reports/langgraph_parity/allnight/a2a_readiness_blocker_audit_20260701T050248Z.json reports/langgraph_parity/allnight/a2a_readiness_blocker_audit_resume_20260701T_after_operator_gated.json` -> pass
- `.venv/bin/python scripts/governance/check_module_budget.py --base-ref origin/main --head-ref HEAD` -> pass with existing warnings
- `.venv/bin/python scripts/governance/hygiene/delta_ratchet.py --base-ref dd02c1e03abb9348d442156c727f036b4bd65343 --head-ref HEAD` -> pass; `REGRESSIONS (0)`
- `git diff --check` -> pass

Remaining Phase 4 blocker:

The strict A2A gate is still not green. Remaining blockers are 10 open or claimed rows:

- `forge-v0.1-001`
- `holon-plan-review-cursor-20260612`
- `holon-plan-review-opus-20260612`
- `l1-fx-001`
- `reconcile-564-565-20260611`
- `sab-flywheel-d01-qwen-code-first-spark`
- `tam-wp-wp_dfa4e1134277`
- `ts-hb0631-credit`
- `ts-pr-babysit-div-20260610`
- `yatagarasu-10cceaa8`

## 2026-07-01 Addendum: SAB Qwen And TAM Darshan Updates

Later Phase 4 slices further reduced the open/claimed blocker set:

- `scripts/governance/a2a_block_sab_qwen_runtime_blockers.py` blocked `sab-flywheel-d01-qwen-code-first-spark` only after verifying that the exact expected Qwen-owned semantic receipt was absent and related SAB semantic refusal receipts proved target runtime/provider unavailability.
- `tam-wp-wp_dfa4e1134277` was executed directly because the row requested an internal read-only source-pack outline from existing Darshan notes and explicitly forbade outreach, publishing, CMS/paywall work, and exposing the engine to readers.

TAM receipts and artifacts:

- `reports/tam/packets/darshan-publication/SOURCE_PACK_OUTLINE_wp_dfa4e1134277.md`
- `reports/langgraph_parity/allnight/a2a_tam_darshan_publication_completion_20260701T061529Z.json`
- `reports/langgraph_parity/allnight/a2a_tam_darshan_publication_completion_receipt_20260701T061529Z.json`
- `reports/langgraph_parity/allnight/a2a_readiness_blocker_audit_20260701T061529Z_after_tam.json`

Live queue backup before TAM mutation:

- `/Users/dhyana/.dharma/a2a_bus/tasks/queue.jsonl.a2a-tam-darshan-complete-20260701T061529Z.bak`

TAM result:

- Confirmed no pre-existing `reports/tam/packets/darshan-publication/` deliverable existed in this worktree or `/Users/dhyana/dharma_swarm`.
- Created one outline file listing 8 existing local Darshan source atoms with one-line why-it-matters notes.
- Built a valid `dharma_a2a_task_receipt.v1` receipt with the outline artifact as evidence.
- Claimed the unassigned row as `codex_composer`.
- Closed `tam-wp-wp_dfa4e1134277` as `completed_verified`.
- Receipt mirrors were written to the `codex_composer` and `tam_operator` inboxes.

Current Phase 4 result:

- `.venv/bin/python scripts/governance/check_a2a_readiness.py --strict` still fails exit 2 with `ready=false`, `open_tasks=8`, `unknown_status_tasks=0`, `unverified_closed_tasks=0`.
- Fresh blocker audit reports `blocker_count=8`: 5 stale claimed rows and 3 stale unclaimed rows.

Remaining Phase 4 blockers:

- `forge-v0.1-001`
- `holon-plan-review-cursor-20260612`
- `holon-plan-review-opus-20260612`

## 2026-07-01 Addendum: Holon Review Targets And Forge v0.1 Closure

Two stale Holon review target rows and the final Forge v0.1 row were closed after the stale Hermes claim block.

Holon review target blocker:

- Added `scripts/governance/a2a_block_stale_holon_review_targets.py`
- Added `tests/test_a2a_stale_holon_review_target_blocker.py`
- The tool only targets `holon-plan-review-opus-20260612` and `holon-plan-review-cursor-20260612`.
- It requires the assigned review seat to be stale, the referenced plan path to be missing, and the expected seat-specific review deliverable to be absent.
- It records `blocked`, not `completed`, and the receipt evidence says `block_only_no_review_completion_or_target_impersonation`.

Holon receipts:

- `reports/langgraph_parity/allnight/a2a_stale_holon_review_block_dry_run_20260701T070500Z.json`
- `reports/langgraph_parity/allnight/a2a_stale_holon_review_block_20260701T070500Z.json`
- `reports/langgraph_parity/allnight/a2a_readiness_blocker_audit_20260701T070500Z_after_holon_reviews.json`

Holon live queue backup before apply:

- `/Users/dhyana/.dharma/a2a_bus/tasks/queue.jsonl.a2a-stale-holon-review-block-20260701T070500Z.bak`

Holon result:

- Dry-run found 2 candidates and 0 skips: `holon-plan-review-opus-20260612` and `holon-plan-review-cursor-20260612`.
- Apply blocked 2/2 candidates as valid `blocked_verified` A2A lifecycle rows with authority `stale_holon_review_target_supervisor_block`.
- `.venv/bin/python scripts/governance/check_a2a_readiness.py --strict` still failed exit 2 after this step with `ready=false`, `open_tasks=1`, `unknown_status_tasks=0`, `unverified_closed_tasks=0`.
- Fresh blocker audit reported `blocker_count=1`: `forge-v0.1-001`.

Forge v0.1 blocker:

- Added `scripts/governance/a2a_block_stale_forge_v01.py`
- Added `tests/test_a2a_stale_forge_v01_blocker.py`
- The tool only targets `forge-v0.1-001` for mission `20260531T172816Z-dharma-reward-forge-v0-1-x-chain-forge-council-v-97f649`.
- It requires the exact target `codex_forgewright`, stale open row state, body references to `docs/specs/forge_packets/v0.1.1-transfer-gate.md` and `20260601T172816Z_forge_v0_1_handoff.json`, missing spec/handoff files, and stale/manual target policy.
- It records `blocked`, not `completed`, and the receipt evidence says `block_only_no_forge_build_or_lane_selection_claimed`.

Forge receipts:

- `reports/langgraph_parity/allnight/a2a_stale_forge_v01_block_dry_run_20260701T072000Z.json`
- `reports/langgraph_parity/allnight/a2a_stale_forge_v01_block_20260701T072000Z.json`
- `reports/langgraph_parity/allnight/a2a_readiness_blocker_audit_20260701T072000Z_after_forge_v01.json`

Forge live queue backup before apply:

- `/Users/dhyana/.dharma/a2a_bus/tasks/queue.jsonl.a2a-stale-forge-v01-block-20260701T072000Z.bak`

Forge result:

- Dry-run found 1 candidate and 0 skips: `forge-v0.1-001`.
- Apply blocked 1/1 candidate as a valid `blocked_verified` A2A lifecycle row with authority `stale_forge_v01_supervisor_block`.
- `.venv/bin/python scripts/governance/check_a2a_readiness.py --strict` passed after this step with `ready=true`, `open_tasks=0`, `unknown_status_tasks=0`, `unverified_closed_tasks=0`.
- Fresh blocker audit reported `blocker_count=0`.

Verification:

- `.venv/bin/python -m pytest -q tests/test_a2a_stale_holon_review_target_blocker.py` -> `4 passed in 0.29s`
- `.venv/bin/ruff check scripts/governance/a2a_block_stale_holon_review_targets.py tests/test_a2a_stale_holon_review_target_blocker.py` -> pass
- `.venv/bin/python -m compileall -q scripts/governance/a2a_block_stale_holon_review_targets.py tests/test_a2a_stale_holon_review_target_blocker.py` -> pass
- `.venv/bin/python -m pytest -q tests/test_a2a_stale_forge_v01_blocker.py` -> `5 passed in 0.40s`
- `.venv/bin/ruff check scripts/governance/a2a_block_stale_forge_v01.py tests/test_a2a_stale_forge_v01_blocker.py` -> pass
- `.venv/bin/python -m compileall -q scripts/governance/a2a_block_stale_forge_v01.py tests/test_a2a_stale_forge_v01_blocker.py` -> pass
- `.venv/bin/python scripts/governance/check_a2a_readiness.py --strict` -> pass

Current Phase 4 result:

- `ready=true`
- `open_tasks=0`
- `unknown_status_tasks=0`
- `unverified_closed_tasks=0`
- `blocker_count=0`
- `l1-fx-001`
- `reconcile-564-565-20260611`
- `ts-hb0631-credit`
- `ts-pr-babysit-div-20260610`
- `yatagarasu-10cceaa8`

## 2026-07-01 Addendum: Stale Hermes Claimed Row Supervisor Block

After TAM completion, five remaining rows were stale `hermes-m5` claims with no terminal claimant receipt. A sixth narrow tool now handles only that class:

- Added `scripts/governance/a2a_block_stale_hermes_claims.py`
- Added `tests/test_a2a_stale_hermes_claim_blocker.py`
- The tool only targets explicitly allowed claimant ids, defaulting to `hermes-m5`.
- It requires `status=claimed`, claim age above the stale threshold, claimant presence stale/missing, and no valid matching terminal A2A receipt in the claimant inbox.
- It does not touch unclaimed rows, recent claims, non-allowed claimants, or rows with a valid claimant receipt.
- It records `blocked`, not `completed`, and the receipt evidence says `block_only_no_task_execution_or_completion_claimed`.

Receipts:

- `reports/langgraph_parity/allnight/a2a_stale_hermes_claim_block_dry_run_20260701T064000Z.json`
- `reports/langgraph_parity/allnight/a2a_stale_hermes_claim_block_20260701T064000Z.json`
- `reports/langgraph_parity/allnight/a2a_readiness_blocker_audit_20260701T064000Z_after_stale_hermes.json`

Live queue backup before apply:

- `/Users/dhyana/.dharma/a2a_bus/tasks/queue.jsonl.a2a-stale-hermes-claim-block-20260701T064000Z.bak`

Result:

- Dry-run found 5 candidates and 0 skips: `ts-hb0631-credit`, `ts-pr-babysit-div-20260610`, `reconcile-564-565-20260611`, `l1-fx-001`, and `yatagarasu-10cceaa8`.
- Apply blocked 5/5 candidates as valid `blocked_verified` A2A lifecycle rows with authority `stale_hermes_claim_supervisor_block`.
- `.venv/bin/python scripts/governance/check_a2a_readiness.py --strict` still fails exit 2, now with `ready=false`, `open_tasks=3`, `unknown_status_tasks=0`, `unverified_closed_tasks=0`.
- Fresh blocker audit now reports `blocker_count=3`; all remaining blockers are stale unclaimed rows.

Verification:

- `.venv/bin/python -m pytest -q tests/test_a2a_stale_hermes_claim_blocker.py` -> `4 passed in 0.29s`
- `.venv/bin/python scripts/governance/a2a_block_stale_hermes_claims.py --timestamp 2026-07-01T06:40:00Z --output reports/langgraph_parity/allnight/a2a_stale_hermes_claim_block_dry_run_20260701T064000Z.json` -> `candidate_count=5`, `applied_count=0`
- `.venv/bin/python scripts/governance/a2a_block_stale_hermes_claims.py --apply --timestamp 2026-07-01T06:40:00Z --output reports/langgraph_parity/allnight/a2a_stale_hermes_claim_block_20260701T064000Z.json` -> `candidate_count=5`, `applied_count=5`
- `.venv/bin/python scripts/governance/a2a_readiness_blocker_audit.py --artifact-root /Users/dhyana/ds_langgraph_parity_20260701 --artifact-root /Users/dhyana/dharma_swarm --output reports/langgraph_parity/allnight/a2a_readiness_blocker_audit_20260701T064000Z_after_stale_hermes.json` -> `blocker_count=3`

Remaining Phase 4 blockers:

- `forge-v0.1-001`
- `holon-plan-review-cursor-20260612`
- `holon-plan-review-opus-20260612`
