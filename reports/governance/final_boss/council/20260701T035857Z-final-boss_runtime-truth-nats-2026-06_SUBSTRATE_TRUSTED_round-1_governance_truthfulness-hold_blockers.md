# Decorrelated Review Council

conviction_gate: **hold_blockers**
target_score: 100
critics: 6 required=6
score_min: 0
score_avg: 0.0

## Blockers

- glm52: RuntimeError Ollama cloud error after 1 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 40eea4ba-161e-4085-8cf9-b4f783f08f12)"}

- glm52: disagreement=Ollama cloud error after 1 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 40eea4ba-161e-4085-8cf9-b4f783f08f12)"}

- kimi27code: RuntimeError Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: c4a942c3-bfb5-46bc-a570-eaf48d60dbd4)"}

- kimi27code: disagreement=Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: c4a942c3-bfb5-46bc-a570-eaf48d60dbd4)"}

- qwen3coder: RuntimeError Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 00b3e0fe-c871-4f12-a06e-f56bd6af6d0e)"}

- qwen3coder: disagreement=Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 00b3e0fe-c871-4f12-a06e-f56bd6af6d0e)"}

- deepseekv4pro: RuntimeError Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: b153a618-810f-4693-886b-d4fd7280ddfb)"}

- deepseekv4pro: disagreement=Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: b153a618-810f-4693-886b-d4fd7280ddfb)"}

- minimaxm3: RuntimeError Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 3e112ff4-8566-455c-a562-bfd97104e7b8)"}

- minimaxm3: disagreement=Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 3e112ff4-8566-455c-a562-bfd97104e7b8)"}

- nemotron3ultra: CriticResponseError invalid critic JSON from openrouter_free:nvidia/nemotron-3-ultra-550b-a55b:free; actual_model=nvidia/nemotron-3-ultra-550b-a55b-20260604:free; content_len=2899; parse_error=JSONDecodeError: Invalid control character at: line 17 column 7 (char 1697); preview={\n  "verdict": "reject",\n  "score": 0,\n  "summary": "The track runtime-truth-nats-2026-06 is explicitly closed as VERIFIED_SLICE with a clear note: 'this is still not a production live-readiness or SUBSTRATE_TRUSTED NATS claim.' The review target  ... This is a direct contradiction. Governance truthfulness requires honoring the track's own declared closure kind and non-claims. Claiming SUBSTRATE_TRUSTED here would mislead future agents into treating a verified slice as durable substrate truth."\n}
- nemotron3ultra: disagreement=invalid critic JSON from openrouter_free:nvidia/nemotron-3-ultra-550b-a55b:free; actual_model=nvidia/nemotron-3-ultra-550b-a55b-20260604:free; content_len=2899; parse_error=JSONDecodeError: Invalid control character at: line 17 column 7 (ch

## Critics

- `glm52` `ollama:glm-5.2:cloud` ok=False verdict=blocked score=0 actual=-
  summary: glm52 could not run.
  blocker: Ollama cloud error after 1 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 40eea4ba-161e-4085-8cf9-b4f783f08f12)"}

- `kimi27code` `ollama:kimi-k2.7-code:cloud` ok=False verdict=blocked score=0 actual=-
  summary: kimi27code could not run.
  blocker: Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: c4a942c3-bfb5-46bc-a570-eaf48d60dbd4)"}

- `qwen3coder` `ollama:qwen3-coder:480b-cloud` ok=False verdict=blocked score=0 actual=-
  summary: qwen3coder could not run.
  blocker: Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 00b3e0fe-c871-4f12-a06e-f56bd6af6d0e)"}

- `deepseekv4pro` `ollama:deepseek-v4-pro:cloud` ok=False verdict=blocked score=0 actual=-
  summary: deepseekv4pro could not run.
  blocker: Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: b153a618-810f-4693-886b-d4fd7280ddfb)"}

- `minimaxm3` `ollama:minimax-m3:cloud` ok=False verdict=blocked score=0 actual=-
  summary: minimaxm3 could not run.
  blocker: Ollama cloud error after 10 attempts: 429: {"error":"you (johnvincentshrader) have reached your weekly usage limit, add extra usage: https://ollama.com/settings (ref: 3e112ff4-8566-455c-a562-bfd97104e7b8)"}

- `nemotron3ultra` `openrouter_free:nvidia/nemotron-3-ultra-550b-a55b:free` ok=False verdict=blocked score=0 actual=nvidia/nemotron-3-ultra-550b-a55b-20260604:free
  summary: nemotron3ultra could not run.
  blocker: invalid critic JSON from openrouter_free:nvidia/nemotron-3-ultra-550b-a55b:free; actual_model=nvidia/nemotron-3-ultra-550b-a55b-20260604:free; content_len=2899; parse_error=JSONDecodeError: Invalid control character at: line 17 column 7 (char 1697); preview={\n  "verdict": "reject",\n  "score": 0,\n  "summary": "The track runtime-truth-nats-2026-06 is explicitly closed as VERIFIED_SLICE with a clear note: 'this is still not a production live-readiness or SUBSTRATE_TRUSTED NATS claim.' The review

## Persistent Agent

- `palantir-pilot` status=running fresh=True
