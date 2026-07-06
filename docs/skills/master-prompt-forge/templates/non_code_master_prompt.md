# Template: Research / Writing / Analysis Agent Prompt

Use this template for any seed whose target is not a coding agent: a
research agent, a writing task, an analysis or synthesis request. No
workspace hygiene block — instead, evidence/citation discipline is
mandatory and load-bearing. Fill every bracketed section from the seed;
delete this instruction line before returning the final prompt.

---

```
# [Short task title inferred from the seed]

## Role
You are [target agent — e.g. "a research agent producing a cited report" /
"a writing assistant producing a final draft, not an outline"].

## Goal
[One to two sentences: the concrete outcome, inferred from the seed.]

## Inferred assumptions
- [Assumption 1, and why it was inferred]
- [Assumption 2, or "none — the seed was explicit about this"]

## Context
[What the agent needs to know: audience, prior work already done, tone/
register expected, length expectations, anything the seed implied but
didn't state.]

## Constraints & non-goals
- [What NOT to cover / produce]
- [Any hard limits: length, sources to avoid or require, time period]

## Deliverables
- [Concrete artifact: e.g. "a 1000-1500 word report", "a comparison
  table plus a one-paragraph recommendation", "3 alternative drafts"]

## Evidence / verification discipline
- Every non-obvious factual claim must be traceable to a source; state
  the source inline, not just in a bibliography.
- Distinguish clearly between "verified from a source" and "inference/
  opinion" — never blend the two without marking which is which.
- If sources conflict, say so rather than silently picking one.

## Subagent / swarm strategy (only if the task warrants decomposition)
[Suggested split — e.g. "parallel searches by angle, then synthesis" —
or omit this section entirely for a small, single-pass task.]

## Done when
- [Checkable criterion 1 — e.g. specific question answered with sources]
- [Checkable criterion 2 — e.g. specific format/length requirement met]
- [Checkable criterion 3 — e.g. explicit call-out of any unresolved
  uncertainty rather than papering over it]
```
