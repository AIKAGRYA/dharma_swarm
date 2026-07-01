# Decorrelated Review Council

conviction_gate: **hold_blockers**
target_score: 100
critics: 6 required=6
score_min: 0
score_avg: 0.0

## Blockers

- glm52: RuntimeError Ollama cloud error after 1 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 688c08ff-f3a2-43f7-903d-c54dbc0cb034)"}

- glm52: disagreement=Ollama cloud error after 1 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 688c08ff-f3a2-43f7-903d-c54dbc0cb034)"}

- kimi27code: RuntimeError Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: c1b4dc10-b567-4b37-9bbc-54ea2c55cc99)"}

- kimi27code: disagreement=Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: c1b4dc10-b567-4b37-9bbc-54ea2c55cc99)"}

- qwen3coder: RuntimeError Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: bd15b78a-1fa6-4d2c-9579-85610142a465)"}

- qwen3coder: disagreement=Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: bd15b78a-1fa6-4d2c-9579-85610142a465)"}

- deepseekv4pro: RuntimeError Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: f3b4142e-2903-4bd2-a573-6dce8219c945)"}

- deepseekv4pro: disagreement=Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: f3b4142e-2903-4bd2-a573-6dce8219c945)"}

- minimaxm3: RuntimeError Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 0b6dfa27-8d29-464b-9179-744a63d24b49)"}

- minimaxm3: disagreement=Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 0b6dfa27-8d29-464b-9179-744a63d24b49)"}

- nemotron3ultra: verdict=reject
- nemotron3ultra: disagreement=The track's own closeout receipt and governance docs explicitly classify this as VERIFIED_SLICE, not SUBSTRATE_TRUSTED. Pursuing SUBSTRATE_TRUSTED with the current mock-only evidence contradicts the project's own documented position and the

## Critics

- `glm52` `ollama:glm-5.2:cloud` ok=False verdict=blocked score=0 actual=-
  summary: glm52 could not run.
  blocker: Ollama cloud error after 1 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 688c08ff-f3a2-43f7-903d-c54dbc0cb034)"}

- `kimi27code` `ollama:kimi-k2.7-code:cloud` ok=False verdict=blocked score=0 actual=-
  summary: kimi27code could not run.
  blocker: Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: c1b4dc10-b567-4b37-9bbc-54ea2c55cc99)"}

- `qwen3coder` `ollama:qwen3-coder:480b-cloud` ok=False verdict=blocked score=0 actual=-
  summary: qwen3coder could not run.
  blocker: Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: bd15b78a-1fa6-4d2c-9579-85610142a465)"}

- `deepseekv4pro` `ollama:deepseek-v4-pro:cloud` ok=False verdict=blocked score=0 actual=-
  summary: deepseekv4pro could not run.
  blocker: Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: f3b4142e-2903-4bd2-a573-6dce8219c945)"}

- `minimaxm3` `ollama:minimax-m3:cloud` ok=False verdict=blocked score=0 actual=-
  summary: minimaxm3 could not run.
  blocker: Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 0b6dfa27-8d29-464b-9179-744a63d24b49)"}

- `nemotron3ultra` `openrouter_free:nvidia/nemotron-3-ultra-550b-a55b:free` ok=True verdict=reject score=0 actual=nvidia/nemotron-3-ultra-550b-a55b-20260604:free
  summary: The track's test evidence is entirely mock-based (hand-rolled _FakeJetStream, _FakeMessage, _InspectingAckMessage). No real NATS broker behavior is exercised. The track is currently closed as VERIFIED_SLICE with explicit note 'This is not a production-live NATS substrate claim.' Targeting SUBSTRATE_TRUSTED with mock-only evidence violates the runtime_transport profile's hard rejects: 'mock-only or fake-only evidence for a production/substrate transport claim' and 'real broker, reconnect, degrada
  blocker: All transport tests use hand-rolled fakes (_FakeJetStream, _FakeMessage) — zero real broker connection
  blocker: No evidence of real broker E2E, reconnect, degradation, or cross-host behavior
  blocker: Track explicitly closed as VERIFIED_SLICE with note 'not a production-live NATS substrate claim'
  blocker: SUBSTRATE_TRUSTED target requires production/substrate evidence; mock-only fails hard reject

## Persistent Agent

- `palantir-pilot` status=running fresh=True
