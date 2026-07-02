# Decorrelated Review Council

conviction_gate: **hold_blockers**
target_score: 100
critics: 6 required=6
score_min: 0
score_avg: 0.0

## Blockers

- glm52: RuntimeError Ollama cloud error after 1 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 1148ff54-920d-40e0-ab1a-596ef901d95c)"}

- glm52: disagreement=Ollama cloud error after 1 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 1148ff54-920d-40e0-ab1a-596ef901d95c)"}

- kimi27code: RuntimeError Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: adbec4b5-260b-4911-beab-f36f9f65c98d)"}

- kimi27code: disagreement=Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: adbec4b5-260b-4911-beab-f36f9f65c98d)"}

- qwen3coder: RuntimeError Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 4f74a18c-0859-4baf-b8f6-16256ace98fd)"}

- qwen3coder: disagreement=Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 4f74a18c-0859-4baf-b8f6-16256ace98fd)"}

- deepseekv4pro: RuntimeError Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 6ae4ee6c-d7c5-439a-aee8-07bc6e80b24e)"}

- deepseekv4pro: disagreement=Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 6ae4ee6c-d7c5-439a-aee8-07bc6e80b24e)"}

- minimaxm3: RuntimeError Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 59110cbd-c3f7-47b8-b8b0-1c02d8411b6a)"}

- minimaxm3: disagreement=Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 59110cbd-c3f7-47b8-b8b0-1c02d8411b6a)"}

- nemotron3ultra: verdict=reject
- nemotron3ultra: disagreement=The review target asks for SUBSTRATE_TRUSTED grading, but the track's own closeout receipt and portfolio entry explicitly disclaim SUBSTRATE_TRUSTED. Grading it as SUBSTRATE_TRUSTED would violate governance truthfulness (hard reject: mock-o

## Critics

- `glm52` `ollama:glm-5.2:cloud` ok=False verdict=blocked score=0 actual=-
  summary: glm52 could not run.
  blocker: Ollama cloud error after 1 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 1148ff54-920d-40e0-ab1a-596ef901d95c)"}

- `kimi27code` `ollama:kimi-k2.7-code:cloud` ok=False verdict=blocked score=0 actual=-
  summary: kimi27code could not run.
  blocker: Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: adbec4b5-260b-4911-beab-f36f9f65c98d)"}

- `qwen3coder` `ollama:qwen3-coder:480b-cloud` ok=False verdict=blocked score=0 actual=-
  summary: qwen3coder could not run.
  blocker: Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 4f74a18c-0859-4baf-b8f6-16256ace98fd)"}

- `deepseekv4pro` `ollama:deepseek-v4-pro:cloud` ok=False verdict=blocked score=0 actual=-
  summary: deepseekv4pro could not run.
  blocker: Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 6ae4ee6c-d7c5-439a-aee8-07bc6e80b24e)"}

- `minimaxm3` `ollama:minimax-m3:cloud` ok=False verdict=blocked score=0 actual=-
  summary: minimaxm3 could not run.
  blocker: Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 59110cbd-c3f7-47b8-b8b0-1c02d8411b6a)"}

- `nemotron3ultra` `openrouter_free:nvidia/nemotron-3-ultra-550b-a55b:free` ok=True verdict=reject score=0 actual=nvidia/nemotron-3-ultra-550b-a55b-20260604:free
  summary: The track is closed as VERIFIED_SLICE and explicitly disclaims SUBSTRATE_TRUSTED. The evidence consists entirely of mock/fake tests (_FakeJetStream, _FakeMessage) with zero real broker E2E validation. Hard reject: mock-only evidence for a substrate transport claim; real_broker_e2e and reconnect_or_degradation failure modes are unproven.
  blocker: Hard reject: mock-only evidence for SUBSTRATE_TRUSTED claim (test_nats_transport.py uses only _FakeJetStream/_FakeMessage)
  blocker: Hard reject: real_broker_e2e failure mode unproven — no live NATS broker test evidence exists
  blocker: Hard reject: reconnect_or_degradation failure mode unproven — no cross-host or reconnect behavior exercised
  blocker: Track dossier explicitly states: 'closure_kind is VERIFIED_SLICE: this is still not a production live-readiness or SUBSTRATE_TRUSTED NATS claim'

## Persistent Agent

- `palantir-pilot` status=running fresh=True
