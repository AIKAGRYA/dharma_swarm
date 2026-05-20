# VentureCell Lifecycle

**Status:** Spec (companion to `SHAKTI_GINKO_ORGAN.md`)
**Branch:** `spec/shakti-ginko-organ`
**Telos gates:** AHIMSA · SATYA · REVERSIBILITY · SVABHAAVA
**Ground truth:** `dharma_swarm/ontology.py:1470-1507`, `dharma_swarm/fractal/fractal_room.py`, `dharma_swarm/ginko_orchestrator.py:820-892`

> A VentureCell is a Card in BoardStore terms — an ontology-typed work unit with its own roster, budget, KPIs, autonomy stage, and lifecycle. Cells are the cells of the organ. Their lifecycle is the organ's metabolism.

---

## 1. What a VentureCell Is (and Is Not)

A **VentureCell** is the unit of *bounded economic survival pressure* inside dharma_swarm. It carries:

- A first-class **ontology object** at `ontology.py:1470-1507` (`_VENTURE_CELL`) with `create_roles=["orchestrator","system"]`, `telos_required=True`, `audit_all=True`, `shakti_energy=MAHALAKSHMI`, `telos_alignment=0.95`.
- A **runtime dataclass** `VentureCellV1` at `fractal/fractal_room.py:175+` that extends `FractalRoom` with business fields: `customer_or_beneficiary`, `value_proposition`, `self_funding_hypothesis`, `first_revenue_proof`, `kill_conditions`, `spinout_conditions`, `jagat_kalyan_constraint`, `welfare_tons_produced`.
- A **declared instance** at `docs/governance/VENTURE_CELL_REVENUE_WEDGE.md` (the `revenue-wedge` cell, $50k token budget, $10k revenue target).

A VentureCell is **not**:

- A new service or microservice. It is a typed row + roster + budget that lives in BoardStore.
- A startup. It is a unit of *focused work with kill/spinout conditions* inside an organ. Most VentureCells stay in dharma_swarm forever.
- A pure code module. Modules implement domain logic for one or more cells; the cell is the governance/economic boundary.

The cell is **the operator's instrument for delegation under constraint**. Each cell answers four operator questions:

1. *Who is the customer or beneficiary?* (`customer_or_beneficiary`)
2. *How does it pay for itself, or by when does it stop trying?* (`self_funding_hypothesis`, `kill_conditions`)
3. *What does it produce for Jagat Kalyan?* (`jagat_kalyan_constraint`, `welfare_tons_produced`)
4. *When does it graduate, dissolve, or spin out?* (`spinout_conditions`)

---

## 2. State Machine

VentureCells move through a finite set of states. State is stored on the cell row in BoardStore (specifically the `room_status` / `venture_cell_status` column), and every transition is a BoardStore mutation gated by RBAC + telos checks.

```
            ┌──────────────┐
            │   PROPOSED   │   (created from IdeationNoticer or operator)
            └──────┬───────┘
                   │  operator/system approve · roster ≥ 1 · budget set
                   ▼
            ┌──────────────┐
            │  INCUBATING  │   (Stage 1: research-only, no live capital)
            └──────┬───────┘
                   │  ViabilityNoticer green · ≥1 first_revenue_proof attempt
                   ▼
            ┌──────────────┐
            │    ACTIVE    │   (Stages 2-4: paper → micro → small capital)
            └──┬───┬───┬───┘
               │   │   │
   spinout ◄───┘   │   └────► kill (any kill_condition met)
                   │
                   ▼
            ┌──────────────┐
            │    MATURE    │   (Stage 5: self-funding, autonomous)
            └──────┬───────┘
                   │
                   ├─► DIVESTING   (graduating into spinout)
                   └─► ARCHIVED    (mission complete or wound down)
```

The status enum already exists in code at two places that must stay in sync:

- `ontology.py:1483` — `enum_values=["incubating","active","mature","divesting","archived"]`
- `fractal_room.py:62-69` — `RoomStatus = PROPOSED|INCUBATING|ACTIVE|GRADUATING|ARCHIVED|SPUN_OUT`

**Action item (substrate work):** unify these into a single `VentureCellStatus` enum exported from `dharma_swarm.ontology.venture` and have both call sites import it. This is a Phase 1 substrate migration (see `SHAKTI_GINKO_ORGAN.md` §11) and lands with the BoardStore facade PR.

### 2.1 Transition table

| From | To | Trigger | Required | Forbidden | Telos gates |
|------|-----|---------|----------|-----------|-------------|
| (none) | PROPOSED | `Create` action | `customer_or_beneficiary` set, `value_proposition` set | none | AHIMSA, SATYA, REVERSIBILITY |
| PROPOSED | INCUBATING | operator approval *or* `system` auto-promote when arjuna_weight ≥ T | roster ≥ 1, `budget_tokens > 0`, `jagat_kalyan_constraint` non-empty | autonomy_stage > 1 | AHIMSA, SATYA |
| INCUBATING | ACTIVE | `Advance` action with `autonomy_stage = 2` | first_revenue_proof attempted, ViabilityNoticer green | live capital | SVABHAAVA |
| ACTIVE | ACTIVE (stage++) | `Advance` action | `AUTONOMY_REQUIREMENTS[next_stage]` satisfied (see §3) | skipping stages | SVABHAAVA |
| ACTIVE | MATURE | `Advance` action to stage 5 | all stage-5 reqs met | none | SVABHAAVA |
| any | DIVESTING | `evaluate_spinout_conditions(cell.spinout_conditions, kpis) == True` AND operator approval | cell already at stage ≥ 4 | none | SATYA, REVERSIBILITY |
| any (≠ ARCHIVED) | ARCHIVED | `evaluate_kill_conditions(cell.kill_conditions, kpis) == True` OR operator override | none | reviving without ADR | AHIMSA, REVERSIBILITY |
| DIVESTING | ARCHIVED | spinout complete (external entity holds the work) | new entity referenced in cell metadata | none | SATYA |

All evaluator functions already exist as pure functions in `fractal_room.py:243-303`:

- `evaluate_kill_conditions(conditions, kpis)` — returns `True` if **any** condition met (OR semantics).
- `evaluate_spinout_conditions(conditions, kpis)` — returns `True` if **all** conditions met (AND semantics).

### 2.2 Reversibility

REVERSIBILITY gate forbids destructive transitions without recoverable state. Concretely:

- `ARCHIVED` is *append-only soft delete*: the row stays, status flips, agents unassigned. Recovery = unarchive PR + ADR.
- `DIVESTING` snapshots the cell's BoardStore subtree (cards + cards' children + artifacts) into `~/.dharma/spinouts/<cell_id>.tar.zst` before status flip. Snapshot location is on the operator's Mac, not in repo.
- Stage downgrade (`autonomy_stage` 5 → 4) is allowed only via operator action and emits `SIGNAL_VENTURE_CELL_AUTONOMY_DOWNGRADED` for audit.

---

## 3. Autonomy Stage Gates (1–5)

Five-stage ladder, ground truth at `ginko_orchestrator.py:826-849`:

| Stage | Name | Capital allowed | Requirements (additive to lower stages) |
|------:|------|-----------------|-----------------------------------------|
| 1 | Research-only | none | cell exists, roster ≥ 1, telos gates green |
| 2 | Paper trading / dry run | none | `min_predictions ≥ 100`, `max_brier ≤ 0.20` |
| 3 | Micro-capital ($100–$500) | up to $500 live | `min_predictions ≥ 500`, `max_brier ≤ 0.125`, `min_win_rate ≥ 0.55` |
| 4 | Small capital ($1K–$5K) | up to $5K live | `min_predictions ≥ 1000`, `max_brier ≤ 0.10`, `min_win_rate ≥ 0.58`, `min_sharpe ≥ 1.5` |
| 5 | Mostly autonomous | governed by `spinout_conditions` | `min_predictions ≥ 2000`, `max_brier ≤ 0.08`, `min_win_rate ≥ 0.60`, `min_sharpe ≥ 2.0`, `max_drawdown ≤ 0.15` |

> The current `AUTONOMY_REQUIREMENTS` table is **trading-specific** (Brier, Sharpe, drawdown). It must remain valid for the trading-lab grouping but each non-trading VentureCell defines its own analogous table in `kpi_requirements` on its cell row. See §3.3.

### 3.1 Advancement procedure

1. **Check** via `check_autonomy_advancement(state)` at `ginko_orchestrator.py:853-892`. Returns `{can_advance, next_stage, requirements, met, unmet}`.
2. **Propose** advancement → BoardStore mutation `Advance(VentureCell, autonomy_stage += 1)`.
3. **Telos gate** SVABHAAVA: the proposer's role authority covers the new stage.
4. **Operator approval** required for stage 3 → 4 (first non-trivial live capital) and stage 4 → 5 (autonomous). Stages 1 → 2, 2 → 3 may be auto-advanced when `check_autonomy_advancement.can_advance == True` and arjuna_weight ≥ AUTO_ADVANCE_THRESHOLD (default 0.7).
5. **Emit** `SIGNAL_VENTURE_CELL_AUTONOMY_ADVANCED` with `{cell_id, from_stage, to_stage, justification, evidence_ids}`.
6. **Write** `WitnessEvent` to ledger.

### 3.2 Stage demotion

Demotion (downgrade) is **operator-only** and **always logged**. Triggers that *recommend* demotion (auto-demotion is forbidden; humans pull the trigger):

- Brier score deteriorates by ≥ 0.02 over 200 predictions
- Drawdown breaches stage threshold for 3 consecutive days
- `welfare_tons_produced` turns negative
- Operator override

When QualityNoticer (§4 below) detects any of these, it emits `WARN_VENTURE_CELL_DEMOTION_RECOMMENDED` and creates a card on the operator's TaskBoard.

### 3.3 Non-trading stage gates

For VentureCells outside the trading-lab grouping (e.g., research cells, infra cells, community cells), the trading-specific KPIs (`brier_score`, `min_sharpe`) are inapplicable. Each non-trading cell must define a `kpi_requirements` dict in its row, with the same shape as `AUTONOMY_REQUIREMENTS`:

```yaml
# example: research-cell autonomy gates
kpi_requirements:
  2:
    min_published_findings: 3
    peer_review_score_min: 0.7
  3:
    min_published_findings: 10
    peer_review_score_min: 0.8
    operator_satisfaction_min: 0.85
```

`check_autonomy_advancement` becomes a thin dispatcher: if `cell.domain == "economic"` and cell belongs to the trading-lab grouping, use the canonical table; otherwise, use `cell.kpi_requirements`. This refactor lives in the Phase 2 migration PR (`SHAKTI_GINKO_ORGAN.md` §11).

---

## 4. KPI Tracking

Every VentureCell tracks KPIs in its `kpis` dict (PropertyType.DICT at `ontology.py:1485`). KPIs are computed by **noticers** (see `BUSINESS_INTELLIGENCE_NOTICERS.md`) and updated by mutation actions. Cells never compute their own KPIs — that would be a circular trust path.

### 4.1 Universal KPIs (every cell)

These KPIs are required on every VentureCell, regardless of domain. They are also the KPIs consumed by the kill/spinout evaluators at `fractal_room.py:248-303`.

| KPI | Type | Computed by | Updated cadence | Used by |
|-----|------|-------------|------------------|---------|
| `revenue_usd` | float | RevenueSpine (`dharma_swarm/revenue/spine.py`) | per-event | spinout, kill |
| `burn_usd` | float | TreasuryNoticer (new, see `SHAKTI_GINKO_ORGAN.md` §6.4) | hourly | spinout, kill |
| `days_active` | int | system | nightly | kill |
| `days_since_last_packet` | int | TaskBoard | nightly | kill |
| `agent_count` | int | RoomBridge | on-mutation | kill |
| `budget_ratio` | float | TreasuryNoticer | hourly | kill |
| `welfare_tons` | float | OutcomeJudge | weekly | kill (negative), Jagat Kalyan |
| `paying_customers` | int | RevenueSpine | per-event | spinout |
| `monthly_revenue_gt_burn_months` | int | TreasuryNoticer | monthly | spinout |
| `autonomy_stage` | int | orchestrator | on-advance | spinout (stage 5 gate) |
| `operator_kill` | bool | operator | on-demand | kill (override) |
| `operator_approved_graduation` | bool | operator | on-demand | spinout |

### 4.2 Domain-specific KPIs

For trading-lab cells, KPIs additionally include `brier_score`, `resolved_predictions`, `win_rate`, `sharpe_ratio`, `max_drawdown`. For research cells, e.g., `published_findings`, `peer_review_score`. The `kpis` dict is intentionally untyped (PropertyType.DICT) so domain extension is non-breaking.

### 4.3 Computation rules

- **Notice-only.** KPI computation is performed by noticers. A noticer reads BoardStore, computes, writes back via a mutation. Noticers never mutate via raw SQL.
- **Idempotent.** Each KPI update carries a `(cell_id, kpi_name, computed_at, source_noticer)` tuple. Re-running a noticer produces identical results.
- **Deterministic.** v1 KPIs are explicit formulas. No learned aggregation. (See `SHAKTI_GINKO_ORGAN.md` §6.6 — no learned ranking in v1.)
- **Audited.** Every KPI mutation emits a `WitnessEvent` to the witness ledger.

### 4.4 KPI lag and freshness

Cells display freshness on the operator brief: `kpi.last_updated` per KPI. If any kill-condition input is older than 24 h, the cell shows a `STALE_KPI` warning and the kill evaluator returns `unknown` (not `False`). Operator must refresh or kill manually — a stale cell does not get to skip the gate by lying.

---

## 5. Autonomy Gates and the ARJUNA Directive

> *"Every build must measurably advance Jagat Kalyan, not be meta-tooling."*

The ARJUNA gate is the cross-cutting constraint over all lifecycle transitions. Concretely:

1. **At cell creation,** the `jagat_kalyan_constraint` field must be non-empty and reviewed by the operator. If empty, the cell is rejected before reaching PROPOSED.
2. **At autonomy advance,** the cell must produce evidence of `welfare_tons_produced > 0` since last advance. (Stage 1 → 2 is exempt because welfare measurement starts at stage 2.)
3. **At spinout,** the cell must show three months of positive `welfare_tons_produced`.
4. **At kill,** archival snapshots include the welfare ledger so future cells can learn from the dissolution.

The ARJUNA gate is enforced by `OutcomeJudge` (existing) and `WelfareGate` (new — wraps OutcomeJudge into a callable for advance/spinout transitions). WelfareGate ships in the Phase 2 migration PR.

---

## 6. Kill Criteria

Kill conditions are **OR-semantic**: if any single condition evaluates True, the cell is killed. The default kill set for new cells is conservative and lives at `SHAKTI_GINKO_ORGAN.md §8.4`. Reproduced here for completeness:

```python
DEFAULT_KILL_CONDITIONS = [
    "no_revenue_after_60_days",     # exception: stage 1 research cells
    "burn_exceeds_3x_revenue",
    "budget_exceeded",              # budget_ratio > 1.2
    "no_work_packets_30_days",
    "zero_agents_assigned",
    "welfare_tons_negative",
    "operator_override",
]
```

### 6.1 Per-condition semantics

All evaluators are pure functions in `fractal_room.py:248-275`. Operator may add custom conditions; the registry `_KILL_CONDITION_EVALUATORS` supports extension via simple module-level dict update.

| Condition | Evaluates | Threshold | Note |
|-----------|-----------|-----------|------|
| `no_revenue_after_60_days` | `revenue_usd == 0 AND days_active > 60` | hard | exempt for stage-1 research cells |
| `burn_exceeds_3x_revenue` | `burn_usd > 3 * max(revenue_usd, 0.01)` | hard | tightens at stage ≥ 3 |
| `budget_exceeded` | `budget_ratio > 1.2` | hard | always |
| `no_work_packets_30_days` | `days_since_last_packet > 30` | soft | gives operator option to revive |
| `zero_agents_assigned` | `agent_count == 0` | soft | starvation kill |
| `welfare_tons_negative` | `welfare_tons < 0` | hard | ARJUNA violation, immediate |
| `operator_override` | `operator_kill == True` | hard | manual kill switch |

**Hard vs soft:** hard conditions trigger automatic archival within 24 h of detection (the operator gets one explicit confirm). Soft conditions raise a warning card for operator decision.

### 6.2 Per-cell customization

Cells may override the default set by writing to their `kill_conditions: list[str]` field at creation time. Operator approval required for any deviation that *removes* a hard condition. *Adding* conditions is unilateral.

The Revenue Wedge cell already declares `kill_conditions` at `docs/governance/VENTURE_CELL_REVENUE_WEDGE.md`. New cells inherit `DEFAULT_KILL_CONDITIONS` unless explicitly overridden.

### 6.3 Kill execution

When `evaluate_kill_conditions` returns True:

1. **Emit** `SIGNAL_ROOM_KILL_CONDITION_MET` (already defined at `fractal_room.py:86`).
2. **Operator notification** card auto-created on TaskBoard, ARJUNA-weighted high, 24 h response window.
3. **Auto-archival** at 24 h unless operator dismisses.
4. **Snapshot** the cell subtree (cards, artifacts, recent WitnessEvents) to `~/.dharma/cell_archives/<cell_id>.tar.zst` before status flip.
5. **Flip** `status = ARCHIVED`, unassign agents (move agents to free pool).
6. **WitnessEvent** logged with reason and evaluator output.
7. **Roster reclaim** — agents become available for other cells.

### 6.4 Kill regret window

Operator may unarchive within 7 days via `unarchive_venture_cell <cell_id>` (BoardStore CLI). After 7 days, unarchival requires a manual ADR PR and operator sign-off. This is REVERSIBILITY at work.

---

## 7. Spinout Criteria

Spinout conditions are **AND-semantic**: all must be True. Defaults at `SHAKTI_GINKO_ORGAN.md §8.5`:

```python
DEFAULT_SPINOUT_CONDITIONS = [
    "revenue_exceeds_burn",      # 3 consecutive months
    "3_paying_customers",
    "autonomy_stage_5",
    "operator_approval",
]
```

All evaluators at `fractal_room.py:277-303`.

### 7.1 Spinout procedure

1. **Detect** via `evaluate_spinout_conditions(cell.spinout_conditions, cell.kpis)` — auto-runs nightly.
2. **Emit** `SIGNAL_ROOM_SPINOUT_CONDITION_MET`.
3. **Card** appears on operator TaskBoard with ARJUNA priority.
4. **Operator approval** required — no automatic spinout, ever.
5. **Status** → `DIVESTING`.
6. **Snapshot** subtree (see §2.2).
7. **Externalize** — cell metadata gains `spun_out_to: <entity>` field with URI/repo/contact.
8. **Status** → `ARCHIVED` once externalization complete.
9. **Treasury** transfers remaining budget per operator instruction (back to organ, or to spinout, or split).

### 7.2 Spinout vs maturity

Not every mature cell spins out. A MATURE cell that produces ongoing welfare for Jagat Kalyan without commercial pressure (e.g., a community cell) stays in the organ indefinitely. Spinout is for cells that have outgrown the organ's governance frame and benefit from their own legal/economic entity.

---

## 8. Roster and Budget

### 8.1 Roster (S1 — operations)

Each cell declares an `agents: list[str]` plus `agent_authorities: dict[str, str]`. Roster invariants:

- **Min roster:** ≥ 1 agent to leave PROPOSED.
- **Authority bounds:** each entry in `agent_authorities` lists what the agent may modify (e.g., `"codex": "code,docs"`). Authority cannot exceed the cell's `allowed_work`.
- **Trust separation:** an agent assigned to cell A cannot read cell B's private artifacts unless explicitly federated. Federation is recorded on the federation graph (BoardStore.federation_edges).
- **Heterogeneous trust:** different agents (Claude Code, Codex, Cursor, Devin, Warp, Perplexity) have different default authorities. Defaults live in `dharma_swarm/agent_registry.py`.

### 8.2 Budget (S3 — control / economy)

- `budget_tokens: int` — token allocation (LLM tokens, normalized).
- `current_burn: int` — running burn.
- `revenue_target: int` — fiat goal (USD cents).
- `remaining_budget()` method already at `fractal_room.py:152-153`.

Budget flow:

1. Organ Treasury allocates `budget_tokens` at cell creation.
2. Each action that consumes tokens charges via `TreasuryNoticer.charge(cell_id, tokens)`.
3. At `budget_ratio > 1.0` (overrun), TreasuryNoticer warns.
4. At `budget_ratio > 1.2`, `budget_exceeded` kill condition triggers.
5. Treasury can mint additional budget via operator ADR.

### 8.3 Welfare ledger

`welfare_tons_produced` is the cell's running tally of measurable Jagat Kalyan contributions. Units are deliberately fuzzy ("tons") — the goal is to force operator and OutcomeJudge to negotiate what counts. Initial scoring rubric lives at `docs/governance/WELFARE_TONS_RUBRIC.md` (to be authored — Phase 3 PR).

---

## 9. Lifecycle Events on the Signal Bus

All cell transitions emit signals. Signal names align with existing constants in `fractal_room.py:80-89` and are extended for VentureCell-specific events:

```python
# Existing (fractal_room.py)
SIGNAL_ROOM_CREATED
SIGNAL_ROOM_ARCHIVED
SIGNAL_ROOM_SPAWNED_CHILD
SIGNAL_ROOM_KILL_CONDITION_MET
SIGNAL_ROOM_SPINOUT_CONDITION_MET
SIGNAL_ROOM_BUDGET_DEPLETED
SIGNAL_WORK_PACKET_CREATED
SIGNAL_WORK_PACKET_COMPLETED
SIGNAL_YDS_RATING_ADDED

# New (this spec)
SIGNAL_VENTURE_CELL_PROPOSED
SIGNAL_VENTURE_CELL_INCUBATING
SIGNAL_VENTURE_CELL_ACTIVATED
SIGNAL_VENTURE_CELL_MATURED
SIGNAL_VENTURE_CELL_AUTONOMY_ADVANCED
SIGNAL_VENTURE_CELL_AUTONOMY_DOWNGRADED
SIGNAL_VENTURE_CELL_KILL_RECOMMENDED      # soft, from QualityNoticer
SIGNAL_VENTURE_CELL_SPINOUT_RECOMMENDED   # soft, from OpportunityNoticer
SIGNAL_VENTURE_CELL_TREASURY_WARNING      # from TreasuryNoticer
```

Subscribers:

- **OperatorBriefBuilder** — for the morning brief card.
- **WitnessLedger** — for audit.
- **OutcomeJudge** — for welfare attribution.
- **NoticerScheduler** — to trigger re-evaluation.

---

## 10. Operator Surface

The operator interacts with cell lifecycle through three surfaces:

1. **Morning brief** — `dharma_swarm/operator_brief/` produces a daily card list. Each cell appears with status, stage, KPI snapshot, recommended actions.
2. **TaskBoard** — kanban-style view of cards. Cell lifecycle events appear as cards (e.g., "Approve incubation of vault-mirror cell").
3. **CLI** — `dharma cell create|advance|kill|spinout|snapshot|unarchive` (to be authored — Phase 1 migration PR §11).

Operator never has to touch the database. All actions go through BoardStore facade with RBAC + telos checks.

---

## 11. Worked Example: the Revenue Wedge Cell

The cell already declared at `docs/governance/VENTURE_CELL_REVENUE_WEDGE.md`:

```yaml
cell_id: revenue-wedge
status: incubating               # at declaration time
autonomy_stage: 1
budget_tokens: 50000             # $50k token equivalent
revenue_target: 1000000          # $10k in USD cents
customer_or_beneficiary: "agentic-code-governance teams"
value_proposition: "guided agent governance sprint"
self_funding_hypothesis: "outreach → discovery call → $5k sprint, 2 in 60 days"
first_revenue_proof: "first $5k signed agreement"
kill_conditions:
  - no_revenue_after_60_days
  - burn_exceeds_3x_revenue
  - operator_override
spinout_conditions:
  - revenue_exceeds_burn
  - 3_paying_customers
  - autonomy_stage_5
  - operator_approval
jagat_kalyan_constraint: "no spam; outreach must include verifiable governance value upfront"
```

Lifecycle so far:

1. **PROPOSED** — declared in markdown by operator.
2. **INCUBATING** — current state (research-only, no live capital).
3. **ACTIVE (stage 2)** — pending: requires first outreach draft + ViabilityNoticer green.
4. **kill watch** — at day 30: TaskBoard auto-creates card "Revenue Wedge at day 30 of 60 with $0 revenue — review hypothesis".

---

## 12. Invariants the Substrate Must Enforce

These are the non-negotiable invariants the BoardStore facade (Codex's `SWARM_BOARDSTORE_SPEC.md`) must enforce on every cell mutation:

1. **Telos gates green** on every transition.
2. **Audit trail** — every mutation writes a WitnessEvent.
3. **Reversibility** — destructive transitions snapshot first.
4. **Idempotent retries** — retrying a transition is a no-op if already in target state.
5. **No-fly zones** — agents cannot mutate cells they're not assigned to, period.
6. **Operator final say** — kill/spinout/stage-4-up always operator-confirmable.
7. **ARJUNA enforced at three points** — creation, advance, spinout.
8. **Single status enum** — `VentureCellStatus` is the single source of truth (after Phase 1 unification).

---

## 13. Open Questions

These are explicit operator decisions that this spec does not pre-commit:

1. **Auto-advance threshold.** Default arjuna_weight ≥ 0.7 for stages 1 → 2 → 3. Should it be lower for trading-lab cells where the gates already provide guardrails?
2. **Snapshot retention.** Default ARCHIVED snapshots kept indefinitely. Should the operator be able to GC after N years?
3. **Welfare tons unit.** Concrete rubric is deferred to `WELFARE_TONS_RUBRIC.md`. What's the v1 anchor — operator gut-feel, GiveWell-style cost-per-DALY, repository PRs merged, dollars donated downstream?
4. **Cross-cell budget transfer.** Should Treasury allow operator to move budget from a high-burn / low-welfare cell to a starving cell *without* killing the first? Or is kill-then-reallocate the only path?
5. **Spinout templates.** When a cell spins out, what's the externalization template — new repo, new entity, license to existing entity? Probably cell-specific, but a default would help.
6. **Heterogeneous-agent default authorities.** Defaults for Claude Code, Codex, Cursor, Devin, Warp, Perplexity must live in `agent_registry.py`. First-cut proposal in `SHAKTI_GINKO_ORGAN.md §9`.

---

## Appendix — File:Line Citation Index

- `dharma_swarm/ontology.py:1470-1507` — VentureCell ontology object
- `dharma_swarm/ontology.py:1480-1488` — properties (autonomy_stage, status, budget_tokens, kpis)
- `dharma_swarm/ontology.py:1491-1496` — Create + Advance actions with telos gates
- `dharma_swarm/fractal/fractal_room.py:60-69` — RoomStatus enum
- `dharma_swarm/fractal/fractal_room.py:80-89` — Signal bus event types
- `dharma_swarm/fractal/fractal_room.py:99-160` — FractalRoom dataclass (VSM-mapped)
- `dharma_swarm/fractal/fractal_room.py:163-200` — VentureCellV1 dataclass
- `dharma_swarm/fractal/fractal_room.py:248-275` — `_KILL_CONDITION_EVALUATORS`
- `dharma_swarm/fractal/fractal_room.py:277-303` — `_SPINOUT_CONDITION_EVALUATORS`
- `dharma_swarm/fractal/fractal_room.py:305-317` — `evaluate_kill_conditions`, `evaluate_spinout_conditions`
- `dharma_swarm/ginko_orchestrator.py:826-849` — `AUTONOMY_REQUIREMENTS` table
- `dharma_swarm/ginko_orchestrator.py:853-892` — `check_autonomy_advancement`
- `docs/governance/VENTURE_CELL_REVENUE_WEDGE.md` — first declared VentureCell
- `docs/architecture/SHAKTI_GINKO_ORGAN.md` — companion spec (organ shape, migration, noticer roster)
- `docs/architecture/BUSINESS_INTELLIGENCE_NOTICERS.md` — companion spec (noticer details)
