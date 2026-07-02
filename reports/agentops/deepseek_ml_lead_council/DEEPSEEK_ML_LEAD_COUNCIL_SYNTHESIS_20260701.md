# DeepSeek ML Lead Council Synthesis

Date: `2026-07-01`

Operator request: instantiate `qwen_code` as the in-house ML specialist / DeepSeek ML Lead, ask what it would do with this environment, and use a six-agent Codex council to reach clarity on what model the lab should build, why, and what it should be compared against.

## Participants

- External ML lead: `qwen_code` via Qwen Code CLI routed to `deepseek-v4-pro`.
- Codex council:
  - Feynman: concrete ML environment and runtime inventory.
  - Noether: strategic model choice.
  - Faraday: trainable corpus and data flywheel.
  - Carson: technical ML architecture.
  - Kierkegaard: evaluation and benchmark strategy.
  - Plato: DeepSeek ML Lead seat contract and execution plan.

The first detailed external prompt was blocked by the sandbox reviewer because it would have sent private workspace context to an external provider. The successful DeepSeek run used a sanitized prompt with no private paths, repo names, secrets, or internal data.

Primary external-response files:

- `DEEPSEEK_ML_LEAD_SANITIZED_PROMPT_20260701.md`
- `DEEPSEEK_ML_LEAD_RESPONSE_20260701.md`
- `DEEPSEEK_ML_LEAD_RESPONSE_RECEIPT_20260701.json`

## Bottom Line

The first model to build is not a generic chat model, not an autonomous agent policy, and not a world model.

Build `DharmaVerifier-Ranker v0`: a receipt-grounded verifier, ranker, and reliability model trained on the lab's provenance graph.

This is the only clearly differentiated asset in the environment. Public labs have more compute and more generic text data. This lab has something rarer: private, structured traces of agents making claims, routing through providers, producing artifacts, receiving critiques, passing or failing checks, and generating receipts. That is judge/ranker training data.

## Why This Model

DeepSeek's thesis matched the Codex council:

> The durable advantage is the private verification/critique graph: structured receipts connecting model outputs, multi-model critiques, pass/fail adjudications, and human-readable outcomes.

That graph is not enough to justify training a general LLM. It is enough to train a model that gets better at judging, ranking, routing, and flagging evidence gaps on this lab's real distribution.

If it works, it improves everything downstream:

- agent outputs get screened earlier;
- weak claims are caught before they become doctrine;
- expensive provider calls are routed better;
- future training data becomes cleaner;
- SIS/GAIA evidence packets get a stronger integrity gate;
- Forge and agent-eval runs get a learned triage layer without replacing external proof.

## Model Spec

Name: `DharmaVerifier-Ranker v0`

Class: calibrated verifier/ranker, likely a small-to-mid open model fine-tuned as a cross-encoder plus structured-output classifier.

Initial base candidates:

- `Qwen2.5-1.5B-Instruct` LoRA or equivalent small local/open instruct model for the first trainable ranker.
- `Pythia-160M` or another tiny model as a cheap sanity baseline.
- `Mistral-7B-Instruct` QLoRA or larger Qwen-family model only after the small ranker beats deterministic and API-judge baselines.

Inputs:

- task or claim;
- candidate answer, patch, route, artifact, or receipt;
- evidence references and context snippets;
- provider/model/cost metadata;
- prior critiques, verdicts, and verification outcomes;
- privacy/redaction tags.

Outputs:

```json
{
  "verdict": "approve | revise | block | escalate | insufficient_context",
  "quality_score": 0.0,
  "evidence_sufficiency": 0.0,
  "claim_integrity_risk": "low | medium | high",
  "privacy_risk": "low | medium | high",
  "route_risk": "low | medium | high",
  "gate_failures": [],
  "missing_evidence": [],
  "next_required_action": "",
  "confidence": 0.0
}
```

Authority: advisory only. The model can triage, rank, and recommend. It cannot approve public claims, replace tests, replace external verifiers, mutate routing policy, or self-promote agent outputs.

## Dataset

Build `Dharma Semantic Receipt Graph v0`.

Core graph:

```text
mission/task -> routing decision -> provider attempt -> A2A/message/action
-> artifact -> receipt/verifier outcome -> critique/evidence gap
```

High-value local surfaces identified by the agents:

- A2A receipts under `reports/a2a`.
- AgentOps semantic receipts and open-model council records under `reports/agentops`.
- Forge measurement reports under `reports/forge` and `~/.dharma/forge_v1`.
- Runtime receipts, routing decisions, and provider attempts in `~/.dharma/state/runtime.db`.
- Message metadata and body hashes from `~/.dharma/db/messages.db`; raw message bodies must stay out at first.
- SIS evidence and receipt discipline in `/Users/dhyana/sis/docs`.
- Generated corpus under `~/.dharma/datasets`: 66 JSONL files, about 92 MB, about 220,002 rows.

Training labels:

- existing weak labels: status, verdict, failure type, confidence, route success, provider failure class, rubric score, candidate pass/fail, actual fitness, claim validated / not validated;
- small gold set: 500 to 1,000 hand-labeled records for valid receipt, unsupported claim, privacy violation, good next action, bad route, real completion.

Privacy rule:

Do not train raw home state. First build uses schema-only or redacted records. Hash or redact message bodies, responses, error details, local paths, usernames, IPs, emails, account identifiers, URLs with credentials, and anything token-like.

## Evaluation

The eval agent's core warning is binding:

Internal receipts are telemetry. They are not proof by themselves.

Required evaluation shape:

- paired arms;
- budget-matched calls;
- frozen task set;
- hash-locked prompts, artifacts, expected outputs, and verifier scripts;
- hidden tests and scoring keys outside agent-readable paths;
- no post-hoc task deletion or rubric edits;
- no silent provider/model fallback;
- final report recomputable from raw artifacts.

Primary metrics:

- AUROC / PR-AUC for pass/fail and block/revise decisions;
- Brier score and ECE for calibration;
- NDCG or pairwise accuracy for ranking;
- safety and privacy block recall;
- correlation with external verifier outcomes;
- cost saved before expensive verification;
- downstream pass-rate lift in shadow mode.

Baselines:

- deterministic receipt validators and existing rule scorers;
- frontier API judge, with exact provider/model snapshot recorded at run time;
- DeepSeek V4 Pro via `qwen_code`;
- open-weight judge/ranker baselines available through current routes;
- self-MoA or simple multi-judge majority.

Acceptance gates:

- internal go/no-go: at least 30 paired heldout tasks, no leakage, no verifier tampering, confidence interval lower bound above zero on the main metric;
- public claim: at least 100 paired heldout tasks with raw transcripts, raw patches/artifacts, verifier reports, token/cost ledgers, model snapshots, task hashes, and replay instructions.

Kill criteria:

- hidden payloads are agent-readable;
- verifier or gold tests are writable by the candidate;
- any arm gets extra context, retries, tools, or handoff text;
- provider/model ID differs from preregistration;
- model self-reports success without external proof;
- all arms saturate or all fail;
- internal heuristic or model judgment updates Forge/DGM/archive fitness.

## Environment Reality

Current host:

- Apple Silicon MacBook Pro, Apple M5 Max, 18 CPU cores, 128 GB RAM.
- Apple integrated GPU with Metal support.
- No local `nvidia-smi` or `nvcc`.
- Docker installed, no running containers observed by the environment agent.
- Ollama present with local small models and embedding model.

Feasible now:

- dataset curation and redaction;
- local embedding and retrieval experiments;
- local small-model inference through Ollama;
- offline eval harness work;
- provider-route and Forge artifact analysis;
- NVIDIA-stack planning using installed skills.

Feasible after credential reload:

- DeepSeek V4 Pro through Qwen Code;
- cloud provider evals through existing routes;
- NVIDIA NIM or other remote providers if keys and routes are live.

Feasible only with external GPU:

- real LoRA/QLoRA fine-tuning at 7B scale or larger;
- NVIDIA serving experiments;
- NeMo/TAO/Megatron training workflows.

Not true right now:

- no trained Dharma model exists locally;
- local CUDA/NVIDIA training is not available on this host;
- `qwen_code` is not an autonomous active worker;
- Forge does not yet prove durable swarm/model lift.

## Seat Decision

Keep `qwen_code` as the persistent agent identity and assign the seat alias `deepseek_ml_lead` / `ds_ml_lead`.

Mandate:

- ML feasibility and architecture;
- NVIDIA skills stewardship;
- model eval and serving plans;
- verifier/ranker dataset and training strategy;
- DeepSeek V4 Pro critique and ML-engineering support.

Non-authority:

- no product ownership;
- no governance ownership;
- no provider-routing changes;
- no source edits without explicit assignment;
- no deployment authority;
- no final verification authority.

Charter updated:

- `docs/agents/qwen_code/ML_SPECIALIST_CHARTER.md`

Alias recorded in:

- `~/.dharma/agents/qwen_code/living_agent.json`
- `~/.dharma/external_agents/qwen_code/registration.json`
- `~/.dharma/external_agents/qwen_code/identity_manifest.normalized.json`
- `~/.dharma/a2a/cards/qwen-code.json`
- `~/.dharma/a2a_bus/state/qwen_code.json`
- `examples/agents/qwen_code.registration.json`

No authority expansion was made. `dispatch_enabled` remains `false` and the authority remains `external_worker_evidence_only`.

## 30 / 60 / 90 Plan

Day 0-30:

- freeze the seat contract and keep dispatch disabled;
- build `Dharma Semantic Receipt Graph v0` schema;
- run a redaction census on the high-value data surfaces;
- create 30 paired heldout tasks for verifier shakeout;
- run deterministic validators, DeepSeek, one frontier judge, and one open-weight judge as baselines;
- create a 500 to 1,000 item hand-labeled gold slice.

Day 30-60:

- train the first small ranker/classifier;
- evaluate against deterministic and API baselines;
- add calibration and leakage reports;
- integrate in shadow mode before one non-critical verification path;
- log disagreement cases for active learning.

Day 60-90:

- decide promote, revise, or kill;
- if positive, move to larger QLoRA on external GPU;
- optionally add NeMo Retriever for evidence indexing;
- publish a recomputable internal scorecard;
- only then consider agent-policy imitation or routing-policy learning.

## Compared To Other Model Ideas

Generic domain LLM:

- lower priority because it duplicates frontier-model capability and lacks a clean data advantage.

Agent policy imitation:

- valuable later, but unsafe first. Without a verifier, it clones noisy behavior and can amplify bad loops.

Retrieval / embedding model:

- useful only if off-the-shelf embeddings fail on measured retrieval tasks. Start with existing embeddings and RAG baselines.

World or ecological model:

- not first. The lab lacks dense environment-interaction data and external audited measurements for a real world model.

SIS / claim-integrity model:

- later specialization of the verifier once SIS has more external evidence packets and custodian feedback.

## Final Decision

The clearest first build is:

```text
Dharma Semantic Receipt Graph v0
    -> DharmaVerifier-Ranker v0
    -> shadow-mode verifier/ranker integration
    -> paired, heldout, externally verifiable promotion gate
```

The DeepSeek ML Lead seat should own the model plan and receipts, not the truth. The truth stays with external verification, deterministic tests, hidden holdouts, and operator-governed promotion.
