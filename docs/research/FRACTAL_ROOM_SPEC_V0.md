# Fractal Room Spec v0

**Status:** Proposed (pending operator approval)
**Research:** [FRACTAL_VENTURE_CELL_RESEARCH.md](FRACTAL_VENTURE_CELL_RESEARCH.md)
**Build plan:** [BUILD_PLAN_FRACTAL_ROOM_V0.md](BUILD_PLAN_FRACTAL_ROOM_V0.md)

---

## 1. Design Principles

### 1.1 This is NOT a Cofounder clone

Cofounder is a UI-first company workspace with flat departments. Dharma's fractal room is a governed, self-funding, recursive operating container with telos gates, dissolution thresholds, and welfare constraints. The architecture is closer to Haier's RenDanHeYi micro-enterprise model than to any agent product on the market.

### 1.2 The Room is the recursive building block

From De Florio (2013): "Fractal social organizations are characterized by a single building block recursively applied at different layers." The Room dataclass is that building block. A Room containing three sub-rooms has the same schema as a sub-room containing three agents. Complexity is added by nesting, not by adding new component types.

### 1.3 Every Room is a Viable System

From Beer (1972): viable systems contain viable systems that can be modeled with the identical cybernetic description. Every room must have:
- S1 (Operations): agents + work packets
- S2 (Coordination): signal bus subscriptions
- S3 (Control): gates + approval requirements + budget
- S4 (Intelligence): kaizen reviews + trend analysis
- S5 (Identity): purpose + operator authority

### 1.4 Economic accountability with dissolution

From Haier: autonomy requires survival pressure. VentureCells that don't produce value get archived. Their agents and budget return to the parent. Their knowledge is preserved.

### 1.5 Knowledge compounds through SECI cycles

From Nonaka (2014): work → outcome → review → playbook → better work. This cycle must be explicit at the room level, not implicit.

---

## 2. Type Definitions

### 2.1 Room (base type)

```
FractalRoom:
  # Identity (S5)
  id: str                          # unique room identifier
  kind: RoomKind                   # operations | governance | venture_cell | research
  parent_id: str | None            # None = root room
  purpose: str                     # why this room exists (non-empty)
  status: RoomStatus               # proposed | incubating | active | graduating | archived | spun_out
  operator: str                    # human operator ID (S5 authority)

  # Roster (S1)
  agents: list[str]                # agent IDs assigned to this room
  agent_authorities: dict[str,str] # per-agent authority level within this room

  # Economy (S3)
  budget_tokens: int               # token budget allocated from parent
  current_burn: int                # tokens consumed so far (default 0)
  revenue_target: int              # expected revenue in tokens (0 for ops rooms)

  # Law (S3)
  allowed_work: list[str]          # types of work this room may perform
  forbidden_work: list[str]        # types of work this room must NOT perform (inherits from parent)
  gates: list[str]                 # telos gate names that apply to this room's work
  approval_required_for: list[str] # actions requiring human approval

  # Memory (S4)
  report_paths: dict[str,str]      # {"agentops": "reports/agentops/", "kaizen": "reports/kaizen/", ...}
  memory_namespace: str            # namespace for stigmergy marks and artifacts

  # Pulse (S4/S1 feedback)
  last_brief_date: str | None      # ISO date of last daily brief
  next_packet_recommendation: str | None  # what work should happen next
```

### 2.2 VentureCell (extends Room)

```
VentureCellV1 extends FractalRoom:
  # Business
  customer_or_beneficiary: str     # who this cell serves (non-empty, Haier zero-distance)
  value_proposition: str           # what value it provides

  # Hypothesis
  self_funding_hypothesis: str     # how this cell will fund itself
  first_revenue_proof: str         # what constitutes proof of first revenue

  # Lifecycle
  kill_conditions: list[str]       # conditions under which this cell should be archived
  spinout_conditions: list[str]    # conditions under which this cell graduates to independent

  # Welfare (Jagat Kalyan)
  jagat_kalyan_constraint: str     # welfare constraint this cell must satisfy
  welfare_tons_produced: float     # welfare-tons produced to date (default 0.0)

  # Autonomy
  autonomy_stage: int              # 1-5, maps to VentureCell ontology type
```

### 2.3 WorkPacket (scoped to a room)

```
WorkPacket:
  id: str                          # unique packet identifier
  source_room_id: str              # room that created this packet
  purpose: str                     # what this packet is trying to accomplish
  action_proposal_id: str | None   # ontology ActionProposal link (set after gate approval)
  assigned_agent_id: str | None    # agent executing this packet
  allowed_tools: list[str]         # tools the agent may use
  forbidden_mutations: list[str]   # files/resources the agent may not modify
  gate_requirements: list[str]     # gates that must pass before execution
  success_criteria: str            # how to determine if packet succeeded
  timeout_seconds: int             # max execution time (default 3600)
  cost_ceiling: int                # max token cost (0 = no limit)
  report_target: str               # where to write the result report
```

### 2.4 YDS Rating (human-only)

```
YDSRating:
  id: str                          # unique rating identifier
  artifact_id: str                 # what was rated
  room_id: str                     # which room context
  rater: str                       # MUST be human operator, not agent
  score: int                       # 1-10
  dimension: str                   # craft | truth | usefulness | beauty | coherence
  comment: str                     # optional human note
  timestamp: str                   # ISO datetime
```

---

## 3. Validation Rules

### 3.1 Room creation

1. `purpose` must be non-empty
2. `id` must be unique in registry
3. If `parent_id` is set, parent must exist
4. `budget_tokens` must be ≤ parent's remaining budget
5. `forbidden_work` must be superset of parent's `forbidden_work`
6. `approval_required_for` must be superset of parent's `approval_required_for`
7. Nesting depth ≤ 3 (root=0, room=1, sub-room=2, sub-sub-room=3)

### 3.2 VentureCell creation

1. All Room validation rules apply
2. `customer_or_beneficiary` must be non-empty (Haier zero-distance)
3. `revenue_target` must be > 0
4. `kill_conditions` must be non-empty
5. `kind` must be `venture_cell`
6. `autonomy_stage` must be 1-5

### 3.3 WorkPacket creation

1. `source_room_id` must reference an active room
2. `purpose` must be non-empty
3. If `cost_ceiling` > 0, room's `budget_tokens - current_burn` must be ≥ `cost_ceiling`
4. `assigned_agent_id` must be in the source room's `agents` list
5. `forbidden_mutations` must be superset of room's `forbidden_work`

### 3.4 YDS Rating creation

1. `rater` must be a recognized human operator ID (not an agent ID)
2. `score` must be 1-10
3. `dimension` must be one of: craft, truth, usefulness, beauty, coherence
4. `artifact_id` must reference an existing artifact
5. `room_id` must reference an existing room

### 3.5 Room archival (dissolution)

1. Room status changes to `archived`
2. All agents move to parent room's roster
3. Unspent `budget_tokens - current_burn` returns to parent's budget
4. Knowledge artifacts remain accessible (not deleted)
5. No new WorkPackets may be created for archived rooms
6. Sub-rooms are recursively archived

---

## 4. Spawn Protocol

When a room wants to spawn a sub-room:

```
1. Validate: CONSENT gate passes for spawning
2. Validate: parent has sufficient budget for child's budget_tokens
3. Validate: nesting depth < max (3)
4. Create: child inherits parent's forbidden_work + own additions
5. Create: child inherits parent's approval_required_for + own additions
6. Deduct: parent.budget_tokens -= child.budget_tokens
7. Register: child in RoomRegistry with parent_id set
8. Log: WitnessLog entry for spawn event
```

---

## 5. Kill Condition Evaluation

Kill conditions are strings that reference KPI keys. Evaluation:

```
kill_conditions: ["no_revenue_after_60_days", "burn_exceeds_3x_revenue"]

KPIs: {"revenue_usd": 0, "days_active": 75, "burn_usd": 500}

Evaluator:
  "no_revenue_after_60_days" → revenue_usd == 0 AND days_active > 60 → TRUE
  "burn_exceeds_3x_revenue" → burn_usd > 3 * revenue_usd → TRUE (500 > 0)

Result: kill conditions met → room should be archived
```

The evaluator is a pure function: `(conditions: list[str], kpis: dict) → bool`. No side effects. The archival decision is a separate step requiring operator approval in v0.

---

## 6. Example Room Instances

### 6.1 Root Room: Dharma Swarm Core

```yaml
id: dharma-swarm-core
kind: operations
parent_id: null
purpose: "Maintain system integrity and governed evolution of Dharma Swarm"
status: active
operator: dhyana
agents: [claude.local, codex.local, devin.cloud]
budget_tokens: 1000000
revenue_target: 0
allowed_work: [ci_fix, mismatch_fix, guardian_audit, cron_fleet, brief_generation]
forbidden_work: [live_autonomy, broad_v3_impl, ontology_refactor]
gates: [AHIMSA, SATYA, REVERSIBILITY]
approval_required_for: [merge, push, external_outreach, budget_increase, subcell_spawn]
report_paths:
  agentops: reports/agentops/
  kaizen: reports/kaizen/
  daily_brief: ~/dharma_briefs/
memory_namespace: core_ops
```

### 6.2 Revenue Wedge Room

```yaml
id: revenue-wedge
kind: venture_cell
parent_id: dharma-swarm-core
purpose: "Find and prove the first self-funding offer from Dharma Swarm"
status: incubating
operator: dhyana
agents: [devin.cloud, claude.local, codex.local]
budget_tokens: 50000
revenue_target: 100000  # $1,000 equivalent in tokens
customer_or_beneficiary: "Solo founders building with AI agents"
value_proposition: "Governed multi-agent repo operations that work safely without constant supervision"
self_funding_hypothesis: "Founders will pay for a system that runs CI, reviews PRs, and manages agent work across their repos with telos-gated safety"
first_revenue_proof: "One paying customer or LOI for managed agent operations"
kill_conditions: ["no_revenue_after_60_days", "burn_exceeds_3x_revenue"]
spinout_conditions: ["revenue_covers_burn", "3_paying_customers"]
jagat_kalyan_constraint: "Produce >= 1 welfare-ton per quarter"
allowed_work: [market_research, product_experiments, pricing_tests, customer_outreach, mvp_build]
forbidden_work: [live_autonomy, broad_v3_impl, ontology_refactor, dashboard_expansion, memory_consolidation]
gates: [AHIMSA, SATYA, REVERSIBILITY, CONSENT]
approval_required_for: [merge, push, external_outreach, spending_money, authoritative_yds_rating, budget_increase, subcell_spawn]
```

### 6.3 AgentOps Room

```yaml
id: agentops
kind: operations
parent_id: dharma-swarm-core
purpose: "Make multi-agent repo work safe and repeatable"
status: active
operator: dhyana
agents: [devin.cloud, warp.oz]
budget_tokens: 20000
revenue_target: 0
allowed_work: [work_packets, agent_registration, session_management, authority_review]
forbidden_work: [live_autonomy, broad_v3_impl, ontology_refactor, dashboard_expansion, memory_consolidation]
gates: [AHIMSA, SATYA, REVERSIBILITY]
approval_required_for: [merge, push, external_outreach, budget_increase, subcell_spawn, authority_escalation]
```

---

## 7. VSM Recursion Check

For each example room, verify all five subsystems are present:

| Room | S1 (Ops) | S2 (Coord) | S3 (Control) | S4 (Intel) | S5 (Identity) |
|------|----------|------------|--------------|------------|----------------|
| Core | agents + work packets | SignalBus | gates + approval + budget | kaizen + brief | purpose + operator |
| Revenue Wedge | agents + work packets | SignalBus | gates + approval + budget + kill_conditions | kaizen + brief + market signals | purpose + operator + customer |
| AgentOps | agents + work packets | SignalBus | gates + approval + budget | kaizen + brief | purpose + operator |

All rooms pass the recursion check. Each can (in principle) operate as a standalone viable system if removed from its parent.

---

## 8. Relationship to Existing Ontology

The Room/VentureCell schema does NOT replace the existing `VentureCell` ObjectType in `ontology.py:1444`. Instead:

- `ontology.py:VentureCell` remains the **identity record** in the ontology graph
- `fractal_room.py:FractalRoom` is the **runtime container** that scopes operations
- The link between them is `cell_id` — both reference the same ID
- The ontology type gains new properties over time (as the Room schema matures)
- Existing instances (Shakti Ginko, Operator Brief v0) become rooms when Build 2 lands

This avoids broad ontology refactoring (which is on the `forbidden_work` list for good reason).
