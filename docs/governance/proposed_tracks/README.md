# Proposed Tracks

This directory holds draft track blocks that are **not yet active**.

A file here is a proposal — a complete track block that an operator (or another
agent at the operator's direction) may move into `ACTIVE_TRACK.yaml` under
`active_tracks:` once two conditions hold:

1. **Doctrine permits the concurrent track.** The `track_policy` floor and
   ceiling in `ACTIVE_TRACK.yaml` (default `min_active: 1`, `max_active: 10`)
   must permit one more active track, and the proposed block must have
   non-overlapping surfaces and non-goals with the currently ACTIVE tracks.
2. **Schema machinery is in place.** The multi-track v2 schema readers
   (`check_track_status.py`, `render_active_track_includes.py`, and the
   `api/routers/` + `dharma_swarm/operator_core/dashboard_ssot.py`
   projections) must be live on `main`. Proposals authored against the v2
   `active_tracks:` list (not the v1 scalar) require those readers.

## Rules

- A proposal here is **draft only**. It does not constitute a declared track;
  CI does not gate against it, `make onboard` does not surface it, and no agent
  should treat it as load-bearing until promoted into `ACTIVE_TRACK.yaml`.
- A proposal must declare an `owner` and a non-empty `completion_criteria`
  list using the same `{id, kind, file, pattern}` shape the live checker
  accepts (`file_exists`, `file_contains`, `pr_merged`).
- A proposal that sits here for >30 days without being promoted should either
  be promoted, withdrawn (deleted by its author), or explicitly extended in a
  comment at the top of the file.
- Authorship: any agent or human contributor may add a proposal. The operator
  decides when (and whether) to promote.

## Current proposals

- `spine-adoption-2026-06.yaml` — successor to `runtime-truth-spine-2026-06`
  (which shipped 13/13 by the letter but has zero callers outside the spine
  package and tests as of 2026-05-31). Migrates the five god objects
  (agent_runner, orchestrator, swarm, thinkodynamic_director, telos_substrate)
  onto `invoke_agent()`. Authored by perplexity-computer per the 2026-05-31
  A2A handoff from claude-code.

## Why not just put proposals in `ACTIVE_TRACK.yaml` as inactive entries?

The schema does not have an "inactive" or "proposed" track state. A track in
`ACTIVE_TRACK.yaml` is either ACTIVE (current work, TTL counts down),
SHIPPED/SUPERSEDED (in `closed_tracks`, append-only history), or absent.
Holding draft proposals as a separate filesystem surface keeps the YAML clean
of speculative state while preserving the proposal as a reviewable artifact.
