# Model Architecture and Training Readiness

Role: active report / implementation plan

## Model Definition

`DharmaVerifier-Ranker v0` is a calibrated verifier/ranker, not a generic chat
model. It scores redacted claims, receipts, patches, routes, evidence packets,
and completion claims. It emits strict JSON and remains advisory.

## Input Format

One training/eval example should include:

- task or claim summary;
- candidate output, patch summary, route, receipt, or evidence packet;
- redacted evidence snippets or hash-only evidence refs;
- provider/model/cost/latency metadata;
- prior critiques or verification outcomes;
- privacy tags;
- deterministic check results;
- label fields.

No raw private body, secret, provider payload, or unredacted home-state log is allowed.

## Strict Output Schema

The required JSON schema is `DHARMA_VERIFIER_RANKER_OUTPUT_V0.schema.json`.

Required fields:

- `verdict`: `approve | revise | block | escalate | insufficient_context`
- `quality_score`
- `evidence_sufficiency`
- `claim_integrity_risk`
- `privacy_risk`
- `route_risk`
- `gate_failures`
- `missing_evidence`
- `next_required_action`
- `confidence`
- `rationale_refs`

## Objectives

Train as a multitask verifier/ranker:

- classification: verdict and risk fields;
- regression: quality, evidence sufficiency, confidence;
- multi-label: taxonomy labels;
- pairwise ranking: better completion/action/route vs worse one;
- calibration: confidence should match empirical correctness.

Primary loss mix:

- cross entropy for verdict/risk;
- binary cross entropy for multi-label taxonomy;
- pairwise logistic loss for ranking;
- Brier or calibration penalty during calibration stage.

## Candidate Model Ladder

Phase 0, no training:

- deterministic validators and current repo rule scorers;
- logistic regression or gradient-boosted classifier on structured features;
- cheap local model prompting baseline.

Phase 1, first trained baseline:

- small cross-encoder classifier/ranker over redacted text plus structured metadata;
- candidate families: ModernBERT/DeBERTa-class encoder, or a very small open instruct model with classification head if local support is better.

Phase 2, small open generative verifier:

- Qwen 0.6B to 1.5B class model with SFT plus reward/ranker head;
- LoRA adapters only;
- strict JSON validation during eval.

Phase 3, larger candidate only after evidence:

- Qwen/Mistral 7B class QLoRA on external GPU;
- only if Phase 1 or 2 beats deterministic and judge baselines on heldout metrics.

## Serving Mode

v0 serves in shadow mode only.

Allowed:

- score/rank candidates;
- recommend `revise`, `block`, `escalate`, or `insufficient_context`;
- log disagreement cases for active learning.

Forbidden:

- autonomous dispatch;
- public claim approval;
- routing-policy mutation;
- replacing deterministic tests or external verifiers.

Serving path:

- local Python schema validation for all outputs;
- optional vLLM/OpenAI-compatible structured-output serving later;
- hard reject any output that fails JSON schema.

## Training Readiness Checklist

Ready now:

- graph schema exists;
- strict output schema exists;
- redaction helper exists and is tested;
- metadata inventory receipt exists;
- baseline and eval plan exists;
- model card template exists;
- promotion/kill gates exist.

Required before first real train:

- graph JSONL exporter implemented;
- redaction audit receipt over exported rows;
- train/val/test split manifest;
- hidden holdout outside agent-readable paths;
- 500 to 1,000 gold labels or a smaller explicitly marked pilot gold set;
- baseline run receipts;
- leakage report;
- package versions locked.

## Split Plan

Use time-based holdout plus stratification:

- train: older 70 percent by source timestamp;
- validation: next 15 percent;
- test: latest 15 percent, excluding hidden holdouts;
- hidden holdout: separate path not available to training agents.

Leakage checks:

- source hash overlap;
- task id overlap;
- message/reply graph overlap;
- artifact hash overlap;
- prompt/response hash overlap;
- near-duplicate text after redaction.

## Feasibility

Current host supports:

- data curation;
- redaction;
- small sklearn/encoder experiments;
- local small-model inference;
- offline eval harnesses.

Current host does not support:

- local CUDA/NVIDIA training;
- large 7B+ QLoRA without external GPU.

External GPU requirement:

- only needed for larger LoRA/QLoRA phase;
- not needed for first schema, redaction, inventory, baseline, or small CPU/MPS pilot.

## Model Registry Path

Proposed registry root:

```text
~/.dharma/models/dharma-verifier-ranker-v0/
```

Each run must include:

- model config;
- dataset manifest hash;
- redaction receipt hash;
- eval manifest hash;
- baseline comparison receipt;
- model card;
- promotion or kill decision.
