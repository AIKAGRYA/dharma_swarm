# Requirements + Edge-Case Audit — Cockpit Backplane Canonicalization — 2026-06-23

This audit independently re-derives the active objective requirements and every edge case that can break the cockpit backplane if ignored. It verifies whether current artifacts handle each case.

## Objective requirements

| Requirement | Current handling | Evidence | Status |
|---|---|---|---|
| Canonicalize cockpit backplane as control-tower substrate | Planned but not canonical | `INDEX_2026-06-23.md`, `COCKPIT_ADMISSION_RECOMMENDATION_2026-06-23.md`; origin/main lacks operator_coherence files | OPERATOR-GATED |
| Extract/plan around dirty-checkout cockpit without destructive cleanup | Dedicated extraction plan and lane packet | `OPERATOR_COHERENCE_COCKPIT_LANE_PACKET_2026-06-23.*`, `CANONICALIZATION_RUNBOOK_2026-06-23.md` | HANDLED |
| Define truth/admission schemas | Canonicality taxonomy + lane schema | `COCKPIT_CANONICALITY_TAXONOMY_2026-06-23.*`, `AGENT_LANE_ADMISSION_SCHEMA_2026-06-23.*` | HANDLED |
| Define canonical-vs-candidate semantics | Taxonomy + unified feed contract | canonical labels, proof states, feed canonicality, hard invariants | HANDLED |
| Integrate production-readiness results | Two-axis contract + final closeout | `PROD_READINESS_BACKPLANE_CONTRACT_2026-06-23.md`, `prod_readiness/*` | HANDLED |
| Verify UI/backplane contract | UI contract + prior build/test verification | `UI_BACKPLANE_CONTRACT_2026-06-23.md`, `FINALIZER_VERIFICATION_2026-06-23.md` | HANDLED |
| Durable Arena/Forge readiness handoff | Forge/Arena input contract + Index | `FORGE_ARENA_INPUT_CONTRACT_2026-06-23.md`, `INDEX_2026-06-23.md` | HANDLED |

## Edge cases and handling

| Edge case | Why it matters | Handling | Status |
|---|---|---|---|
| Grading branch advances while agents work | Hardcoded ahead counts go stale; candidate/canonical state drifts | `FINALIZER_VERIFICATION_2026-06-23.md` says recompute branch relation dynamically; latest audit: 10 ahead / 0 behind | HANDLED |
| Unified feed supersedes three-feed model | UI could ingest lower-level feeds and duplicate logic | `TRACK_COHERENCE_UNIFIED_FEED_CONTRACT_2026-06-23.*` defines preference order: `track_coherence` first, health/audits backing | HANDLED |
| Branch-only feeds presented as canonical | Would falsely let candidate reviews drive closure/Forge | canonicality taxonomy marks `track_coherence`, `track_health`, `track_audits` as `OPEN_PR_REMOTE` until branch lands | HANDLED |
| Dirty checkout cockpit presents local 11/11 portfolio as canonical 7/10 | Biggest confusion source | UI contract requires self-banner: dirty generated, not canonical; taxonomy hard invariant | HANDLED |
| Criterion id rename / old ids pinned by UI | Handoff renamed IDs; old IDs still canonical on main | consolidation spec says detect criterion IDs dynamically by feed/source, never hardcode | HANDLED |
| `render_active_track_includes.py --check` false blocker | System python without PyYAML gives spurious diff | prod-readiness contract + render discrepancy record classify it as dependency-honesty issue, not docs drift | HANDLED |
| Lower-tier reviewer signoff treated as authoritative | Violates operator-locked Opus 4.8+ floor | unified feed / finalization record map `below_floor`, `families`, `quorum_met`; cockpit must consume accepted grader output only | HANDLED |
| File-green but claim false (OVERSTATED) hidden | Truth-graph's key defect; file checks cannot catch hand-authored receipt | unified feed contract requires loud `OVERSTATED` from `coherence_state` / `portfolio.overstated` | HANDLED |
| Live-vs-static proof collapsed | NATS/truth-graph can be file-green but live-proof missing | canonicality taxonomy includes proof_state and prod-readiness two-axis contract | HANDLED |
| Source probe unavailable (gh/tmux/ps) coerced into pass/fail | False confidence in cockpit | taxonomy/UI contract require `UNAVAILABLE_UNCERTAIN` and visible source_errors | HANDLED |
| UI Fugu duplicates backplane semantics | Divergent truth labels | UI/backplane contract says UI renders labels and does not derive truth | HANDLED |
| Backplane Fugu edits UI lane | Agent conflict | UI/backplane contract names UI-owned files and coordinate-before-edit backplane generator surfaces | HANDLED |
| Forge/Arena ingests dirty/candidate feeds | Would train/evolve on false state | Forge/Arena input contract: only canonical or clean read-only feeds drive fitness | HANDLED |
| Cleanup before off-machine preservation | Could lose local-only work | Index checklist requires gh auth/off-machine preservation before destructive cleanup | HANDLED |
| Goal marked complete prematurely | Candidate artifacts exist but not canonical | objective trace + finalizer record state NOT COMPLETE / operator-gated | HANDLED |

## Current blocker state (fresh resume audit)

- `gh auth`: unavailable (`gh_exit=1`)
- `origin/main`: `839fd25f43c76375f49e45012fe8f20a324aa74c`
- grading branch: `8124388991fe4a368cd54efa944303fb194968f1`, `0 behind / 10 ahead`
- cockpit on origin/main: no operator_coherence files
- `track_coherence.json` on origin/main: no

## Verdict

All agent-doable objective requirements and edge cases are handled by durable artifacts. Actual canonicalization remains blocked by operator-gated branch landing/extraction and missing gh/off-machine preservation.
