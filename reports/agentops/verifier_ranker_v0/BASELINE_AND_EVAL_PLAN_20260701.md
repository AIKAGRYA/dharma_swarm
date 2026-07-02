# Baseline and Evaluation Plan

Role: active report / eval design

## Principle

Internal receipts are telemetry, not proof. A verifier/ranker is promotable only
through paired, reproducible, hash-locked evaluation.

## Baselines

Required baselines:

1. Deterministic validators:
   - semantic receipt validator;
   - redaction scanner;
   - schema validator;
   - existing rule scorers and evaluation modules.
2. Current repo rule scorers:
   - `dharma_swarm/evaluator.py`
   - `dharma_swarm/operator_core/semantic_receipt.py`
   - `scripts/runtime/cross_model_verification.py`
3. DeepSeek V4 Pro as judge:
   - route: `qwen_code` / `deepseek_ml_lead`;
   - current status: blocked by missing `DEEPSEEK_API_KEY`;
   - receipt: `reports/agentops/deepseek_smokes/qwen-code-deepseek-v4-pro-smoke-20260630T163239Z.json`.
4. Frontier API judge if available:
   - exact provider/model snapshot required at run time;
   - no silent fallback.
5. Open/open-weight judge or ranker:
   - local Ollama or open-weight judge if live;
   - exact model id and quantization recorded.
6. Simple majority / self-MoA:
   - budget matched;
   - no extra context for one arm.
7. Cheap local model baseline:
   - prompt-only JSON judge over redacted inputs;
   - schema validity and calibration measured.

## Eval Set

Minimum internal shakeout:

- 30 paired heldout tasks.

Minimum model comparison:

- 100 paired heldout tasks.

Gold promotion candidate:

- 500 to 1,000 labeled items with hidden holdouts.

Each eval item has:

- frozen task id;
- redacted input;
- candidate outputs/actions/routes;
- expected label or adjudicated outcome;
- evidence refs and hashes;
- privacy tags;
- source timestamp bucket;
- split id.

## Hash-Locking

Hash-lock:

- task ids;
- input JSON;
- candidate artifacts;
- expected labels;
- scoring script;
- model output JSON;
- provider/model snapshot;
- cost/token ledger;
- replay command.

No item deletion, rubric edits, model fallback, prompt edits, or retry expansion after preregistration.

## Metrics

Classification:

- accuracy and macro F1 for verdict;
- AUROC / PR-AUC for `block/revise` vs `approve`;
- recall for `privacy_violation`;
- recall for `unsupported_claim`;
- false approve rate.

Ranking:

- pairwise accuracy;
- NDCG;
- Kendall tau where multiple candidates exist.

Calibration:

- Brier score;
- expected calibration error;
- reliability curve;
- confidence interval on main metric.

Operational:

- cost saved before expensive verification;
- downstream pass-rate lift in shadow mode;
- disagreement cases routed to active learning;
- latency.

## Budget Matching

For each paired comparison:

- same task set;
- same evidence refs;
- same privacy-redacted input;
- same max retries;
- same model fallback policy: no fallback unless preregistered for all arms;
- token/cost ledger recorded.

## Replay Instructions

Required future commands:

```text
export DHARMA_VERIFIER_EVAL_MANIFEST=<hash-locked manifest>
run deterministic baseline
run local judge baseline
run DeepSeek/frontier/open judge baselines when credentials exist
run candidate model
score with frozen scorer
write eval receipt and model card
```

## Pass / Fail Gates

Internal go:

- no leakage;
- no schema invalid outputs;
- better than deterministic baseline on main metric;
- confidence interval lower bound above zero for paired improvement;
- privacy recall not worse than deterministic scanner;
- no public authority granted.

Internal no-go:

- hidden payloads agent-readable;
- gold labels leak into train;
- candidate can mutate verifier/scorer;
- provider/model differs from preregistration;
- all arms saturate or all fail;
- confidence is miscalibrated and unsafe;
- privacy recall regresses.
