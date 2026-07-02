# Provider Chain Hardening Receipt - 2026-06-30

**Track:** `loop-closure-2026-06`
**Scope:** Phase 1a provider-chain hardening, not Loop 1 closure
**Generated:** 2026-06-29T15:35:18Z / 2026-06-30T00:35:18+09:00
**Checkout:** `/Users/dhyana/dharma_swarm`
**Update:** Loop 1 closure was later proven in
`reports/loop_closure/phase1/LOOP1_CLOSURE_RECEIPT.md`.

## Verdict

Phase 1a has current, local evidence for separated provider failure classes,
fallback ordering, and honest provider-smoke reporting. This receipt does not
create or replace `LOOP1_CLOSURE_RECEIPT.md`.

At creation time, Loop 1 remained incomplete until a fresh accepted runtime
dispatch produced a persisted served-provider/served-model receipt that
`make orient` read from the current owner surface. That closure proof now
exists.

## Commands Run

- `pytest -q tests/test_provider_failure_classes.py tests/test_provider_smoke.py`
  - result: 32 passed.
- `dkeys test`
  - result: 10 live providers, 2 valid-but-no-funds, 2 auth-fail, 1 no-key-yet.
- `.venv/bin/python -c 'from dharma_swarm.provider_smoke import run_provider_smoke; ...'`
  - result: sanitized provider-smoke summary below.

## Local Contract Evidence

`tests/test_provider_failure_classes.py` proves:

- rate limit, quota exhaustion, billing exhaustion, access denial, timeout, and
  generic provider errors are separate classes.
- `rate_limited` falls through without fast-tripping a circuit breaker.
- `quota_exhausted` fast-trips the failed lane and falls through to the next
  available provider.

`tests/test_provider_smoke.py` proves:

- local Ollama smoke can be forced with `OLLAMA_FORCE_LOCAL=1` even on machines
  where the canonical dkeys store contains an Ollama Cloud key.
- provider-wide terminal failures stop a model pack instead of pretending
  later models are meaningful.
- empty OpenRouter outputs are skipped rather than treated as success.
- provider-smoke outcomes can be persisted as telemetry outcome records when a
  telemetry database is supplied.

## Sanitized Live Smoke Summary

No API keys were printed.

```text
ollama status=ok model=glm-5 strongest=glm-5 configured=glm-5:cloud
  verified= [('glm-5', 'ok')]
nvidia_nim status=ok model=meta/llama-3.3-70b-instruct strongest=meta/llama-3.3-70b-instruct configured=nvidia/llama-3.1-nemotron-ultra-253b-v1
  verified= [('nvidia/llama-3.1-nemotron-ultra-253b-v1', 'error'), ('meta/llama-3.3-70b-instruct', 'ok')]
openrouter status=insufficient_credits model=moonshotai/kimi-k2.5 strongest=None configured=moonshotai/kimi-k2.5
  verified= [('moonshotai/kimi-k2.5', 'insufficient_credits')]
```

`dkeys test` still reports the configured OpenRouter key as HTTP 404 on its
live-test path. The provider-smoke path classifies OpenRouter as insufficient
credits for the current model probe. These remain OpenRouter-specific blocker
states, but Loop 1 itself was later closed through the live `nvidia_nim` lane.

## Remaining Closure Gap

The current checkout had working fallback lanes, but the active closure proof
was still missing when this receipt was written. The later closure proof itself
proves:

1. a fresh dispatch through the accepted runtime/spine path,
2. a persisted receipt with non-empty actual served provider and model,
3. `make orient` projecting that current proof, and
4. a repeatable no-secret transcript.
