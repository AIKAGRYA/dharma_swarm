# Decorrelated Review Council

conviction_gate: **hold_blockers**
target_score: 100
critics: 6 required=6
score_min: 0
score_avg: 5.83

## Blockers

- glm52: RuntimeError Ollama cloud error after 1 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 2eee6b55-91e8-46db-b73d-9d568850e3a7)"}

- glm52: disagreement=Ollama cloud error after 1 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 2eee6b55-91e8-46db-b73d-9d568850e3a7)"}

- kimi27code: RuntimeError Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: cfdb92b7-bdf1-4e9b-acc3-79d032076193)"}

- kimi27code: disagreement=Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: cfdb92b7-bdf1-4e9b-acc3-79d032076193)"}

- qwen3coder: RuntimeError Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 30efc777-68a2-401a-9794-40dc107da279)"}

- qwen3coder: disagreement=Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 30efc777-68a2-401a-9794-40dc107da279)"}

- deepseekv4pro: RuntimeError Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 48b39075-480e-439d-b270-00d8131360da)"}

- deepseekv4pro: disagreement=Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 48b39075-480e-439d-b270-00d8131360da)"}

- minimaxm3: RuntimeError Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 9b96f774-d0c6-4d1f-8fe5-ede53837fca4)"}

- minimaxm3: disagreement=Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 9b96f774-d0c6-4d1f-8fe5-ede53837fca4)"}

- nemotron3ultra: verdict=reject
- nemotron3ultra: disagreement=The dossier targets SUBSTRATE_TRUSTED but the track is closed as VERIFIED_SLICE with explicit acknowledgment that it lacks production/substrate evidence. This review cannot pass a dimension when the track's own governance record contradicts

## Critics

- `glm52` `ollama:glm-5.2:cloud` ok=False verdict=blocked score=0 actual=-
  summary: glm52 could not run.
  blocker: Ollama cloud error after 1 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 2eee6b55-91e8-46db-b73d-9d568850e3a7)"}

- `kimi27code` `ollama:kimi-k2.7-code:cloud` ok=False verdict=blocked score=0 actual=-
  summary: kimi27code could not run.
  blocker: Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: cfdb92b7-bdf1-4e9b-acc3-79d032076193)"}

- `qwen3coder` `ollama:qwen3-coder:480b-cloud` ok=False verdict=blocked score=0 actual=-
  summary: qwen3coder could not run.
  blocker: Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 30efc777-68a2-401a-9794-40dc107da279)"}

- `deepseekv4pro` `ollama:deepseek-v4-pro:cloud` ok=False verdict=blocked score=0 actual=-
  summary: deepseekv4pro could not run.
  blocker: Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 48b39075-480e-439d-b270-00d8131360da)"}

- `minimaxm3` `ollama:minimax-m3:cloud` ok=False verdict=blocked score=0 actual=-
  summary: minimaxm3 could not run.
  blocker: Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 9b96f774-d0c6-4d1f-8fe5-ede53837fca4)"}

- `nemotron3ultra` `openrouter_free:nvidia/nemotron-3-ultra-550b-a55b:free` ok=True verdict=reject score=35 actual=nvidia/nemotron-3-ultra-550b-a55b-20260604:free
  summary: The track claims SUBSTRATE_TRUSTED but evidence consists entirely of mock-based tests (_FakeJetStream, _FakeMessage). No real broker e2e, reconnect, degradation, or cross-host behavior is exercised. The track's own closeout notes explicitly state 'this is still not a production live-readiness or SUBSTRATE_TRUSTED NATS claim.' Future maintainers cannot safely extend/debug without reconstructing hidden context about real NATS semantics.
  blocker: mock-only evidence for SUBSTRATE_TRUSTED transport claim (hard reject per profile)
  blocker: real_broker_e2e failure mode untested - all tests use _FakeJetStream
  blocker: reconnect_or_degradation failure mode untested - no network partition, broker restart, or slow consumer tests
  blocker: cross-host behavior unproven - single-process fake transport only
  blocker: track's own closeout notes contradict SUBSTRATE_TRUSTED claim

## Persistent Agent

- `palantir-pilot` status=running fresh=True
