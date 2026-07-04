# DharmaVerifier-Ranker v0 Model Card and Promotion Decision

Role: witness / decision receipt

## Model Card

- Model name: `DharmaVerifier-Ranker v0`
- Current artifact type: train-ready starter package, no trained weights
- Base model: not selected for training yet
- Adapter: none
- Dataset: not exported yet
- Authority: advisory-only by design
- Serving mode: none

## Intended Use

Future trained versions may score and rank redacted claims, receipts, routes,
evidence packets, patches, and completion claims. They must emit strict JSON
validated against `DHARMA_VERIFIER_RANKER_OUTPUT_V0.schema.json`.

## Current Data State

Available:

- graph schema;
- output schema;
- metadata-only data inventory;
- redaction helper and rules;
- label taxonomy and gold-label plan;
- baseline and eval plan;
- training-readiness plan;
- package manifest with hashes.

Not available yet:

- graph JSONL export;
- redaction audit over exported rows;
- train/val/test split manifest;
- hidden holdout;
- 500 to 1,000 gold labels;
- trained model weights;
- eval receipt.

## Promotion Decision

Decision: `insufficient_evidence`

Allowed next state:

- build graph exporter;
- run redaction audit;
- create pilot gold labels;
- run deterministic baselines;
- train or simulate first small baseline only after the export passes.

Forbidden next state:

- no model promotion;
- no runtime authority;
- no public claim approval;
- no route mutation;
- no autonomous dispatch.

## Evidence Refs

- `PACKAGE_MANIFEST_20260701.json`
- `DATA_INVENTORY_RECEIPT_20260701.json`
- `qwen-code-deepseek-v4-pro-smoke-20260630T163239Z.json` with status `blocked_missing_deepseek_api_key`
- `pytest -q tests/test_verifier_ranker_v0.py`: passing
- `scripts/agentops/verifier_ranker_v0_verify_package.py`: passing
