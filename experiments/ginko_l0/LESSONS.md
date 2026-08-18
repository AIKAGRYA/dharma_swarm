# Lessons — Ginko L0 fine (2026-08-18)

Verified against `origin/main` (`ginko_brier.py`, `ginko_data.py`), not the megha live pin.

- Mechanical resolve was **already implemented** in `resolve_matured` (PR #1380). Not missing. FRED / CoinGecko vs `metadata.resolution`. Unknown comparator / missing actual / legacy row without a rule stays pending.
- `build_dashboard()` field is `resolved_predictions`. `asdict` is correct. `resolved_count` lives only on `check_edge_validation()["metrics"]` and is not an L0 gate.
- L0 must not import `wedge_pipeline` / `store_sync` (BR-007). Belt is delta-vs-baseline so the shared CI interpreter cannot false-positive.
- No 0.5 default. Model failure records nothing. `--resolve-only` must not call the model.
- `icontract` / `httpx` / `anthropic` are base extras. `pip install -e .` is enough for the runner.
- Tests that call `main_async` must stub `socket.gethostname`. Otherwise they
  false-pass or false-fail on meghadharma-cloud (refuse is first, exit 2).
- Do not publish. Do not call Kalshi. Do not add an ACTIVE_TRACK row.
