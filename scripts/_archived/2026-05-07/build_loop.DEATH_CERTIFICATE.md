# Death Certificate: build_loop.sh

**Path at archive time:** `scripts/build_loop.sh`
**Archived to:** `scripts/_archived/2026-05-07/build_loop.sh`
**Date:** 2026-05-07
**Signed:** Dhyana + Claude (wiring lane Phase B inaugural archive)

## What it was

First-generation autonomous build loop, March 2026. Bash launcher that read a JSON
queue, called `claude -p` per iteration with fresh 200K context (Ralph Wiggum
pattern), and tracked completed/failed/dead-cycle outcomes via filesystem state.
Default model `claude-sonnet-4-6`, opt-in `claude-opus-4-6`. Hardcoded paths
under `~/.dharma/build_loop/`.

## What's missing

- Replaced by `loop_metabolic.sh` (Apr 10) — metabolic-loop variant.
- Replaced by `agent_loop.py` (Apr 10) — Python rewrite with richer state.
- Default `claude-opus-4-6` model ID is stale (canonical is `claude-opus-4-7`).
- Zero tests, zero documentation outside the header comment.
- Zero references inside the repo (`rg -l "build_loop"` empty as of 2026-05-07).

## Why archived now

Three signals converged: 39 days untouched, zero internal callers, runtime
directory `~/.dharma/build_loop/` taken over by successor implementations
(`metabolic_queue.json`, `loop_output.log`, `progress.txt` all modified
2026-05-07 by `loop_metabolic.sh` / `agent_loop.py`). Keeping this file in
`scripts/` perpetuated the illusion of choice between four implementations of
the same pattern. Archiving forces clarity.

## What would resurrect it

- Need for a non-metabolic build loop with no Python dependency.
- Future Ralph-Wiggum variant where the bash version is preferred over
  `loop_metabolic.sh` (e.g. environments without metabolic-loop state schema).
- A revival run of the original 2026-03 build queue with the original prompt
  template `PROMPT_BUILD.md` (still present at `~/.dharma/build_loop/`).

## References

- Audit that flagged it: 2026-05-07 graveyard scan (7 half-wired scripts).
- Last commit: `2026-03-29 feat(ops): add autonomous build loop script + skill`.
- Imports at archive time: 0.
- Test refs at archive time: 0.
- Active successor today: `~/.dharma/build_loop/loop_metabolic.sh` + `agent_loop.py`.

## Follow-up (not blocking this archive)

The `autonomous-build` skill still describes this pattern. Re-point its docs at
`loop_metabolic.sh` / `agent_loop.py` in a separate PR.
