# Provider Registry Migration Plan (PR-H3 scaffold → PR-H3a/H3b/...)

**Status:** scaffold landed; piecewise migration pending.
**Doctrine posture:** zero new substrate, additive only.

## What landed in PR-H3 (scaffold)

`dharma_swarm/provider_registry.py` (217 LOC) — pure stdlib. Provides:

- `PROVIDER_REGISTRY: dict[str, ProviderFactory]` — opt-in registry
- `@register_provider(provider_id, *, default_model, requires_env_vars, notes)` — class decorator
- `get_registered_provider(provider_id)` — typed lookup
- `registered_provider_ids()` — sorted ids
- `clear_registry_for_tests()` — test-only reset
- `render_registry_summary()` — human-readable inspector
- Custom exceptions: `ProviderRegistryError`, `ProviderAlreadyRegisteredError`

`tests/test_provider_registry.py` (150 LOC, 11 tests) — verifies decorator semantics, duplicate rejection, isolation.

**`dharma_swarm/providers.py` is unchanged.** No import sites modified. No behavior change.

## Why scaffold-only first

Splitting `providers.py` (3,005 LOC, 14 provider classes, 1,200-LOC `ModelRouter`, 40 import sites) is a real multi-day refactor that touches the dispatch hot path. Doing it as one batch without a full CI run risks subtle drift. The registry is the *contract* that makes piecewise extraction safe.

## The piecewise plan

### PR-H3a — opt in the simplest provider first

Add `@register_provider("anthropic", default_model=..., requires_env_vars=("ANTHROPIC_API_KEY",))` to `AnthropicProvider` in `providers.py`. **No other changes.** Verify:
- All existing tests still pass.
- `registered_provider_ids()` returns `["anthropic"]`.
- Production code still constructs `AnthropicProvider()` directly through every existing pathway.

Small PR, low risk, builds confidence in the contract.

### PR-H3b–H3n — opt in remaining providers one PR at a time

In this order (cheapest-first, biggest-blast-radius-last):

1. `MistralProvider`, `CerebrasProvider`, `SiliconFlowProvider`, `TogetherProvider`, `FireworksProvider`, `GoogleAIProvider`, `SambaNovaProvider`, `ChutesProvider` — all are HTTPx-thin and very similar shape. One PR each, or batched as one "thin OpenAI-compat" PR.
2. `GroqProvider`, `NVIDIANIMProvider`, `OllamaProvider` — have their own quirks.
3. `OpenAIProvider`, `OpenRouterProvider`, `OpenRouterFreeProvider` — heavier; touch fallback chains.
4. `ClaudeCodeProvider`, `CodexProvider` — subprocess-style; `requires_env_vars=()`.

After each opt-in PR: `registered_provider_ids()` grows by one, all tests pass, dispatch behavior identical.

### PR-H3-router — teach ModelRouter to consult the registry

Once all 14 providers are registered, `create_default_router()` can iterate `PROVIDER_REGISTRY` instead of hardcoding the constructor list. This is the first PR with *actual* behavior change: previously, adding a provider required editing `create_default_router()`; afterward, the decorator is sufficient.

### PR-H3-split — finally rename providers.py → providers/

After every provider is registered and `create_default_router()` is registry-driven, the actual file split becomes mechanical:

1. Rename `dharma_swarm/providers.py` → `dharma_swarm/providers/__init__.py`.
2. Move each `*Provider` class to `dharma_swarm/providers/<id>.py`.
3. `__init__.py` re-exports every public name so the 40 import sites keep working.
4. `ModelRouter` moves to `dharma_swarm/providers/router.py` (or stays as a sibling module).

Add `manifest_check.py` rule: every entry in `PROVIDER_REGISTRY` must have its class defined in a file under `dharma_swarm/providers/`. The checker catches drift.

## Manifest invariants this enables

Future addition to `tools/manifest_check.py`:

- **Check 6 (when ready):** every `agents` and `loops` provider reference must resolve to a registered `provider_id`. Catches typos in YAML routing rules.
- **Check 7 (when ready):** every provider class with an `LLMProvider` base must either be registered OR live in a `legacy/` subpackage. Prevents new provider classes from sneaking in unregistered.

## Anti-doctrine self-check

- New substrate? **No.** The registry is one module of plain Python data.
- Meta-framework? **No.** The decorator is a 30-line function; the registry is a dict.
- Parallel governance? **No.** `create_default_router()` remains authoritative until explicitly migrated.
- Forced opt-in? **No.** Providers without `@register_provider` keep working.
- Touches frozen surfaces? **No.**

## Rollback

If the registry causes any problem, the rollback is to delete `provider_registry.py` and `test_provider_registry.py`. Since no production code imports them and `providers.py` is unchanged, the rollback has zero blast radius.
