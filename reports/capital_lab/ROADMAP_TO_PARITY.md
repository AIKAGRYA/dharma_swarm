# capital_lab — Roadmap to Parity (and Beyond) the 5 Reference Systems

> Companion to NORTH_STAR_ARCHITECTURE.md. The north-star is the *what* (the
> 6-layer architecture). This is the *plan*: a phase-gated, measurable route to
> reach — then surpass — five named reference systems, with honest dependencies
> and timelines. Every gate is a concrete, checkable condition, not a vibe.

## The five bars we are measuring against

| # | System | What it is | Bar it sets |
|---|--------|-----------|-------------|
| A | Self-Driving Portfolio (Ang et al., arXiv 2604.02279, Apr 2026) | ~50-agent governed asset-allocation pipeline | best *agentic architecture* |
| B | TradingAgents (Tauric, arXiv 2412.20138) | 7-role multi-agent trading desk | best *agentic research-desk* |
| C | Microsoft RD-Agent(Q) (arXiv 2505.15155) | autonomous quant factor/model R&D loop | best *autonomous strategy discovery* |
| D | Numerai | real-money crowd-ML fund, anti-overfitting tournament | the *real operating fund* bar |
| E | Two Sigma / Renaissance | institutional systematic gold standard | the *world-class* summit |

Critical honesty note from the precedent study: A, B, C are **research systems
without live capital**, and the published agentic-trading returns are largely a
*mirage* — "Profit Mirage" (2510.07920) and a 20-year study (2505.07078) found
FinMem/FinAgent-class systems produce **no statistically significant alpha**
(p>0.34); buy-and-hold beats them. So "parity" with A/B/C means *architectural +
rigor parity*, and our differentiator is to **not reproduce the mirage**.

## Current honest state (2026-06-06)

- Built + verified, fixture-only: R0 risk governor (real detect-and-halt), R1
  six-layer typed contracts. 27/27 tests. Stable lane `capital-lab/build`.
- Goal A (alpha evidence): **41/100, clean=false, 25 blockers** (6 code, 15 data, 4 operator).
- Goal B (execution): fixture membrane with real risk now wired.
- **No market data. No validated strategy. No real broker. No capital. No track record.**
- **#1 risk — provider famine:** only GLM (zai_coding) + OpenRouter live; Anthropic
  no credit. Our entire edge is *multi-model decorrelation* and right now we have
  ~1 reliably-live family. Without 2–3 funded, decorrelated families, the swarm
  thesis is crippled. **This is the single most important near-term dependency and
  it is partly an operator decision (fund the keys).**

---

## Phase 1 — Build the honest brain  *(reaches architectural+rigor parity with A, B, C)*

Goal: a strategy the system invents *survives a leakage-proof gauntlet on real
(free-tier) data* — i.e., we have a research engine that **cannot fool itself.**
Almost entirely in our control; no paid data, no broker, no capital required.

**Rungs:** R2 (risk FSM + price-drift reconciliation) · R3 (honest-evidence gate)
· R4 on free data (PIT security-master, as-of joins, lineage hashes; Stooq +
Tiingo-free + Zipline-Reloaded) · R5 (5-stage agent research graph).

**Parity gates (measurable, must all hold):**

- **vs C (RD-Agent):** the system autonomously proposes ≥1 strategy that passes
  the full gauntlet — Combinatorial Purged CV + Deflated Sharpe Ratio **> 0.95** +
  all **6 leakage traps execute and pass** + walk-forward OOS **≥ 3 windows** +
  tamper-evident trial-count (N) ledger honest. **Goal A: 41 → ≥80, clean=true, on free data.**
- **vs B (TradingAgents):** the 5-stage graph (analysts → bull/bear debate →
  trader → risk-team → fund-manager) runs end-to-end producing an
  Insight→PortfolioTarget→RiskAdjustedTarget→Order chain, with a debate-health
  floor (min-disagreement) + a first-class **no-trade** option, evaluated
  **leakage-free (post-knowledge-cutoff data, StockBench-style).**
- **vs A (Self-Driving Portfolio):** the full pipeline integrates — regime →
  multi-model estimators → construction → RiskGovernor → telos-gate IPS — with an
  **adversarial-diversifier** cross-check, every step receipted.

**Dependencies:** free data (now), and **≥2–3 decorrelated live model families**
(the famine — operator-gated). **Honest effort: weeks-to-a-few-months**, gated
mainly on provider credit, not money or time.

---

## Phase 2 — Prove it, then touch real money small  *(reaches parity with a real operating shop / early D)*

Goal: a real (paper) broker track record that survives the honesty gates, then
**graduated tiny-live** by explicit operator lease.

**Rungs:** R6 (NautilusTrader as the execution/backtest spine — research-to-live
parity, deterministic order IDs, event-sourced ledger) · R7 (Alpaca-paper +
IBKR-paper behind the authority fence; drop-copy reconciliation) · R8 entry
(smallest live size).

**Parity gates:**

- **vs D (Numerai):** **3–6 months of *paper* track record** through a real paper
  broker whose live-reconciled results survive Deflated-Sharpe + drift gates →
  then a real (small) live track record *begins* under an operator
  capital-authority lease.

**Dependencies:** a data decision (free → likely Norgate/Sharadar paid when
promotion-grade is needed), free paper-broker accounts, **your lease for tiny-live**,
small capital, and **calendar time for the paper record.** Honest effort:
**several months**, and the paper-record clock cannot be compressed.

---

## Phase 3 — Become a real fund  *(reaches D fully, then climbs toward E)*

Goal: real assets under management, a multi-strategy decorrelated book, a credible
multi-year live track record.

**Gates:** sustained live track record (Deflated Sharpe stable out-of-sample over
**≥12 months live**), multiple decorrelated validated strategies, capacity/cost
modeling proven at size.

**Dependencies:** capital, time, talent, promotion-grade data — the hard things.
**Honest horizon: 1–3+ years.** A credible track record **cannot be rushed**;
this is the structural moat A/B/C don't have and D/E earned with calendar time.
Naming it honestly: we do not shortcut Phase 3.

---

## Where we go *beyond* the five

We can lead on the axis the whole field is weak on, *before* we are the biggest or
most profitable — and it is defensible:

1. **The most honest fund** — anti-Goodhart as a structural runtime gate (deflated
   truth, tamper-evident N-ledger, leakage gauntlet as a *blocker*). A/B/C report
   mirages; we report the deflated number or refuse to report.
2. **The most decorrelated** — genuinely different model families (GLM/DeepSeek/
   Kimi/Opus) in adversarial debate; everyone else runs one family (correlated herding).
3. **The most auditable** — a receipt for every decision (autonomy_spine ledger),
   graduated autonomy by operator lease; not a black box.
4. **The most aligned** — telos-bound: returns flow to Jagat Kalyan. A fund with a
   conscience, not just a P&L.

## Immediate next 3 moves (fully in our control)

1. **R2** — risk FSM {ACTIVE,REDUCING,HALTED} + price-drift reconciliation +
   duplicate-economics guard. *Building now, via autonomy_spine with hermes-m5 (GLM)
   as the decorrelated adversary.*
2. **R3** — make Goal A's 6 leakage traps actually execute + add Deflated Sharpe +
   the tamper-evident N-ledger. Move Goal A 41 → toward 80 on free data.
3. **Provider decorrelation** — get ≥2–3 model families funded + live. *Operator
   move; the #1 unblock for the entire decorrelated-swarm thesis.*

## How this gets executed (the swarm, not a soloist)

Each rung runs as an `autonomy_spine` mission (Planner→Builder→Adversary→Verifier→
Reporter) in this lane, receipts in `~/.dharma/autonomy_spine/`, with the Adversary
routed to a *different model family* (hermes-m5/GLM) for genuine decorrelation —
not Opus grading Opus. That is the convergence to Codex's pattern and the fund's
own thesis.

---
*Honest one-line status: ~5–8% of a real fund (no data/alpha/execution/capital/
record), but at the frontier on honesty+decorrelation+auditability. Phase 1 is
ours to walk now; Phase 2 needs a broker + your lease; Phase 3 needs capital +
years. No step is hand-waved.*
