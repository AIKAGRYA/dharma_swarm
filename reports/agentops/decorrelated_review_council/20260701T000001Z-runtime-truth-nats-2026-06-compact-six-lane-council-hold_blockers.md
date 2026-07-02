# Decorrelated Review Council

conviction_gate: **hold_blockers**
target_score: 100
critics: 6 required=6
score_min: 0
score_avg: 66.67

## Blockers

- nimdeepseekv4: verdict=insufficient_context
- nimdeepseekv4: disagreement=The evidence claims all live matrix rows passed, but no raw data is provided to substantiate any of the required production readiness criteria. The review cannot proceed without concrete evidence.
- groqgptoss: verdict=insufficient_context

## Critics

- `nemotron3ultra` `openrouter_free:nvidia/nemotron-3-ultra-550b-a55b:free` ok=True verdict=pass score=100 actual=nvidia/nemotron-3-ultra-550b-a55b-20260604:free
  summary: All 12 live matrix paths passed against fresh local JetStream broker (run_id: nats-live-20260630T234132Z-187818af, generated 2026-06-30T23:42:50Z). Governance gates enforced: ACTIVE_TRACK.yaml requires live evidence checker, make nats-substrate-contract validates fresh evidence before local tests, negative test blocks a2a_send.py overclaim. Bypass publisher marked non-canonical (production_contract.canonical_runtime_truth_nats_task_path=false, production_readiness_claim_allowed=false). Caveat: e
- `nimllama` `nvidia_nim:meta/llama-3.3-70b-instruct` ok=True verdict=pass score=100 actual=meta/llama-3.3-70b-instruct
  summary: The provided evidence demonstrates end-to-end readiness for the scoped live broker profile, meeting all the required criteria for production-grade integration quality, anti-AI-slop, governance truthfulness, and code assurance.
- `nimdeepseekv4` `nvidia_nim:deepseek-ai/deepseek-v4-pro` ok=True verdict=insufficient_context score=0 actual=deepseek-ai/deepseek-v4-pro
  summary: The provided evidence is a summary report claiming all live matrix rows passed, but no actual live broker evidence, topology snapshots, envelope samples, or raw test outputs are included. The reviewer cannot independently verify any of the required production readiness criteria from the attached evidence file alone.
  blocker: No fresh live NATS/JetStream broker evidence (e.g., stream info, consumer info, message samples) is provided.
  blocker: No DS_TASKS or DS_DLQ topology evidence (e.g., nats stream info output) is included.
  blocker: No durable explicit-ack consumer evidence for a2a_task_handler is shown.
  blocker: No live publish evidence through A2ANatsTransport.publish_task is provided.
  blocker: No canonical envelope sample with dharma.nats.envelope.v1, stable message id, identity/causality fields, typed payload, and Nats-Msg-Id is included.
- `groqqwen` `groq:qwen/qwen3-32b` ok=True verdict=pass score=100 actual=qwen/qwen3-32b
  summary: All required production-grade NATS/JetStream integration criteria verified with live broker evidence. DLQ topology, explicit-ack consumers, idempotency, and governance-negative paths pass. Bypass publishers marked non-production-ready.
- `groqllama` `groq:llama-3.3-70b-versatile` ok=True verdict=pass score=100 actual=llama-3.3-70b-versatile
  summary: The provided evidence demonstrates end-to-end readiness for the scoped live broker profile, meeting all required criteria.
- `groqgptoss` `groq:openai/gpt-oss-120b` ok=True verdict=insufficient_context score=0 actual=openai/gpt-oss-120b
  summary: The submission provides only a high‑level markdown summary and command‑line output. No raw live‑broker matrix JSON, envelope samples, consumer configuration dumps, or failure‑injection logs are attached. Without these concrete artifacts the claims of passing every required path (topology, happy‑path, duplicate handling, DLQ behavior, idempotency, governance‑negative tamper, etc.) cannot be independently verified. Therefore the evidence is insufficient to certify production readiness.
  blocker: Missing raw live NATS/JetStream matrix JSON (reports/governance/nats_live_production_matrix/latest.json).
  blocker: No concrete message envelope examples showing dharma.nats.envelope.v1 fields, stable message ID, identity/causality, typed payload, and Nats-Msg-Id header.
  blocker: No broker or client logs demonstrating publish, ack, nack, redelivery, DLQ publish attempts, or ack‑failure handling.
  blocker: No evidence of idempotency retry and stale‑started path behavior.
  blocker: No proof of concurrent duplicate detection and truthful nacking.

## Persistent Agent

- `palantir-pilot` status=running fresh=True
