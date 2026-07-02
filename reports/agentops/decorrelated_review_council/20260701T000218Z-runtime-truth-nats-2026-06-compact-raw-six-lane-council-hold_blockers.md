# Decorrelated Review Council

conviction_gate: **hold_blockers**
target_score: 100
critics: 6 required=6
score_min: 0
score_avg: 66.67

## Blockers

- nemotron3ultra: CriticResponseError invalid critic JSON from openrouter_free:nvidia/nemotron-3-ultra-550b-a55b:free; actual_model=nvidia/nemotron-3-super-120b-a12b-20230311:free; content_len=12022; parse_error=JSONDecodeError: Extra data: line 6 column 6 (char 167); preview=We are given a JSON evidence file. We must review it for production-grade integration quality, anti-AI-slop, governance truthfulness, and code assurance.\n We are to return a JSON object with the specified structure.\n\n Steps:\n 1. Check if the evid ... urce: "reports/governance/nats_live_production_matrix/latest.json"). \n    We assume that the report is generated from the current codebase.\n\n 5. We must check for any signs of simulation without disclosure. \n    The evidence uses forced errors (e
- nemotron3ultra: disagreement=invalid critic JSON from openrouter_free:nvidia/nemotron-3-ultra-550b-a55b:free; actual_model=nvidia/nemotron-3-super-120b-a12b-20230311:free; content_len=12022; parse_error=JSONDecodeError: Extra data: line 6 column 6 (char 167); preview=W
- groqqwen: APIStatusError Error code: 413 - {'error': {'message': 'Request too large for model `qwen/qwen3-32b` in organization `org_01kmg5twh6f83byc0j3pnj7c8m` service tier `on_demand` on tokens per minute (TPM): Limit 6000, Requested 9852, please reduce your message size and try again. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- groqqwen: disagreement=Error code: 413 - {'error': {'message': 'Request too large for model `qwen/qwen3-32b` in organization `org_01kmg5twh6f83byc0j3pnj7c8m` service tier `on_demand` on tokens per minute (TPM): Limit 6000, Requested 9852, please reduce your messa

## Critics

- `nemotron3ultra` `openrouter_free:nvidia/nemotron-3-ultra-550b-a55b:free` ok=False verdict=blocked score=0 actual=nvidia/nemotron-3-super-120b-a12b-20230311:free
  summary: nemotron3ultra could not run.
  blocker: invalid critic JSON from openrouter_free:nvidia/nemotron-3-ultra-550b-a55b:free; actual_model=nvidia/nemotron-3-super-120b-a12b-20230311:free; content_len=12022; parse_error=JSONDecodeError: Extra data: line 6 column 6 (char 167); preview=We are given a JSON evidence file. We must review it for production-grade integration quality, anti-AI-slop, governance truthfulness, and code assurance.\n We are to return a JSON object with the specified structure.\n\n Steps:\n 1. Check if the evid ... urce: 
- `nimllama` `nvidia_nim:meta/llama-3.3-70b-instruct` ok=True verdict=pass score=100 actual=meta/llama-3.3-70b-instruct
  summary: The provided evidence demonstrates end-to-end readiness for the scoped live broker profile.
- `nimdeepseekv4` `nvidia_nim:deepseek-ai/deepseek-v4-pro` ok=True verdict=approve score=100 actual=deepseek-ai/deepseek-v4-pro
  summary: All required production paths are evidenced with live broker data, durable explicit-ack consumer, canonical envelope, idempotency, DLQ, restart, and governance-negative checks. No blockers remain.
- `groqqwen` `groq:qwen/qwen3-32b` ok=False verdict=blocked score=0 actual=-
  summary: groqqwen could not run.
  blocker: Error code: 413 - {'error': {'message': 'Request too large for model `qwen/qwen3-32b` in organization `org_01kmg5twh6f83byc0j3pnj7c8m` service tier `on_demand` on tokens per minute (TPM): Limit 6000, Requested 9852, please reduce your message size and try again. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}
- `groqllama` `groq:llama-3.3-70b-versatile` ok=True verdict=pass score=100 actual=llama-3.3-70b-versatile
  summary: The provided evidence demonstrates end-to-end readiness for the scoped live broker profile.
- `groqgptoss` `groq:openai/gpt-oss-120b` ok=True verdict=pass score=100 actual=openai/gpt-oss-120b
  summary: All required production readiness evidence is present, fresh, and passes validation. Live NATS broker, topology, durable consumer, publish/ack flows, idempotency, duplicate handling, failure injection paths, DLQ behavior, restart recovery, and governance negative test are all demonstrated with concrete timestamps and receipts. No blockers detected.

## Persistent Agent

- `palantir-pilot` status=running fresh=True
