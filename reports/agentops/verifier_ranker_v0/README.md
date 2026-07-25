# DharmaVerifier-Ranker v0 Starter Package

Date: 2026-07-01 JST  
Role: report / witness / training-readiness package  
Authority: advisory only, no dispatch, no promotion, no public-claim approval

## Status

This directory is the first train-ready starter package for `DharmaVerifier-Ranker v0`.
It does not contain a trained model. It makes real training possible by freezing the
schema, privacy boundary, inventory, label plan, baseline plan, eval plan, training
readiness plan, model-card template, and artifact hashes.

Current external-worker state:

- `qwen_code` / `deepseek_ml_lead` remains `external_worker_evidence_only`.
- A sanitized DeepSeek smoke for this package was attempted.
- Receipt: `reports/agentops/deepseek_smokes/qwen-code-deepseek-v4-pro-smoke-20260630T163239Z.json`
- Result: `blocked_missing_deepseek_api_key`.
- No private prompt text or API key was logged.

## Package Contents

- `DHARMA_SEMANTIC_RECEIPT_GRAPH_V0.schema.json`
- `DHARMA_VERIFIER_RANKER_OUTPUT_V0.schema.json`
- `DATA_INVENTORY_20260701.md`
- `DATA_INVENTORY_RECEIPT_20260701.json`
- `REDACTION_AND_PRIVACY_RULES_20260701.md`
- `LABEL_TAXONOMY_AND_GOLD_PLAN_20260701.md`
- `MODEL_ARCHITECTURE_AND_TRAINING_READINESS_20260701.md`
- `TRAINING_COMMAND_PLAN_20260701.md`
- `BASELINE_AND_EVAL_PLAN_20260701.md`
- `TOOL_RESOURCE_RESEARCH_20260701.md`
- `PROMOTION_AND_KILL_GATES_20260701.md`
- `MODEL_CARD_TEMPLATE_20260701.md`
- `MODEL_CARD_AND_PROMOTION_DECISION_20260701.md`
- `PACKAGE_MANIFEST_20260701.json`

Supporting code:

- `dharma_swarm/verifier_ranker_v0/redaction.py`
- `dharma_swarm/verifier_ranker_v0/schemas.py`
- `dharma_swarm/verifier_ranker_v0/inventory.py`
- `dharma_swarm/verifier_ranker_v0/package.py`
- `scripts/agentops/verifier_ranker_v0_inventory.py`
- `scripts/agentops/verifier_ranker_v0_write_schemas.py`
- `scripts/agentops/verifier_ranker_v0_verify_package.py`
- `tests/test_verifier_ranker_v0.py`

## Boundary

The model may recommend:

- `approve`
- `revise`
- `block`
- `escalate`
- `insufficient_context`

The model may not:

- approve public claims;
- replace tests, hidden holdouts, external verifiers, or operator judgment;
- mutate routing policy;
- dispatch agents;
- train on raw private logs, secrets, credentials, provider payloads, raw message bodies, or unredacted home-state logs.

## Verification Commands

```bash
pytest -q tests/test_verifier_ranker_v0.py
./.venv/bin/python scripts/agentops/verifier_ranker_v0_inventory.py
./.venv/bin/python scripts/agentops/verifier_ranker_v0_write_schemas.py
./.venv/bin/python scripts/agentops/verifier_ranker_v0_verify_package.py --write-manifest
./.venv/bin/python scripts/agentops/verifier_ranker_v0_verify_package.py
```

## Evidence Notes

- `make onboard` was run before report edits, per `docs/AGENTS.md`.
- Memory Common was queried for this task; the only directly useful retrieved source was governance context `text_file:users-dhyana-dharma_swarm-claude.md:eb791d775cef`, which reinforced the `make onboard` and evidence discipline rules. It was not used as proof of data counts.
- Current counts and SQLite table metadata come from `DATA_INVENTORY_RECEIPT_20260701.json`, generated metadata-only with `raw_private_body_readout=false`.
