---
name: master-prompt-forge
description: Turn a rough, vague, under-articulated, misspelled, or emotionally compressed seed into a master-level prompt for Claude, Codex, Claude Code, repo agents, research agents, or swarms. Use whenever the user pastes a short/messy idea and asks for it to be turned into a prompt, task spec, or brief for another agent or session — including phrases like "forge this into a prompt", "turn this into a master prompt", or "write me a prompt for X".
---

# Master Prompt Forge

Take the user's seed — however rough — and infer the strongest useful task
inside it, then produce a complete, execution-ready prompt for the target
agent (Claude, Codex, Claude Code, a repo agent, a research agent, or a
swarm of agents). Do not merely rephrase the seed. Add the structure a
seed never has on its own.

## When invoked

1. Read the seed. Identify: the actual goal, the target agent/surface
   (repo-code agent vs. research/writing agent vs. multi-agent swarm), and
   anything load-bearing that's implied but unstated.
2. Pick the base template:
   - Code / repo / Claude Code / Codex / agentic-terminal work →
     `templates/repo_agent_master_prompt.md`. This template requires the
     hygiene block from `templates/workspace_hygiene_block.md` — always
     splice it in verbatim, never paraphrase it away.
   - Research, writing, analysis, or any non-code deliverable →
     `templates/non_code_master_prompt.md`.
   - Either way, both templates are built on the shared contract in
     `templates/master_prompt_contract.md` — read that first, it defines
     the sections every forged prompt must have.
3. Fill every section of the chosen template from the seed. Where the seed
   is silent on something load-bearing, do not invent silently — write the
   assumption inline (e.g. "Assuming X because the seed didn't specify Y")
   so the user can correct it before it ships.
4. Self-check the draft against `rubrics/quality_gate.md` before returning
   it. Fix anything that fails the gate; do not present a draft that fails
   it and hope the user won't notice.
5. Return the forged prompt as a single copy-pasteable block. If the
   target is Codex rather than Claude, mention that
   `codex/AGENTS.fragment.md` exists and can be merged into the target
   repo's `AGENTS.md` so Codex inherits the same hygiene doctrine
   automatically on future runs.

## Core behavior (non-negotiable)

- **Infer, then label.** Guess the strongest useful task from a weak seed,
  but always surface the guesses as explicit assumptions — never bury them.
- **Context engineering, not prompt decoration.** Add the context an
  executing agent actually needs (repo state, constraints, prior art,
  non-goals) rather than stylistic flourishes.
- **Evidence discipline.** Every forged prompt for a research or claims-
  bearing task must require the executing agent to cite what it verified,
  not just what it concluded.
- **Workspace hygiene is mandatory for any code/repo target.** See
  `templates/workspace_hygiene_block.md`. A forged prompt for a coding
  agent that omits this block has failed the quality gate.
- **Never default to destructive.** A forged prompt must never instruct
  an agent to `git reset --hard`, `git clean -fdx`, force-push, mass-
  reformat, or upgrade dependencies as a default/first move. If the seed
  explicitly asks for one of these, keep it, but require the executing
  agent to confirm current state first and flag the risk instead of
  auto-approving it.
- **A dirty worktree is user property, not trash.** If the seed mentions
  a repo with a large number of uncommitted/tracked changes, route through
  the quarantine posture in `templates/workspace_hygiene_block.md`
  ("Dirty-Worktree Quarantine Mode") instead of proposing cleanup.
- **Always end with "done when."** Every forged prompt states concrete,
  checkable completion criteria — not "make it good," but what a reviewer
  can verify.

## Supporting files (loaded only when needed)

- `templates/master_prompt_contract.md` — the shared skeleton every
  forged prompt is built from (role, context, constraints, deliverables,
  done-when, evidence discipline, assumptions).
- `templates/workspace_hygiene_block.md` — the mandatory read-only-first
  hygiene section for any prompt that touches a repo or workspace,
  including the dirty-worktree quarantine posture.
- `templates/repo_agent_master_prompt.md` — full template for Claude Code
  / Codex / repo / swarm agent prompts.
- `templates/non_code_master_prompt.md` — full template for research,
  writing, and analysis prompts (no hygiene block; adds evidence/citation
  discipline instead).
- `rubrics/quality_gate.md` — the checklist a forged prompt must pass
  before being returned to the user.
- `codex/AGENTS.fragment.md` — a portable fragment for a target repo's
  `AGENTS.md` so Codex applies the same forging + hygiene doctrine without
  needing this skill re-invoked each time.
- `scripts/dirty_worktree_report.sh` — read-only inventory of a repo's
  git state (branch, upstream, worktrees, dirty file count, lockfiles,
  generated/vendor/cache dirs). Never mutates anything; safe to suggest
  running before any cleanup decision.
