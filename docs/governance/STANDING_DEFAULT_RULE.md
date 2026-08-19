# Standing Default Rule — asks carry deadlines and defaults

**Status:** drafted 2026-08-18 under the yes-sheet ratification
(docs/plans/YES_SHEET_RATIFICATION_2026-08-18.md, row "+"). **Enacted when the
PR carrying this file merges.** Authority: operator.

## The rule

Every question an agent puts to the operator MUST carry three parts, stated in
the ask itself:

1. **The ask** — one line, answerable with a word.
2. **A deadline** — a concrete date/time by which silence is interpreted.
3. **A pre-stated default** — the exact action that executes if the deadline
   passes with no answer.

An ask missing any of the three is malformed; agents treat a malformed ask as
their own defect, not the operator's backlog.

## The hard exception

**Live-money and live-authority asks never default to yes.** Any ask whose
"yes" would (a) spend or stake money, (b) publish to the outside world under
the operator's name, (c) widen an agent's standing authority, or (d) do
something that cannot be undone, may only carry a default of **no / hold**.
Silence on such an ask always means "not yet." Deadlines on these asks exist
only to expire the offer, never to execute it.

## Why this exists

The 2026-08-18 Playing-Small Audit found the portfolio's largest single drag
was decision latency: asks phrased without deadlines or defaults sat open for
weeks, and agents treated the silence as a stop sign. This rule converts
silence into a scheduled outcome for reversible work while keeping every
irreversible door operator-locked.

## Mechanics for agents

- State the default in the same sentence as the ask: "Default if no answer by
  Friday: I close the eight stale drafts."
- Record executed defaults the same way as answered asks: cite the ask, the
  deadline, and the silence in the receipt or PR body that carries the action.
- A default that executed on silence is still reversible on the operator's
  later word; reverse it without argument.
- Never batch a live-money ask inside a reversible-work ask to inherit its
  default. One ask, one default class.
