---
id: doc-code-drift
version: 0.0.1
theme: 21-drift-and-entropy
status: tested
invariant: >
  Documentation that contradicts the code is worse than none — it actively misleads,
  and readers trust it. Drift is detectable where a doc makes a CHECKABLE claim (a
  count, a path, a command, an API signature, a config key) that can be diffed against
  the code. The durable fix is not "update the doc" — it's to make the claim GENERATED
  from the code (single source of truth) so it cannot drift again.
lineage:
  - "Lehman's laws — a system and its description both decay unless continuously updated"
  - "Knuth — literate programming: doc and code as one artifact, not two that diverge"
  - "single source of truth — generate the volatile claim, don't hand-maintain it"
ground_truth_tools: ["diff doc claims (counts/paths/commands/signatures) against the code", "is the claim generated or hand-typed?", "last-touched dates"]
returns_clean: true
---

## Prompt

> Detect **doc↔code drift**. The invariant (Lehman): a doc that contradicts the code
> misleads with authority. Target **checkable** claims — counts, file paths, commands,
> API signatures, config keys, env vars — and diff each against the actual code. For
> each drift: the doc location, the claim, the actual value, and the **durable fix**:
> prefer **generating** the claim from code (single source of truth) over hand-editing,
> so it can't drift again.
>
> Ignore prose/intent (not mechanically checkable). **Return clean** for docs whose
> checkable claims match — and flag *hand-maintained volatile claims* (a frozen count
> in prose) as drift-prone even if currently correct.

## Why it's built this way

You can't mechanically check "this explains the architecture well," but you *can*
check "771 modules," "see `foo.py:42`," "run `make bar`." The discipline is scoping to
checkable claims and pushing the fix toward generation — because a hand-typed count is
drift waiting to happen (Lehman), and literate/generated docs are the structural cure.

## Demonstration run

**Target:** `dharma_swarm/`, 2026-06-25.

- **The repo already knows it drifts** — `CLAUDE.md` warns about drift **6 times**,
  e.g. *"If this file disagrees with that output on anything live (track id, prereqs,
  recent commits), trust the onboarding output"* and *"do not freeze a count here
  (that duplication is exactly how this section rotted)."* That's a codebase that has
  *felt* doc-drift and built a reconciliation rule.
- **Disciplined finding:** the drift-prone claims are the **hand-typed counts/paths**
  in `CLAUDE.md` / map docs (module counts, BLOCKER tallies, frozen percentages). The
  durable fix is exactly what the repo half-did: make them **generated** (`make
  onboard` / `make xray` render live state) and have the prose **point at the
  generator** instead of repeating the number. Where a doc still hard-codes a count,
  flag it — even if right today, it's drift-by-construction.
- **Return clean** on docs that already defer to a generator (the onboarding system).

This is the rare case where the repo's own canon *states the invariant for us* — the
prompt just operationalizes "trust the generated source, not the frozen prose."

## Changelog

- **v0.0.1** (2026-06-25) — doc↔code drift (Lehman/Knuth/SSOT): diff checkable claims,
  push fix toward generation, flag hand-typed volatile claims. Tested on `dharma_swarm`:
  the repo self-warns about drift 6× in `CLAUDE.md`; flagged hand-typed counts as
  drift-by-construction with "generate it" as the durable fix.
