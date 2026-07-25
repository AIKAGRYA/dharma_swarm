# Decorrelated Review Council

conviction_gate: **hold_blockers**
target_score: 100
critics: 6 required=6
score_min: 0
score_avg: 0.0

## Blockers

- glm52: RuntimeError Ollama cloud error after 1 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: a6de0dc9-e5b9-47ff-9885-82a872a93a70)"}

- glm52: disagreement=Ollama cloud error after 1 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: a6de0dc9-e5b9-47ff-9885-82a872a93a70)"}

- kimi27code: RuntimeError Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 8512fd40-8a4d-4002-896e-22f17b58e6a6)"}

- kimi27code: disagreement=Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 8512fd40-8a4d-4002-896e-22f17b58e6a6)"}

- qwen3coder: RuntimeError Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 60ef9b73-e9ad-43a5-9da7-9859938f2da4)"}

- qwen3coder: disagreement=Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 60ef9b73-e9ad-43a5-9da7-9859938f2da4)"}

- deepseekv4pro: RuntimeError Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 990a766d-552d-44ec-9e75-20502ed72b1a)"}

- deepseekv4pro: disagreement=Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 990a766d-552d-44ec-9e75-20502ed72b1a)"}

- minimaxm3: RuntimeError Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: e5680c04-451f-4b18-a774-3aab5fed0f16)"}

- minimaxm3: disagreement=Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: e5680c04-451f-4b18-a774-3aab5fed0f16)"}

- nemotron3ultra: verdict=reject
- nemotron3ultra: disagreement=Track claims VERIFIED_SLICE (honest bounded slice). Review target asks for SUBSTRATE_TRUSTED. These are incompatible per the track's own closeout receipt and the Final Boss gate requirements. No amount of re-review changes the fact that zer

## Critics

- `glm52` `ollama:glm-5.2:cloud` ok=False verdict=blocked score=0 actual=-
  summary: glm52 could not run.
  blocker: Ollama cloud error after 1 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: a6de0dc9-e5b9-47ff-9885-82a872a93a70)"}

- `kimi27code` `ollama:kimi-k2.7-code:cloud` ok=False verdict=blocked score=0 actual=-
  summary: kimi27code could not run.
  blocker: Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 8512fd40-8a4d-4002-896e-22f17b58e6a6)"}

- `qwen3coder` `ollama:qwen3-coder:480b-cloud` ok=False verdict=blocked score=0 actual=-
  summary: qwen3coder could not run.
  blocker: Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 60ef9b73-e9ad-43a5-9da7-9859938f2da4)"}

- `deepseekv4pro` `ollama:deepseek-v4-pro:cloud` ok=False verdict=blocked score=0 actual=-
  summary: deepseekv4pro could not run.
  blocker: Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 990a766d-552d-44ec-9e75-20502ed72b1a)"}

- `minimaxm3` `ollama:minimax-m3:cloud` ok=False verdict=blocked score=0 actual=-
  summary: minimaxm3 could not run.
  blocker: Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: e5680c04-451f-4b18-a774-3aab5fed0f16)"}

- `nemotron3ultra` `openrouter_free:nvidia/nemotron-3-ultra-550b-a55b:free` ok=True verdict=reject score=0 actual=nvidia/nemotron-3-ultra-550b-a55b-20260604:free
  summary: The track is closed as VERIFIED_SLICE and explicitly disclaims SUBSTRATE_TRUSTED. All test evidence uses in-memory fakes (_FakeJetStream, _FakeMessage) with zero real broker E2E exercise. Hard rejects triggered: mock-only evidence for substrate claim; real broker/reconnect/degradation unproven. Required failure modes (real_broker_e2e, reconnect_or_degradation) have no evidence.
  blocker: Hard reject: mock-only evidence (all tests use _FakeJetStream/_FakeMessage) for a SUBSTRATE_TRUSTED transport claim
  blocker: Hard reject: real broker, reconnect, degradation, cross-host behavior unproven while claiming substrate trust
  blocker: Required failure mode 'real_broker_e2e' has zero evidence - no live NATS broker test
  blocker: Required failure mode 'reconnect_or_degradation' has zero evidence - no reconnect/degradation test
  blocker: Track itself declares closure_kind=VERIFIED_SLICE and notes 'this is still not a production live-readiness or SUBSTRATE_TRUSTED NATS claim'

## Persistent Agent

- `palantir-pilot` status=running fresh=True
