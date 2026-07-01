# Tool and Resource Research

Role: reference report for current tooling choices

## Sources Consulted

Context7 current docs:

- Hugging Face TRL `/huggingface/trl/v0.29.0`
  - `RewardTrainer`
  - `DPOTrainer`
  - `OnlineDPOTrainer`
  - `CPOTrainer`
  - `ORPOTrainer`
  - Source URLs returned by Context7 include TRL docs under `https://github.com/huggingface/trl/blob/v0.29.0/docs/source/`.
- Hugging Face PEFT `/huggingface/peft`
  - `LoraConfig`
  - `get_peft_model`
  - QLoRA-style `target_modules="all-linear"` guidance
  - Source URLs returned by Context7 include `https://github.com/huggingface/peft/blob/main/docs/source/package_reference/lora.md`.
- vLLM stable docs `/websites/vllm_ai_en_stable`
  - structured outputs with JSON schema / Pydantic schema
  - Source URL returned by Context7: `https://docs.vllm.ai/en/stable/features/structured_outputs`.

Primary docs to pin during implementation:

- Transformers Trainer: `https://huggingface.co/docs/transformers/en/main_classes/trainer`
- Hugging Face Datasets splits: `https://huggingface.co/docs/datasets/en/package_reference/main_classes`
- scikit-learn calibration: `https://scikit-learn.org/stable/modules/calibration.html`
- MLflow Model Registry: `https://mlflow.org/docs/latest/ml/model-registry/`
- DVC data versioning: `https://dvc.org/doc/start/data-management/data-versioning`
- Hugging Face LightEval: `https://huggingface.co/docs/lighteval/`

## Recommended Stack

Data and versioning:

- JSONL graph export validated against `DHARMA_SEMANTIC_RECEIPT_GRAPH_V0.schema.json`.
- DVC or content-addressed manifests for dataset versioning.
- Hash-locked split manifests and artifact receipts.

Training:

- sklearn baseline for structured features and calibration sanity.
- Transformers `Trainer` for encoder/cross-encoder classifier.
- TRL `RewardTrainer` for pairwise reward/ranker training.
- TRL `DPOTrainer` only if training a small generative preference model is justified.
- PEFT LoRA for small adapter experiments.
- QLoRA-style adapters only after smaller baselines justify external GPU use.

Evaluation:

- deterministic validators first;
- frozen Python scorer;
- LightEval or custom harness only after the task schema is stable;
- calibration via scikit-learn-style Brier/ECE/reliability curves.

Serving:

- Python schema validation for every output.
- vLLM structured outputs only when moving to a served model path.
- OpenAI-compatible JSON-schema response format where supported.

Registry:

- Local model registry path under `~/.dharma/models/dharma-verifier-ranker-v0/`.
- MLflow can be adopted if experiments multiply; v0 can remain content-addressed receipts.

## Tool Choices Not Yet Justified

Do not start with:

- 7B QLoRA;
- NeMo/Megatron training;
- production vLLM service;
- autonomous router integration;
- public benchmark claims.

Reason: the graph export, redaction audit, gold labels, and baselines are not complete yet.

## Current External Blockers

- DeepSeek V4 Pro route is not live in the current shell because `DEEPSEEK_API_KEY` is absent.
- CUDA/NVIDIA local training is unavailable on this host.
- Frontier API judging depends on live credentials and must record exact provider/model snapshots.
