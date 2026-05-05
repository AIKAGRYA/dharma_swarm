# Fractal Venture Cell: Research Foundations

**Status:** Research artifact (informs `dharma_swarm/fractal_room.py` build)
**Build plan:** [BUILD_PLAN_FRACTAL_ROOM_V0.md](BUILD_PLAN_FRACTAL_ROOM_V0.md)

---

## 1. Source Models

This document synthesizes seven external bodies of work that inform how Dharma Swarm should model governed, fractal, self-funding venture cells.

### 1.1 Stafford Beer — Viable System Model (VSM)

**Source:** Beer, S. (1972). *Brain of the Firm*. Allen Lane.
**Also:** Beer, S. (1979). *The Heart of Enterprise*. Wiley.
**Online reference:** https://viable-systems.github.io/vsm-docs/overview/what-is-vsm/

**Core principle:** Any autonomous system capable of producing itself must contain five interacting subsystems. This is **recursive** — viable systems contain viable systems modeled with the identical cybernetic description at every level (Beer's "cybernetic isomorphism").

**The Five Systems:**

| System | Function | Dharma Mapping |
|--------|----------|----------------|
| S1 (Operations) | Primary activities producing value | `agent_runner.py`, WorkPackets, TaskBoard |
| S2 (Coordination) | Prevents conflict between operational units | `signal_bus.py`, `stigmergy.py` |
| S3 (Control) | Manages current operations, resource allocation | `telos_gates.py`, `orchestrator.py`, budget enforcement |
| S3* (Audit) | Sporadic random checks on S1 | `guardian_crew.py`, `vsm_channels.py:SporadicAudit` |
| S4 (Intelligence) | Looks outward and forward, planning | Zeitgeist feedback, market research, KaizenReview |
| S5 (Policy/Identity) | Ultimate authority, system identity | `dharma_kernel.py`, `identity.py`, human operator (Dhyana) |

**Key VSM principles for fractal rooms:**

1. **Recursion.** Each room must contain the same five functional subsystems as the parent room. A Revenue Wedge Room needs its own S1 (operations), S2 (coordination), S3 (control/gates), S4 (intelligence/kaizen), S5 (identity/purpose). If any is missing, the room is not viable.

2. **Algedonic channel.** Emergency signals bypass all intermediate management and go straight to S5 (identity/operator). Dharma already has this: `AlgedonicSignal` in `vsm_channels.py`. Fractal rooms must preserve this bypass — a sub-room's emergency signal must reach the human operator, not just the parent room's S3.

3. **Variety engineering.** A viable system must have requisite variety (Ashby's Law) — enough response capacity to match its environmental complexity. For fractal rooms: a room's `allowed_work` + `agents` must provide enough variety to achieve its `purpose`. If the room's variety is insufficient, it either needs more agents/tools or its purpose must narrow.

4. **Autonomy boundary.** S3-S5 of the containing system set the boundary of autonomy for each S1 unit. This maps directly to `allowed_work`, `forbidden_work`, `gates`, and `approval_required_for` in the room schema. The parent room defines the envelope; the child room operates within it.

**What Dharma already has from VSM:**
- `vsm_channels.py` (838 lines) implements S3↔S4 channel, sporadic S3* audit, algedonic signal, agent-internal recursion, variety expansion protocol
- `signal_bus.py` implements S2 coordination
- `telos_gates.py` implements S3 control
- `dharma_kernel.py` implements S5 identity

**What's missing:** The recursion. VSM says every viable sub-unit must have the same structure. Dharma's VSM implementation is flat — it describes the whole organism's S1-S5 but doesn't apply the same model inside each room/cell.

---

### 1.2 Haier RenDanHeYi (Win-Win Model of Individual-Goal Combination)

**Source:** Zhang Ruimin, CEO of Haier Group (2005-present)
**Key references:**
- Haier official: https://www.haier.com/global/press-events/news/20150922_142614.shtml
- EnliveningEdge analysis: https://enliveningedge.org/organizations/next-management-model-china/
- ZeroBlockers case study: https://www.zeroblockers.com/case-studies/haier-microenterprise-ownership
- EFMD Global Focus: https://globalfocusmagazine.com/special-supplement/rendanheyi/

**History:** Proposed in 2005, Phase 2.0 announced in 2015. Transformed 80,000 employees into 4,000+ micro-enterprises (MEs), each under 10 people. 12,000 middle managers became entrepreneurs or left.

**Key mechanisms:**

| Mechanism | Description | Dharma Mapping |
|-----------|-------------|----------------|
| Micro-Enterprise (ME) | Autonomous unit, <10 people, owns P&L | VentureCell (ontology type) |
| Ecosystem Micro-Community (EMC) | Cluster of related MEs along value chain | Room (container of cells) |
| Zero Distance to User | Every ME must have direct connection to customer | `customer_or_beneficiary` field |
| VAM (Value Adjustment Mechanism) | Profit sharing tied to value created above market average | EconomicEngine + ValueEvent chain |
| Centralized Pool | Safety net for failed MEs — employees return, bid for new opportunities | VentureCell status: `archived` → agents reassigned |
| Dissolution Threshold | When losses reach threshold, ME is dissolved | `kill_conditions` field |
| Bidding for Roles | Employees pitch their value and salary to join MEs | Agent assignment with authority ladder |

**The four RenDanHeYi principles that matter most:**

1. **Zero distance.** No ME exists "for internal purposes only." If you can't name your user, you don't exist. For Dharma: every VentureCell must have a `customer_or_beneficiary`. Core Ops Room's customer is "the system itself + its operator." Revenue Wedge Room's customer is "solo founders building with AI agents."

2. **Self-funding with dissolution.** EMCs bear their own losses. When losses reach a threshold, the community dissolves. This is NOT failure punishment — it's resource recycling. Failed experiments free up agents/budget for new experiments. For Dharma: `kill_conditions` evaluated against KPIs. Budget not replenished when kill conditions fire. Agents move to parent room's pool.

3. **Jellyfish organization.** No central nervous system gives commands. When one tentacle senses prey, others naturally surround it via coordinated effort. For Dharma: `SignalBus` + `StigmergyStore` already implement this. Rooms don't command sub-rooms — they emit signals that sub-rooms can subscribe to.

4. **Win-win value-added statement.** Replaces traditional P&L. Measures: (a) user value created, (b) ecosystem value shared, (c) ME compensation — all linked. You can't earn more unless users get more value. For Dharma: `ValueEvent` chain already models this. Extend with per-room aggregation.

**What Haier teaches that nobody else does:**
- **Autonomy with survival pressure.** Cofounder gives departments autonomy but no survival pressure. Holacracy gives circles autonomy but no economic accountability. Haier gives MEs both: full autonomy AND "if you don't create value, you dissolve." This is the key innovation for Dharma's fractal rooms.

---

### 1.3 Holacracy — Self-Governing Circles

**Source:** Robertson, B. (2015). *Holacracy: The New Management System for a Rapidly Changing World*. Henry Holt.
**Online reference:** https://www.holacracy.org/how-it-works/

**Core principle:** Replace management hierarchy with a constitutional framework. Roles are defined around work, not people. One person can hold multiple roles; one role can have multiple people.

**Holacracy's 5 modules:**

| Module | Function | Dharma Relevance |
|--------|----------|-----------------|
| 1. Organizational Structure | Encode roles and circles with Purpose, Accountabilities, Domains, Policies | Room schema (purpose, allowed_work, forbidden_work) |
| 2. Rules of Cooperation | Duties of transparency, processing requests, prioritization | Governance rules (approval requirements) |
| 3. Tactical Process | Regular meetings for coordination and unblocking | Daily Brief (room's pulse) |
| 4. Authority Distribution | Rights of circle members to take action within their roles | Agent authority levels per room |
| 5. Governance Process | Distributed governance at every level — anyone can propose structure changes | Kaizen Review → playbook updates |

**What Holacracy gets right that Dharma should adopt:**

1. **Roles around work, not people.** A room's agents are assigned to roles (WorkPacket types), not to the room generically. An agent assigned to "test runner" in the Revenue Wedge Room does test running, even if the same agent does "code review" in Core Ops Room.

2. **Governance as a process, not a document.** Holacracy's Module 5 allows anyone to propose structural changes to circles/roles through a defined process. Dharma's equivalent: KaizenReview can propose changes to room configuration (allowed_work, agents, budget) through the same gate process that governs work.

3. **Tensions as fuel.** Holacracy uses "tensions" (gaps between current reality and potential) as the driver for governance proposals. Dharma's equivalent: SignalBus events, guardian findings, and algedonic signals are tensions that should drive room-level governance changes.

**What Holacracy gets wrong (and Dharma should avoid):**

1. **No economic accountability.** Circles have authority and autonomy but no budget or revenue target. This means circles can exist indefinitely without producing value. Dharma fixes this with kill_conditions and budget enforcement.

2. **No survival pressure.** In Holacracy, circles don't die. They get restructured through governance meetings. This removes the evolutionary pressure that Haier's dissolution threshold provides.

3. **Meeting-heavy governance.** Holacracy's governance meetings are synchronous, scheduled, and have specific facilitation rules. For an agent swarm, synchronous meetings are the wrong pattern. Dharma should use asynchronous signals (SignalBus) and daily briefs instead.

---

### 1.4 Nonaka et al. — Dynamic Fractal Organizations

**Source:** Nonaka, I., Kodama, M., Hirose, A., & Kohlbacher, F. (2014). "Dynamic fractal organizations for promoting knowledge-based transformation." *European Management Journal*, 32(1), 137-146.
**DOI:** 10.1016/j.emj.2013.02.003

**Core idea:** A fractal organization builds on "dynamic ba" — shared contexts for knowledge creation that repeat self-similarly at every scale. Three types of knowledge interact in a triad:

1. **Tacit knowledge** — embodied, experiential
2. **Explicit knowledge** — codified, transferable
3. **Phronesis** — practical wisdom synthesized from tacit + explicit

**The fractal property:** Each organizational unit (ba) has the same knowledge creation process: externalization (tacit→explicit), combination (explicit→explicit), internalization (explicit→tacit), and socialization (tacit→tacit). This SECI cycle operates at individual, team, organization, and inter-organization levels — fractally.

**Dharma mapping:**

| Nonaka Concept | Dharma Equivalent |
|----------------|-------------------|
| Ba (shared context) | Room — the bounded operating context |
| Tacit knowledge | StigmergyStore marks, agent-internal state |
| Explicit knowledge | KnowledgeArtifact, Operator Brief, reports |
| Phronesis | YDS ratings (human practical wisdom about quality) |
| SECI cycle | WorkPacket execution → KaizenReview → playbook update → next WorkPacket |
| Fractal self-similarity | Room schema recursion (every room has same structure) |

**The key Nonaka insight for Dharma:** Knowledge creation requires a **boundary-crossing mechanism.** Tacit knowledge doesn't cross organizational boundaries naturally — it needs to be externalized into explicit artifacts. In Dharma: agent-internal learning needs to be externalized into KaizenReview records and then internalized by other agents as updated playbooks. Without this cycle, each room learns independently and the system doesn't compound knowledge.

---

### 1.5 De Florio et al. — Fractal Social Organizations

**Source:** De Florio, V., Bakhouya, M., Coronato, A., & Di Marzo, G. (2013). "Models and Concepts for Socio-technical Complex Systems: Towards Fractal Social Organizations." *Systems Research and Behavioral Science*, 30(6), 750-772.
**PDF:** https://cui.unige.ch/~dimarzo/papers/eSoC.pdf

**Core idea:** Fractal social organizations are characterized by a **single building block recursively applied at different layers.** This provides a homogeneous way to model collective behaviors at different complexity levels and scales.

**Key formal properties:**

1. **Recursive building block.** One organizational template is applied at every scale. At the lowest level, it contains individual agents. At higher levels, it contains instances of itself. The mathematical model shows that this recursive application spontaneously produces hierarchical and modular patterns.

2. **Mutualistic relationships.** Drawing from biology: organisms in fractal organizations relate through mutualism (both benefit), not parasitism. For Dharma: sub-rooms must benefit their parent room (contribute to parent's revenue/welfare target), and parent rooms must benefit their sub-rooms (provide budget, protection, governance).

3. **Structured addition of complexity.** Complexity is added by nesting the building block, not by adding new types of components. This means the same governance rules, economic tracking, and knowledge creation processes work at every level.

**Why this matters for Dharma:** It provides formal justification for the design principle that every room has the same schema. The Room dataclass is the recursive building block. A room containing three sub-rooms has the same structure as a sub-room containing three agents. The difference is only in what populates the `agents` and `children` fields.

---

### 1.6 BAMAS — Budget-Aware Multi-Agent Systems

**Source:** Yang, L., Luo, J., Liu, X., Lou, Y., & Chen, Z. (2025). "BAMAS: Structuring Budget-Aware Multi-Agent Systems." arXiv:2511.21572.
**URL:** https://arxiv.org/html/2511.21572v1

**Core contribution:** First framework to formally structure multi-agent systems under explicit budget constraints. Uses Integer Linear Programming (ILP) for agent selection and reinforcement learning for topology selection.

**Key findings relevant to Dharma:**

1. **Budget-aware agent selection.** Given a cost budget, select the optimal set of LLMs by solving an ILP that maximizes capability coverage while staying under budget. For Dharma: when a room has `budget_tokens`, the room should select agents that maximize capability coverage within that budget, not just use whatever agents are available.

2. **Topology matters.** BAMAS learns that simpler topologies (linear chains) work under tight budgets, while richer topologies (star, full mesh) work when resources are ample. For Dharma: a room with a small budget should use simple sequential work packets. A room with a large budget can use parallel fan-out work packets.

3. **Cost reduction up to 86%.** By jointly optimizing agent selection and collaboration topology, BAMAS achieves comparable performance at dramatically lower cost. For Dharma: budget enforcement isn't just a constraint — it's a performance optimization. Rooms that are forced to be economical often produce better results because they can't waste tokens on unnecessary elaboration.

**Dharma integration point:** The `CostTracker` and `EconomicEngine` already track per-agent cost. The missing piece is using cost data to inform agent selection and topology within rooms.

---

### 1.7 Venture Studio Model

**Source:** MIT Sloan Management Review (2026): "Is a Venture Studio Right for Your Company?"
**Also:** Venture Studios Hub: "The Venture Studio Playbook" (2025)
**Also:** Lionpeak Partners: "Venture Studio: Definition, Economics & Governance" (2026)

**Core model:** A venture studio systematically creates new startups by assembling ideas, people, and resources. Unlike VC (which invests in external founders), a studio **co-founds** ventures with shared equity and shared operating infrastructure.

**Lifecycle stages (from Venture Studios Hub):**

| Timeline | Status | Description | Dharma Mapping |
|----------|--------|-------------|----------------|
| Day 0 | Red | Idea proposed, not validated | VentureCell status: `proposed` |
| Day 30 | Amber | Basic validation done, hypothesis formed | VentureCell status: `incubating` |
| Day 90 | Yellow | MVP built, initial customer contact | VentureCell status: `active` |
| Day 180 | Green | Revenue or strong traction | VentureCell status: `graduating` |
| Spinout | Independent | Separate entity, studio retains equity | VentureCell status: `spun_out` |
| Kill | Dissolved | Failed to reach milestones | VentureCell status: `archived` |

**Four conditions for venture success (MIT Sloan):**
1. Specialized talent, IP portfolio, or market insights
2. Combination of internal assets and external capabilities
3. Right governance mechanisms
4. Long-term commitment of time and money

**Capital structure lessons:**
- Studio-level capital funds shared infrastructure (for Dharma: the runtime, orchestrator, telos gates — shared across all rooms)
- Venture-level capital is allocated per-venture at milestones (for Dharma: budget_tokens allocated per room, replenished only with proof)
- Kill decisions are made at milestone boundaries, not continuously (for Dharma: kill_conditions evaluated at KaizenReview intervals, not on every work packet)

---

## 2. Synthesis: The Five Laws of Fractal Rooms

From these seven sources, five laws emerge that any fractal room implementation must satisfy:

### Law 1: Recursive Self-Similarity (Beer, De Florio)

Every room has the same structure. A room containing three sub-rooms has the same schema as a sub-room containing three agents. The Room dataclass is the single recursive building block.

**Test:** Given any room, it must have: purpose, roster, economy, law, memory, pulse. No room may exist without all six.

### Law 2: Economic Accountability (Haier, Venture Studio)

Every room with kind `venture_cell` must have a revenue target or a hypothesis about how it will create measurable value. Every room must have a budget that is subtracted from its parent's budget. Kill conditions must be evaluable against KPIs.

**Test:** Creating a VentureCell without `revenue_target` raises ValidationError. Budget of child rooms sums to ≤ parent budget. Kill condition evaluation produces a boolean from KPI dict.

### Law 3: Governed Autonomy (Holacracy, Beer, Factory)

Rooms have autonomy within boundaries set by their parent's S3 (control layer). Forbidden work inherits additively — a child room inherits all parent forbidden work plus its own. Approval requirements propagate downward.

**Test:** A child room's `forbidden_work` is a superset of its parent's `forbidden_work`. A child room cannot approve actions its parent requires approval for.

### Law 4: Knowledge Compounding (Nonaka)

Every room has a SECI cycle: work produces outcomes → outcomes produce KaizenReviews → reviews update playbooks → playbooks improve next work. This cycle must be explicit, not implicit.

**Test:** A completed WorkPacket produces a KaizenReview record. The review updates the room's playbook recommendations. The next WorkPacket references the updated playbook.

### Law 5: Dissolution with Recycling (Haier, Venture Studio)

When a room's kill conditions fire, the room is archived (not deleted). Its agents are returned to the parent room's pool. Its knowledge (KaizenReviews, playbooks, artifacts) is preserved in the parent room's memory. The budget tokens are returned to the parent.

**Test:** Archiving a room: agents appear in parent roster, budget returns to parent, knowledge artifacts remain accessible via parent memory, room status changes to `archived`.

---

## 3. How Dharma's Existing Primitives Map

### 3.1 Already Built (can reuse directly)

| Primitive | Location | What It Does | Room Role |
|-----------|----------|-------------|-----------|
| VentureCell ObjectType | `ontology.py:1444-1482` | First-class ontology type with autonomy_stage, budget_tokens, kpis | The cell identity |
| cell_has_agent link | `ontology.py:1510-1513` | Links VentureCell → AgentIdentity (1:many) | Agent roster |
| belongs_to_cell link | `ontology.py:1506-1509` | Links ActionProposal → VentureCell (many:1) | Work packet scoping |
| TelosGatekeeper | `telos_gates.py` | 11 dharmic safety gates with witness logs | Room-level gates |
| CorrelationContext | `correlation_context.py` | trace_id/proposal_id/session_id propagation | Need to add cell_id |
| SignalBus | `signal_bus.py` | Pub-sub fanout for S2 coordination | Inter-room signals |
| StigmergyStore | `stigmergy.py` | Pheromone-trail coordination (append-only JSONL) | Room-local memory |
| EconomicEngine | `economic_engine.py` | Revenue/expense tracking with trace_id | Room economic tracking |
| CostTracker | `cost_tracker.py` | LLM cost tracking per agent | Budget consumption |
| KaizenOpsLocal | `kaizen_ops_local.py` | SQLite-backed ops monitoring | Room improvement loop |
| Operator Brief | `operator_brief/insight_brief.py` | Daily brief generator (already cell-scoped) | Room pulse |
| QualityForge | `quality_forge.py` | Artifact scoring (elegance + behavioral + telos) | Automated quality signal |
| ExternalAgentRegistration | `external_agent_registration.py` | Authority ladder for Devin/Kimi/Warp | External agent scoping |
| AutonomyPolicy | `external_agent_registration.py:136-177` | Positive refusal flags (can_approve_prs, can_write_source, etc.) | Per-agent permissions |
| AlgedonicSignal | `vsm_channels.py:73` | Emergency bypass to S5 (operator) | Room emergency channel |
| GuardianCrew | `guardian_crew.py` | 4-hour cycle auditing (S3*) | Room audit |
| JagatKalyanEngine | `jagat_kalyan.py` | Welfare-ton tracking, world domain registry | Welfare constraint |
| TaskBoard | `task_board.py` | Task assignment with trace_id | Work packet execution |
| RuntimeStateStore | `runtime_state.py` | Workspace leases, artifact records | Execution isolation |

### 3.2 Needs Extension

| Gap | What's Needed | Effort |
|-----|---------------|--------|
| Room container | FractalRoom dataclass wrapping the above | Small — schema + validation |
| VentureCell v1 | Extend with customer, hypothesis, kill_conditions, spinout_conditions | Small — schema + validation |
| cell_id in CorrelationContext | Add `cell_id: str` field, propagate via contextvars | Small — 1 file edit + tests |
| Budget enforcement | Something reads `budget_tokens` and blocks work when depleted | Medium — hook into orchestrator |
| Kill condition evaluation | Evaluate kill_conditions against KPI dict periodically | Small — pure function |
| Spawn protocol | Parent room creates child room with budget subtraction, forbidden_work inheritance | Small — validation logic |
| WorkPacket type | Explicit type linking room→proposal→agent→report | Small — dataclass |
| KaizenReview per room | Extend KaizenOpsLocal with room_id scoping | Small — add column |
| Room Brief sections | Extend operator brief with budget/revenue/agent activity | Medium — template changes |
| YDS as distinct type | Human-only quality rating separate from QualityForge | Small — dataclass + validation |

### 3.3 Does Not Exist Yet (future builds)

| Feature | Description | When |
|---------|-------------|------|
| Room registry with persistence | SQLite or file-backed room store | Build 2+ |
| Orchestrator room dispatch | Orchestrator routes work to rooms | Build 3+ |
| Inter-room signal routing | SignalBus routes events to specific rooms | Build 3+ |
| Room Dashboard UI | Next.js room state viewer | Build 5+ |
| Autonomous room spawning | Agent-initiated sub-room creation (with gates) | Build 4+ |

---

## 4. VSM Recursion: How Each Room Must Be Viable

Every room, at every nesting level, must have all five Beer subsystems. Here is how the Room schema maps to S1-S5:

```
Room
│
├── S1 (Operations): agents + WorkPackets + TaskBoard
│   What produces value inside this room
│
├── S2 (Coordination): SignalBus subscriptions + StigmergyStore
│   How agents in this room coordinate without central command
│
├── S3 (Control): gates + approval_required_for + budget enforcement
│   How current operations are governed and resourced
│
├── S3* (Audit): GuardianCrew cycle + sporadic checks
│   Random verification that S1 is obeying S3 boundaries
│
├── S4 (Intelligence): KaizenReview + market signals + trend analysis
│   What this room is learning about its environment
│
└── S5 (Identity): purpose + operator + dharma_kernel constraints
    Why this room exists and who has ultimate authority
```

**The recursion test:** Take any room. Remove it from its parent. Can it still operate as a standalone viable system? If yes, the VSM recursion is correct. If no, identify which S-system is missing and add it.

---

## 5. The Metabolic Chain (How Layers Connect)

```
Room.purpose
  ↓ creates
WorkPacket (AgentOps scope: which agent, which tools, which gates)
  ↓ executed by
Agent (via agent_runner, with CorrelationContext carrying cell_id)
  ↓ produces
Outcome + KnowledgeArtifact + ValueEvent
  ↓ reviewed by
KaizenReview (what worked, what failed, playbook update)
  ↓ summarized in
Daily Brief (room's current truth)
  ↓ rated by
YDS (human taste verdict — is this actually good?)
  ↓ feeds back into
Room.purpose refinement + next WorkPacket recommendation
  ↓ evaluated against
Kill conditions / spinout conditions
  ↓ if kill → archive room, return agents+budget to parent
  ↓ if spinout → promote room to independent entity
```

This maps to the invariant chain already in the ontology:

```
Evidence → ActionProposal → GateDecision → WitnessLog →
KnowledgeArtifact → Outcome → ValueEvent → Contribution → Memory
```

The fractal room adds economic accountability at each step:
- ActionProposal: costs tokens from room budget
- GateDecision: checked against room-specific gates
- KnowledgeArtifact: scoped to room via cell_id
- ValueEvent: aggregated into room-level revenue
- Memory: retained even if room is archived

---

## 6. External Product Pattern Analysis

### 6.1 Cofounder (docs.cofounder.co)

**What it is:** Company-shaped agent workspace. Departments → agents → tasks → skills → integrations. "Superoptimizer" manager agent coordinates across departments.

**What Dharma should take:**
- Skills as first-class reusable guidance packages (Dharma equivalent: SKILL.md + KaizenOps playbooks)
- Flows with approval modes: "Always Ask" vs "Auto-Approve" (Dharma equivalent: `approval_required_for` field)
- Agent memory: short-term context + durable preferences + tool-derived knowledge (Dharma equivalent: StigmergyStore + MemoryPalace)

**What Dharma should NOT take:**
- Flat department model (no fractal nesting)
- UI-first approach (canvas, task panel, publishing pipeline)
- No economic accountability (departments don't have budgets or kill conditions)
- No telos/ethical gates (binary approve/deny only)
- No welfare constraint

**Cofounder ↔ Dharma Mapping:**

| Cofounder | Dharma Equivalent | Status |
|-----------|-------------------|--------|
| Department | Room | Needs building |
| Agent | AgentIdentity + ExternalAgentRegistration | Exists |
| Task | WorkPacket (→ ActionProposal → TaskBoard) | Needs building |
| Skill | SKILL.md + KaizenOps playbook | Partially exists |
| Canvas | Not needed (docs/reports are Dharma's canvas) | Skip |
| Company View | Daily Brief + room aggregation | Partially exists |
| Library | artifact_manifest + MemoryPalace | Exists |
| Integration | ExternalAgentRegistration | Exists |
| Review Queue | Operator approval queue (operator_core/contracts.py) | Exists |

### 6.2 Factory Missions (docs.factory.ai)

**What it is:** Planned, milestone-based work execution. Collaborative planning → feature decomposition → Mission Control orchestration → validation at milestones → hooks for deterministic enforcement.

**What Dharma should take:**
- Planning before execution (WorkPacket must be planned and approved before agent starts)
- Milestone validation (KaizenReview at completion, not just at end)
- Hooks as deterministic code, not prompt suggestions (telos gates already do this)

**What Dharma should NOT take:**
- Their risk classification system (Dharma's PermissionRisk enum is already more nuanced)
- Their hook format (bash commands returning exit codes — Dharma's gates are Python with witness logs)

**Factory's Hook Events → Dharma Gate Events:**

| Factory Hook | Dharma Equivalent |
|-------------|-------------------|
| PreToolUse | Gate check before ActionProposal execution |
| PostToolUse | Outcome validation after work packet completion |
| UserPromptSubmit | Not needed (agents don't take prompts in room model) |
| Stop | Kill condition evaluation |
| SubagentStop | Sub-room archival with agent recycling |

### 6.3 Haier RenDanHeYi

(Detailed in Section 1.2 above)

**The single most important lesson:** Autonomy WITH survival pressure. This is the piece that Cofounder, Factory, and Holacracy all lack. Haier proves that micro-enterprises with dissolution thresholds outperform departments with infinite tenure.

**Haier's centralized pool → Dharma's parent room roster:**
When a Haier ME dissolves, employees go back to the centralized pool and bid for new opportunities. When a Dharma VentureCell archives, its agents go back to the parent room's roster and can be assigned to new sub-rooms or work packets.

---

## 7. Open Questions for Build Phase

1. **Should rooms be persistent (SQLite) or ephemeral (in-memory)?** Build 1 recommendation: in-memory with JSON serialization. Persistence comes in Build 2.

2. **Should the Room schema extend VentureCell or wrap it?** Recommendation: Room is the base type. VentureCell extends Room with economic fields. Not all rooms are venture cells (Core Ops Room is a room but not a venture cell).

3. **How frequently should kill conditions be evaluated?** Recommendation: at KaizenReview intervals (after each work packet batch), not continuously. This prevents premature killing of rooms that have slow-building value.

4. **Should budget enforcement be hard or soft?** Recommendation: hard for venture cells (work packet rejected if budget depleted), soft for operations rooms (warning emitted, work continues). The rationale: venture cells exist to prove economic viability; ops rooms exist to keep the system running.

5. **Who can create a room?** Recommendation: only the human operator or an agent with CONSENT gate approval. No autonomous room spawning in v0.

6. **How deep can nesting go?** Recommendation: maximum depth 3 for v0 (root → room → sub-room). Deeper nesting adds coordination overhead that outweighs benefits at early stages.

---

## 8. References

1. Beer, S. (1972). *Brain of the Firm*. Allen Lane.
2. Beer, S. (1979). *The Heart of Enterprise*. Wiley.
3. De Florio, V. et al. (2013). "Towards Fractal Social Organizations." *Syst. Res. Behav. Sci.*, 30(6), 750-772.
4. Nonaka, I. et al. (2014). "Dynamic fractal organizations for promoting knowledge-based transformation." *European Management Journal*, 32(1), 137-146.
5. Robertson, B. (2015). *Holacracy: The New Management System for a Rapidly Changing World*. Henry Holt.
6. Yang, L. et al. (2025). "BAMAS: Structuring Budget-Aware Multi-Agent Systems." arXiv:2511.21572.
7. Haier Group (2015). "Phase 2.0 of RenDanHeYi." https://www.haier.com/global/press-events/news/20150922_142614.shtml
8. MIT Sloan Management Review (2026). "Is a Venture Studio Right for Your Company?"
9. Venture Studios Hub (2025). "The Venture Studio Playbook."
10. Maturana, H.R. & Varela, F.J. (1974). "Autopoiesis: The organization of living systems." *BioSystems*, 5(4), 187-196.
11. Zhang et al. (2024). NeurIPS — diversity-competence tradeoff in multi-agent ensembles.
12. Condorcet, M. (1785). *Essai sur l'application de l'analyse à la probabilité des décisions rendues à la pluralité des voix.*
13. Böttcher, L. & Kernell, G. (2022). "Examining the limits of the Condorcet Jury Theorem." *Collective Intelligence*, 1(2).
