# Cockpit Canonicality / Truth Taxonomy — 2026-06-23

## Purpose

The Operator Coherence Cockpit aggregates state from many sources (origin/main, dirty checkout, worktrees, branches, stashes, PRs, live ops, runtime receipts, off-repo artifacts). For a multi-agent swarm, the dangerous failure is **mixing dirty/local truth with canonical truth**. This taxonomy defines the canonicality labels the backplane assigns so the UI never has to derive truth semantics.

Grounded in the real cockpit data model `operator_coherence_cockpit.v0.1`:
- card.kind ∈ {track, proposed_track, broken_register, stash, worktree, dirty_files, branch, live_ops_surface, onboarding, runtime_db, operator_surface, preservation_risk}
- card.facets includes: `origin_backed`, `tracked`, `local_only`, `preserved`, `live`, `stale`, `intentional`, `rogue`, `operator_decision`

## Canonicality labels

Every card SHOULD carry exactly one primary `canonicality` label derived from facets + kind + git state.

| Label | Meaning | Authority source | Can drive closure? | Can drive Forge/Arena? | UI severity |
|---|---|---|---|---|---|
| `CANONICAL_ORIGIN_MAIN` | Exists and is committed on `origin/main` | remote `origin/main` | yes | yes | neutral/green |
| `CLEAN_RECONCILIATION_WORKTREE` | In a clean detached worktree at origin/main HEAD | local clean worktree | advisory | yes (read-only) | neutral |
| `OPEN_PR_REMOTE` | Proposed via open PR, not yet merged | GitHub PR | no (until merged) | candidate-only | info |
| `DIRTY_LOCAL_CANDIDATE` | Uncommitted/untracked in a dirty checkout | working tree | no | no (until extracted) | amber |
| `LOCAL_ONLY_BRANCH` | Committed locally, no remote ref | local branch | no | candidate-only | amber |
| `UNPUSHED_LOCAL_BRANCH` | Ahead of upstream, not pushed | local branch | no | candidate-only | amber |
| `ORPHANED_UPSTREAM_GONE` | Upstream deleted; local ref stranded | local branch | no | no | red |
| `STASHED_PRESERVED` | In a git stash / preservation ref | stash/preserve ref | no | no | amber |
| `OFF_REPO_ARTIFACT` | Outside the repo (.dharma, off-repo tar) | filesystem | no | no | amber |
| `UNAVAILABLE_UNCERTAIN` | Probe failed (gh/tmux/ps/network) | source_errors | no | no | grey |

## Proof-state labels (orthogonal to canonicality)

A card may also carry a `proof_state` describing evidence strength. This is separate from where the code lives.

| Label | Meaning | Example |
|---|---|---|
| `LIVE_RUNTIME_PROOF` | Fresh runtime/ack receipt observed | NATS JetStream ack receipt |
| `STATIC_CRITERIA_ONLY` | File-exists / file-contains criteria pass, no runtime proof | check_track_status SHIPPABLE |
| `STALE_RECEIPT` | Receipt exists but exceeds freshness window | live-ops `wired_stale` |
| `INFERRED` | Estimated/derived, not directly observed | test_ci_state estimated when gh unavailable |
| `CONTRADICTED` | Two sources disagree | live-ops says nats live, socket refused |

## Mapping from cockpit facets

Backplane derivation rules (deterministic):

- `origin_backed == true` and `tracked == true` and not dirty -> `CANONICAL_ORIGIN_MAIN`
- `origin_backed == false` and `local_only == true` -> `LOCAL_ONLY_BRANCH` (branch) or `DIRTY_LOCAL_CANDIDATE` (untracked/dirty_files)
- kind == `stash` or `preservation_risk` -> `STASHED_PRESERVED`
- kind == `worktree` with status `prunable` -> `ORPHANED_UPSTREAM_GONE` adjacent
- risk == `orphaned_upstream_gone` -> `ORPHANED_UPSTREAM_GONE`
- present only under `/Users/dhyana/.dharma` or off-repo tar -> `OFF_REPO_ARTIFACT`
- source present in `source_errors` -> `UNAVAILABLE_UNCERTAIN` for the dependent panel
- facets.live == true -> proof_state `LIVE_RUNTIME_PROOF`; facets.stale == true -> `STALE_RECEIPT`

## Hard invariants

1. A cockpit-rendered fact MUST NOT claim canonical status unless `origin_backed == true`.
2. The current cockpit JSON is itself generated from the DIRTY checkout, so its `track_portfolio` reflects dirty local state (11 active / max 11), NOT canonical origin/main (7 active / max 10). Until the generator runs from a clean worktree, the cockpit MUST badge its own `track_portfolio` as `DIRTY_LOCAL_CANDIDATE`.
3. `UNAVAILABLE_UNCERTAIN` MUST be shown as uncertainty, never silently coerced to a positive/negative claim.
4. Only `CANONICAL_ORIGIN_MAIN` (and read-only `CLEAN_RECONCILIATION_WORKTREE`) may feed Forge/Arena fitness decisions.
