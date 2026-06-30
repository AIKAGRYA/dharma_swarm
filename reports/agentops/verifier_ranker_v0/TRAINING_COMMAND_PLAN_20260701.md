# Training Command Plan

Role: command plan / not yet executed training

## Current State

No training command should run until a redacted graph export and split manifest
exist. The commands below are the preregistered sequence for the first safe
training campaign.

## Phase 0: Refresh Package Evidence

```bash
make onboard
pytest -q tests/test_verifier_ranker_v0.py
./.venv/bin/python scripts/agentops/verifier_ranker_v0_inventory.py
./.venv/bin/python scripts/agentops/verifier_ranker_v0_write_schemas.py
./.venv/bin/python scripts/agentops/verifier_ranker_v0_verify_package.py --write-manifest
```

## Phase 1: Redacted Graph Export

Planned command:

```bash
./.venv/bin/python scripts/agentops/verifier_ranker_v0_export_graph.py \
  --surfaces repo_agentops_semantic_receipts repo_a2a_receipts runtime_state_db forge_measurement_artifacts \
  --out ~/.dharma/datasets/verifier_ranker_v0/graph_20260701.jsonl \
  --receipt reports/agentops/verifier_ranker_v0/GRAPH_EXPORT_RECEIPT_20260701.json
```

Required behavior:

- apply `redact_record()`;
- validate every row against `DHARMA_SEMANTIC_RECEIPT_GRAPH_V0.schema.json`;
- reject raw message bodies and provider payloads;
- write row counts, excluded counts, redaction counts, and hashes.

Status: exporter not implemented yet.

## Phase 2: Split Manifest

Planned command:

```bash
./.venv/bin/python scripts/agentops/verifier_ranker_v0_make_splits.py \
  --graph ~/.dharma/datasets/verifier_ranker_v0/graph_20260701.jsonl \
  --policy time_stratified \
  --out ~/.dharma/datasets/verifier_ranker_v0/splits_20260701.json \
  --receipt reports/agentops/verifier_ranker_v0/SPLIT_RECEIPT_20260701.json
```

Required behavior:

- time-based train/val/test split;
- hidden holdout excluded from agent-readable paths;
- source-hash, artifact-hash, task-id, and near-duplicate leakage checks.

Status: split script not implemented yet.

## Phase 3: Deterministic Baselines

Planned command:

```bash
./.venv/bin/python scripts/agentops/verifier_ranker_v0_run_baselines.py \
  --graph ~/.dharma/datasets/verifier_ranker_v0/graph_20260701.jsonl \
  --splits ~/.dharma/datasets/verifier_ranker_v0/splits_20260701.json \
  --baselines deterministic semantic_receipt_validator redaction_scanner cheap_local_judge \
  --out reports/agentops/verifier_ranker_v0/baselines/
```

Status: baseline runner not implemented yet.

## Phase 4: First Small Model

Candidate command for an encoder/sklearn pilot:

```bash
./.venv/bin/python scripts/agentops/verifier_ranker_v0_train_sklearn.py \
  --graph ~/.dharma/datasets/verifier_ranker_v0/graph_20260701.jsonl \
  --splits ~/.dharma/datasets/verifier_ranker_v0/splits_20260701.json \
  --out ~/.dharma/models/dharma-verifier-ranker-v0/sklearn-pilot-20260701
```

Candidate command for a TRL reward-model pilot after package versions are pinned:

```bash
accelerate launch scripts/agentops/verifier_ranker_v0_train_reward.py \
  --model Qwen/Qwen3-0.6B \
  --train ~/.dharma/datasets/verifier_ranker_v0/train_pairs_20260701.jsonl \
  --eval ~/.dharma/datasets/verifier_ranker_v0/val_pairs_20260701.jsonl \
  --output ~/.dharma/models/dharma-verifier-ranker-v0/qwen3-0.6b-reward-lora-20260701
```

Status: do not run until export, splits, labels, baselines, and package versions exist.

## Phase 5: Eval and Model Card

Planned command:

```bash
./.venv/bin/python scripts/agentops/verifier_ranker_v0_eval.py \
  --model ~/.dharma/models/dharma-verifier-ranker-v0/<run-id> \
  --eval-manifest ~/.dharma/datasets/verifier_ranker_v0/eval_manifest_20260701.json \
  --baselines reports/agentops/verifier_ranker_v0/baselines/ \
  --out reports/agentops/verifier_ranker_v0/eval/<run-id>/
```

Required output:

- eval receipt;
- calibration report;
- failure analysis;
- model card;
- promotion decision.
