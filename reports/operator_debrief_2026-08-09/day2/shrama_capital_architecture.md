# Shrama Capital — Architecture & Platform Dossier

*Research + architecture deliverable, 2026-08-09. Repo: `/home/user/dharma_swarm`. All repo claims cite `file:line`; all platform claims carry a source URL. Jurisdiction unknown — flagged wherever it matters.*

---

## 1. What already exists in the repo, and what it proved

Shrama Capital does not start from zero. The `capital_lab` lane already built and verified the safety-critical bottom half of a fund.

### 1.1 The north-star spine

- `reports/capital_lab/NORTH_STAR_ARCHITECTURE.md:38-56` — a 6-layer reference architecture (Data → Alpha → Portfolio → Risk → Execution → Ops/Governance) with typed inter-layer contracts, explicitly mapped onto dharma substrate (council for alpha, RiskGovernor + TelosGatekeeper for risk, autonomy-spine ledger for receipts).
- `reports/capital_lab/NORTH_STAR_ARCHITECTURE.md:77-113` — a verified-increment build ladder R0–R8: R0 (Risk Governor) SHIPPED; R1–R5 offline-buildable; R6–R7 need data/broker; R8 (live) only by explicit operator capital-authority lease.
- `reports/capital_lab/NORTH_STAR_ARCHITECTURE.md:114-123` — the hard safety frame: graduated autonomy ladder **fixture → paper → small-live → scaled**, with `live_readiness=0`, `live_authority=false`, `broker_write_authority=false` until receipt-backed evidence clears each gate. "Only the operator grants live authority. Never the fleet."
- `reports/capital_lab/NORTH_STAR_ARCHITECTURE.md:10-36` — the anti-Goodhart thesis: the published agentic-fund literature's returns collapse under leakage correction ("Profit Mirage", arXiv 2510.07920, cited at line 15), so the differentiator is runtime leakage gates, multi-dimensional fitness, and multi-model decorrelation — not a better backtest.

### 1.2 Shipped code (all tests pass: 21/21, run 2026-08-09)

`python3 -m pytest tests/test_capital_lab_risk_governor.py tests/test_capital_lab_broker_paper_membrane.py tests/test_capital_lab_alpha_evidence.py -q` → **21 passed**.

- **Typed contracts** — `dharma_swarm/capital_lab/contracts.py:7` defines the pipeline `Universe -> Insight -> PortfolioTarget -> RiskAdjustedTarget -> Order` as frozen dataclasses (`Insight` at `contracts.py:87`, `PortfolioTarget` at `:121`, `RiskAdjustedTarget` at `:141`, `Order` at `:169`). `Direction.FLAT` (`contracts.py:37`) makes *abstain / no-trade* a first-class alpha output. `TradingState {ACTIVE, REDUCING, HALTED}` (`contracts.py:50`) is the canonical kill-switch substrate.
- **Risk kernel** — `dharma_swarm/capital_lab/risk_governor.py:76` (`RiskGovernor`): real detect-and-halt controls — order-rate, per-symbol position, gross exposure, drawdown (`risk_governor.py:163-166`), heartbeat timeout, stale market data — with an operator-configured `RiskLimits` envelope (`risk_governor.py:42-53`). Once tripped it blocks all subsequent orders until explicit operator reset (`risk_governor.py:1-12`). Drills inject a real adverse condition and prove `observed > limit` plus a clean negative control (`risk_governor.py:265` runs drills at `max_drawdown_fraction=0.10`).
- **Paper-execution membrane** — `dharma_swarm/capital_lab/broker_paper_membrane.py:1-6`: fixture-only, imports no broker SDK, never signs payloads. Hard-coded authority zeros at `broker_paper_membrane.py:24-27` (`LIVE_READINESS=0`, `LIVE_AUTHORITY=False`, `BROKER_WRITE_AUTHORITY=False`, `CLEAN=False`). Full order lifecycle `submit/ack/partial_fill/full_fill/cancel/reject/expire` (`broker_paper_membrane.py:32-40`), deterministic idempotent client order IDs, ledger↔snapshot reconciliation, duplicate/reject/expire drills.
- **Alpha-evidence membrane** — `dharma_swarm/capital_lab/alpha_evidence.py:1-6`: evidence-only packets for provider lineage, leakage traps, walk-forward gates, alpha graveyard, institutional scorecard; grants no trading authority (`alpha_evidence.py:26-29`: `LIVE_READINESS=0`, `CAPITAL_PERMISSION="none"`).

### 1.3 What the prior missions proved (and honestly failed to prove)

- **Goal B (paper membrane)** — independent adversarial re-adjudication (`reports/capital_lab/goal-b-broker-paper-execution-membrane-continuation-20260605T141918Z/verifier_readjudication_20260606T.md:22-27`) confirmed the safety invariants are *defensible*: the membrane imports no broker SDK, the false/zero constants are hard-coded, and no live Hyperliquid key/order surface was found on disk. Lifecycle parity: **confirmed** for all 7 events (same file, lane table). Known honest gaps: the AST authority fence is name-match-only and bypassable (overclaimed, but not load-bearing), and dedup is id-string-only (a footgun only on a future real-broker route).
- **Goal A (alpha evidence)** — closed *blocked-partial* (`reports/capital_lab/goal_a_12h/GOAL_A_CLOSEOUT_20260606T023150Z.md:7-11`, `completion_claim: false`). Blockers at `:49-58`: no PIT provider receipt, no lineage hashes, leakage traps present but not passed, zero walk-forward OOS windows. Lesson recorded at `:68-73`: fix provider/data lineage before any strategy work — "not strategy score inflation."
- **Operator posture** — `reports/capital_lab/goal-b-.../operator_brief.md:9-17`: the standing verdict is *unclean* until a verifier records terminal proof; no live orders, keys, or profit claims were ever made.

### 1.4 Organism substrate Shrama Capital inherits

- **Evolution engine** — `DarwinEngine` (`dharma_swarm/evolution.py:271`), diversity-preserving selection via `MAPElitesGrid` (`dharma_swarm/archive.py:354`).
- **Safety gates** — `TelosGatekeeper` (`dharma_swarm/telos_gates.py:233`); gate-check witness JSONL under `~/.dharma/witness/` (CLAUDE.md "State directory").
- **Quality-weighted aggregation** — `dharma_swarm/ginko_brier.py` (CLAUDE.md "Ensemble principle").

**Net:** the repo has a verified risk kernel, a verified paper-order lifecycle, typed layer contracts, and a receipts/verifier culture. What it does *not* yet have: real market data with clean lineage (Goal A blocker), any external broker/paper connection (R7 not started), and the lab/agent organizational layer this document designs.

---

## 2. Architecture: 5 labs, one risk kernel, paper-first, evolving agents

### 2.1 Shape

```
                 ┌────────────────────────────────────────────┐
                 │        SHRAMA CAPITAL (operator root)      │
                 │  capital-authority leases · promotion gate │
                 └───────────────┬────────────────────────────┘
        ┌───────────┬────────────┼────────────┬───────────────┐
   Lab 1 Vega   Lab 2 Nadi  Lab 3 Setu   Lab 4 Ghata     Lab 5 Tula
   (momentum)   (on-chain)  (funding-arb) (event-driven)  (market-making)
        │           │            │            │               │
        └───────────┴─────┬──────┴────────────┴───────────────┘
                          ▼
              SHARED RISK KERNEL (RiskGovernor + TelosGatekeeper)
                          ▼
              EXECUTION MEMBRANE  (fixture → paper → small-live)
                          ▼
              RECEIPTS LEDGER (append-only, hash-chained)
```

Each lab is one **evolving, trackable research agent** (a genome: prompt + feature set + model + parameters) plus a frozen harness the agent cannot modify. Labs communicate with the rest of the system **only** through the typed contracts (`contracts.py:7`): a lab emits `Insight`s; it never sizes, never orders. This is the existing north-star separation (`NORTH_STAR_ARCHITECTURE.md:54-56`) applied at the lab level.

### 2.2 Lab charters

| Lab | Codename | Mandate | Primary venue class | Data needs | Horizon |
|---|---|---|---|---|---|
| 1 | **Vega** — Momentum / trend | Cross-sectional + time-series momentum on liquid crypto majors and, later, equity ETFs. Explicit no-trade regime detection. | Spot CEX (Coinbase/Kraken); equities via Alpaca | Daily/hourly OHLCV, clean PIT | days–weeks |
| 2 | **Nadi** — On-chain flows | Exchange net-flows, stablecoin issuance, whale-wallet clustering, DEX volume as leading indicators. Research-heavy; expected lowest initial hit-rate. | Spot CEX for expression | On-chain data (public RPC / free tiers), CEX flow proxies | days |
| 3 | **Setu** — Funding-rate / basis arb | Perp funding vs spot basis; cash-and-carry. Delta-neutral by construction — the *risk-teaching* lab: its edge is execution and fee math, not direction. | Perp DEX (Hyperliquid/dYdX **jurisdiction-permitting**, §3) or Kraken Futures demo | Funding-rate history, basis curves | hours–days |
| 4 | **Ghata** — Event-driven | Scheduled events: token unlocks, upgrades, listings, macro prints. Thesis-per-trade is mandatory and pre-registered (thesis-hit-rate is directly measurable). | Spot CEX; options later | Event calendars, unlock schedules | hours–days |
| 5 | **Tula** — Market-making / liquidity | Passive two-sided quoting on one liquid pair in *paper only* for a long time; inventory-risk control is the research object. Highest operational risk; last to ever go live. | Paper/testnet only initially (Binance Spot Testnet, Kraken Futures demo) | L2 order-book data | seconds–minutes |

Charter rules common to all five:
- One agent per lab, one genome per agent, identity tracked in the receipts ledger (agent id + genome hash on every `Insight`; `Insight.source_agent` already exists — `contracts.py:97`).
- Every `Insight` must carry `knowledge_ts` (`contracts.py:99`) — the PIT/leakage gate from `NORTH_STAR_ARCHITECTURE.md:60-64` applies to live decisions, not just backtests.
- A lab may emit `Direction.FLAT` (`contracts.py:37`) and is *rewarded* for calibrated abstention (see fitness, §2.4).
- Labs own research; they never touch keys, sizing, or the execution membrane.

### 2.3 Shared risk kernel — one, not five

A single `RiskGovernor` instance (`risk_governor.py:76`) sits between all portfolio targets and the membrane, with per-lab sub-limits layered inside one fund-level envelope (`RiskLimits`, `risk_governor.py:42-53`):

- Fund-level: max gross exposure, max drawdown fraction, order-rate cap, heartbeat + stale-data timeouts (all shipped controls).
- Per-lab: capital allocation cap (e.g. each lab ≤ 20% of paper NAV initially), per-symbol position cap, per-lab kill switch that flips that lab's `TradingState` to `REDUCING` (`contracts.py:50-57`) without halting siblings.
- TelosGatekeeper veto (`telos_gates.py:233`) applies to promotion decisions (paper→live) — the anti-Goodhart layer from `NORTH_STAR_ARCHITECTURE.md:23-27`.
- Once tripped, only *operator* reset — already the shipped semantics (`risk_governor.py:1-12`).

### 2.4 PAPER TRADING FIRST — the hard gate

This is not a preference; it is the existing graduated-autonomy ladder (`NORTH_STAR_ARCHITECTURE.md:116-123`) made concrete:

1. **Rung 0 — fixture**: today's state. `broker_paper_membrane.py` only; no network.
2. **Rung 1 — external paper**: real broker paper APIs (Alpaca paper, IBKR paper, Kraken Futures demo — §3). Promotion gate from Rung 0: Goal A's data-lineage blockers closed (`GOAL_A_CLOSEOUT_...md:49-58`), plus lifecycle + reconciliation receipts against the *external* paper venue (the R7 spec, `NORTH_STAR_ARCHITECTURE.md:108-110`).
3. **Rung 2 — small-live**: only by an explicit written operator capital-authority lease naming a dollar cap; requires ≥ 90 calendar days of Rung-1 receipts for that lab and its fitness gate (below) green. `live_readiness`/`live_authority`/`broker_write_authority` stay hard-coded false until this lease exists (`broker_paper_membrane.py:24-27`).
4. **Rung 3 — scaled**: out of scope for this document; never before 12 months of receipts.

**No lab skips a rung. A rung is granted per-lab, not fund-wide.**

### 2.5 Evolution loop with multi-dimensional fitness

Run each lab's agent through `DarwinEngine` (`evolution.py:271`) with `MAPElitesGrid` (`archive.py:354`) so selection preserves behavioral diversity — the repo's standing ensemble principle (CLAUDE.md, "Ensemble principle"). Generation cadence: weekly on paper receipts.

**Fitness is a vector, never a scalar** (the Goodhart trap the north star names at `NORTH_STAR_ARCHITECTURE.md:17-19`):

| Dimension | Measure | Gate |
|---|---|---|
| Return quality | Deflated Sharpe Ratio, not raw PnL (`NORTH_STAR_ARCHITECTURE.md:65-69`) | DSR threshold before any promotion |
| Drawdown | Max drawdown + time-under-water on paper NAV | breach of lab drawdown budget = automatic demotion one rung |
| Turnover / cost realism | Turnover × modeled fees+slippage; net-of-cost PnL is the only PnL that counts | fee-adjusted return must stay positive |
| Thesis hit-rate | Every trade pre-registers a falsifiable thesis (Ghata mandatory, all labs encouraged); scored resolved-true / resolved-false | calibration (Brier, via `ginko_brier.py`) tracked per agent |
| Abstention quality | Reward for `FLAT` calls in regimes where trading would have lost | prevents overtrading pressure |
| N-honesty | Every evaluated config appended to the tamper-evident N-ledger (`NORTH_STAR_ARCHITECTURE.md:67-69`); MinBTL check against realized N | mutation count itself is audited |

MAP-Elites behavioral axes per lab: holding period, long/short balance, abstention rate — so the archive keeps *different kinds* of profitable behavior, not one converged strategy.

**Generator/Evaluator separation** (`NORTH_STAR_ARCHITECTURE.md:70-73`): the mutated agent never grades itself; an adversarial multi-model evaluator scores each generation from receipts only.

### 2.6 Receipts & audit trail per trade

Extend the existing hash-chained packet discipline (`broker_paper_membrane.py:32-40` lifecycle; ledger receipts like `reports/capital_lab/goal-b-.../broker_paper_ledger.json`) into one append-only, per-trade receipt:

```
receipt = {
  trade_id, lab_id, agent_id, genome_hash,
  insight: {direction, magnitude, confidence, knowledge_ts, thesis_text, thesis_resolution_criteria},
  portfolio_target, risk_adjusted_target (incl. any clamp + which control),
  order lifecycle events [submit..terminal] with venue acks,
  fills {price, qty, fees}, reconciliation snapshot hash,
  outcome {pnl_net, thesis_resolved, resolution_evidence},
  prev_receipt_hash, receipt_hash (SHA-256)
}
```

Written to `~/.dharma/` runtime state, **never to git** — runtime receipts are explicitly gitignored (CLAUDE.md:~"Runtime receipts never enter git"). The chain is what feeds both the evolution fitness (§2.5) and the public track-record page (§6).

---

## 3. Platform research — where an individual can actually trade in 2026

**Jurisdiction is unknown for this operator and it is the single biggest fork in this table.** Assume nothing below until §5's questions are answered. "Custody risk" = counterparty risk of the venue holding your assets.

### Crypto — centralized spot/derivatives

| Venue | API quality | Paper/sandbox | Custody risk | Jurisdiction caveats |
|---|---|---|---|---|
| **Coinbase Advanced Trade** | Good: REST + WebSocket, official Python SDK ([github.com/coinbase/coinbase-advanced-py](https://github.com/coinbase/coinbase-advanced-py)); CDP keys with granular view/trade/transfer permissions ([docs.cdp.coinbase.com](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/overview)) | Sandbox exists with separate keys and simulated books ([docs overview](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/overview)); **note 2026-09-09 hard cutover** of international derivatives to a Deribit-powered gateway — spot/US futures unaffected ([coinbase.com developer platform](https://www.coinbase.com/developer-platform/products/advanced-trade-api)) | Custodial; US-listed public company, regulated — among the lower CEX counterparty risks, but still not your keys | Broad availability incl. US; product set (esp. derivatives) varies sharply by country/state |
| **Kraken (spot + futures)** | Good REST/WS; separate spot and derivatives APIs; derivatives keys offer No-Access/Read-Only/Full-Access tiers, **withdrawals excluded even from full access** ([support.kraken.com derivatives keys](https://support.kraken.com/articles/360022839451-how-to-create-an-api-key-for-kraken-derivatives)) | **Best-in-class crypto sandbox**: full futures demo at `demo-futures.kraken.com`, self-service signup, no real account needed, own API keys ([support.kraken.com test env](https://support.kraken.com/hc/en-us/articles/360000919926-Does-Kraken-offer-an-API-test-environment-), [API testing environment](https://support.kraken.com/articles/360024809011-api-testing-environment-derivatives)); demo resets periodically | Custodial; long operating history, strong security record; still a CEX | Futures/margin availability depends heavily on jurisdiction (e.g. US clients historically restricted from Kraken Futures) — **verify for your country** |
| **Binance (global)** | Deepest liquidity; excellent, versioned API docs ([developers.binance.com](https://developers.binance.com/docs/binance-spot-api-docs)); Spot Testnet with mirrored rate limits ([testnet.binance.vision](https://testnet.binance.vision/), [testnet docs](https://developers.binance.com/docs/binance-spot-api-docs/testnet)) | Yes — Spot Testnet, free, high rate limits | Custodial; largest venue but heaviest regulatory history | **Only where lawful.** Binance global is unavailable to US persons; US persons get the thinner Binance.US API ([docs.binance.us](https://docs.binance.us/)). Multiple other jurisdictions restrict it. Do not VPN around geofences — ToS breach and potential legal exposure |
| **Hyperliquid** (perp DEX) | Strong: on-chain order book, REST/WS + Python SDK, sub-accounts, vaults; no KYC — wallet connect + IP geofencing ([cryptoslate review](https://cryptoslate.com/decentralized-exchanges/hyperliquid-exchange-review/)) | Public **testnet** — free play environment | **Self-custody** (you hold keys) — removes CEX counterparty risk, adds smart-contract/bridge and key-management risk | **US is a restricted jurisdiction** ([datawallet](https://www.datawallet.com/crypto/is-hyperliquid-available-in-the-usa)); CFTC has signaled a future regulated US pathway but it does not exist today ([buildix](https://www.buildix.trade/blog/how-to-trade-hyperliquid-us-access-options-2026)). Also note repo history: the live Hyperliquid surface was deliberately quarantined (`NORTH_STAR_ARCHITECTURE.md:120-121`; `operator_brief.md:38`) |
| **dYdX v4** (perp DEX) | Cosmos app-chain; indexer + typed clients ([docs.dydx.exchange](https://dydx.exchange/docs)) | Public testnet operational ([status.v4testnet.dydx.exchange](https://status.v4testnet.dydx.exchange/)) | Self-custody | **Not available to US or Canadian persons** ([dydx docs/terms via v4 docs](https://dydx.exchange/docs)) |

### Equities / futures brokers with APIs

| Broker | API quality | Paper mode | Custody risk | Jurisdiction caveats |
|---|---|---|---|---|
| **Alpaca** | Developer-first REST/WS, official SDKs (Python/JS/C#/Go); stocks, ETFs, options, crypto ([alpaca.markets](https://alpaca.markets/), [docs.alpaca.markets/trading-api](https://docs.alpaca.markets/us/docs/trading-api)) | **Best paper onramp anywhere**: free paper-only account with just an email, *available globally*, up to 3 paper accounts, real-time simulated fills ([docs.alpaca.markets/paper-trading](https://docs.alpaca.markets/us/docs/paper-trading), [alpaca.markets/learn/start-paper-trading](https://alpaca.markets/learn/start-paper-trading)). Caveat: fills don't model slippage/liquidity realistically (same doc) | US broker-dealer, SIPC coverage on securities for live accounts; crypto side differs | Live accounts: US-centric with some international onboarding; paper: anyone. Crypto product availability varies by US state |
| **Interactive Brokers (IBKR)** | Industrial-grade but higher friction: TWS API + Client Portal Web API; huge asset coverage (global equities, futures, options, FX) ([interactivebrokers.com/ib-api](https://www.interactivebrokers.com/en/trading/ib-api.php)) | Every client gets a paper account with $1M simulated equity; paper TWS on port 7497 vs live 7496 ([IBKR paper docs](https://www.interactivebrokers.com/docs/tws-api/doc/notes-limitations/limitations/paper-trading), [IBKR glossary](https://www.interactivebrokers.com/campus/glossary-terms/paper-trading-account/)) — **requires opening (and typically funding) a real account first** | Large regulated multi-jurisdiction broker; strong protections | Available in most countries — the best choice if the operator is outside the US. KYC/funding required before paper access |
| **Tradier** | Clean REST brokerage API aimed at developers; equities + options ([docs.tradier.com](https://docs.tradier.com/docs/getting-started)) | Sandbox at `sandbox.tradier.com/v1` supporting the full trading API with paper money and **delayed** market data ([docs.tradier.com/faq](https://docs.tradier.com/docs/faq), [trade.tradier.com/developer-api](https://trade.tradier.com/developer-api/)) | US regulated broker-dealer | US-focused; delayed sandbox data limits strategy realism |

### Cross-cutting notes

- **Sandbox ≠ market realism.** Alpaca says so itself ([paper-trading docs](https://docs.alpaca.markets/us/docs/paper-trading)); Kraken's demo resets periodically ([Kraken test env](https://support.kraken.com/hc/en-us/articles/360000919926-Does-Kraken-offer-an-API-test-environment-)). Paper results systematically overstate live results (no queue position, no adverse selection). Fold a slippage haircut into every fitness number (§2.5 turnover row).
- **DEX vs CEX custody trade**: CEX = counterparty risk (the FTX lesson) but simpler ops; DEX = self-custody but the agent's wallet key *is* the money — a leaked DEX key is total loss with no support desk. That is a materially worse blast radius than a leaked no-withdrawal CEX key (§4).

---

## 4. The "safe place": credential vault design for ~20 platform credentials

Governing rule first: **no secrets in git, ever** — the repo hard rule at `CLAUDE.md:78-79` ("No secrets in git. No keys, credentials, or `.env` files — gitleaks blocks merge"), and runtime state stays under `~/.dharma/` (CLAUDE.md, "State directory"). The design below extends that rule to the whole fund.

### 4.1 Layered design

1. **Root of trust: a password manager with a real security model** — 1Password or Bitwarden. One vault named `shrama-capital`, one entry per platform holding: login, TOTP seed *or* note of hardware-key binding, API key id, API secret, key permissions, IP allowlist, creation + rotation dates.
2. **Hardware 2FA (FIDO2/passkey) on every account that supports it** — two YubiKeys (one daily, one in a physically separate backup location). Hardware keys defeat the phishing that TOTP does not. Where only TOTP is offered, TOTP lives in the password manager, never SMS.
3. **API keys: least privilege, always**
   - **Withdrawal permission DISABLED on every trading key, no exceptions.** Coinbase CDP keys let you grant trade without transfer ([Coinbase docs](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/overview)); Kraken derivatives keys exclude withdrawals even at Full Access ([Kraken key docs](https://support.kraken.com/articles/360022839451-how-to-create-an-api-key-for-kraken-derivatives)). A stolen trade-only key can lose money by bad trading, but it cannot drain the account to an attacker's wallet.
   - Separate **read-only keys** for data/monitoring vs **trade keys** for the membrane; the labs (§2.2) get *no keys at all* — only the execution membrane process holds trade keys.
   - One key per (venue × environment × purpose); paper/sandbox keys are separate entries so a sandbox key can never be confused with live (Kraken demo keys are inherently separate — [Kraken test env](https://support.kraken.com/hc/en-us/articles/360000919926-Does-Kraken-offer-an-API-test-environment-); Coinbase sandbox requires its own keys — [Coinbase docs](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/overview)).
4. **IP allowlisting** on every venue that supports it, pinned to the static egress IP of the single machine that runs the execution membrane. A stolen key without that IP is inert.
5. **Runtime delivery, never storage in code**: the membrane process reads secrets at start from the OS keychain or the password manager CLI (`op run` / `bw get`) into process env — never `.env` files in the repo tree (they're banned, `CLAUDE.md:78-79`), never logs, never receipts. Receipts store the key *alias* only — exactly the Goal-B practice already on record ("secret aliases only and recording no secret values", `operator_brief.md:50`).
6. **DEX wallets are a different animal**: if Hyperliquid/dYdX are ever in scope (jurisdiction-permitting), use a dedicated hot wallet holding only the active trading allocation, funded from a hardware-wallet cold vault; use Hyperliquid's agent-wallet mechanism so the trading key ≠ the funds key. Treat the hot-wallet key as total-loss-on-leak.
7. **Hygiene loop**: quarterly key rotation; immediate rotation on any anomaly; venue-side audit of active keys monthly; gitleaks already guards the repo side (`CLAUDE.md:78-79`).

### 4.2 Blast-radius table (why each layer exists)

| Compromise | With this design | Without |
|---|---|---|
| Trade-only API key leaks | Attacker can churn fees / bad trades from allowlisted IP only → effectively inert off-box | Full account drain |
| Machine compromised | Keys usable until rotated; withdrawals still impossible; drawdown kill-switch (`risk_governor.py:163-166`) caps trading damage | Same plus withdrawal drain |
| Password manager master compromised | Hardware 2FA still blocks venue logins | Everything |
| DEX hot-wallet key leaks | Loss capped at active trading allocation | Entire crypto stack |

---

## 5. RECOMMENDATION

### 5.1 Sign up for these first (in order)

1. **Alpaca (paper account)** — *today, cost: an email address.* Global paper signup with no funding, real-time simulated fills, first-class API ([docs](https://docs.alpaca.markets/us/docs/paper-trading)). This is the fastest path to closing R7 (`NORTH_STAR_ARCHITECTURE.md:108-110`): real external lifecycle receipts against a real broker API. Labs Vega and Ghata start here on equities/ETF proxies.
2. **Kraken Futures demo** — *today, cost: an email address.* Self-service demo, separate API keys, real derivatives semantics ([Kraken](https://support.kraken.com/hc/en-us/articles/360000919926-Does-Kraken-offer-an-API-test-environment-)). This gives Setu (funding/basis) and Tula (market-making) a perp/futures sandbox — the crypto-derivatives analogue of Alpaca paper. A live Kraken spot account (with KYC) can follow later for real crypto data + eventual small-live spot.
3. **Coinbase Advanced *or* IBKR — deferred until the jurisdiction question is answered.** US-based → Coinbase Advanced (regulated US spot venue, granular no-withdrawal keys). Non-US → IBKR (global multi-asset paper + live under one roof, $1M paper account, [IBKR](https://www.interactivebrokers.com/docs/tws-api/doc/notes-limitations/limitations/paper-trading)). Do not open both now; two paper venues (Alpaca + Kraken demo) already saturate the build capacity.

Explicitly **not now**: Binance (jurisdiction-dependent, heaviest compliance history), Hyperliquid/dYdX (US-restricted, and the repo already quarantined its live Hyperliquid surface — `NORTH_STAR_ARCHITECTURE.md:120-121`), Tradier (delayed sandbox data is a worse R7 target than Alpaca's real-time paper).

### 5.2 Questions the operator must answer before anything goes past paper

1. **Jurisdiction**: What country (and US state, if applicable) are you tax-resident in? This alone decides Binance-vs-Binance.US, Hyperliquid/dYdX legality, Kraken Futures access, and IBKR entity.
2. **Capital at risk**: What is the maximum amount you can lose to zero without life impact? Rung-2 leases (§2.4) will be a fraction of that number.
3. **Tax situation**: Are you prepared for high-frequency short-term-gains accounting? Crypto trades are taxable events in most jurisdictions; five active labs can generate thousands of lots. Who does your accounting?
4. **Custody preference**: CEX convenience vs self-custody responsibility (§3 cross-cutting notes)? This decides whether the DEX labs ever leave the testnet.
5. **Entity**: personal account or an LLC/company wrapper for the fund? (Affects venue onboarding, tax, and liability.)

### 5.3 The honest caveat (goes in every operator brief, verbatim)

- 70–80% of active retail day traders lose money net of costs; ESMA-mandated broker disclosures show 74–89% of retail CFD accounts lose ([babypips/CFTC summary](https://www.babypips.com/news/almost-80-percent-of-retail-traders-are-unprofitable), [quantifiedstrategies CFD stats](https://www.quantifiedstrategies.com/cfd-trading-statistics/)); academic evidence suggests <1% of day traders earn persistent positive returns ([theinvestorscentre UK stats](https://www.theinvestorscentre.co.uk/trading/statistics/day-trading/)).
- **Agent-run trading is unproven.** The strongest published agentic-fund results collapse when look-ahead and data leakage are corrected ("Profit Mirage", arXiv 2510.07920, cited at `NORTH_STAR_ARCHITECTURE.md:14-16`). Our own Goal A honestly closed with zero passed leakage traps and zero OOS windows (`GOAL_A_CLOSEOUT_...md:54-56`). There is currently **no evidence anywhere in this repo that any strategy makes money.**
- Therefore: paper-only until the §2.4 gates pass, live capital only under an explicit written lease, capped at an amount you can lose entirely, and the default expected outcome of the live experiment is a small loss purchased for information.

---

## 6. shramacapital — one-page website structure

Static one-pager (matches the repo's Next.js competence in `dashboard/`, but should be a separate public repo — fund receipts are runtime state and must not enter this git tree, CLAUDE.md "Runtime receipts never enter git").

```
shramacapital.example
├── HERO         "Shrama Capital — a personal research fund run by evolving
│                agents, in public, receipts-first."  One line of positioning:
│                effort (śrama) + verification, not promises. No "returns" language.
├── HOW IT WORKS 3 cards: 5 labs (§2.2 one-liners) → shared risk kernel →
│                paper-first ladder (fixture→paper→small-live), mirroring
│                NORTH_STAR_ARCHITECTURE.md:116-118.
├── TRACK RECORD The load-bearing page. Fed *only* from the receipts chain (§2.6):
│                per-lab equity curve (paper clearly watermarked "PAPER"),
│                DSR / max-DD / turnover / thesis-hit-rate / abstention-rate
│                (the §2.5 fitness vector), N-ledger count, and a per-trade
│                receipt browser showing hash-chained entries. Every number
│                links to the receipt hash that produced it — the site makes
│                the same citation-or-silence promise as CLAUDE.md ("Citation-
│                or-silence" hard rule).
├── EPISTEMICS   Short honest-methods note: leakage gates, deflated Sharpe,
│                why paper ≠ live, and the §5.3 caveat block verbatim.
├── ABOUT        Operator identity to taste; substrate note (dharma_swarm).
└── LEGAL        See below.
```

**Legal disclaimer needs (page footer + /legal):**
- Not investment advice; nothing on the site is an offer or solicitation to buy any security or to invest in any fund.
- Shrama Capital manages **only the operator's personal capital**; it does not accept outside money. (This sentence is what keeps it out of investment-adviser/fund-registration territory in most jurisdictions — the moment outside capital or paid advice appears, licensing analysis is required. Jurisdiction unknown → have this reviewed once §5.2-Q1 is answered.)
- Paper results are simulated, do not reflect real execution, and systematically overstate live performance ([Alpaca's own caveat](https://docs.alpaca.markets/us/docs/paper-trading)); past performance (real or simulated) does not predict future results.
- Loss statistics disclosure mirroring §5.3.
- Trading involves substantial risk of loss; crypto assets may be unregulated and can lose all value.

---

## Appendix — verification commands

```bash
# repo evidence
python3 -m pytest tests/test_capital_lab_risk_governor.py \
  tests/test_capital_lab_broker_paper_membrane.py \
  tests/test_capital_lab_alpha_evidence.py -q          # 21 passed (2026-08-09)
sed -n '24,27p' dharma_swarm/capital_lab/broker_paper_membrane.py  # authority zeros
sed -n '76,79p' dharma_swarm/capital_lab/risk_governor.py          # RiskGovernor
grep -n "No secrets in git" CLAUDE.md                              # line 78
```
