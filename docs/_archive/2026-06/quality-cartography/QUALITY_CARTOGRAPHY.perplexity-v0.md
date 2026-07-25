---
title: Sattva Quality Cartography
status: seed
schema_version: quality_cartography.v0
last_updated: 2026-06-12
witnessed_branch: qwen/spine-adoption
witnessed_head: ca890d117a
authoring_agent: perplexity-computer (cartographer pass)
owners:
  - docs/quality/QUALITY_CARTOGRAPHY.md (this file — narrative)
  - docs/quality/QUALITY_LAYER_MAP.yaml   (machine-readable cartography)
  - scripts/governance/verify_quality_membrane.py (deterministic membrane runner)
intent: |
  Living map of the *actual* layers of code quality in dharma_swarm.
  Feeds the Sattva Quality Lattice (invariants → exemplars → scoring → verification loops).
  This document is self-witnessing: every claim cites a file, gate, or receipt.
---

# Sattva Quality Cartography — dharma_swarm

> *"Receipts may differ by closure layer. Correlation identity must not."*
> — Correlation Spine doctrine, surfaced by `make onboard`

## 0. How to read this document

This is **the positive attractor side of quality** — the map of where the
system is already *guru-level*, where it is *grammatically correct but not
yet wise*, and where invariants must be authored to close the loop. It is
not an audit report. It is the first ring of a lattice.

Every section is grounded in a real surface in the working tree at
`~/dharma_swarm` (worktree `qwen/spine-adoption`, HEAD `ca890d117a`,
ahead 0 / behind 29 vs `origin/main`, 76 dirty files at observation time).
All gate outputs in this document were collected on 2026-06-12 (JST) via
the local Makefile.

**Companion artifacts:**

- `docs/quality/QUALITY_LAYER_MAP.yaml` — structured cartography for agents.
- `docs/quality/QUALITY_RECEIPT.md` — short receipt for onboard / orient / memory-kernel ingestion.

---

## 1. Executive summary — current quality posture

**Overall posture: structurally strong, doctrinally sophisticated, invariant-poor at the seams.**

dharma_swarm runs a governance stack that is unusually deliberate by 2026
standards: a 10-rule anti-slop register (`docs/governance/ANTI_SLOP_RULES.md`),
a 70-pattern hygiene catalogue (`docs/governance/hygiene/`,
12 AI-agent + 58 vibe-code patterns across observed → measured → advisory
→ enforced lifecycle stages), 8 Living Axioms (`docs/governance/SOVEREIGN_MANIFEST.md`),
and an active correlation spine that classifies receipts by closure layer.
`make onboard` is a single-door, evidence-projected orientation surface
that hardens against doc-decay by re-rendering from owners every call.

What the system has:

- **Real gates that fail loudly.** `make hygiene-check` and `make
  uplift-guards` pass clean; `make docops-integrity` currently fails on 4
  specific assertions (drift between docs and disk truth, which is the
  *correct* failure mode for a docops checker).
- **Frozen-dataclass receipts everywhere.** 62 `@dataclass(frozen=True)`
  uses across MemoryKernel + governance + docops, 61 `schema_version`
  declarations — receipts are versioned values, not strings.
- **Doctrine that knows its own decay.** Axiom A6 is literally "DOCS DECAY
  -- CHECK BEFORE CITING," and onboard surfaces a `[STALE Nd]` line for
  every known-decay doc.
- **Layered scoring substrate already present:** quality_gates,
  WitnessAuditor, gnani_verdicts, algedonic_events, drift_triage
  (73 zones scored by `blast × age × centrality`).

What the system lacks (and what this cartography exists to seed):

- **No first-class quality lattice.** There is no `quality/` or
  `docs/quality/` directory. This pass creates it.
- **No promotion path from advisory hygiene → invariant.** 38 of 70
  hygiene patterns are still `review_required`; nothing currently
  graduates them deterministically.
- **Receipts are not yet machine-comparable across layers.** The
  correlation spine declares the shape but the `request_response` layer
  is `[MISSING] A2ATaskReceipt`.
- **God-files persist as grandfathered budgets.** `runtime_state.py`
  (3796 lines), `autonomous_agent.py` (1380 lines),
  `operator_core/control_surface.py` (1046, near ceiling 1101) —
  Axiom A5 (NO GOD OBJECTS) is declared but not yet enforced for
  pre-existing offenders.

The cartography below names six layers of quality. Each layer has real
artifacts that already enforce parts of it, named exemplars where the
system is already guru-level, and named gaps where the next invariant
must land.

---

## 2. The six layers of quality

Quality in dharma_swarm is not a single dimension. It stacks. The model
below is empirical — each layer was found in the codebase, not invented
for this document.

| # | Layer | What it asks | Current strength (0–10) |
|---|-------|--------------|------------------------:|
| L1 | Syntactic / Lint | Does it parse? Are names bound? | 8 |
| L2 | Semantic / Contract | Do the types, schemas, and ports cohere? | 7 |
| L3 | Architectural / Structural | Are surfaces, owners, and budgets respected? | 6 |
| L4 | Coherence / Manifest Alignment | Do docs, code, and runtime tell the same story? | 7 |
| L5 | Verifiability / Invariant | Can a machine re-prove each claim? | 5 |
| L6 | Dharmic / Systemic Health | Is the code non-harming, truthful, zero-waste? | 6 |

Strength scores are read off live gate outputs and surface health
indicators; the rubric is in `QUALITY_LAYER_MAP.yaml`. They are deliberately
conservative — the goal is to *grow* them through invariant authoring,
not flatter the current state.

---

### L1 — Syntactic / Lint level

**Asks:** Does every file parse? Are imports resolvable? Are names not
re-bound, not unused, not shadowed? Are commit messages well-formed?

**Already enforced by:**

- `make verifier-selfcheck` → `syntax-check` (compiles every `.py` in
  `dharma_swarm/`, `scripts/`, `api/`, `tests/`).
- `scripts/governance/verify_quality_membrane.py` gate `runtime_names`
  runs `ruff --select F821,F811` across `dharma_swarm api scripts tests`
  ([`verify_quality_membrane.py:35-48`](#)).
- `make precommit-run` (ruff/black/isort wiring), `make lint`,
  `make lint-blockers`.
- `make go-fmt-check` + `make go-vet` for the Go modules under
  `tools/{evidence_ingestor_go, go_sdk, github_ingestor_go,
  world_signal_ingestor_go, world_scout_go}`.
- `.github/workflows/commit-lint.yml` enforces Anti-Slop Rule 7
  (`no-lf5-whole-file-restore`).

**Exemplars (where L1 is guru-level):**

1. `scripts/governance/verify_quality_membrane.py` (102 LOC, frozen
   `GateResult` dataclass, fail-fast iteration, JSON-or-plain output).
   It is a textbook example of a tiny, deterministic, composable gate
   harness.
2. `dharma_swarm/memory_kernel/readiness.py` (382 LOC) — every public
   shape is a frozen dataclass with `to_json()`, `READINESS_SCHEMA_VERSION
   = "memory_kernel_readiness.v1"`, and Counter-driven summaries.
3. `.semgrep/dharma-anti-slop.yml` — 162 lines of rules with explicit
   allowlists, TODO-promote-to-ERROR markers, and inline doctrine
   comments.

**Areas needing elevation:**

1. **No green semgrep on this machine.** `make semgrep` warns "semgrep
   not found on PATH" and skips. Phase 1 is "warn-only locally so the
   install does not block on 4 pre-existing real findings (3 shell=True +
   1 eval)." The Phase 4 promotion to ERROR for anti-slop rules is still
   pending.
2. **`syntax-check` is dirtied by `__pycache__` permissions** in some
   runs (observed: `PermissionError ... vector_store.cpython-313.pyc`).
   The compile step should isolate stale bytecode.
3. **`F841` (unused local), `F811` (redef)** are selected by the
   membrane, but `F401` (unused import) lives only in advisory `vulture`
   / `ruff F401` channels per onboard tooling hints — promote where
   noise is low.

---

### L2 — Semantic / Contract level

**Asks:** Do producers and consumers agree on the schema? Do ports,
adapters, and bridges declare and verify their contracts? Are A2A
messages, receipts, and budgets typed end-to-end?

**Already enforced by:**

- `scripts/governance/verify_quality_membrane.py` gate
  `a2a_and_module_contract_tests` runs
  `test_a2a_readiness_gate.py`, `test_a2a_task_lifecycle.py`,
  `test_module_coherence_gate.py`.
- `scripts/governance/check_module_coherence.py` (membrane gate
  `module_coherence`).
- `tests/properties/` — 3 Hypothesis property-based test files already
  exist (`test_fitness_properties.py`, `test_monad_properties.py`,
  `test_proposal_properties.py`).
- `contracts/typed_proposal_envelope.py` (the only file in `contracts/`)
  models a typed envelope schema.
- `dharma_swarm/memory_kernel/` 27 modules (atoms.py, facade.py,
  context_admission.py, write_policy.py, write_receipts.py,
  promotion_gate.py …) — receipts and admission rules are first-class
  types.

**Exemplars:**

1. **`MemoryKernel` adapter surface.** `dharma_swarm/memory_kernel/readiness.py`
   produces a `READINESS_SCHEMA_VERSION = "memory_kernel_readiness.v1"`
   report whose summary dict has ~30 explicit counts
   (ready, degraded, unavailable, missing_adapter, uncovered, optional_*,
   warning_count, …) and a `_report_status()` derivation. Strict mode
   passed in this session: `writer_count=57, missing=6,
   by_classification={approved:3, dormant:6, legacy_tolerated:10,
   review_required:38}`.
2. **`scripts/governance/spine_bypass_report.py`** classifies every
   `_server.submit(` callsite into
   `spine-adopted | intentional | unknown | non-production | test-only`,
   with an `_INTENTIONAL_BYPASS: dict[tuple[str,int], str]` allowlist
   carrying *prose reasons* for each migration deferral. Warning-only by
   design; the hard guard lives separately in
   `scripts/uplift_guards/check_spine_ownership.py`.
3. **Hypothesis PBT already adopted.** `tests/properties/` exists and is
   non-empty — the substrate for invariant-shaped tests is already there.

**Areas needing elevation:**

1. **`[MISSING] request_response: A2ATaskReceipt`** in the Correlation
   Spine (surfaced by `make onboard` § CORRELATION SPINE). The
   `dispatch_invocation` and `test_acceptance` layers have canonical
   receipts; `request_response` does not yet.
2. **Spine adoption is mid-migration.** Onboard reports the
   `runtime-truth-spine-adoption-2026-06` track at 7/8 criteria:
   `bypass_allowlist_empty` is the open criterion — the migration
   target.
3. **`contracts/` is sparse.** Only 1 module
   (`typed_proposal_envelope.py`). The directory's name promises more —
   either expand or rename.

---

### L3 — Architectural / Structural level

**Asks:** Are surfaces named and owned? Are hot paths gated? Are module
sizes bounded? Is the package shape coherent? Do worktrees stay
non-overlapping?

**Already enforced by:**

- `ACTIVE_SURFACE_MANIFEST.yaml` (768 lines) — declares state_dir,
  api_routers (19), dashboard surfaces (15), hot_path_modules (4 with
  warrants), governance_rules, health_check_registry, opportunity stages.
- `make module-budget` → `scripts/governance/check_module_budget.py`
  (Anti-Slop Rule 10) — grandfather + ceiling per module.
- `scripts/uplift_guards/run_pre_commit.py` — `hotpath-ack`,
  `kernel-integrity`, `secrets-scan`, `autonomous-destruction`,
  `mismatch-adjacency`, `assurance-diff`, `spine-ownership`,
  `fourfold-shakti-warrant`.
- `.github/workflows/structure.yml` (Rules 8 `no-root-markdown` + 9
  `no-committed-guardian-report`).
- `make spine-check` → `scripts.uplift_guards.check_spine_ownership`.
- Living Axioms A1 (NO FLAT-PACKAGE GROWTH), A2 (NO DUPLICATE
  IMPLEMENTATIONS), A3 (NO UNDOCUMENTED SEAMS), A5 (NO GOD OBJECTS),
  A7 (NO CIRCULAR IMPORTS).

**Exemplars:**

1. **`ACTIVE_SURFACE_MANIFEST.yaml`** is a load-bearing surface: it is
   read by the dashboard, by agents, by the hot-path ack guard, and by
   semgrep Rule 1 (state_dir ownership). It encodes warrants
   per hot-path module (`swarm.py`, `orchestrator.py`, `dgc_cli.py`,
   `telic_seam.py`) — *behavioral* contracts, not just structural ones.
2. **The `holon/` package** is a clean nested module with its own
   `pyproject.toml`, `README.md`, `cli.py`, `holon_bridge.py`,
   `holon_runtime.py`, `inbox.py`, `ports.py`, `pulse.py`,
   plus child packages `holon/memory_kernel/` and `holon/organs/`. It
   models packageability inside a monorepo.
3. **The hygiene catalogue** (`docs/governance/hygiene/patterns/`,
   `LIFECYCLE.md`, `CATALOGUE.md`, `AUDIT_PROMPT.md`,
   `AI_AGENT_GOVERNANCE.md`) is itself a structurally-sound mini-system:
   `check_hygiene_integrity.py` enforces REQUIRED_FIELDS, STAGES,
   DETECTOR_TYPES, SEVERITIES on every pattern file. Hygiene patterns
   are themselves first-class objects with schemas.

**Areas needing elevation:**

1. **God-files persist as grandfathered budgets.** Per
   `make module-budget`:
   - `dharma_swarm/runtime_state.py`: 3796 lines (over budget,
     grandfathered).
   - `dharma_swarm/autonomous_agent.py`: 1380 lines (over budget,
     grandfathered).
   - `dharma_swarm/operator_core/control_surface.py`: 1046 lines
     (grandfather=1001, ceiling=1101 — *approaching the budget*).
   Axiom A5 is declared, not yet load-bearing for these surfaces.
2. **287 local branches across 28 worktrees** (per onboard § PARALLEL
   WORK LANES). Lane families: other=179, pr/review/merge=61,
   cleanup/repair=24. The boundary policy ("parallel lanes are allowed;
   non-overlapping surfaces are the boundary") is doctrine but is not
   yet machine-enforced as a continuous gate.
3. **Drift triage** reports 73 zones, top 5 at `blast=3.0 age=7d`
   (Evolution / Telos Gates / BoardStore Facade / Observatory / Runtime,
   all `[partial]`). These are L3 gaps awaiting closure.

---

### L4 — Coherence / Manifest Alignment level

**Asks:** Do `WHAT_IT_WANTS_TO_BECOME.md`, `WORLD_MODEL.md`,
`LIVING_LAYERS.md`, `GNANI_LODESTONE.md`, `CYBERNETIC_LOOP_MAP.md`,
`ACTIVE_SURFACE_MANIFEST.yaml`, the dashboard, and the running code
tell the *same* story?

**Already enforced by:**

- `make onboard` (single-door v2) — re-renders from owners every call.
- `make docops-integrity` → `scripts/docops/check_docops_integrity.py` —
  asserts metrics in docs match disk reality, that referenced paths
  exist, that auto-sections are not stale.
- `scripts/governance/check_pr_coherence_delta.py` (`make pr-gate`
  pipeline) — coherence delta on every PR.
- `make ci-truth`, `make spine-check`.
- Onboard's `KNOWN-DECAY DOCS — verify before citing` section
  (Axiom A6) tags each watched doc with `[recent Nd]` / `[STALE Nd
  since last touch]`.
- `docs/governance/CANONICAL_DOC_STACK.md` declares the doc ownership map.

**Exemplars:**

1. **`CYBERNETIC_LOOP_MAP.md`** is a closure ledger: 13 loops with
   `Closed? / Remaining Blocker`, evidence rows from `~/.dharma/state/`
   counters (sessions=27, task_claims=42 failed, witness/*.jsonl=1013
   entries, etc.). Loop-by-loop "What Changed Since April 4" diff shows
   3 BLOCKERs resolved with commit hashes.
2. **`make onboard` output** is itself an exemplar of self-witnessing:
   it lists portfolio criteria as `✓ [file_exists] X` / `✗ [file_contains]
   Y — pattern not found in scripts/.../foo.py`, with the *path*
   to the failing assertion in the message.
3. **`WHAT_IT_WANTS_TO_BECOME.md`** declares 5 named Gaps and 7 named
   Fangs, each falsifiable, each with a file path or an external
   benchmark. The doctrine reads like a spec, not prose.

**Areas needing elevation (the 4 current docops failures):**

1. `manifest-markdown-lines`: doc claims 235372 markdown lines;
   `markdown_total_lines` on disk = 235465. Drift = +93 lines.
2. `docs/governance/CANONICAL_DOC_STACK.md:44` references
   `check_track_status.py` — file missing at that relative path.
3. `docs/governance/CANONICAL_DOC_STACK.md:52` references
   `render_active_track_includes.py` — same.
4. `docs/docops/AUTO_INVENTORY.md` has stale generated content; needs
   `check_docops_integrity.py --write-auto-sections`.

These are *correct* docops failures: the system is telling the truth
about its drift. The cartography proposes to keep them visible at L4
rather than silence them.

Other L4 risks: `KNOWN-DECAY DOCS` flags
`docs/plans/NEXT_10_SUBSTRATE_TODO.md` (38d), `ONTOLOGY_NATIVE_OPERATOR_BRIEF_MASTER_SPEC.md`
(42d), `HANDOFF_ONTOLOGY_NATIVE_OPERATOR_BRIEF.md` (42d), and
`reports/audit/end_to_end/000_MASTER_COHERENCE_SYNTHESIS.md` (46d).

---

### L5 — Verifiability / Invariant level

**Asks:** Can a machine re-prove each quality claim, on every commit,
without human eyes?

**Already enforced by:**

- `scripts/uplift_guards/run_pre_commit.py` — runs 8 named guards;
  observed all-green this session.
- `tests/properties/` (Hypothesis PBT) — 3 property files already.
- `scripts/governance/check_test_hygiene.py` (Rules 3 + 5).
- `scripts/memory_kernel_readiness.py --strict --fail-on-missing-adapter`
  passed in this session.
- `scripts/memory_context_eval.py --run-default-cases
  --fail-on-hard-failure` runs 11 named cases (current_context_redaction,
  observed_runtime_admitted, …) with `expected_min_warnings`.
- `make verifier-selfcheck` chains `syntax-check` →
  `precommit-run` (composable membrane).

**Exemplars:**

1. **`memory_context_eval.py` case files** — each case declares
   `expected_admitted_atoms`, `expected_hard_failures`,
   `expected_min_warnings` and a `title`/`description`. This is property
   testing for memory admission, expressed declaratively.
2. **`spine_bypass_report.py`** is read by an active-track criterion:
   the portfolio gate
   `[file_contains] bypass_allowlist_empty` looks for
   `^_INTENTIONAL_BYPASS: dict[tuple[str, int], str] = {\s*}` —
   an invariant on the allowlist itself reaching zero.
3. **`check_hygiene_integrity.py`** enforces a schema *on the hygiene
   patterns themselves* — REQUIRED_FIELDS, STAGES,
   DETECTOR_TYPES, SEVERITIES, BLOCKED_COMMAND_RE for detectors.
   This is a meta-invariant (invariant on the invariant catalogue).

**Areas needing elevation:**

1. **Promotion path is implicit.** Hygiene LIFECYCLE.md exists but the
   `observed → measured → advisory → enforced` graduation is manual; an
   invariant that auto-promotes when a baseline holds for N days at
   zero would close this loop.
2. **Receipts are not yet cross-layer-comparable.** The Correlation
   Spine declares the identity (`correlation_id` / `trace_id`) but no
   single gate currently asserts "for every dispatch_invocation
   `trace_id`, exactly one `test_acceptance` row exists with the same
   `correlation_id`."
3. **Property tests are scarce relative to surface.** 3 PBT files vs
   666 test files; the highest-value invariants (idempotency on A2A
   submit, monotonicity of evolution archive, frozen-dataclass
   equality) are mostly unwritten.

---

### L6 — Dharmic / Systemic Health level

**Asks:** Is the system non-harming (ahimsa), truth-telling (satya),
non-wasting (zero-slop), and aware of itself (samyak darshan)? Does the
code know what it is doing while it does it?

**Already enforced by:**

- WitnessAuditor (`dharma_swarm/auditor.py`, 1,013 entries observed in
  `~/.dharma/witness/*.jsonl` per `CYBERNETIC_LOOP_MAP.md` § Evidence
  table) — BLOCKED 230 destructive filesystem commands (AHIMSA gate),
  PASSED 444, WARN 4.
- `scripts/uplift_guards/run_pre_commit.py`
  `autonomous-destruction` guard.
- `algedonic_activation.py` — algedonic events (48 observed) feed
  organism heartbeat.
- The `gnani_verdicts` channel (18 verdicts observed).
- `dharma_swarm/anekanta_gate.py` (multi-perspective gate).
- `GNANI_LODESTONE.md` + `LIVING_LAYERS.md` doctrine.

**Exemplars:**

1. **`.semgrep/dharma-anti-slop.yml` Rule 4** (`scripts-no-git-add-all`,
   ERROR severity) is a textbook ahimsa-in-code rule: blanket-staging
   can quietly carry away `.env`, secrets, or another author's
   in-flight work. The patterns are exhaustive across `$RUN(...)`,
   `asyncio.create_subprocess_exec(...)`.
2. **`AGENT_IDENTITY_UNIFICATION.md`** is now 4 lines that say only
   *"Archived: snapshot, do not trust without re-verification."*
   pointing at `docs/_archive/2026-04/...`. This is satya in
   documentation — an archived surface telling the reader it is
   archived, with a stable redirect.
3. **The hygiene LIFECYCLE** — patterns must start at `observed`,
   accumulate measurements, become `advisory`, and only graduate to
   `enforced` once noise is low. This is zero-waste applied to
   governance itself.

**Areas needing elevation:**

1. **In-flight witness still partial.** Per CYBERNETIC_LOOP_MAP.md
   Loop 6, WitnessAuditor is "S3* — retrospective audit" and "operates
   on test data from pytest; will audit real agent actions when Loop 1
   closes." The samyak darshan gap from `GNANI_LODESTONE.md` is real
   and named.
2. **No code-level ahimsa metric.** Destructive-command blocking is
   binary; there is no scoring of "how much disposable scaffolding,
   half-built files, or dead branches the agent left behind" — the
   slop side of zero-waste.
3. **`BROKEN_REGISTER.md`** lists 5 open items
   (BR-003 self-evolution apply gate, BR-004 cron split-brain, BR-005
   algedonic stream degenerate steady-state, plus two not surfaced in
   onboard's top-3). These are dharmic surfaces (truthful logs of
   what is broken) that drift unless re-verified.

---

## 3. Initial gap analysis — prioritized invariant opportunities

Each gap below is keyed `Q-NNN`, ordered by leverage (impact × testability).
Each names the layer it belongs to, the existing surface that should
*host* the invariant, and the proposed implementation tool.

### Q-001 — Allowlist-at-zero invariant for spine bypass (L2 + L5)

**Status:** open, named in active track `runtime-truth-spine-adoption-2026-06`.
**Surface:** `scripts/governance/spine_bypass_report.py:_INTENTIONAL_BYPASS`.
**Current:** dict has 5 entries (a2a_bridge, node_gateway×2, a2a_client,
nats_transport). Track criterion checks for the *empty* shape.
**Invariant:** `len(_INTENTIONAL_BYPASS) == 0` AND every entry, when
present, has a reason string containing a migration target.
**Implementation:** AST check in `scripts/uplift_guards/` — promote
existing read into a hard guard once the allowlist is empty.

### Q-002 — Correlation-id round-trip invariant (L2 + L5)

**Status:** open. `[MISSING] request_response: A2ATaskReceipt` per
onboard.
**Surface:** `dharma_swarm/operator_core/a2a_task_lifecycle.py` +
`dharma_swarm/spine/receipt.py`.
**Invariant:** For every `EvidenceReceipt(trace_id=T,
correlation_id=C)`, there exists exactly one
`A2ATaskReceipt(correlation_id=C)` and exactly one
`closure_v0` row with the same correlation_id.
**Implementation:** Hypothesis PBT in `tests/properties/test_correlation_spine_properties.py`
backed by a sqlite probe of `~/.dharma/state/runtime.db` receipt_json
DDL.

### Q-003 — Module-budget descent invariant (L3)

**Status:** open. 3 modules over budget, grandfathered.
**Surface:** `scripts/governance/check_module_budget.py` +
`.github/workflows/module-budget.yml`.
**Invariant:** For each grandfathered module, line count is
non-increasing across commits (the grandfather can only *shrink*, never
grow).
**Implementation:** add `--ratchet` mode that reads the prior ceiling
from `.github/workflows/module-budget.yml` and fails if the new value
is higher.

### Q-004 — DocOps zero-drift invariant (L4)

**Status:** open, 4 failures observed this session.
**Surface:** `scripts/docops/check_docops_integrity.py`.
**Invariant:** `make docops-integrity` exits 0 on `main`.
**Implementation:** Already exists; the gap is that the failures are
not currently *blocking* `make ci-truth`. Promote to required-check.

### Q-005 — Hygiene auto-promotion invariant (L5 + L6)

**Status:** open. 38 patterns `review_required`, 27 `measured`,
28 `observed`, 15 `advisory`.
**Surface:** `docs/governance/hygiene/LIFECYCLE.md` + `patterns/*.yaml`
`stage` field.
**Invariant:** A pattern at `measured` for ≥30 days with `findings == 0`
auto-promotes to `advisory`; an `advisory` pattern at `findings == 0`
for ≥30 days auto-promotes to `enforced`. Conversely, an `enforced`
pattern with `findings > 0` for ≥7 days demotes to `advisory` with a
`BR-NNN` row appended.
**Implementation:** new `scripts/governance/hygiene/promote.py` (file
already exists as a stub) extended with a deterministic ratchet driven
by `baselines/YYYY-MM-DD.txt`.

### Q-006 — Frozen-receipt invariant (L1 + L2 + L6)

**Status:** open. 62 frozen dataclasses already exist; no gate asserts
that *new* dataclasses in `dharma_swarm/memory_kernel/`,
`scripts/governance/`, `scripts/docops/`, `dharma_swarm/spine/` use
`frozen=True`.
**Surface:** new semgrep rule under `.semgrep/dharma-anti-slop.yml`.
**Invariant:** every `@dataclass(...)` in those paths includes
`frozen=True` AND the class has a `to_json` (or
`asdict`-compatible) projection.
**Implementation:** semgrep rule (WARNING → ERROR after baseline scan).

### Q-007 — Stale-doc invariant (L4 + L6)

**Status:** open. 4 docs currently `[STALE]` in onboard's known-decay
list (38–46 days).
**Surface:** `scripts/governance/agent_onboard.py` known-decay section.
**Invariant:** No known-decay doc may exceed `stale_threshold_days`
without an open `BR-NNN` row in `docs/state/BROKEN_REGISTER.md` that
references it.
**Implementation:** extend `check_docops_integrity.py` to cross-check.

### Q-008 — Inline-witness latency invariant (L6)

**Status:** open. `GNANI_LODESTONE.md` and
`WHAT_IT_WANTS_TO_BECOME.md` Fang 2 name this. Loop 6 is "S3* —
retrospective."
**Surface:** `dharma_swarm/auditor.py` + a new
`dharma_swarm/witness_inline.py`.
**Invariant:** Every agent action emits a pre-action witness verdict
within ≤200ms; missing verdicts within window are an algedonic event.
**Implementation:** runtime contract enforced by
`tests/test_witness_inline_latency.py` (synthetic) + a runtime gauge in
`organism_memory`.

The first five (Q-001 through Q-005) are the proposed **first
machine-checkable invariants**; Q-006 and Q-007 are tractable next; Q-008
is the deepest and feeds the Gnani layer roadmap directly.

---

## 4. Cross-layer signals worth preserving as the lattice grows

These were noticed during the cartography pass and should not be lost:

- **Severity grading is already a lattice signal.** The hygiene system
  has `SEVERITIES = {informational, structural, security, correctness,
  performance, distributed, operational}`. Quality scoring can lift
  these directly.
- **Stage lifecycle is already a lattice signal.**
  `STAGES = {observed, measured, advisory, enforced, resolved,
  archived}`. The Sattva lattice can adopt this verbatim.
- **The drift_triage `priority_score = blast × age × centrality`**
  formula in `dharma_swarm/dhyana/drift_triage.py` is the embryonic
  scoring function for the lattice. 73 zones already scored.
- **`agent-build-preflight` / `agent-build-closeout`** are the natural
  session-bracketing hooks. Quality cartography should be written-from
  and read-into them.

---

## 5. Self-witnessing — sources and assumptions

**Sources (every claim in this doc traces to one of these):**

1. `make onboard` output, 2026-06-12 (saved on Mac at
   `/tmp/onboard.txt`, 390 lines).
2. `make hygiene-check` → exit 0, "Hygiene integrity OK".
3. `make docops-integrity` → exit 1, 4 named failures (reproduced
   verbatim in §2 / L4).
4. `make memory-kernel-readiness-strict` → exit 0, 1612 lines, summary
   `writer_count=57, present=51, missing=6, by_classification
   {approved:3, dormant:6, legacy_tolerated:10, review_required:38}`.
5. `make verifier-selfcheck` → exit 2 (sandbox `__pycache__` permission
   issue on `vector_store.cpython-313.pyc`, *not* a code defect — a
   sandbox state issue).
6. `make semgrep` → "semgrep not found on PATH — skipping" (Phase 1
   warn-only locally).
7. `make uplift-guards` → all 8 guards `✓` (kernel-integrity,
   secrets-scan, autonomous-destruction, hotpath-ack,
   fourfold-shakti-warrant, mismatch-adjacency, assurance-diff,
   spine-ownership).
8. `make spine-check` → exit 0, "spine ownership clear (importable +
   all sqlite users declared)".
9. `make module-budget` → exit 0, 3 grandfather warnings.
10. `make test-hygiene` → exit 0, 1 known offender
    (`tests/test_full_loop.py:343 state = RuntimeStateStore()`).
11. Direct reads of: `.semgrep/dharma-anti-slop.yml`,
    `ACTIVE_SURFACE_MANIFEST.yaml`, `WHAT_IT_WANTS_TO_BECOME.md`,
    `WORLD_MODEL.md`, `LIVING_LAYERS.md`, `GNANI_LODESTONE.md`,
    `CYBERNETIC_LOOP_MAP.md`, `AGENT_IDENTITY_UNIFICATION.md`,
    `dharma_swarm/memory_kernel/readiness.py`,
    `dharma_swarm/memory_kernel/facade.py`,
    `scripts/governance/verify_quality_membrane.py`,
    `scripts/governance/spine_bypass_report.py`,
    `scripts/governance/hygiene/check_hygiene_integrity.py`,
    `scripts/governance/check_module_budget.py`, `swarm.sh`,
    `agent_loop.sh`.

**Assumptions explicitly declared:**

- Strength scores in §2 are read-off-evidence judgments by this agent,
  not measurements. They MUST be re-scored on each cartography pass.
- "Dharmic / Systemic Health" maps Jain/yogic terms to concrete code
  surfaces. Mappings are seeds, not creed. The next agent may
  rename `dharmic` to `axiological` or any other term if it serves
  clarity — only the *layer* is load-bearing.
- The directory `docs/quality/` did not exist at session start. This
  cartography proposes its creation. If a swarm-wide decision instead
  places quality under `quality/` (root), move both this file and
  `QUALITY_LAYER_MAP.yaml` together to preserve the pair.

---

## 6. Proposed updates to existing governance surfaces

These are *proposals*, not edits. The next agent decides.

1. **`ACTIVE_SURFACE_MANIFEST.yaml`** — add a `quality_lattice` section
   declaring the 6 layers and the two new files. Sketch:
   ```yaml
   quality_lattice:
     schema_version: quality_layer_map.v0
     map: docs/quality/QUALITY_LAYER_MAP.yaml
     narrative: docs/quality/QUALITY_CARTOGRAPHY.md
     receipt: docs/quality/QUALITY_RECEIPT.md
     layers:
       - L1_syntactic
       - L2_semantic_contract
       - L3_architectural
       - L4_coherence_manifest
       - L5_verifiability_invariant
       - L6_dharmic_systemic_health
   ```
2. **`docs/governance/CANONICAL_DOC_STACK.md`** — fix the two missing
   references (`check_track_status.py`,
   `render_active_track_includes.py`) flagged by `make docops-integrity`,
   then add a row for `docs/quality/` as canonical.
3. **`Makefile`** — add a `quality-cartography` target that runs the
   five `Q-00x` candidate invariants in `--dry-run` mode and prints a
   per-layer score line.
4. **`.semgrep/dharma-anti-slop.yml`** — once Q-006 baseline is taken,
   add the frozen-receipt rule (WARNING; promote-to-ERROR after one
   stable week).

---

## 7. Next-agent handoff

The next quality-focused agent (human or AI) should:

1. **Land `docs/quality/` itself.** This file plus
   `QUALITY_LAYER_MAP.yaml` plus `QUALITY_RECEIPT.md` form the seed.
   Run `make docops-integrity --write-auto-sections` after landing so
   the AUTO_INVENTORY refresh and the directory creation register
   together.
2. **Fix the 4 docops failures.** They are listed verbatim in §2/L4.
   This closes Q-004's prerequisite.
3. **Take baselines for Q-006 and Q-007.** Run a scan that counts
   `@dataclass(...)` *without* `frozen=True` in the four target paths;
   list every known-decay doc whose age exceeds the threshold without an
   open BR row. Save under `reports/governance/quality_baselines_2026-06-12.json`.
4. **Author the first Hypothesis property test for Q-002.** Even a
   trivial `assert correlation_id_roundtrip(receipt)` is a real
   invariant; the goal is to get the file
   `tests/properties/test_correlation_spine_properties.py` born.
5. **Decide naming.** If `dharmic` layer is contested, propose a rename
   PR — but keep the *layer* (L6) intact.
6. **Wire `quality-cartography` into `agent-build-closeout`.** The
   closeout is the right time to re-render the receipt.
7. **Drain `_INTENTIONAL_BYPASS` one entry at a time** — Q-001 is the
   highest-leverage invariant in the system right now because closing
   it closes the active track `runtime-truth-spine-adoption-2026-06`
   AND makes the spine itself a load-bearing invariant.

**Blockers / human collaboration needed:**

- The L6 inline-witness invariant (Q-008) is conceptually deep and
  touches `auditor.py`, the algedonic stream, and Loop 6. Recommend an
  explicit human sit-down before authoring; this is the Gnani-layer
  question from `GNANI_LODESTONE.md` and must not be reduced to a
  latency metric without the surrounding philosophy.
- Promotion of `.semgrep/dharma-anti-slop.yml` Rule 6 (`providers-canonical`)
  to ERROR is gated on fixing `dharma_swarm/autonomous_agent.py:468`;
  that fix is also tangled with the 1380-line god-file (Q-003), so the
  refactor must come first.

---

## 8. Citations

- `make onboard` output (2026-06-12 JST) — captured in
  `~/dharma_swarm` working tree at `/tmp/onboard.txt`.
- [`.semgrep/dharma-anti-slop.yml`](.semgrep/dharma-anti-slop.yml) —
  10-rule register, lines 1–162.
- [`ACTIVE_SURFACE_MANIFEST.yaml`](ACTIVE_SURFACE_MANIFEST.yaml) —
  schema_version 2, last_updated 2026-05-20.
- [`docs/governance/ANTI_SLOP_RULES.md`](docs/governance/ANTI_SLOP_RULES.md) —
  10-rule table with status column.
- [`docs/governance/SOVEREIGN_MANIFEST.md`](docs/governance/SOVEREIGN_MANIFEST.md) —
  Living Axioms A1–A8.
- [`docs/governance/hygiene/`](docs/governance/hygiene/) — 70-pattern
  catalogue, LIFECYCLE.md, CATALOGUE.md.
- [`dharma_swarm/memory_kernel/readiness.py`](dharma_swarm/memory_kernel/readiness.py) —
  `READINESS_SCHEMA_VERSION = "memory_kernel_readiness.v1"`.
- [`scripts/governance/verify_quality_membrane.py`](scripts/governance/verify_quality_membrane.py) —
  102-line deterministic membrane runner.
- [`scripts/governance/spine_bypass_report.py`](scripts/governance/spine_bypass_report.py) —
  classified bypass register, `_INTENTIONAL_BYPASS` allowlist.
- [`scripts/governance/hygiene/check_hygiene_integrity.py`](scripts/governance/hygiene/check_hygiene_integrity.py) —
  meta-invariant on pattern schema.
- [`CYBERNETIC_LOOP_MAP.md`](CYBERNETIC_LOOP_MAP.md) — 13-loop closure
  ledger.
- [`GNANI_LODESTONE.md`](GNANI_LODESTONE.md), [`WHAT_IT_WANTS_TO_BECOME.md`](WHAT_IT_WANTS_TO_BECOME.md),
  [`LIVING_LAYERS.md`](LIVING_LAYERS.md), [`WORLD_MODEL.md`](WORLD_MODEL.md) —
  doctrine surfaces.
- [`docs/state/BROKEN_REGISTER.md`](docs/state/BROKEN_REGISTER.md) — 23
  items total, 5 open, BR-NNN schema.

---

*Authored by: perplexity-computer cartographer pass (2026-06-12).
Re-witness on every `make agent-build-closeout`.*
