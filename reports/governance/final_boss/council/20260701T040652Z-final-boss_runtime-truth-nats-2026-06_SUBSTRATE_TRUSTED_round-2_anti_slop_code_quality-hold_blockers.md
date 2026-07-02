# Decorrelated Review Council

conviction_gate: **hold_blockers**
target_score: 100
critics: 6 required=6
score_min: 0
score_avg: 2.5

## Blockers

- glm52: RuntimeError Ollama cloud error after 1 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: f62ecf2a-5d40-4b77-bf6c-383337e1fb72)"}

- glm52: disagreement=Ollama cloud error after 1 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: f62ecf2a-5d40-4b77-bf6c-383337e1fb72)"}

- kimi27code: RuntimeError Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: ff7cdd84-72ce-4b92-9d8c-bbd2af105a51)"}

- kimi27code: disagreement=Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: ff7cdd84-72ce-4b92-9d8c-bbd2af105a51)"}

- qwen3coder: RuntimeError Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 0f85444f-e0ea-474e-9ebb-18096f999ad1)"}

- qwen3coder: disagreement=Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 0f85444f-e0ea-474e-9ebb-18096f999ad1)"}

- deepseekv4pro: RuntimeError Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: cd59652e-69e8-4c76-9855-c48703a2e34c)"}

- deepseekv4pro: disagreement=Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: cd59652e-69e8-4c76-9855-c48703a2e34c)"}

- minimaxm3: RuntimeError Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 3d9085ef-5c99-4adc-8396-310cedaa3643)"}

- minimaxm3: disagreement=Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 3d9085ef-5c99-4adc-8396-310cedaa3643)"}

- nemotron3ultra: verdict=reject
- nemotron3ultra: disagreement=Track claims SUBSTRATE_TRUSTED in dossier target_closure_kind but is closed as VERIFIED_SLICE with explicit disclaimer. This is a governance truthfulness violation — the target claim contradicts the actual closure evidence.

## Critics

- `glm52` `ollama:glm-5.2:cloud` ok=False verdict=blocked score=0 actual=-
  summary: glm52 could not run.
  blocker: Ollama cloud error after 1 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: f62ecf2a-5d40-4b77-bf6c-383337e1fb72)"}

- `kimi27code` `ollama:kimi-k2.7-code:cloud` ok=False verdict=blocked score=0 actual=-
  summary: kimi27code could not run.
  blocker: Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: ff7cdd84-72ce-4b92-9d8c-bbd2af105a51)"}

- `qwen3coder` `ollama:qwen3-coder:480b-cloud` ok=False verdict=blocked score=0 actual=-
  summary: qwen3coder could not run.
  blocker: Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 0f85444f-e0ea-474e-9ebb-18096f999ad1)"}

- `deepseekv4pro` `ollama:deepseek-v4-pro:cloud` ok=False verdict=blocked score=0 actual=-
  summary: deepseekv4pro could not run.
  blocker: Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: cd59652e-69e8-4c76-9855-c48703a2e34c)"}

- `minimaxm3` `ollama:minimax-m3:cloud` ok=False verdict=blocked score=0 actual=-
  summary: minimaxm3 could not run.
  blocker: Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 3d9085ef-5c99-4adc-8396-310cedaa3643)"}

- `nemotron3ultra` `openrouter_free:nvidia/nemotron-3-ultra-550b-a55b:free` ok=True verdict=reject score=15 actual=nvidia/nemotron-3-ultra-550b-a55b-20260604:free
  summary: The track is closed as VERIFIED_SLICE and explicitly disclaims SUBSTRATE_TRUSTED. All test evidence is mock-only (_FakeJetStream, _FakeMessage, _InspectingAckMessage). No real broker e2e, reconnect, or degradation evidence exists. Hard reject: mock-only evidence for substrate transport claim.
  blocker: mock-only test evidence (_FakeJetStream, _FakeMessage) for SUBSTRATE_TRUSTED claim
  blocker: no real broker e2e test (required failure mode: real_broker_e2e)
  blocker: no reconnect/degradation test (required failure mode: reconnect_or_degradation)
  blocker: track itself notes: 'closure_kind is VERIFIED_SLICE: this is still not a production live-readiness or SUBSTRATE_TRUSTED NATS claim'
  blocker: test_nats_substrate_contract.py is a tautology (asserts checker returns 0)

## Persistent Agent

- `palantir-pilot` status=running fresh=True
