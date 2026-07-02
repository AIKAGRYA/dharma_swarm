# Decorrelated Review Council

conviction_gate: **hold_blockers**
target_score: 100
critics: 6 required=6
score_min: 0
score_avg: 50.0

## Blockers

- groqqwen: APIStatusError Error code: 413 - {'error': {'message': 'Request too large for model `qwen/qwen3-32b` in organization `org_01kmg5twh6f83byc0j3pnj7c8m` service tier `on_demand` on tokens per minute (TPM): Limit 6000, Requested 31357, please reduce your message size and try again. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- groqqwen: disagreement=Error code: 413 - {'error': {'message': 'Request too large for model `qwen/qwen3-32b` in organization `org_01kmg5twh6f83byc0j3pnj7c8m` service tier `on_demand` on tokens per minute (TPM): Limit 6000, Requested 31357, please reduce your mess
- groqllama: APIStatusError Error code: 413 - {'error': {'message': 'Request too large for model `llama-3.3-70b-versatile` in organization `org_01kmg5twh6f83byc0j3pnj7c8m` service tier `on_demand` on tokens per minute (TPM): Limit 12000, Requested 28093, please reduce your message size and try again. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- groqllama: disagreement=Error code: 413 - {'error': {'message': 'Request too large for model `llama-3.3-70b-versatile` in organization `org_01kmg5twh6f83byc0j3pnj7c8m` service tier `on_demand` on tokens per minute (TPM): Limit 12000, Requested 28093, please reduce
- groqgptoss: APIStatusError Error code: 413 - {'error': {'message': 'Request too large for model `openai/gpt-oss-120b` in organization `org_01kmg5twh6f83byc0j3pnj7c8m` service tier `on_demand` on tokens per minute (TPM): Limit 8000, Requested 28305, please reduce your message size and try again. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- groqgptoss: disagreement=Error code: 413 - {'error': {'message': 'Request too large for model `openai/gpt-oss-120b` in organization `org_01kmg5twh6f83byc0j3pnj7c8m` service tier `on_demand` on tokens per minute (TPM): Limit 8000, Requested 28305, please reduce your

## Critics

- `nemotron3ultra` `openrouter_free:nvidia/nemotron-3-ultra-550b-a55b:free` ok=True verdict=pass score=100 actual=nvidia/nemotron-3-ultra-550b-a55b-20260604:free
  summary: All 12 required live matrix rows pass against fresh local JetStream broker (generated 2026-06-30T23:42:50Z, within 24h). Topology shows DS_TASKS/DS_DLQ streams, explicit-ack durable consumer a2a_task_handler with max_deliver=3. Happy path proves canonical envelope (dharma.nats.envelope.v1), stable Nats-Msg-Id, identity/causality headers, typed payload (dharma.a2a.nats_task.v1), live publish via A2ANatsTransport.publish_task, model-backed semantic receipt (glm-5.2:cloud), and handler ack. Failure
- `nimllama` `nvidia_nim:meta/llama-3.3-70b-instruct` ok=True verdict=pass score=100 actual=meta/llama-3.3-70b-instruct
  summary: The provided evidence proves end-to-end readiness for the scoped live broker profile.
- `nimdeepseekv4` `nvidia_nim:deepseek-ai/deepseek-v4-pro` ok=True verdict=approve score=100 actual=deepseek-ai/deepseek-v4-pro
  summary: All 12 required live matrix rows pass with fresh evidence (2026-06-30T23:42:50Z, within 24h). Topology confirms DS_TASKS/DS_DLQ streams, explicit ack consumer a2a_task_handler with max_deliver=3. Happy path proves canonical dharma.nats.envelope.v1, Nats-Msg-Id, identity/causality headers, typed payload, live model-backed semantic receipt, and broker ack. Handler failure nacks and redelivers successfully. Stale/concurrent idempotency paths correctly retry or block/nack. Ack failure surfaces truth
- `groqqwen` `groq:qwen/qwen3-32b` ok=False verdict=blocked score=0 actual=-
  summary: groqqwen could not run.
  blocker: Error code: 413 - {'error': {'message': 'Request too large for model `qwen/qwen3-32b` in organization `org_01kmg5twh6f83byc0j3pnj7c8m` service tier `on_demand` on tokens per minute (TPM): Limit 6000, Requested 31357, please reduce your message size and try again. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- `groqllama` `groq:llama-3.3-70b-versatile` ok=False verdict=blocked score=0 actual=-
  summary: groqllama could not run.
  blocker: Error code: 413 - {'error': {'message': 'Request too large for model `llama-3.3-70b-versatile` in organization `org_01kmg5twh6f83byc0j3pnj7c8m` service tier `on_demand` on tokens per minute (TPM): Limit 12000, Requested 28093, please reduce your message size and try again. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- `groqgptoss` `groq:openai/gpt-oss-120b` ok=False verdict=blocked score=0 actual=-
  summary: groqgptoss could not run.
  blocker: Error code: 413 - {'error': {'message': 'Request too large for model `openai/gpt-oss-120b` in organization `org_01kmg5twh6f83byc0j3pnj7c8m` service tier `on_demand` on tokens per minute (TPM): Limit 8000, Requested 28305, please reduce your message size and try again. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}

## Persistent Agent

- `palantir-pilot` status=running fresh=True
