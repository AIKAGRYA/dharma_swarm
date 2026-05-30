# Devin Outbound — PR-H3 Provider Registry (scaffold)

**From:** Devin (Roaming) `AGT-DEVIN_ROAMING_2987D222`
**Authority:** `external_worker_evidence_only`
**Date:** 2026-05-30
**Branch:** `devin/2026-05-30-provider-registry` (sibling to main, independent of PR #384 / PR #388)
**Active track:** `runtime-truth-spine-2026-06` — not displaced.
**Frozen surfaces touched:** none.
**Existing code touched:** none. `providers.py` is unchanged.

## Scope decision

The audit identified `dharma_swarm/providers.py` (3,005 LOC, 14 LLM provider classes, 1,200-LOC `ModelRouter`, 40 import sites) as the highest-value module to split. The "natural" full PR is multi-day and touches the dispatch hot path.

After explicit operator decision ("Scaffold-only (safe)"), this PR delivers the **contract** that makes a piecewise extraction safe, without touching providers.py or any import site.

## What landed

1. `dharma_swarm/provider_registry.py` (217 LOC, stdlib only)
   - `ProviderFactory` (frozen dataclass) — descriptor for one registered provider
   - `PROVIDER_REGISTRY: dict[str, ProviderFactory]` — opt-in registry, starts empty
   - `@register_provider(provider_id, *, default_model, requires_env_vars, notes)` — class decorator
   - `get_registered_provider(provider_id)` — typed lookup; raises `KeyError` with known-ids hint
   - `registered_provider_ids()` — sorted list
   - `clear_registry_for_tests()` — test-only registry reset
   - `render_registry_summary()` — human-readable inspector
   - Custom exceptions: `ProviderRegistryError`, `ProviderAlreadyRegisteredError`

2. `tests/test_provider_registry.py` (150 LOC, 11 tests, all passing) — verifies decorator semantics, duplicate rejection, isolation, frozen-factory immutability, sorted enumeration, empty-state rendering.

3. `docs/reports/provider_registry_migration_plan.md` — the piecewise plan for opting providers in one-PR-at-a-time, then renaming providers.py → providers/ once every class is registered.

## What did NOT happen (deliberate)

- `providers.py` is **not** modified.
- No provider class is registered yet. `PROVIDER_REGISTRY` is empty until a follow-up PR adopts the decorator.
- `create_default_router()` is **not** changed. The registry exists; no one consults it yet.
- No import sites touched.
- `dharma_swarm.__init__` unchanged.

This is the safe shape: rollback is `rm dharma_swarm/provider_registry.py tests/test_provider_registry.py` with zero blast radius.

## Why this is still "moving the needle"

It establishes the **contract** the eventual extraction must conform to. Without it, every future "let's split providers.py" attempt has to invent its own registry shape under deadline pressure. With it, each subsequent PR is mechanical and small: add one decorator, verify one provider, repeat 14 times. The hard architectural choice (decorator? registry function? module-import side effect? class hierarchy?) is decided **now**, in slow time, in isolation, with tests.

It also enables future manifest-checker invariants:
- "every registered provider has its class defined under `dharma_swarm/providers/`" (catches the file-split's completion)
- "every YAML routing rule's `provider_id` resolves to a registered id" (catches typos)

## Anti-doctrine self-check

- Builds AGI? No.
- Uncontrolled self-modification? No.
- Autonomous capital deployment? No.
- Autonomous external messaging? No.
- Deceptive memetic engineering? No.
- Parallel governance? No — `create_default_router` remains authoritative.
- Vague prose? No — 11 tests, exact decorator semantics.
- New substrate? **No.** One module, one dict, one decorator.
- Meta-framework? **No.** The decorator is a 30-line function.
- Forced opt-in? **No.** Providers without `@register_provider` keep working.
- Touches frozen surfaces? **No.**

## Follow-up sequence (separate PRs)

- **PR-H3a:** opt in `AnthropicProvider` only. Smallest possible adopter, sanity-checks the contract end-to-end.
- **PR-H3b–H3n:** opt in remaining 13 providers, batched by similarity (thin OpenAI-compat / quirky / heavy / subprocess).
- **PR-H3-router:** teach `create_default_router()` to enumerate `PROVIDER_REGISTRY` instead of hardcoding the constructor list.
- **PR-H3-split:** mechanical rename `providers.py` → `providers/__init__.py` + per-provider files. Possible only after every provider is registered.

Each step is independently testable, independently revertible.

Authority compliance: this notice + open PR + await operator merge. No autonomous merge.
