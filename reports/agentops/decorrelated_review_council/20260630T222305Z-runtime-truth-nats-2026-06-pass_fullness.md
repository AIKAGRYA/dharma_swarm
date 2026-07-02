# Decorrelated Review Council

conviction_gate: **pass_fullness**
target_score: 100
critics: 6 required=6
score_min: 100
score_avg: 100.0

## Blockers

- none

## Critics

- `glm52` `ollama:glm-5.2:cloud` ok=True verdict=approve score=100 actual=glm-5.2
  summary: All ten original required changes are addressed for the scoped local/offline NATS substrate slice. Idempotency retry semantics use :retry:<uuid> side-effect keys with retry_blocked for in-progress and completed-only duplicate success. DLQ behavior publishes typed dharma.nats.dlq_failure.v1 with NATS_MAX_DELIVER_EXHAUSTED before acking original. Canonical envelope dharma.nats.envelope.v1 includes all required fields and Nats-Msg-Id. Durable topology declares DS_TASKS/DS_DLQ with explicit ack cons
- `kimi27code` `ollama:kimi-k2.7-code:cloud` ok=True verdict=pass score=100 actual=kimi-k2.7-code
  summary: All ten original required changes for the scoped local/offline NATS substrate hardening slice are satisfied by the provided evidence.
- `qwen3coder` `ollama:qwen3-coder:480b-cloud` ok=True verdict=pass score=100 actual=qwen3-coder:480b-cloud
  summary: All ten original requirements have been satisfied for the local/offline NATS substrate hardening slice. Idempotency retry semantics are correctly implemented with side-effect keys and proper duplicate handling. Regression tests cover all required failure modes and behaviors. The canonical NATS envelope contract is fully implemented and tested. Durable stream/consumer setup and DLQ behavior match the spec. A2A paths use a governed transport abstraction with equivalent guarantees. Negative contrac
- `deepseekv4pro` `ollama:deepseek-v4-pro:cloud` ok=True verdict=pass score=100 actual=deepseek-v4-pro
  summary: All ten original requirements are satisfied for the scoped local/offline NATS substrate slice. Evidence covers idempotent retry semantics, regression tests, canonical envelope, durable stream/DLQ, governed transport abstraction, negative contract tests, executable active-track gates, correct owned surfaces, closeout packet with explicit scoping, and the track remains ACTIVE pending operator lifecycle review.
- `minimaxm3` `ollama:minimax-m3:cloud` ok=True verdict=pass score=100 actual=minimax-m3
  summary: All 10 original requirements are satisfied for the scoped local/offline NATS substrate slice. Retry semantics are state-machine driven via :retry:<uuid> side-effect keys with explicit retry_blocked state; regression tests cover all six required failure modes; canonical envelope contract (dharma.nats.envelope.v1) is implemented end to end with message_id, full causality tuple, actors, subject, payload, and Nats-Msg-Id; durable topology (DS_TASKS, DS_DLQ) and MaxDeliver exhaustion with operator-vi
- `nemotron3ultra` `openrouter_free:nvidia/nemotron-3-ultra-550b-a55b:free` ok=True verdict=approve score=100 actual=nvidia/nemotron-3-super-120b-a12b-20230311:free
  summary: All ten original requirements for the scoped local/offline NATS substrate hardening slice are satisfied by the provided evidence.

## Persistent Agent

- `palantir-pilot` status=running fresh=True
