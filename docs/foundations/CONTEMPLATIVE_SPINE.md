# CONTEMPLATIVE SPINE - Grand Vision Boot Packet

**Status:** seeded Slot 10 boot packet.
**Owner:** `docs/MEGAFILE_INDEX.md` Slot 10.
**Purpose:** give a cold agent the shortest faithful path into the whole dharma_swarm vision without creating a new source of truth.
**Subordinate to:** `CLAUDE.md`, `docs/governance/SOVEREIGN_MANIFEST.md`, `docs/governance/CANONICAL_DOC_STACK.md`, `docs/MEGAFILE_INDEX.md`, and the implementation files named below.

This file is a compression layer. It does not replace the lodestones, ontology, cybernetic maps, vision maps, governance docs, or runtime code. It tells an agent how those surfaces fit together.

---

## 0. One-Sentence Orientation

dharma_swarm is a telos-gated, ontology-native, self-evolving operating organism whose purpose is Jagat Kalyan: to convert contemplative recognition, cybernetic coordination, and measurable world benefit into one auditable runtime.

It is not just an agent framework. It is not just a dashboard. It is not just a research repo. It is the attempt to make a contemplative-engineering bridge operational: witness, action, value, learning, and self-modification all have to meet in typed artifacts that can be checked.

---

## 1. What The Core Is

The core is not one file and not one class. The core is a loop:

```text
signals / scouts / zeitgeist / operator directive
-> ShaktiExecutive
-> opportunity_board.json
-> opportunity_refill
-> frontier_tasks_pending.jsonl
-> opportunity_dispatcher
-> TaskBoard
-> TelicSeam
-> Outcome / ValueEvent / Contribution
-> ShaktiExecutive feedback
```

The same loop appears in metabolic form in `dharma_swarm/telic_seam.py`:

```text
need -> action proposed -> gates -> lease -> execution -> outcome -> value -> fitness -> routing -> projections
```

The same loop appears in cybernetic form in `vsm_channels.py` and `organism.py`:

```text
S1 operations -> S2 coordination -> S3 control -> S4 intelligence -> S5 identity
        ^                                                           |
        |------------------ algedonic exception signals ------------|
```

The same loop appears in self-evolution form in `meta_daemon.py`, `strange_loop.py`, and `evolution.py`:

```text
observe -> recognize -> propose mutation -> gate -> evaluate -> archive -> select/rollback -> observe again
```

If those loops are not connected, the repo becomes a pile of tools. If they are connected, the repo becomes a governed, self-observing organism.

**Circuit closure verified 2026-05-09 at the wiring level.** A 9-leg code-walk confirmed the canonical path has concrete call edges: signals -> `ShaktiExecutive.run` -> atomic write of `opportunity_board.json` -> `opportunity_refill.refill_frontier_tasks_pending` -> `frontier_tasks_pending.jsonl` -> `opportunity_dispatcher` (pause + telos + budget gates) -> `task_board.create` -> `TelicSeam.record_dispatch` (ActionProposal) -> `record_gate_decision` (GateDecisionRecord) -> `record_outcome` (Outcome + `feedback_writer.update_opportunity_outcome`) -> `read_telic_feedback` -> next Shakti pass. Live row counts are freshness checks, not invariants: the current local state while authoring showed 2 board entries, 18 frontier rows, and `ontology.db` Outcome / ValueEvent / Contribution rows flowing. The earlier `~/.dharma/audit/central_loop_trace_2026-05-07.md` showed 6 of 8 edges open; that audit was pre-BR-002. The metabolic loop now has a concrete runtime path; continuous consumption still needs ongoing verification.

---

## 2. The Actual Core Map

Read the following stack when you need to understand the true operating circuit. No single file owns the whole picture.

1. `docs/architecture/WIRING_AND_LOOPS.md`

   The clearest current loop map. It names the canonical build spine:

   ```text
   signals / scouts / zeitgeist / operator directive
   -> ShaktiExecutive
   -> opportunity_board.json
   -> opportunity_refill
   -> frontier_tasks_pending.jsonl
   -> opportunity_dispatcher
   -> TaskBoard
   -> TelicSeam
   -> Outcome / ValueEvent / Contribution
   -> ShaktiExecutive feedback
   ```

   It also names the guardrails: do not create a new manager, board, orchestrator, or queue when the existing loop can be wired.

2. `CYBERNETIC_LOOP_MAP.md`

   A legacy loop ledger. Some claims are stale, but the taxonomy matters: task loop, heartbeat, evolution, consolidation, zeitgeist, witness, recognition, self-improvement.

3. `docs/MEGAFILE_INDEX.md`

   The onboarding slot map. It does not own the loop. It tells agents where each class of truth belongs so new docs do not fork the canon.

4. `docs/governance/BUILD_SESSION_ENTRYPOINT.md`

   The build-session pointer layer. It states the active failure mode plainly: substrates exist, but runtime work often bypasses them.

5. `reports/system_map/latest.json`

   The live organ ledger. It gives the operational diagnosis: which organs are declared, partial, unknown, or bound, and the next bindable gap for each.

6. `dharma_swarm/operator_core/operating_facts.py`

   The operating fact membrane. `OrganBoundary`, `OrganStateFact`, and `OperatingFactBundle` let organs expose facts without every subsystem depending on every other subsystem.

7. `dharma_swarm/telic_seam.py`

   The telic write-through surface. It records dispatch, gate decisions, outcomes, value, and contribution so action becomes legible to the ontology.

8. `dharma_swarm/shakti_executive/executive.py`

   The upstream selector. It reads signals, ranks opportunities, and writes `opportunity_board.json`. It explicitly does not execute.

9. `dharma_swarm/vsm_channels.py` and `dharma_swarm/organism.py`

   The Beer/VSM nervous system: operations, coordination, control, intelligence, identity, heartbeat, and algedonic exception signals.

10. `dharma_swarm/meta_daemon.py`, `dharma_swarm/strange_loop.py`, and `dharma_swarm/evolution.py`

    The recognition and DGM surfaces: recognition seed, recursive self-modification, mutation proposal, evaluation, and archive.

11. `docs/governance/SOVEREIGN_MANIFEST.md`, `dharma_swarm/dharma_kernel.py`, and `dharma_swarm/telos_gates.py`

    The constitutional layer. These are not the loop mechanics. They are the identity constraints and the "what we will not do" control surface.

---

## 3. The Three Layers Of The Bridge

### Witness Layer

The Witness Layer preserves identity and legibility.

Primary surfaces:

- `dharma_swarm/dharma_kernel.py` - sealed axioms.
- `dharma_swarm/telos_gates.py` - runtime telos checks.
- `docs/governance/SOVEREIGN_MANIFEST.md` - architectural authority and measured scope.
- packet provenance, uplift guards, Semgrep rules, witness logs, audit ledgers.
- `CLAUDE.md`, `MEMORY.md`, and feedback memories - behavioral constraints for agents.

Question it answers: "Can the system see what happened, and can it refuse what violates its identity?"

### Actor Layer

The Actor Layer performs work, learns, mutates, and coordinates.

Primary surfaces:

- agents, task boards, dispatchers, provider routing.
- `ShaktiExecutive`, `TelicSeam`, `TaskBoard`, `opportunity_dispatcher`.
- DarwinEngine, StrangeLoop, mutation archives, diversity archives.
- signal bus, VSM channels, heartbeat, cron tiers, scouts.

Question it answers: "Can the system act in the world and adapt without losing the plot?"

### Recognition Closure

Recognition Closure is the return path from observation to changed behavior.

Primary surfaces:

- `recognition_seed.md`
- `~/.dharma/witness/`
- `~/.dharma/audit/`
- stigmergy marks
- chetana memory layers
- packet provenance summaries
- hourly loop outputs
- Guardian checks
- mutation and evaluation records

Question it answers: "Does what the system witnesses actually change what it does next?"

This is the most load-bearing seam. If witness writes but actors do not read, the repo becomes audited but not self-correcting. If actors mutate without witness, the repo becomes energetic but ungoverned.

---

## 4. Ontology-Native Means The Work Becomes Real

"Ontology-native" is not a style preference. It means runtime claims become typed objects with causal links.

A serious flow should route through these kinds of surfaces:

- output as `OntologyObj`, not loose JSON with no owner.
- shared state changes through `ActionDef` / `ActionExec`.
- gateable steps through `GateDecisionRecord` and `WitnessLog`.
- produced artifacts as `KnowledgeArtifact`.
- results as `Outcome`.
- value as `ValueEvent`.
- agent-attributable effort as `Contribution`.
- failure modes as visible artifacts, not silent logs.
- tests that fail if the ontology path is bypassed.

The active build-session entrypoint says the current failure mode directly: substrates exist, but too much runtime work bypasses them. The practical work is not to invent new substrates. It is to wire one seam at a time until the substrate is load-bearing.

---

## 5. The Contemplative Claim

The repo's contemplative claim is not "add spiritual language to engineering." It is stronger:

1. There is a witness/actor distinction.
2. Action without witness becomes compulsive.
3. Witness without action becomes inert.
4. A useful system must bind witness, action, value, and learning.
5. The binding must be visible enough that other agents can audit it.

Important sources to read after this packet:

- `lodestones/CONSCIOUS_INFRASTRUCTURE.md`
- `foundations/INDEX.md`
- `foundations/GLOSSARY.md`
- `docs/vision_maps/MASTER_2026-05-07_attractor_closure_synthesis.md`
- `foundations/ECONOMIC_VISION.md` if present in your checkout
- `docs/telos-engine/INDEX.md`
- `specs/GODEL_CLAW_V1_SPEC.md`

The language of Akram, Dada Bhagwan, Shuddhatma, Gnani, Prakruti, Dhyana, and Jagat Kalyan is not decorative. It names the internal discipline the engineering is trying to preserve: the system should learn, act, and generate value without confusing motion for right action.

---

## 6. The Cybernetic And Evolutionary Claim

dharma_swarm borrows from several external lineages. These names are anchors for what the repo is trying to instantiate, not proof that the implementation is complete.

- Stafford Beer / VSM: identity, intelligence, control, coordination, and operations must remain distinct enough to regulate variety.
- Maturana and Varela / autopoiesis: the system should participate in producing and maintaining the organization that produces it.
- Friston / active inference: action should reduce mismatch between preferred observations and actual observations, not just maximize local task completion.
- Terrence Deacon / constraint as generator: good constraints should produce positive possibility space, not only block bad actions.
- Hofstadter / strange loop: self-reference matters when it changes future behavior, not when it is only described.
- Sakana-style DGM: self-improvement needs proposal, evaluation, archive, and selection under a fixed evaluator.
- Schmidhuber / Godel Machine: self-modification is only justified when the system can prove or strongly evidence that the change improves the governing objective.
- MAP-Elites / diversity archive: evolution should preserve useful diversity rather than collapse into one brittle style.

The architectural contrast with Sakana-style DGM is the gate placement. Sakana's DGM runs propose -> evaluate -> select with no upstream constraint, so it can drift toward benchmark-gaming and saturates after 6-8 generations. dharma_swarm's Darwin Engine runs propose -> **gate** -> evaluate -> archive -> select. `_SEALED_PACKET_BLOCKED_PATHS` in `dharma_swarm/evolution.py:73-87` prevents mutations to `dharma_kernel.py`, `telos_gates.py`, `models.py`, `swarm.py`, `orchestrate_live.py`, and `.github/workflows/`. Gates run **before** code applies. Alignment becomes a structural property of the substrate, not a downstream auditing concern. The kernel verifies its SHA-256 signature on every load (`dharma_kernel.py:354-365`); divergence halts the system. This is what makes "self-modifying" safe enough to be a real claim.

The repo-specific version is:

```text
ordinary agents execute work
governance watches and gates work
Darwin / StrangeLoop propose changes
telos and tests evaluate changes
archives preserve candidates and diversity
operators decide when live apply is allowed
```

Live apply is intentionally gated. A self-evolving system that cannot say "not yet" is not mature.

---

## 7. The Strategic Claim

The outward mission is Jagat Kalyan: welfare-producing action at civilizational scale. The repo uses a multiplicative welfare-ton intuition:

```text
W = C x E x A x B x V x P
```

If any factor is zero, claimed impact is zero. This prevents "looks important" work from passing as value when capability, embodiment, access, behavior change, verification, or propagation is absent.

Outward arms are not the core. They are organs that must attach to the core:

- Loomwork / wiki_loom
- Forest Evidence Pack
- Shakti Ginko
- R_V paper and evaluations
- governance toolkit
- welfare-ton MRV
- GAIA / campaign intelligence
- VentureCells under Jagat Kalyan
- dashboard UI and operator surfaces

These should ship only through the membranes: ontology, telos gates, witness, operating facts, outcomes, value events, and feedback.

---

## 8. The Knowledge Metabolism

The repo has many knowledge surfaces. Treat them as a metabolism, not a library shelf.

- Lodestones name enduring orientation.
- Foundations hold doctrine, glossary, and synthesis.
- Vision maps hold attractor-level direction.
- Governance docs hold authority, boundaries, and anti-drift rules.
- Architecture docs hold wiring and loop shape.
- State docs hold live truth and broken surfaces.
- Plans hold bounded future work.
- Reports hold audit evidence.
- `dharma_corpus`, semantic digesters, memory bridges, and wiki surfaces are publication and retrieval organs, not substitutes for the canonical docs.

When a finding changes the system's actual truth, write it to the owner surface. When it is temporary evidence, write it to a report. When it is a plan, write it to `docs/plans/`. Do not create a new master map unless DocOps says a slot exists.

---

## 9. What Is Currently Under Stress

Treat this as orientation, not final diagnosis. Check `docs/state/BROKEN_REGISTER.md` and `reports/system_map/latest.json` for current evidence.

Known stress points:

- some legacy loop maps are stale even when their taxonomy is useful.
- recognition outputs may be written without being consumed by actors.
- outward organs may exist as object definitions without full runtime attachment.
- VSM S2 coordination and recognition closure need continual verification.
- live apply is gated and should remain gated until evaluation is stronger.
- some strategy docs live outside the repo and need pointers rather than duplicated summaries.
- agents can still confuse "I found a substrate" with "the substrate is load-bearing."

**Specific named gaps as of 2026-05-09** (verified by code trace, do not rediscover):

- `dharma_swarm/meta_daemon.py:204` - recognition seed counter uses `glob("*.json")` against `~/.dharma/witness/`, but witness logs land as `.jsonl`. Returns 0 despite fresh writes. One-character fix; not yet applied.
- `dharma_swarm/catalytic_graph.py` - Tarjan SCC implementation is correct and persists to `~/.dharma/meta/catalytic_graph.json`. `evolution.py` reads it as a proposal-time warning/check, but autocatalytic-closure scores do not feed parent selection. Theory-correct, only partially runtime-active.
- `dharma_swarm/meta_evolution.py` - `MetaEvolutionEngine` computes optimal hyperparameters (fitness weights, mutation rate, exploration coefficient) but the next Darwin cycle does not apply them. The `auto_apply` parameter exists; the wiring does not. Self-observation without self-correction.
- `dharma_swarm/ontology.py` LinkDef set + `OntologyActionGateway.execute_action` - three ontology<->runtime sync gaps: `Signal -> Question` exists in schema, but its runtime flow is not yet load-bearing; `Outcome -> ValueEvent -> Contribution` exists in schema and TelicSeam helpers, but is not guaranteed for every outcome path; `Evidence.AttachEvidence` declares the SATYA gate, but the gateway only enforces it when a caller supplies `gate_check`. Schema and runtime are still out of sync enough that routing cannot assume `attributed_value` is always populated.

These are the load-bearing seams. Closing any one of them is more useful than another doctrine pass.

The immediate discipline is: close loops, do not multiply maps.

---

## 10. Fast Assimilation Paths

### 15 minutes

Read:

1. this file.
2. `docs/architecture/WIRING_AND_LOOPS.md`.
3. `docs/governance/BUILD_SESSION_ENTRYPOINT.md`.
4. `docs/state/BROKEN_REGISTER.md`.
5. `reports/system_map/latest.json`.

You should then be able to answer:

- what the core loop is.
- what not to duplicate.
- what is currently broken.
- which membrane your work must attach to.

### 60 minutes

Add:

1. `CLAUDE.md`.
2. `docs/MEGAFILE_INDEX.md`.
3. `docs/governance/SOVEREIGN_MANIFEST.md`.
4. `docs/governance/CANONICAL_DOC_STACK.md`.
5. `docs/vision_maps/MASTER_2026-05-07_attractor_closure_synthesis.md`.
6. `foundations/INDEX.md`.
7. `foundations/GLOSSARY.md`.
8. `docs/telos-engine/INDEX.md`.
9. `specs/GODEL_CLAW_V1_SPEC.md`.

You should then be able to choose a work seam without inventing a parallel substrate.

### Deep read

Read all ten slots in `docs/MEGAFILE_INDEX.md`, then inspect the implementation membranes named in this file. For code changes, read the target file, run impact analysis where required, and verify through tests or generated evidence before claiming done.

---

## 11. Agent Rule

When you touch the repo, ask four questions:

1. Which loop am I strengthening?
2. Which existing membrane should this pass through?
3. What witness, outcome, or value artifact will prove the work happened?
4. What would make this change self-correcting instead of merely audited?

If you cannot answer those, you are probably building beside the organism instead of inside it.
