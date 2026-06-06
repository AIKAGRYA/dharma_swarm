# Strategy Seeds — the IG "12 AI Trading Prompts" (the seed, not the substance)

Source: Instagram, `stics.ai` ("Claude Cowork Is Making Trading Research More
Accessible"), captured by operator 2026-06-06. These are **retail-grade
single-LLM prompts** — useful as a coverage map of the fund stack, but they are
the *tip of the iceberg*. Each is the naive version of a layer whose real depth
lives in the academic + practitioner literature (see DEEP_STRATEGY_LIBRARY.md,
produced by the deep-research sweep). Honest note: "generate a strategy, then
backtest and report the Sharpe" is exactly the **Profit Mirage** our R3 gate exists
to prevent.

| # | IG prompt | Our stack layer | Our rigorous version adds |
|---|-----------|-----------------|---------------------------|
| 1 | Strategy Generation | R5 alpha research | multi-model debate, no-trade option, leakage-free eval |
| 2 | Backtesting | **R3 honest-evidence** | CPCV, **Deflated** Sharpe, PIT data, N-ledger |
| 3 | Risk-Reward Analysis | R3 / risk | tail risk (CVaR), not just reward/risk ratio |
| 4 | Market Regime Detection | risk / portfolio | HMM/ensemble regime, limits auto-tighten |
| 5 | Multi-Factor Strategy | R5 alpha | the real factor zoo + factor-crowding/decay checks |
| 6 | Strategy Optimization | (danger zone) | optimization IS Goodhart — gated by PBO/DSR |
| 7 | Portfolio Construction | portfolio | MV/Black-Litterman/HRP/risk-parity/Kelly, not just "allocation %" |
| 8 | Trade Setup Generation | execution | real pre-trade risk gate + cost/impact model |
| 9 | Monte Carlo Simulation | R3 robustness | bootstrap + combinatorial paths, not one MC run |
| 10 | Drawdown Analysis | risk governor | the real max-loss/drawdown kill-switch (shipped R0) |
| 11 | Macro-Based Strategy | R5 alpha (macro) | cross-asset risk premia, carry, real macro factors |
| 12 | Alpha / Edge Detection | R5 alpha | the actual sources of edge (microstructure, behavioral, crowding) |

The point of the seed: it confirms the *coverage* of a full fund stack. The build
loads the *depth* from the real literature, not these prompts.
