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

dharma_swarm is a Python multi-agent orchestration runtime with a typed ontology, an immutable kernel, gated proposal flow, an append-only witness log, and an artifact/value loop. The substrates exist. The current failure mode is that most runtime work bypasses them. Each active build track makes one seam ontology-native end-to-end; the active build portfolio (1–N co-equal, surface-disjoint tracks) is declared in [`ACTIVE_TRACK.yaml`](ACTIVE_TRACK.yaml) and surfaced by `make onboard`. Do not introduce new substrates. Wire existing ones.

Current substrate-nativeness estimate (from audit): **~10–15% of runtime is ontology-native; ~85–90% bypasses substrate.** Each track's goal: bring its seam to 100% native and prove it with tests, surface-disjoint from sibling tracks.

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

The governing principle: each track ships **one seam, end-to-end, with gates and witness load-bearing**. Multiple co-equal tracks may run concurrently (up to `track_policy.max_active`) as long as they have **non-overlapping `owned_surfaces`** — that surface-disjointness, not a single-track mutex, is what keeps the substrate-nativeness measurement clean. When the operator proposes a new project, **declare a new track** under `active_tracks:` in `ACTIVE_TRACK.yaml` (with `serves:`, `owned_surfaces:`, acceptance criteria) — a new project is a new track, not a violation. The failure mode the audit flagged is *undeclared, surface-overlapping* cross-track work, which CI now flags as a conflict — not concurrency itself.

<!-- ACTIVE_TRACK:START -->

<!-- This block is generated from docs/governance/ACTIVE_TRACK.yaml.
     Do not hand-edit. Run scripts/governance/render_active_track_includes.py
     after updating the YAML. -->

**Active portfolio:** 2 co-equal track(s) (WIP warn 5, max 10). A new project is a new track here, not a violation — model: 1..N co-equal active tracks; typed graph; WIP-limited; surface-owned.

**Spine objectives (each track serves one):**

- `substrate-nativeness` — Substrate nativeness — runtime flows through the ontology/spine, not around it (covered)
- `revenue-external-humans-served` — Revenue & external humans served — value leaves the house and someone acts on it (**no active track**)
- `research-depth` — Research depth — the contemplative-mechanistic bridge (R_V, geometric lens) deepens (**no active track**)

### Runtime Truth Reconciliation — operator-visible truth packets

**Track id:** `runtime-truth-reconciliation-2026-06` · **Status:** ACTIVE · **Owner:** @AmitabhainArunachala
**Serves spine objective:** `substrate-nativeness` · **Verified at:** 2026-06-04 (TTL 14 days)
**Relations:** complements: runtime-truth-nats-2026-06
**Owns surfaces:** dharma_swarm/operator_core/**, scripts/governance/agent_onboard.py, dharma_swarm/runtime_state.py
**Moves vital signs:** quality_gates, memory_persistence

The Runtime Truth Spine substrate is merged and shippable. This track moves
from substrate existence to read-only reconciliation: operator-visible
runtime truth packets that separate heartbeat, readiness, artifact progress,
completion, authority, projection/cache, mutation, and external-gated proof.

The track must not create a new truth store, daemon, receipt system, or
authority surface. It projects from existing owners only:
spine.EvidenceReceipt for in-flight dispatch proof, runtime_state.RuntimeReceipt
for persisted runtime receipts, IdempotencyRecord for exactly-once substrate,
and existing operator/onboard/control-surface rows for read-only rendering.

Doctrine line that must hold:
  Read models project truth from owners; they do not become authority.

**Next items:**

- [code] (blocker) Define the smallest read-only RuntimeTruthPacket contract in the existing operator_core owner.
- [code] (blocker) Render compact runtime truth in make onboard without making onboard an authority surface.
- [test] Protect A2A single-persistence invariant while adding runtime truth projections.

**Non-goals:**

- Do not create a new daemon, database, event log, truth store, or receipt system.
- Do not mint a second RuntimeReceipt for A2A or paths with an inner runtime owner.
- Do not mutate external systems, live processes, archive fitness, payments, or gateways.
- Do not broadly refactor orchestrator.py, agent_runner.py, swarm.py, providers.py, or SwarmManager.
- Do not build Verified Experiment Loop runtime in this track.
- Do not create standalone BetCard, Experiment, SwarmRun, DecisionRecord, LineageRecord, WikiUpdate, or cost-tracker classes.

### Runtime Truth NATS — internal live transport for A2A dispatch

**Track id:** `runtime-truth-nats-2026-06` · **Status:** ACTIVE · **Owner:** @codex
**Serves spine objective:** `substrate-nativeness` · **Verified at:** 2026-06-07 (TTL 21 days)
**Relations:** complements: runtime-truth-reconciliation-2026-06
**Owns surfaces:** docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md, dharma_swarm/a2a/a2a_nats_contact.py, dharma_swarm/a2a/a2a_core_contact.py
**Moves vital signs:** tool_coverage

The concurrent Codex transport lane. NATS was scoped out of the global
prohibition by the 2026-05-31 doctrine amendment and runs as a concurrent
scoped track with non-overlapping surfaces (transport layer only). This
track wires the internal live transport so A2A dispatch can travel at
broker speed, distinct from the reconciliation lane's read-model surfaces.

Surface separation is the safety boundary: this track owns the NATS
transport contact modules and the master spec; it does not touch the
operator_core read models the reconciliation lane owns.

**Next items:**

- [code] Confirm NATS transport contact modules are wired and receipted end-to-end.

**Non-goals:**

- Do not introduce Redis or gRPC as part of this track.
- Do not touch the operator_core read-model surfaces owned by the reconciliation lane.
- Do not add a parallel spine-check CI workflow.

**Recently closed tracks:**

- `runtime-truth-spine-2026-06` — Runtime Truth Spine — one invariant, one invocation path, one receipt (SHIPPED, closed 2026-06-04)
- `trace-identity-coverage-2026-05` — Trace Identity Coverage — native propagation and soft coverage findings (SUPERSEDED, closed 2026-05-28)
- `trace-attractor-causal-spine-2026-05` — Trace Attractor Causal Spine — operator-visible trace packets (SHIPPED, closed 2026-05-21)

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

## 5. What "done" looks like for a seam track (template)

Each track defines its own acceptance criteria in `ACTIVE_TRACK.yaml` (`completion_criteria:`), enforced by `scripts/governance/check_track_status.py`. The pattern below — taken from the historical operator-brief seam as a worked **example**, not the current track — is the shape a substrate-native seam track should aim for; adapt it per track:

1. The seam's artifact is created on the canonical path (e.g. a `KnowledgeArtifact` row on each scheduler tick), never by a side path.
2. That artifact links to its witness/proposal/gate-decision/outcome/value rows (e.g. `WitnessLog`, `ActionProposal`, one `GateDecisionRecord` per applied gate, `Outcome`, `ValueEvent`).
3. The applied gates are evaluated, and a BLOCK on any one prevents materialisation. The block is itself witnessed.
4. No code path produces the artifact by writing JSON to disk without going through the ontology and gates.
5. A failing gate or missing input produces a visible error artifact, not silent success.
6. The seam runs from a single scheduler entry and a single new module under `dharma_swarm/` (in an existing subdirectory, not the flat top level).
7. The seam adds zero new bridges, routers, adapters, ledgers, or memory stores.

When a track's `completion_criteria` all pass, the substrate-nativeness estimate moves measurably; that track flips SHIPPABLE and can close while sibling tracks keep running.

---

## 6. Where to record what you find

- New architectural truth → `SOVEREIGN_MANIFEST.md` (edit, don't fork).
- New behavioral rule → `CLAUDE.md` (edit, don't fork).
- New plan → `docs/plans/<date>-<slug>.md` (the existing convention).
- Drift you discover in old docs → log it in `docs/governance/REPO_GOVERNANCE_AUDIT.md`. Do not silently fix without logging.
- Build-session pointers → this file. Keep it short. If it grows past one screen of read-order plus current track, split the bloat back into the canonical docs it should live in.
