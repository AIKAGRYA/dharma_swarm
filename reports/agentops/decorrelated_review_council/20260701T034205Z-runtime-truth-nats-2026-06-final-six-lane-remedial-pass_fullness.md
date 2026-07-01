# Decorrelated Review Council

conviction_gate: **pass_fullness**
target_score: 100
critics: 6 required=6
score_min: 100
score_avg: 100.0

## Blockers

- none

## Critics

- `glm52` `ollama:glm-5.2:cloud` ok=True verdict=pass score=100 actual=glm-5.2
  summary: All required production-readiness criteria are proven by fresh live evidence: live NATS/JetStream topology (DS_TASKS/DS_DLQ streams, explicit-ack consumer a2a_task_handler, max_deliver=3, duplicate_window=600s), governed A2ANatsTransport.publish_task and A2AServer(require_execution_identity=True) on every row, live model-backed happy-path semantic receipt (ollama:glm-5.2:cloud, response_model glm-5.2, confirmed), ack-after-success, nack/redelivery with num_delivered 1→2, MaxDeliver typed DLQ wit
- `kimi27code` `ollama:kimi-k2.7-code:cloud` ok=True verdict=pass score=100 actual=kimi-k2.7-code
  summary: All required production gates are concretely evidenced: live NATS/JetStream topology with DS_TASKS/DS_DLQ and consumer a2a_task_handler; governed A2ANatsTransport.publish_task / consume_message path; A2AServer with require_execution_identity=True; model-backed happy-path semantic receipt; ack-after-success; nack/redelivery on handler and broker-ack failures; MaxDeliver-typed DLQ with dharma.nats.dlq_failure.v1; DLQ publish-failure visibility; restart recovery after 65s wait; duplicate-window, st
- `qwen3coder` `ollama:qwen3-coder:480b-cloud` ok=True verdict=pass score=100 actual=qwen3-coder:480b-cloud
  summary: All required production readiness criteria verified including live NATS/JetStream topology, governed A2ANatsTransport.publish_task, A2AServer(require_execution_identity=True), live model-backed happy-path handler receipt, ack after success, nack/redelivery, MaxDeliver typed DLQ, DLQ failure visibility, restart recovery, duplicate/idempotency safety, source-tied evidence, and governance/compatibility gates.
- `deepseekv4pro` `ollama:deepseek-v4-pro:cloud` ok=True verdict=pass score=100 actual=deepseek-v4-pro
  summary: All production readiness criteria are met: live NATS/JetStream topology, governed transport, identity enforcement, happy-path handler with model receipt, ack/nack/redelivery, MaxDeliver DLQ, DLQ failure visibility, restart recovery, duplicate/idempotency safety, source-tied evidence, and governance/compatibility gates all pass.
- `minimaxm3` `ollama:minimax-m3:cloud` ok=True verdict=pass score=100 actual=minimax-m3
  summary: Evidence packet meets every required gate for runtime-truth-nats-2026-06 production readiness. Fresh live NATS/JetStream topology is shown via DS_TASKS (subjects dharma.a2a.task.>, file storage, 600s dedup window) and DS_DLQ (subjects dharma.dlq.>) with consumer a2a_task_handler (explicit ack policy, MaxDeliver=3, ack_wait=60s, zero pending). Production path contract on every active matrix row is the governed A2ANatsTransport.publish_task / A2ANatsTransport.consume_message with consumer_class dh
- `nemotron3ultra` `openrouter_free:nvidia/nemotron-3-ultra-550b-a55b:free` ok=True verdict=pass score=100 actual=nvidia/nemotron-3-ultra-550b-a55b-20260604:free
  summary: All production-readiness criteria proven by fresh live NATS/JetStream evidence. Topology shows DS_TASKS/DS_DLQ streams with consumer max_deliver=3, ack_wait=60s, explicit ack policy. Happy path demonstrates live model-backed handler (ollama:glm-5.2:cloud) with semantic receipt, ack after success. Failure paths prove nack/redelivery (handler_failure_redelivery_path), MaxDeliver=3 typed DLQ (max_deliver_path), DLQ failure visibility (dlq_failure_path operator_visible=true), restart recovery after

## Persistent Agent

- `palantir-pilot` status=running fresh=True
