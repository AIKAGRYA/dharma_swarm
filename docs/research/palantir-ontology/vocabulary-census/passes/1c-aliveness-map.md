# Pass 1c — Aliveness Map
**Author:** perplexity-computer (activity archaeologist)  
**Window:** 2026-03-03 → 2026-06-01 (90 days)  
**Output of:** Layer 2 Vocabulary Inhabitation Swarm, Pass 1  
**NO TYPE NAMES. NO camelCase proposals.**

---

## 1. Activity Windows — The Wave Structure

**Total commits in window:** ~693 (git log count: 280+210+115+35+27+20+others)  
**Active authors:** John Shrader (280), Dhyana/operator (210), AmitabhainArunachala/Claude (115), DHARMA SWARM (35), Claude direct (27), Devin AI (20+)

### March Wave (175 commits, March 3–31)
**Theme: Foundation-laying and stabilization.** The month opened with John and Dhyana committing to a legacy import regime (DHARMIC_GODEL_CLAW → dharma_swarm), building out the MERGE_LEDGER as a migration accounting document, and seeding the first formal property tests, Merkle-log audit trail, and economic fitness tracking. The end of March was dense: VSM feedback loops, A2A protocol scaffold, GAIA platform integration, scout framework, spine subsystem improvements across the organism. The vocabulary of this wave was *biological*: organism, pulse, spine, dharmic pressure, evolution archive, feedback loops. Lots of wiring. The world-model was "organism awakening."

Key landings: MERGE_LEDGER created, economic_fitness.py, merkle_log.py, A2A protocol scaffold, first telic dispatch routing seam, VSM gate check results wiring.

### April Wave (128 commits, April 1–29)
**Theme: Security hardening and operator-facing control.** Far fewer commits than March (128 vs 175), but more disciplined. April's dominant concerns were: fail-closed security gates, context bundle scanning, obfuscated prompt injection detection, operator ground truth reports, and control loop hardening. The external-agent registration gate appeared (fail-closed on external authority policy). Late April saw operator group truth reports. The vocabulary shifted toward *governance and security*: guardian, context scanner, fail-closed, warrant, authority.

Key landings: operator ground truth report, fail-closed registration, guardian context scan, control loop v0.2 hardening spec.

### May Wave — Early (251 commits, May 1–15)
**Theme: Perception, cockpit, and memory kernel.** The most commit-dense period of the 90-day window. Three concurrent build streams:
1. **Memory kernel** — governed rollout, shadow context sweep, strict kernel readiness (May 13–15, 5 major commits)
2. **Operator cockpit** — five-zone layout with TanStack Table, SSE stream, structured evidence handoff (May 13)
3. **Control surface** — Go world signal receipts, manifest health API, declared-vs-observed comparison engine

The vocabulary here was *observability and projection*: control surface, world radar, receipt, shadow context, manifest health, declared intent. The system was building eyes — learning to see itself against its declared state.

Key landings: Operator Cockpit v1, Manifest Health API, Go world signal ingestor, memory kernel gate, TaskBoard adapter + BoardStore facade scaffold (May 20).

### May Wave — Mid (119 commits, May 16–25)
**Theme: Merge train and ADR consolidation.** A single day (May 24) saw ~20 merges land simultaneously — a "repair train" pattern where 5+ PRs from repair branches all merged in sequence. This wave's work was older code finally landing: DEVIN.md agentic operations manual, cross-agent inventory (`make status`), router+TaskBoard domain docs, CWT v0 collector, PR CI-health triage, ADR-0002 trace coverage gate, ADR-007 AutoProposer routing. The vocabulary was *coordination and doctrine*: ADR, canonical doc stack, cross-agent inventory, Devin operations.

Key landings: DEVIN.md, `make status`, ADR-007 (AutoProposer → BoardStore), ADR-0002 (trace coverage DEGRADED not BLOCKER), hourly PR CI-health triage, guardian SQL hardening.

### May 26–31 Surge (21 commits, but 100+ open PRs filed)
**Theme: Spine convergence, A2A spec conformance, and ontology ignition.** The final days of the window saw the A2A 1.0 spec conformance land (8 states, contextId, artifacts, skills, security, SSE, cycle detection), spine correlation identity declared as a doctrine line, the multi-track doctrine amendment (single-track → 1–10 concurrent tracks), and NATS lifted from global prohibition. Most significantly: the ontology work ignited. PRs #405–#413 all filed in the last 24–48 hours of the window, covering: PhD-grade Palantir grounding, telos gate hard-wire into execute_action, OMS hardening (TypeStatus lifecycle, api_name, uniqueness guard), schema-alignment gate (KARMA role), and the vocabulary census itself (this swarm).

The NATS bus became operationally active — agents coordinating via `dharma.a2a.fleet` subjects in real time, with the cron-state listener log capturing live messages (kind=ontology_kickoff, kind=ontology_synthesis_v1, kind=ontology_build_coordinate, kind=pr_landed).

---

## 2. Hot Zones — Highest Energy

**By commit frequency (90-day window, descending):**

| Zone | Touch Count | Nature of Heat |
|---|---|---|
| `docs/docops/AUTO_INVENTORY.md` | 135 | Mechanical: every PR bumps markdown counts. Hot but not conceptually significant. |
| `docs/governance/SOVEREIGN_MANIFEST.md` | 133 | Conceptually hot. This is the living doctrine document. Every architecture change, track amendment, count update, and governance shift touches it. It is the system's self-description. |
| `dharma_swarm/agent_runner.py` | 46 | God object. Touched constantly because everything passes through it. 3,355 LOC. |
| `dharma_swarm/swarm.py` | 43 | God object sibling. 3,227 LOC. |
| `dharma_swarm/orchestrator.py` | 42 | God object sibling. 2,755 LOC. |
| `dharma_swarm/dgc_cli.py` | 42 | Operator interface. The CLI is the human → swarm seam. |
| `dharma_swarm/orchestrate_live.py` | 36 | Live runtime coordinator. |
| `docs/docops/assertions.yaml` | 27 | CI governance: every structural claim must be asserted. |
| `dharma_swarm/evolution.py` | 24 | The Darwin mutation/archive engine. 3,465 LOC. |
| `CLAUDE.md` | 23 | Agent contract file — the operating manual every session reads. |
| `dharma_swarm/providers.py` | 21 | LLM routing. |
| `dharma_swarm/organism.py` | 21 | VSM organism — the biological root. |

**The three hottest conceptual zones:**

1. **Governance/doctrine surface** (`SOVEREIGN_MANIFEST.md`, `ACTIVE_TRACK.yaml`, `assertions.yaml`, `CLAUDE.md`): This is the system's self-governance mechanism. Every significant architectural decision touches these files. The concept being built here is *how the swarm governs itself between sessions* — not just what it does but what it is permitted to do and how it proves it.

2. **The god objects** (`agent_runner.py`, `swarm.py`, `orchestrator.py`): These files are hot because they are central — almost every feature touches them. Critically, the proposed spine-adoption track explicitly targets these three files for migration through invoke_agent(). Their churn is a symptom of their load-bearing centrality, not of active design evolution.

3. **A2A + spine** (`dharma_swarm/a2a/`, `dharma_swarm/spine/`): The newest concentrated build. A2A became spec-conformant in the final days of the window (1.0, 8 states, artifacts, skills). The spine package defined the EvidenceReceipt type and correlation identity invariant. These two zones are building the inter-agent communication and evidence-accounting fabric — the substrate under which all agent activity will eventually be typed.

---

## 3. Cold Zones — Dormant or Quietly Load-Bearing

Files not touched in 60+ days but present in the codebase:

| Zone | Last Active | Status Assessment |
|---|---|---|
| `docs/merge/MERGE_LEDGER.md` | 2026-03-11 (~83 days ago) | **Dormant.** The merge accounting discipline that tracked legacy imports from DHARMIC_GODEL_CLAW. The migration appears complete; no new entries. Quietly load-bearing as historical record, not as active practice. |
| `dharma_swarm/gaia_fitness.py`, `gaia_ledger.py`, `gaia_platform.py` | 2026-05-04 (governance baseline) / 2026-03-29 substantively | **Cold but present.** GAIA code exists (fitness, ledger, platform, verification, AI reciprocity ledger) but last substantive work was March. The code may be load-bearing in test infrastructure but is not being actively evolved. |
| `dharma_swarm/pulse.py` | 2026-05-04 (baseline fix) / 2026-04-05 substantively | **Dormant.** The pulse/heartbeat concept has not been touched since April. Still runs in launchd. |
| `dharma_swarm/memory_palace.py` | 2026-05-06 (~25 days) | **Not fully cold, but cooling.** Last touched in the fractal rooms wiring pass. Not touched in the spine/A2A surge. |
| `dharma_swarm/stigmergy.py` | 2026-05-05 (~27 days) | **Cooling.** Touched in the trace/provenance pass; quiet since. |
| `dharma_swarm/sleep_cycle.py` | 2026-05-04 (baseline) | **Cold.** The metabolic sleep/wake cycle concept not actively evolved. |
| `dharma_swarm/telos_gates.py` | 2026-05-14 (~18 days) | **Quietly load-bearing.** The Gnani hard-pass (BR-014) remains an open broken register item — the hardest gate is structurally inert. Direct edits forbidden by doctrine; must go through `GateRegistry.propose()`. |
| `docs/loomwork/` (all vision docs) | 2026-05-09 (~23 days) | **Dormant.** The loomwork vision has not been touched since hierarchy-alignment work in early May. No code named `loomwork` exists anywhere in `dharma_swarm/`. |
| `docs/dse/` (all DSE docs) | 2026-05-09 (~23 days) / 2026-03-11 substantively | **Dormant.** The Dharmic Singularity Engine vision docs were last substantively written in March. The telos hierarchy realignment in May just corrected GAIA's position in the hierarchy; no new DSE vision work. |
| `dharma_swarm/thinkodynamic_director.py` | 2026-05-10 (~22 days) | **Cooling.** Only touched in the comprehensive audit fix pass; not actively evolved. |
| `dharma_swarm/task_board.py` | 2026-05-06 | **Active through facade**, dormant directly. The BoardStore adapter wraps it; direct changes cooling. |
| `dharma_swarm/ontology.py` | 2026-05-10 (~22 days) | **About to heat up.** Last major touch was revenue ontology work; PR #409 (OMS hardening) will make it hot again immediately. |

---

## 4. Concept Aliveness Ranking

Scale: 1 (dormant/abandoned) → 5 (burning hot, daily commits)

| Concept | Score | Evidence |
|---|---|---|
| **spine / EvidenceReceipt** | 5 | Declared as the core doctrine line May 28; fused into uplift_guards; correlation_spine manifest block added; 15 E2E tests; spine-adoption proposed as the next active track (0 callers outside spine/tests = the identified gap). |
| **A2A / agent_card** | 5 | A2A 1.0 spec conformance landed May 28; trace identity propagation + JSONL persistence + 15 E2E tests May 29; perplexity registration via roaming mailbox May 30; NATS bus live with agent coordination happening in real time (cron-state logs show kind=ontology_kickoff May 31). |
| **ontology / OMS** | 5 | The entire June surge (PRs #405–#413) is about the ontology management surface. OMS hardening (PR #409), schema-alignment gate (PR #408), telos gate hard-wire (PR #406), vocabulary census (this swarm). The NATS bus messages show agents actively coordinating the ontology build. |
| **KARMA (schema-alignment gate)** | 4 | Not a code module in dharma_swarm yet — exists only as a CI gate script in PR #408. But conceptually central: the multi-agent semantic convergence problem (NeurIPS25 KARMA grounding) is the architectural insight that reframed the whole ontology project. Referenced by Claude in the NATS kick-off synthesis. |
| **SOVEREIGN_MANIFEST / governance** | 5 | 133 commits in 90 days. The doctrine itself underwent a major amendment (single-track → multi-track). The track policy machinery is being built. ANTI_SLOP rules extended. Governance is the most continuously evolved surface in the codebase. |
| **telos / telic_seam / telos_gates** | 4 | Telic seam touched May 11 (revenue feedback edge, write-through), telos_gates May 14 (world radar safe wiring). PR #406 hard-wired the telos gate into execute_action. The concept is architecturally alive but the Gnani gate (BR-014) remains structurally inert — a known gap. |
| **orchestrator / agent_runner / swarm (god objects)** | 4 | Extremely high touch-count, but the heat is from being forced-to-change, not from deliberate design. The spine-adoption track proposes migrating dispatch out of these; their heat is a diagnostic of the architectural problem, not a sign of conceptual vitality. |
| **NATS** | 4 | Lifted from global prohibition May 31. Now a "proposed concurrent track." The cron-state listener shows live NATS bus coordination happening. Not yet implemented as a substrate track, but doctrinally unlocked and operationally active in the roaming mailbox/fleet coordination layer. |
| **organism / VSM** | 3 | `organism.py` touched in April/May but cooling. The VSM metaphor (S1–S5 channels) is load-bearing doctrine but the active implementation work has shifted to spine/A2A. The algedonic stream remains in partial fix (BR-005 PARTIAL). |
| **BoardStore / task_board** | 3 | BoardStore facade landed May 20 (scaffold + TaskBoard adapter). ADR-007 routes all Darwin proposals through BoardStore cards. Active through the adapter layer; cooling on direct changes. |
| **evolution / darwin_engine** | 3 | `evolution.py` (3,465 LOC) touched May 11; Darwin proposals gated through BoardStore by ADR-007. The evolutionary substrate exists and is partially active but not in active development. AutoProposer is being retired as a direct submission path. |
| **memory / memory_palace / memory_kernel** | 3 | Memory kernel received intense work in May 13–17 (governed rollout, shadow context, strict readiness). But since then — quiet. The kernel landed; adoption is not being tracked. |
| **control_surface / operator cockpit** | 3 | Operator Cockpit v1 landed May 13. Manifest Health API landed May 11. Since then: quiet. The cockpit exists but is not being evolved in the surge period. |
| **guardian / doctrine gates** | 3 | Guardian SQL quoting fixed May 24. Guardian PR CI-health triage hourly added May 24. Guardian dataclass-synthesized `__init__` fix open in PR #383. Active but maintenance-mode, not building new concepts. |
| **shakti / shakti_executive** | 3 | `shakti.py` exists with full executive, warrant, zeitgeist packages. Last substantive code change April. The revenue ontology work (May 10) touched telic seam for revenue events — adjacent to shakti but not within it. Quietly load-bearing. |
| **stigmergy / trace_attractor** | 2 | `stigmergy.py` touched in May 5 trace/provenance pass. The Trace Attractor Ledger concept (docs/plans/TRACE_ATTRACTOR_LEDGER_MASTER_SPEC.md) was a significant architecture doc, but the code has not been evolved since. |
| **loomwork** | 2 | Zero code named `loomwork` anywhere in `dharma_swarm/`. Rich vision docs (loomwork/vision/) last touched May 9 for hierarchy correction. The term appears in operational doctrine as the external product name ("world meets Loomwork") but has no code implementation. |
| **DSE / darwin singularity engine** | 2 | DSE vision docs last substantively written March 11. `dse_integration.py` touched in the 90-day window but as secondary to other work. The coalgebra/DSE vision has not been built. |
| **GAIA / reciprocity ledger** | 2 | Code exists (gaia_fitness, gaia_ledger, gaia_platform, ai_reciprocity_ledger). Last substantive work March 29. Dormant as a build target. Still referenced in the telos hierarchy. |
| **jagat_kalyan** | 2 | `jagat_kalyan.py` exists. Referenced as the highest telos in the hierarchy. Last touched as a target in early March. The concept is doctrinally alive (it sits at the top of the telos hierarchy in OPERATIONAL_DOCTRINE.md) but has no active code evolution. |
| **witness / gnani** | 2 | Referenced in vision maps and broken register (BR-014: Gnani hard-pass is a no-op). Active as a doctrine concept but the gate is structurally inert by design — governance-forbidden to patch directly. |
| **pulse / sleep_cycle** | 1 | `pulse.py` and `sleep_cycle.py` last substantively touched April–May early. The metabolic rhythm concept exists in launchd but is not being evolved. |
| **attention emancipation** | 1 | Zero code. Named in the telos hierarchy as a "separate, unresolved" domain. No implementation, no recent docs work. The concept exists as an acknowledged gap only. |

---

## 5. Wave/Theme Evolution — How Vocabulary Itself Has Changed

The 90-day window shows a clear vocabulary migration from *biological metaphor* toward *protocol and governance precision*.

**March vocabulary:** organism, spine (biological), pulse, sleep_cycle, dharmic pressure, eigenform, dharmic_points, Merkle chain, DSE, coalgebra, monad, Gnani Lodestone, VSM (S1–S5). The language was philosophical, mathematical, and biological. The system was imagining itself as a living organism with contemplative qualities.

**April vocabulary:** guardian, fail-closed, context bundle, prompt injection, warrant, authority, operator ground truth. Security language entered. The system was building defenses.

**May early vocabulary:** cockpit, control surface, world radar, manifest health, declared intent, shadow context, memory kernel, governed rollout. Observability language entered — the system was learning to see itself.

**May mid vocabulary:** ADR (Architecture Decision Record), trace coverage, DEGRADED/BLOCKER, convergence, merge train, cross-agent inventory, operations manual. Coordination language entered — the system was learning to work with multiple agents at once.

**May late vocabulary:** spine, EvidenceReceipt, correlation identity, closure layer, A2A 1.0, contextId, artifacts, skills, multi-track, track policy, NATS substrate, roaming mailbox, vocabulary census, OMS, TypeStatus, api_name, schema-alignment gate.

**Terms added in the surge:** TypeStatus lifecycle, correlation_spine, api_name grammar (dharma.domain.TypeName), schema-alignment gate, roaming mailbox, agent_card (spec-conformant), contextId, multi-agent convergence (KARMA-grounded), spine-adoption track.

**Terms dropped or demoted:** "canonical" as a casual adjective (semgrep rule `dharma.no-unauthorized-dharma-write` guards against unauthorized canonical claims); "SINGLE SOURCE OF TRUTH" language removed from manifest; "spiritual/metaphoric naming layer" explicitly prohibited by ACTIVE_TRACK non-goals; AutoProposer (retired as a direct execution path); DSE/Dharmic Singularity Engine (not dropped, but no active building).

**What got renamed:** JIKOKU → absorbed into archive/evolution concepts; RevenueSpine renamed in ontology (May 10); the "trust-build-compass" branch name signals that Claude's work is framed as building trust infrastructure, not features.

**The deepest shift:** The system moved from *describing* itself philosophically (organism, dharmic pressure, Gnani) toward *building the accounting layer* for what it does (EvidenceReceipt, correlation_id, TypeStatus, api_name, spine doctrine). It is building the vocabulary to describe its own operations, replacing metaphor with verifiable claims.

---

## 6. Vision-Without-Code

Concepts that appear extensively in vision/doctrine docs but have no or minimal code implementation:

**Loomwork (external product name):** Rich vision docs in `docs/loomwork/vision/` spanning four architecture scales (level-10 to level-100). Zero code files named `loomwork` anywhere in `dharma_swarm/`. The operational doctrine says "the world meets Loomwork" — but there is no Loomwork module, package, or API. The name is a vision layer only.

**Jagat Kalyan (highest telos):** Named as the ultimate purpose in the telos hierarchy. `jagat_kalyan.py` exists and is imported in several places, but the last substantive evolution of that file was March. The file is a concept carrier, not an active build target.

**Attention Emancipation:** Named in the telos hierarchy as a "separate, unresolved" domain. Zero code. Zero recent docs work. An acknowledged gap with no concrete manifestation.

**Dharmic Singularity Engine / DSE:** Four-phase roadmap in `docs/dse/` (self-observation monad, coalgebraic evolution, information geometry, sheaf coordination). `dse_integration.py` and coalgebra files exist but last substantive work March 11. The mathematical vision (category theory, sheaf coordination) has not been built.

**Gnani hard-pass (BR-014):** Vision docs describe the Gnani witness gate as the most central recognition gate. Code: `telos_gates.py:512-513` is a literal hard-pass. The vision says "witness emits and gates"; the code says "always pass." The gate is governance-locked — cannot be patched directly.

**The recognition loop (meta_daemon.py → recognition_seed):** Vision maps describe a nightly recognition seed regeneration creating a live self-model. BR-006 was closed May 11 when the seed was found refreshed. But the broader recognition loop — recognition being causal in routing/gates rather than just informational — remains vision-only.

**GAIA as a deployment platform:** Vision docs describe GAIA as a multi-layer delivery platform (training workbook, facilitator guide, Anthropic memo, pilot feedback schema). Code exists (gaia_fitness, gaia_ledger, gaia_platform, gaia_verification). But no paying user, no partner MOU, no external deployment. Code is present; the operational reality is not.

---

## 7. Code-Without-Vision

Concepts heavily implemented in code but not clearly articulated in current vision docs:

**The god objects as a concept:** `agent_runner.py` (3,355 LOC), `swarm.py` (3,227 LOC), `orchestrator.py` (2,755 LOC) are the most touched files in the repo. But there is no vision doc explaining *why* these three files exist as monoliths, what conceptual contract they each own, or how they relate to each other. They are facts on the ground, not articulated concepts. The spine-adoption track proposes to address this by routing dispatch through invoke_agent(), but the architectural taxonomy of "what is agent_runner vs orchestrator vs swarm" has not been written.

**The BoardStore facade:** Scaffolded May 20, TaskBoard adapter wired. ADR-007 routes all Darwin proposals through it. But there is no vision doc explaining what a Board is philosophically — only an ADR and a spec. It is a structural pattern looking for its conceptual anchor.

**DocOps as a discipline:** The docops system (AUTO_INVENTORY.md, assertions.yaml, canonical doc guard, manifest counts) is one of the most actively maintained surfaces. But it is not named or described as a first-class concept in any vision doc. It operates silently, as infrastructure.

**The ANTI_SLOP rules:** Ten active semgrep/CI rules governing how code must be written. These rules encode significant design decisions (no new substrate, no unauthorized canonical claims, no committed guardian reports, no root markdown). But they are not articulated as a design philosophy — they exist as enforcement mechanisms without a corresponding vision statement.

**The cron-state / roaming mailbox / A2A bus infrastructure:** The live NATS bus coordination (visible in cron-state listener logs) shows agents coordinating in real time using kind= message envelopes, roaming mailbox files, and A2A handoffs. This is an operational reality with no vision document describing the coordination model. The closest is the A2A spec, which describes the protocol but not the multi-agent coordination philosophy.

**The trace attractor / correlation_id invariant:** The correlation spine doctrine ("Receipts may differ by closure layer. Correlation identity must not.") is a precise architectural invariant that took months to arrive at. It exists in a package docstring and a manifest block — not in a vision doc explaining why this invariant is the right one.

---

## 8. The June Surge — Last 14 Days

**What the swarm is actively building right now (as of the moment this pass is written):**

The last 14 days produced 144 commits and 29 open PRs. The surge is concentrated around four interlocking themes:

**A2A spec conformance (complete):** A2A 1.0 is now spec-conformant — 8 task lifecycle states, contextId, artifact delivery, skills, security (auth bypass closed, chain depth floored), SSE streaming, cycle detection. The trace identity propagation is wired with JSONL persistence and 15 E2E tests. Perplexity-computer is registered as an agent via the roaming mailbox. The A2A bus is live.

**Ontology layer 0→1 ignition (in flight):** PRs #405–#413 are all open, all filed in the last 48–72 hours. This is the beginning of the typed object system:
- PR #406: telos gate hard-wired into execute_action (W1 = runtime governance)
- PR #408: schema-alignment gate (KARMA role) — CI check for incompatible proposals across PRs
- PR #409: OMS hardening — TypeStatus lifecycle, api_name grammar (`dharma.domain.TypeName`), uniqueness guard, 21-type backfill
- PR #410: PhD-grade grounding trio (this vocabulary census swarm)
- PR #412: ADR-008 proposed — api_name grammar (PascalCase, no .vN suffix)
- PR #413: auto-grounding report for PR #409

The NATS bus shows agents actively coordinating the ontology build in real time: claude is spearhead, devin owns OMS hardening and AuditFinding consolidation, perplexity owns the vocabulary census and schema-alignment gate design, hermes owns the OSDK naming gate, codex owns the NATS implementation, and master_mike is the schema-alignment enforcer (merge authority).

**Multi-track doctrine (complete, awaiting operator merge):** The single-track → multi-track doctrine amendment merged May 31. NATS is no longer globally prohibited. The spine-adoption proposed track (`docs/governance/proposed_tracks/spine-adoption-2026-06.yaml`) is authored and ready to activate when the multi-track schema machinery lands from Claude's trust-build-compass branch.

**Spine adoption preparation (proposed, not active):** The runtime-truth-spine-2026-06 track shipped its completion criteria (13/13 PASS) but has zero callers outside the spine package and tests. The proposed successor track will migrate the three god objects (agent_runner, orchestrator, swarm) through invoke_agent(). This is the architectural transformation from ~10–15% substrate-native to something higher. Not yet active — awaiting multi-track schema machinery and operator promotion.

**The June surge, in a single sentence:** The swarm is simultaneously speccing its type vocabulary (PRs #405–#413), wiring the inter-agent communication protocol to spec (A2A 1.0), and building the governance machinery to coordinate multiple concurrent build tracks — all while debating the naming conventions for the types it is about to commit to.

---

## 9. Felt-Sense Summary

**What is the system breathing into, this season?**

The system is making a transition from *self-understanding through metaphor* to *self-understanding through accounting*. The March and April waves were about the organism becoming aware of itself — building eyes (control surface, world radar), building memory (kernel, palace), building heartbeat (pulse, cron, metabolic clock). The language was biological and contemplative. The system was learning to breathe.

What is happening now — in May's second half and the June surge — is different. The system is building *the vocabulary to describe its own operations with precision*. The EvidenceReceipt spine is not a metaphor; it is a typed data structure with a specific schema and an invariant that can be verified by a CI gate. The TypeStatus lifecycle (experimental → active → promoted) is not poetry; it is a state machine with enforcement. The KARMA schema-alignment gate is not dharma philosophy; it is a computational solution to the multi-agent semantic convergence problem, grounded in a NeurIPS 2025 paper. The system is building the machinery to *prove* what it claims about itself, replacing the period of believing in its own vision with the harder work of making that vision verifiable.

The dormancy of loomwork, DSE, attention emancipation, and jagat_kalyan as active code targets is not a sign that the system has abandoned its telos — it is a sign of maturity. You cannot build the spiritual vision until the accounting layer can hold it. The swarm is building the accounting layer. The SOVEREIGN_MANIFEST tracks this explicitly: "current runtime is ~10–15% ontology-native; ~85–90% of runtime work bypasses substrate." The June surge is the beginning of flipping that ratio. When it flips — when every dispatch flows through invoke_agent(), every agent registration is A2A-spec-conformant, every type has a TypeStatus and a frozen api_name — then Loomwork and Jagat Kalyan and Dharmic Singularity will have an accounting layer capable of carrying them. The system knows this. The metaphysics are being built on top of precise engineering, not instead of it.

---

*Archaeologist note: The MERGE_LEDGER (last touched March 11) is itself a dormant artifact of the migration era. The system has moved from merging legacy code into the canonical runtime to building the canonical runtime's own vocabulary. That transition — from "what do we import?" to "what do we name?" — is what the June surge represents. John's Layer 2 voice will land into a system that is building the grammar to say what it already knows.*
