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

## Verification

How was the change verified end-to-end? Check all that apply.

- [ ] `make test-smoke`
- [ ] `make test-all` (full suite)
- [ ] `make semgrep` clean (or new findings triaged inline)
- [ ] `make gitleaks` clean
- [ ] Pre-commit hooks pass on each commit
- [ ] Manual smoke (describe below)

```
# paste verification command output / screenshot reference here
```

## Plan reference

<!-- Link to the planning doc if this PR comes from a multi-step plan. -->
- Plan: `~/.claude/plans/...` or N/A

## Risk + rollback

- Blast radius: <!-- low / medium / high; what breaks if this is bad? -->
- Rollback: <!-- single revert? Multi-step migration? Stateful? -->

## Checklist

- [ ] No unintended changes (`git diff main...HEAD --stat` reviewed)
- [ ] No new files at repo root (per `CLAUDE.md` — use `docs/`, `scripts/`, etc.)
- [ ] No `git add -A` / `git add .` in any added scripts
- [ ] Tests added / updated for behavior change
