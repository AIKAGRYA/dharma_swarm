# Naming Drift Report

Mission ID: `20260618T020138Z`

## Scope

This report covers the Agent 1 naming requirement for the model-routing E2E
mission: canonical model/provider identities, aliases, forbidden/deprecated
names, hardcoded debt, and Semantic Commons alignment.

Primary evidence:

- `reports/model_routing/e2e/20260618T020138Z/model_inventory.json`
- `tests/test_model_key_routing_guard.py`
- sibling Semantic Commons worktree: `/Users/dhyana/dharma_swarm/docs/ontology`

## Canonical Model Inventory

Current inventory:

- logical model entries: `30`
- floor entries: `12`
- grunt-only entries: `18`
- declared routes: `42`
- route providers: `10`
- roster slots: `42`

Canonical model identity owner:

- `dharma_swarm.model_pool`

Route/status owner:

- `dharma_swarm.model_pool`
- `dharma_swarm.key_oracle.live_providers()`
- `dharma_swarm.model_status` for operator-facing projection

Every inventory entry in `model_inventory.json` has:

- a stable logical `id`
- a floor/grunt lane
- at least one declared provider route
- `route_status_owner` set to
  `dharma_swarm.model_pool + dharma_swarm.key_oracle.live_providers`

The current pool does not carry per-model aliases: all `aliases` arrays are
empty. Operator aliases for floor TUI targets are maintained in
`dharma_swarm.tui.model_routing` and are now projected into Terminal/Bun through
the canonical `dharma_swarm.model_status` bridge contract.

## Semantic Commons Alignment

The target patch worktree `/Users/dhyana/ds_model_pool` does not currently own
the Semantic Commons ontology files:

- `docs/ontology/SEMANTIC_COMMONS.md`: missing in target
- `docs/ontology/semantic_aliases.yaml`: missing in target
- `docs/ontology/semantic_objects.yaml`: missing in target

The sibling `/Users/dhyana/dharma_swarm` worktree does own them:

- `docs/ontology/SEMANTIC_COMMONS.md`
- `docs/ontology/semantic_aliases.yaml`
- `docs/ontology/semantic_objects.yaml`

The sibling Semantic Commons includes routing objects for:

- `ModelKeyRouting`
- `DKeysKeyStore`
- `RuntimeProvider`
- `ModelHierarchy`
- `ProviderPolicyRouter`
- `ModelRouter`
- `RoutingMemory`

It also defines forbidden aliases that match this mission's constraints:

- `parallel model routing layer`
- `project .env keys`
- `direct provider factory`
- `scattered model order`

Conclusion: naming discipline is aligned by concept, but not physically
registered inside the target routing worktree. The target worktree therefore
uses the guard below as the enforceable drift gate until the Semantic Commons
branch is reconciled.

## Guarded Drift

`tests/test_model_key_routing_guard.py` enforces the one-way contract:

- new model literals belong in approved registry/catalog files only
- new provider key reads belong in `api_keys.py` or `runtime_provider.py`
- feature code cannot silently add model strings or direct key reads

Canonical inventory source:

- `dharma_swarm/model_pool.py`

Approved model-literal registry files in the current guard include:

- `dharma_swarm/model_catalog.py`
- `dharma_swarm/model_hierarchy.py`
- `dharma_swarm/provider_matrix.py`
- `dharma_swarm/provider_smoke.py`
- `dharma_swarm/providers.py`
- `dharma_swarm/router_v1.py`
- `dharma_swarm/tui/model_routing.py`

The guard currently passes as part of the final verification run.

## Known Hardcoded Debt

The existing known-debt baseline is still non-zero and remains explicitly
registered in `tests/test_model_key_routing_guard.py`:

- known model literal debt occurrences: `69`
- known raw key-read debt occurrences: `22`

Largest model-literal debt buckets:

- `dharma_swarm/terminal_adapters/claude.py`: `6`
- `dharma_swarm/tui/engine/adapters/claude.py`: `6`
- `dharma_swarm/orchestrate_live.py`: `5`
- `scripts/full_stack_smoke.py`: `5`
- `dharma_swarm/startup_crew.py`: `4`
- `scripts/onboard_cybernetics_stewards.py`: `4`
- `scripts/organism_with_intelligence.py`: `4`
- `scripts/runtime/forge_swarm_evolution_arena_v0_measurement_runner.py`: `4`

Largest raw key-read debt buckets:

- `scripts/dgc_max_stress.py`: `6`
- `scripts/allout_autopilot.py`: `3`
- `scripts/strange_loop.py`: `3`
- `dharma_swarm/tui_legacy.py`: `2`

No new model literal debt was added by the routing decision matrix; its fake
provider request now uses `DEFAULT_MODELS[ProviderType.OPENAI]` rather than a
hardcoded model id.

## Forbidden/Deprecated Names

Forbidden names are enforced by source placement rather than by a runtime alias
table in this worktree:

- `project .env keys`: forbidden by Semantic Commons and by key-read guard.
- `direct provider factory`: forbidden by Semantic Commons; runtime construction
  must enter through `resolve_runtime_provider_config()` and
  `create_runtime_provider()`.
- `scattered model order`: forbidden by Semantic Commons; provider/model order
  belongs in `model_hierarchy` and the model pool.
- sub-floor models in default picker/fallback paths: blocked by
  `dharma_swarm.tui.model_routing` import-time validation.

## Required Follow-Up

The remaining naming work is branch reconciliation, not new local drift:

1. Reconcile `/Users/dhyana/dharma_swarm/docs/ontology/*` into the routing
   consolidation branch, or add an explicit Semantic Commons registration guard
   to this branch.
2. Retire known debt from `tests/test_model_key_routing_guard.py` in small
   migrations, shrinking the baseline rather than expanding it.
3. Promote model aliases from surface-local tables into the canonical model pool
   when alias semantics become stable enough to own globally.

Until then, the current merge gate is:

```bash
pytest -q tests/test_model_key_routing_guard.py
```
