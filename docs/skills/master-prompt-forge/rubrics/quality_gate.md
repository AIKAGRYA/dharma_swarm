# Quality Gate

Run every forged prompt through this checklist before returning it. If any
required item fails, fix the draft — do not return a prompt that fails
its own gate.

## Required for every forged prompt

- [ ] **Goal is concrete**, not a restatement of the seed's vague phrasing.
- [ ] **Assumptions are labeled**, not silently baked in. If the forger
      guessed at scope, target, or intent, that guess is visible.
- [ ] **Scope is bounded** — constraints/non-goals section says what NOT
      to do, not just what to do.
- [ ] **Deliverables are specific** — format and artifact stated, not just
      "do the thing well."
- [ ] **Evidence/verification discipline is present** and fits the task
      (commands to run for code; sourcing/citation rules for research).
- [ ] **"Done when" is checkable** by someone other than the executing
      agent — no criterion that only the agent itself could judge.
- [ ] **No stylistic padding.** Every section earns its place; nothing is
      restating the same instruction in different words.

## Required only when the target touches a repo/workspace

- [ ] **Workspace hygiene block is present verbatim**, not paraphrased or
      trimmed.
- [ ] **No destructive operation is a default/first move** — force-push,
      hard reset, mass clean, dependency upgrades are absent unless the
      user explicitly asked for that exact operation, and even then the
      prompt requires a state check + risk flag first.
- [ ] **Dirty-tree handling matches severity.** If the seed describes (or
      the forger infers) a workspace with substantial pre-existing
      uncommitted state, quarantine-mode language is present, not a
      cleanup instruction.

## Required only when the task is large enough to warrant it

- [ ] **Subagent/swarm strategy, if included, is proportionate** — not
      proposed for a task a single pass could finish; not omitted for a
      task that genuinely needs decomposition to fit in one pass.

## Red flags — if any of these are true, the draft fails

- The forged prompt is shorter and less specific than the contract in
  `templates/master_prompt_contract.md` would produce.
- The forged prompt tells a coding agent to clean up, reset, or reformat
  a workspace as an opening move without the user asking for exactly that.
- The forged prompt has a "done when" that boils down to "when it feels
  finished."
- The forged prompt asks for citations/evidence but never says what
  counts as one.
