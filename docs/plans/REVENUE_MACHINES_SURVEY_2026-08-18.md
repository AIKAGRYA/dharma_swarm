# Revenue Machines Survey — 2026-08-18

**Doc role:** research / decision-support. **Authority: none.** Companion to
`docs/plans/FIRST_FIRE_DECISION_DOSSIER_2026-08-18.md`. Produced by an
independent research agent (operator-directed, 2026-08-18) via external web
research (regulator sources, exchange fee schedules, academic studies —
citations inline as URLs) plus repo-fit analysis against `ginko_data.py`,
`ginko_brier.py`, and `capital_lab/`. Numbers are net-of-fees central
estimates with honest ranges; promotional sources are flagged; the operator
profile assumed is: US citizen (possible Japan residency flagged where it
changes an answer), solo, no sales conversations, capital tiers $1K/$10K/$50K.

## Ranked top-5 for this operator

1. **Kalshi systematic event trading, maker-side, long-tail markets** —
   CFTC-regulated, US-citizen-native; the swarm's Brier-scored calibrated
   forecasting IS the edge; taker fee ≈ 0.07·P·(1−P), maker fees near zero;
   realistic with a validated edge: $1K → $200–800/yr, $10K → $1.5–6K/yr,
   $50K → $5–15K/yr (long-tail capacity binds). Gate live dollars on the
   repo's own `edge_validated` bar (Brier < 0.125 over 500+ resolved,
   `ginko_brier.py:75`). Blowup mode: correlated miscalibration on one theme
   across many "independent" markets; tax treatment of event contracts is
   unsettled (report conservatively, keep per-contract receipts). Fit 9/10.
2. **Skill-sale layer: Collective2 publishing + Numerai/WorldQuant BRAIN
   submissions** — monetizes proven calibration with ~no capital; publisher-
   side of the Advisers Act line (15 U.S.C. §80b-2(a)(11)(D), Lowe v. SEC)
   provided signals stay impersonal and self-serve; realistic years 2–3 at
   moderate proven skill: $3–20K/yr, mode near zero year 1. Most robust
   family to a Japan move. Blowup: one public drawdown after subscribers
   arrive. Fit 8/10.
3. **Prediction-market picks-and-shovels** (Kalshi/Polymarket analytics,
   fee-aware execution tooling, the ledger itself packaged as a data
   product) — revenue uncorrelated with market direction; distribution must
   be product-led (the public ledger is the zero-conversation marketing
   artifact); mode $0–2K/yr, niche fit $5–30K/yr. Blowup: a year of
   engineering with zero distribution. Fit 6/10.
4. **Funding-rate / cash-and-carry basis harvest on CFTC-regulated US
   perps** (Coinbase nano perps, Kraken/Bitnomial, Kalshi BTCPERP — all
   newly US-legal 2026 under CFTC PR 9242-26) — structural carry paid by
   leveraged longs; model 4–10% net; $10K → $400–1K/yr, $50K → $2–5K/yr;
   skip at $1K; leverage cap ≤2x; degrades badly on a Japan move (~55%
   miscellaneous-income tax on the spot leg). Requires vigilance, not
   forecasting — the swarm's 24/7 monitoring is the edge. Blowup:
   liquidation on a squeeze; venue failure (the FTX collateral lesson).
   Fit 7/10.
5. **Slow-turnover systematic directional (trend/momentum), US-brokered
   (Alpaca/IBKR; IBKR best if Japan-resident)** — the compounding backbone
   only AFTER ranks 1–2 prove edge; professionals compound ~5% with 20%
   drawdowns (SG Trend Index); $50K tier central estimate $1.5–2.5K/yr.
   Pre-registration through the forward ledger prevents backtest-overfit
   deployment. Fit 6/10.

## Closed doors (with reasons)

- **Classic MEV / HFT / DEX-CEX arb** — 2/10: measured concentration (3
  searchers ≈ 75% of $233.8M extracted, arXiv 2507.13023); every axis
  (latency, capital, builder relationships) is one this operator is
  structurally last on. Carve-out already scored in rank 1: thin-book
  maker-side prediction-market making.
- **Outside-money fund structures ("agentic hedge fund")** — 2/10 now:
  RIA/ERA/CPO/CTA lanes all require filings plus raising money, which is a
  sales conversation by definition (doctrine-forbidden); a <$1M fund cannot
  pay its own legal costs. Own-capital prop trading needs no license at
  all. Revisit only after 2+ years of public ledger, with counsel.
- **DeFi yield at these tiers** — 3/10: ETH staking ~2.1–2.8% net has run
  below the 3-month Treasury (comparable in the repo's own FRED feed) while
  adding smart-contract/slashing/price risk; Ethena excludes US persons by
  its own terms — do not route around.
- **Darwinex Zero / eToro Popular Investor** — US-person access barred or
  impractical.

## What the forecast ledger feeds

The ledger is the hub: rank 1 consumes its calibrated probabilities as order
signals and its Brier gate as the go-live test; rank 2 sells its provenance;
rank 3 packages it as product and credibility; rank 5 uses it as forward
pre-registration against overfit. Rank 4 deliberately consumes no forecasts —
it is the diversifier that pays while the forecasting edge is in drawdown.

## Pre-registered failure modes (the three ways solo algo traders lose)

1. **Backtest overfitting deployed live** — expected out-of-sample return of
   an overfit strategy is negative, not zero (Bailey/Borwein/López de
   Prado/Zhu, Notices of the AMS 2014). Countermeasure in-repo: forward-only
   ledger gating (`ginko_brier.py` edge_validated).
2. **Overtrading and cost blindness** — most-active retail traders
   underperform ~6.5pp/yr; 97% of persistent Brazilian day traders lost
   money (Chague et al.); at <$10K volume, 0.60% taker fees turn daily
   turnover into a ~150%/yr fee donation. Countermeasure: maker-only and
   weekly-cadence defaults enforced by the risk governor.
3. **Leverage + counterparty/operational failure** — liquidation cascades on
   "neutral" positions and venue failures convert riskless carry into total
   loss. Countermeasure: leverage ≤2x, CFTC-regulated US venues only,
   `capital_lab` authority fences as the enforcement point.

## Jurisdiction note

Every number assumes US residency. A Japan move flips the crypto-heavy
machines (rank 4; crypto side of rank 5) to tax-hostile (~55% miscellaneous
income, no loss carryforward) and possibly closes Kalshi eligibility, while
leaving ranks 2 and 3 fully intact. If a Japan move is likely, weight toward
ranks 2–3 now.

*Full agent report with all inline citations retained in the session record
of 2026-08-18; this document is the condensed decision surface.*
