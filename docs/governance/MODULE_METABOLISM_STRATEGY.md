# Module Metabolism Strategy

Status: conceptual and operational synthesis, 2026-05-05. No runtime behavior,
pre-commit hook, Makefile target, or hard gate is changed by this document.

## 1. Thesis

Dharma Swarm is not copy-paste rotten. It is conceptually over-accreted.

The next architecture move is not mass deletion or broad refactoring. It is
metabolism by ownership:

1. Find repeated concepts.
2. Identify the one semantic owner.
3. Add a facade or bridge when consumers cannot move at once.
4. Move callers in small verified PRs.
5. Retire duplicate centers only after tests and import evidence prove safety.

This follows the repo's own doctrine: the failure mode is too many surfaces
claiming canonical truth at once, not merely too many files
(`docs/REPO_ONTOLOGY_AND_HYGIENE_MASTER_SPEC_2026-04-01.md:75`).

## 2. Measured Shape

Fresh static scan of `dharma_swarm/` on 2026-05-05:

- 570 Python files under `dharma_swarm/`
- 556 production modules excluding internal tests
- 388 production modules at package root, about 70 percent
- 249,559 total package LOC
- 162 files over 500 LOC
- 39 files over 1000 LOC
- 7 files over 3000 LOC
- 0 syntax parse errors
- about 1,445 intra-package import edges
- about 130 to 150 modules with no inbound package import, depending on test inclusion
- 91 root modules with no inbound package import
- 11 import-cycle components

The old manifest is directionally right but stale. It already prohibits
flat-package growth and duplicate bridge/router/adapter/orchestrator surfaces
(`docs/governance/SOVEREIGN_MANIFEST.md:17`,
`docs/governance/SOVEREIGN_MANIFEST.md:20`), and it explicitly warns that
numerical claims decay and must be rechecked before citation
(`docs/governance/SOVEREIGN_MANIFEST.md:41`).

## 3. External Lenses

- Parnas: decompose around hidden design decisions, not around execution
  sequence or file size alone. Source: CACM 1972 DOI listing for "On the
  Criteria to Be Used in Decomposing Systems into Modules".
- Ousterhout: prefer deep modules, where a small interface hides a larger
  implementation. This repo has too many shallow peers around session,
  governance, adapters, routing, and bridges.
- Google large-scale change practice: avoid sweeping atomic rewrites; make
  broad changes in small, testable increments.
- Fowler branch-by-abstraction: introduce an abstraction, migrate clients, keep
  the system running, then remove the old supplier.
- Karpathy verifiability: AI gets strongest where tasks are resettable,
  efficient, and rewardable. Repo health metrics should produce recomputable
  JSON evidence, not prose-only opinions.
- Ashby and Beer: regulation needs requisite variety. Do not centralize all
  module decisions into one gate. Use local ownership plus S3/S3* audit loops.
- Baldwin and Clark: modularity has option value when hidden modules can evolve
  independently while obeying visible design rules.

## 4. Local Doctrine

The strongest local rule is already in the Core Four blueprint:

> Typed contracts govern state mutation. Emergent dynamics govern behavior.

Operationally, the collapse rule is:

1. Same authority?
2. Same failure mode?
3. Same lifecycle?
4. Same rollback / provenance need?
5. Same query surface?

Collapse only if all five match. If any differ, bridge instead
(`docs/CORE_FOUR_ONTOLOGY_BLUEPRINT_v3_FULL_PICTURE.md:117`).

The substrate rubric gives the native-write standard: typed contract, authority
metadata, governance hook, and traceability
(`docs/governance/SUBSTRATE_NATIVENESS_RUBRIC.md:66`).

PTR gives the cybernetic frame: monitor, analyze, plan, execute later, verify,
and preserve knowledge, with no immediate runtime authority change
(`docs/governance/PTR_CYBERNETIC_LOOP_SPEC.md:232`,
`docs/governance/PTR_CYBERNETIC_LOOP_SPEC.md:255`).

## 5. Metric Frame

Do not make TCS the one repo-health metric. TCS is identity coherence, an S5
signal. The stronger top metric is PTR because it asks whether the system can
predict, act, verify, repair, and preserve telos under evidence.

Module metabolism should feed PTR only as `repo_integrity` evidence. It must not
grant authority, block commits, or become a hidden Rule 10 expansion.

The one top metric:

- `PTR`: Predictive Telic Repair, confidence-aware and negative-authority only.

Four support pillars:

1. Capsule operability: LOC, public API size, branch count, fan-in/fan-out,
   side-effect density, and test references.
2. Contract clarity: typed API coverage, raw `dict[str, Any]` pressure, schema
   duplication, and canonical owner.
3. Verifiability loop: direct tests, integration tests, replayability, JSON
   artifacts, resettable state, and rewardable outcomes.
4. Substrate traceability: runtime store, ontology ActionDef, witness logs,
   artifact records, memory facts, timestamps, and evidence refs.

## 6. Decision Rules

- Merge when two modules encode the same design decision with the same
  authority, lifecycle, failure mode, and consumers.
- Bridge when representations differ by authority or failure mode but need
  explicit reconciliation.
- Metabolize into typed surfaces when a module writes durable state, decisions,
  lineage, tasks, artifacts, memory, or governance traces.
- Preserve as a bounded vertical when the surface is experimental,
  domain-specific, or intentionally diverse.
- Archive-review only after import graph, tests, entrypoint scan, and operator
  usage all agree. No-inbound is not proof of dead code.

## 7. Target Taxonomy

Use this as the package map before moving files:

- `core`: stable models, base contracts, identity primitives
- `governance`: DharmaKernel, TelosGatekeeper, PolicyCompiler, Shakti, PTR
- `runtime`: SQLite/JSONL state, lifecycle, artifacts, write surfaces
- `operator_core`: shell-neutral session, event, routing, permission truth
- `surfaces`: dashboard, terminal, API, CLI as presentation/transport only
- `providers`: provider implementations, model routing, fallback policy
- `orchestration`: swarm, agent runner, dispatch, task execution
- `knowledge`: context, memory, retrieval, semantic index
- `ontology`: ontology registry/runtime, Chetana provenance, substrate contracts
- `evolution`: Darwin/Jikoku/meta-evolution/control-loop learning
- `domains`: Ginko, Gaia, cascade domains, economic/product verticals
- `assurance`: xray, scanner, verify, integrity probes, capsule reports

## 8. First Corridors

These are review corridors, not automatic refactors:

1. Operator session store:
   `operator_core/session_store.py` and `tui/engine/session_store.py`.
   Likely owner: `operator_core`; TUI becomes facade/projection.

2. Operator permission/governance:
   `operator_core/permissions.py` and `tui/engine/governance.py`.
   Likely owner: `operator_core`; TUI keeps display and filtering logic.

3. Claude adapter convergence:
   `terminal_adapters/claude.py` and `tui/engine/adapters/claude.py`.
   Likely owner: one adapter contract plus compatibility shim.

4. Model/provider/routing:
   `providers.py`, `provider_policy.py`, `router_v1.py`, `smart_router.py`,
   `swarm_router.py`, `runtime_provider.py`, and routing memory.
   Goal: one routing contract, many strategies.

5. Runtime/ontology state:
   `runtime_state.py`, `ontology.py`, `ontology_hub.py`, `telic_seam.py`,
   Chetana provenance, artifact records, memory facts.
   Goal: write authority plus explicit projections.

6. Ginko vertical:
   17 root `ginko*` files. Package as `dharma_swarm/ginko/` behind a facade,
   but do not mix into core runtime.

7. CLI/god object:
   `dgc_cli.py` first needs a command inventory and ownership map. Split only
   after command families have characterization tests.

## 9. Ranked Queue

1. Terminal adapter convergence.
2. Session store convergence.
3. Permission/governance convergence.
4. `ginko/` package boundary.
5. `dgc_cli.py` command-family inventory.
6. `agent_runner.py` execution/memory/routing/provider split map.
7. `providers.py` facade stabilization.
8. Model-routing cycle reduction.
9. Memory/context/semantic/retrieval contract.
10. Bridge inventory: active, facade, deprecated, archive-review.

## 10. Warn-Only Report

Next shippable tool:

`scripts/governance/module_metabolism_report.py`

It should emit JSON and text with:

- module path and package family
- LOC and public API count
- class/function/import counts
- inbound/outbound import counts
- cycle membership
- no-inbound status
- test-reference count
- side-effect/write-surface hits
- similarity pairs
- family cluster
- suggested action:
  `keep`, `split-review`, `merge-review`, `facade`, `move-to-package`,
  `archive-review`
- confidence flags:
  `entrypoint_possible`, `test_signal_missing`, `doc_claim_stale`,
  `write_surface`, `core_hub`

It must be warn-only:

- no pre-commit wiring
- no Makefile wiring
- no Rule 10 change
- no runtime import
- no commit blocking
- no automatic delete recommendation

The eventual artifact can feed PTR as:

`~/.dharma/meta/module_metabolism.json`

## 11. Operating Plan

Two weeks:

- Add the warn-only report and tests.
- Produce a baseline JSON artifact.
- Characterize session store, permissions/governance, and Claude adapter pairs.
- Do not move callers yet.

Six weeks:

- One corridor per branch.
- Add facade first.
- Move 1 to 3 callers at a time.
- Keep old modules importable as compatibility shims.
- Track import deltas and test deltas.

Twelve weeks:

- Ratchet only new debt:
  no new root modules, no new files over 500 LOC without exception, no new
  import cycles, no new bridge/router/adapter duplicates.
- Promote reports to CI artifacts/comments only after baselining.
- Delete only when import graph, tests, and entrypoint scans all agree.

## 12. Non-Goals

- No mass file moves.
- No runtime rewrite.
- No hard gate.
- No Makefile or pre-commit integration.
- No Rule 10 change.
- No ontology collapse unless the five-question test passes.
- No deletion from static no-inbound evidence alone.
- No dashboard/API replatforming.
- No PTR authority expansion.

## 13. Sources

- Local: `docs/governance/SOVEREIGN_MANIFEST.md`
- Local: `docs/REPO_ONTOLOGY_AND_HYGIENE_MASTER_SPEC_2026-04-01.md`
- Local: `docs/CORE_FOUR_ONTOLOGY_BLUEPRINT_v3_FULL_PICTURE.md`
- Local: `docs/governance/PTR_CYBERNETIC_LOOP_SPEC.md`
- Local: `docs/governance/SUBSTRATE_NATIVENESS_RUBRIC.md`
- Local: `docs/telos-engine/07_VSM_GOVERNANCE.md`
- Parnas, "On the Criteria to Be Used in Decomposing Systems into Modules":
  https://www.scirp.org/reference/referencespapers?referenceid=2908532
- Ousterhout deep modules summary:
  https://softengbook.org/articles/deep-modules
- Google large-scale changes:
  https://abseil.io/resources/swe-book/html/ch22.html
- Fowler, Branch by Abstraction:
  https://martinfowler.com/bliki/BranchByAbstraction.html
- Fowler/Dehghani, breaking monoliths by capability:
  https://martinfowler.com/articles/break-monolith-into-microservices.html
- Karpathy, Verifiability:
  https://karpathy.bearblog.dev/verifiability/
- Ashby, requisite variety:
  https://panarchy.org/ashby/variety.1956.html
- VSM overview:
  https://vsm-training.org/columns/
- Baldwin and Clark, option value of modularity:
  https://scholarsarchive.byu.edu/facpub/8944/
