# Template: Repo / Code / Claude Code / Codex / Swarm Agent Prompt

Use this template for any seed whose target is a coding agent operating on
a real repository or workspace: Claude Code, Codex, a generic "repo agent",
or a swarm of such agents. Fill every bracketed section from the seed;
delete this instruction line before returning the final prompt.

---

```
# [Short task title inferred from the seed]

## Role
You are [target agent — e.g. "a Claude Code session with full repo and
shell access" / "a Codex agent running in this repository"]. [Any
persona/scope framing the seed implies, e.g. "operating as a focused
contributor, not the repo's sole maintainer."]

## Goal
[One to two sentences: the concrete outcome. Written as the forger's best
inference from the seed, in plain language.]

## Inferred assumptions
- [Assumption 1, and why it was inferred]
- [Assumption 2, or "none — the seed was explicit about this"]

## Context
[Relevant repo conventions, prior art, related modules/files, and why they
matter for this task. Point at specific paths where known. Note anything
adjacent that should NOT be touched.]

<workspace-hygiene>
[Paste templates/workspace_hygiene_block.md here verbatim]
</workspace-hygiene>

## Constraints & non-goals
- [Explicit out-of-scope items]
- [Hard limits: files/dirs not to touch, APIs not to call, turn/token
  budget if relevant]

## Deliverables
- [Concrete artifact: e.g. "a diff limited to <paths>", "a PR against
  <branch>", "a passing test file at <path>"]

## Evidence / verification discipline
- Before claiming something works, run [the actual project test/build/lint
  commands] and show the result.
- Before claiming a bug is fixed, reproduce the failure first, then show
  it resolved.
- Cite file:line for any claim about existing code behavior.

## Subagent / swarm strategy (only if the task warrants decomposition)
[Suggested split — e.g. "one agent per independent module", "a
finder/verifier pair" — or omit this section entirely for a small,
single-thread task.]

## Done when
- [Checkable criterion 1 — e.g. specific test suite green]
- [Checkable criterion 2 — e.g. specific behavior manually verified]
- [Checkable criterion 3 — e.g. no unrelated files changed]
```
