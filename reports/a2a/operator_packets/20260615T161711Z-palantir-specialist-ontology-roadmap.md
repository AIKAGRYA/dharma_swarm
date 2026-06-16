# Prompt for Palantir Specialist Agent

**Operator:** John Shrader (`@AmitabhainArunachala`) · dharma_swarm lead
**Routing agent:** `codex` via Palantir Pilot A2A worker (`external_worker_evidence_only`)
**Date:** 2026-06-16 (Asia/Tokyo)
**Repo:** `AmitabhainArunachala/dharma_swarm`
**Your runtime:** local CLI sub-agent with filesystem read on the repo working tree

## 0. Your charter for this task

You are the **Palantir Specialist** in this repo. You have prior knowledge of Palantir Foundry's Object/Link/Action ontology, Pipeline Builder/Code Workbook lineage, branching, ACL/policy, write-back, Functions, and the Gotham operational doctrine (entities, events, links, sources, derived intelligence, audit). Your job in this turn is **not** to advise toward a Palantir-shaped clone. It is to produce a **graduated, phased upgrade roadmap** that takes `dharma_swarm` from its current shape toward a Palantir-grade *semantic ontology* without breaking what already ships, and without triggering the AI-driven name-drift failure mode this repo just diagnosed.

Produce **Phase 0 -> Phase N**, each phase carrying:

1. **Scope** — what changes, what does not
2. **Acceptance criteria** — receipts/tests/lints that prove the phase shipped
3. **Blast radius** — files touched, deprecations introduced, migration cost
4. **Evidence to produce** — concrete artifacts such as lane entries in `ACTIVE_TRACK.yaml`, ADRs in `docs/architecture/ADRs/`, schemas, tests
5. **Exit criterion to next phase** — what must be true on disk before phase N+1 begins
6. **Why this phase before the next** — the dependency rationale

Phases must be graduated, not cliff-edged. The operator works mobile-first, leads many concurrent PRs, and runs a multi-agent system that ships under continuous integration. A phase that requires a stop-the-world rewrite is rejected. A phase that converts one already-shipped concept into Palantir-grade primitives with a deprecation shim is correct shape.

## 1. Hard constraints

### 1.1 Authority model

- The invoking agent is Stage 1 evidence-only: authors PRs, no merge, no governance writes.
- You may recommend changes to governance files but flag them clearly; the operator applies governance changes manually.
- 3-day off-limits files are read-only for recommendations: `docs/governance/ACTIVE_TRACK.yaml`, `docs/governance/ACTIVE_SURFACE_MANIFEST.yaml`, `docs/governance/SOVEREIGN_MANIFEST.md`, `docs/governance/CANONICAL_DOC_STACK.md`, `docs/governance/ANTI_SLOP_RULES.md`, `docs/governance/BUILD_SESSION_ENTRYPOINT.md`, `docs/governance/MEGAFILE_INDEX.md`, `docs/architecture/THE_ORGANISM.md`, `docs/architecture/NORTH_STAR.md`, `CLAUDE.md`, `README.md`, `docs/architecture/INTERFACE_MISMATCH_MAP.md`. Any change to them goes in an operator-action subsection.

### 1.2 Name-drift constraint

The repo has just diagnosed that AI-driven name drift causes most cross-doc confusion. Examples:

- "Operator Brief" / "Insight Brief" / "Daily Insight Brief" / "Ontology-Native Operator Brief" / "Morning brief"
- "Substrate" / "Ontology-Native" / "Runtime-Truth" / "Spine-Adoption"
- "Dharma Radar" vs `world_radar/`
- Two `world_radar/` packages on disk

The roadmap must not introduce new synonyms. When naming a Palantir-shaped concept, either:

(a) reuse an existing name on disk, such as `ArtifactRecord` or `MemoryEdge`;
(b) adopt Palantir's term directly, such as `ObjectType`, `LinkType`, or `ActionType`, with a one-sentence definition and an explicit introduction flag; or
(c) say `naming TBD by NAMING_CANON.md`.

Do not generate a new bespoke name for an existing concept.

### 1.3 No sprawling audit docs

The deliverable is a roadmap the operator can execute against, not a giant review-me document. Be opinionated. Pick winners. Where you genuinely cannot decide without operator input, say so explicitly with one line per blocker.

### 1.4 No wholesale replacement

Do not replace `runtime_state.py`, `ontology.py`, `ontology_hub.py`, or `ontology_runtime.py` wholesale. Phases convert in place with deprecation shims, never via parallel rewrite.

## 2. What to read before answering

Read these files in this order:

1. `docs/governance/ACTIVE_TRACK.yaml`
2. `docs/architecture/ADRs/ADR-008-ontology-api-name-grammar.md`
3. `dharma_swarm/runtime_state.py` lines 483-700
4. `dharma_swarm/ontology.py`, `dharma_swarm/ontology_hub.py`, `dharma_swarm/ontology_runtime.py`, `dharma_swarm/ontology_query.py`, `dharma_swarm/ontology_adapters.py`, `dharma_swarm/ontology_agents.py`, `api/routers/ontology.py`
5. `dharma_swarm/operator_brief/`
6. `dharma_swarm/guardian_crew.py` and `dharma_swarm/operator_brief/watchdog.py`
7. `reports/audit/end_to_end/000_MASTER_COHERENCE_SYNTHESIS.md`
8. `docs/state/BROKEN_REGISTER.md`
9. `docs/state/CYBERNETIC_LOOP_MAP.md`
10. `dharma_swarm/world_radar/` and `dharma_swarm/operator_core/world_radar/`

Then run:

```bash
grep -rIlE "class.*Record|class.*Artifact|@dataclass" dharma_swarm/ --include="*.py" | head -40
grep -nE "^class " dharma_swarm/runtime_state.py
ls dharma_swarm/ontology* api/routers/ontology*
git log --oneline -20 -- dharma_swarm/ontology.py dharma_swarm/ontology_runtime.py
wc -l dharma_swarm/runtime_state.py dharma_swarm/ontology*.py
find docs/architecture/ADRs -name "*.md" | sort | tail -10
```

Verify assumptions against what you find. Do not trust this prompt over the filesystem.

## 3. Current repo state snapshot to triple-check

Triple-check these facts before relying on them:

- Active lanes serving `substrate-nativeness` were reported as: `runtime-truth-reconciliation-2026-06`, `runtime-truth-nats-2026-06`, `runtime-truth-spine-adoption-2026-06`, `runtime-truth-spine-2026-06`, `loop-closure-2026-06`, `orientation-graph-2026-06`, `composer-holon-spine-longrun-2026-06`.
- Open Broken Register entries were reported as: `BR-003`, `BR-004`, `BR-005`, `BR-013`, `BR-014`.
- Code ObjectType-shaped classes were reported in `dharma_swarm/runtime_state.py`: `ArtifactRecord`, `MemoryEdge`, `MemoryFact`, `OperatorAction`, `RuntimeReceipt`, `SessionEventRecord`, `IdempotencyRecord`.
- Naming-canon work is in flight in a separate lane/session.
- PR #609 was reported as onboard-doc refresh with 5 commits pushed.

## 4. Conversational arc

The operator wants a context-rich prompt to the Palantir Specialist agent asking what the repo should do, after reading the filesystem and Palantir specialization, to slowly upgrade in graduated steps to Palantir-grade semantic ontology.

Lessons to honor:

1. AI agents drift names every session.
2. Audit-style deliverables that hand decisions back to the operator are the same failure mode as drift.
3. Stage-1 agents recommend and produce evidence, not merge or mark governance complete.
4. The operator is mobile-first and ships continuously.
5. The previous top-5 ROI moves were PR #609 finalization, spine-adoption regex fix, loop-closure receipts, BR re-verification, and an architecture-decision issue; the roadmap may subsume or reorder them but must say why.

## 5. Deliverable

A single Markdown document, target 800-1,500 lines, structured as:

### Section 0 — Triple-check log

One-line bullets per fact in section 3: confirmed, refuted, or changed. If refuted or changed, state the new ground truth.

### Section 1 — Palantir-grade target state, in dharma_swarm's own vocabulary

Define what Palantir-grade semantic ontology means for `dharma_swarm`, with a mapping table:

`Palantir primitive | dharma_swarm current | gap`

Use Palantir primitives: ObjectType, LinkType, ActionType, Function, Code Workbook, Pipeline, Branch, Permission, Write-back, Lineage.

### Section 2 — Phased roadmap, Phase 0 -> Phase N

Likely 4-7 phases. Each phase must include Scope, Acceptance, Blast Radius, Evidence, Exit, Dependency Rationale. Phase 0 must be doable this week with Stage-1 authority. The final phase may require operator-tier work and must be flagged explicitly.

For each phase also note active lanes served or extended, BR entries addressed or unblocked, and which prior top-5 ROI move it subsumes.

### Section 3 — Cross-cutting concerns

Address:

- Lineage
- Branching/write-back
- Policy/ACL
- Functions vs agents
- The two `world_radar/` packages
- The six-file ontology surface

### Section 4 — Anti-pattern register

3-7 things the operator must not do in pursuit of Palantir-grade, each with one sentence for the anti-pattern and one sentence for why it hurts `dharma_swarm`.

### Section 5 — Open decisions

One line each, at most 7 items.

### Section 6 — Recommended first commit

A copy-pasteable starter commit the operator or Stage-1 agent can land today. File paths, content sketches, lane entry or "no new lane needed", acceptance lint. Keep it under 500 LOC of new content, one ADR maximum.

## 6. Tone and style

Opinionated. Concrete. Spare. Honest. No emojis. No exclamation marks. Plain headers.

## 7. Success

The operator reads the output once on a phone and can start Phase 0 within 30 minutes.
