# Strategy Verdict — what's real, what's a mirage, what to build

> The digest of DEEP_STRATEGY_LIBRARY.md (14 source-grounded dossiers). Read this
> first. The library is the reference; this is the verdict.

## The one-paragraph truth

**Almost every famous "money-printer" strategy is decayed or crowded.** The retail
loop the IG-12 teaches (generate → backtest → report the Sharpe → profit) targets
*exactly* the strategies that no longer pay, because a strategy everyone knows is a
strategy that's been arbitraged away. What actually survives is three things: (a) a
few premia that live only in **capacity-constrained corners** where arbitrage stays
expensive; (b) the **methods**, which never decay because they're math, not trades;
and above all (c) the **discipline** — combining many decorrelated weak signals,
sizing them honestly, executing cheaply, and gating ruthlessly. *The durable edge is
not a strategy. It's the discipline.* Which is precisely what dharma is built to be.

## Verdict table — the 14 families

| Family | Honest verdict | What to do with it |
|---|---|---|
| **Trend / Time-Series Momentum** | Decayed less than most (deep futures, high capacity); real net Sharpe ~**0.3–0.5** with crisis-alpha convexity. *Vol-scaling does much of the "edge" (Kim-Tse-Wald).* | **Build — as a diversifier**, not a standalone winner. Honest about the modest Sharpe. |
| **Cross-sectional equity momentum** | **Heavily crowded/decayed.** Subsumed by factor-momentum (Ehsani-Linnainmaa). | Skip as standalone; only as part of a factor combo. |
| **Mean-reversion / stat-arb** | Distance-pairs **dead**; cointegration survives in **mid-cap/international/futures spreads**; short-term reversal is the **most crowded + most dangerous** (Aug-2007 quant quake). | Build only in the un-crowded corners; never naive daily reversal. |
| **Factor zoo (value/quality/profitability/investment)** | **Crowd the least**; modest, durable-ish. Momentum crowds hardest; low-vol/BAB got smart-beta-crowded; **size is effectively dead**. | **Build — value+quality+profitability combo.** This is the durable factor core. |
| **Carry (FX/commodity/bond/vol)** | FX carry substantially decayed (low rate dispersion); **vol-carry is a Volmageddon trap** (Feb 2018). Diversification real in calm, **illusory in tails**. | Bond-carry/roll-down is the cleanest; treat vol-carry as hazardous. |
| **Volatility / options** | VIX-roll & short-vol **heavily crowded and blow-up-prone**; gamma-scalping is an **execution edge** (needs infra); tail-hedging episodically crowded. | Mostly **not** for a paper-first fund. Vol-targeting yes (as an overlay, with eyes open). |
| **Market microstructure / market-making** | The math doesn't decay, but spread-capture is **fully crowded by HFT**; queue-racing is a colocation arms race. **Micro-price = an estimator everyone uses.** | **Not** a paper-first strategy. Adopt micro-price as plumbing only. |
| **ML / AI alpha** | The **techniques** (triple-barrier, meta-labeling, fractional-diff) **don't decay — adopt freely.** LLM alpha-mining has **high self-acknowledged decay**; RL is overfitting-as-mirage. | **Adopt the methods; distrust the "LLM prints alpha" claims.** |
| **Macro / cross-asset** | TSMOM partially decayed; multi-style real-but-modest; business-cycle *timing* never-robustly-there; **bond carry+roll transparent & durable**. | Build the transparent, low-turnover pieces; avoid fitted regime-timing. |
| **Crypto-native** | Funding-rate carry **heavily decaying** (spot-ETF 2024); basis trade **severely crowded** (2025 unwind); cross-exchange arb is **HFT**; **AMM LP's "yield" is offset by LVR** (a structural cost, not edge). | Mostly crowded/infra-gated. AMM-LP only with LVR modeled honestly. |
| **Portfolio construction / sizing** | Estimators (**Ledoit-Wolf shrinkage**) don't decay — adopt. **HRP outperformance fragile/overfit**; risk-parity decayed post-2021 (stock-bond corr flip); vol-targeting is itself a crowding/feedback risk. | **Adopt shrinkage + signal-combination discipline.** Don't believe HRP magic. |
| **Backtest rigor (DSR/PBO/CPCV/Harvey-Liu/MinBTL)** | **None decay — they're the gates.** (Caveat: PBO's overlapping paths aren't independent — a known critique.) | **This is the moat. Build it first** (R3). |
| **Reading list** | Confirms the cross-family decay verdicts; gives the priority order to read the rest of the iceberg. | The map for ongoing depth. |

## What to actually build (priority order)

1. **The rigor gate first (R3)** — Deflated Sharpe + Purged/Combinatorial CV + the
   trial-count ledger + a real net-of-cost engine (square-root impact). *Nothing
   graduates without it.* This is the one thing that never decays and that the whole
   field is missing.
2. **A durable, un-crowded alpha core** — value+quality+profitability factors, trend
   as a diversifier, mean-reversion only in capacity-constrained corners. Modest,
   honest, real.
3. **The combiner + sizing discipline (R5 + portfolio)** — Ledoit-Wolf shrinkage,
   z-score/decorrelate/equal-risk combination of many weak signals, fractional-Kelly
   sizing. The "Fundamental Law" edge: breadth × honest IC, not one magic signal.
4. **Adopt the methods freely** (they don't decay): triple-barrier/meta-labeling,
   fractional-diff, Almgren-Chriss execution, micro-price plumbing.
5. **Defer the infra/crowded games**: HFT market-making, latency arb, short-vol,
   crypto basis — not for a paper-first fund.

## Why this *validates* our architecture (the payoff)

The research independently confirms the north-star thesis. The durable edge is **not
a strategy — it's the discipline of decorrelated combination + ruthless honesty.**
That is exactly dharma's design: multi-model decorrelation (R5) + the anti-Goodhart
evidence gate (R3). We are not betting the fund on a magic strategy that will be
crowded out; we are building the **discipline the whole field lacks.** The strategies
are commodities; the BS-detector and the honest combiner are the moat. We were
already building the right thing — now we have the literature proving it.

---
*Full mechanics, formulas, parameters, sources, and go-deeper pointers per family:
DEEP_STRATEGY_LIBRARY.md. Seeds: STRATEGY_SEEDS_IG_12.md. Architecture:
NORTH_STAR_ARCHITECTURE.md. Plan: ROADMAP_TO_PARITY.md.*
