# Decorrelated Review Council

conviction_gate: **hold_blockers**
target_score: 100
critics: 6 required=6
score_min: 0
score_avg: 16.67

## Blockers

- glm52: RuntimeError Ollama cloud error after 1 attempts: 429: {"error":"you (johnvincentshrader) have reached your session usage limit, add extra usage: https://ollama.com/settings (ref: 25c25f2c-be85-42f7-81f1-e73086db4e15)"}

- glm52: disagreement=Ollama cloud error after 1 attempts: 429: {"error":"you (johnvincentshrader) have reached your session usage limit, add extra usage: https://ollama.com/settings (ref: 25c25f2c-be85-42f7-81f1-e73086db4e15)"}

- kimi27code: RuntimeError Ollama cloud error after 1 attempts: 429: {"error":"you (johnvincentshrader) have reached your session usage limit, add extra usage: https://ollama.com/settings (ref: 627ef1a8-0f86-4fda-b2ba-77c32f8c3ef9)"}

- kimi27code: disagreement=Ollama cloud error after 1 attempts: 429: {"error":"you (johnvincentshrader) have reached your session usage limit, add extra usage: https://ollama.com/settings (ref: 627ef1a8-0f86-4fda-b2ba-77c32f8c3ef9)"}

- qwen3coder: RuntimeError Ollama cloud error after 5 attempts: 429: {"error":"you (johnvincentshrader) have reached your session usage limit, add extra usage: https://ollama.com/settings (ref: 45234dd2-765a-4f2e-b657-a42f1e6a8a77)"}

- qwen3coder: disagreement=Ollama cloud error after 5 attempts: 429: {"error":"you (johnvincentshrader) have reached your session usage limit, add extra usage: https://ollama.com/settings (ref: 45234dd2-765a-4f2e-b657-a42f1e6a8a77)"}

- deepseekv4pro: RuntimeError Ollama cloud error after 1 attempts: 429: {"error":"you (johnvincentshrader) have reached your session usage limit, add extra usage: https://ollama.com/settings (ref: 7bbd1a1d-6efe-490d-bfc1-37395077ebce)"}

- deepseekv4pro: disagreement=Ollama cloud error after 1 attempts: 429: {"error":"you (johnvincentshrader) have reached your session usage limit, add extra usage: https://ollama.com/settings (ref: 7bbd1a1d-6efe-490d-bfc1-37395077ebce)"}

- minimaxm3: RuntimeError Ollama cloud error after 1 attempts: 429: {"error":"you (johnvincentshrader) have reached your session usage limit, add extra usage: https://ollama.com/settings (ref: a2791861-74e2-4bdd-81f9-154aa3fd8737)"}

- minimaxm3: disagreement=Ollama cloud error after 1 attempts: 429: {"error":"you (johnvincentshrader) have reached your session usage limit, add extra usage: https://ollama.com/settings (ref: a2791861-74e2-4bdd-81f9-154aa3fd8737)"}


## Critics

- `glm52` `ollama:glm-5.2:cloud` ok=False verdict=blocked score=0 actual=-
  summary: glm52 could not run.
  blocker: Ollama cloud error after 1 attempts: 429: {"error":"you (johnvincentshrader) have reached your session usage limit, add extra usage: https://ollama.com/settings (ref: 25c25f2c-be85-42f7-81f1-e73086db4e15)"}

- `kimi27code` `ollama:kimi-k2.7-code:cloud` ok=False verdict=blocked score=0 actual=-
  summary: kimi27code could not run.
  blocker: Ollama cloud error after 1 attempts: 429: {"error":"you (johnvincentshrader) have reached your session usage limit, add extra usage: https://ollama.com/settings (ref: 627ef1a8-0f86-4fda-b2ba-77c32f8c3ef9)"}

- `qwen3coder` `ollama:qwen3-coder:480b-cloud` ok=False verdict=blocked score=0 actual=-
  summary: qwen3coder could not run.
  blocker: Ollama cloud error after 5 attempts: 429: {"error":"you (johnvincentshrader) have reached your session usage limit, add extra usage: https://ollama.com/settings (ref: 45234dd2-765a-4f2e-b657-a42f1e6a8a77)"}

- `deepseekv4pro` `ollama:deepseek-v4-pro:cloud` ok=False verdict=blocked score=0 actual=-
  summary: deepseekv4pro could not run.
  blocker: Ollama cloud error after 1 attempts: 429: {"error":"you (johnvincentshrader) have reached your session usage limit, add extra usage: https://ollama.com/settings (ref: 7bbd1a1d-6efe-490d-bfc1-37395077ebce)"}

- `minimaxm3` `ollama:minimax-m3:cloud` ok=False verdict=blocked score=0 actual=-
  summary: minimaxm3 could not run.
  blocker: Ollama cloud error after 1 attempts: 429: {"error":"you (johnvincentshrader) have reached your session usage limit, add extra usage: https://ollama.com/settings (ref: a2791861-74e2-4bdd-81f9-154aa3fd8737)"}

- `nemotron3ultra` `openrouter_free:nvidia/nemotron-3-ultra-550b-a55b:free` ok=True verdict=pass score=100 actual=nvidia/nemotron-3-ultra-550b-a55b-20260604:free
  summary: All 12 required live matrix rows pass with fresh evidence (generated 2026-06-30T23:42:50Z, within 24h). Live NATS/JetStream broker at nats://127.0.0.1:4222 verified with DS_TASKS/DS_DLQ topology, explicit-ack durable consumer a2a_task_handler (max_deliver=3, ack_wait=60s). Canonical envelope dharma.nats.envelope.v1 with stable Nats-Msg-Id, identity/causality headers (Dharma-Trace-Id, Dharma-Causation-Id, Dharma-Correlation-Id, Dharma-Idempotency-Key), typed payload dharma.a2a.nats_task.v1. Live 

## Persistent Agent

- `palantir-pilot` status=running fresh=True
