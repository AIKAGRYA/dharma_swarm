# Decorrelated Review Council

conviction_gate: **hold_blockers**
target_score: 100
critics: 6 required=6
score_min: 0
score_avg: 83.33

## Blockers

- kimi27code: CriticResponseError invalid critic JSON from ollama:kimi-k2.7-code:cloud; actual_model=kimi-k2.7-code; content_len=55811; parse_error=JSONDecodeError: Expecting ':' delimiter: line 1 column 13 (char 12); preview=We need act as strict JSON-only production review critic. Need return JSON only, no markdown fences, no prose outside JSON. We are lane kimi27code. Review target runtime-truth-nats-2026-06, requested provider/model ollama:kimi-k2.7-code:cloud. We gra ...  #5 and #4 are about the transport/spec. The scripts are not the transport. So maybe all 10 are satisfied for the slice.\n\nThe closeout packet test count inconsistency is still a current evidence issue. But maybe not a functional blocker. The prompt
- kimi27code: disagreement=invalid critic JSON from ollama:kimi-k2.7-code:cloud; actual_model=kimi-k2.7-code; content_len=55811; parse_error=JSONDecodeError: Expecting ':' delimiter: line 1 column 13 (char 12); preview=We need act as strict JSON-only production revie

## Critics

- `glm52` `ollama:glm-5.2:cloud` ok=True verdict=pass score=100 actual=glm-5.2
  summary: All 10 original rejection requirements are satisfied for the explicitly scoped local/offline NATS substrate hardening slice. Idempotency retry semantics are fixed (failed/stale records create retry keys, not duplicate acks). Tests cover all six required failure modes. Canonical envelope dharma.nats.envelope.v1 with message_id, causality, actors, subject, payload, and Nats-Msg-Id is implemented and tested. Durable stream/consumer setup and DLQ behavior with MaxDeliver exhaustion and operator-visi
- `kimi27code` `ollama:kimi-k2.7-code:cloud` ok=False verdict=blocked score=0 actual=kimi-k2.7-code
  summary: kimi27code could not run.
  blocker: invalid critic JSON from ollama:kimi-k2.7-code:cloud; actual_model=kimi-k2.7-code; content_len=55811; parse_error=JSONDecodeError: Expecting ':' delimiter: line 1 column 13 (char 12); preview=We need act as strict JSON-only production review critic. Need return JSON only, no markdown fences, no prose outside JSON. We are lane kimi27code. Review target runtime-truth-nats-2026-06, requested provider/model ollama:kimi-k2.7-code:cloud. We gra ...  #5 and #4 are about the transport/spec. The scripts 
- `qwen3coder` `ollama:qwen3-coder:480b-cloud` ok=True verdict=pass score=100 actual=qwen3-coder:480b-cloud
  summary: The NATS substrate implementation meets all requirements for local/offline hardening. All original rejection items have been addressed through comprehensive idempotency handling, proper envelope contracts, durable stream/consumer setup, DLQ behavior, and executable governance gates. The track remains ACTIVE as required pending operator lifecycle review.
- `deepseekv4pro` `ollama:deepseek-v4-pro:cloud` ok=True verdict=pass score=100 actual=deepseek-v4-pro
  summary: All 10 original rejection requirements are satisfied with concrete evidence: idempotency retry/DLQ, behavioral tests, canonical envelope, durable topology/DLQ, governed transport abstraction, negative contract tests, executable gates, owned surfaces, closeout packet, and explicit local/offline scope. No blockers remain.
- `minimaxm3` `ollama:minimax-m3:cloud` ok=True verdict=approve score=100 actual=minimax-m3
  summary: The local/offline NATS substrate hardening slice now satisfies all 10 original rejection requirements with concrete, verifiable evidence. The transport (dharma_swarm/a2a/nats_transport.py) implements retry-on-failed-stale via :retry:<uuid> side-effect keys, blocks in-progress duplicates with retry_blocked receipts, and publishes typed dharma.nats.dlq_failure.v1 envelopes with operator_blocker=NATS_MAX_DELIVER_EXHAUSTED to dharma.dlq.<stream>.<consumer>. The canonical envelope dharma.nats.envelop
- `nemotron3ultra` `openrouter_free:nvidia/nemotron-3-ultra-550b-a55b:free` ok=True verdict=pass score=100 actual=nvidia/nemotron-3-ultra-550b-a55b-20260604:free
  summary: All 10 original rejection requirements are satisfied for the explicitly scoped local/offline NATS substrate hardening slice. The implementation provides: (1) correct idempotency retry semantics with retry keys for failed/stale records and DLQ visibility; (2) behavioral regression tests covering all 6 required failure modes; (3) canonical envelope dharma.nats.envelope.v1 with message_id, causality fields, actors, subject, payload, and Nats-Msg-Id; (4) durable stream/consumer topology (DS_TASKS, D

## Persistent Agent

- `palantir-pilot` status=running fresh=True
