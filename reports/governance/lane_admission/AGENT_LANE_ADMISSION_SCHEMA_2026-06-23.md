# Agent Lane Admission Packet Schema — 2026-06-23

## Why this exists

The operator routinely runs 4–10 agents in parallel across providers, windows, branches, and worktrees. The cockpit makes that work *visible*; this schema makes it *admissible*. Every lane that wants to influence canonical state (ACTIVE_TRACK.yaml, closures, Forge/Arena) must first emit a Lane Admission Packet so the backplane can classify and gate it.

This is the contract between "an agent did work somewhere" and "that work is allowed to change the canonical organism."

## Packet schema (`dharma.agent_lane_admission.v1`)

Required fields:

- `lane_id` — stable id, e.g. `operator-coherence-cockpit-2026-06-23`
- `agent_or_provider` — who built it (claude/codex/devin/local/remote + model)
- `branch` — current branch
- `worktree` — absolute path
- `base_ref` — ref it forked from (ideally origin/main SHA)
- `canonicality` — one label from the canonicality taxonomy
- `intended_surfaces` — globs the lane declares it owns
- `actual_touched_surfaces` — files actually modified/added (git status truth)
- `dirty_untracked_count` — count of dirty+untracked entries
- `verification_commands` — exact commands run
- `verification_results` — pass/fail per command
- `receipt_paths` — durable receipts/artifacts produced
- `preservation_status` — none | local_only | off_machine
- `depends_on` — other lane_ids / track ids
- `conflicts_with` — lane_ids / surfaces that overlap
- `candidate_track` — proposed track id if promoted
- `promotion_recommendation` — see enum
- `operator_decision_needed` — booleans/notes requiring John
- `forge_arena_relevance` — none | input_source | prerequisite | consumer

## promotion_recommendation enum

- `ADMIT_AS_ACTIVE_TRACK`
- `FOLD_INTO_EXISTING_TRACK`
- `KEEP_CANDIDATE`
- `ARCHIVE_PRESERVED`
- `NEEDS_PROD_REVIEW`
- `BLOCKED_EXTERNAL_AUTH`
- `DO_NOT_PROMOTE`

## Admission gate (deterministic order)

A lane may be `ADMIT_AS_ACTIVE_TRACK` only if ALL hold:

1. `canonicality` is at least `OPEN_PR_REMOTE` (i.e. not pure dirty/local) OR an explicit operator-approved extraction plan exists.
2. `actual_touched_surfaces` ⊆ `intended_surfaces` (no scope leakage).
3. `verification_results` all pass (or failures are explained and accepted).
4. No unresolved `conflicts_with` against an ACTIVE track's owned surfaces.
5. `preservation_status != none` if the lane carries unique local-only value.
6. Admitting it keeps the canonical portfolio within `max_active` (currently 7/10, so room exists).
7. `NEEDS_PROD_REVIEW` is cleared if the lane claims production-grade.

If any fail -> downgrade to `KEEP_CANDIDATE` / `NEEDS_PROD_REVIEW` / `BLOCKED_EXTERNAL_AUTH`.

## Relationship to the cockpit

The cockpit already emits cards with `kind`, `lane`, `status`, `risk`, `decision_type`, `facets`. A Lane Admission Packet is the **promotion-grade superset** of a cockpit card: a card observes a lane; a packet proposes what to *do* with it and records the gate result. The backplane can synthesize a draft packet from any cockpit card of kind `branch|worktree|dirty_files|proposed_track` and let an owner complete it.

## Worked example: the cockpit lane itself

See `OPERATOR_COHERENCE_COCKPIT_LANE_PACKET_2026-06-23.{md,json}` — it is the first instance of this schema. Its current values:

- canonicality: `DIRTY_LOCAL_CANDIDATE`
- verification_results: PASS (compile, pytest, json, lint, build)
- preservation_status: local_only
- promotion_recommendation: `KEEP_CANDIDATE` -> extract to dedicated branch -> then `ADMIT_AS_ACTIVE_TRACK`
- forge_arena_relevance: `prerequisite`
