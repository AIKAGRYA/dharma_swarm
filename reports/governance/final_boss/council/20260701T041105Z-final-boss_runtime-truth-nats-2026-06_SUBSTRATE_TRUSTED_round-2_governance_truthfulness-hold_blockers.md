# Decorrelated Review Council

conviction_gate: **hold_blockers**
target_score: 100
critics: 6 required=6
score_min: 0
score_avg: 0.0

## Blockers

- glm52: RuntimeError Ollama cloud error after 1 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 2a4e5e67-e7e5-44f2-ab94-01f9879701bc)"}

- glm52: disagreement=Ollama cloud error after 1 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 2a4e5e67-e7e5-44f2-ab94-01f9879701bc)"}

- kimi27code: RuntimeError Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 3a69ac42-f2c7-4947-a3d1-3ad462409a40)"}

- kimi27code: disagreement=Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 3a69ac42-f2c7-4947-a3d1-3ad462409a40)"}

- qwen3coder: RuntimeError Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 2583df96-4367-47ee-aae0-9b48ccb936fd)"}

- qwen3coder: disagreement=Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 2583df96-4367-47ee-aae0-9b48ccb936fd)"}

- deepseekv4pro: RuntimeError Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 435e641a-c782-4a0c-9d26-60229e51ed97)"}

- deepseekv4pro: disagreement=Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 435e641a-c782-4a0c-9d26-60229e51ed97)"}

- minimaxm3: RuntimeError Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 11c03a5f-24c6-4381-bfe5-0b927369b357)"}

- minimaxm3: disagreement=Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 11c03a5f-24c6-4381-bfe5-0b927369b357)"}

- nemotron3ultra: verdict=reject
- nemotron3ultra: disagreement=The track honestly claims VERIFIED_SLICE with explicit non-claims about production readiness. The review target requests SUBSTRATE_TRUSTED assessment, but the track itself explicitly disclaims this closure kind. Governance truthfulness requ

## Critics

- `glm52` `ollama:glm-5.2:cloud` ok=False verdict=blocked score=0 actual=-
  summary: glm52 could not run.
  blocker: Ollama cloud error after 1 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 2a4e5e67-e7e5-44f2-ab94-01f9879701bc)"}

- `kimi27code` `ollama:kimi-k2.7-code:cloud` ok=False verdict=blocked score=0 actual=-
  summary: kimi27code could not run.
  blocker: Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 3a69ac42-f2c7-4947-a3d1-3ad462409a40)"}

- `qwen3coder` `ollama:qwen3-coder:480b-cloud` ok=False verdict=blocked score=0 actual=-
  summary: qwen3coder could not run.
  blocker: Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 2583df96-4367-47ee-aae0-9b48ccb936fd)"}

- `deepseekv4pro` `ollama:deepseek-v4-pro:cloud` ok=False verdict=blocked score=0 actual=-
  summary: deepseekv4pro could not run.
  blocker: Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 435e641a-c782-4a0c-9d26-60229e51ed97)"}

- `minimaxm3` `ollama:minimax-m3:cloud` ok=False verdict=blocked score=0 actual=-
  summary: minimaxm3 could not run.
  blocker: Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 11c03a5f-24c6-4381-bfe5-0b927369b357)"}

- `nemotron3ultra` `openrouter_free:nvidia/nemotron-3-ultra-550b-a55b:free` ok=True verdict=reject score=0 actual=nvidia/nemotron-3-ultra-550b-a55b-20260604:free
  summary: The track runtime-truth-nats-2026-06 explicitly closes as VERIFIED_SLICE with an explicit non-claim: 'this is still not a production live-readiness or SUBSTRATE_TRUSTED NATS claim.' The evidence consists entirely of mock-based tests (_FakeJetStream, _FakeMessage) with zero real broker E2E testing. For a SUBSTRATE_TRUSTED claim under the runtime_transport profile, this triggers hard rejects: 'mock-only or fake-only evidence for a production/substrate transport claim' and 'real broker, reconnect, 
  blocker: Mock-only evidence (_FakeJetStream, _FakeMessage) for a SUBSTRATE_TRUSTED transport claim violates hard reject: 'mock-only or fake-only evidence for a production/substrate transport claim'
  blocker: No real broker E2E testing — required failure mode real_broker_e2e completely unproven
  blocker: No reconnect/degradation testing — required failure mode reconnect_or_degradation completely unproven
  blocker: Track explicitly disclaims SUBSTRATE_TRUSTED in closeout receipt and ACTIVE_TRACK.yaml notes
  blocker: Receipt durability only tested against mock RuntimeStateStore, not real broker persistence

## Persistent Agent

- `palantir-pilot` status=running fresh=True
