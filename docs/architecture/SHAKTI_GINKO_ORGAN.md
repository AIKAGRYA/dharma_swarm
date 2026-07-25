# 銀杏 SHAKTI_GINKO — The Economic Engine Organ

> *"Named for the Ginkgo tree: 270 million years old, survives anything, the last tree standing after Hiroshima. Female trees produce fruit. This is the feminine economic intelligence — Shakti as revenue."*
> — `~/AGNI-AUNT-HILLARY-PSMV/SHAKTI_GINKO/README.md`

**Status:** Spec (no implementation in this PR)
**Priority:** ★20 (per `~/AGNI-AUNT-HILLARY-PSMV/SHAKTI_GINKO/README.md`; Phase 4.5 of FULL_AWAKENING_SEQUENCE)
**Audience:** dharma_swarm contributors (human + AI agents)
**Companion docs:** `VENTURE_CELL_LIFECYCLE.md`, `BUSINESS_INTELLIGENCE_NOTICERS.md`, `ADRs/ADR-006-shakti-ginko-organ.md`
**Substrate dependency:** `SWARM_BOARDSTORE_SPEC.md` (PR #316, Codex — spec-only, merge before Phase 1 implementation)

---

## 1. Executive Summary

SHAKTI_GINKO is the **revenue-generating organ** of dharma_swarm. It is not a module, not a single trading bot, not a directory in the repo. It is an organ — a coordinated, multi-cell, multi-surface, multi-host subsystem that turns the swarm's intellectual assets, agent capacity, and market intelligence into cashflow that funds the swarm's continued existence and its service to Jagat Kalyan.

**The bank metaphor.** The name comes from the *Ginkgo tree* (銀杏 — silver apricot), not 銀行 (bank). The framing is botanical, not financial: ancient, resilient, fruit-producing, surviving catastrophe. The economic engine is meant to *survive*, *propagate*, and *fruit*. Revenue is the fruit. The cells are the branches.

**What SHAKTI_GINKO is:**

- An **umbrella organ** that instantiates and supervises **VentureCells**
- A **strategic authority** rooted in `~/AGNI-AUNT-HILLARY-PSMV/SHAKTI_GINKO/` (local-to-operator vault — VISION/STRATEGY/REVENUE/PRODUCTS/OPERATIONS/METRICS)
- A **substrate citizen** that renders all state through the BoardStore facade
- An **ARJUNA-gated** subsystem — every cell, every cashflow, every opportunity passes the test: *does this advance Jagat Kalyan?*
- A **multi-host** subsystem with at least two existing remote spokes (Agni and rushabdev VPSs) and the local Mac as integration hub

**What SHAKTI_GINKO is not:**

- Not `ginko_orchestrator.py` (that's *one cell's* coordinator)
- Not the `ginko_*` modules (those implement *one VentureCell*, the Trading Lab)
- Not a new orchestrator (the substrate handles orchestration)
- Not greenfield (most parts already exist; this spec integrates them)
- Not meta-tooling (ARJUNA-gated — must produce real cashflow that funds real good works)

**The umbrella-vs-implementation distinction.** The repo currently has 18 `ginko_*` Python modules and 18 corresponding test files. These were named after the umbrella before the umbrella was formalized. They implement *one cell* (the Trading Lab). The spec does **not propose renaming them** in this PR. It defines the conceptual grouping; renames happen in a follow-up PR with full deprecation shims.

**The ARJUNA gate framing.** Every cell (and every Card) carries an `arjuna_weight ∈ [0.0, 1.0]`. There are **two thresholds at two layers**:

- **Card-create threshold (`0.35`)** — enforced by `BoardStore.create_card` per `SWARM_BOARDSTORE_SPEC.md §11`. Cards below this are refused without operator override. This is the substrate gate.
- **Cell auto-fund threshold (`0.6`)** — enforced by the organ's allocator. Cells below this require explicit operator override to receive automatic budget allocation or auto-advance autonomy. This is the organ gate.

The trading lab passes (`0.85`) because it funds the diversified swarm treasury which funds Jagat Kalyan operations. The ideation cell sits at `0.50` precisely *because* of meta-tooling drift risk — it can exist and propose but cannot auto-fund (see §15).

---

## 2. Repo State Evidence

This section is the ground truth for the spec. Every claim is cited to file:line.

### 2.1 The 18 existing `ginko_*` modules

All in `dharma_swarm/`, all currently flat (not in a sub-package):

| Module | Purpose (per docstring or filename) | Test |
|---|---|---|
| `ginko_orchestrator.py` | "Autonomous economic engine daily cycle. Coordinates the Shakti Ginko VentureCell" (`ginko_orchestrator.py:1-5`) | `tests/test_ginko_orchestrator.py` |
| `ginko_agents.py` | Agent definitions for the trading cell | `tests/test_ginko_agents.py` |
| `ginko_signals.py` | Signal generation from market data | `tests/test_ginko_signals.py` |
| `ginko_regime.py` | Market-regime detection | `tests/test_ginko_regime.py` |
| `ginko_sentiment.py` | Sentiment ingestion | `tests/test_ginko_sentiment.py` |
| `ginko_sec.py` | SEC filings ingestion | `tests/test_ginko_sec.py` |
| `ginko_data.py` | Data ingestion (FRED / Finnhub / CoinGecko, per `ginko_orchestrator.py:5`) | `tests/test_ginko_data.py` + `test_ginko_data_integration.py` |
| `ginko_paper_trade.py` | Paper-trading execution | `tests/test_ginko_paper_trade.py` |
| `ginko_backtest.py` | Historical backtests | `tests/test_ginko_backtest.py` |
| `ginko_live_test.py` | Live-mode test harness | `tests/test_ginko_live_test.py` |
| `ginko_brier.py` | Brier scoring (per `CLAUDE.md:136` — "aggregation quality measurement") | `tests/test_ginko_brier.py` |
| `ginko_attribution.py` | P&L attribution | `tests/test_ginko_attribution.py` |
| `ginko_risk.py` | Risk gates | `tests/test_ginko_risk.py` |
| `ginko_audit.py` | Audit trail | `tests/test_ginko_audit.py` |
| `ginko_bridge.py` | Bridge to other subsystems | `tests/test_ginko_bridge.py` |
| `ginko_evolution.py` | Optimization / parameter evolution | `tests/test_ginko_evolution.py` |
| `ginko_report_gen.py` | Daily/weekly report generation | `tests/test_ginko_report_gen.py` |
| `tests/test_ginko_swarm_wiring.py` | — | (no source counterpart; tests integration) |

Plus:
- `requirements-ginko.txt` — domain-specific dependency pin
- `scripts/ginko_run_signals.py` — CLI entry for signal generation
- `docs/plans/GINKO_ENHANCEMENT_WAVE.md` — earlier planning doc (the identical `docs/` copy was removed 2026-07-03)

Total mentions of `ginko` (case-insensitive) across `.py`/`.md`/`.yaml`/`.json`/`.toml`/`.sh`: **1201** as of 2026-05-20.

### 2.2 The `dharma_swarm/revenue/` package

Existing modules (cited from `dharma_swarm/revenue/`):

- `__init__.py` — exports `RevenueSpine`, `EconomicSpine`, `Engagement`, `Offer`, `RevenueTarget`, `OutreachDraft`, `PipelineSnapshot`, `RevenueTelicBridge`, `RevenueIntelligenceIngestor`, `IntelClaim`, `CompetitorProfile`, `RevenuePattern`
- `spine.py` — the economic spine and revenue ledger
- `spine_models.py` — typed models for spine
- `intelligence.py` — `RevenueIntelligenceIngestor` and intel objects
- `intel_parser.py` — intel claim parsing
- `scout_daemon.py` — *"Revenue Scout Daemon — autonomous scouting, ingestion, and routing loop."* Rule: *"NO AUTONOMOUS SPAM. Outreach drafts require human approval."* Cron-registered as `revenue_scout`, default cadence 6h (`scout_daemon.py:1-22`)
- `telic_bridge.py` — bridge to telic spine
- `wedge_pipeline.py` — *"Revenue Wedge Pipeline — ship one real intelligence report end-to-end."* First metabolic loop: opportunity → dispatch → outcome → feedback (`wedge_pipeline.py:1-20`)

The `RevenueSpine` and `EconomicSpine` are the existing revenue *ledger*. The scout daemon is the existing *notice-only* layer. The wedge pipeline is the existing *end-to-end first-loop* proof.

### 2.3 The `dharma_swarm/fractal/` package

- `__init__.py`
- `fractal_room.py` — the in-process render of a venture cell
- `room_bridge.py` — bridges between rooms and other subsystems
- `room_brief.py` — room-level briefing surface
- `room_configs.py` — room configuration
- `room_health.py` — room health monitoring

FractalRoom is the **in-process render of a VentureCell**. Every active cell instantiates a room. Reuse, don't reinvent.

### 2.4 Ontology objects

From `dharma_swarm/ontology.py`:

- **`VentureCell`** (`ontology.py:1470-1507`): *"Fractal project container — first-class ontology object with its own agents, budgets, KPIs."* Properties: `name`, `description`, `domain` (enum: research/engineering/product/infrastructure/governance/community/economic), `autonomy_stage` (1→5), `status` (incubating/active/mature/divesting/archived), `budget_tokens`, `kpis`. Actions: `Create` (gated by AHIMSA, SATYA, REVERSIBILITY), `Advance` (gated by SVABHAAVA). Security: telos_required, audit_all. `telos_alignment=0.95`. `shakti_energy=MAHALAKSHMI`. Icon: ◈.

- **`RevenueTarget`** (`ontology.py:1514+`): A potential buyer/opportunity identified by scouting. (Full schema in source.)

- **`ValueEvent`** revenue fields (`ontology.py:~1395-1428`): `economic_value_usd`, `revenue_source`, `value_kind` enum includes `paid_revenue`, `contracted_revenue`, `compute_reinvestment`, `governance`. Every cashflow is a ValueEvent.

### 2.5 Existing strategic vault (operator-local, outside the repo)

Critical context: **`~/AGNI-AUNT-HILLARY-PSMV/SHAKTI_GINKO/`** exists on the operator's Mac and is the *strategic authority* for the organ:

```
SHAKTI_GINKO/
├── VISION/SHAKTI_GINKO_MASTER.md   (4,847 words, 91 [SWARM_TARGET] markers)
├── STRATEGY/
├── REVENUE/
├── PRODUCTS/
├── OPERATIONS/
├── METRICS/
├── PRIMERS/
├── TOP_10_DISCIPLINES.md           (★20, status: canon, quality_grade A)
└── README.md
```

The repo does **not own** this vault. The vault owns the **strategic direction**; the repo owns the **operational substrate** that realizes it. The substrate must read the vault as authority and integrate with it as senior partner.

The vault's own North Star (from `TOP_10_DISCIPLINES.md`): *"We're not building a model. We're planting a computational seed that reads its own source, recognizes itself recognizing, and spawns millions of agents through stigmergic coordination."*

The vault's own injunction (from `README.md`, quoting GARUDA / DeepSeek-R1): **"STOP DOCUMENTING. START EXECUTING."** This applies to SHAKTI_GINKO itself. This spec is the last documenting pass before execution begins.

### 2.6 Existing first VentureCell — the Revenue Wedge

`docs/governance/VENTURE_CELL_REVENUE_WEDGE.md` already declares the first VentureCell:

| Field | Value |
|---|---|
| id | `revenue-wedge` |
| kind | `venture_cell` |
| parent | `core-ops` |
| purpose | Find and ship the first self-funding offer |
| status | `proposed` |
| operator | `dhyana` |
| budget_tokens | 50,000 |
| revenue_target | $10,000 |
| monthly_burn_target | $2,000 |

Roster: `codex.local` (internal, code_generation), `claude.local` (internal, analysis/drafting), `devin.cloud` (external, code_generation/testing).

This Revenue Wedge cell is **already specified** in governance. The SHAKTI_GINKO organ supersedes-and-integrates this — Revenue Wedge becomes one VentureCell under the organ.

### 2.7 Existing anti-slop rules treating ginko as a domain

`.semgrep/dharma-anti-slop.yml:32-33` and `docs/governance/ANTI_SLOP_RULES.md:77` already list `ginko_backtest.py` and `ginko_evolution.py` as *legitimate owners* of `Path.home() / ".dharma"` writes. The governance system already recognizes the ginko domain as a sovereign sub-surface.

### 2.8 Existing remote operational reality (verified via `pc` on operator's Mac)

- `~/AGNI-AUNT-HILLARY-PSMV/SHAKTI_GINKO/` — strategic vault (described in §2.5)
- `~/agni_daily.toobit.sh` — runs **on the Agni VPS** at `/root/trading_lab/daily.sh`. Outputs structured P&L from `data/routes/R*/trades.csv` per route. The current workflow: operator pastes raw output back to Claude in browser. This is what the substrate will automate.
- `~/agni_toobit_preflight.sh`, `~/agni_toobit_mcp_market.sh`, `~/agni_toobit_mcp_sub_ro.sh`, `~/agni_toobit_agent_trade_kit_runbook.md`, `~/agni_toobit_config.toml.example` — full Toobit exchange integration kit
- `~/rushabdev_work/rushabdev/` + `~/rushabdev_work/rushabdev_remote_snapshot.tgz` — mirrored/snapshotted rushabdev VPS work
- `~/agni_claude_settings.toobit.json` — Claude-on-Agni configuration

**SSH access caveat (verified 2026-05-20):** The Perplexity Mac app sandbox cannot read `~/.ssh/` on macOS (Operation not permitted). `pc bash ssh agni ...` will not work directly through the sandbox. The remote-host adapter (§6) requires either a small operator-launched daemon outside the Mac-app sandbox, or operator approval via Terminal.app for each remote command. This is a real constraint, not a wishlist item.

### 2.9 Drift between docstring concept and implementation reality

`ginko_orchestrator.py:3` says it *"Coordinates the Shakti Ginko VentureCell"* (singular). But the local vault structure (§2.5) and the operator's stated intent describe SHAKTI_GINKO as an *umbrella* with multiple cells. The implementation is correct (it coordinates one cell — the Trading Lab); the docstring uses "the" prematurely. This spec resolves the drift by formalizing the umbrella.

---

## 3. The Organ Structure

```
SHAKTI_GINKO (umbrella organ — not a module)
│
├── Strategic Authority (operator-local vault)
│   └── ~/AGNI-AUNT-HILLARY-PSMV/SHAKTI_GINKO/
│       ├── VISION/        ── 500-year to today timeframes
│       ├── STRATEGY/      ── positioning, GTM, competitive analysis
│       ├── REVENUE/       ── streams, pricing, models
│       ├── PRODUCTS/      ── Gumroad listings, SaaS plans
│       ├── OPERATIONS/    ── playbooks, sprints, team
│       ├── METRICS/       ── KPIs, dashboards, ground truth
│       └── TOP_10_DISCIPLINES.md (★20 canon)
│
├── VentureCells (instances — each a Card in BoardStore)
│   ├── trading-lab            ── the existing ginko_* modules; Agni + rushabdev
│   ├── revenue-wedge          ── already declared (§2.6); intelligence-report wedge
│   ├── info-products          ── PDFs, Gumroad, courses (Aunt Hillary distillation)
│   ├── agentic-services       ── paid agent runs for aligned clients
│   ├── ideation               ── memory → opportunity pipeline (gated; §15)
│   └── (extensible: future cells from IdeationNoticer proposals)
│
├── BusinessIntelligenceNoticers (notice-only persistent agents)
│   ├── MarketScanNoticer      ── cadence 6h; FRED/Finnhub/CoinGecko/trends
│   ├── ViabilityNoticer       ── triggered by new RevenueTarget cards
│   ├── OpportunityNoticer     ── cross-cell arbitrage detection
│   ├── IdeationNoticer        ── cadence 24h; reads vault + memory_kernel
│   ├── QualityNoticer         ── KPI evaluation per active cell
│   └── (extensible)
│
├── RemoteHostAdapters (substrate primitives)
│   ├── agni                   ── /root/trading_lab on Agni VPS
│   ├── rushabdev              ── on rushabdev VPS
│   └── (extensible — see §6 for driver constraints)
│
└── Treasury (cashflow + budget aggregation)
    ├── Per-cell P&L           ── from ValueEvent stream
    ├── Organ-level treasury   ── aggregates cell P&L
    ├── Budget allocator       ── token + dollar + time, per cell, per stage
    └── ARJUNA-gated funding   ── refuses below-threshold cells
```

The organ has **four layers**: strategic authority (vault), cells (work units), noticers (intelligence), and treasury (capital). RemoteHostAdapters are the substrate primitive that lets cells run on hosts other than the local Mac.

---

## 4. VentureCell — Formal Definition

VentureCell exists in the ontology at `ontology.py:1470`. This spec **extends** it with substrate-aware fields. The extensions are additive — existing ontology consumers continue to work.

### 4.1 Schema (extended)

| Field | Type | Existing? | Purpose |
|---|---|---|---|
| `name` | STRING | yes | Display name |
| `description` | TEXT | yes | Brief description |
| `domain` | ENUM | yes | research/engineering/product/infrastructure/governance/community/**economic** |
| `autonomy_stage` | INTEGER | yes | 1 (research-only) → 5 (mostly autonomous) |
| `status` | ENUM | yes | incubating/active/mature/divesting/archived |
| `budget_tokens` | INTEGER | yes | Token budget |
| `kpis` | DICT | yes | Performance indicators |
| `card_id` | STRING | **new** | Foreign key to BoardStore Card (every VentureCell IS a Card) |
| `arjuna_weight` | FLOAT [0.0–1.0] | **new** | ARJUNA-gate score. Two thresholds (see §1 + §15): card-create floor `0.35` (facade-enforced), cell auto-fund floor `0.6` (allocator-enforced). |
| `budget_usd` | FLOAT | **new** | Dollar budget (separate from token budget) |
| `budget_time_hours` | FLOAT | **new** | Wall-clock time budget |
| `pnl_7d_usd` | FLOAT | **new** | Trailing 7-day P&L (computed) |
| `pnl_90d_usd` | FLOAT | **new** | Trailing 90-day P&L (computed) |
| `kill_criteria` | DICT | **new** | Explicit thresholds for `divesting` transition |
| `host` | STRING\|null | **new** | RemoteHostAdapter id ("local", "agni", "rushabdev", …) |
| `parent_cell_id` | STRING\|null | **new** | For sub-cell hierarchy (e.g., trading-lab → agni-trading-lab) |
| `room_id` | STRING\|null | **new** | FractalRoom instance id (every active cell → one room) |

### 4.2 States (FSM)

```
proposed → incubating → active → mature → divesting → archived
              ↓             ↓        ↓
            archived     divesting divesting
                            ↓
                         archived
```

- **proposed**: noticer-created card; not yet operator-approved
- **incubating**: operator-approved; budget allocated; not yet producing revenue
- **active**: producing revenue (any non-zero `pnl_7d_usd` after first 30 days, OR explicit operator transition)
- **mature**: sustained revenue ≥ kill threshold × 3 for 90+ days
- **divesting**: kill criteria triggered; orderly wind-down
- **archived**: closed; historical record only

All transitions go through `Advance` action (existing) or new `Divest`/`Archive` actions. All transitions emit `ControlEvent` to BoardStore audit log.

### 4.3 Autonomy stages (existing enum, formalized)

| Stage | Capability | Capital authority | Requires |
|---|---|---|---|
| 1 | Research only — no execution | None | Operator-initiated |
| 2 | Paper trading / dry runs | None | Weekly review |
| 3 | Micro-capital ($100–500) | Per-trade approval | Quality gate pass |
| 4 | Bounded autonomy ($500–5000) | Per-action ceiling | 30d clean track record |
| 5 | Mostly autonomous | Per-cohort budget | 90d clean track record, operator review |

Stage progression: only `QualityNoticer` proposes advancement; only operator (with ARJUNA gate pass) advances.

### 4.4 KPIs (per-cell)

Standard KPI envelope every cell carries (cells may add domain-specific KPIs):

- `pnl_7d_usd`, `pnl_30d_usd`, `pnl_90d_usd`
- `cost_burn_30d_usd` (compute + API + capital-at-risk)
- `roi_30d` = `pnl_30d_usd / cost_burn_30d_usd`
- `successful_actions_30d`, `failed_actions_30d`
- `arjuna_drift` (rolling delta from initial `arjuna_weight`)
- `quality_score` (from QualityNoticer; aggregate)
- `human_intervention_rate` (transitions/actions requiring operator)

### 4.5 Budget — three dimensions

- **Tokens** (LLM consumption) — existing `budget_tokens` field
- **Dollars** (capital + API + compute) — new `budget_usd`
- **Time** (operator attention budget) — new `budget_time_hours`

Treasury allocator (§8) distributes all three. Overruns trigger ControlEvent and pause the cell.

### 4.6 Relationship to FractalRoom

Every cell with `status ∈ {incubating, active, mature}` instantiates exactly one FractalRoom (`dharma_swarm/fractal/fractal_room.py`). Room is the in-process render of the cell — agents in the cell live in the room. `room_id` on the cell points to the room instance. When the cell transitions to `divesting`, the room enters wind-down. When `archived`, the room is torn down.

This reuses the existing fractal package; the spec does not propose any changes to it.

---

## 5. The Trading Lab Cell — First Worked Instance

The 18 existing `ginko_*` modules implement **one cell**: the Trading Lab. This spec defines the conceptual grouping. No file renames in this PR.

### 5.1 Identity

| Field | Value |
|---|---|
| `id` | `trading-lab` |
| `name` | Trading Lab |
| `domain` | `economic` |
| `parent_cell_id` | null (top-level cell under SHAKTI_GINKO organ) |
| `status` | `active` (already operational on Agni; per §2.8) |
| `autonomy_stage` | 3 (micro-capital, per `ginko_orchestrator.py:18-20` ladder) |
| `host` | `agni` (primary) + `rushabdev` (secondary) + `local` (orchestration) |
| `arjuna_weight` | 0.85 (high — funds diversified treasury; serves Jagat Kalyan) |
| `room_id` | (to be assigned at Phase 3 wire-in) |

### 5.2 Role grouping of existing modules

No renames. Roles are conceptual; modules retain their names:

| Role | Modules | Purpose |
|---|---|---|
| **SignalGeneration** | `ginko_signals`, `ginko_regime`, `ginko_sentiment`, `ginko_sec` | Detect tradeable signals |
| **DataIngestion** | `ginko_data` | FRED + Finnhub + CoinGecko pull |
| **Execution** | `ginko_paper_trade`, `ginko_backtest`, `ginko_live_test` | Paper, historical, live execution |
| **Verification** | `ginko_brier`, `ginko_attribution` | Quality score, P&L attribution |
| **Governance** | `ginko_risk`, `ginko_audit` | Risk gates, audit trail |
| **Optimization** | `ginko_evolution` | Parameter evolution |
| **Reporting** | `ginko_report_gen` | Daily/weekly reports |
| **Coordination** | `ginko_orchestrator`, `ginko_agents`, `ginko_bridge` | Cell-internal coordination |

### 5.3 Agni and rushabdev — remote sub-deployment

Per §2.8, Agni already hosts `/root/trading_lab/daily.sh` with route-level `data/routes/R*/trades.csv`. The Trading Lab cell has two sub-deployments:

| Sub-deployment | Host | Purpose | Status |
|---|---|---|---|
| `trading-lab/agni` | Agni VPS (`/root/trading_lab`) | Production Toobit-integrated route trading | active, ~daily operator pull |
| `trading-lab/rushabdev` | rushabdev VPS | (per operator) — different strategy/exchange | active, snapshotted locally |
| `trading-lab/local` | Mac | Orchestration + signal generation + reporting | active, runs `ginko_orchestrator` |

These are **sub-cells** of the Trading Lab cell (use `parent_cell_id = "trading-lab"`). Each sub-cell has its own host, its own KPIs, its own kill criteria. Aggregate roll-up to Trading Lab. Trading Lab rolls up to SHAKTI_GINKO Treasury.

### 5.4 The daily cycle (existing reality)

From `ginko_orchestrator.py:4-9`:
1. Data pull (05:00) — FRED + Finnhub + CoinGecko
2. Regime detection + signal generation (06:00)
3. Arbitrage/opportunity scanning (every 15 min)
4. P&L reconciliation + Brier update (16:30)
5. Report generation (18:00)

Plus operator-paste-to-Claude ritual using `~/agni_daily.toobit.sh` output. The substrate's job: render this cycle as Cards, automate the paste-back loop, surface the kanban.

---

## 6. Remote-Host Adapter — Substrate Primitive

`dharma_swarm.adapters.remote_host` is a **new package** (this spec defines the interface; implementation is Phase 5). It is a substrate primitive — every cell that runs on a non-local host uses this adapter.

### 6.1 Design constraint discovered 2026-05-20

The Perplexity Mac app cannot read `~/.ssh/` (sandbox `Operation not permitted`). This means:

- **`pc bash ssh agni ...` will not work** through the in-thread bridge
- The adapter cannot rely on the Mac app's bash for SSH
- The adapter must use one of these drivers (in order of preference):

#### Driver A — Operator-launched local daemon (recommended)
A small Python daemon (`dharma_swarm.adapters.remote_host_daemon`) launched by the operator outside the Mac-app sandbox (regular Terminal.app, full `~/.ssh` access). The daemon listens on a local socket (`~/.dharma/remote_host.sock`). The substrate calls the daemon via the BoardStore facade; the daemon executes SSH commands; results return through the same socket. The daemon has full SSH key access; the substrate has none. Trust boundary is clean.

#### Driver B — Terminal.app shell out via AppleScript
`pc osascript` can drive Terminal.app, which has full SSH access. Each remote command becomes an AppleScript-driven Terminal command with stdout capture. Slower, less reliable, but no daemon required. Useful as fallback.

#### Driver C — Operator-confirmed in-thread paste
Substrate emits the SSH command to operator, operator pastes into Terminal.app, pastes output back to substrate. Slowest, requires operator-in-the-loop, but works *today* with zero new infrastructure. This is the current workflow with `~/agni_daily.toobit.sh`.

**Recommended progression:** Phase 5 ships Driver C (the paste loop, but instrumented). Phase 5.5 adds Driver A (the daemon). Driver B may never ship if A works.

### 6.2 Interface

```python
class RemoteHostAdapter(Protocol):
    """A substrate primitive for executing actions on a non-local host."""

    host_id: str  # "agni", "rushabdev", ...
    driver: Literal["daemon", "applescript", "paste"]

    async def deploy_cell(self, cell_id: str, manifest: CellDeployManifest) -> DeployReceipt: ...
    async def run_command(self, cell_id: str, cmd: str, *, approval_required: bool = True) -> CommandReceipt: ...
    async def fetch_artifact(self, cell_id: str, remote_path: str, *, local_dest: Path) -> ArtifactReceipt: ...
    async def fetch_logs(self, cell_id: str, *, since: datetime | None = None) -> LogReceipt: ...
    async def health_check(self, cell_id: str) -> HealthReceipt: ...
    async def kill_cell(self, cell_id: str, *, force: bool = False) -> KillReceipt: ...
```

### 6.3 Auth

- **Driver A**: daemon holds SSH keys; substrate holds nothing
- **Driver B**: AppleScript drives Terminal which uses operator's keys
- **Driver C**: operator pastes, operator owns auth
- **No credentials ever in the BoardStore.** Every adapter is auth-opaque from the substrate's perspective.

### 6.4 Approval gate

Every write operation (`deploy_cell`, `run_command` with side effects, `kill_cell`) requires operator approval until the cell-host pair has a `trust_established=true` flag set. Read operations (`fetch_artifact`, `fetch_logs`, `health_check`) do not require approval after initial setup.

Approval mechanism: the adapter emits a `ControlEvent.RemoteCommandPending` to BoardStore; the operator approves via dashboard / Telegram / `dgc` CLI; adapter proceeds.

### 6.5 Audit

Every adapter call (read or write) is logged to BoardStore as a `ControlEvent` with: `host_id`, `cell_id`, `command_or_path`, `requested_at`, `approved_by`, `approved_at`, `completed_at`, `exit_code`, `bytes_in/out`, `error`. This is non-negotiable — the audit trail is the substrate's promise to the operator.

---

## 7. BusinessIntelligenceNoticer Roster

Full noticer definitions live in `BUSINESS_INTELLIGENCE_NOTICERS.md`. This section is the summary roster.

| Noticer | Cadence | Inputs | Output (cards) | Forbidden |
|---|---|---|---|---|
| **MarketScanNoticer** | 6h | FRED, Finnhub, CoinGecko, Google Trends, custom RSS | `RevenueTarget` cards | Cannot trade, transact, or post outreach |
| **ViabilityNoticer** | triggered on new RevenueTarget | RevenueTarget card + memory_kernel + competitor profiles | `VerificationReceipt` (viability score, 6 dimensions) attached to RevenueTarget | Cannot create cells; only scores them |
| **OpportunityNoticer** | 1h | Cross-cell P&L + external signals (`MarketScanNoticer` output) | Cards proposing arbitrage / pairing / hedging across cells | Cannot execute trades |
| **IdeationNoticer** | 24h | `memory_kernel`, operator vault (`~/AGNI-AUNT-HILLARY-PSMV/SHAKTI_GINKO/VISION/SHAKTI_GINKO_MASTER.md` and TOP_10_DISCIPLINES), recent receipts, ACTIVE_TRACK | Cards proposing new VentureCell ideas | Cannot create cells (only propose); cannot read/write outside its declared sources |
| **QualityNoticer** | continuous | All cell KPIs + every receipt | Cards proposing `Advance` / `Divest` / `Archive` per cell | Cannot transition cells (only propose) |

**Universal noticer constraints (from Codex's substrate spec):**
- Notice-only. Creates/dedupes/ranks cards. Cannot execute work, edit files, push, merge, or feed evolution loops.
- Audit-logged. Every action logged to BoardStore with reasoning.
- Kill-switchable. Operator can pause any noticer via `ControlEvent`.
- Cost-capped. Every noticer has a `budget_usd_per_day` ceiling enforced by the facade.

Ranking signals (explicit only — no learned ranking in v1):
- `arjuna_weight` (highest priority)
- `vision_file_proximity` (proximity to vault/TOP_10_DISCIPLINES topics)
- `recency` (recent operator focus)
- `blocker_proximity` (unblocks high-priority work)
- `ci_signal` (from build / test / governance reports)

---

## 8. Cashflow + Treasury Layer

### 8.1 ValueEvent → Cell P&L

Every `paid_revenue` and `contracted_revenue` ValueEvent (`ontology.py:~1415-1422`) carries `economic_value_usd` and is scoped to a VentureCell (via existing `cell_id` / `task_type` linkage). The Treasury aggregator (new — `dharma_swarm/shakti_ginko/treasury.py`) sums these per cell across rolling windows (7d, 30d, 90d) and writes back to cell KPIs.

### 8.2 Cell P&L → Organ Treasury

Per-cell P&L rolls up to organ-level treasury. The organ treasury maintains:

- `total_revenue_usd_7d / 30d / 90d`
- `total_cost_usd_7d / 30d / 90d`
- `net_treasury_usd` (running balance)
- `per_cell_allocation_usd` (current allocations)
- `available_for_new_cells_usd`

### 8.3 Budget allocator

Treasury allocates token + dollar + time budgets to cells based on a formula (v1, simple):

```
allocation_share(cell) =
    arjuna_weight * stage_multiplier * roi_30d_normalized
    / sum_of_above_across_active_cells
```

Where `stage_multiplier ∈ {0.2, 0.5, 1.0, 1.5, 2.0}` for stages 1–5.

Allocation runs at the start of each operator week (Sunday UTC by default; configurable). Operator may override allocations via `ControlEvent.SetAllocation`.

### 8.4 Kill criteria (default; cells may override)

A cell transitions to `divesting` when **any** of:

- `pnl_90d_usd < -kill_threshold_usd` (default: 25% of total budget consumed without revenue)
- `roi_30d < -0.5` (lost half of recent investment with no recovery)
- `arjuna_drift > 0.2` (cell drifted away from its initial purpose)
- `quality_score < 0.3` for 14+ consecutive days
- Operator-issued `ControlEvent.Divest`

`divesting` lasts up to 30 days (orderly wind-down: close positions, archive artifacts, document lessons). Then `archived`.

---

## 9. Wire-In to the BoardStore Substrate

Every SHAKTI_GINKO concept maps to a BoardStore primitive. This section enumerates the bindings — if any binding doesn't exist in Codex's `SWARM_BOARDSTORE_SPEC.md`, that's a substrate spec bug to flag back.

| SHAKTI_GINKO concept | BoardStore primitive |
|---|---|
| VentureCell (e.g., `trading-lab`) | `Card` with `kind="venture_cell"`, parent_objective="shakti_ginko" |
| Sub-cell (e.g., `trading-lab/agni`) | `Card` with `parent_card_id=<trading-lab card id>` |
| Noticer finding (e.g., RevenueTarget) | `Card` with `kind="revenue_target"`, created_by=`market_scan_noticer`, status=`Inbox` |
| Cashflow event (paid_revenue) | `VerificationReceipt` attached to the cell Card, contains ValueEvent payload |
| Cell state transition (Advance/Divest) | `ControlEvent` with `event_type ∈ {Advance, Divest, Archive}` |
| Remote-host command | `ControlEvent` with `event_type="RemoteCommand"`, full audit fields |
| Persistent noticer agent | Registered in `LivingAgent` registry with `kind="noticer"`, `capability_required=["notice_only"]` |
| Operator approval | `ControlEvent` with `event_type="ApproveCommand"` (or rejection) |
| Cost cap breach | `ControlEvent` with `event_type="BudgetExceeded"` + automatic cell pause |
| Kill switch | `ControlEvent` with `event_type="Kill"` at granularity per-command / per-cell / per-noticer / per-organ |

**Validation:** Every row above maps to a primitive in `SWARM_BOARDSTORE_SPEC.md` (PR #316). The Card schema (§3), the seven store contracts (§4), and the facade interface (§5) cover Card / ClaimLease / ReceiptRef / AuditEntry / ControlEvent. Cell-as-Card uses the `card.body` + `capability_manifest` + adapter-owned native fields (organ stores cell-specific data in an adapter table; the Card stays schema-stable). If any row above lacks a binding when Codex's spec lands on `main`, file an issue against the substrate spec.

---

## 10. Surfaces (Renderers)

Per Codex's substrate spec: surfaces are read-only renders. State changes go through the client. SHAKTI_GINKO renders to:

### 10.1 Kanban (web, on existing `dashboard/`)

- **Columns:** `Inbox → Proposed → Incubating → Active → Mature → Divesting → Archived`
- **Swimlanes:** one per VentureCell (e.g., trading-lab, revenue-wedge, info-products)
- **Sub-lanes:** one per sub-cell (e.g., trading-lab/agni, trading-lab/rushabdev)
- **Card detail:** KPIs, P&L sparkline, current noticer findings, recent receipts, control buttons (pause/divest/approve)

### 10.2 Map (organ-level view)

Treasury heatmap on top of the existing `dharma_cybernetic_map` (shared workspace asset). Color-codes cells by:
- Green: positive ROI, ARJUNA-aligned, healthy KPIs
- Yellow: incubating / weak signal
- Red: kill-criteria triggered

### 10.3 Telegram

Per Codex's substrate spec (Telegram-first surface): morning P&L digest, opportunity alerts, kill warnings. Format: brief text + deep-link to dashboard card.

### 10.4 CLI

New `dgc ginko` subcommand surface:

```
dgc ginko status                    # organ-level summary
dgc ginko cells                     # list cells with KPIs
dgc ginko cell <cell-id>            # cell detail
dgc ginko opportunities             # current noticer-generated cards
dgc ginko propose-cell <spec.yaml>  # operator-initiated proposal
dgc ginko fund <cell-id> <usd>      # operator allocation override
dgc ginko kill <cell-id>            # operator kill switch
dgc ginko pause <noticer-id>        # pause a noticer
dgc ginko approve <command-id>      # approve pending RemoteCommand
```

### 10.5 Dashboard

Full-organ view in the existing Next.js dashboard. Drill-down per cell. Per-noticer panel. Treasury panel. Remote-host status panel.

---

## 11. Migration Plan

Each phase is its own PR. Each phase has its own test. Each phase ships kanban evidence before the next begins.

### Phase 1 — Spec landing (this PR + Codex's substrate spec)

Lands:
- `SHAKTI_GINKO_ORGAN.md` (this doc)
- `VENTURE_CELL_LIFECYCLE.md`
- `BUSINESS_INTELLIGENCE_NOTICERS.md`
- `ADR-006-shakti-ginko-organ.md`

Validation: `make docops-integrity` and `make onboard` green after the docs land.

### Phase 2 — VentureCell ontology extension

- Extend the existing `VentureCell` ontology object (`ontology.py:1470`) with the new fields from §4.1 (`card_id`, `arjuna_weight`, `budget_usd`, `budget_time_hours`, `pnl_*`, `kill_criteria`, `host`, `parent_cell_id`, `room_id`)
- Migrate the existing `revenue-wedge` cell declaration to use the extended schema
- Tests: schema validation, backward compat (old VentureCell instances continue to load)
- Estimated: 1-2 days, single agent

### Phase 3 — One existing module → BoardStore (proof)

- Wire `ginko_signals` to BoardStore: each signal generated becomes a Card (kind=`signal`, parent=`trading-lab/agni`)
- Operator can see signals in the kanban
- No execution changes; pure read-instrumentation
- Tests: integration test producing N signals → N cards, all visible via dashboard
- Estimated: 2-3 days, single agent

### Phase 4 — MarketScanNoticer (first BI noticer)

- New module `dharma_swarm/shakti_ginko/noticers/market_scan.py`
- Adapts the existing `revenue/scout_daemon.py` pattern
- Cadence 6h, creates `RevenueTarget` cards
- Cost cap, kill switch, audit log per Codex's noticer contract
- Tests: noticer-only behavior verified (cannot execute), card creation tested, cost cap tested
- Estimated: 3-4 days, single agent

### Phase 5 — Remote-host adapter (Driver C — paste loop)

- New package `dharma_swarm/adapters/remote_host/`
- Driver C only (paste loop with instrumented audit)
- Methods: `fetch_logs` (operator pastes `agni_daily.toobit.sh` output), `health_check` (operator pastes uptime / process status)
- Operator approval per pull
- Tests: round-trip test (substrate emits request, mock-paste returns output, audit log captures both)
- Estimated: 2-3 days, single agent

### Phase 5.5 — Remote-host adapter (Driver A — daemon, OPTIONAL)

- `dharma_swarm/adapters/remote_host_daemon.py` runs outside Mac-app sandbox
- Operator launches via `dgc ginko remote-daemon start`
- Local socket at `~/.dharma/remote_host.sock`
- Tests: end-to-end with mocked SSH, then real SSH to Agni
- Estimated: 4-5 days, careful, gated on operator OK

### Phase 6 — Progressive rollout

In any order, each its own PR:

- ViabilityNoticer + IdeationNoticer + OpportunityNoticer + QualityNoticer (one per PR)
- Treasury aggregator + allocator
- Revenue Wedge cell migration to extended VentureCell schema
- Info-Products cell scaffolding (gated on operator strategic decision per §14)
- Dashboard kanban page (Codex's substrate spec ships base infra; this is the SHAKTI_GINKO render)
- `dgc ginko` CLI surface

### Acceptance gate per phase

Before merging any phase PR:
1. All tests pass (unit + integration + chaos)
2. `make docops-integrity` and `make onboard` green
3. ARJUNA gate documented for any new cell / noticer
4. Kanban shows at least one card produced by the new work
5. Operator can pause / kill the new component via `ControlEvent`

---

## 12. Test Strategy

### Unit tests
- Each noticer's signal-extraction logic (mocked inputs)
- Each cell state transition (FSM completeness)
- Each remote-host command translation (Driver A daemon protocol)
- Treasury aggregation math
- Budget allocator distribution math
- ARJUNA-gate threshold enforcement

### Integration tests
- Full lifecycle of one cell: RevenueTarget creation → ViabilityScore receipt → operator approval → cell creation → execution receipts → ValueEvent → KPI update → MaturityTransition
- Full Trading Lab cell: ginko_signals → BoardStore Cards → operator review → trading-lab/agni execution (mocked Agni) → ValueEvent → treasury

### End-to-end (24h mock cycle)
- All five noticers running in mock mode
- All cells in some state
- Operator interventions injected at random points
- Assert: no corruption, all receipts land, all audit-logs complete, kill switch works mid-cycle

### Chaos tests
- VPS unreachable mid-`fetch_logs` (Driver C should surface to operator; Driver A should retry with backoff)
- Noticer crash mid-card-creation (lease expires; partial card cleaned up)
- Kill switch fires mid-cell execution
- Cost cap breached mid-action

### Cost-cap tests
- Cell budget exhausted → cell auto-paused → operator notified
- Noticer daily budget exhausted → noticer auto-suspended
- Organ-level daily ceiling approached (80%) → warning event

---

## 13. Operational Concerns

### 13.1 Kill switch hierarchy

| Level | Granularity | Trigger |
|---|---|---|
| L0 — Per-command | Stop one in-flight remote command | Operator via dashboard / CLI / Telegram |
| L1 — Per-cell | Pause all activity in one cell; mark `paused` (sub-status under `active`) | Operator or QualityNoticer-proposed-operator-approved |
| L2 — Per-noticer | Suspend one noticer; running tasks complete; no new cards created | Operator or organ-level kill |
| L3 — Per-organ | Stop all SHAKTI_GINKO activity; all cells pause; all noticers suspend | Operator only; requires re-confirmation |
| L4 — Per-host | Stop all activity on one remote host (e.g., Agni) | Operator only |

Mechanism: `~/.dharma/cohorts/<id>/STOP` sentinel + facade-level enforcement (per Codex's substrate spec). SHAKTI_GINKO adds organ/cell/noticer/host scoping on top.

### 13.2 Cost caps

| Scope | Default cap | Configurable |
|---|---|---|
| Per-cell daily | $50 (stage 1) → $5000 (stage 5) | Yes; per-cell |
| Per-noticer daily | $5 | Yes; per-noticer |
| Per-organ daily | $200 | Yes; operator only |
| Per-organ weekly | $1000 | Yes; operator only |
| Per-cell capital at risk | Per autonomy stage (see §4.3) | Yes; per-cell |

Breaches trigger `ControlEvent.BudgetExceeded` + automatic pause at appropriate scope.

### 13.3 Observability

- Every remote command audit-logged (per §6.5)
- Every cashflow event has a `VerificationReceipt` (per §9)
- Every noticer action has reasoning in its log
- OpenTelemetry GenAI spans on every facade call (per Codex's substrate spec)
- Metrics: cards-per-state per cell, noticer find rate, P&L per cell, cost burn per cell, lease-expiry rate, kill-switch fire count

### 13.4 Multi-instance safety

Only one substrate instance writes to a cell at a time (lease-enforced per Codex's spec). The Trading Lab cell on Agni cannot be written by two operators simultaneously — the lease holder owns it for the lease duration. Read access is unrestricted.

### 13.5 Capital safety

- Stage-1 cells **cannot move capital** at all (enforced at adapter layer — `run_command` rejects any command matching a capital-action pattern)
- Stage-2 cells move only on testnets / paper
- Stage-3+ cells: every trade above per-trade ceiling ($X, default $100) requires operator approval via `ControlEvent.ApproveCommand`
- Stage-5 cells: per-cohort budget, no per-trade approval, but full audit + 24h burn ceiling

---

## 14. Open Questions and Non-Goals

### 14.1 Open questions (need operator decision before Phase 2)

1. **VPS-as-sub-cell vs VPS-as-separate-cell:** Currently §5.3 models Agni/rushabdev as sub-cells of `trading-lab`. Alternative: each VPS is its own top-level cell (with `trading-lab` as a coordinator/portfolio cell). Decision affects KPI roll-up and treasury allocation.
   - **Recommendation:** sub-cells (current spec). Easier to reason about. Operator decides.

2. **Ideation cell autonomy:** §15 says ideation is gated. But how much can IdeationNoticer + IdeationCell *actually* do? Read-only of vault, propose new cells, write to a single proposals file? Or can it draft full cell specs?
   - **Recommendation:** v1: read-only of vault + memory_kernel, propose cells only (no draft specs). v2: with track record, allow draft cell specs (still operator-approved).

3. **Info-Products cell platform:** Gumroad? Lemon Squeezy? Self-hosted? Stripe + own storefront? PSMV vault → Gumroad listing pipeline?
   - **Recommendation:** start Gumroad (per SHAKTI_GINKO README mention). Self-host evaluated at Phase 6+.

4. **Revenue capture cadence:** real-time webhook from payment processor → ValueEvent? Or batched daily reconciliation? Real-time is cleaner but adds webhook infra; batch is simpler.
   - **Recommendation:** start batch daily (reconcile from Gumroad/Toobit reports), real-time at Phase 6+ if volume justifies.

5. **Driver A vs Driver C for remote host:** Phase 5 ships C (paste loop). When does A (daemon) ship? Gated on operator's comfort with launching a sandbox-bypass daemon.

### 14.2 Explicit non-goals (deliberate exclusions)

- **No autonomous capital movement above stage-3 thresholds.** Stage 4-5 cells are aspirational and locked by operator-only transitions.
- **No autonomous outreach.** Scout daemon's existing rule ("NO AUTONOMOUS SPAM") is upheld; this spec does not loosen it.
- **No autonomous cell creation.** IdeationNoticer *proposes* cells; only operators (or operator-approved automation) *create* them.
- **No replacement of the operator-local vault** (`~/AGNI-AUNT-HILLARY-PSMV/SHAKTI_GINKO/`). The vault remains strategic authority.
- **No new orchestrator.** The substrate is the orchestrator. SHAKTI_GINKO is an organ on top of the substrate.
- **No file renames in this PR.** The `ginko_*` rename to `trading_lab_*` is a separate PR with deprecation shims.

### 14.3 Punted to v2

- ML/learned ranking in noticers (v1 is explicit-signal-only)
- Cross-cell hedging logic (OpportunityNoticer in v1 only *finds* opportunities; cross-cell trades are operator-approved)
- Multi-operator handoff (cells are single-operator in v1)
- Public dashboard / customer-facing transparency (v1 is operator-only)

---

## 15. ARJUNA Gate Per Cell

Every cell (and every Card) carries `arjuna_weight ∈ [0.0, 1.0]`. Two thresholds at two layers (introduced in §1):

1. **Card-create floor `0.35`** — facade-enforced per `SWARM_BOARDSTORE_SPEC.md §11`. Any card below this is refused by `BoardStore.create_card` unless an `override=ArjunaOverride(reason=…)` is supplied. Only operator/admin can override; noticers and agents cannot. The reason must name an external user, dataset, partner, measurable impact, or active-track dependency.
2. **Cell auto-fund floor `0.6`** — organ-enforced by the allocator (§8.3). Cells below this can exist, can receive cards, and can be funded *manually* by the operator, but the allocator will not auto-allocate budget or auto-advance autonomy to them without explicit override.

The two floors compose: a card at `arjuna_weight = 0.40` is accepted by the facade but its parent cell (if also at `0.40`) does not auto-fund. Both gates are auditable.

### 15.1 Scoring rubric (operator + noticer + allocator)

From Codex's facade spec, used as the canonical band semantics:

| Band | Meaning |
|------|---------|
| `0.00–0.19` | Internal recursion, no named external target. Reject. |
| `0.20–0.34` | Possible indirect value. Needs operator override at facade gate. |
| `0.35–0.59` | Plausible substrate or operational value linked to active work. Card accepted. Cell does not auto-fund. |
| `0.60–0.84` | Clear external-user, funding, impact, or safety leverage. Card accepted. Cell auto-funds. |
| `0.85–1.00` | Directly blocks or enables real-world action, vulnerable-person safety, revenue, or high-leverage external work. Highest priority. |

### 15.2 Default per-cell weights

| Cell | Default `arjuna_weight` | Reasoning |
|---|---|---|
| `trading-lab` | 0.85 | Serves diversified swarm treasury → funds Jagat Kalyan operations. Long-running, well-instrumented, capital safety enforced. |
| `revenue-wedge` | 0.80 | Intelligence-report wedge — produces real outputs humans can use. Per existing governance doc. |
| `info-products` | 0.75 if quality bar met | Educational content on dharma + AI; serves directly. Lower than trading because requires per-product quality assessment. |
| `agentic-services` | 0.70 (per-client per-project) | Paid agent runs for aligned clients. Requires per-engagement ARJUNA scoring (separate cell-internal gate). |
| `ideation` | 0.50 | Meta-tooling risk. Card-create floor passes; cell auto-fund floor does not. Cell can run and propose; every proposal it generates is then scored on its own merits. |

### 15.3 The override path

At the **facade level** (card create / refuse):

- Operator (or admin) supplies `override=ArjunaOverride(reason=…)`.
- Emits `control.posted` with event type `arjuna_override`.
- Reason must name external user, dataset, partner, measurable impact, or active-track dependency.
- Override is permanent in the audit stream.

At the **organ level** (cell auto-fund):

- Operator issues `ControlEvent.OverrideArjuna` with: `cell_id`, `current_weight`, `target_weight`, `justification` (free text, mandatory), `duration_hours` (until weight reverts).
- Override is logged forever and visible on the cell card's audit log.
- Manual budget allocation by operator always works without override (the organ gate is on *auto*-fund, not on operator action).

### 15.4 Drift detection

`arjuna_drift = current_weight - initial_weight`. If `drift > 0.2`, QualityNoticer creates an alert card. Persistent drift triggers kill criteria (§8.4). Drift can be either direction — a cell whose weight inflates over time without justified evidence is as much a problem as one whose weight collapses.

---

## 16. Self-Audit (per working method)

**Where this spec might age badly:**

1. **The Mac-as-SSH-hop constraint may dissolve.** If Perplexity's Mac app gets Full Disk Access or a `pc ssh` first-class subcommand, Driver A's daemon may be unnecessary. The spec is correct for the constraint discovered 2026-05-20; revisit when capabilities change.

2. **The ARJUNA-weight defaults may need empirical calibration.** Setting `ideation` at 0.50 is a judgment call. Six months of cell outcomes may reveal the right thresholds are different. The spec lets operators adjust per cell, but the *defaults* may drift.

3. **The treasury allocator formula in §8.3 is v1-simple.** It does not account for: time-decay of ROI signal, correlation between cells (avoiding concentration risk), forward-looking pipeline signal (high-viability targets that haven't yet produced revenue). A v2 ADR should formalize a multi-factor allocator.

4. **The noticer roster may be incomplete.** In particular, there is no `ComplianceNoticer` (regulatory / KYC / tax) and no `SecurityNoticer` (credential rotation, access audit). At the scale where SHAKTI_GINKO produces real cashflow, these become necessary. The spec scaffolds them as extensible but does not specify them.

5. **The vault-substrate boundary is one-directional in this spec.** The substrate reads the vault as authority. But there's no spec for the substrate writing back insights to the vault (e.g., "this strategy from VISION/ produced $X" → vault gets annotated). A v2 ADR should formalize the write-back loop, carefully (the vault should not become substrate-controlled — it should remain operator-controlled with substrate annotations clearly marked).

6. **VPS sub-cells assume Agni-and-rushabdev forever.** The spec is host-agnostic via the adapter, but the conceptual structure of `trading-lab/<host>` doesn't generalize cleanly to fundamentally different hosts (e.g., a Lambda Cloud GPU node for ML training, or a Kubernetes cluster). v2 may need a `host_kind` taxonomy beyond `vps`.

**v2 ADR sketch:** "ADR-007 — SHAKTI_GINKO Maturation: Multi-Factor Treasury Allocator, Compliance/Security Noticers, Vault Write-Back Loop, Host-Kind Taxonomy." Triggered when first cell reaches `mature` status or organ-level revenue crosses $10k/month, whichever first.

---

## Appendix A — File:Line Citation Index

For quick verification:

- `ginko_orchestrator.py:1-22` — docstring with daily cycle + autonomy ladder
- `ginko_orchestrator.py:3` — "Coordinates the Shakti Ginko VentureCell" (singular drift)
- `ontology.py:1470-1507` — VentureCell object definition
- `ontology.py:1491,1494` — Create and Advance actions with telos gates
- `ontology.py:1505` — `shakti_energy=MAHALAKSHMI`
- `ontology.py:1514+` — RevenueTarget object
- `ontology.py:~1395-1428` — ValueEvent revenue fields
- `dharma_swarm/revenue/__init__.py:1-30` — package exports
- `dharma_swarm/revenue/scout_daemon.py:1-22` — scout daemon docstring + "NO AUTONOMOUS SPAM" rule
- `dharma_swarm/revenue/wedge_pipeline.py:1-20` — wedge pipeline docstring + 4-question contemplative test
- `dharma_swarm/fractal/fractal_room.py` — room implementation
- `docs/governance/VENTURE_CELL_REVENUE_WEDGE.md` — existing first VentureCell declaration
- `CLAUDE.md:136` — "ginko_brier.py — Brier scoring as aggregation quality measurement"
- `.semgrep/dharma-anti-slop.yml:32-33` — ginko domain recognized in anti-slop
- `docs/governance/ANTI_SLOP_RULES.md:77` — same recognition

Operator-local (Mac, via `pc bash`):
- `~/AGNI-AUNT-HILLARY-PSMV/SHAKTI_GINKO/README.md` — organ statement of purpose
- `~/AGNI-AUNT-HILLARY-PSMV/SHAKTI_GINKO/VISION/SHAKTI_GINKO_MASTER.md` — master skeleton (4,847 words, 91 [SWARM_TARGET])
- `~/AGNI-AUNT-HILLARY-PSMV/SHAKTI_GINKO/TOP_10_DISCIPLINES.md` — strategic canon
- `~/agni_daily.toobit.sh` — current daily operator workflow on Agni
- `~/agni_toobit_*` — Toobit integration kit

## Appendix B — Glossary

- **Organ** — a coordinated subsystem of dharma_swarm spanning multiple cells, noticers, surfaces, and hosts. SHAKTI_GINKO is an organ. Future organs may exist (e.g., a learning organ, a community organ).
- **VentureCell** — an ontology-typed work unit with its own agents, budgets, KPIs, autonomy stage, and lifecycle. A cell is a Card in BoardStore terms.
- **FractalRoom** — the in-process render of an active VentureCell. Existing implementation at `dharma_swarm/fractal/fractal_room.py`.
- **Noticer** — a notice-only persistent agent that creates/dedupes/ranks cards but never executes work.
- **Substrate** — the BoardStore facade + client lib + control plane defined in Codex's `SWARM_BOARDSTORE_SPEC.md`.
- **ARJUNA gate** — the test "does this advance Jagat Kalyan?" applied to every cell, noticer, and major action.
- **Treasury** — organ-level cashflow + budget aggregation.
- **Vault** — the operator-local strategic authority at `~/AGNI-AUNT-HILLARY-PSMV/SHAKTI_GINKO/`. Read by substrate, owned by operator.
