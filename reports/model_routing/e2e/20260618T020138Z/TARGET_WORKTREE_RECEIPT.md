# Target Worktree Receipt

Mission ID: `20260618T020138Z`
Generated: `2026-06-18T02:01:38Z`
Primary execution checkout: `/Users/dhyana/ds_model_pool`

## Decision

Final routing-hardening work for this mission lands in:

`/Users/dhyana/ds_model_pool`

This checkout owns the model-routing consolidation branch and contains the existing
model-pool consolidation work. Semantic Commons naming alignment is not owned by
this checkout yet; it must be reconciled from `/Users/dhyana/dharma_swarm` before
the naming-drift gate can close.

## Comparison

| Checkout | Branch / state | HEAD | Dirty tracked state | Untracked count | Routing ownership signal | Semantic Commons signal | Verdict |
|---|---|---:|---|---:|---|---|---|
| `/Users/dhyana/dharma_swarm` | `telos-ai-seed-v0-from-sandbox` tracking same remote branch | `f70644d84cbca9aed90deff77dad7c244a586d11` | 21 tracked files modified, including `docs/ontology/*`, A2A/live-ops files, and semantic tests | 21000 | Has base routing files, but branch is Telos/A2A/Semantic Commons work, not model-routing consolidation | Owns current tracked `docs/ontology/SEMANTIC_COMMONS.md`, `semantic_aliases.yaml`, `semantic_objects.yaml` edits | Source for Semantic Commons alignment, not final patch target |
| `/Users/dhyana/ds_model_pool` | `model-routing/consolidation-2026-06` tracking `origin/main`, ahead 21 / behind 1 | `b575de89743c98ad246764bf259a99b9557a35ff` | 9 tracked files modified: `providers.py`, routing/provider tests, governance evidence | 8 | Branch name, log, and reports identify this as routing consolidation; existing model-pool report says all model surfaces derive from pool and no-model-literals guard is wired | Lacks tracked `docs/ontology/semantic_aliases.yaml` and `semantic_objects.yaml`; has `docs/ops/MODEL_KEY_ROUTING.md` and routing guard test | Primary execution checkout |
| `/Users/dhyana/dharma_swarm_main` | detached `HEAD` / main | `9c76b2106d95ff3706ed0fa81f732240dfa01183` | 3 governance evidence files modified | 0 | Mainline baseline only | No tracked Semantic Commons ontology yaml files in target set | Baseline/reference only |

## Evidence Commands

- `git -C /Users/dhyana/dharma_swarm status --short --branch --untracked-files=no`
- `git -C /Users/dhyana/ds_model_pool status --short --branch --untracked-files=no`
- `git -C /Users/dhyana/dharma_swarm_main status --short --branch --untracked-files=no`
- `git -C /Users/dhyana/dharma_swarm rev-parse HEAD`
- `git -C /Users/dhyana/ds_model_pool rev-parse HEAD`
- `git -C /Users/dhyana/dharma_swarm_main rev-parse HEAD`
- `git -C /Users/dhyana/dharma_swarm log -8 --oneline --decorate`
- `git -C /Users/dhyana/ds_model_pool log -8 --oneline --decorate`
- `git -C /Users/dhyana/dharma_swarm_main log -8 --oneline --decorate`
- `git -C <checkout> ls-files <routing/status/surface/ontology target paths>`
- `git -C <checkout> ls-files --others --exclude-standard | wc -l`

## File Coverage

All three checkouts contain the core routing files:

- `dharma_swarm/model_hierarchy.py`
- `dharma_swarm/model_catalog.py`
- `dharma_swarm/provider_matrix.py`
- `dharma_swarm/api_keys.py`
- `dharma_swarm/runtime_provider.py`
- `dharma_swarm/providers.py`
- `dharma_swarm/routing_memory.py`
- `dharma_swarm/tui/model_routing.py`
- `dashboard/src/app/dashboard/models/page.tsx`
- `docs/ops/MODEL_KEY_ROUTING.md`
- `tests/test_model_key_routing_guard.py`

Only `/Users/dhyana/dharma_swarm` currently tracks these Semantic Commons
ontology files in the checked target set:

- `docs/ontology/SEMANTIC_COMMONS.md`
- `docs/ontology/semantic_aliases.yaml`
- `docs/ontology/semantic_objects.yaml`

`/Users/dhyana/ds_model_pool` has existing untracked model-pool receipts:

- `reports/model_pool/CONSOLIDATION_REPORT.md`
- `reports/model_pool/e2e_20260617T110309.json`
- `reports/model_pool/e2e_20260617T124759.json`
- `reports/model_pool/e2e_20260617T125818.json`
- `reports/model_pool/e2e_20260617T193229.json`
- `reports/model_pool/e2e_20260617T220156.json`
- `reports/model_pool/e2e_20260617T221542.json`
- `reports/model_pool/e2e_20260617T222523.json`

Those receipts are useful prior evidence but do not satisfy the current mission's
required artifact layout or live-failure classification requirements.

## Ownership Ruling

Routing consolidation owner: `/Users/dhyana/ds_model_pool`.

Semantic Commons naming-alignment owner: `/Users/dhyana/dharma_swarm` currently
contains the live branch edits and ontology YAML files. The final mission patch
must either import the relevant ontology files into `/Users/dhyana/ds_model_pool`
or add an explicit guard that registers routing names against the available
Semantic Commons source.

Final patch target: `/Users/dhyana/ds_model_pool`.

## Edit Boundary

No implementation edits were made before this target receipt. From this point
forward, implementation changes for the model-routing hardening mission should
be made only in `/Users/dhyana/ds_model_pool`, except for read-only comparison
against the other checkouts.

Secrets boundary remains active: no key values, environment secret values, or
raw provider credentials may be printed, copied, committed, or sent to agents.
