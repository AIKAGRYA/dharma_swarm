<!--
Paste this fragment into a Codex AGENTS.md (global ~/.codex/AGENTS.md, or
a repo-local AGENTS.md) so Codex applies master-prompt-forge's doctrine
without the skill being re-invoked by name each time. Codex reads layered
AGENTS.md guidance (global, then repo-local) before acting; this fragment
is meant to compose with whatever else is already in that file, not
replace it.
-->

## Master Prompt Forge doctrine

When asked to turn a rough or vague seed into a prompt, task spec, or
brief for another agent (including yourself in a later session), do not
just rephrase the seed. Produce a complete prompt with:

1. A concrete goal inferred from the seed.
2. Assumptions labeled explicitly wherever the seed was silent on
   something load-bearing — never bake in a silent guess.
3. The context an executing agent would actually need (repo conventions,
   prior art, constraints, what not to touch).
4. Explicit constraints and non-goals.
5. Specific deliverables (format, not just content).
6. Evidence/verification discipline: for code, which commands to run and
   what "verified" looks like; for research/writing, sourcing and
   citation rules.
7. Concrete, checkable "done when" criteria.

### Workspace hygiene (mandatory whenever the task touches a repo)

Before making any change: check repo root, current branch, upstream,
`git worktree list`, `git status --short` dirty-file count, lockfiles
present, and the project's real test/lint/build commands (from its
Makefile/package.json/pyproject.toml, not assumed defaults). Do not
descend into generated/vendor/cache directories (`node_modules/`,
`dist/`, `build/`, `.venv/`, `__pycache__/`) for edits.

Never perform, as a default/first move: `git reset --hard`, `git clean
-fdx`, force-push, rewriting published history, `--no-verify`, mass
reformatting, or unrequested dependency upgrades. If the user explicitly
asked for one of these exact operations, confirm current state and flag
the risk before doing it — never treat it as a safe opener.

If the workspace has substantial pre-existing uncommitted or unfamiliar
changes unrelated to the current task, treat it as **user property to
preserve**, not clutter to clean: inventory it, report the inventory, and
do the new work in a clean sibling worktree (`git worktree add -b
<branch> <path> <commit-ish>`) instead of inside the contaminated tree.
Cleanup of pre-existing dirty state is a separate, explicit task — never
bundle it into an unrelated feature/fix.
