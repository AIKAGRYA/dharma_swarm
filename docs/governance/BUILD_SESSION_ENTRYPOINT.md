# BUILD SESSION ENTRYPOINT

**Status:** depth doc — read after running the onboarding command.
**Owner of:** the longer-form pre-flight narrative for a build session.
**Subordinate to:** [`CLAUDE.md`](../../CLAUDE.md) (behavior), [`SOVEREIGN_MANIFEST.md`](SOVEREIGN_MANIFEST.md) (architectural truth), and [`ACTIVE_TRACK.yaml`](ACTIVE_TRACK.yaml) (current build track). When this file disagrees with any of them, they win.

## Run this first

```bash
make onboard
```

That command renders the current operating reality (active track, live ops, broken register, axioms, depth pointers) in one screen. It replaces the old hand-maintained "read order". This file is the depth narrative you read **after** the onboarding command, when you need more context than one screen.

---

## 0. What this repo is, in one paragraph

dharma_swarm is a Python multi-agent orchestration runtime with a typed ontology, an immutable kernel, gated proposal flow, an append-only witness log, and an artifact/value loop. The substrates exist. The current failure mode is that most runtime work bypasses them. The current build track is to make one seam ontology-native end-to-end before generalising. Do not introduce new substrates. Wire existing ones.

Current substrate-nativeness estimate (from audit): **~10–15% of runtime is ontology-native; ~85–90% bypasses substrate.** Goal of the current track: bring one user-visible seam to 100% native and prove it with tests.

---

## 1. Depth pointers (read on demand, not in order)

The onboarding command (`make onboard`) lists the depth pointers inline. The same list, for offline reference:

- [`CLAUDE.md`](../../CLAUDE.md) — behavioural rules, key abstractions, build/test commands. *What rules govern any change I make?*
- [`docs/governance/SOVEREIGN_MANIFEST.md`](SOVEREIGN_MANIFEST.md) — domain map, axioms, verified numbers, boundary constraints. *Which domain is my change in? Which boundaries must I not cross?*
- [`reports/audit/end_to_end/000_MASTER_COHERENCE_SYNTHESIS.md`](../../reports/audit/end_to_end/000_MASTER_COHERENCE_SYNTHESIS.md) — settled truths, unresolved gaps, "do not build new, wire existing" list. *Does what I'm about to do duplicate something that already exists?*
- [`docs/governance/CANONICAL_DOC_STACK.md`](CANONICAL_DOC_STACK.md) — doc hierarchy, ownership table, anti-doc-maze rules. *Which file owns the truth I'm about to write down?*
- [`docs/governance/ANTI_SLOP_RULES.md`](ANTI_SLOP_RULES.md) — explicit do-nots backed by Semgrep rules.

If any of these contradict each other on numbers, trust SOVEREIGN_MANIFEST first, then CLAUDE.md, then the audit, then CANONICAL_DOC_STACK. Each is authoritative for the topic CANONICAL_DOC_STACK assigns it.

---

## 2. Current build track

The current build track is declared in [`ACTIVE_TRACK.yaml`](ACTIVE_TRACK.yaml) and surfaced by `make onboard`. **Do not duplicate the track name in prose here** — the YAML is the single source of intent, and any prose copy here will go stale.

The governing principle behind whatever track is active: **one seam, end-to-end, with gates and witness load-bearing**, before any second seam. Do not start work on a parallel seam until the active track’s acceptance criteria pass (visible in the onboarding output) or a new track is declared in `ACTIVE_TRACK.yaml`. Cross-track work fragments the substrate-nativeness measurement and is the failure mode the audit flagged.

<!-- ACTIVE_TRACK:START -->

<!-- This block is generated from docs/governance/ACTIVE_TRACK.yaml.
     Do not hand-edit. Run scripts/governance/render_active_track_includes.py
     after updating the YAML. -->

**Active track:** Runtime Truth Spine — one invariant, one invocation path, one receipt
**Track id:** `runtime-truth-spine-2026-06`
**Status:** ACTIVE
**Verified at:** 2026-05-28 (TTL 14 days)
**Owner:** @AmitabhainArunachala

**Description:**

Define the Runtime Truth Spine before expanding agent fabric. Three audits
(Perplexity, Codex, Devin) converged: dharma_swarm has accreted without a
spine. The fix is one invariant chain (Task + Runner + Claim + Context +
RoutingDecision + ProviderCall + EvidenceReceipt = safe execution path).
Every dispatch produces exactly one receipt. No more generic dispatch_dropoff.
PR A.5 (governance convergence): the spine guard is fused into the existing
uplift_guards composition (no parallel CI workflow), each closure layer's
canonical receipt is declared in ACTIVE_SURFACE_MANIFEST.yaml under
correlation_spine, and ANTI_SLOP Rule 2 is extended with role vocabulary
so future receipts must declare their layer instead of growing a second
truth surface.
Doctrine line that must hold across all closure layers:
  Receipts may differ by closure layer. Correlation identity must not.
Reference: docs/reports/CONVERGED_SEAM_AUDIT_RUNTIME_TRUTH_SPINE.md
A2A anchor: dharma_swarm/a2a/README.md (three-layer receipt architecture)

**Next items on this track:**

- [code] (blocker) Define spine types (EvidenceReceipt, RoutingDecision, invoke_agent) — zero behavior change.
- [code] (blocker) Wire A2A into the spine (invoke_agent becomes the only invocation path for A2A delegation).
- [code] Collapse 7 routers to 2 on the spine rail.
- [code] Shard providers.py into per-provider files.
- [code] Decompose agent_runner.py run_task onto spine boundary.

**Non-goals (do not work on these during this track):**

- Do not decompose AgentRunner.run_task in this track (except where strictly necessary).
- Do not split providers.py into per-provider files yet.
- Do not rewrite SwarmManager.
- Do not introduce NATS, Redis, gRPC, or a new daemon.
- Do not create a second event log or truth surface.
- Do not add another spiritual/metaphoric naming layer.
- Do not add a parallel spine-check CI workflow — the uplift_guards composition is the only entry point.

**Recently closed tracks:**

- `boardstore-facade-2026-05` — BoardStore Facade — unified task/state surface for multi-agent coordination (SHIPPED, closed 2026-05-20)
- `cockpit-control-surface-2026-05` — Operator Cockpit v1 + Control-Surface contract hardening (SHIPPED, closed 2026-05-20)
- `operator-brief-seam-2026-04` — Ontology-Native Operator Brief (first substrate-native seam) (SHIPPED, closed 2026-05-19)

For machine-readable status, see [`reports/governance/active_track_evidence.md`](../../reports/governance/active_track_evidence.md) (generated by `scripts/governance/check_track_status.py`).

<!-- ACTIVE_TRACK:END -->

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
