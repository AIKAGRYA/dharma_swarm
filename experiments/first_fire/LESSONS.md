# Lessons — first-fire plumbing fine (2026-08-18)

Verified against `origin/main` (`dharma_swarm/evolution.py`, `diff_applier.py`), not the megha live pin.

- `difflib.unified_diff(..., fromfile="a/<rel>", tofile="b/<rel>")` matches `parse_unified_diff` / `_strip_prefix`. Do not add timestamps.
- `apply_diff_and_test` is **not** `ApplyTestResult`. Empty diff → `{"pass_rate": 1.0, "skipped": True}`. Apply path → `{"pass_rate", "rolled_back"}`. `applied` is never returned.
- A refused apply leaves the toy file original. `file_restored` alone is a fake red. Require `rolled_back is True`.
- Workflow `pip install -e ".[dev]" || pip install -e .` can drop pytest. Pin `pip install -e .` plus `pytest>=7.0`.
- `icontract` is a base extra. Do not treat `[dev]` as the engine extra.
- Consume the grant after scratch + diffs exist. A failed copy must not burn the one-shot.
- Do not run the runner on meghadharma-cloud. Landing ≠ lighting.
