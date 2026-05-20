# Business Intelligence Noticers

**Status:** Spec (companion to `SHAKTI_GINKO_ORGAN.md`, `VENTURE_CELL_LIFECYCLE.md`)
**Branch:** `spec/shakti-ginko-organ`
**Telos gates:** SATYA (truth) · AHIMSA (no harm) · REVERSIBILITY (no destructive side effects)
**Ground truth:** `dharma_swarm/auto_proposer.py`, `dharma_swarm/revenue/scout_daemon.py`, `dharma_swarm/cron_runner.py`

> A noticer is a persistent agent that *notices*. It reads BoardStore, computes patterns, ranks them with explicit signals, and writes proposal cards back. It never executes the work. The operator (or an executor agent) reads the card and decides.

This document specifies the five Business Intelligence Noticers that wire SHAKTI_GINKO's persistent background intelligence:

1. **MarketScanNoticer** — external opportunity radar (6 h cadence)
2. **ViabilityNoticer** — VentureCell hypothesis-check (triggered)
3. **OpportunityNoticer** — cross-cell pattern recognition (1 h cadence)
4. **IdeationNoticer** — new-cell candidate generator (24 h cadence)
5. **QualityNoticer** — continuous KPI / health surveillance (continuous)

A sixth noticer — **TreasuryNoticer** — is sketched in `SHAKTI_GINKO_ORGAN.md §6.4` and not detailed here because it is mechanical (budget bookkeeping). The five above carry the *intelligence*.

---

## 0. The Notice-Only Contract

All noticers obey one constraint, derived from Codex's substrate review: **notice only, never execute**.

```
Allowed                                   Forbidden
─────────                                 ─────────
read from BoardStore                      execute work packets
read from external sources (HTTP, Git)    send emails / messages / posts
compute KPIs and rankings                 commit code
write proposal cards                      mutate VentureCell status
write WitnessEvents                       allocate / move budget
emit signals on SignalBus                 advance autonomy_stage
update KPI dict on a cell                 archive / spinout cells
```

The notice-only contract is enforced by RBAC. Noticers run under role `noticer` with a capability bundle that excludes every executor verb. If a noticer tries to call an executor verb, the BoardStore facade returns `PermissionDenied` and emits `WARN_NOTICER_OVERREACH`.

This contract is what makes noticers safe to run persistently in the background.

---

## 1. Shared Architecture

### 1.1 Common base class

```python
# dharma_swarm/noticers/base.py  (new — Phase 2 PR)

class Noticer(Protocol):
    """Persistent background agent that proposes, never executes."""

    name: str                     # unique noticer ID, e.g. "market_scan"
    cadence: NoticerCadence       # CONTINUOUS | TRIGGERED | FIXED_INTERVAL
    interval_seconds: int | None  # for FIXED_INTERVAL
    triggers: list[str]           # SignalBus signals that trigger TRIGGERED noticers
    role: str = "noticer"         # RBAC role

    def scan(self, ctx: NoticerContext) -> NoticerReport: ...

class NoticerContext:
    board: BoardStoreClient       # read-only facade view
    arjuna_priors: ArjunaWeights  # current operator priors
    vision_index: VisionIndex     # operator-local vault index (via VaultBridge)
    clock: Clock                  # injectable for tests

class NoticerReport(BaseModel):
    noticer: str
    scan_id: str
    started_at: datetime
    finished_at: datetime
    cards_proposed: list[CardProposal]
    cards_deduped: int
    kpis_updated: list[KpiUpdate]
    signals_emitted: list[str]
    notes: str
```

The base class is **not** new infrastructure — it is a *thin adapter* around `AutoProposer` (`dharma_swarm/auto_proposer.py:136+`), which already implements the notice-only pattern for fitness, failures, hotspots, providers, stale tasks, plateaus, test clusters, and evolution stagnation. The BI noticers extend the same idea to *business* signals.

### 1.2 Cadence types

| Cadence | Trigger | Use case |
|---------|---------|----------|
| `CONTINUOUS` | runs in a loop with backoff | KPI surveillance, kill-condition watch |
| `FIXED_INTERVAL` | cron-driven (`cron_runner.py`) | external scans, ideation |
| `TRIGGERED` | SignalBus event | viability check after cell mutation |

### 1.3 Ranking signals (v1 — explicit only)

Per Codex's constraint and Doc A §6.6, **v1 forbids learned ranking**. Every noticer scores candidate cards with the same explicit five-signal vector:

```python
@dataclass
class RankingSignals:
    arjuna_weight: float          # 0..1, from operator priors
    vision_file_proximity: float  # 0..1, similarity to vault VISION/* files
    recency: float                # 0..1, exp-decay over hours
    blocker_proximity: float      # 0..1, distance to known blocker cards
    ci_signal: float              # 0..1, CI health for relevant code paths

    def score(self, weights: RankingWeights) -> float:
        return (
            weights.arjuna * self.arjuna_weight +
            weights.vision * self.vision_file_proximity +
            weights.recency * self.recency +
            weights.blocker * self.blocker_proximity +
            weights.ci * self.ci_signal
        )
```

`RankingWeights` defaults (operator-tunable in `~/.dharma/noticer_weights.toml`):

```toml
arjuna  = 0.40   # ARJUNA Directive dominates
blocker = 0.20   # unblocking active track / CI / claimed work
ci      = 0.15   # failing-check severity, PR blocker
vision  = 0.15   # citation proximity to active vision/doctrine files
recency = 0.10
```

These defaults are pinned to `docs/architecture/SWARM_BOARDSTORE_SPEC.md §8 Noticer Contract — Ranking signals` (Codex's facade spec, PR #316). Both documents must agree on the same default weights; if either changes, the other follows. The substrate enforces these weights as the noticer-role's deterministic ranking formula. Operators may override per-installation by editing the TOML.

These weights are written down — there is no learned model. If we add learned ranking later, it lands behind a feature flag with its own ADR (`ADR-007-learned-ranking-signals`, currently deferred).

### 1.4 Card deduplication

Every noticer must dedupe before proposing. Dedupe key:

```python
dedupe_key = sha256(f"{noticer.name}|{topic}|{cell_id or 'organ'}|{day_bucket}")
```

`day_bucket` rounds the timestamp to the UTC day for daily-fresh dedupe; per-noticer overrides allow finer/coarser buckets. If a card with the same `dedupe_key` already exists in BoardStore with status `OPEN` or `IN_PROGRESS`, the new proposal is **merged** (notice count incremented, last_seen updated, evidence appended) rather than created.

### 1.5 Witness / audit

Every noticer scan emits one `WitnessEvent` with the full `NoticerReport`. Operator can replay any day's scans by date range. Replay is the audit story.

---

## 2. MarketScanNoticer

> **One-liner:** Scans external markets (job boards, GitHub stars, news, competitive signals) for opportunities aligned with SHAKTI_GINKO's domain. Proposes cards on the organ board, never on a specific cell, unless an existing cell domain matches.

### 2.1 Cadence and triggers

- **Type:** `FIXED_INTERVAL`
- **Default interval:** 6 hours (matches existing `revenue/scout_daemon.py` cadence)
- **Also triggered by:** `SIGNAL_OPERATOR_MARKET_SCAN_REQUEST`, `SIGNAL_VENTURE_CELL_PROPOSED` (re-scan for the new cell's domain)

### 2.2 Sources

```yaml
github_queries:           # extends DEFAULT_GITHUB_QUERIES in scout_daemon.py
  - "copilot agent language:python stars:>50"
  - "ai-governance language:python stars:>20"
  - "llm agent framework language:python stars:>200"
  - "autonomous coding agent stars:>50"
hn_search:
  - "ai governance"
  - "agent framework"
  - "llm orchestration"
rss_feeds:
  - "https://techcrunch.com/category/artificial-intelligence/feed/"
  - "https://www.anthropic.com/feed.xml"
  - "https://blog.langchain.dev/rss/"
operator_pinned_sources:  # from ~/.dharma/market_sources.toml
  - <operator-curated list>
```

External calls go through the existing intel infrastructure (`dharma_swarm/revenue/intelligence.py`, `intel_parser.py`). MarketScanNoticer is a **thin reorganization of the existing scout daemon** under the new noticer contract, *not* a parallel implementation.

### 2.3 Outputs

For each detected opportunity:

1. Compute ranking signals.
2. Look up matching existing cells by domain. If found, propose card on cell board. Else propose on organ board.
3. Card body: source URL, title, summary, why-this-matches (top-3 ranking signals), competitive-signal-rating.
4. ARJUNA-gated: every card carries a justified `arjuna_weight ∈ [0.0, 1.0]` per the rubric in §9.2. The noticer does not pre-suppress — it submits and lets the BoardStore facade enforce the threshold (see §9.3).

### 2.4 Pseudocode

```python
class MarketScanNoticer:
    name = "market_scan"
    cadence = NoticerCadence.FIXED_INTERVAL
    interval_seconds = 6 * 3600
    triggers = [
        "SIGNAL_OPERATOR_MARKET_SCAN_REQUEST",
        "SIGNAL_VENTURE_CELL_PROPOSED",
    ]

    def scan(self, ctx: NoticerContext) -> NoticerReport:
        report = self._start_report(ctx)

        # 1. Pull from sources (reuses RevenueIntelligenceIngestor)
        intel = self._ingest_sources(ctx)

        # 2. Score each opportunity
        candidates = [
            self._score(item, ctx) for item in intel
            if item.signal_strength > 0.2
        ]

        # 3. Dedupe + propose
        for candidate in candidates:
            # No pre-suppression — facade enforces threshold (§9).
            # Noticer is responsible only for honest scoring + justification.
            self._propose_card(candidate, ctx, report)

        # 4. Emit signals + witness
        self._finish_report(report)
        return report
```

### 2.5 Migration from scout_daemon

`revenue/scout_daemon.py` already does ~80 % of this. Migration path:

1. Phase 2 PR: introduce `Noticer` base class, refactor `scout_daemon.py` to *implement* it.
2. Rename module to `noticers/market_scan_noticer.py` with a `scout_daemon.py` shim that re-exports (deprecation shim).
3. Drop shim in Phase 4 after 2 release cycles.

---

## 3. ViabilityNoticer

> **One-liner:** For each active VentureCell, checks whether its `self_funding_hypothesis` and `first_revenue_proof` are still plausible given current KPIs. Proposes "rethink hypothesis" or "advance autonomy" cards.

### 3.1 Cadence and triggers

- **Type:** `TRIGGERED`
- **Triggers:**
  - `SIGNAL_ROOM_CREATED` (cell just became INCUBATING)
  - `SIGNAL_VENTURE_CELL_ACTIVATED` (cell just became ACTIVE)
  - `SIGNAL_WORK_PACKET_COMPLETED` (work just finished, KPIs may have changed)
  - `SIGNAL_REVENUE_INTEL_INGESTED` (MarketScanNoticer just finished)
  - Periodic fallback: every 24 h per active cell (in case triggers fail)

### 3.2 Logic

For each active cell:

1. Compute **viability score** = function of:
   - revenue_usd vs revenue_target (proportion to date)
   - burn_usd vs budget_tokens (burn rate normalized to schedule)
   - days_active vs days_to_first_revenue_target
   - paying_customers vs spinout threshold
   - external comparables from MarketScanNoticer
2. Classify into:
   - **GREEN** (`score ≥ 0.7`): cell is on track. Recommend autonomy advance if AUTONOMY_REQUIREMENTS met.
   - **AMBER** (`0.4 ≤ score < 0.7`): cell is at risk. Recommend operator review.
   - **RED** (`score < 0.4`): cell is failing. Recommend hypothesis rework or early kill.
3. Propose one card per cell per scan with the verdict, full evidence trail, and recommended next step.

### 3.3 Specific recommendations

| Verdict | Trigger conditions | Card produced |
|---------|--------------------|---------------|
| Advance | GREEN + `check_autonomy_advancement.can_advance == True` | "Advance `<cell>` to stage `<n+1>` — requirements met: `<list>`" |
| Hold | GREEN + `can_advance == False` | "Continue current stage; missing: `<unmet list>`" |
| Pivot | AMBER + welfare positive + revenue lagging | "Pivot hypothesis — current revenue path failing, welfare path viable" |
| Reduce | AMBER + burn high | "Reduce burn — `<cell>` overspending; consider budget cut" |
| Kill watch | RED + ≥ 1 kill condition partially met | "Kill watch — `<cell>` at `<n>` days, $0 revenue. Default kill in `<days>`." |

### 3.4 Pseudocode

```python
class ViabilityNoticer:
    name = "viability"
    cadence = NoticerCadence.TRIGGERED
    triggers = [
        "SIGNAL_ROOM_CREATED",
        "SIGNAL_VENTURE_CELL_ACTIVATED",
        "SIGNAL_WORK_PACKET_COMPLETED",
        "SIGNAL_REVENUE_INTEL_INGESTED",
    ]

    def scan(self, ctx: NoticerContext) -> NoticerReport:
        cells = ctx.board.list_cells(status_in=["INCUBATING","ACTIVE"])
        for cell in cells:
            verdict = self._compute_verdict(cell, ctx)
            self._propose_verdict_card(cell, verdict, ctx)
        return self._finish_report()
```

### 3.5 Welfare safety net

If a cell shows `welfare_tons_produced < 0`, ViabilityNoticer **always** produces a RED card regardless of revenue. ARJUNA enforced: negative-welfare cells cannot hide behind good revenue.

---

## 4. OpportunityNoticer

> **One-liner:** Sees patterns *across* multiple cells, the substrate, and the operator vault. Proposes federation, deduplication, and cross-cell wedge ideas.

### 4.1 Cadence and triggers

- **Type:** `FIXED_INTERVAL`
- **Default interval:** 1 hour
- **Also triggered by:** any `SIGNAL_VENTURE_CELL_*`, `SIGNAL_VAULT_FILE_CHANGED`

### 4.2 What it looks for

This is the **most operationally creative noticer**. Patterns it scans:

1. **Cross-cell duplication.** Two cells producing similar artifacts → propose federation card.
2. **Shared blocker.** Multiple cells blocked on same dependency → propose elevate-blocker card.
3. **Vault-cell gap.** Vault VISION file references work that no cell is doing → propose new cell (delegates to IdeationNoticer).
4. **Concentration risk.** One agent assigned to too many cells → propose roster rebalance.
5. **Federation opportunity.** Cell A's artifacts unblock Cell B → propose explicit federation edge.
6. **Stigmergy hotspot.** Substrate signals (from `stigmergy.py`) show convergent activity → surface as opportunity card.

### 4.3 Output cards

Each card includes:

- Pattern type
- Cells involved (with links)
- Evidence (specific BoardStore queries with results)
- Suggested action (operator-actionable)
- Expected value (ARJUNA-weighted)

### 4.4 Pseudocode (one pattern shown)

```python
def _detect_cross_cell_duplication(self, ctx) -> list[CardProposal]:
    cells = ctx.board.list_cells(status="ACTIVE")
    proposals = []
    for cell_a, cell_b in itertools.combinations(cells, 2):
        artifacts_a = ctx.board.list_artifacts(cell_id=cell_a.id, since=ctx.window)
        artifacts_b = ctx.board.list_artifacts(cell_id=cell_b.id, since=ctx.window)
        similarity = self._artifact_similarity(artifacts_a, artifacts_b)
        if similarity > 0.6:
            proposals.append(
                self._build_card(
                    topic="cross-cell-duplication",
                    cells=[cell_a.id, cell_b.id],
                    evidence={"similarity": similarity, "samples": ...},
                    suggested="federate or merge",
                )
            )
    return proposals
```

### 4.5 Why it lives at 1 h cadence

Cross-cell patterns emerge slowly. Faster than 1 h is wasteful (cells don't change that fast). Slower than 1 h misses inter-day patterns. 1 h is the default; operator can tune.

---

## 5. IdeationNoticer

> **One-liner:** Generates *new VentureCell candidates* from the vault, market scans, and unaddressed blockers. Operator approves or rejects.

### 5.1 Cadence and triggers

- **Type:** `FIXED_INTERVAL`
- **Default interval:** 24 hours (overnight scan, brief includes morning)
- **Also triggered by:** `SIGNAL_VAULT_FILE_CHANGED` (new VISION content), `SIGNAL_OPERATOR_IDEATION_REQUEST`

### 5.2 Sources

1. **Vault VISION files** — read via VaultBridge (`~/AGNI-AUNT-HILLARY-PSMV/SHAKTI_GINKO/VISION/`). Look for `[SWARM_TARGET]` markers (vault has 91 of these per Doc A) that don't yet map to a cell.
2. **MarketScanNoticer cards** — promote high-arjuna market cards to cell candidates.
3. **OpportunityNoticer "vault-cell gap" cards** — direct input.
4. **Operator-pinned ideas** — from `~/.dharma/ideation_seeds.yaml`.

### 5.3 Candidate card schema

```yaml
ideation_card:
  proposed_cell_id: "<slug>"
  proposed_name: "<short name>"
  customer_or_beneficiary: "<draft>"
  value_proposition: "<draft>"
  self_funding_hypothesis: "<draft>"
  first_revenue_proof: "<draft, 60 days>"
  jagat_kalyan_constraint: "<draft>"
  recommended_kill_conditions: [default_set]
  recommended_spinout_conditions: [default_set]
  recommended_initial_budget_tokens: <int>
  recommended_initial_roster: ["<agent>", ...]
  arjuna_weight: <float>
  vision_proximity: <float>
  evidence:
    vault_files: [...]
    market_signals: [...]
    operator_seeds: [...]
```

Operator approval = card status `APPROVED` → orchestrator creates the cell (Create action on VentureCell ontology object) → cell enters PROPOSED → INCUBATING per lifecycle (Doc B §2).

### 5.4 Cap on proposals

To prevent ideation spam, IdeationNoticer:

- Proposes at most **3 new candidates per scan** (top-3 by ranking score).
- Suppresses duplicates against existing cells *and* against ideation cards proposed in the last 7 days.
- Cards expire after 14 days without operator action (status → `EXPIRED`).

### 5.5 Pseudocode

```python
class IdeationNoticer:
    name = "ideation"
    cadence = NoticerCadence.FIXED_INTERVAL
    interval_seconds = 24 * 3600
    triggers = ["SIGNAL_VAULT_FILE_CHANGED", "SIGNAL_OPERATOR_IDEATION_REQUEST"]
    max_proposals_per_scan = 3

    def scan(self, ctx: NoticerContext) -> NoticerReport:
        seeds = self._collect_seeds(ctx)  # vault + market + opportunity + operator
        candidates = [self._draft_candidate(s, ctx) for s in seeds]
        scored = sorted(candidates, key=lambda c: -c.score)
        top = scored[: self.max_proposals_per_scan]
        for c in top:
            if not self._is_duplicate(c, ctx):
                self._propose_card(c, ctx)
        return self._finish_report()
```

---

## 6. QualityNoticer

> **One-liner:** Continuous KPI / health surveillance. Fires kill-watch, demotion-recommend, and budget warnings. The most paranoid noticer.

### 6.1 Cadence and triggers

- **Type:** `CONTINUOUS`
- **Loop:** every active cell evaluated every N minutes (N defaults to 15); kill-conditions evaluated every 60 s on cells flagged "kill-watch".
- **Triggered re-evaluation:** any `SIGNAL_WORK_PACKET_COMPLETED`, `SIGNAL_VENTURE_CELL_TREASURY_WARNING`, KPI mutation.

### 6.2 Responsibilities

1. **KPI freshness audit.** Any cell with a kill-condition input older than 24 h gets a `STALE_KPI` warning (per Doc B §4.4).
2. **Kill condition watch.** Re-evaluate `evaluate_kill_conditions(cell.kill_conditions, cell.kpis)` on every loop. On True:
   - Emit `SIGNAL_ROOM_KILL_CONDITION_MET`.
   - Create kill-watch card with 24 h operator response window.
   - **Does not archive.** Operator-confirmation or auto-archival after 24 h handled by the lifecycle FSM, not the noticer.
3. **Spinout condition watch.** Re-evaluate `evaluate_spinout_conditions(cell.spinout_conditions, cell.kpis)`. On True, emit `SIGNAL_ROOM_SPINOUT_CONDITION_MET`. Operator always approves.
4. **Autonomy demotion recommend.** When trading-lab cell shows:
   - Brier deterioration > 0.02 over 200 predictions, OR
   - drawdown breaches stage threshold for 3 consecutive days, OR
   - `welfare_tons_produced < 0`
   ...emit `WARN_VENTURE_CELL_DEMOTION_RECOMMENDED` with TaskBoard card.
5. **Budget warnings.** At `budget_ratio > 1.0`, emit `SIGNAL_VENTURE_CELL_TREASURY_WARNING` (collaboration with TreasuryNoticer).
6. **Witness completeness check.** If a mutation lacks a WitnessEvent within 60 s, emit `WARN_WITNESS_GAP`.

### 6.3 Pseudocode

```python
class QualityNoticer:
    name = "quality"
    cadence = NoticerCadence.CONTINUOUS
    loop_interval_seconds = 60  # kill-watch loop
    full_scan_interval_seconds = 15 * 60  # full KPI scan

    def scan(self, ctx: NoticerContext) -> NoticerReport:
        # Fast loop: kill watch
        for cell in ctx.board.list_cells(flag="kill_watch"):
            if evaluate_kill_conditions(cell.kill_conditions, cell.kpis):
                self._fire_kill_card(cell, ctx)

        # Periodic loop: full scan (every 15 min, gated by timestamp)
        if self._should_run_full_scan(ctx):
            for cell in ctx.board.list_cells(status_in=["ACTIVE","MATURE"]):
                self._kpi_freshness_audit(cell, ctx)
                self._demotion_check(cell, ctx)
                self._budget_check(cell, ctx)
                if evaluate_spinout_conditions(
                    cell.spinout_conditions, cell.kpis
                ):
                    self._fire_spinout_card(cell, ctx)

        return self._finish_report()
```

### 6.4 Why CONTINUOUS

Kill conditions can become True at any moment (e.g., burn spike, operator override, welfare turning negative). A 1 h or 24 h cadence would let a cell rack up $10k of waste before the next scan. The 60 s tight loop is cheap (BoardStore reads are indexed) and the safety upside is large.

### 6.5 Backpressure

If BoardStore reads degrade (p95 > 200 ms), QualityNoticer reduces full-scan frequency to 30 min and emits `WARN_NOTICER_BACKPRESSURE`. Kill-watch tight loop continues unchanged — that's the safety floor.

---

## 7. Noticer Scheduling

All noticers register with `NoticerScheduler` (new — Phase 2 PR), a thin wrapper over the existing `cron_runner.py` / `cron_daemon.py`. Registration:

```python
# dharma_swarm/noticers/__init__.py

NOTICERS: list[Noticer] = [
    MarketScanNoticer(),
    ViabilityNoticer(),
    OpportunityNoticer(),
    IdeationNoticer(),
    QualityNoticer(),
    TreasuryNoticer(),
]

def register_all(scheduler: NoticerScheduler) -> None:
    for n in NOTICERS:
        scheduler.register(n)
```

`NoticerScheduler` is a *thin reorganization* of `cron_runner` — no new daemon infrastructure. Existing handlers (`revenue_scout`, etc.) become Noticers via deprecation shims.

---

## 8. Failure modes and observability

### 8.1 What if a noticer crashes?

- Crash is logged with full context.
- Scheduler restarts noticer after exponential backoff (max 5 retries, then quarantine).
- Quarantined noticers raise `WARN_NOTICER_QUARANTINED` and require operator unfreeze.

### 8.2 What if a noticer floods cards?

- Per-noticer rate limits in `~/.dharma/noticer_rate_limits.toml`. Defaults:
  - MarketScanNoticer: 50 cards/day
  - ViabilityNoticer: 1 card/cell/scan (capped at N cells)
  - OpportunityNoticer: 20 cards/day
  - IdeationNoticer: 3 cards/scan (hard cap)
  - QualityNoticer: unlimited (safety)
- Exceeding rate limit → noticer suspended for the day, `WARN_NOTICER_RATELIMIT` raised.

### 8.3 Observability

- Per-scan: report stored at `~/.dharma/noticer_reports/<noticer>/<date>/<scan_id>.json`.
- Daily summary: `dharma noticer report --since 24h` (CLI to be authored — Phase 3).
- Operator brief includes noticer activity summary by default.

---

## 9. ARJUNA Enforcement Across Noticers

The ARJUNA test is doctrine; the gate is code at the BoardStore facade. This section pins how noticers participate in that gate. Authority: `docs/doctrine/OPERATIONAL_DOCTRINE.md:52` (the test) and `docs/architecture/SWARM_BOARDSTORE_SPEC.md §11 ARJUNA Gate Integration` (the code-level rules).

### 9.1 The threshold

**Default threshold: `arjuna_weight = 0.35`.** This is the facade-enforced floor in `SWARM_BOARDSTORE_SPEC.md §11` and is **operator-tunable**, not noticer-tunable.

`BoardStore.create_card` refuses any card with `arjuna_weight < 0.35` unless an `override` is supplied. Noticers, by their role contract (§0, `SWARM_BOARDSTORE_SPEC.md §8`), **cannot** supply override. Only operator or admin can.

### 9.2 Scoring rubric

Codex's facade pins the meaning of weight bands (`SWARM_BOARDSTORE_SPEC.md §11`):

| Band | Meaning | Noticer behaviour |
|------|---------|-------------------|
| `0.00–0.19` | Internal recursion, no named external target | reject — do not propose |
| `0.20–0.34` | Possible indirect value | propose but expect facade to refuse without operator override |
| `0.35–0.59` | Plausible substrate or operational value linked to active work | propose normally |
| `0.60–0.84` | Clear external-user, funding, impact, or safety leverage | propose with priority boost in card list |
| `0.85–1.00` | Directly blocks or enables real-world action, vulnerable-person safety, revenue, or high-leverage external work | propose with highest priority + emit `SIGNAL_VENTURE_CELL_HIGH_LEVERAGE` |

### 9.3 What each noticer must do, before proposing

1. Compute `arjuna_weight ∈ [0.0, 1.0]` per the rubric above. The score itself must be auditable: the noticer logs the named external target, dataset, partner, measurable impact, or active-track dependency that justifies the band.
2. Compute the full ranking score using the v1 weights in §1.3.
3. Boost cards where the underlying claim cites a vault `[SWARM_TARGET]` marker (this is what `vision_file_proximity` measures).
4. Submit the card via `BoardStore.create_card`. **Do not pre-suppress.** Let the facade enforce the threshold. This makes refusal centralized, audited, and consistent across all six noticers.
5. If the facade refuses with `ArjunaThresholdNotMet`, log the refusal to WitnessEvent so the operator can review what was *not* proposed and tune weights/thresholds with full visibility.

### 9.4 Override flow (operator only)

When the operator chooses to override (e.g., to surface a 0.30-band card they personally judge worth pursuing):

1. Operator (or admin) calls `BoardStore.create_card(..., override=ArjunaOverride(reason=…))`.
2. The `reason` field **must** name one of: external user, dataset, partner, measurable impact, or active-track dependency. Free-text reasons without a named target are rejected by the facade.
3. Override emits `control.posted` with event type `arjuna_override` (per `SWARM_BOARDSTORE_SPEC.md §7 Control event schema`).
4. The override is permanent in the audit stream — replay always shows it.

Noticers and other agents have **no** override path. This is enforced by RBAC in the facade.

### 9.5 Why centralize in the facade and not in each noticer

This is a change from earlier drafts of this document (which had noticers pre-suppress at 0.30). Centralizing in the facade gives us:

- **One threshold** all six noticers, all six agent kinds, and all surface paths (CLI, dashboard, Telegram, API) obey identically.
- **One audit stream** for every refusal and every override.
- **One tunable** (`arjuna_threshold` in operator config) instead of six noticer-local knobs.
- **No drift** between what a noticer thinks the threshold is and what the substrate enforces.

---

## 10. Migration Plan (per `SHAKTI_GINKO_ORGAN.md §11`)

| Phase | PR | Adds | Removes / Renames |
|-------|-----|------|-------------------|
| 2 (substrate) | this spec's land | `Noticer` base, `NoticerContext`, `NoticerReport` | none |
| 3 (noticers) | follow-up | MarketScanNoticer (refactor scout_daemon), ViabilityNoticer, OpportunityNoticer, IdeationNoticer, QualityNoticer | `scout_daemon` becomes deprecation shim |
| 4 (cleanup) | follow-up | TreasuryNoticer, NoticerScheduler CLI | drop scout_daemon shim |

No noticer ships until BoardStore facade lands (`SWARM_BOARDSTORE_SPEC.md`). Without the facade, noticers cannot enforce the notice-only contract via RBAC.

---

## 11. Open Questions

1. **Per-noticer model.** Should MarketScanNoticer use a smaller / cheaper LLM than QualityNoticer (the latter is rarely LLM-bound)? Probably yes — model selection per noticer.
2. **Vault read frequency.** VaultBridge polls vault files; how often? Currently 30 s for changes, full re-read every 6 h. Is this too aggressive?
3. **IdeationNoticer max=3.** Too restrictive? Too permissive? Operator should tune over first 30 days.
4. **CONTINUOUS for QualityNoticer.** Should we *also* CONTINUOUS-ify ViabilityNoticer, accepting more compute for tighter loops? Doc currently says TRIGGERED + 24 h fallback.
5. **Cross-noticer dedupe.** If MarketScanNoticer and OpportunityNoticer both surface the same external opportunity, what wins? Current spec: first-write-wins with merge. Better: operator-visible "agreement strength" indicator showing both noticers concur.
6. **Learned ranking.** Forbidden in v1. When (not if) we add it, what's the gating ADR look like? Probably ADR-007 (next after this PR).
7. **AutoProposer direct Darwin submission.** Codex flagged this at `SWARM_BOARDSTORE_SPEC.md §16 Open Question 5`: should `AutoProposer`'s existing direct Darwin / evolution submission be retired or gated behind cards? Our noticer roster (§2–6) implicitly assumes Darwin submissions flow through the BoardStore as proposal cards, so the operator can see and approve them. This needs an explicit operator decision before the Phase 3 noticer-roster PR lands.

---

## Appendix — File:Line Citation Index

- `dharma_swarm/auto_proposer.py:136+` — `AutoProposer` (existing notice-only precedent)
- `dharma_swarm/auto_proposer.py:51-67` — `ObservationType` + `ProposalSource` enums (analog of noticer-types)
- `dharma_swarm/revenue/scout_daemon.py:1-22` — existing scout daemon (refactor target for MarketScanNoticer)
- `dharma_swarm/revenue/intelligence.py`, `intel_parser.py` — sources MarketScanNoticer will reuse
- `dharma_swarm/cron_runner.py`, `cron_scheduler.py`, `cron_daemon.py` — scheduling infra NoticerScheduler wraps
- `dharma_swarm/stigmergy.py` — substrate signals OpportunityNoticer reads
- `dharma_swarm/fractal/fractal_room.py:80-89` — existing signal bus event types
- `dharma_swarm/fractal/fractal_room.py:248-303` — `evaluate_kill_conditions`, `evaluate_spinout_conditions` (used by QualityNoticer + ViabilityNoticer)
- `dharma_swarm/ginko_orchestrator.py:826-892` — `AUTONOMY_REQUIREMENTS`, `check_autonomy_advancement` (used by ViabilityNoticer)
- `docs/architecture/SHAKTI_GINKO_ORGAN.md` — organ spec (this doc's parent)
- `docs/architecture/VENTURE_CELL_LIFECYCLE.md` — lifecycle spec (kill/spinout semantics that noticers respect)
- `docs/architecture/SWARM_BOARDSTORE_SPEC.md` — Codex's substrate spec (PR #316; defines BoardStoreClient noticers consume, §8 Noticer Contract, §11 ARJUNA Gate Integration)
