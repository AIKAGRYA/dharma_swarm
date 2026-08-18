# Packet L-0 — forecast ledger (plumbing of the income organ), real edition

**Status:** drafted, not published, not trading.  
**Mechanical resolve:** implemented in `scripts/ginko_ledger_l0.py::resolve_matured` (FRED / CoinGecko vs the rule frozen in `metadata.resolution`). Not a stub.  
**Ratified:** yes-sheet 2026-08-18 line 7 (`docs/plans/YES_SHEET_RATIFICATION_2026-08-18.md`):
20+ model-generated forecasts per run, public + timestamped, no 0.5 defaults.  
**Bit purchased if valid:** a public, miss-included, resolvable forecast row that could have come out red.  
**Not purchased:** edge, Kalshi P&L, live capital, harness-sale, spin-out.

Parent map: [Wayfinder MAP: megha dual-loop](https://github.com/AIKAGRYA/dharma_swarm/issues/1366) · sibling fire: #1379.

## What survived the attack (and what did not)

Survived: L0 as a **forward-only Brier ledger** using `record_prediction` /
`resolve_prediction` / `build_dashboard` / `check_edge_validation` in
`dharma_swarm/ginko_brier.py`. SATYA (rows cannot be deleted). Paper-only.
Megha stays out. Live capital last. Publish is its own operator yes. Kill
date. Model-agnostic `source=` slot already on the Prediction.

Died (do not build in this packet):

- L1→L2 on `edge_validated` alone (global Brier < 0.125 over 500; no per-universe, no liquidity, no PBO — `ginko_brier.py:318-321`).
- “Maker-side long-tail Kalshi avoids adverse selection.” Resting quotes **are** the adverse-selection surface.
- “Hydra restarted with the world as referee.” Hydra is a different organ, STOPPED-HONESTLY.
- “Assets compound monotonically.” Track records go red.
- Invoking `revenue/wedge_pipeline.py` (BR-007) or `engine/store_sync`.
- Two paper books (`ginko_paper_trade.py` **and** `capital_lab/`). L1 later picks **one**.
- A new ACTIVE_TRACK row.
- L3/L4/L5 legal and venue claims.

Desk correction: receipts belong under Darshan **desk 3 (Witness Ledger)**, not desk 5 (Field Notes).

## Refuse

- hostname `meghadharma-cloud`
- any call to `sync_all` / `_sync_stores` / `run_pipeline`
- Kalshi, broker, or live-order imports
- deleting or rewriting a prediction row (resolution only fills in outcome fields)
- resolving a row with a model-judged outcome (the resolver replays the
  mechanical rule frozen in the row's metadata; sources are FRED or CoinGecko)
- **recording a row whose probability did not come from a live model call**
  — there is no 0.5 default, no hardcoded prior, and no probability file; a
  failed model call records nothing and exits nonzero
- publishing outside `reports/darshan/forecast_ledger/**` /
  `generated/forecast-ledger` without a PUBLISH grant
- committing ledger output to `main`
- treating `edge_validated` as a go-live

## Named functions

| Step | Function | File |
|---|---|---|
| record | `record_prediction` | `dharma_swarm/ginko_brier.py` |
| resolve | `resolve_prediction` (store) + `resolve_matured` (runner; **implemented**, not missing) | `ginko_brier.py` / `scripts/ginko_ledger_l0.py` |
| grade | `build_dashboard` / `check_edge_validation` | same |
| data | `fetch_fred_series` / `fetch_crypto_prices` | `dharma_swarm/ginko_data.py` |
| probabilities | `model_probabilities` (Anthropic Messages API, fail-loud) | `scripts/ginko_ledger_l0.py` |
| runner | `scripts/ginko_ledger_l0.py` | this packet |

Do **not** call `dharma_swarm.revenue.wedge_pipeline.run_pipeline`.

## Universes (yes/no, mechanical resolve — 26 questions per run)

Five families; every question freezes its strike AND its full resolution rule
(source + series + comparator + threshold) in `metadata` at record time. The
resolver replays that rule mechanically — never judgment. Families overlap
Kalshi market categories (CPI, Treasury yields, jobless claims, BTC/ETH
levels); no Kalshi contract IDs — overlap is incidental.

1. `fred.cpi` — next CPIAUCSL print vs the frozen level (1 question, 45d)
2. `fred.dgs10` — 10y yield vs five strikes bracketing the current print (5 questions, 7d)
3. `fred.icsa` — weekly initial jobless claims vs strike and a +5% band (2 questions, 14d)
4. `crypto.btc_usd` — BTC-USD spot vs 98%/100%/102% strikes at 1/3/7-day horizons (9 questions)
5. `crypto.eth_usd` — same grid for ETH-USD (9 questions)

## Probabilities (real edition — no null rows)

Every probability comes from one Anthropic Messages API call per run
(`model_probabilities` in the runner; default model `claude-opus-5`,
override with `GINKO_L0_MODEL` or `--model`). The model must return a
probability strictly inside (0, 1) for **every** question; anything else —
missing key, refused call, malformed JSON, missing qid — aborts the run
with a nonzero exit and **zero rows recorded**. Fail loud, never fake.

**Operator-hands step:** provision the `ANTHROPIC_API_KEY` repository secret
(GitHub → Settings → Secrets and variables → Actions). Without it every
non-resolve-only run fails by design. `FRED_API_KEY` is also required.

## Publication (durable, off-main)

- The workflow (`.github/workflows/ginko-l0.yml`, dispatch-only) commits the
  publish dir to the dedicated **`generated/forecast-ledger`** branch —
  mirroring how derived status ships on `generated/status`. Never to `main`.
- `reports/darshan/forecast_ledger/YYYY-MM-DD.json` — day receipt (dashboard,
  new rows, resolutions, timestamp grade), plus `index.md`.
- `predictions.public.jsonl` — the **full store snapshot** (all rows with
  current resolution state). Rows are never removed; resolution only fills
  in outcome fields. This file is the durable store of record: each run
  rehydrates the ephemeral `~/.dharma/ginko` store from it before doing
  anything else, so CI runs accumulate instead of starting blank.
- Timestamping: if the `ots` client is present and the stamp succeeds, the
  day file is `GREEN_ots_stamped` (its `.ots` proof published alongside);
  otherwise everything stays `AMBER_git_self_asserted`. Never claim anchored
  when not.
- External platforms (Substack, X, Kalshi profile): **out of this packet**.

## Kill

After `kill_after_days` (default 30) from the first published row:

- stop recording **new** forecasts if `resolved_predictions < 15` **or** `overall_brier >= 0.25`
- keep resolving already-open rows (`--resolve-only` stays allowed)
- no prompt enrichment, no new universes, no L1

## Grants

- **L0 PUBLISH grant** (this packet): dated, one-shot to *start* the ledger.
  Consumed on first successful public row; later daily runs reuse it until
  expiry or kill. `allowed_universes` must equal the five families above.
- **L2 MONEY grant**: not minted here. When (if) written later it must
  require per-universe Brier, a liquidity floor, and a residency gate —
  `edge_validated` is necessary, not sufficient.

## Receipt schema (`dharma.ginko.l0.v2`)

`valid` only if: ≥1 new or resolved row (or an explicit resolve-only run),
`published_path` exists, no BR-007 module ever imported, grant id recorded.
The receipt also carries `model`, `timestamp_grade`, `n_store`, `n_new`,
`n_resolved`, and `n_resolve_skipped`.

This is a **ledger receipt**, not an edge receipt.
