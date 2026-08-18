# Packet L-0 — forecast ledger (plumbing of the income organ)

**Status:** drafted, not published, not trading.  
**Bit purchased if valid:** a public, miss-included, resolvable forecast row that could have come out red.  
**Not purchased:** edge, Kalshi P&L, live capital, harness-sale, spin-out.

Parent map: [Wayfinder MAP: megha dual-loop](https://github.com/AIKAGRYA/dharma_swarm/issues/1366) · sibling fire: #1379.

## What survived the attack (and what did not)

Survived: L0 as a **forward-only Brier ledger** using `record_prediction` / `resolve_prediction` / `build_dashboard` / `check_edge_validation` in `dharma_swarm/ginko_brier.py`. SATYA (rows cannot be deleted). Paper-only. Megha stays out. Live capital last. Publish is its own operator yes. Kill date. Model-agnostic `source=` slot already on the Prediction.

Died (do not build in this packet):

- L1→L2 on `edge_validated` alone (global Brier < 0.125 over 500; no per-universe, no liquidity, no PBO — `ginko_brier.py:318-321`).
- “Maker-side long-tail Kalshi avoids adverse selection.” Resting quotes **are** the adverse-selection surface.
- “Hydra restarted with the world as referee.” Hydra is a different organ, STOPPED-HONESTLY.
- “Assets compound monotonically.” Track records go red.
- “Every component already exists.” Zero Kalshi / OpenTimestamps / PBO / Deflated-Sharpe symbols in the Python tree.
- Invoking `revenue/wedge_pipeline.py` (line 258 always calls `_sync_stores` → BR-007).
- Two paper books (`ginko_paper_trade.py` **and** `capital_lab/`). L1 later picks **one**.
- A new ACTIVE_TRACK row (portfolio at 10; #1213 is helm closeout, still open).
- L3/L4/L5 legal and venue claims.

Desk correction: receipts belong under Darshan **desk 3 (Witness Ledger)**, not desk 5 (Field Notes).

## Refuse

- hostname `meghadharma-cloud`
- any call to `sync_all` / `_sync_stores` / `run_pipeline`
- Kalshi, broker, or live-order imports
- deleting or rewriting a prediction row
- resolving a row with a model-judged outcome (resolver must be FRED or CoinGecko)
- publishing outside `reports/darshan/forecast_ledger/**` without a PUBLISH grant
- treating `edge_validated` as a go-live

## Named functions

| Step | Function | File |
|---|---|---|
| record | `record_prediction` | `dharma_swarm/ginko_brier.py` |
| resolve | `resolve_prediction` | same |
| grade | `build_dashboard` / `check_edge_validation` | same |
| data | `fetch_fred_latest` / CoinGecko helpers | `dharma_swarm/ginko_data.py` |
| runner | `scripts/ginko_ledger_l0.py` | this packet |

Do **not** call `dharma_swarm.revenue.wedge_pipeline.run_pipeline`.

## Universes (yes/no, mechanical resolve)

Only these three in L0. Strikes frozen at record time in `metadata`.

1. `fred.cpi_mom_positive` — next CPI-U monthly change > 0 (FRED `CPIAUCSL`)
2. `fred.dgs10_up` — 10y yield (FRED `DGS10`) higher than the printed value at forecast time
3. `crypto.btc_usd_up` — BTC-USD 00:00 UTC close above the CoinGecko price recorded at forecast time

No Kalshi contract IDs. Overlap with event markets is incidental.

## Publication

- In-repo: `reports/darshan/forecast_ledger/YYYY-MM-DD.json` plus `index.md`
- Append-only JSONL copy under the same dir (`predictions.public.jsonl`)
- OpenTimestamps: if `ots` exists, stamp the daily SHA; if not, label the git commit **AMBER** (self-asserted time)
- External platforms (Substack, X, Kalshi profile): **out of this packet**

## Kill

After `kill_after_days` (default 30) from the first published row:

- stop recording **new** forecasts if `resolved < 15` **or** `overall_brier >= 0.25`
- keep resolving already-open rows
- no prompt enrichment, no new universes, no L1

## Grants

- **L0 PUBLISH grant** (this packet): dated, one-shot to *start* the ledger. Consumed on first successful public row.
- **L2 MONEY grant**: not minted here. When (if) written later it must require per-universe Brier, a liquidity floor, and a residency gate — `edge_validated` is necessary, not sufficient.

## Receipt schema (`dharma.ginko.l0.v1`)

`valid` only if: ≥1 new or resolved row, non-empty `question` + `probability`, `source` set, resolver ∈ {fred, coingecko}, no `store_sync` invoked, `published_path` exists, grant id recorded.

This is a **ledger receipt**, not an edge receipt.
