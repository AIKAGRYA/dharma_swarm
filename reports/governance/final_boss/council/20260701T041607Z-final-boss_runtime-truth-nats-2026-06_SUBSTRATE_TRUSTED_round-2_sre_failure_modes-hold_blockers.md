# Decorrelated Review Council

conviction_gate: **hold_blockers**
target_score: 100
critics: 6 required=6
score_min: 0
score_avg: 0.0

## Blockers

- glm52: RuntimeError Ollama cloud error after 1 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: d3526f28-b8b6-495f-9db0-51be01f59403)"}

- glm52: disagreement=Ollama cloud error after 1 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: d3526f28-b8b6-495f-9db0-51be01f59403)"}

- kimi27code: RuntimeError Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 1a339162-90fe-4104-a798-582ed7dd22a3)"}

- kimi27code: disagreement=Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 1a339162-90fe-4104-a798-582ed7dd22a3)"}

- qwen3coder: RuntimeError Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 70424750-3f68-4c5d-abd4-5988e1a048a0)"}

- qwen3coder: disagreement=Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 70424750-3f68-4c5d-abd4-5988e1a048a0)"}

- deepseekv4pro: RuntimeError Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: fa1ec0df-36c1-4a33-88db-ee32c56c5b47)"}

- deepseekv4pro: disagreement=Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: fa1ec0df-36c1-4a33-88db-ee32c56c5b47)"}

- minimaxm3: RuntimeError Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 7ada5103-b650-4ad5-b9c0-93598ef12096)"}

- minimaxm3: disagreement=Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 7ada5103-b650-4ad5-b9c0-93598ef12096)"}

- nemotron3ultra: verdict=reject
- nemotron3ultra: disagreement=The dossier requests SUBSTRATE_TRUSTED review but the track's own governance records show it was closed as VERIFIED_SLICE with explicit disclaimer that it is NOT a SUBSTRATE_TRUSTED claim. Reviewing for SUBSTRATE_TRUSTED against mock-only e

## Critics

- `glm52` `ollama:glm-5.2:cloud` ok=False verdict=blocked score=0 actual=-
  summary: glm52 could not run.
  blocker: Ollama cloud error after 1 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: d3526f28-b8b6-495f-9db0-51be01f59403)"}

- `kimi27code` `ollama:kimi-k2.7-code:cloud` ok=False verdict=blocked score=0 actual=-
  summary: kimi27code could not run.
  blocker: Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 1a339162-90fe-4104-a798-582ed7dd22a3)"}

- `qwen3coder` `ollama:qwen3-coder:480b-cloud` ok=False verdict=blocked score=0 actual=-
  summary: qwen3coder could not run.
  blocker: Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 70424750-3f68-4c5d-abd4-5988e1a048a0)"}

- `deepseekv4pro` `ollama:deepseek-v4-pro:cloud` ok=False verdict=blocked score=0 actual=-
  summary: deepseekv4pro could not run.
  blocker: Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: fa1ec0df-36c1-4a33-88db-ee32c56c5b47)"}

- `minimaxm3` `ollama:minimax-m3:cloud` ok=False verdict=blocked score=0 actual=-
  summary: minimaxm3 could not run.
  blocker: Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 7ada5103-b650-4ad5-b9c0-93598ef12096)"}

- `nemotron3ultra` `openrouter_free:nvidia/nemotron-3-ultra-550b-a55b:free` ok=True verdict=reject score=0 actual=nvidia/nemotron-3-ultra-550b-a55b-20260604:free
  summary: The track claims SUBSTRATE_TRUSTED but provides only mock/fake evidence. Hard reject triggered: 'real broker, reconnect, degradation, or cross-host behavior is unproven while claiming substrate trust'. Tests use _FakeJetStream, _FakeMessage, _InspectingAckMessage — no real NATS broker exercised. Required failure modes real_broker_e2e and reconnect_or_degradation have zero evidence. The track's own closeout receipt explicitly states 'this is still not a production live-readiness or SUBSTRATE_TRUS
  blocker: Hard reject: mock-only evidence for SUBSTRATE_TRUSTED claim (runtime_transport profile requires real broker behavior)
  blocker: Hard reject: real_broker_e2e failure mode untested — only fake JetStream used
  blocker: Hard reject: reconnect_or_degradation failure mode untested — no reconnect, degradation, or cross-host behavior exercised
  blocker: Track's own closeout receipt explicitly disclaims SUBSTRATE_TRUSTED: 'closure_kind is VERIFIED_SLICE: this is still not a production live-readiness or SUBSTRATE_TRUSTED NATS claim.'

## Persistent Agent

- `palantir-pilot` status=running fresh=True
