---
title: Sattva Quality Cartography
status: seed
schema_version: quality_cartography.v1
last_updated: 2026-06-12
witnessed_branch: qwen/spine-adoption
witnessed_head: ca890d117a
doc_role: report
authority: descriptive
companion_artifacts:
  - docs/quality/QUALITY_LAYER_MAP.yaml
  - docs/quality/QUALITY_RECEIPT.md
---

# Sattva Quality Cartography

This is the first living map of the positive side of code quality in
`dharma_swarm`: not just anti-slop prevention, but the observable layers that
can become the Sattva Quality Lattice. It is grounded in the working tree at
`/Users/dhyana/dharma_swarm`, branch `qwen/spine-adoption`, HEAD `ca890d117a`.

This file is descriptive, not authority. The authoritative owners remain the
repo gates and manifests cited below: `make onboard`,
`ACTIVE_SURFACE_MANIFEST.yaml`, `docs/governance/ACTIVE_TRACK.yaml`,
`docs/governance/SOVEREIGN_MANIFEST.md`, and the scripts under
`scripts/governance/`.

## Executive Summary

Current posture: strong governance substrate, real receipt discipline, and
several truth-telling gates, with quality gaps concentrated at seams where
advisory signals have not yet become invariants.

Observed strengths:

- Governance has real mechanics: 10 anti-slop rules in
  [docs/governance/ANTI_SLOP_RULES.md](/Users/dhyana/dharma_swarm/docs/governance/ANTI_SLOP_RULES.md:13),
  70 hygiene patterns generated from JSON-compatible YAML, and active
  Makefile gates at [Makefile](/Users/dhyana/dharma_swarm/Makefile:175).
- MemoryKernel is unusually disciplined: 30 modules under
  `dharma_swarm/memory_kernel`, strict readiness is green, and core surfaces
  use frozen dataclasses plus schema-versioned receipts.
- The correlation spine states a precise invariant in
  [ACTIVE_SURFACE_MANIFEST.yaml](/Users/dhyana/dharma_swarm/ACTIVE_SURFACE_MANIFEST.yaml:687):
  receipts may differ by closure layer, but correlation identity must not.
- The system tells the truth about drift. `make docops-integrity` currently
  fails on four named items instead of hiding stale documentation.

Observed gaps:

- Semgrep is now live locally and reports one blocking Rule 1 finding in
  untracked `holon/cli.py`: a direct `Path.home() / ".dharma"` receipt path at
  [holon/cli.py](/Users/dhyana/dharma_swarm/holon/cli.py:213).
- `scripts/governance/verify_quality_membrane.py` is a good membrane design,
  but its current `runtime_names` gate fails on 19 `F821/F811` issues before
  later gates run.
- The runtime truth spine adoption track is still 7/8: the intentional bypass
  allowlist in [scripts/governance/spine_bypass_report.py](/Users/dhyana/dharma_swarm/scripts/governance/spine_bypass_report.py:46)
  is not empty, while the active-track criterion explicitly requires the empty
  shape at [docs/governance/ACTIVE_TRACK.yaml](/Users/dhyana/dharma_swarm/docs/governance/ACTIVE_TRACK.yaml:358).
- God-file risk remains real. `make module-budget` passed, but warned on
  `runtime_state.py` at 3796 lines, `autonomous_agent.py` at 1380 lines, and
  `operator_core/control_surface.py` at 1046 lines.
- Doctrine knows what "wise" means, but several runtime loops are partial or
  test-only. [CYBERNETIC_LOOP_MAP.md](/Users/dhyana/dharma_swarm/CYBERNETIC_LOOP_MAP.md:24)
  says there are 0 fully closed production loops, 1 closed in test, 7 partial,
  and 5 still "NO".

## Gate Witness

These commands were run on 2026-06-12 JST.

| Gate | Result | Notes |
|---|---|---|
| `make onboard` | pass | Single-door orientation; branch ahead 0, behind 29; 77 dirty files at first observation. |
| `make hygiene-check` | pass | `Hygiene integrity OK`. |
| `make docops-integrity` | fail | Four pre-existing drift items: markdown line count drift, two missing canonical-stack path refs, stale auto inventory. |
| `make memory-kernel-readiness-strict` | pass | status `ready`; 81 surfaces; 7 required ready; 0 missing adapters; 1 optional warning. |
| `make verifier-selfcheck` | pass | syntax, F821 blockers, test collection, onboard all passed; 11373 tests collected. |
| `make semgrep` | pass with finding | Scan succeeded with 1 blocking finding in untracked `holon/cli.py`. |
| `make module-budget` | pass with warnings | Three grandfathered/near-ceiling modules noted. |
| `make test-hygiene` | pass with known offender | `tests/test_full_loop.py:343` remains known Rule 3 offender. |
| `make uplift-guards` | pass | 8/8 guards green; fourfold warrant warns source changes lack test paths/metadata. |
| `make spine-check` | pass | Spine ownership clear. |
| `scripts/governance/verify_quality_membrane.py --json` | fail | First gate `runtime_names` fails on 19 `F821/F811` findings. |

## Layered Quality Map

### L1: Syntactic / Lint Level

Question: does code parse, import, bind names, avoid obvious lint defects, and
avoid syntactic anti-slop?

Observed state: mostly strong, but inconsistent. `make verifier-selfcheck`
passes because it checks syntax, `F821`, test collection, and onboard. The
broader membrane in `verify_quality_membrane.py` selects both `F821` and `F811`
at [scripts/governance/verify_quality_membrane.py](/Users/dhyana/dharma_swarm/scripts/governance/verify_quality_membrane.py:35)
and currently fails on redefinitions and two undefined forward-reference names
inside tests.

Strong exemplars:

- `Makefile` has explicit verification entrypoints for syntax, semgrep,
  hygiene, DocOps, module budget, MemoryKernel readiness, and agent closeout at
  [Makefile](/Users/dhyana/dharma_swarm/Makefile:139) and
  [Makefile](/Users/dhyana/dharma_swarm/Makefile:268).
- `.semgrep/dharma-anti-slop.yml` encodes concrete lint/security/ownership
  rules. Rule 1 centralizes `~/.dharma` access at
  [.semgrep/dharma-anti-slop.yml](/Users/dhyana/dharma_swarm/.semgrep/dharma-anti-slop.yml:10);
  Rule 4 blocks blanket `git add -A` / `git add .` at
  [.semgrep/dharma-anti-slop.yml](/Users/dhyana/dharma_swarm/.semgrep/dharma-anti-slop.yml:88).
- `scripts/governance/hygiene/check_hygiene_integrity.py` is stdlib-only and
  schema-checks every hygiene pattern through required fields, stages,
  detector types, severities, and blocked mutating detector commands at
  [scripts/governance/hygiene/check_hygiene_integrity.py](/Users/dhyana/dharma_swarm/scripts/governance/hygiene/check_hygiene_integrity.py:27).

Needs elevation:

- `verify_quality_membrane.py --json` fails before reaching contract and
  DocOps checks. Current findings include duplicate `__post_init__`, `pure`,
  and `bind` in `dharma_swarm/monad.py`, duplicate local imports in terminal
  command modules, and missing `OntologyRegistry` names in
  `tests/test_br_closures.py`.
- Semgrep warns that multiple rule-local `paths.exclude` entries will change
  interpretation under semgrepignore v2 unless anchored or made explicitly
  unanchored.
- One active Semgrep finding exists in new holon work:
  [holon/cli.py](/Users/dhyana/dharma_swarm/holon/cli.py:213) writes talk
  receipts directly under `~/.dharma`, which violates Rule 1 until the surface
  is declared or routed through the canonical owner.

### L2: Semantic / Contract Level

Question: do schemas, receipts, adapters, idempotency records, and request
flows agree on the meaning of data?

Observed state: strong, especially around MemoryKernel and spine tests. The
repo has 263 `@dataclass(frozen=True)` occurrences and 395 `schema_version`
mentions across `dharma_swarm`, `scripts`, `tests`, `api`, and `docs`. It also
has 430 mutable or non-frozen dataclass declarations, so the discipline is
present but not universal.

Strong exemplars:

- MemoryKernel readiness defines `READINESS_SCHEMA_VERSION`, frozen report
  rows, and summary counts in [dharma_swarm/memory_kernel/readiness.py](/Users/dhyana/dharma_swarm/dharma_swarm/memory_kernel/readiness.py:25).
  The strict CLI fails when required surfaces are not ready or adapters are
  missing at [scripts/memory_kernel_readiness.py](/Users/dhyana/dharma_swarm/scripts/memory_kernel_readiness.py:72).
- Memory context admission is read-only by construction: the module docstring
  says it does not inject prompts, write retrieval feedback, promote facts, or
  mutate memory surfaces at
  [dharma_swarm/memory_kernel/context_admission.py](/Users/dhyana/dharma_swarm/dharma_swarm/memory_kernel/context_admission.py:1).
  It also blocks rejected/superseded truth states, projections, and high-risk
  atoms by default at
  [dharma_swarm/memory_kernel/context_admission.py](/Users/dhyana/dharma_swarm/dharma_swarm/memory_kernel/context_admission.py:306).
- MemoryKernel write receipts are append-only and digest-protected. Direct
  mutation of canon, Chetana, projection, runtime, prompt, and vector surfaces
  is blocked by policy at
  [dharma_swarm/memory_kernel/write_receipts.py](/Users/dhyana/dharma_swarm/dharma_swarm/memory_kernel/write_receipts.py:21),
  with tests at [tests/test_memory_kernel_write_receipts.py](/Users/dhyana/dharma_swarm/tests/test_memory_kernel_write_receipts.py:18).
- A2A spine persistence tests assert identity agreement across
  `ExecutionIdentity`, spine receipt, runtime receipt, and idempotency record
  at [tests/test_spine_persistence_invariant.py](/Users/dhyana/dharma_swarm/tests/test_spine_persistence_invariant.py:250).

Needs elevation:

- `ACTIVE_SURFACE_MANIFEST.yaml` declares cross-layer joins at
  [ACTIVE_SURFACE_MANIFEST.yaml](/Users/dhyana/dharma_swarm/ACTIVE_SURFACE_MANIFEST.yaml:761),
  but `make onboard` still reports the request/response leg as missing:
  `request_response: A2ATaskReceipt`.
- `dharma_swarm/operator_core/a2a_task_lifecycle.py` is named as the
  request-response receipt module in the manifest at
  [ACTIVE_SURFACE_MANIFEST.yaml](/Users/dhyana/dharma_swarm/ACTIVE_SURFACE_MANIFEST.yaml:721),
  but that file is absent in this worktree. This is the sharpest L2 contract
  drift.
- The runtime contract surface is test-heavy but not yet property-heavy: only 4
  files exist under `tests/properties` out of 713 test files.

### L3: Architectural / Structural Level

Question: are ownership, module size, state surfaces, dispatch seams, and
parallel work lanes bounded enough that the system can evolve without losing
shape?

Observed state: medium-strong. Structural gates exist and pass, but several
major surfaces are grandfathered or mid-migration.

Strong exemplars:

- `ACTIVE_SURFACE_MANIFEST.yaml` owns declared surfaces and the correlation
  spine. Its doctrine states that adding a new receipt type requires adding a
  new layer entry and extending Rule 2 vocabulary at
  [ACTIVE_SURFACE_MANIFEST.yaml](/Users/dhyana/dharma_swarm/ACTIVE_SURFACE_MANIFEST.yaml:702).
- `scripts/governance/check_memory_kernel_canonical.py` prevents new
  memory-authority sprawl outside the MemoryKernel boundary with AST scanning
  and allowlisted paths at
  [scripts/governance/check_memory_kernel_canonical.py](/Users/dhyana/dharma_swarm/scripts/governance/check_memory_kernel_canonical.py:16).
- The spine bypass report classifies production `A2AServer.submit()` call sites
  into `spine-adopted`, `intentional`, `unknown`, and `non-production` at
  [scripts/governance/spine_bypass_report.py](/Users/dhyana/dharma_swarm/scripts/governance/spine_bypass_report.py:1).
- `mission_preflight.sh` fail-closes swarm launch through `dharma_swarm.dgc_cli
  mission-status` and `BLOCK_ON_FAIL=1` at
  [scripts/mission_preflight.sh](/Users/dhyana/dharma_swarm/scripts/mission_preflight.sh:58).

Needs elevation:

- Module budget is not a descent ratchet. `runtime_state.py`,
  `autonomous_agent.py`, and `operator_core/control_surface.py` are allowed by
  current grandfathering so long as they do not exceed ceilings.
- `swarm.sh` and `agent_loop.sh` are historically important but still write
  directly to `~/.dharma/shared`, embed broad prompts, and launch `claude -p`
  subprocesses from shell at [swarm.sh](/Users/dhyana/dharma_swarm/swarm.sh:31)
  and [agent_loop.sh](/Users/dhyana/dharma_swarm/agent_loop.sh:40). They need
  modern admission, receipt, and surface ownership treatment if they remain
  runtime surfaces.
- The branch has many concurrent lanes: onboard reported 28 worktrees and 288
  local branches. The doctrine says lanes are bounded by non-overlapping
  surfaces, but continuous machine enforcement is still emerging.

### L4: Coherence / Manifest Alignment Level

Question: do code, manifests, generated inventories, and doctrine say the same
thing at the same time?

Observed state: strong philosophy, mixed execution. DocOps correctly fails on
drift today.

Strong exemplars:

- `make onboard` is the single door. The Makefile states it reads active track,
  live ops, broken register, and active surface owners, and always exits 0 at
  [Makefile](/Users/dhyana/dharma_swarm/Makefile:321).
- `docs/governance/CANONICAL_DOC_STACK.md` defines the three-layer single-source
  model: intent, surface, and state at
  [docs/governance/CANONICAL_DOC_STACK.md](/Users/dhyana/dharma_swarm/docs/governance/CANONICAL_DOC_STACK.md:16).
- `docs/governance/ANTI_SLOP_RULES.md` explicitly links broad hygiene signals
  to the hard anti-slop rule set and says only mature, low-noise signals
  graduate into hard gates at
  [docs/governance/ANTI_SLOP_RULES.md](/Users/dhyana/dharma_swarm/docs/governance/ANTI_SLOP_RULES.md:8).
- `AGENT_IDENTITY_UNIFICATION.md` is honest archive metadata, not stale
  doctrine: it says the historical content moved and should not be trusted
  without re-verification at
  [AGENT_IDENTITY_UNIFICATION.md](/Users/dhyana/dharma_swarm/AGENT_IDENTITY_UNIFICATION.md:1).

Needs elevation:

- `make docops-integrity` fails on `manifest-markdown-lines`: the manifest says
  235372 markdown lines, while disk truth is 235465.
- `docs/governance/CANONICAL_DOC_STACK.md` has two backtick path references
  that DocOps treats as missing: `check_track_status.py` at line 44 and
  `render_active_track_includes.py` at line 52. They likely need
  `scripts/governance/` prefixes.
- `docs/docops/AUTO_INVENTORY.md` is stale and needs regeneration with
  `scripts/docops/check_docops_integrity.py --write-auto-sections`.
- `CYBERNETIC_LOOP_MAP.md` is useful doctrine but its last audit line is
  2026-05-20 at [CYBERNETIC_LOOP_MAP.md](/Users/dhyana/dharma_swarm/CYBERNETIC_LOOP_MAP.md:3);
  onboard already marks it as recent-but-aging depth context.

### L5: Verifiability / Invariant Level

Question: can a machine re-prove the quality claim on demand, cheaply enough
that the claim can block regressions?

Observed state: promising but under-promoted. Many checks exist. Fewer are
required, property-based, or cross-layer.

Strong exemplars:

- `tests/test_spine_adoption_dispatch.py` tests the active-track criterion that
  every dispatch emits exactly one `EvidenceReceipt` by counting actual
  `invoke_agent` traversals at
  [tests/test_spine_adoption_dispatch.py](/Users/dhyana/dharma_swarm/tests/test_spine_adoption_dispatch.py:278).
- `tests/test_spine_persistence_invariant.py` asserts retry idempotency: two
  dispatches sharing the same identity create one `a2a_task` runtime receipt at
  [tests/test_spine_persistence_invariant.py](/Users/dhyana/dharma_swarm/tests/test_spine_persistence_invariant.py:305).
- Hygiene patterns are themselves schema-checked: `REQUIRED_FIELDS`, `STAGES`,
  `DETECTOR_TYPES`, and `SEVERITIES` live at
  [scripts/governance/hygiene/check_hygiene_integrity.py](/Users/dhyana/dharma_swarm/scripts/governance/hygiene/check_hygiene_integrity.py:27).
- The hygiene lifecycle defines explicit stages and promotion criteria at
  [docs/governance/hygiene/LIFECYCLE.md](/Users/dhyana/dharma_swarm/docs/governance/hygiene/LIFECYCLE.md:3).

Needs elevation:

- `verify_quality_membrane.py` is not currently green, so it cannot yet serve
  as the quality lattice's top-level deterministic membrane.
- Hygiene lifecycle promotion is manual. The lifecycle file defines promotion
  criteria but no gate automatically promotes or flags long-clean advisory
  patterns.
- Correlation identity is asserted in focused tests, but no single gate proves
  all manifest-declared receipt layers are present and joinable in the live
  runtime store.
- Property tests are scarce compared with the surface area: 4 property files
  versus 713 test files.

### L6: Dharmic / Systemic Health Level

Question: does the code reduce harm, tell the truth, avoid waste, preserve
living context, and keep witness upstream of power?

Observed state: philosophically rich and partially wired. The strongest health
pattern is truthful self-reporting; the weakest is production closure.

Strong exemplars:

- `WHAT_IT_WANTS_TO_BECOME.md` names five falsifiable structural gaps, including
  simulated evolution, retrospective witness, unwired sub-swarms, sparse
  knowledge store, and unvalidated telos gates at
  [WHAT_IT_WANTS_TO_BECOME.md](/Users/dhyana/dharma_swarm/WHAT_IT_WANTS_TO_BECOME.md:17).
- `GNANI_LODESTONE.md` states the deepest architectural claim: the witness must
  be upstream of capability, not a downstream safety filter, at
  [GNANI_LODESTONE.md](/Users/dhyana/dharma_swarm/GNANI_LODESTONE.md:41).
- `WORLD_MODEL.md` defines the target attractor as "Dharmic Equilibrium" and
  names long-horizon flourishing, reduced suffering, regenerative capacity, and
  humility under uncertainty as the goal-function change at
  [WORLD_MODEL.md](/Users/dhyana/dharma_swarm/WORLD_MODEL.md:78).
- `CYBERNETIC_LOOP_MAP.md` is honest about runtime closure: 0 fully closed
  production loops, 1 test-closed witness loop, 7 partial loops, and 5 "NO"
  loops at [CYBERNETIC_LOOP_MAP.md](/Users/dhyana/dharma_swarm/CYBERNETIC_LOOP_MAP.md:42).

Needs elevation:

- Witness remains mostly retrospective or test-only. The "inline witness"
  doctrine is named, but `CYBERNETIC_LOOP_MAP.md` says the Witness Auditor will
  audit real actions when Loop 1 closes at
  [CYBERNETIC_LOOP_MAP.md](/Users/dhyana/dharma_swarm/CYBERNETIC_LOOP_MAP.md:33).
- Agent-generated runtime prompts in `swarm.sh`, `agent_loop.sh`, `cron_jobs.json`,
  `deep_reading_daemon.py`, and `garden_daemon.py` contain rich intent but also
  broad authority. They need the same admission and receipt discipline now
  applied to MemoryKernel.
- There is no explicit "waste budget": no invariant for stale branches,
  scaffolding, unconsumed receipts, outdated daemons, or long-lived partial
  loops.

## Prioritized Invariant Opportunities

### Q-001: Semgrep owner declaration for new `~/.dharma` surfaces

- Layers: L1, L3, L6
- Current evidence: `make semgrep` reports `holon/cli.py:213`.
- Proposed check: extend Rule 1 so any new `Path.home() / ".dharma"` access
  either routes through the canonical owner or has a matching
  `ACTIVE_SURFACE_MANIFEST.yaml` surface id.
- Implementation: Semgrep plus a small manifest cross-check script.

### Q-002: Spine bypass allowlist at zero

- Layers: L2, L5
- Current evidence: active track criterion requires an empty
  `_INTENTIONAL_BYPASS` dict, while the dict has 5 entries.
- Proposed check: once migrated, hard-fail if `_INTENTIONAL_BYPASS` is non-empty.
- Implementation: `scripts/uplift_guards/check_spine_ownership.py` or a new
  `spine_bypass_zero` guard using AST, not regex.

### Q-003: A2ATaskReceipt presence and joinability

- Layers: L2, L4, L5
- Current evidence: manifest names `dharma_swarm.operator_core.a2a_task_lifecycle`,
  but the module is absent in this worktree and onboard marks the
  request-response layer missing.
- Proposed check: assert every `correlation_spine.layers[*].receipt_module`
  imports and exposes `receipt_class`; then assert declared joins are present in
  tests or runtime probes.
- Implementation: Makefile gate plus one focused pytest.

### Q-004: Module-budget descent ratchet

- Layers: L3, L6
- Current evidence: module-budget passes while three files remain over or near
  budget.
- Proposed check: grandfathered files may not grow relative to a stored baseline
  unless the PR carries a decomposition issue and explicit operator warrant.
- Implementation: extend `scripts/governance/check_module_budget.py` with
  `--ratchet`.

### Q-005: DocOps zero-drift before quality promotion

- Layers: L4, L5
- Current evidence: `make docops-integrity` fails on 4 drift items.
- Proposed check: do not promote any quality cartography artifact to
  `active_spec` or `canon` while DocOps is red; this report can stay
  descriptive.
- Implementation: Makefile/docs gate or DocOps assertion keyed to `docs/quality`.

### Q-006: Quality membrane repair

- Layers: L1, L5
- Current evidence: `verify_quality_membrane.py` fails on `runtime_names` and
  also references a missing `tests/test_a2a_task_lifecycle.py` in its command
  list at [scripts/governance/verify_quality_membrane.py](/Users/dhyana/dharma_swarm/scripts/governance/verify_quality_membrane.py:54).
- Proposed check: make the membrane green and add it to `governance-all` only
  after it is deterministic.
- Implementation: repair F821/F811 issues, update stale test target, then wire
  the gate.

### Q-007: Hygiene lifecycle promotion assistant

- Layers: L5, L6
- Current evidence: lifecycle criteria exist; promotion is manual.
- Proposed check: a non-mutating report that finds advisory patterns with
  deterministic detectors, recent zero baselines, and named owners.
- Implementation: `scripts/governance/hygiene/promote.py --report-only` first;
  later `--apply` behind review.

### Q-008: Inline witness latency and coverage

- Layers: L6
- Current evidence: doctrine requires witness upstream of capability, but loop
  map says real action witness depends on Loop 1 closure.
- Proposed check: for every external action or runtime dispatch, record
  `action_started_at`, `witnessed_at`, `witness_status`, and fail if coverage
  falls below threshold.
- Implementation: runtime contracts plus receipt schema, then a dashboard/onboard
  projection.

## Proposed Manifest / Governance Updates

Do not apply these blindly; they should become small PRs:

- Add `docs/quality/QUALITY_CARTOGRAPHY.md`,
  `docs/quality/QUALITY_LAYER_MAP.yaml`, and
  `docs/quality/QUALITY_RECEIPT.md` to the doc ownership stack as `report`
  artifacts once DocOps is green.
- Add a `quality_cartography` surface to `ACTIVE_SURFACE_MANIFEST.yaml` only if
  another tool starts consuming `QUALITY_LAYER_MAP.yaml`. Until then, the files
  are reports, not authority.
- Add a manifest entry or reroute for `holon/cli.py` talk receipts before the
  holon package is promoted, because Semgrep Rule 1 is already catching the
  seam.
- Add `scripts/governance/verify_quality_membrane.py` to `governance-all` only
  after Q-006 is green.

## Next-Agent Handoff

1. Fix the four DocOps failures first. They are mechanical and unblock trusted
   promotion of this cartography.
2. Resolve the Semgrep finding in `holon/cli.py`: either declare the receipt
   surface in `ACTIVE_SURFACE_MANIFEST.yaml` or route talk receipts through an
   existing canonical owner.
3. Repair `verify_quality_membrane.py`: clear current `F821/F811` issues and
   replace the missing `tests/test_a2a_task_lifecycle.py` target with the
   correct current test surface.
4. Drive `_INTENTIONAL_BYPASS` in `spine_bypass_report.py` to zero and promote
   the bypass-zero invariant to a guard.
5. Implement the `correlation_spine` import-and-joinability check for every
   declared receipt layer.
6. Only after those are green, consider turning `QUALITY_LAYER_MAP.yaml` into
   a consumed surface in onboard or MemoryKernel.

## Sources And Assumptions

Sources used: live command output from the gates listed above, GitNexus repo
context and symbol queries, source reads of governance, MemoryKernel, runtime,
and doctrine files, and `make onboard` output.

Assumptions:

- Existing dirty tracked files are active user/agent work. This pass does not
  revert or alter them.
- `docs/quality/` files were untracked before this pass. This pass refreshes
  them as descriptive artifacts.
- DocOps failures are pre-existing relative to this pass because they were
  observed before editing `docs/quality/`, and the failing markdown count uses
  tracked files only.
