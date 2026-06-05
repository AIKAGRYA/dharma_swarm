# Pass 1d — Prior-Art Critique
**Author:** perplexity-computer (adversarial, non-validating)  
**Date:** 2026-06-01  
**Charter ref:** `00-swarm-charter.md`  
**Posture:** Challenge. Where did Devin's 21 come from? Which earn their place? Which are decoration?

---

## 1. Devin's 21, Enumerated

All 21 names come from `dharma_swarm/ontology.py` on branch `devin/1780259643-oms-hardening` (PR #409). Their `api_name` slugs follow the grammar `dharma.<domain>.<TypeName>` — the `.v<N>` suffix that PR #408's regex enforced was already dropped by the time the backfill landed (PR #409's body notes "3 commits: initial, PascalCase rebase, .vN drop"). Each type is declared with `status=TypeStatus.ACTIVE`.

| # | Name | Domain | Declared Purpose |
|---|------|--------|-----------------|
| 1 | **ResearchThread** | research | A research direction with experiments and findings — the container unit for a line of investigation |
| 2 | **Experiment** | research | A specific test: config, execution, results, fitness, r_v_value — the atomic research act |
| 3 | **Paper** | research | An academic paper with claims, evidence, and submission status — the publishable artifact |
| 4 | **AgentIdentity** | agent | A swarm agent with role, capabilities, permissions — the system's self-model of who is acting |
| 5 | **CustodianRole** | agent | A persistent identity for an autonomous code-maintenance custodian role — the devin/hermes/mike archetype |
| 6 | **KnowledgeArtifact** | knowledge | A piece of knowledge: file, note, finding, measurement, code — the epistemic catch-all |
| 7 | **TypedTask** | task | A task with ontology-aware inputs, outputs, and lineage — the unit of work flowing through the metabolic loop |
| 8 | **EvolutionEntry** | evolution | A record in the Darwin Engine evolution archive — one mutation/crossover/ablation proposal and its result |
| 9 | **WitnessLog** | governance | The act of checking IS witnessing — audit trail as dharmic practice |
| 10 | **ActionProposal** | governance | A proposed action before gate evaluation — the metabolic loop entry point |
| 11 | **GateDecisionRecord** | governance | Result of telos gate evaluation on an ActionProposal — PASS/FAIL with gate reasoning |
| 12 | **ExecutionLease** | execution | The orchestrator's active claim lease for executing an ActionProposal — locking primitive |
| 13 | **Outcome** | execution | What happened after an ActionProposal was executed — terminal record of actual effect |
| 14 | **ValueEvent** | economic | Measures the value an Outcome produced — the credit chain entry point |
| 15 | **Contribution** | economic | Assigns credit from a ValueEvent to an agent — what routing reads for incentive alignment |
| 16 | **VentureCell** | economic | Fractal project container — first-class ontology object with its own agents, budgets, KPIs |
| 17 | **RevenueTarget** | revenue | A potential buyer/opportunity identified by scouting |
| 18 | **RevenueOffer** | revenue | A packaged service offering mapped to target pain |
| 19 | **RevenueOutreachDraft** | revenue | A drafted outreach message awaiting human approval — NO autonomous send |
| 20 | **RevenueEngagement** | revenue | An active paid engagement with a target |
| 21 | **ComputeReinvestment** | revenue | Reinvestment of revenue into compute, training, or infrastructure |

---

## 2. Provenance Scan

Methodology: `grep -r <name> --include="*.py" --include="*.md" -l` across the full repo, excluding `.git`. For each type, I count non-ontology-file references and characterize whether callers are producers (write instances), consumers (read/query instances), or nominators (mention the name in docs/plans without wiring).

### Metabolic Loop Cluster (types 10–15)

These six types form a tightly wired chain: `ActionProposal → GateDecisionRecord → ExecutionLease → Outcome → ValueEvent → Contribution`. All six are **directly instantiated** in `dharma_swarm/telic_seam.py` (TelicSeam), which is called from `dharma_swarm/agent_runner.py`. The chain is also consumed in `dharma_swarm/operator_brief/persistence.py`, `operator_brief/insight_brief.py`, `trace_attractor/readers.py`, `trace_attractor/projector.py`, `trace_attractor/models.py`, `shakti_executive/feedback_writer.py`, `engine/store_sync.py`, `operator_core/telic_value_reader.py`, and `assurance/scanner_lifecycle.py`. This is the most wired cluster in the registry.

- **ActionProposal**: 20+ non-ontology files. The orchestrator creates proposals; gate evaluators write decisions against them; the insight brief surfaces them. Real producer+consumer chain. ✓
- **GateDecisionRecord**: 20+ non-ontology files. Written by `telic_seam.py` after gate evaluation; read by agent_runner, orchestrator, and operator briefing. ✓
- **ExecutionLease**: 10 non-ontology files. Written by `telic_seam.py`; used in `orchestrator.py`, `assurance/scanner_lifecycle.py`, `telic_seam.py`. ✓
- **Outcome**: 20+ non-ontology files. `telic_seam.py` writes both success and failure Outcomes; broadly consumed across revenue, operator briefing, and evolution. ✓
- **ValueEvent**: 20+ non-ontology files. Dedicated `operator_brief/value_events.py` module; consumed by shakti_executive, telic_value_reader, dgc_cli. ✓
- **Contribution**: 15+ non-ontology files. `telic_seam.py` writes; `shakti_executive` reads to assign agent credit. ✓

### Agent Cluster (types 4–5)

- **AgentIdentity**: 20+ non-ontology files. Referenced in `agent_registry.py`, `agent_runner.py`, `autonomous_agent.py`, `contracts/intelligence_agents.py`, `operator_bridge.py`, `persistent_agent.py`, multiple API routers. Real backbone type. ✓
- **CustodianRole**: 3 non-ontology files (`dharma_swarm/custodians.py` defines a parallel native `CustodianRole` class; `tests/test_custodians.py`; `tests/test_ontology_registry.py`). The `custodians.py` native class is the real one. The ontology type is a secondary registration of it. Partial real grounding. ~

### Revenue Cluster (types 17–21)

- **RevenueTarget**: 20+ non-ontology files. `revenue/spine_models.py`, `revenue/spine.py`, `revenue/scout_daemon.py`, `revenue/intelligence.py`, `revenue/telic_bridge.py`, scripts, tests. The `spine_models.py` module has its own native `RevenueTarget` Pydantic model that predates the ontology type. Real grounding. ✓
- **RevenueOutreachDraft**: 8 non-ontology files. `orchestrate_live.py`, `revenue/scout_daemon.py`, `revenue/spine.py`, `revenue/telic_bridge.py`, tests. Real grounding. ✓
- **RevenueEngagement**: 4 non-ontology files. `revenue/telic_bridge.py` and tests. Thin but real. ~
- **ComputeReinvestment**: 8 non-ontology files. `revenue/spine.py`, `revenue/spine_models.py`, `revenue/telic_bridge.py`, `shakti_executive/inputs.py`, `operator_core/telic_value_reader.py`, tests. Real grounding. ✓
- **RevenueOffer**: **2 total files** — `ontology.py` (definition) + `tests/test_ontology_registry.py` (registry presence test). Zero real producers or consumers outside the registry. The native `spine_models.py` has an `Offer` Pydantic class and an `OfferType` enum, but this never references the ontology type `RevenueOffer`. Name mismatch between native model ("Offer") and ontology type ("RevenueOffer"). ✗

### Economic Cluster (types 14–16 overlap with metabolic)

- **VentureCell**: 20+ non-ontology files. `dharma_swarm/fractal/` module suite (`fractal_room.py`, `room_bridge.py`, `room_brief.py`, `room_configs.py`, `room_health.py`), `orchestrate_live.py`, `orchestrator.py`, `telos_substrate.py`, `operator_brief/types.py`, `dgc_cli.py`. Substantial real grounding. ✓

### Research Cluster (types 1–3)

- **Experiment**: 20+ non-ontology files — but most references are to **two other native `Experiment` classes** (`dharma_swarm/self_research.py:37` and `dharma_swarm/amiros.py:42`), neither of which is the ontology `ObjectType`. The ontology type sits in `dharma_swarm/ontology.py` and appears in GraphQL schema and API routers, but there is no adapter that maps the native `Experiment` classes to the registry type. Name collision between three distinct things. ✗/~
- **ResearchThread**: Referenced in `ontology_adapters.py` (the adapter creates objects), in the GraphQL schema, and in `docs/governance`. The `ontology_adapters.py` wires a `ZeitgeistSignal → ResearchThread` link but never creates `ResearchThread` instances from real data. The adapter code explicitly notes: "ResearchThread the signal relates to, which is not encoded." Declared but not populated. ~
- **Paper**: Referenced in `api/routers/ontology.py`, GraphQL schema, multiple docs. But in actual dharma code, `Paper` appears as "ginko paper trade" (completely different meaning — simulated paper trading portfolio). No producer creates `Paper` ontology objects from research outputs. The system does not yet write academic papers programmatically. ✗

### Knowledge & Task (types 6–7)

- **KnowledgeArtifact**: 20 non-ontology files. `operator_brief/persistence.py` writes KnowledgeArtifacts; `operator_brief/watchdog.py` monitors them; `trace_attractor/readers.py` consumes them; `revenue/wedge_pipeline.py` references them. The type is a real catch-all used across the system. ✓
- **TypedTask**: 10 non-ontology files. GraphQL schema, `trace_attractor/readers.py` (listed in DEFAULT_ONTOLOGY_TYPES), `docs/missions/EVOLUTION_META_LOG_2026-03-21.md`. Referenced but thinly produced — `trace_attractor/readers.py` reads objects by this type_name but the ontology has no adapter that creates TypedTask objects from the native task system. The task system runs on separate internal primitives. ~

### Governance Cluster (type 9)

- **WitnessLog**: 20+ non-ontology files. `cron_runner.py`, `fractal/fractal_room.py`, `fractal/room_bridge.py`, `harness_audit.py`, `meta_daemon.py`, `persistent_agent.py`, `operator_brief/` suite, `trace_attractor/models.py`, `trace_attractor/projector.py`. Broadly produced and consumed. ✓

### Evolution (type 8)

- **EvolutionEntry**: 8 non-ontology files. GraphQL schema, API routers, `ontology_adapters.py`, test files. But `dharma_swarm/evolution.py` defines its own `Proposal` class (Pydantic, 95 lines) that is the real Darwin Engine data model — and `evolution.py` has zero references to `EvolutionEntry`. There is no adapter bridging the native `Proposal` to the ontology `EvolutionEntry`. The ontology type is aspirational, not wired. ~

---

## 3. Load-Bearing vs. Cargo-Cult

### (a) Load-Bearing — Real producers + consumers + vision grounding

These types have evidence of: (1) being written/instantiated by non-ontology code, (2) being read or consumed by downstream code, and (3) explicit grounding in doctrine or vision docs.

1. **ActionProposal** — The metabolic loop starts here. TelicSeam writes it; gate evaluators read it; the entire execution accounting hangs on it. The FOURFOLD_ACTION_WARRANT doc grounds it philosophically. Cannot remove without dismantling the credit chain.
2. **GateDecisionRecord** — The constitutional gate's output record. Written by TelicSeam, read by orchestrator. SATYA/AHIMSA gating is meaningless without persistence. Load-bearing.
3. **ExecutionLease** — The idempotency primitive. The orchestrator cannot safely dispatch without this locking record. Real operational necessity.
4. **Outcome** — The terminal result of any executed proposal. Every agent's success or failure writes an Outcome. The full credit chain (ValueEvent, Contribution) references it. Cannot remove.
5. **ValueEvent** — The credit-chain entry point. `operator_brief/value_events.py` is a dedicated module. Shakti executive reads it to route attention. Load-bearing.
6. **Contribution** — What makes agent credit attribution possible. Shakti scoring depends on it. Load-bearing.
7. **AgentIdentity** — The self-model. `agent_registry.py`, `agent_runner.py`, `contracts/intelligence_agents.py` all reference it. The system cannot talk about who did what without this.
8. **WitnessLog** — Deeply wired into `cron_runner`, `harness_audit`, `meta_daemon`, `persistent_agent`. The witnessing practice is constitutively operative, not aspirational.
9. **KnowledgeArtifact** — `operator_brief/persistence.py` produces them; `trace_attractor` consumes them. The catch-all epistemic type is a live traffic lane.
10. **VentureCell** — The `fractal/` module suite is a real working subsystem. VentureCell is the ontological representation of that subsystem's central object.
11. **RevenueTarget** — `revenue/spine_models.py` defines the native model; the ontology type mirrors it. Real pipeline scouting produces targets.
12. **RevenueOutreachDraft** — `orchestrate_live.py` and `revenue/scout_daemon.py` produce these. The human-approval gate depends on their existence.
13. **ComputeReinvestment** — `revenue/spine_models.py` defines it natively; the telic_bridge records reinvestment events. Real accounting.

**Count: 13 load-bearing.**

### (b) Aspirational-but-grounded — Vision says this; code does not yet produce it; but it belongs

14. **TypedTask** — The vision docs (`EVOLUTION_META_LOG_2026-03-21`, `NEXT_10_SUBSTRATE_TODO`) describe an ontology-native task system. The native task dispatching hasn't been bridged to the ontology type yet. The `trace_attractor/readers.py` lists it in `DEFAULT_ONTOLOGY_TYPES`, anticipating data. Belongs; not yet producing.
15. **EvolutionEntry** — The Darwin Engine runs a real `Proposal` lifecycle (`dharma_swarm/evolution.py`). That lifecycle should write to the ontology. The adapter is missing, not the concept. Belongs.
16. **CustodianRole** — `dharma_swarm/custodians.py` defines the native class. The ontology type is a valid second-order registration. The adapter that syncs custodians to the registry exists but is thin. Belongs; partially wired.
17. **ResearchThread** — The ZeitgeistSignal→ResearchThread link in `ontology_adapters.py` anticipates thread-grouping of research signals. The concept is correct; the population logic is a stub. Belongs; population missing.
18. **RevenueEngagement** — `revenue/telic_bridge.py` writes engagement records. Thin but real. The type captures an operationally important stage (paid work has started). Belongs.

**Count: 5 aspirational-but-grounded.**

### (c) Speculative / Cargo-Cult — No real producers, no real consumers, or concept not earned by this system

19. **Paper** — dharma_swarm does not write academic papers programmatically. The system's `Paper` mention in `dharma_swarm/` files refers to financial "paper trading" (ginko_paper_trade.py) — a completely different domain. The ontology type `Paper` models an academic submission lifecycle (drafting → submitted → accepted) that has no producer in the codebase. The system has no LaTeX pipeline, no arXiv submitter, no paper claim tracker. This type is aspirational at best, and it's borrowing a name that is semantically polluted in the codebase. **Cargo-cult.**
20. **RevenueOffer** — 2 files total (registry definition + existence test). The native `spine_models.py` uses the class `Offer` (not `RevenueOffer`), and nothing bridges them. No producer. The `RevenueOffer` ontology type is not the same object as `Offer` in the revenue pipeline; they are named differently and connected by nothing. **Cargo-cult.**
21. **Experiment (ontology type)** — The concept of experiments is real and alive (`self_research.py`, `amiros.py`). But the ontology `Experiment` type is a third definition that coexists with two native Experiment classes without bridging any of them. The `ontology_adapters.py` has no adapter for Experiment. The type definition is a good name attached to an orphan schema. Cargo-cult in its current wiring, though the concept belongs in the vocabulary.

**Count: 3 speculative / cargo-cult.**

**Summary of classification:**
- **Load-bearing: 13** (ActionProposal, GateDecisionRecord, ExecutionLease, Outcome, ValueEvent, Contribution, AgentIdentity, WitnessLog, KnowledgeArtifact, VentureCell, RevenueTarget, RevenueOutreachDraft, ComputeReinvestment)
- **Aspirational-but-grounded: 5** (TypedTask, EvolutionEntry, CustodianRole, ResearchThread, RevenueEngagement)
- **Speculative/cargo-cult: 3** (Paper, RevenueOffer, Experiment-as-ontology-type)

---

## 4. What Palantir Actually Does

Synthesized from the Palantir community design guide (Foundry Solutions Architect, Nov 2025, [Ontology and Pipeline Design Principles](https://community.palantir.com/t/ontology-and-pipeline-design-principles/5481)), the Palantir API reference cited in PR #410's palantir-api-discipline.md, and the PALANTIR_ONTOLOGY_GAP_ANALYSIS archive.

### ObjectType Naming

> "Object Types and Actions should map to natural-language business concepts. The Ontology is built to support operational decision-making. Your primary audience is business users."
> — Palantir Solutions Architect, Nov 2025

- Names are **plain camelCase**, no namespace prefix, no version suffix. Canonical examples: `employee`, `Flight`, `Employee`.
- Names must avoid abbreviations ("Good: Aircraft. Bad: AC").
- Groups (collections in Ontology Manager) replace tag prefixes. Never `[demo]Customer` — use a "Demo" group and a clean `Customer` type.
- **Absolutely no versioned names**: "Avoid versioned Object Type names. Bad: Message_v2. Worse: Message_v3_Embedded." This is the direct inverse of what PR #408's regex enforced.

### api_name vs. RID

- The `api_name` (ObjectTypeApiName) is **mutable** — Palantir docs state "After creating a new object type, you can change the API name from the assigned default." It is the developer-facing human shorthand.
- The **Resource Identifier (RID)** — `ri.ontology.main.object-type.<UUID>` — is the stable machine identity. It never changes.
- dharma_swarm's claim that `api_name` is "frozen and immutable" misreads Palantir's model. The RID is immutable; the api_name is a mutable shorthand that you *should not change* once OSDK consumers depend on it (because changes break generated code at compile time). This is a social contract, not a platform constraint.

### Status Lifecycle

Palantir has **five** statuses, not three:
- `experimental` — Default. Unfinished; expect changes.
- `active` — Stable. Breaking changes communicated. Activates deletion protections.
- `deprecated` — No production usage; slated for deletion. Carries deprecation reason, deadline, replacement pointer.
- `example` — Demo/tutorial content only; not for production reference.
- `promoted` — Highest trust. Core resource. Requires Ontology Owner role. Object types only.

Status cascades are platform-enforced: moving a type to `experimental` automatically makes all its properties `experimental`; deprecated properties make dependent links deprecated. This cascade is entirely absent from dharma_swarm's model.

### Link Types

> "Configure Link Types. Isolated Objects are often a red flag for bad Ontology design."
> "Link Type API name on the plural side should be plural."
> — Palantir Solutions Architect

Links are explicit, named, bidirectional, with distinct names for each side. Bad: `Port ↔ Ship` as just "Port" and "Ship". Good: `Port ↔ Ship` as "Current Port" / "Docked Ship" and "Visited Ports" / "Ships Harboured."

### Action Types

Actions are structured mutations with: typed parameters, submission criteria (validation rules), permissions, side effects, audit logging. The action log is itself first-class: each submission creates an action log object type entry including the action type version (auto-incremented). Actions are the *kinetic* layer; objects are the *semantic* layer.

### Primary Key / ID Rules

- Primary key must be string type, always. No exceptions.
- Primary key must be named `id` in a separate column.
- Primary key must be intrinsic to the object, not derived from external ordering or UUIDs regenerated at pipeline runtime.

---

## 5. Where Devin's 21 Diverge from Palantir-Canonical

Beyond the casing correction already addressed in ADR-008 (PR #412), the structural divergences are:

### 5.1 Namespace Prefix in api_name — Conceptual Mismatch

Devin's `dharma.<domain>.<TypeName>` prefix structure has no Palantir precedent. Palantir uses flat camelCase api_names (`employee`, `Flight`). The namespace (`dharma.research.`, `dharma.governance.`, etc.) is doing org-level disambiguation work that Palantir handles through **Groups** in the Ontology Manager — a UI grouping that doesn't pollute the api_name. Importing the namespace into the api_name means every OSDK consumer must write `dharmaResearchResearchThread` or equivalent — which is precisely the kind of name the Palantir guide calls a disaster: "This results in production ontologies with APIs such as `demoCustomer` four years into deployment."

**Implication:** The api_name should probably be just the TypeName in camelCase (`researchThread`, `actionProposal`). Namespace/domain grouping belongs in a separate `domain` field or in the OMS group mechanism, not in the api_name string.

### 5.2 The `.v<N>` Suffix Was An Anti-Pattern (Already Dropped)

PR #409 dropped it during the "PascalCase rebase, .vN drop" commit. Good. But the fact that PR #408's align-gate encoded it as the enforced pattern, and that it took a PhD grounding trio to name it as an anti-pattern, reveals the pattern was adopted without Palantir source consultation.

### 5.3 Three-State Status vs. Five-State

The PR #409 status enum is `EXPERIMENTAL / ACTIVE / PROMOTED`. Palantir's is `experimental / active / deprecated / example / promoted`. The two missing states are operationally critical:
- `DEPRECATED` is the machine-readable sunset signal. Without it, there is no way for an agent consumer to know "stop depending on this type." The system currently has no deprecation workflow.
- `EXAMPLE` would allow sandbox/demo types to be marked so they are never referenced from production logic.

### 5.4 No Property-Level api_name Discipline

Palantir's `PropertyApiName` applies the same naming contract to individual properties. dharma_swarm's `PropertyDef` has only `name: str` — no api_name, no immutability semantics, no pattern validation. The align-gate (PR #408) also never validates properties. Half the schema is ungoverned.

### 5.5 No Link Type api_name Discipline

Palantir's link type design requires distinct, meaningful names for each side ("directReports" not "employee2"). dharma_swarm's `LinkDef` has `name` and `inverse_name` — structurally correct — but no naming conventions are enforced or documented for the link api_name. The existing links in `_METABOLIC_LINKS` and `_DOMAIN_LINKS` use snake_case (e.g., `has_gate_decision`, `engagement_reinvestment`) inconsistently with the PascalCase `api_name` convention for types.

### 5.6 Action Types Are Not First-Class Ontology Citizens

Palantir treats `ActionType` as a top-level OMS resource with its own api_name, versioning, and action log. dharma_swarm's `ActionDef` is a child attribute of an `ObjectType` — it has no independent api_name, no version, and is not registered separately in the `OntologyRegistry`. Actions are not discoverable as first-class objects; they are subordinate to their parent type.

### 5.7 No Status Cascade Enforcement

If a dharma_swarm `ObjectType` is marked `ACTIVE`, nothing prevents its `LinkDef` targets from remaining `EXPERIMENTAL`. Palantir enforces cascade consistency at the OMS layer with named conflict errors. This absence means the status field is decorative, not operational.

### 5.8 No Stable RID Equivalent

Palantir's system has `ri.ontology.main.object-type.<UUID>` as the immutable machine identifier separate from the human api_name. dharma_swarm's only unique identifier for a type is its `name` string (PascalCase). If a type is renamed (even in EXPERIMENTAL status), all references break with no redirect mechanism. The register_type uniqueness guard protects against accidental duplicate registration but does not provide stable cross-system addressing.

---

## 6. The Morning Trio's Findings Re-Tested

PR #410 identified five top findings. After this deeper read, here is the status of each:

### Finding 1: api_name pattern is an inverted anti-pattern — STANDING, SHARPER

The `.v<N>` suffix was already dropped by Devin before PR #409 merged. The community guide finding still stands, but the operational urgency has decreased: the *suffix* is gone. The *prefix* (`dharma.<domain>.`) remains and is not Palantir-canonical. The deeper issue — namespace-in-api_name vs. Groups — is still unaddressed and was not named in the trio. The finding should be sharpened: not just "drop the `.v<N>`" but "reconsider whether `dharma.<domain>.` belongs in api_name at all."

### Finding 2: Status enum is wrong shape (3 states, not 5) — STANDING, PARTIALLY VALIDATED

Confirmed: the five-state model is documented in both Palantir's API reference and the community guide. The two missing states (`DEPRECATED`, `EXAMPLE`) are operationally significant. However, the trio report identified the gap at the structural level; what it did not surface is the *cascade enforcement* requirement — not just adding states but enforcing cascade semantics across linked types. That is an additional gap the trio missed.

### Finding 3: In-memory uniqueness guard is unsafe under concurrency — STANDING

Confirmed by code read. The `register_type` guard in `OntologyRegistry._types` is a dict in memory, reset on every process instantiation. Two agents in separate processes can both register the same api_name. The CI gate (ALIGN-001 through ALIGN-007) runs only on merges. Runtime protection is zero. This finding is fully standing and has not been addressed in any subsequent PR.

### Finding 4: KARMA is a conceptual mismatch — STANDING, REFINED

The multi-agent-convergence report correctly identifies that KARMA's Schema Alignment Agent classifies ABox facts against a *fixed* schema, not a mutating one. After reading the full corpus: dharma_swarm's problem is not ABox enrichment (adding instances) but TBox evolution (adding/modifying type definitions). These are different problems. The KARMA citation in PR #408's PR body is marketing-level framing, not a technical model. The finding stands. However, I would add a nuance: PR #408's actual mechanism (AST snapshot diff across PRs) is closer to Apollo Federation's composition gate than to KARMA. The KARMA name is cargo-cult labeling of a simpler, reasonable git-diff-based gate.

### Finding 5: CALM+AGM auto-convergence formally impossible — STANDING, CONTEXTUALLY BOUNDED

The formal impossibility result (CALM theorem + AGM non-commutativity) is correct and uncontested. However, I would add a reality check: the current system operates with 2-5 agents and PR-based serial merges (John merges one PR at a time). The formal impossibility of *automatic* convergence under concurrency is real, but the actual concurrency level is low enough that human-in-the-loop merge ordering is viable as a short-term scaffold. The finding should be framed as "this matters at scale; right now it manifests as: which PR does John merge first changes the registry state." The deeper implication is that the swarm needs a documented merge ordering policy before auto-convergence becomes critical.

---

## 7. Concepts the 21 MISS Entirely

Without naming them (per charter), here are the domain nouns obviously absent from the registry given the code reality:

**The pheromone-mark substrate.** The stigmergy system is one of the most-referenced subsystems in the entire codebase — 8+ core files in `dharma_swarm/`, a dedicated API router, a GraphQL schema entry. `ontology_adapters.py` already defines an `ObjectType` for this concept and wires it. Yet it is absent from the 21 "domain types." This is the most glaring omission: a concept with full code grounding, its own adapter, and doctrine-level importance is not in the registry.

**The zero-copy snapshot / perception signal.** `ontology_adapters.py` defines a second type for real-time environmental signals — external news, repo events, research discoveries that the system notices and categorizes. This too is absent from the 21. It is an active subsystem with tests.

**The constitutional self-model / organism state.** The system extensively models its own identity — TCS, GPR, BSI, RM regime — in `ontology_adapters.py` as a third standalone type. These are the system's self-measurements, written periodically by the identity-tracking subsystem. Not in the 21.

**The verified claim.** The system processes claims made about it, against it, and by it. `ontology_adapters.py` defines a type for this. Not in the 21.

**The agent skill / capability advertisement.** `dharma_swarm/a2a/agent_card.py` defines `AgentSkill` and `AgentCard` as rich structured objects that agents broadcast. These are the system's A2A coordination primitives — yet neither appears in the registry. The A2A protocol has no ontology representation.

**The memory/consolidation unit.** The system has `agent_memory.py`, `agent_memory_manager.py`, `memory_kernel/`, `memory_palace.py`, and `consolidation.py`. Memory is central to agent continuity and self-evolution. Nothing in the 21 represents a memory record or consolidation artifact.

**The telos gate evaluation unit.** Telos gates are the constitutional primitive — they are what separates dharma_swarm from any generic multi-agent system. The individual gate (SATYA, AHIMSA, CONSENT, etc.) and its per-evaluation result have no ontology representation beyond `GateDecisionRecord` (which records aggregate gate outcomes on proposals). The gate itself — its definition, its pass/fail threshold, its historical accuracy — is not modeled.

**The spend/cost record.** Every LLM call has a token cost. The system tracks this in `auto_grade/` but it has no ontology representation. Revenue types are modeled; cost types are not. An economic system that tracks inflows but not outflows is half an economy.

---

## 8. Concepts in the 21 That Should Not Be There

### Paper

The academic publication lifecycle — drafting, review, submission, acceptance, rejection — has no implementation in the codebase. The system's research outputs are `KnowledgeArtifact` objects and `Experiment` records. The name `Paper` is semantically polluted by `ginko_paper_trade.py` ("paper trading" in the financial sense). Even if an academic paper type eventually belongs in this system, it does not belong in the registry now. It is a wish, not a noun this system speaks.

### RevenueOffer

The native model in `spine_models.py` is called `Offer`, not `RevenueOffer`. No code in the revenue pipeline references the ontology type. The type's existence in the registry creates a false impression of ontology coverage of the revenue funnel. The actual offer logic lives in a parallel native model. Having both `Offer` (native, active) and `RevenueOffer` (ontology type, orphan) is a split-brain problem waiting to cause confusion when someone tries to bridge them.

### Experiment (ontology type, in its current form)

The concept of an experiment belongs in this system — it is central. But three definitions of "Experiment" (`ontology.py:ObjectType`, `self_research.py:Experiment`, `amiros.py:Experiment`) with no bridging adapter is worse than one definition. The ontology type is not wrong; it is premature. It should be declared after one of the two native classes is chosen as canonical and an adapter is written. In the meantime, the registry `Experiment` type creates a ghost: it passes all tests, appears in the GraphQL schema, and silently has zero instances in production.

---

## 9. Open Questions for the Swarm

1. **What is the system's native vocabulary before Palantir?** The Palantir ontology framework was chosen as a reference architecture, not a constraint. Before asking "does this match Palantir?" we should ask: "what are the nouns this system actually emits and consumes in its own operating life?" The four types in `ontology_adapters.py` that *were not chosen* for the 21 (StigmergyMark, ZeitgeistSignal, IdentitySnapshot, CorpusClaim) are arguably more dharma-native than `Paper`. Why did those not make the cut?

2. **Who chose the 21, and by what selection criterion?** The PR #409 body describes "21-type backfill" but gives no selection rationale. Were these the types that Devin considered "load-bearing," or were they the types the Palantir upgrade prompt suggested, or were they all types Devin could think of in one session? The provenance of the list is opaque. Pass 1c (aliveness archaeologist) may have context from git log archaeology.

3. **Should the metabolic loop (ActionProposal → ... → Contribution) be its own domain, or is it the ontological backbone that all other types hang on?** Currently the loop spans `governance` and `execution` and `economic` domains. These six types are not a "domain" — they are a *spine*. A naming/grouping decision here has architectural consequences.

4. **Is `KnowledgeArtifact` doing too much work?** It currently encompasses: file, note, finding, measurement, citation, prompt, result, visualization, code, model_output. That is 10 subtypes under one name. In a Palantir ontology, these would be separate object types with shared properties via Interfaces. Is `KnowledgeArtifact` a real object or a union type masquerading as an object?

5. **What is the right relationship between the native model in `revenue/spine_models.py` and the ontology types in the revenue cluster?** The spine_models.py file predates the ontology types and has its own lifecycle (`TargetStatus` enum with 10 states). The ontology `RevenueTarget` has 4 status states. These two models are not synchronized. Is the ontology type the canonical definition, or is it a projection of the native model? The answer changes what "load-bearing" means for the revenue cluster.

6. **Is the A2A layer ontology-invisible by design, or by oversight?** `AgentCard`, `AgentSkill`, A2A messages, remote node registrations — these are the system's inter-agent communication substrate. None appear in the 21 types. If the vision is "everything flows through the ontology" (as the `ontology.py` module docstring states: "Everything flows through the ontology"), then A2A objects should be in the registry. Is this a deliberate choice to keep A2A as infrastructure (below the ontology), or an oversight?

7. **What is the canonical unit of agent memory for this system?** The memory subsystem is substantial (`agent_memory.py`, `memory_kernel/`, `memory_palace.py`, `consolidation.py`). Yet "memory" as a typed ontology object does not exist in the 21. If the system is to reason about its own knowledge state over time, a memory-record type seems necessary. What is blocking it?

8. **Should `VentureCell` be at the same level as `ActionProposal`?** VentureCell is a project container that has its own agents, budgets, and KPIs — it sounds like a management abstraction, not a metabolic primitive. ActionProposal is a low-level event record. Both are in the registry as peer `ObjectType`s with no hierarchy. Does the ontology need an explicit notion of "management container" vs. "event record" vs. "entity identity"? Palantir solves this with Interfaces — shared shapes across object types with different granularity.

---

## 10. Felt-Sense Summary

Devin's 21 are **a useful but uneven draft**, not a seed crystal. The metabolic loop cluster (ActionProposal through Contribution) is genuinely excellent: six tightly wired types that model the system's operational heartbeat, grounded in `telic_seam.py`, consumed across multiple subsystems, and rooted in doctrine (the fourfold action warrant). These six types feel inevitable — any serious ontology of this system would have them. Similarly, AgentIdentity, WitnessLog, KnowledgeArtifact, and VentureCell are well-earned. The revenue cluster is partially wired but has a naming mismatch problem (Offer vs. RevenueOffer) and the RevenueEngagement type is thin. Thirteen of the 21 pull their weight.

The deeper problem is not the three cargo-cult types (Paper, RevenueOffer, Experiment-as-orphan) — it is what the 21 *systematically omit*. The pheromone mark, the environmental signal, the agent capability advertisement, the memory record: these are dharma-native concepts with substantial code grounding that did not make the cut, presumably because they were not on Devin's mental model when writing the backfill. The 21 look like they were generated from a top-level inspection of the codebase's domain structure (research, agent, knowledge, task, evolution, governance, execution, economic, revenue) rather than from asking "what objects does this system actually produce, emit, consume, and reason about?" The former gives a taxonomy; the latter gives a vocabulary. This system needs the latter. Pass 2 must surface the tension between what the 21 *declare* and what the codebase *lives*.

---

*Evidence base: `dharma_swarm/ontology.py` (PR #409 branch), `dharma_swarm/ontology_adapters.py`, `dharma_swarm/telic_seam.py`, `dharma_swarm/revenue/spine_models.py`, `dharma_swarm/trace_attractor/readers.py`, `dharma_swarm/evolution.py`, `dharma_swarm/self_research.py`, `dharma_swarm/amiros.py`, `dharma_swarm/custodians.py`, `docs/archive/PALANTIR_ONTOLOGY_GAP_ANALYSIS.md`, PR #408 body, PR #409 body, PR #410 body + four reports (`palantir-api-discipline.md`, `multi-agent-convergence.md`, `migration-semantic-layer.md`, `EXECUTIVE-BRIEF.md`), PR #413 + `2026-06-01-1200-oms-hardening-pr409.md`, [Palantir community design guide](https://community.palantir.com/t/ontology-and-pipeline-design-principles/5481), grep provenance scans across full repo.*
