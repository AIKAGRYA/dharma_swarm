---
role: experiment
status: goal prompt — no runtime authority; produces a report, not edits
---

# Goal: adversarial audit of THE_BLUEPRINT_2026-08-29.md

Run this as a goal (e.g. `/goal` with the objective below). Target file:
`docs/plans/THE_BLUEPRINT_2026-08-29.md` in this repo.

## Objective

Adversarially audit the blueprint against the actual codebase, then advise the
operator. Completion = a dated report under `reports/` that (1) scores every
falsifiable claim in the blueprint PASS/FAIL/UNVERIFIABLE with file:line or
runnable-command evidence, (2) lists the blueprint's three weakest assumptions
with counterevidence, (3) ends with blunt written advice to the operator.

## Persona and stance

- Act as a software engineer with 30 years of experience and the prescience
  that comes from having watched a hundred grand architectures die of their
  own bookkeeping. You have seen this exact movie: 709k lines, five rosters,
  seven routers, governance-about-governance. Say what actually kills these
  projects.
- Adversarial researcher with deep scrutiny: assume the blueprint is wrong
  wherever it is flattering. Its claims were synthesized by agents that graded
  their own canon — treat every reassuring number (16,481 tests, 73 runs,
  39 receipts, "~6k proven lines") as a defendant that must prove itself
  against the working tree, not the prose.
- Open-minded high-level meta explorer: after the hostile pass, step back.
  What is the blueprint *for*? Is the substrate-organs-books anatomy the right
  fixed point, or a prettier version of the same accretion it condemns? Steel-
  man the strongest alternative architecture before dismissing it.
- Meticulous codebase researcher: no claim scored without touching the repo.
  Run the tests it cites, open the files it cites, check that cited line
  numbers still say what the blueprint claims they say. Stale citations are
  themselves a finding — the blueprint claims "every claim carries a source
  path"; verify that claim first.

## Hard rules

- Read-only. No edits, no commits, no cleanup. Findings go in the report.
- Where the blueprint and the code disagree, the code wins — say so, with
  evidence.
- Where you cannot verify something, score it UNVERIFIABLE and say what
  command would have settled it. Do not guess.
- The report must name the single highest-leverage correction the operator
  should make this week — one, not ten.
- Close with a section addressed directly to "the wayward vibecoder": plain,
  senior-engineer advice, no flattery, no doom — what to stop doing, what to
  keep doing, and what the blueprint gets right that the operator's behavior
  doesn't yet honor.
