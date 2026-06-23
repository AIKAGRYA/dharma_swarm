# Objective Requirements Trace — Cockpit Backplane Canonicalization — 2026-06-23

This trace independently re-derives the active goal requirements and maps each to current evidence. It is intentionally strict: the goal is **not complete** until candidate feeds and cockpit code are canonical, but substantial backplane work is complete and verified.

| Requirement from objective | Current status | Evidence | Remaining gap |
|---|---|---|---|
| `extract/plan around the dirty-checkout cockpit without destructive cleanup` | PLAN COMPLETE; extraction not executed | `COCKPIT_ADMISSION_RECOMMENDATION_2026-06-23.md`, `OPERATOR_COHERENCE_COCKPIT_LANE_PACKET_2026-06-23.*`; no reset/clean/stash/branch deletion performed | Operator must approve dedicated extraction branch and preservation first |
| `define truth/admission schemas` | DONE | `COCKPIT_CANONICALITY_TAXONOMY_2026-06-23.{md,json}`, `AGENT_LANE_ADMISSION_SCHEMA_2026-06-23.{md,json}` valid JSON | None for planning layer |
| `canonical-vs-candidate semantics` | DONE and updated for moving grading branch | taxonomy + `COCKPIT_CONSOLIDATION_SPEC`, `TRACK_COHERENCE_UNIFIED_FEED_CONTRACT`; verified grading branch now 9 ahead / 0 behind main | Candidate remains candidate until branch lands |
| `integrate production-readiness results` | DONE | `PROD_READINESS_BACKPLANE_CONTRACT_2026-06-23.md`; prod readiness JSON valid; render-check correction carried | None for planning layer |
| `verify UI/backplane contract` | DONE as contract + prior build verification | `UI_BACKPLANE_CONTRACT_2026-06-23.md`; cockpit compile/pytest/generator/json/lint/build previously PASS | UI agent must consume labels when implementing |
| `produce durable handoff artifacts for Arena/Forge readiness` | DONE | `FORGE_ARENA_INPUT_CONTRACT_2026-06-23.md`, `INDEX_2026-06-23.md`, `BACKPLANE_LONG_GOAL_CLOSEOUT_2026-06-23.md` | Arena implementation intentionally deferred |
| `canonicalize the cockpit backplane as control tower substrate` | NOT COMPLETE; operator-gated | Artifacts exist only in reconciliation worktree; cockpit code dirty-local; grading feeds branch-only | Land grading branch + extract cockpit branch/PR + rerun from clean worktree |

## Current authoritative state

- `origin/main`: `839fd25f43c76375f49e45012fe8f20a324aa74c`
- grading branch: `bfaaae350ca784355ac1829898f23aa7dceb8813`, `9 ahead / 0 behind`
- cockpit implementation: dirty checkout `/Users/dhyana/dharma_swarm`, not canonical
- `ACTIVE_TRACK.yaml`: not edited by this backplane work

## Why the goal must remain active

The backplane design and handoff layer are complete enough to guide implementation, but the objective says **canonicalize**. Canonicalization requires two operator-gated changes that this agent must not force:

1. Land `claude/tracks-consolidation-grading-nb67lq` to make `track_coherence.json`, `track_health.json`, `track_audits/*`, hardened criteria, and track-coherence tooling canonical.
2. Extract the dirty cockpit to a dedicated branch/PR and land it without raw-merging unrelated dirty work.

Until those land and the cockpit generator runs from a clean worktree, this is a verified candidate backplane, not the canonical control tower.
