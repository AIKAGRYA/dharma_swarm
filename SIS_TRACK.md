# SIS — Active Track

## Identity

| Field        | Value                          |
|--------------|--------------------------------|
| Track        | SIS (Sustainable Intelligence System) |
| Branch       | `agent/sis`                    |
| Worktree     | `/Users/dhyana/ds_sis`         |
| Base         | `main` @ `802ed21cb`           |
| Created      | 2026-07-11                     |
| Status       | ACTIVE                         |

## Quick Agent Access

```bash
# Switch to this track
cd /Users/dhyana/ds_sis

# Verify branch
git branch --show-current
# → agent/sis

# Check track status
cat /Users/dhyana/ds_sis/SIS_TRACK.md
```

## Purpose

SIS is the Sustainable Intelligence System track. It is the designated clean,
stable worktree for building, testing, and evolving SIS-domain work, including
ecological coordination (GAIA/Jagat Kalyan carbon offset), reciprocity ledger
infrastructure, and sustainable AI mission substrates.

## Agent Protocol

- **Read this file first** before touching anything in this worktree.
- All SIS work is committed to branch `agent/sis`.
- Do NOT push directly to `main` from this worktree.
- PRs from `agent/sis` → `main` require operator review.
- This worktree is the single source of truth for SIS-scoped work.

## Discovery Invariant

Any agent can locate this track by:

1. Path: `/Users/dhyana/ds_sis`
2. Branch: `agent/sis`
3. This file: `/Users/dhyana/ds_sis/SIS_TRACK.md`
4. Git worktree list: `git --no-pager worktree list | grep ds_sis`

## Governance

- Type: `active_spec` (see `docs/AGENTS.md`)
- Owner: operator
- Replaces/extends: `claude/sis-seed1-carbon-attribution` (prior seed branch, now superseded)
