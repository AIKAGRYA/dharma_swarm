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

## Blocker

Phase 4 is not green. The live queue still contains open/claimed work and completed rows without embedded A2A task receipts. The SAB rows carry `sab.semantic_receipt` pointers or stale `receipt_validation` metadata, but the strict A2A gate correctly requires an embedded valid `dharma_a2a_task_receipt.v1` receipt or terminal closure through the governed lifecycle.
