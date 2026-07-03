<!--
dharma_swarm pull request template.
Delete sections that don't apply, but keep at least: Why, Surface, Verification.
-->

## Why

<!-- 1-3 sentences: what problem does this solve, what prompted it,
     and what changes for users / operators / agents after merge? -->

## Surface area touched

<!-- List the modules, services, and worktrees this change affects. -->

- [ ] `dharma_swarm/...`
- [ ] `api/...`
- [ ] `dashboard/...`
- [ ] `scripts/...`
- [ ] `tests/...`
- [ ] `docs/...` / DocOps
- [ ] `.github/` / governance configs

### Worktree mirrors checked

If this touches a hot-path symbol that exists in multiple worktrees,
record the blast-radius check:

```
# get_blast_radius output for affected symbols (paste output here):
```

Hot-path symbols mirrored across worktrees include `_complete_deferred_startup`
and any `swarm.py` / `orchestrator.py` / `runtime_state.py` change.

## Interface mismatch impact

- [ ] No new mismatch introduced
- [ ] Existing mismatch resolved — `INTERFACE_MISMATCH_MAP.md` updated
- [ ] Net-new mismatch documented in the map (transitional)

## Coherence Delta

Every PR must answer these four fields. If any answer is UNKNOWN, say why.

- Organ touched:
- Declared-vs-actual gap closed:
- Proof that re-reads the map:
- New drift introduced:

## Pre-flight check (collision prevention)

Before opening this PR, did you check that no other open PR addresses the same BR-id(s)?

- [ ] Ran `gh pr list --state open --search "BR-NNN"` for each cited BR-id, OR no BR-id cited
- [ ] No collision found, OR collision noted and coordinated:

A `pr-collision-detect` workflow runs on PR open and posts a warning comment if any BR-id in this body matches an open PR. See `docs/governance/COHERENCE_DELTA.md` § "Pre-flight check" for why this matters.

## Verification

How was the change verified end-to-end? Check all that apply.

- [ ] `make test-fast` (fast subset)
- [ ] `make test` (standard suite)
- [ ] `make semgrep` clean (or new findings triaged inline)
- [ ] `make gitleaks` clean
- [ ] `make docops-integrity` clean
- [ ] Pre-commit hooks pass on each commit
- [ ] Manual smoke (describe below)

```
# paste verification command output / screenshot reference here
```

## Plan reference

<!-- Link to the planning doc if this PR comes from a multi-step plan. -->
- Plan: `~/.claude/plans/...` or N/A

## DocOps impact

- [ ] No count-sensitive documentation claims changed
- [ ] Count-sensitive claims refreshed via `make docops-integrity`
- [ ] Python-file changes reviewed against DocOps change-review warnings
- [ ] New authority-scope language is registered or locally scoped

## Risk + rollback

- Blast radius: <!-- low / medium / high; what breaks if this is bad? -->
- Rollback: <!-- single revert? Multi-step migration? Stateful? -->

## Checklist

- [ ] No unintended changes (`git diff main...HEAD --stat` reviewed)
- [ ] No new files at repo root (per `CLAUDE.md` — use `docs/`, `scripts/`, etc.)
- [ ] No `git add -A` / `git add .` in any added scripts
- [ ] Tests added / updated for behavior change
