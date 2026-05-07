# BUILD SESSION ENTRYPOINT

**Status:** canonical pointer layer (no new truths)
**Owner of:** the read-order and current-track pointers every agent should hit before a build session.
**Subordinate to:** [`CLAUDE.md`](../../CLAUDE.md) (behavior) and [`SOVEREIGN_MANIFEST.md`](SOVEREIGN_MANIFEST.md) (architectural truth). When this file disagrees with either, they win.

This file exists because the audit synthesis at `reports/audit/end_to_end/000_MASTER_COHERENCE_SYNTHESIS.md` found that agents repeatedly rebuild substrates that already exist or skip canonical reads before committing. This is a single short page that every build agent reads first, then proceeds to the canonical docs.

If you are about to write code in this repo, read this file fully, then read the four numbered files below in order. Do not skim. Do not skip the audit. The repo will not give you a second chance to re-orient mid-session.

---

## 0. What this repo is, in one paragraph

dharma_swarm is a Python multi-agent orchestration runtime with a typed ontology, an immutable kernel, gated proposal flow, an append-only witness log, and an artifact/value loop. The substrates exist. The current failure mode is that most runtime work bypasses them. The current build track is to make one seam ontology-native end-to-end before generalising. Do not introduce new substrates. Wire existing ones.

Current substrate-nativeness estimate (from audit): **~10–15% of runtime is ontology-native; ~85–90% bypasses substrate.** Goal of the current track: bring one user-visible seam to 100% native and prove it with tests.

---

## 1. Mandatory read order

Read in this exact order. Stop at each file until you have actually answered the questions next to it.

1. [`CLAUDE.md`](../../CLAUDE.md) — behavioral rules, key abstractions, build/test commands. *What rules govern any change I make?*
2. [`docs/governance/SOVEREIGN_MANIFEST.md`](SOVEREIGN_MANIFEST.md) — domain map, axioms, verified numbers, boundary constraints. *Which domain is my change in? Which boundaries must I not cross?*
3. [`reports/audit/end_to_end/000_MASTER_COHERENCE_SYNTHESIS.md`](../../reports/audit/end_to_end/000_MASTER_COHERENCE_SYNTHESIS.md) — settled truths, top 20 unresolved gaps, "do not build new, wire existing" list, canonical substrate table. *Does what I'm about to do duplicate something that already exists?*
4. [`docs/governance/CANONICAL_DOC_STACK.md`](CANONICAL_DOC_STACK.md) — doc hierarchy, ownership table, anti-doc-maze rules. *Which file owns the truth I'm about to write down?*

If any of those four contradict each other on numbers, trust SOVEREIGN_MANIFEST first, then CLAUDE.md, then the audit, then CANONICAL_DOC_STACK. All four are still authoritative for the topic each one owns per CANONICAL_DOC_STACK.md.

---

## 2. Current build track

The active engineering track is **one ontology-native seam, end-to-end, with gates and witness load-bearing**, before any second seam.

- **Track name:** Ontology-Native Operator Brief (Daily Insight Brief)
- **Master spec:** [`docs/plans/ONTOLOGY_NATIVE_OPERATOR_BRIEF_MASTER_SPEC.md`](../plans/ONTOLOGY_NATIVE_OPERATOR_BRIEF_MASTER_SPEC.md)
- **Next ten substrate todos:** [`docs/plans/NEXT_10_SUBSTRATE_TODO.md`](../plans/NEXT_10_SUBSTRATE_TODO.md)
- **Handoff to next code agent:** [`docs/plans/HANDOFF_ONTOLOGY_NATIVE_OPERATOR_BRIEF.md`](../plans/HANDOFF_ONTOLOGY_NATIVE_OPERATOR_BRIEF.md)

Do not start work on a different seam (Dharma Radar v0, full identity unification, dashboard chat routing, training flywheel) until either the operator-brief seam is acceptance-tested or the active ledger in `SOVEREIGN_MANIFEST.md` lists a new track. Cross-track work fragments the substrate-nativeness measurement and is the failure mode the audit flagged.

---

## 3. What "ontology-native" means for this repo

A flow is ontology-native when **every** statement below is true:

1. The flow's outputs are typed `OntologyObj` instances persisted via `OntologyRegistry`, not loose dicts or JSON files written to arbitrary paths.
2. Side effects that change shared state go through `ActionDef` executions recorded in `ActionExec`, not raw function calls.
3. Every gateable step writes a `GateDecisionRecord` linked to a `WitnessLog` entry. ALLOW, BLOCK, and REVIEW outcomes are all witnessed.
4. Generated artifacts are linked from `KnowledgeArtifact` to their producing `Experiment`, `ResearchThread`, or `ActionProposal`, and to the `WitnessLog` entries that gated their creation.
5. Value-bearing outcomes emit a `ValueEvent`; agent-attributable contributions emit a `Contribution` linked to the producing `AgentIdentity`.
6. The flow's failure modes (gate block, missing input, schema violation) are visible in artifacts and witness, not silent.
7. The flow has a test that fails if any of points 1–6 regress. "Best effort, never blocks" is not acceptable for a track-1 seam.

If your change satisfies fewer than all seven for the seam it touches, it is not ontology-native yet. Do not claim otherwise in the PR description.

---

## 4. What you must not do

These are direct from `SOVEREIGN_MANIFEST.md` axioms and the audit's "do not build new" list. Reread them at the source if you need detail:

- Do not add files to the top level of `dharma_swarm/` (axiom A1).
- Do not create a duplicate bridge, router, adapter, or orchestrator (axiom A2).
- Do not introduce a new event ledger, work ledger, artifact registry, fact memory store, context bundle table, provider hierarchy, routing memory, Shakti queue, or telemetry read model. Use the canonical substrates listed in audit §6.
- Do not create new top-level markdown files. New docs go under `docs/plans/`, `docs/governance/`, `docs/architecture/`, or `reports/`. The canonical doc stack already says "max 5 governance docs"; this file is justified as a pointer layer and identifies the four it points to. Do not add a sixth governance doc casually.
- Do not promote a new identity schema by docs alone (audit §5 finding 10).
- Do not write to the filesystem outside `~/.dharma/` at runtime.

---

## 5. What success on the current track looks like

The operator-brief seam is done when all of the following hold simultaneously, and a single test asserts each:

1. A `KnowledgeArtifact` row of subtype `operator_brief` is created on each scheduler tick by the canonical path.
2. That artifact has links to at least one `WitnessLog`, one `ActionProposal`, one `GateDecisionRecord` per applied gate (BHED_GNAN, STEELMAN, DOGMA_DRIFT, CONSENT), one `Outcome`, and one `ValueEvent`.
3. The four gates above are evaluated for the brief, and a BLOCK on any one prevents artifact materialisation. The block is itself witnessed.
4. No code path produces an operator brief by writing JSON to disk without going through the ontology and gates.
5. A failing gate or missing input produces a visible error artifact, not silent success.
6. The seam runs from a single scheduler entry in `cron_jobs.json` and a single new module under `dharma_swarm/` (in an existing subdirectory, not the flat top level).
7. The seam adds zero new bridges, routers, adapters, ledgers, or memory stores.

When all seven are tested and passing, the substrate-nativeness estimate moves measurably and the next track can open.

---

## 6. Where to record what you find

- New architectural truth → `SOVEREIGN_MANIFEST.md` (edit, don't fork).
- New behavioral rule → `CLAUDE.md` (edit, don't fork).
- New plan → `docs/plans/<date>-<slug>.md` (the existing convention).
- Drift you discover in old docs → log it in `docs/governance/REPO_GOVERNANCE_AUDIT.md`. Do not silently fix without logging.
- Build-session pointers → this file. Keep it short. If it grows past one screen of read-order plus current track, split the bloat back into the canonical docs it should live in.
