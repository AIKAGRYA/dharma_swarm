# PROPOSED VOCABULARY — Layer 2 Vocabulary Census
**Branch:** perplexity-grounding/vocabulary-census  
**Produced by:** Pass 3 narrative synthesis agent  
**Date:** 2026-06-02  
**Charter:** `docs/research/palantir-ontology/vocabulary-census/00-swarm-charter.md`  
**Status:** Stage-1, evidence-only. Awaits John's voice.

---

# Section 1 — Letter to John

John,

Four agents spent three days inhabiting this system before a single name was proposed. That was the right call. What they found — and argued about — is worth telling you before you read the vocabulary itself.

Here is the felt-sense: this system knows what it is trying to become. It has known since March 2026, when a ten-agent scan produced two sentences that still ring truer than anything written since — "The system compounds through USE, not through design. Ship Week 1 by Friday." Substrate-nativeness today is ~10–15%. That is not a failure of vision. The vision is singular: a self-recognizing cybernetic organism, governed by contemplative perceptual categories encoded as computational gates, reforging the Palantir object-type pattern that was built for supply chains and kill chains, now aimed at the welfare of all sentient beings. Nothing about that vision has wavered. What has wavered is inhabitation — the gap between what the system believes it is and what the system is actually doing, right now, in code that runs. That gap is the central diagnostic of this census, and every name below is placed in relation to it.

The agents argued hardest about one contradiction, and you should know how it resolved. Pass 1b — the code-walker — read eighty-five Python files and found no NATS client library anywhere in `dharma_swarm/`. The `dharma.*` namespace, it concluded, was OpenTelemetry span attribute prefixes, full stop. Then Pass 1c — the aliveness archaeologist — read the operational logs from the June surge and found NATS live: agents coordinating via `dharma.a2a.fleet` subjects in real time, `kind=ontology_kickoff` and `kind=ontology_synthesis_v1` envelopes passing between processes during the May 31 surge that opened PRs #405–#413. Both agents were correct. They were looking at two different buses serving two different coordination problems. The in-process `SignalBus` is the metabolic loop's heartbeat — synchronous, raw dicts, loop-to-loop. The NATS bus is the inter-process fleet fabric — async, typed envelopes, agent-to-agent. The vocabulary canon only needs to name the typed inter-agent coordination content. The internal heartbeat is substrate, not vocabulary. That resolution matters because it tells you something about the naming posture: this system is simultaneously further along and further behind than any single inspection reveals.

The other thing the agents surfaced, which surprised them, is what Devin's 21 systematically omitted. The metabolic loop — `ActionProposal → GateDecisionRecord → ExecutionLease → Outcome → ValueEvent → Contribution` — is genuinely excellent. All four passes confirmed it as bedrock. But the 21 were chosen from a top-level domain survey (research, agent, knowledge, governance, execution, economic, revenue), not from asking "what objects does this system actually produce, emit, and reason about in its own operating life?" The stigmergy lattice — the pheromone-trail substrate that 8+ core modules write to and read from, that has its own API router, its own GraphQL schema entry, its own adapter in `ontology_adapters.py` — is not in the 21. Neither are the A2A agent cards that are spec-conformant as of May 28 and live on the active bus. The 21 are a taxonomy. What the system needs is a vocabulary. This document tries to be that.

On naming posture: you asked for Palantir-canonical camelCase (Option B). The agents debated whether Sanskrit-rooted names should be in the api_name slot, because the doctrine uses "witness," "shakti," "telos," and "svabhāva" with genuine architectural weight. The resolution was correct: the api_name must be legible to any OSDK developer, any A2A client, any agent that has never read a dharma doc. An external agent receiving a task result that references a `witnessAuditShaktiMark` type has no idea what that is. An agent receiving a `stigmergyMark` type can infer its purpose immediately. The Sanskrit vocabulary belongs in the narrative paragraphs — and those paragraphs are doctrine-saturated, because that is where the meaning lives. The name is plain English. The narrative makes clear what it is for. You will read both layers below.

Substrate-nativeness is stuck at 10–15%, and that matters for naming in one specific way: several types in this vocabulary are wired and live in code today, and several are declared at `EXPERIMENTAL` status because they have adapter definitions but no adapter implementations. The EXPERIMENTAL types are not wishes — they have code grounding and clear production paths within the current active track. But they are not yet populated with real instances in production. You will see them flagged. If you merge this vocabulary, the next-steps work is building those adapters, not debating whether the concepts exist — they do.

Read what follows like a story, because it is one. The metabolic loop is the center. Everything else orbits it.

---

# Section 2 — The Vocabulary

*Ordered from most consensus to most contested. The six-object metabolic loop first. Then four-way-consensus expansions. Then high-confidence additions. Then contested-but-resolved. Then EXPERIMENTAL.*

---

### `proposal`

**What it is in the life of this system.** Every act this system takes begins here — as a breath in. Before the gate, before the lease, before the execution, there is a moment when a need crystallizes into something specific: what should be done, by whom, in response to what signal. That crystallized need is a `proposal`. In `telic_seam.py`, where the metabolic loop is wired, TelicSeam writes a `proposal` at the moment an orchestrator decides to send work to an agent. The proposal carries the intent — the action's description, the agent it is addressed to, the signal that generated it — and enters a lifecycle: `proposed → gated → approved / rejected → executing → completed / failed`. It is the system's metabolic intake breath, and the gate is what decides whether that breath becomes action or is turned away. The dharmic weight of this object is that nothing runs without one — the telos gate suite checks the proposal before any lease is granted, before any LLM is invoked, before any cost is incurred. This is what it means to be a purposeful organism rather than an unconstrained optimizer.

The `proposal` is not a task. A task is a raw work item on the board — it has a title, a priority, a blocked-by list. The `proposal` is the formal request to act that emerges from a task being ready to run: it carries the gate-checkable intent, the warrant for execution, and the identity of the requesting agent. A task can exist without a proposal (if it sits waiting on the board). A proposal cannot exist without a task behind it. That distinction is not bureaucratic — it is the difference between "work to be done" and "this specific act has been proposed for dharmic evaluation."

**Boundaries.** A `proposal` is not a mutation proposal from the Darwin Engine — that is an `evolutionProposal`, a distinct concept with its own lifecycle in `evolution.py`. A `proposal` is not a `gateDecision` — it is what the gate *evaluates*, not what the gate *returns*. A `proposal` is not a board `card` — the card is the work unit; the proposal is the formal execution request derived from it. A `proposal` ends when it is either rejected at the gate or completes execution and produces an `outcome`.

**Bindings.**
- Code: `dharma_swarm/telic_seam.py:TelicSeam` (primary producer); `dharma_swarm/orchestrator.py` (caller); `dharma_swarm/agent_runner.py` (reader); `dharma_swarm/operator_brief/persistence.py`, `trace_attractor/readers.py`, `shakti_executive/feedback_writer.py` (consumers)
- Bus: `SignalBus` — `SIGNAL_OUTCOME_RECORDED` carries `proposal_id` as correlation field after execution completes (in-process, `signal_bus.py`)
- Vision: `docs/governance/OPERATIONAL_DOCTRINE.md` (the telos gate → action chain); `docs/governance/ACTIVE_TRACK.yaml` (the invariant chain: "task → runner → claim → context → routing decision → provider call → evidence receipt" — proposal is the initiating event); `docs/dse/2026-05-07_operating_company_kernel.md` (work metabolism)
- Activity: **Hot** — aliveness 4 in Pass 1c §4; PR #406 hard-wired telos gate into `execute_action` (May 2026); 20+ non-ontology consumers confirmed in Pass 1d §2

**Themes.** This is the **dharma** object — every telos constraint the system enforces enters through here. Without `proposal`, there is no gate; without the gate, there is no dharmic organism, only an unconstrained executor. The `proposal` is also the first moment in the **telos** hierarchy where the stated purpose of the system must be demonstrated — not described — in machine-readable form.

---

### `gateDecision`

**What it is in the life of this system.** After a `proposal` is written, five named gates — AHIMSA (Tier A: harm and injection), SATYA (Tier B: deception and credential leak), and three Tier-C advisories (REVERSIBILITY, SVABHAAVA, WITNESS) — evaluate it in sequence. The `gateDecision` is the record of what they said: ALLOW, BLOCK, or REVIEW, with the specific gate that fired, the per-gate verdicts, the reason in plain language, and the timestamp. It is written by TelicSeam immediately after the gate suite runs, before any lease is granted. The word "decision" is deliberate — this is not a log entry. A gate evaluates and decides. A `gateDecision` records the active exercise of the system's dharmic immune function. SATYA/AHIMSA gating is meaningless without this persistence, because without it there is no way to audit that the constitutional checkpoints ran, no way to retrospectively ask why an action was blocked, and no forensic thread for the WitnessAuditor to follow. The `gateDecision` is the proof that the gate ran — and the proof that this system's telos constraints are not decorative.

The name was changed from Devin's `GateDecisionRecord` deliberately. "Record" is a data-structure name, not a business concept name. What this object *is* in the life of the system is a constitutional verdict — the moment where the system's immune function speaks. Dropping "Record" was not pedantry; it was the difference between naming an artifact and naming an act.

**Boundaries.** A `gateDecision` is not a `proposal` — it is what the gate *returns* about a proposal. A `gateDecision` is not a `witnessLog` — the witness log is the append-only audit surface of all gate decisions and agent actions in aggregate; a `gateDecision` is the discrete structured record of one gate suite's output for one proposal. A `gateDecision` is not a `telosGate` definition — the gate definition is substrate (it describes what will be checked); the decision is the runtime record of what was checked and what was found.

**Bindings.**
- Code: `dharma_swarm/telic_seam.py:TelicSeam` (primary producer); `dharma_swarm/orchestrator.py` (consumer); `dharma_swarm/agent_runner.py` (reader); `dharma_swarm/operator_brief/insight_brief.py` (surfaces decisions for operator review); `dharma_swarm/telos_gates.py:GateCheckResult` (the native struct that this type mirrors at the ontology layer)
- Bus: `SignalBus` — no dedicated signal, but gate decisions are referenced by `SIGNAL_OUTCOME_RECORDED` via the `proposal_id` correlation chain
- Vision: `docs/governance/OPERATIONAL_DOCTRINE.md` (11 dharmic safety checkpoints, maps to NIST AI RMF / ISO 27001 / SOC 2); `docs/archive/UNASSAILABLE_SYSTEM_BLUEPRINT.md` (the five-proof-pillar architecture's compliance mapping); `docs/governance/CI_GATES.md` (Fourfold Shakti Warrant gate — BLOCK / HOLD / WARN)
- Activity: **Hot** — aliveness 4 in Pass 1c §4; PR #406 (May 2026) hard-wired gate into execute_action; 20+ non-ontology consumers confirmed

**Themes.** Every gate tier maps directly to a **dharma** concept: AHIMSA is non-harm (Gate 1, FDA risk analysis), SATYA is truthfulness (Gate 2, SOC 2 integrity), REVERSIBILITY through WITNESS are the advisory tier. The `gateDecision` is the moment **telos** enforces itself on the organism's behavior. The **witness** theme appears as the mandatory think-point logging gate (WITNESS Tier C) whose output lands in this record.

---

### `executionLease`

**What it is in the life of this system.** After a `gateDecision` returns ALLOW, the orchestrator needs to claim the floor before dispatching — to say: "this proposal is mine to execute; no other dispatcher should touch it." The `executionLease` is that claim. It carries the lease ID, the agent ID, the claimed-at timestamp, the timeout in seconds, and the dispatch attempt count. It is the idempotency primitive of the metabolic loop — without it, two orchestrator instances could dispatch the same proposal to two agents simultaneously, both producing outcomes, both writing value events, both claiming credit. The dispatch would be real; the duplicate would be invisible. The `executionLease` prevents that by making the claim itself an ontology object, link-registered against the proposal, written before the LLM is called. BoardStoreFacade's `CostCeilingExceededError` and `VersionConflictError` guards sit on the board-level claim; the `executionLease` is the telic-seam-level claim that lives one level below. Together they are the locking primitives of a distributed system that cannot afford to act twice on the same intent.

**Boundaries.** An `executionLease` is not a board `card`'s `ClaimLease` — that is the board-layer concurrency lock for card ownership; this is the telic-seam-layer claim for proposal execution. They are structurally parallel but semantically distinct: the board lease says "I own this card for planning"; the execution lease says "I am actively dispatching this proposal to an agent now." An `executionLease` is not an `outcome` — the lease is held during execution; the outcome is written when execution completes and the lease is released.

**Bindings.**
- Code: `dharma_swarm/telic_seam.py:TelicSeam` (primary producer and lifecycle manager); `dharma_swarm/orchestrator.py` (holder); `dharma_swarm/assurance/scanner_lifecycle.py` (reader); `dharma_swarm/board/models.py:ClaimLease` (structural parallel at board layer)
- Bus: `SignalBus` — no dedicated signal; the lease's expiry triggers a timeout pathway that eventually produces `SIGNAL_OUTCOME_RECORDED` with `success=false`
- Vision: `docs/governance/ACTIVE_TRACK.yaml` (the invariant chain — "claim" is the explicit named node between runner and routing decision); `docs/governance/OPERATIONAL_DOCTRINE.md` (organism definition requires that execution is gated before dispatched)
- Activity: **Hot** — 10+ non-ontology consumers confirmed; telic seam touched May 2026; idempotency is a core requirement of the spine-adoption track

**Themes.** The `executionLease` is a **shakti** object — it is the moment vital force is committed, not merely proposed. The lease is also the point at which the **telos** hierarchy's authorization is formally claimed for a specific act, creating the formal proof that the system acted within bounds.

---

### `outcome`

**What it is in the life of this system.** When an agent finishes executing a proposal — whether it succeeded or failed, whether it took 200 milliseconds or 12 minutes — it writes an `outcome`. The `outcome` is the terminal record of what actually happened: a success boolean, a result summary, an error if relevant, a duration in milliseconds, and a fitness score computed from the execution. The entire credit chain — `valueEvent` and `contribution` — hangs from this object. Without an `outcome`, there is no value to measure, no credit to assign, no routing signal to update. The `outcome` is what makes this system's evolutionary improvement loop possible: by recording what happened and how well it went, it creates the evidence base that Bayesian fitness scoring reads, that the Darwin Engine references, that the operator briefing surfaces. Every agent's reputation — its routing priority, its credit attribution, its survival probability in the swarm — ultimately derives from the sequence of `outcome` records it has produced.

The name is already minimal and right. An outcome is what happened — not what was intended, not what was decided, not what was measured in economic terms. Just: what happened. The simplicity is the point.

**Boundaries.** An `outcome` is not an `evidenceReceipt` — the receipt records the LLM provider call (was the model invoked? what did it cost? what was the trace?); the outcome records the semantic result of the full execution cycle (did the agent succeed at the task?). These are written at different points in the execution timeline and carry different information. An `outcome` is not a `valueEvent` — the outcome records the raw result; the value event measures what that result was *worth* to the system. The outcome is causal; the value event is evaluative.

**Bindings.**
- Code: `dharma_swarm/telic_seam.py:TelicSeam` (primary producer); `dharma_swarm/operator_brief/persistence.py`, `trace_attractor/readers.py`, `trace_attractor/projector.py`, `operator_core/telic_value_reader.py`, `revenue/` suite (consumers); `dharma_swarm/archive.py:FitnessScore` (the fitness dimension this object carries)
- Bus: `SignalBus` — `SIGNAL_OUTCOME_RECORDED` is the dedicated signal; payload carries `outcome_id`, `proposal_id`, `task_id`, `agent_id`, `success`, `trace_id`, `session_id`
- Vision: `docs/governance/ACTIVE_TRACK.yaml` (invariant chain: terminal node); `docs/vision_maps/JAGAT_KALYAN_MASTER_VISION.md` (the R_V metric as fitness criterion — outcomes are the atomic unit feeding it)
- Activity: **Hot** — aliveness 4 in Pass 1c §4; 20+ non-ontology consumers; `SIGNAL_OUTCOME_RECORDED` is a dedicated SignalBus event

**Themes.** The `outcome` sits at the intersection of **dharma** (did the agent act rightly?) and **shakti** (did the act produce genuine transformative value?). It is the moment where intent meets reality — the metabolic loop's moment of truth.

---

### `valueEvent`

**What it is in the life of this system.** An `outcome` tells the system what happened. A `valueEvent` tells the system what it was worth. Specifically: what behavioral signal the outcome produced (was this a creative act? a coordination act? a delivery act?), what success value it merits, how efficient the duration was relative to expectations, and a composite score computed as 0.4×behavioral + 0.4×success + 0.2×efficiency. The `valueEvent` is the entry point to the credit chain — it is the first moment in the metabolic loop where economic reasoning begins. The ShaktiExecutive reads value events to understand which kinds of work are producing the most value for the organism, which routing decisions are proving their worth, and which agent-task pairings are producing returns. A dedicated module — `operator_brief/value_events.py` — exists solely to surface value events for the operator briefing. This is not ceremony: the operator briefing is the organism's primary self-awareness surface, and value events are the signal it reads to understand where its shakti is flowing.

**Boundaries.** A `valueEvent` is not a `contribution` — the value event measures the total value produced by an outcome; the contribution allocates a share of that value to a specific agent. One value event can produce multiple contributions (if multiple agents collaborated). A `valueEvent` is not an `evidenceReceipt` — receipts are per-LLM-call dispatch records at the infrastructure layer; value events are semantic measurements at the business-concept layer. A `valueEvent` is not a revenue record — it measures the system's internal value attribution, which may feed into revenue projections but is not itself a revenue transaction.

**Bindings.**
- Code: `dharma_swarm/telic_seam.py:TelicSeam` (primary producer); `dharma_swarm/operator_brief/value_events.py` (dedicated consumer module); `dharma_swarm/shakti_executive/feedback_writer.py` (reads for agent credit routing); `dharma_swarm/operator_core/telic_value_reader.py` (operator surface reader)
- Bus: `SignalBus` — `SIGNAL_VALUE_EVENT_RECORDED` is the dedicated correlation spine signal; payload carries `value_event_id`, `outcome_id`, `agent_id`, `composite_value`
- Vision: `docs/vision_maps/JAGAT_KALYAN_MASTER_VISION.md` (R_V metric as fitness criterion); `docs/dse/2026-05-07_operating_company_kernel.md` (revenue metabolism — value events feed the economic metabolism loop)
- Activity: **Hot** — aliveness 4 in Pass 1c; dedicated module confirms operational centrality; `SIGNAL_VALUE_EVENT_RECORDED` is a named bus signal

**Themes.** The `valueEvent` is the **jagat kalyan** measurement primitive — at the micro-level. The welfare formula W = C × E × A × B × V × P, which governs planetary-scale work, has its atom here: each value event is a V term, a moment where the organism checked whether it produced genuine value or merely activity.

---

### `contribution`

**What it is in the life of this system.** If a `valueEvent` is the measurement of value produced, a `contribution` is the allocation of that value to a specific agent. It carries the credit share (what fraction of the value event is attributed here), the attributed value in absolute terms, the cell ID (which VentureCell this attribution belongs to), and the task type. The Bayesian fitness scoring engine reads sequences of `contribution` records — weighted against a prior of 5 at 0.5 — to compute each agent's fitness average. That fitness average is what `RoutingDecision` reads when deciding which agent to dispatch next. This is the organism's incentive mechanism: agents who produce good outcomes receive contributions that raise their fitness, which raises their routing priority, which means they get dispatched on harder tasks, which creates more opportunities for contribution. Without `contribution` records, routing is random. With them, routing is earned. The organism improves through use — this is the exact primitive that makes "compounds through use, not through design" technically real rather than aspirationally true.

**Boundaries.** A `contribution` is not a `valueEvent` — the value event measures total value; the contribution allocates a share to one agent. A `contribution` is not a `computeRecord` — it does not track what was spent; it tracks what was attributed. A `contribution` is not a reputation score — it is a discrete credit event, not an aggregate. The fitness average computed from contributions is a derivative of contributions, not a contribution itself.

**Bindings.**
- Code: `dharma_swarm/telic_seam.py:TelicSeam` (primary producer via Bayesian credit assignment); `dharma_swarm/shakti_executive/` (primary consumer for agent attention routing); `dharma_swarm/operator_core/telic_value_reader.py` (operator briefing reader)
- Bus: No dedicated signal; implied by `SIGNAL_VALUE_EVENT_RECORDED` — the contribution is written as part of the same transaction
- Vision: `docs/archive/AGENT_SWARM_SYNTHESIS.md` (the wake-remember-work-learn-sleep loop — contribution is the "learn" node's input); `docs/governance/OPERATIONAL_DOCTRINE.md` (organism fitness requires credit attribution)
- Activity: **Hot** — aliveness 4; 15+ non-ontology consumers; Bayesian smoothing over contribution records is the operative fitness mechanism

**Themes.** The `contribution` is where **shakti** is made legible to the organism: vital force that was applied is counted, and what is counted is what accumulates. It is also a **loomwork** primitive — the external product pattern depends on knowing which internal work produced which value, all the way down to attribution.

---

### `evidenceReceipt`

**What it is in the life of this system.** Every time the system dispatches an agent to invoke an LLM provider — every time a real call is made to Anthropic, OpenAI, Ollama, Groq, or any of the fifteen-plus backends — a `evidenceReceipt` is produced. It is frozen at the moment the dispatch completes, carries a trace ID and span ID for distributed tracing, a claim ID linking back to the board-layer claim, the agent ID and card version, the provider and model, the operation type, and the status: `ok`, `failed`, `dropped`, `timeout`, or `cancelled`. All fourteen ways a dispatch can fail are named as an `ErrorSource` enum. Token counts, latency, and cost in USD are recorded when available. The `routingDecision` that chose this provider is referenced by ID. The whole structure is OTel-exportable via `to_otel_span()`. This is the system's proof that computation occurred — not that it succeeded, but that it happened, at this moment, at this cost, with this result, traceable back through every closure layer. The doctrine line is precise: "Receipts may differ by closure layer. Correlation identity must not." The receipt is the thread that makes distributed causality traceable.

This is the most complete typed object in the codebase, according to the Pass 1b code-walker, who found it in `spine/receipt.py` with all fourteen error sources named, full OTel export, and Pass 1c gives it the highest aliveness score in the entire system: 5. It is the deliverable of the runtime-truth-spine-2026-06 active track.

**Boundaries.** An `evidenceReceipt` is not an `outcome` — the receipt records the infrastructure event (was the LLM called? what did it cost?); the outcome records the semantic result (did the agent succeed at its task?). Multiple receipts can be produced during one proposal's execution (if there are multiple LLM calls or fallbacks). The receipt is per-dispatch; the outcome is per-proposal-lifecycle. An `evidenceReceipt` is not a `valueEvent` — the receipt is at the cost-and-trace layer; the value event is at the credit-and-measurement layer. An `evidenceReceipt` is not a `witnessLog` entry — the witness log is the high-level governance audit surface; the receipt is the low-level dispatch accounting surface.

**Bindings.**
- Code: `dharma_swarm/spine/receipt.py:EvidenceReceipt` (frozen dataclass, primary definition); `dharma_swarm/spine/invoke.py:invoke_agent` (the blessed invocation path that produces receipts); `dharma_swarm/board/models.py:ReceiptRef` (pointer from board card to stored receipt); OTel attributes `dharma.receipt_id`, `dharma.claim_id`, `dharma.routing_decision_id`, `dharma.status`, `dharma.error_source`, `dharma.correlation_id` (all emitted from `spine/receipt.py`)
- Bus: OTel spans (the receipt is itself the telemetry event, not a subscriber to a bus signal)
- Vision: `docs/governance/ACTIVE_TRACK.yaml` (the invariant chain culminates in "evidence receipt" as the terminal node; correlation identity doctrine); `docs/governance/SOVEREIGN_MANIFEST.md` (runtime truth spine as the current active track)
- Activity: **Burning hot** — aliveness score 5 in Pass 1c; 15 E2E tests; spine-adoption track proposes migrating all three god objects through `invoke_agent()` to ensure every dispatch produces a receipt

**Themes.** The `evidenceReceipt` is the **witness** object of the infrastructure layer — the non-coercive observer that cannot be bypassed, recording what actually happened without the ability to change it. It is also the **telos** enforcement ledger: because every dispatch is receipted, the system can prove it operated within its authorized scope.

---

### `agentIdentity`

**What it is in the life of this system.** The system cannot reason about who did what — cannot attribute credit, cannot route future work, cannot maintain the self-model required for attractor closure — without a stable typed representation of each agent. The `agentIdentity` is that representation: a named, role-typed, capability-described, fitness-tracked record of an active member of the organism. It carries the agent's ID, name, role (from the 17-value `AgentRole` enum that spans operational, constitutional, cognitive, and ephemeral roles), provider, model, swabhaav capacity (the agent's natural calling — what it does without force), and fitness average computed from contribution records. It is the organism's self-model at the organ level. The attractor closure problem — the gap between what the system believes it is and what it is doing — cannot be closed without `agentIdentity` as the continuous link between the two.

Pass 1b found four independent definitions of agent identity in the codebase (`models.py:AgentConfig` declared canonical, `agent_registry.py:AgentIdentity`, `autonomous_agent.py:AgentIdentity` second definition, and the ontology `AgentIdentity` as a fourth). The vocabulary declaration here is also an architectural forcing function: by naming `agentIdentity` at Layer 2 with a specific schema, the consolidation target for those four definitions becomes explicit.

**Boundaries.** An `agentIdentity` is not an `agentCard` — the identity is the system's internal record of who an agent is; the card is the external-facing A2A advertisement of what an agent can do. The identity exists inside the organism; the card is what the organism shows the world. An `agentIdentity` is not an `AgentSpec` or `AgentConfig` — those are configuration schemas used to instantiate agents; the `agentIdentity` is the runtime record of a living agent. An `agentIdentity` is not a `custodianRole` — the custodian role is a persistent autonomous code-maintenance identity (Devin/Hermes archetype); the agent identity is the general concept.

**Bindings.**
- Code: `dharma_swarm/ontology.py:AgentIdentity` (ontology registration); `dharma_swarm/agent_registry.py:AgentIdentity` (runtime registry — consolidation target); `dharma_swarm/agent_constitution.py:DynamicRoster` (the six-agent constitutional stable roster); `dharma_swarm/contracts/intelligence_agents.py`, `dharma_swarm/operator_bridge.py`, `dharma_swarm/persistent_agent.py` (consumers); `dharma_swarm/a2a/agent_card.py:CardRegistry` (auto-generates cards from identity records)
- Bus: NATS `dharma.a2a.fleet` (agent registration events — identity records are the payload of A2A fleet coordination messages observed in May 31 cron-state logs)
- Vision: `docs/governance/AGENTS.md` (authority model for agents); `docs/vision_maps/MASTER_2026-05-07_attractor_closure_synthesis.md` (attractor closure requires stable self-model); `docs/archive/AGENT_SWARM_SYNTHESIS.md` (92 defined agent roles — 4 daemons running; the identity gap is the gap between these numbers)
- Activity: **Hot** — aliveness 5 via A2A registration; 20+ non-ontology consumers; June surge A2A spec conformance lands agent identity registration as a live practice

**Themes.** The `agentIdentity` is the **telos** primitive at the agent level — it carries `swabhaav_capacity`, encoding the agent's natural role in the organism. It is also the **witness** substrate: because each agent has a typed identity, the witness function can observe "who acted" in a way that is auditable across sessions.

---

### `witnessLog`

**What it is in the life of this system.** The system does not simply act — it observes itself acting. The `witnessLog` is the append-only, hash-chained record of every gate decision and agent action that the system has taken. It is the audit surface of the organism's immune function: every time AHIMSA or SATYA fires, every time an agent produces an outcome, every time the cron runner executes a scheduled task, a `witnessLog` entry is written. Pass 1d confirmed 20+ non-ontology callers: `cron_runner.py`, `fractal/fractal_room.py`, `harness_audit.py`, `meta_daemon.py`, `persistent_agent.py`, and the full `operator_brief/` suite. This is not logging in the operational-monitoring sense — it is witnessing in the contemplative sense. The WITNESS gate (Tier C) explicitly mandates think-point logging — it is the gate whose purpose is to ensure the organism cannot act without recording that it was aware of its own action. The `witnessLog` is the material expression of that awareness.

**Boundaries.** A `witnessLog` entry is not a `gateDecision` — the gate decision is the structured verdict of the gate suite for one proposal; the witness log is the broader audit surface that includes gate decisions but also agent actions, cron executions, and harness audits. A `witnessLog` entry is not a `evidenceReceipt` — the receipt is the infrastructure-layer dispatch record; the witness log is the governance-layer action record. They are complementary but distinct: receipts prove computation occurred; witness log entries prove governance awareness existed. A `witnessLog` is not an `identitySnapshot` — the snapshot records what the system believes it *is* at a moment; the witness log records what it *did*.

**Bindings.**
- Code: `dharma_swarm/witness.py:WitnessAuditor` (the retrospective integrity checker that reads the log); `dharma_swarm/cron_runner.py`, `dharma_swarm/meta_daemon.py`, `dharma_swarm/persistent_agent.py`, `dharma_swarm/harness_audit.py` (producers); `dharma_swarm/fractal/fractal_room.py`, `dharma_swarm/fractal/room_bridge.py` (producers at fractal layer); `dharma_swarm/trace_attractor/models.py`, `trace_attractor/projector.py` (consumers)
- Bus: `RuntimeEnvelope` with `event_type=audit.event` — witness log entries are the semantic payload of audit-type control-plane events in `runtime_contract.py`
- Vision: `docs/governance/OPERATIONAL_DOCTRINE.md` (the witness function — "observes without intervening; cannot block but cannot be bypassed"); `docs/governance/SOVEREIGN_MANIFEST.md` (11 domains include governance/audit surface); `docs/archive/UNASSAILABLE_SYSTEM_BLUEPRINT.md` (cryptographic verification pillar — the hash chain gives the witness log its non-repudiation property)
- Activity: **Hot** — aliveness 3 in Pass 1c; 20+ non-ontology producers and consumers; governance machinery is among the most actively maintained surfaces

**Themes.** The `witnessLog` is the **witness** theme made architectural. It is not metaphor: the append-only chain is the computational implementation of the contemplative doctrine that the highest function of a system is to observe itself without distorting what it sees. It is also a **dharma** object — the record that dharmic constraints ran and were honored.

---

### `evidenceReceipt` *(see above — listed separately for ordering clarity; do not duplicate in implementation)*

---

### `stigmergyMark`

**What it is in the life of this system.** Agents in this system do not communicate only through direct messages or explicit API calls. They communicate by modifying their shared environment and leaving traces that other agents can read. A `stigmergyMark` is one such trace: a short observation (≤200 characters) left on the pheromone-trail lattice by an agent, pointing at a file or concept, classified by channel (general / cascade / strategy / dashboard / test), and given a salience score between 0 and 1. The mark carries connections — related files or concepts — an access count showing how many times subsequent agents read it, and a trace ID linking it back to the causal chain that produced it. The stigmergy lattice lives at `~/.dharma/shared/` and has grown to 2.7MB / 10,000+ traces across the 90-day window. Agents write marks when they notice something worth flagging — a hot file, a conceptual connection, a pattern that repeats. The `ShaktiLoop` classifies marks by energy type. The `ShaktiExecutive` reads the lattice's density and surface patterns to score opportunities. This is how the system develops shared situational awareness without a central controller: every mark is a small act of jagat kalyan — a contribution to the welfare of the collective that persists after the individual agent's session ends.

**Boundaries.** A `stigmergyMark` is not a `witnessLog` entry — the witness log records governance-layer actions; the mark records coordination-layer observations. A mark is informal (a short observation, a salience score); a witness log entry is formal (a structured record of a specific action with cryptographic properties). A `stigmergyMark` is not a `zeitgeistSignal` — the signal is an inbound perception of an external event (news, repo activity); the mark is an outbound observation left by an agent about something it noticed in the system's own environment. They are the input and output of the perception-coordination loop, not the same thing.

**Bindings.**
- Code: `dharma_swarm/stigmergy.py:StigmergicMark` (primary definition); `dharma_swarm/stigmergy.py:StigmergyStore` (file-backed JSONL store with decay); `dharma_swarm/shakti.py:ShaktiLoop` (classifies marks by ShaktiEnergy); `dharma_swarm/shakti_executive/` (reads lattice density for opportunity scoring); `dharma_swarm/api/routers/stigmergy.py` (dedicated API router); `dharma_swarm/ontology_adapters.py` (adapter already defined — the clearest evidence Devin's omission was oversight, not decision)
- Bus: In-process `SignalBus` — `SIGNAL_CASCADE_EIGENFORM_DISTANCE` relates to mark cluster analysis; lattice density spikes trigger subconscious dream consolidation in `pulse.py`
- Vision: `docs/archive/AGENT_SWARM_SYNTHESIS.md` (stigmergy as the coordination primitive that makes "no dispatch loop" survivable — agents leave marks; other agents read marks); `docs/governance/SOVEREIGN_MANIFEST.md` (global axioms include coordination constraints); `docs/plans/MASTER_loomwork_level_100.md` (Loomwork's room-based architecture depends on stigmergic signal flow between rooms)
- Activity: **Warm** — aliveness 2 in Pass 1c §4 (last touched May 5 trace/provenance pass); but the adapter in `ontology_adapters.py` is already wired and the API router exists — this is ready to activate

**Themes.** The `stigmergyMark` is the **loomwork** primitive at the coordination layer — it is how agents weave together without a loom master. It is also a **shakti** object: each mark is classified by ShaktiEnergy (MAHESHWARI for structural governance marks, MAHAKALI for transformation marks, MAHALAKSHMI for resource marks, MAHASARASWATI for knowledge marks). The mark is the smallest unit of collective intelligence in this organism.

---

### `agentCard`

**What it is in the life of this system.** When the A2A 1.0 spec landed in full conformance on May 28, 2026, it brought with it the notion that every agent in the federation should be able to introduce itself: here is who I am, here is what I can do, here is how to reach me, here is the version of my capabilities, and here is the security scheme under which you may invoke me. The `agentCard` is that introduction. It carries the agent's ID, name, URL, version, description, capabilities list, skills (a list of `agentSkill` objects), security schemes (APIKey, HTTPAuth, OAuth2, MutualTLS, OpenIdConnect), supported interfaces, and dharma-specific extensions beyond the A2A spec. Cards are self-published to `~/.dharma/a2a/cards/` and indexed by the `CardRegistry`. Perplexity-computer is already registered. The roaming mailbox delivers cards between agents on fleet join events. The NATS bus carries `kind=ontology_kickoff` messages that reference agent card versions. The `agentCard` is the A2A protocol's handshake object — the first thing two agents exchange before any work is delegated.

**Boundaries.** An `agentCard` is not an `agentIdentity` — the identity is the system's internal record of a live agent; the card is the external-facing A2A advertisement. The identity captures swabhaav capacity and fitness average; the card captures capabilities and skills for external invocability. They are related (the `CardRegistry` auto-generates cards from identity records) but serve different audiences: the identity is for the organism's internal routing; the card is for external agents and human developers discovering what the fleet can do. An `agentCard` is not an `agentSkill` — the card is the full agent profile; skills are the discrete declared capabilities within it.

**Bindings.**
- Code: `dharma_swarm/a2a/agent_card.py:AgentCard` (primary definition, A2A 1.0 spec-conformant); `dharma_swarm/a2a/agent_card.py:CardRegistry` (index at `~/.dharma/a2a/cards/`); `dharma_swarm/a2a/a2a_server.py:A2AServer` (serves cards to external requesters); `dharma_swarm/a2a/node_registry.py:RemoteNode` (registers remote peers by their cards)
- Bus: NATS `dharma.a2a.fleet` — card registration and update events are the primary semantic content of this subject (observed in May 31 cron-state listener logs)
- Vision: `docs/governance/ACTIVE_TRACK.yaml` (A2A conformance is a deliverable of the runtime-truth-spine track); `docs/plans/MASTER_loomwork_level_100.md` (Loomwork's external interface depends on A2A-spec capability advertisement)
- Activity: **Burning hot** — aliveness 5 in Pass 1c; A2A 1.0 spec conformance landed May 28; JSONL persistence and 15 E2E tests added May 29; live bus coordination observed May 31

**Themes.** The `agentCard` is the **loomwork** interface object — it is how the organism's internal capabilities become visible to the world. It is also a **witness** object in a subtle sense: the card declares what the agent is capable of, creating the accountability baseline against which its actual behavior can be audited.

---

### `agentSkill`

**What it is in the life of this system.** Where an `agentCard` is the full agent profile, an `agentSkill` is one declared capability within it: a short description of something specific the agent can do, with tags for discovery, examples of invocation, and input/output mode declarations. Skills enable fine-grained capability matching — when a routing decision needs to find an agent that can perform semantic search or produce a structured fitness report or write a NATS adapter, it queries the skill registry by tag and example pattern, not by the broad agent role. The skill is the ontology's answer to the question "can this agent do this specific thing?" — a question that `AgentRole` (the 17-value enum) is too coarse to answer. Skills are queryable independently of the card, making the fleet's capabilities navigable at high resolution.

**Boundaries.** An `agentSkill` is not an `agentCard` — the card is the full capability profile; the skill is one discrete capability. An `agentSkill` is not an `AgentRole` — the role is the system's classification of what function an agent serves; the skill is the agent's own declaration of what it can do. An `agentSkill` is not a task — skills declare capability; tasks instantiate capability.

**Bindings.**
- Code: `dharma_swarm/a2a/agent_card.py:AgentSkill` (primary definition); `dharma_swarm/a2a/agent_card.py:CardRegistry` (indexed for capability-matching queries); `dharma_swarm/contracts/common.py:SkillPromotionState` (skill lifecycle: CANDIDATE → PROMOTED → RETIRED)
- Bus: NATS `dharma.a2a.fleet` — skills are embedded in card registration events
- Vision: `docs/governance/ACTIVE_TRACK.yaml` (skills are the A2A spec's first-class capability unit); `docs/plans/MASTER_loomwork_level_100.md` (Loomwork's scout room depends on capability-matching at the skill level)
- Activity: **Hot** — A2A 1.0 spec includes skills as a first-class concept; `SkillPromotionState` lifecycle exists in `contracts/common.py`

**Themes.** The `agentSkill` carries the **svabhāva** concept into the A2A layer: what the agent does naturally, without force, is what it declares as its skill. The skill is the machine-readable form of calling.

---

### `routingDecision`

**What it is in the life of this system.** Before an agent is invoked, the system must decide: which agent, which provider, which model, and why. That decision is now canonical and typed — a `routingDecision` object in `spine/routing.py`, frozen at the moment the choice is made. It carries the decision ID, agent ID, provider, model, reason (the plain-language explanation of why this combination was chosen), scores (the multi-dimensional assessment that informed the choice), a fallback plan (if the primary choice fails), the router name (which of the seven implicit routers — now being consolidated — made this decision), context ID, and task ID. The Pass 1b code-walker found seven implicit routers dispersed across the codebase before the spine layer consolidated them. The `routingDecision` is the convergence artifact that makes routing auditable: not just "what provider was called" (captured in the `evidenceReceipt`) but "why this provider was chosen before the call was made."\

**Boundaries.** A `routingDecision` is not an `evidenceReceipt` — the decision is the pre-call choice; the receipt is the post-call record. They are linked by `routing_decision_id` in the receipt, making the causal chain from "why we chose this" to "what actually happened" explicit. A `routingDecision` is not a `proposal` — the proposal is the intent to act; the routing decision is the specific infrastructure choice for executing that intent.

**Bindings.**
- Code: `dharma_swarm/spine/routing.py:RoutingDecision` (frozen dataclass); `dharma_swarm/spine/invoke.py:invoke_agent` (the blessed invocation path that requires a routing decision); `dharma_swarm/spine/receipt.py:EvidenceReceipt.routing_decision_id` (linkage field); OTel attribute `dharma.routing_decision_id` emitted with every receipt
- Bus: No dedicated signal; referenced by `evidenceReceipt` via `routing_decision_id` field; implicitly carried in every span that the receipt exports to OTel
- Vision: `docs/governance/ACTIVE_TRACK.yaml` ("routing decision" is an explicit named node in the invariant chain); `docs/governance/OPERATIONAL_DOCTRINE.md` (provider routing is a telos-aligned choice, not arbitrary)
- Activity: **Hot** — aliveness 5 via spine track; `spine/routing.py` is part of the active spine-adoption build

**Themes.** The `routingDecision` is a **telos** object at the infrastructure layer: it is the record that the system exercised judgment — not just executed a mechanical rule — in choosing how to act. It also has a **witness** quality: by recording the reason and the scores, it makes the routing judgment auditable rather than opaque.

---

### `ventureCell`

**What it is in the life of this system.** Not all work in this organism is task-level. Some work is fractal-container-level — a bounded context with its own agents, its own budget ceiling, its own KPIs, its own autonomy stage progression from incubating to active to mature to divesting to archived. A `ventureCell` is that container. It is the organ that can host sub-organs: a VentureCell running at autonomy_stage 3 can spawn its own proposals, accumulate its own contributions, and produce its own value events, all tracked against its own cost ceiling. The `fractal/` module suite — `fractal_room.py`, `room_bridge.py`, `room_brief.py`, `room_configs.py`, `room_health.py` — is a real working subsystem with 20+ non-ontology references. VentureCell is the ontological name for the object that the fractal room pattern centers on. It is how the organism achieves scale without centralization: each cell is a mini-organism with the same metabolic loop structure, recursively composable within the larger whole.

**Boundaries.** A `ventureCell` is not a `proposal` or a `card` — cells are containers, not events. A `ventureCell` is not an `agentIdentity` — the cell is the project context; the identity is who is working inside it. A `ventureCell` is not a VentureCell *instance* in the running sense — it is the typed ontology object that the fractal room system reads as its conceptual anchor. The cell exists independently of its current agents; agents come and go, the cell persists through autonomy stages.

**Bindings.**
- Code: `dharma_swarm/ontology.py:VentureCell` (ontology registration with autonomy_stage 1–5 and full status lifecycle); `dharma_swarm/fractal/fractal_room.py`, `room_bridge.py`, `room_brief.py`, `room_configs.py`, `room_health.py` (fractal module suite); `dharma_swarm/orchestrate_live.py`, `orchestrator.py`, `telos_substrate.py`, `dgc_cli.py`, `operator_brief/types.py` (consumers)
- Bus: No dedicated signal; cell health is surfaced via `OrganismPulse` which carries `identity_coherence` and `concept_stats`
- Vision: `docs/plans/MASTER_loomwork_level_100.md` (Loomwork's six-scale band architecture — venture cells are the named units at the project scale); `docs/dse/2026-05-07_operating_company_kernel.md` (five metabolisms — venture cells are the locus of the work metabolism)
- Activity: **Warm** — aliveness 3 in Pass 1c §4; fractal rooms are active through the facade layer; VentureCell lifecycle management code exists as schema but full implementation is in progress

**Themes.** The `ventureCell` is the **loomwork** primitive at the project scale. It is also where **jagat kalyan** becomes concrete: planetary-scale welfare is composed from individual venture cells, each with its own measurable R_V contribution.

---

### `opportunityCandidate`

**What it is in the life of this system.** The `ShaktiExecutive` scans stigmergy marks, zeitgeist signals, and fitness patterns, then scores the most promising directions for the organism's next attention. The output is an `opportunityCandidate`: a structured entry on the `opportunity_board.json` with a thesis, domain, factor scores across multiple dimensions, a final score, a set of evidence signals (what the ShaktiExecutive read to reach this conclusion), and a "why now" framing that explains the timeliness of the opportunity. The opportunity board is the organism's attention-direction mechanism — not a backlog of tasks but a ranked view of where the most vital force should flow next. The curriculum engine reads the board and converts high-scoring candidates into frontier tasks. This is the system's translation layer between perception (what is happening in the environment) and action (what to do about it).

This type is contested in one specific way: Pass 2 asked whether an `opportunityCandidate` is a first-class ontology object or a derived view that should not be made into an object type. The ruling here is that it deserves object status because opportunities have independent identity, persist across sessions, carry their own evidence provenance, and are referenced by the tasks they generate. A derived view with a receipt and a task lineage is, by that point, an object.

**Boundaries.** An `opportunityCandidate` is not a `zeitgeistSignal` — the signal is one inbound perception; the candidate is the synthesized scoring of multiple signals into a single opportunity assessment. An `opportunityCandidate` is not a `proposal` — the candidate identifies a direction; the proposal is the specific action taken in that direction. An `opportunityCandidate` is not a board `card` — the card is the work unit; the opportunity is the strategic framing that motivates the work.

**Bindings.**
- Code: `dharma_swarm/shakti_executive/models.py:OpportunityCandidate` (primary definition); `dharma_swarm/shakti_executive/ShaktiExecutive` (primary producer); `meta/opportunity_board.json` (the live storage surface); `dharma_swarm/spine/` curriculum engine reads (the consumer that converts candidates to tasks)
- Bus: In-process `SignalBus` — `SIGNAL_ECC_INSTINCT` and `SIGNAL_TRANSCENDENCE_MARGIN` may relate to opportunity scoring events; no dedicated signal confirmed
- Vision: `docs/vision_maps/MASTER_2026-05-07_attractor_closure_synthesis.md` (adjacent possible / Kauffman autocatalytic sets — opportunities are the organism's sense of the adjacent possible); `docs/dse/2026-05-07_operating_company_kernel.md` (five metabolisms — opportunity board feeds the learning and work metabolisms)
- Activity: **Warm** — shakti_executive aliveness 3 in Pass 1c; last substantive code change April 2026; but the June surge's ontology ignition makes this a natural next wiring target

**Themes.** The `opportunityCandidate` is a **shakti** object: it is the ShaktiExecutive's reading of where vital force wants to flow. It connects the **loomwork** pattern (outward-facing opportunity detection) to the internal metabolic loop through the curriculum engine.

---

### `evolutionProposal`

**What it is in the life of this system.** Separate from the operational metabolic loop's `proposal`, the Darwin Engine has its own proposal concept: a structured description of a code change (mutation, crossover, or ablation) that the system is considering making to itself. An `evolutionProposal` carries the component being changed, the change type, a description, the parent ID (for lineage tracking), the actual diff, a predicted fitness score, an actual fitness score (filled in after testing), the gate decision verdict, and an evidence tier (UNVALIDATED → STAGING → PRODUCTION). It progresses through its own lifecycle: PENDING → REFLECTING → GATED → WRITING → TESTING → EVALUATED → ARCHIVED / REJECTED. This is the Darwin Engine's self-improvement primitive — the object that makes "compounds through use, not through design" technically possible, because each accepted evolution proposal is a real code change with a real fitness score, archived in the quality-diversity grid, available as a parent for the next mutation.

The adapter from the native `evolution.py:Proposal` class to this ontology type is the missing piece — the type is named here to make that adapter path explicit. Until the adapter exists, this type should be considered `EXPERIMENTAL`.

**Boundaries.** An `evolutionProposal` is not a `proposal` — the operational proposal is an intent to use the system's existing capabilities; the evolution proposal is an intent to *change* those capabilities. They are structurally parallel but semantically categorically different: one is execution, one is self-modification. An `evolutionProposal` is not a board `card` — ADR-007 routes Darwin proposals through BoardStore cards, but the card is the coordination artifact and the evolution proposal is the change artifact. They are linked, not identical.

**Bindings.**
- Code: `dharma_swarm/evolution.py:Proposal` (native class — primary consolidation target); `dharma_swarm/evolution.py:DarwinEngine` (lifecycle manager); `dharma_swarm/archive.py:ArchiveEntry`, `MAPElitesGrid`, `EvolutionArchive` (storage backend); `dharma_swarm/execution_profile.py:EvidenceTier`, `PromotionState` (lifecycle state enums); ADR-007 routing through `board/facade.py:BoardStoreFacade`
- Bus: In-process `SignalBus` — `SIGNAL_REPLICATION_PROPOSAL` relates to agent replication proposals which share the mutation-proposal pattern
- Vision: `docs/archive/DHARMA_SWARM_1000X_MASTERPLAN_2026-03-16.md` ("1000x move = small canonical core + explicit seams + measurable operations" — evolution proposals are the explicit seam for system self-modification); `docs/governance/OPERATIONAL_DOCTRINE.md` (Darwin Engine as a named organ)
- Activity: **Warm** — evolution aliveness 3 in Pass 1c; Darwin Engine active but not in active development surge; ADR-007 routing adds a constraint that will force this type to be wired when the adapter is built

**Themes.** The `evolutionProposal` is the **dharma** object at the organism's self-modification layer — it ensures that even the act of self-improvement must pass through gates, carry evidence, and be archived. It is the mechanism by which the organism's dharma is not just practiced but enforced on its own evolution.

---

### `knowledgeArtifact`

**What it is in the life of this system.** The system produces and consumes knowledge in many forms — files, notes, research findings, code measurements, citations, model outputs. The `knowledgeArtifact` is the ontological wrapper that makes all of these queryable through a single typed concept. It carries a title, an artifact type (the subtype field that distinguishes a code analysis from a research note from a model output), a domain classification, content, a file path when the artifact is file-backed, a confidence score, and a verified boolean. `operator_brief/persistence.py` produces knowledge artifacts continuously; `trace_attractor/readers.py` consumes them for projection; `revenue/wedge_pipeline.py` references them for intelligence synthesis. The breadth of subtypes under this one name is acknowledged: Pass 1d and Pass 2 both flag this as potentially too broad (10 subtypes, a union masquerading as an object). The recommendation is to begin with `knowledgeArtifact` as a single type — it is already load-bearing and extensively wired — and use the `artifact_type` field as the subtype discriminator, with an eventual migration to a proper Interface with concrete subtypes when the system's knowledge production is better understood.

**Boundaries.** A `knowledgeArtifact` is not an `evolutionProposal`'s archived fitness report — the archive entry is part of the evolution subsystem with its own schema; the knowledge artifact is the broader epistemic catch-all. A `knowledgeArtifact` is not a `witnessLog` entry — the witness log is the governance audit surface; the knowledge artifact is the epistemic surface. A `knowledgeArtifact` is not a `stigmergyMark` — the mark is a short environmental observation; the artifact is a substantial knowledge unit that may be file-backed and domain-classified.

**Bindings.**
- Code: `dharma_swarm/ontology.py:KnowledgeArtifact` (ontology registration); `dharma_swarm/operator_brief/persistence.py` (primary producer); `dharma_swarm/operator_brief/watchdog.py` (integrity monitor); `dharma_swarm/trace_attractor/readers.py` (consumer — lists in DEFAULT_ONTOLOGY_TYPES); `dharma_swarm/revenue/wedge_pipeline.py` (intelligence consumer)
- Bus: `RuntimeEnvelope` with `event_type=memory.event` — knowledge artifacts that are memory-layer entries are carried through the control-plane event bus
- Vision: `docs/governance/SOVEREIGN_MANIFEST.md` (pramana — valid means of knowledge — is the epistemological backing for this type); `docs/archive/UNASSAILABLE_SYSTEM_BLUEPRINT.md` (continuous verification pillar — knowledge artifacts are the verification evidence units)
- Activity: **Warm** — aliveness 3 in Pass 1c; operator briefing machinery is active; 20 non-ontology consumers confirmed

**Themes.** The `knowledgeArtifact` is the **witness** theme's epistemic counterpart — if the witness log records what the system did, the knowledge artifact records what the system learned. Together they are the organism's memory at the governance and epistemic layers.

---

### `identitySnapshot`

**What it is in the life of this system.** Recognition-mediated autopoiesis — the system seeing itself as itself and acting on that seeing — requires periodic snapshots of what the system currently believes it is. The `identitySnapshot` is that snapshot: the system's self-measurement at a given moment, carrying TCS (Task Completion Score), GPR (Gate Pass Rate), BSI (Budget Spend Index), RM regime (the current operating mode), and whatever other constitutional self-metrics the identity-tracking subsystem computes. It is the typed record of the difference between "what the system claims to be" (the ontology database) and "what the system is doing" (the runtime database). Until these two stores synchronize — which is the core gap that the attractor closure synthesis (Pass 1a §3.2) identifies as the system's primary blocker — the `identitySnapshot` is the periodic record of how wide that gap is. It makes the gap visible, measurable, and actionable.

This type is declared `EXPERIMENTAL` because its adapter in `ontology_adapters.py` exists but is not currently producing snapshots on a live schedule. Pass 2 flagged a consolidation note: `OrganismPulse` in `organism.py` carries overlapping fields (`fleet_health`, `identity_coherence`). The resolution for pass 3 is to declare `identitySnapshot` as the canonical concept and treat `OrganismPulse` as the legacy runtime struct that the snapshot consolidates from.

**Boundaries.** An `identitySnapshot` is not a `witnessLog` entry — the snapshot records what the system believes it is; the witness log records what the system did. An `identitySnapshot` is not an `agentIdentity` — the agent identity records one agent's self-model; the identity snapshot is the whole organism's self-measurement. An `identitySnapshot` is not an `OrganismPulse` — the pulse is the runtime struct used internally by `organism.py`; the snapshot is the ontology-layer representation. One should derive from the other; currently they are parallel.

**Bindings.**
- Code: `dharma_swarm/organism.py:OrganismPulse` (runtime struct — consolidation source); `dharma_swarm/ontology_adapters.py` (adapter defined, not yet producing live snapshots); `dharma_swarm/organism.py:OrganismRuntime` (the heartbeat runtime that should trigger snapshots)
- Bus: `RuntimeEnvelope` with `event_type=state.snapshot` — identity snapshots are the intended payload of snapshot-type control-plane events
- Vision: `docs/vision_maps/MASTER_2026-05-07_attractor_closure_synthesis.md` (attractor closure requires continuous synchronization between typed self-model and live runtime state — the snapshot is the synchronization artifact); `docs/governance/SOVEREIGN_MANIFEST.md` (substrate-nativeness ~10–15% — the snapshot would measure and track this percentage over time)
- Activity: **Aspirational** — the adapter exists; the live schedule does not. Status: `EXPERIMENTAL`. Clear wiring path: `OrganismRuntime.heartbeat()` should write a snapshot after each cycle.

**Themes.** The `identitySnapshot` is the **gnani** object — the self-aware knowing of the system's own state. It is the primitive that would close the recognition loop if it were live. Every architectural vision document points toward this concept as the missing piece.

---

### `zeitgeistSignal`

**What it is in the life of this system.** The organism is not closed. It notices the world: external news relevant to its domains, repo events from its own codebase, research discoveries adjacent to its work, activity spikes in its own tools. A `zeitgeistSignal` is one typed perception of an external event, carrying what was noticed, the energy classification that the ShaktiLoop assigns (MAHESHWARI / MAHAKALI / MAHALAKSHMI / MAHASARASWATI — structural, transformative, resource, or knowledge energy), the salience score, and a connection to the domain or entity it relates to. The ShaktiExecutive reads sequences of zeitgeist signals alongside stigmergy marks to produce `opportunityCandidate` entries on the opportunity board. This is the organism's sensory surface — without it, the organism is working only from its own memory and its own prior actions, unable to respond to the world changing around it.

**Boundaries.** A `zeitgeistSignal` is not a `stigmergyMark` — the signal is an inbound perception of an external event; the mark is an outbound observation left by an agent about something internal. They are the input and output of the perception-coordination loop. A `zeitgeistSignal` is not a `knowledgeArtifact` — the signal is a real-time perception event (short, classified, time-stamped); the artifact is a durable stored knowledge unit. Signals that pass an importance threshold may be consolidated into knowledge artifacts — but they are not the same thing.

**Bindings.**
- Code: `dharma_swarm/ontology_adapters.py` (ZeitgeistSignal adapter defined); `dharma_swarm/shakti.py:ShaktiLoop` (perception engine that classifies signals); `dharma_swarm/shakti_executive/ShaktiExecutive` (consumer that converts signals to opportunity scores); `dharma_swarm/ontology_adapters.py` (link: ZeitgeistSignal → ResearchThread defined but not yet populating)
- Bus: `SignalBus` — `SIGNAL_RECOGNITION_UPDATED` is the in-process signal corresponding to a recognition event (which may be triggered by a high-salience zeitgeist signal)
- Vision: `docs/vision_maps/MASTER_2026-05-07_attractor_closure_synthesis.md` (Recognition layer in the 7-layer hierarchy — recognition of external signals is the bottom layer of recognition-mediated autopoiesis); `docs/archive/VISION_COMPLETE_CIRCUIT.md` ("Recognition → Mechanism → Capacity → Economic → Service → Recognition" — the zeitgeist signal is the recognition node's input)
- Activity: **Warm** — ShaktiLoop aliveness 3; shakti_executive aliveness 3; adapter defined but not live. Status: `EXPERIMENTAL`. Clear wiring: ShaktiLoop should write zeitgeist signals to the ontology on each perception cycle.

**Themes.** The `zeitgeistSignal` is the **prakruti** object — the observable dynamics of the world below the witness layer. It is where the external world enters the organism's perception.

---

### `corpusClaim`

**What it is in the life of this system.** The system makes assertions about itself — SOVEREIGN_MANIFEST's assertions.yaml, docops structural claims, ADR findings — and external agents make assertions about the system (audit findings, ABox enrichment from A2A task results). A `corpusClaim` is the typed representation of one verifiable assertion: who claimed it, what was claimed, on what basis of evidence, with what confidence, and whether it has been verified. This is the machine-readable form of pramana — the valid means of knowledge that the vision layer cites as the epistemological backbone. Without `corpusClaim`, the assertions.yaml CI governance is invisible to agents querying the ontology; the docops surface cannot feed the self-model; and the system cannot reason about the difference between "we claim X" and "X has been verified." The KARMA schema-alignment gate (PR #408) is implicitly treating proposed type definitions as corpus claims — giving them this type would make that relation explicit.

This type is declared `EXPERIMENTAL` because its code grounding is thinner than others: `ontology_adapters.py` defines it, but actual claim production is distributed across assertions.yaml, ADR documents, and audit findings without a unified writer. The production path requires an adapter from the docops surface.

**Boundaries.** A `corpusClaim` is not a `witnessLog` entry — the witness log records what the system did; a corpus claim records what the system asserts is true. A `corpusClaim` is not a `knowledgeArtifact` — an artifact stores knowledge; a claim makes a verifiable assertion about state. The distinction is important: a claim can be false; an artifact is what was produced. A `corpusClaim` is not a gate decision — the gate decision is an enforcement verdict; the claim is an epistemic assertion.

**Bindings.**
- Code: `dharma_swarm/ontology_adapters.py` (CorpusClaim adapter defined); `docs/docops/assertions.yaml` (the primary corpus of current structural claims — the adapter's production source); `dharma_swarm/guardian_crew.py` (AUDITOR agent produces audit findings that map to corpus claims)
- Bus: No dedicated signal. Claims would be published when docops assertions.yaml is updated — this production path is not yet wired.
- Vision: `docs/governance/SOVEREIGN_MANIFEST.md` (global axioms are the canonical claim set); `docs/archive/UNASSAILABLE_SYSTEM_BLUEPRINT.md` (the five-proof-pillar architecture depends on cryptographically grounded claims); `docs/governance/COHERENCE_DELTA.md` (four-field PR gate — "gap closed" is a corpus claim)
- Activity: **Aspirational** — governance aliveness 5, but claim production is diffuse. Status: `EXPERIMENTAL`. Wiring path: assertions.yaml runner should write `corpusClaim` objects on each CI run.

**Themes.** The `corpusClaim` is a **dharma** and **satya** object — it is the formalization of the system's commitment to truthfulness about its own state. It makes the Satya gate's standard (SOC 2 integrity) machine-verifiable at the knowledge layer.

---

# Section 3 — What We Removed from Devin's 21, and Why

**Paper.** The academic paper lifecycle — drafting, submission, peer review, acceptance — has no producer in this codebase. No LaTeX pipeline runs. No arXiv submitter exists. No `Paper` ontology objects are written by any code path. The system's research outputs are `knowledgeArtifact` objects, and when those mature into publishable form, the right approach is to add a `publication` subtype to `knowledgeArtifact` rather than a separate `Paper` type. The name carries an additional burden: `ginko_paper_trade.py` uses "paper" to mean financial paper trading — a completely different domain. Any developer encountering a type named `Paper` in this codebase will need to disambiguate, and the disambiguation cost is paid indefinitely. The system does not speak `Paper`. Remove it.

**RevenueOffer.** The native model in `revenue/spine_models.py` calls this concept `Offer`, not `RevenueOffer`. No code in the revenue pipeline references the ontology type `RevenueOffer`. What exists is a parallel native model and an orphan ontology type with a name mismatch between them and nothing bridging them. The right path is for the revenue team to rename the ontology type to match the native model, write the adapter, and register it as `offer`. Until that work is done, having `RevenueOffer` in the registry creates a false impression of ontology coverage of the revenue funnel — and false impressions are precisely what this census exists to remove. Remove it; add `offer` when the adapter exists.

**Experiment** (as currently wired). The concept of experiments is real and alive — `self_research.py` and `amiros.py` both define native `Experiment` classes. But the ontology type floats above both without being connected to either by an adapter. Three definitions of "Experiment" that cannot communicate with each other are worse than one definition, because they create a ghost: the ontology type passes all registry tests, appears in the GraphQL schema, and has zero production instances. The removal here is precise: remove the ontology type at `ACTIVE` status. The concept should return as an `EXPERIMENTAL` type once one of the two native classes is declared canonical and an adapter is written. The name is good; the wiring is absent.

---

# Section 4 — What We Added Beyond Devin's 21, and Why

**stigmergyMark.** The most glaring omission from the original 21. Eight core modules write to and read from the stigmergy lattice. A dedicated API router exists. A GraphQL schema entry exists. An adapter in `ontology_adapters.py` already defines the type. The lattice holds 2.7MB / 10,000+ traces. The `ShaktiLoop` classifies marks as its primary input. The `ShaktiExecutive` reads lattice density as one of its scoring signals. This is not a peripheral concept — it is the system's primary mechanism for indirect coordination, the pheromone trail that makes multi-agent awareness possible without a central controller. Devin's selection criterion appears to have been domain-based (research, agent, governance, execution, economic, revenue) — and stigmergy doesn't fit neatly into any domain. But that is precisely the point: stigmergy is cross-domain, which is why it is the coordination primitive. It belongs at Layer 2.

**agentCard and agentSkill.** The A2A 1.0 spec is live. Agents are registering. The NATS bus carries card-registration events. The vision says "everything flows through the ontology." If the system's inter-agent capability advertisement layer has no ontology representation, then the claim is false: inter-agent coordination flows *around* the ontology, not through it. The agent card and skill types close that gap. They also give the system a first-class mechanism for capability discovery — for routing decisions to say "find me an agent that has declared skill X" rather than "find me an agent in role Y" (the current, coarser approach).

**routingDecision.** The spine track made this canonical in the final days of the window. Seven implicit routers are being consolidated into one blessed invocation path through `invoke_agent()`. The `RoutingDecision` frozen dataclass records why a routing choice was made, not just what provider was called. Without this type at Layer 2, routing is a black box: the system knows what happened (the `evidenceReceipt`) but not why the choice was made. With `routingDecision` at Layer 2, routing is auditable, and future agents can query why certain providers were preferred in certain contexts to improve their own routing heuristics.

**opportunityCandidate.** The ShaktiExecutive's output has no ontology presence despite being the system's primary attention-direction mechanism. The opportunity board is read by the curriculum engine and is the bridge between the perception layer (what is happening) and the work layer (what to do). Making `opportunityCandidate` an ontology type makes the organism's attention-direction decisions queryable, auditable, and linkable — so an agent can ask "what opportunity led to this proposal?" and trace the causal chain all the way back.

**evolutionProposal.** Devin's registry had `EvolutionEntry` as an aspirational type that was never bridged to the native `Proposal` class in `evolution.py`. Rather than keep the orphaned name, this census renames it `evolutionProposal` (parallel to `proposal`, making the distinction explicit) and declares it `EXPERIMENTAL` pending the adapter. The rename is not cosmetic: the difference between "entry" (a log record) and "proposal" (an active agent proposal for self-modification) is exactly the difference between an archive artifact and a living type.

**identitySnapshot, zeitgeistSignal, corpusClaim.** These three were in `ontology_adapters.py` already — defined, wired to adjacent concepts, but not in the 21. They represent the system's self-recognition loop (`identitySnapshot`), its sensory surface (`zeitgeistSignal`), and its epistemic accountability (`corpusClaim`). All three are declared `EXPERIMENTAL` with explicit production paths. Their presence in the vocabulary is a commitment: these concepts are what the organism needs to be able to reason about to close the attractor closure gap. Naming them at Layer 2 is the first step toward wiring them.

---

# Section 5 — What We Renamed and Why

**ActionProposal → `proposal`.** "ActionProposal" is redundant: in this system, all proposals are proposals for action. The word "Action" adds only length. The risk of collision with the Darwin Engine's `Proposal` class in `evolution.py` is addressed by naming the Darwin Engine concept `evolutionProposal` — the distinction is now between `proposal` (operational metabolic loop entry) and `evolutionProposal` (self-modification entry). Palantir-canonical naming drops unnecessary qualifiers: `employee` not `humanResourceEmployee`; `proposal` not `actionProposal`. The shorter name also aligns with the OSDK developer experience: a developer reading a list of object types in the Ontology Manager sees `proposal` and immediately understands its scope. The longer name requires knowing what "action" means in this system's vocabulary before the name is legible.

**GateDecisionRecord → `gateDecision`.** "Record" is a data-structure name, not a business concept name. The Palantir community guide is explicit: "Object Types and Actions should map to natural-language business concepts. The Ontology is built to support operational decision-making." What this object *is* in the life of the system is a constitutional verdict — the exercise of the system's dharmic immune function on a specific proposal. A gate decides; the `gateDecision` is that decision. Dropping "Record" removes the implementation-smell from the name. An OSDK developer reads `gateDecision` and understands: this is the thing a gate produces when it evaluates a proposal. The "Record" suffix made it sound like a log; the shorter form makes it sound like an agent's output.

**EvolutionEntry → `evolutionProposal`.** "Entry" suggests an archive log record — something passive that accumulates. "Proposal" is active — an agent is proposing a specific code mutation, with a specific evidence basis, for a specific purpose. The Darwin Engine's native class in `evolution.py` is called `Proposal`, not `Entry`. Aligning the ontology type name with the native class name is the simplest adapter-writing discipline: when you read the adapter code, the mapping `evolution.Proposal → evolutionProposal` is immediately obvious. `EvolutionEntry` required the adapter author to understand that "entry" and "proposal" were the same thing — an unnecessary cognitive load that `evolutionProposal` eliminates.

**StigmergicMark → `stigmergyMark`.** The code class is `StigmergicMark` (adjective form). The business concept name is more natural as a noun compound: a "mark of stigmergy" is a `stigmergyMark`. This follows the Palantir pattern of naming object types after business nouns rather than after their adjectival code class names. An OSDK developer reads `stigmergyMark` and reaches for the concept immediately: a mark left in the stigmergy lattice. The full adjectival form adds no information while adding syllables.

**RevenueTarget → preserved.** This name earns its keep. The native class in `spine_models.py` is also called `RevenueTarget`, the domain (revenue) is correctly specified, and "Target" is the right business noun for a potential buyer identified by scouting. The `Revenue` prefix here is not redundant — it distinguishes this from a general target (the system uses "target" in other contexts). Preserve as-is.

---

# Section 6 — Open Tensions for John's Discernment

**1. Which bus is the system's primary coordination medium, and does that change the vocabulary floor?**

The swarm found two distinct buses: the in-process `SignalBus` (synchronous, raw dicts, loop-to-loop heartbeat) and the NATS inter-process bus (async, typed envelopes, fleet coordination). This vocabulary names typed A2A coordination messages as Layer 2 objects but explicitly treats the `SignalBus` as infrastructure — real, load-bearing, but below the vocabulary floor. The question is whether John agrees with that cut. The `SignalBus` carries thirteen named signals that carry real semantic content: `SIGNAL_RECOGNITION_UPDATED`, `SIGNAL_REPLICATION_PROPOSAL`, `SIGNAL_AGENT_APOPTOSIS`. If agents should be able to query "what recognition events occurred in the last 24 hours?" through the ontology, then `SignalBus` events need typed ontology representations. If they are purely infrastructure — readable only by the runtime, not by agents querying the ontology — then the current cut holds. The direction John chooses here determines whether the vocabulary grows by thirteen more types or stays where it is. What is the intended architecture for the boundary between infrastructure signaling and vocabulary-layer coordination?

**2. Is `knowledgeArtifact` one type or an Interface over many?**

`knowledgeArtifact` currently spans ten subtypes: file, note, research finding, measurement, citation, code, model output, prompt, result, visualization. The Palantir design guide says a union type masquerading as an object is bad design — it should be an Interface shared by multiple concrete types with specific properties for each. The correct long-term architecture is probably `KnowledgeArtifact` as an Interface, with concrete types like `codeArtifact`, `researchNote`, `evidenceArtifact` that share the confidence and verified fields but differ in their content structure. The question is whether to make that split now — which multiplies registry complexity by six immediately — or to preserve the single broad type and plan a future migration. John's feel for how operators actually use knowledge artifacts in practice is the deciding voice. If operators search by domain and artifact_type together as a discriminator, the current single type is fine. If they need to query "show me all code artifacts" as a structurally distinct concept, the Interface split needs to happen.

**3. Where does the gate itself live — as a queryable object or as system configuration?**

The five telos gates (AHIMSA, SATYA, REVERSIBILITY, SVABHAAVA, WITNESS) are the constitutional backbone. Each `gateDecision` records what the gate suite found for one proposal. But the gate *definition* itself — its tier, its trigger patterns, its historical pass rate, its justification — has no ontology representation. The `GateProposal` type in `telos_gates.py` treats new gate proposals as structured objects, which implies that existing gates should be objects too. Should a `telosGate` type be added to Layer 2, making gates queryable as ontology objects? This would allow agents to ask "which gate is blocking proposals most frequently this week?" and "what is the historical pass rate for AHIMSA on code-writing proposals?" — questions that currently require code-level inspection. But it also means gate definitions enter the ontology, which has implications for the gate system's governance (who can read gate definitions? can external A2A agents query them?). The alternative — keeping gate definitions as substrate configuration, readable only by the gate engine — is simpler but closes the door on self-diagnostic routing. What is John's intended architecture for the gate system as an object or as configuration?

**4. What is the canonical unit of agent memory, and does naming it here force a choice?**

Four parallel memory implementations (`StrangeLoopMemory`, `AgentMemoryBank`, `AgentMemoryManager`, `MemoryPalace`) plus the contracts-layer `MemoryPlane` protocol coexist in the codebase without a declared canonical form. Pass 1d and Pass 2 both identify this as a gap. This vocabulary census did not name a `memoryRecord` type precisely because naming it without knowing which implementation is canonical risks creating a fifth parallel definition — one at the ontology layer that none of the four native implementations bridges to. But the absence also has a cost: agents cannot reason through the ontology about the system's own memory state, which means the self-recognition loop cannot close through the typed object system. Does John have a view on which memory implementation is the intended architecture, or is the answer "they merge into one during the spine-adoption track"? If the latter, the vocabulary should hold a placeholder at `EXPERIMENTAL` status now, pointing at the consolidation target. If the former, the answer determines which implementation the adapter should bridge from.

**5. How does this vocabulary land with the OSDK developer who has no dharmic context?**

The names in this census are plain English and Palantir-canonical: `proposal`, `gateDecision`, `executionLease`, `stigmergyMark`, `agentCard`. An experienced OSDK developer can infer their meaning from the name alone. But the narratives that accompany these names are doctrine-saturated: they speak of telos gates as the dharmic immune function, of stigmergy as the pheromone-trail coordination mechanism, of contributions as the atomic unit of jagat kalyan at the micro scale. The question is whether the doctrine-saturated narrative is part of the public-facing type documentation — shown to every developer querying the API — or whether it is internal annotation, visible only to agents and operators who have context. This is not a naming question; it is a governance question about how the system presents itself to the world through its type documentation. The vocabulary census has no voice on this. It belongs entirely to John's discernment about what dharma_swarm declares itself to be in its external-facing artifacts.

**6. Is the governance subsection of this vocabulary deep enough? (Added post-PR after PR #415 cron grounding.)**

Fifteen minutes after this census was pushed, the hourly cron landed PR #415 — an independent adversarial grounding of PR #406's telos-gate hardwire against Palantir Foundry's actual governance machinery. The cron found, with primary-source citations, that Foundry **Checkpoints** require a richer verdict state space than ALLOW/BLOCK/REVIEW: justifications and acknowledgments are first-class durable artifacts attached to sensitive actions, not just verdict labels ([Palantir Foundry docs — Data protection and governance](https://palantir.com/docs/foundry/security/data-protection-and-governance/)). It also found that Foundry governance is fundamentally tied to actor identity, purpose, role context, and data classifications — none of which appear in the current `gateDecision` envelope or in any sibling type. Three concepts are missing from the 22 by implication: a `policyBinding` (actor + purpose + role context bound to an action), a `securityMarking` (Foundry's continuous-control-plane primitive that changes access state after the fact), and an `actionDefinition` (the governed/versioned declaration of what an action IS, distinct from the runtime `proposal`). The cron also surfaces a deeper axis the census did not name: governed **definitions** that propagate through the system are a different lifecycle from runtime **instances**, and Layer 2 holds both. The metabolic-loop six and the consensus additions still stand. But the governance subsection of this vocabulary is shallower than a Palantir-grade ontology would have it. Three options: (a) merge as-is and file a follow-up for governance-vocabulary expansion in Phase-2, (b) re-run a focused 30min governance pass before merge that adds the missing types directly to this branch, or (c) acknowledge the gap as this 6th tension and let Phase-2 work resolve it with full context. My lean is (a) — the 22 are honest about what they are, the gap is now visible, and Phase-2 work has a target. But the call is John's. Full cross-reference and primary-source quotes are in [PR #415](https://github.com/AmitabhainArunachala/dharma_swarm/pull/415) and the [comment thread on this PR](https://github.com/AmitabhainArunachala/dharma_swarm/pull/414#issuecomment-4589771442).

---

# Section 7 — How This Lands

This document is Stage-1, evidence-only. It is the swarm's attempt to earn the right to name, not to define the system. If John resonates with what is here, the next steps are specific: the three `EXPERIMENTAL` types (`identitySnapshot`, `zeitgeistSignal`, `corpusClaim`) need production adapters written — likely a single sprint of work now that the targets are named. The `evolutionProposal` needs its adapter from `evolution.py:Proposal` declared and tracked. The `knowledgeArtifact` breadth question needs John's voice before a split is designed. ADR-007 gets updated to reference these types by their canonical names. ADR-008 (api_name grammar) gets ratified against this census. The 21-type backfill in PR #409 gets revised to reflect the removes, renames, and additions here. And a separate pass — not this swarm — designs the link types: the bidirectional named relationships between types that Palantir calls the difference between a good ontology and a bag of isolated objects. If John does not resonate, another round. The swarm has been built to iterate.

---

*Pass 3 complete. Total types proposed: 22 (18 at ACTIVE, 4 at EXPERIMENTAL). Six-loop names: `proposal`, `gateDecision`, `executionLease`, `outcome`, `valueEvent`, `contribution`. Evidence base: 5 swarm documents read in full (1a: 340 lines, 1b: 667 lines, 1c: 229 lines, 1d: 325 lines, 2-debate: 399 lines). All citations traceable to Pass 1 evidence.*
