# Workspace / Repo / Ecosystem Hygiene Block

Splice this section verbatim (adapt only the bracketed placeholders) into
any forged prompt whose target agent will touch a repository, worktree,
or local filesystem. Do not paraphrase it down — the enumerated checks
and the "forbidden by default" list are both load-bearing.

---

## Workspace hygiene (read this before touching anything)

Before making any change, gather the following — read-only, no writes:

- Repo root (`git rev-parse --show-toplevel`), current branch, and
  upstream tracking branch.
- `git worktree list` — is this checkout one of several worktrees on the
  same repo? Note any siblings.
- Dirty state: `git status --short` — count of modified/untracked files.
  If this count is large (dozens to hundreds), treat the tree as **user
  property to preserve**, not clutter to clean — see "Dirty-Worktree
  Quarantine Mode" below.
- Lockfiles present (`package-lock.json`, `pnpm-lock.yaml`, `poetry.lock`,
  `Cargo.lock`, `go.sum`, etc.) and which dependency manager they imply.
- Generated / vendor / cache directories (`node_modules/`, `dist/`,
  `build/`, `.venv/`, `__pycache__/`, `target/`, `.next/`) — do not
  descend into these for edits; do not "clean" them unless asked.
- The project's actual test/lint/build commands (check `Makefile`,
  `package.json` scripts, `pyproject.toml`, CI config) rather than
  assuming a generic `npm test` / `pytest` invocation.

**Forbidden by default** (only do these if the user explicitly asked for
this exact operation, and even then, confirm current state and flag the
risk first):

- `git reset --hard`, `git clean -f` / `-fdx`, `git checkout -- .`
- Force-push, rewriting published history, `--no-verify` / skipping hooks
- Mass reformatting or repo-wide auto-fix passes
- Dependency upgrades/downgrades not directly requested
- Deleting or moving files outside the stated scope of the task
- Mixing new agent-driven work into an already-chaotic worktree without
  the user's explicit go-ahead

## Dirty-Worktree Quarantine Mode

Trigger this posture whenever the workspace has a large number of
pre-existing uncommitted or unfamiliar changes that are **not** part of
the current task:

1. Do not touch, stash, or discard the existing changes. Inventory them
   (file count, rough categories, whether they look intentional or
   stale) and report the inventory before doing anything else.
2. Do the new work in a clean sibling worktree or fresh clone instead of
   inside the contaminated tree:
   `git worktree add -b <new-branch> <new-path> <commit-ish>`
   creates an isolated working tree and branch from a chosen commit
   without disturbing the original.
3. If the user wants the dirty tree cleaned up, that is a separate,
   explicit task — never bundle it into an unrelated feature/fix prompt.
4. If unsure whether uncommitted work is intentional, ask before treating
   it as disposable. It is not.
