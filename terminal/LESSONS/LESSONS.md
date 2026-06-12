Read terminal/src/theme.ts before any UI code; never hardcode a hex outside theme.ts and ScenicStrip.tsx.

# LESSONS — append-only. One lesson per line: [date] [F-ID] lesson.
# Every coder session reads this file before implementing and appends anything the next session needs.
[2026-06-11] [F-001] F-001 landed: the failure-set gate is now STRICT — bun test must show 0 fail on every commit; the baseline-failures.txt comm comparison is vestigial.
[2026-06-11] [F-001] Path literals hide as truncated prefixes: Sidebar compact(value,24) renders "Root /Users/dhyana/dharma_sw…", so grep '/Users/dhyana/dharma' (not just the full path); tests mirror it via REPO_ROOT_COMPACT = len<=24 ? root : slice(0,23).trimEnd()+"…".
[2026-06-11] [F-001] bun test (App renders) and every tmux boot-smoke rewrite the TRACKED terminal/.dharma-terminal-state.json — src/persistence.ts STATE_PATH is pinned to TERMINAL_ROOT and ignores DHARMA_TERMINAL_STATE_DIR; check git status and restore byte-exact (file has NO trailing newline) before committing.
[2026-06-11] [F-001] docops pre-commit gate fires on commits with no markdown changes if repo markdown drifted earlier; .venv/bin/python does not exist in this worktree — use python3 scripts/docops/check_docops_integrity.py --write-auto-sections, then update the count it names in docs/governance/SOVEREIGN_MANIFEST.md (line ~201) and retry once.
[2026-06-11] [F-001] Tests are NOT typechecked (tsconfig include=["src"], types=["node"]) — import.meta.dir in tests is bun-runtime-safe but would fail tsc if used in src; src uses fileURLToPath(import.meta.url) instead.
