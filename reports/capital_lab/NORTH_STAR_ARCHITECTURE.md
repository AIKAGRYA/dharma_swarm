# capital_lab — North-Star Architecture

> A world-class, future-proof, autonomous agentic hedge fund built on dharma_swarm.
> Operator mandate 2026-06-06: industry-grade, integrating and surpassing every
> precedent. Not a toy, not a stub. Grounded in an 8-lane precedent study
> (Renaissance/Two Sigma reference architecture, López de Prado anti-overfitting
> canon, NautilusTrader execution, PIT data lineage, the 2026 agentic-fund
> literature). This file is the build spine; every increment executes against it.

## The thesis — why this can be world-class, not just another bot

The published agentic funds (TradingAgents, FinMem, RD-Agent(Q), Ang et al.'s
Self-Driving Portfolio, Apr 2026) are real and capable — but the literature's
own headline returns are **fraudulent under scrutiny**: "Profit Mirage"
(arXiv 2510.07920) shows FinMem/FinAgent gains evaporate once look-ahead and
data-leakage are corrected, and <28% of finance-LLM papers even discuss one bias.
Every precedent optimizes a **single scalar** (cumulative return / Sharpe) — the
textbook Goodhart trap — and most run a **single LLM family** (correlated failure,
debate-sycophancy herding).

dharma_swarm's genuine, structural edge sits exactly in those gaps:

1. **Anti-Goodhart as a runtime governance layer, not a training footnote** —
   telos veto (11 gates) + kernel axioms (25) + multi-dimensional fitness +
   honest-uncertainty/abstain as a first-class, separately-rewarded output. The
   same "label-not-behavior" pathology this session caught in the kill-switches
   is the field-wide failure mode; we make refusing-to-overfit a *gate*.
2. **Multi-model decorrelation as real signal diversity** — GLM-5 / DeepSeek /
   Kimi-K2 / Opus are genuinely decorrelated substrates (Krogh-Vedelsby:
   `E_ensemble = E_mean − E_diversity`). Precedents ensemble one family; we don't.
3. **Contemplative epistemic discipline** — pratikraman/samayik/anekantavada map
   onto leakage-immunity, adversarial self-audit, and never-collapse-to-one-view.
   VIVEKA audits a backtest claim *and* the live decision with the same lens.
4. **Receipts + graduated autonomy native to the substrate** — the autonomy_spine
   ledger, witness logs, and capital-authority leases already exist; we don't
   bolt on governance, we inherit it.

## The reference architecture (6 layers, typed interfaces, strict separation)

The institutional amateur/professional divide is **separation of concerns over
typed contracts**: a layer emits a typed object and must not know how the next
layer works. Adopt the QuantConnect-LEAN/Nautilus contract verbatim, mapped onto
dharma's existing agent/board substrate:

| # | Layer | Emits | dharma substrate it maps onto |
|---|-------|-------|-------------------------------|
| 1 | **Data / Ingestion** | `Universe` | PIT/bitemporal store + feature store; chetana provenance + witness lineage |
| 2 | **Research / Alpha** | `Insight` (dir, magnitude, confidence, period) | multi-model council (analyst fan-out → bull/bear debate); free models score, Opus arbitrates |
| 3 | **Portfolio Construction** | `PortfolioTarget` (target weights) | the board / sheaf; risk-model-aware optimizer (MV/Black-Litterman/HRP) |
| 4 | **Risk Management** | `RiskAdjustedTarget` (validated/clamped) | **RiskGovernor** (shipped) + TelosGatekeeper veto; the mandatory gate |
| 5 | **Execution** | `Order` → fills | `broker_paper_membrane` (fixture) → NautilusTrader OMS → paper broker |
| 6 | **Ops / Governance** | receipts, promotions | autonomy_spine ledger, capital-authority leases, graduated-autonomy ladder |

Layers 2–6 communicate **only** through these objects. An execution agent must
not know what signal produced an order; an alpha agent must not know sizing.

## Differentiating doctrine (the surpass layer, wired as gates)

- **Leakage-immunity as a runtime gate** — lookahead / survivorship /
  feature-availability / cutoff-memorization encoded as telos-style guards that
  *block* a strategy from advancing. PIT/bitemporal (`knowledge_ts ≤ decision_ts`)
  so the model *cannot* see the future. Lineage hash (SHA-256 of raw + feature
  parquet) pinned into every backtest result — a result is unfalsifiably tied to
  the exact dataset it saw.
- **Honest significance** — Deflated Sharpe Ratio (never raw SR) gated on
  `DSR > 0.95`; PBO via CSCV/CPCV; `MinBTL = 2·ln[N]/E[max_N]` hard gate;
  **tamper-evident append-only ledger of N** (every config every agent ever
  evaluated — the most-cheated number in quant). Anti-Goodhart on N *itself*.
- **PGE separation** — a strategy-proposing Generator structurally isolated from
  an adversarial multi-model Evaluator that *never self-grades* (this session's
  re-verification was exactly this; it found the theater the builder's self-grade
  missed).
- **Risk-constrained signal envelope** — FinRL-DeepSeek's hard law: LLM conviction
  enters ONLY as a bounded multiplier inside a CVaR/CPPO objective, never directly
  scaling raw position size.

## Build sequence (verified-increment ladder; effort tags from the precedent study)

Each rung is one TDD increment with a named green-condition; no rung promotes on a
self-graded boolean.

- **R0 — Risk Governor (SHIPPED 2026-06-06).** Real detect-and-halt controls
  (order-rate, position, exposure, heartbeat, stale-data, drawdown); drills that
  inject a condition and prove `observed > limit` + clean negative control +
  enforced halt. 21/21 tests. *This is the field's missing piece, built first.*
- **R1 — `[now_offline]` 6-layer typed contracts** (`capital_lab/contracts.py`):
  `Universe / Insight / PortfolioTarget / RiskAdjustedTarget / Order` as frozen
  typed objects. The executable spine.
- **R2 — `[now_offline]` RiskGovernor → TradingState FSM** `{ACTIVE, REDUCING,
  HALTED}` (Nautilus RiskEngine pattern): REDUCING accepts only risk-reducing
  orders; cancels always pass; port Lean `MaximumDrawdownPercentPortfolio`. Plus
  price field on `OrderState`/snapshot → price-drift reconciliation +
  duplicate-economics mismatch guard.
- **R3 — `[now_offline]` Honest-evidence gate** (Goal A): real leakage-trap
  execution; mlfinlab/skfolio PurgedKFold+embargo / CPCV; Deflated Sharpe; the
  tamper-evident N-ledger. Turns `implemented:True` labels into real pass/fail.
- **R4 — `[now_offline]` PIT/bitemporal data core**: security-master (immutable
  `security_id` + ticker map-file, never-delete delisted), raw-immutable +
  adjusted-on-read, as-of-join feature layer, dataset lineage hash. Free tier:
  Stooq + Tiingo + Zipline-Reloaded.
- **R5 — `[now_offline]` Agentic research graph**: TradingAgents 5-stage
  (analyst-fanout → bull/bear debate → trader → risk-team → fund-manager) on the
  existing council; debate-health metrics (min-disagreement floor); `no-trade`
  as a first-class calibrated output.
- **R6 — `[needs_data]` NautilusTrader integration** as the execution/backtest
  spine (research-to-live parity, deterministic ClientOrderId, event-sourced
  ledger, ParquetDataCatalog). Wrap dharma agents as Nautilus Strategies/Actors.
- **R7 — `[needs_data]` External paper-broker membrane** (Alpaca paper + IBKR
  paper) behind the authority fence; drop-copy reconciliation loop; real external
  receipts. *First contact with a real (paper) broker.*
- **R8 — `[needs_capital]` Graduated live** — only by explicit operator
  capital-authority lease, smallest size, every promotion gated on R3 evidence.

## The hard safety frame (never relax without an operator lease)

Graduated autonomy ladder (CSA-mapped): **fixture → paper → small-live → scaled.**
At every rung: `live_readiness`, `live_authority`, `broker_write_authority`,
`clean` stay false/0 until *receipt-backed* evidence clears the gate. The deepest
fence is structural — fixture-only, imports-no-broker, hardcoded zeros — and the
Hyperliquid live surface is *quarantined and not on this machine*. **Only the
operator grants live authority. Never the fleet.** Anti-Goodhart is the point:
a beautiful backtest on leaked data, or a kill-switch that flags-but-doesn't-halt,
must be *unable* to promote.

---
*Grounding: 8-lane precedent study (workflow `hedge-fund-precedent-intelligence`,
2026-06-06). Status: R0 shipped + verified. Ledger: mission
`20260605T141918Z-goal-b-...-continuation`, receipts r-aa4734735e022dda,
r-89848929401cde50.*
