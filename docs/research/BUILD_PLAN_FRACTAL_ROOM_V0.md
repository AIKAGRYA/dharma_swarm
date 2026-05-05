# Build Plan: Fractal Room v0

**Status:** Proposed (pending operator approval)
**Research foundation:** [FRACTAL_VENTURE_CELL_RESEARCH.md](FRACTAL_VENTURE_CELL_RESEARCH.md)
**Spec:** [FRACTAL_ROOM_SPEC_V0.md](FRACTAL_ROOM_SPEC_V0.md)

---

## Build Sequence

### Build 1: Schema + Tests Only (NO RUNTIME)

**Goal:** Establish the recursive building block. Prove the Five Laws hold.

**Files:**
- `dharma_swarm/fractal_room.py` — FractalRoom, VentureCellV1, WorkPacket, RoomRegistry (in-memory)
- `tests/test_fractal_room.py` — 20+ tests proving the Five Laws

**What gets built:**

```python
# Core types
class RoomKind(StrEnum):
    OPERATIONS = "operations"
    GOVERNANCE = "governance"
    VENTURE_CELL = "venture_cell"
    RESEARCH = "research"

class RoomStatus(StrEnum):
    PROPOSED = "proposed"
    INCUBATING = "incubating"
    ACTIVE = "active"
    GRADUATING = "graduating"
    ARCHIVED = "archived"
    SPUN_OUT = "spun_out"

@dataclass
class FractalRoom:
    # Identity
    id: str
    kind: RoomKind
    parent_id: str | None
    purpose: str
    status: RoomStatus
    operator: str  # human operator

    # Roster
    agents: list[str]  # agent IDs
    agent_authorities: dict[str, str]  # agent_id → authority level

    # Economy
    budget_tokens: int
    current_burn: int = 0
    revenue_target: int = 0  # 0 means no revenue requirement

    # Law
    allowed_work: list[str]
    forbidden_work: list[str]
    gates: list[str]  # gate names from TelosGatekeeper
    approval_required_for: list[str]

    # Memory
    report_paths: dict[str, str]
    memory_namespace: str  # stigmergy/artifact namespace

    # Pulse
    last_brief_date: str | None = None
    next_packet_recommendation: str | None = None

@dataclass
class VentureCellV1(FractalRoom):
    # Business
    customer_or_beneficiary: str = ""
    value_proposition: str = ""

    # Hypothesis
    self_funding_hypothesis: str = ""
    first_revenue_proof: str = ""

    # Lifecycle
    kill_conditions: list[str] = field(default_factory=list)
    spinout_conditions: list[str] = field(default_factory=list)

    # Welfare
    jagat_kalyan_constraint: str = ""
    welfare_tons_produced: float = 0.0

    # Autonomy
    autonomy_stage: int = 1  # 1-5, maps to VentureCell ontology

@dataclass
class WorkPacket:
    id: str
    source_room_id: str
    purpose: str
    action_proposal_id: str | None = None
    assigned_agent_id: str | None = None
    allowed_tools: list[str] = field(default_factory=list)
    forbidden_mutations: list[str] = field(default_factory=list)
    gate_requirements: list[str] = field(default_factory=list)
    success_criteria: str = ""
    timeout_seconds: int = 3600
    cost_ceiling: int = 0
    report_target: str = ""
```

**Tests (proving the Five Laws):**

```
# Law 1: Recursive Self-Similarity
test_room_has_all_six_components       # purpose, roster, economy, law, memory, pulse
test_child_room_has_same_schema        # child room validates same fields as parent
test_venture_cell_extends_room         # VentureCell has all Room fields plus business/lifecycle

# Law 2: Economic Accountability
test_venture_cell_requires_revenue_target      # ValidationError if missing
test_budget_conservation                        # child budgets sum ≤ parent budget
test_kill_condition_evaluation                  # boolean from KPI dict
test_spinout_condition_evaluation               # boolean from KPI dict

# Law 3: Governed Autonomy
test_forbidden_work_inherits_additively         # child = parent + own
test_child_cannot_remove_parent_approval_requirement  # approval propagates
test_child_cannot_exceed_parent_budget          # budget subtraction enforced
test_spawn_requires_consent_gate               # spawn without gate raises error

# Law 4: Knowledge Compounding
test_work_packet_links_to_room                  # source_room_id set
test_kaizen_review_links_to_room                # room_id on review
test_playbook_update_from_review                # review produces recommendation

# Law 5: Dissolution with Recycling
test_archive_returns_agents_to_parent           # agents move up
test_archive_returns_budget_to_parent           # budget moves up
test_archive_preserves_knowledge                # artifacts remain accessible
test_archived_room_rejects_new_work             # no new work packets

# Additional validation
test_max_nesting_depth_3                        # depth > 3 raises error
test_room_id_uniqueness                         # registry enforces unique IDs
test_operations_room_no_revenue_required        # kind=operations, revenue_target=0 OK
test_yds_rating_human_only                      # agent_id must be human operator
```

**Does NOT include:**
- Database persistence
- Orchestrator wiring
- Real agent dispatch
- Dashboard UI
- SignalBus integration
- CorrelationContext cell_id (that's Build 2)

---

### Build 2: CorrelationContext + Room Scoping

**Goal:** Wire rooms into the runtime via cell_id.

**Files:**
- `dharma_swarm/correlation_context.py` — add `cell_id: str` field
- `dharma_swarm/runtime_state.py` — add `cell_id` column
- `dharma_swarm/task_board.py` — add `cell_id` column + filter
- `dharma_swarm/kaizen_ops_local.py` — add `room_id` column
- `tests/test_fractal_room_integration.py` — integration tests

**Depends on:** Build 1 merged

---

### Build 3: Operator Brief Room Sections

**Goal:** Make rooms visible in the daily brief.

**Files:**
- `dharma_swarm/operator_brief/insight_brief.py` — budget/revenue/agent_activity sections
- `dharma_swarm/operator_brief/room_brief.py` — room-specific brief generator

**Depends on:** Build 1 + Build 2 merged

---

### Build 4: KaizenReview v0 (per-room)

**Goal:** Implement the SECI cycle at room level.

**Files:**
- `dharma_swarm/kaizen_review.py` — KaizenReview dataclass + evaluator
- `tests/test_kaizen_review.py` — outcome → review → playbook update cycle

**Depends on:** Build 1 merged

---

### Build 5: Revenue Wedge Room (first real room instance)

**Goal:** Instantiate the first VentureCell with real economic pressure.

**Files:**
- `docs/governance/VENTURE_CELL_REVENUE_WEDGE.md` — room specification
- Room configuration YAML/JSON defining the Revenue Wedge room

**Depends on:** Builds 1-4 merged

---

## Decision Log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Room vs VentureCell relationship | VentureCell extends Room | Not all rooms are venture cells; Core Ops is a room but not a VC |
| Persistence in v0 | None (in-memory + JSON) | Reduces scope; persistence in Build 2+ |
| Max nesting depth | 3 | Deeper nesting adds coordination cost that outweighs benefit early |
| Budget enforcement mode | Hard for VCs, soft for ops | VCs prove viability; ops rooms keep system running |
| Kill condition timing | At KaizenReview intervals | Prevents premature killing; aligned with improvement cycle |
| Room creation authority | Human operator or CONSENT gate | No autonomous room spawning in v0 |
| YDS signal | Separate from QualityForge | YDS is human taste; QualityForge is automated quality |
| Cofounder department model | NOT adopted | Flat departments lack fractal nesting + economic accountability |
| Haier ME model | Primary inspiration | Autonomy + survival pressure + dissolution + recycling |
| Beer VSM recursion | Required for every room | Each room must have S1-S5 functional subsystems |

---

## Success Criteria

Build 1 is complete when:
1. All 20+ tests pass
2. FractalRoom + VentureCellV1 + WorkPacket dataclasses validate correctly
3. The Five Laws are machine-verified by tests
4. No runtime dependencies (pure schema + validation)
5. File stays under 500 lines (per CLAUDE.md)

Build sequence is complete when:
1. Revenue Wedge Room is instantiated as a real VentureCell
2. Daily Brief shows room-specific budget/revenue
3. KaizenReview produces per-room playbook updates
4. CorrelationContext carries cell_id through all operations
5. Kill conditions can archive a room and recycle its resources
