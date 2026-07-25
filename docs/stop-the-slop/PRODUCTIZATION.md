# Productization — what makes this a $1000 ticket, not a $40 markdown pack

> Role: `reference`. This doc is positioning/pricing analysis, not authority. It does
> not gate runtime or doctrine.

## The honest starting point

An independent adversarial review priced **v0 at $20–40 one-time** — and was right.
v0 was inert markdown: every "Demonstration run" was trust-me prose, and three of the
five audited demos had reproduction defects (the flagship crowned the wrong
complexity function, miscounted its own ratchet coverage 4-vs-2, and silently mixed
scopes). A library whose entire pitch is "we don't manufacture findings" cannot ship
manufactured findings. The price ceiling was a credibility ceiling.

**What changed in v0.1 is the thing that moves the ceiling: the product is now
falsifiable.** The `probe/` runner executes the real instrument for each signal and
emits the row that instrument earned; every demo is regenerated from it; a buyer can
re-run one command and reproduce every number. That is the line between a prompt pack
and a tool.

## What a buyer is actually paying for (the value ladder)

1. **Prompts** (commodity) — anyone can write a markdown prompt. Worth ~$0 alone.
2. **Discipline** (scarce) — route-to-ground-truth, return-clean, an operational
   confidence rubric, scope normalization. Worth something, but unprovable as prose.
3. **Falsifiability** (the moat) — a runner that makes the discipline executable and
   every claim reproducible, plus self-tests that prove return-clean AND detection.
   This is what justifies a real price: you are buying *trust you can verify*, not
   adjectives.
4. **Integration** (enterprise) — CI gates, ratchets that can only improve, a
   composite that won't lie about scope. This is what a team pays a seat-year for.

## Tiers

### Free — "prove it to yourself"
- 3 flagship prompts (`ai-slop-index`, `circular-dependency-triage`,
  `dependency-risk-triage`) + the full `probe/` runner.
- The return-clean guarantee, demonstrated by self-tests anyone can run.
- Purpose: the anti-slop claim is checkable for free. Trust is the funnel.

### Pro — for the individual builder ("vibe coder")
- All ~52 prompts across 25 themes + the new AI-specific dimensions
  (phantom-deps, change-coupling, narrative-comment, and the roadmap'd
  mutation-test-effectiveness, spec-to-code-traceability, cognitive-load-budget).
- The runner with every signal, `--online` supply-chain checks, JSON output.
- Updates as the AI-slop literature moves (the canon is dated and cited).
- Indicative price: a modest one-time or low monthly — priced as a *tool*, not a PDF,
  because it now runs.

### Enterprise / Team — the $1000+/seat-year ticket
What actually justifies four figures is **integration and guarantee**, not more prompts:
- **CI templates** that wire each signal to a ratchet so the AI-Slop Index can only
  move down — a merge gate, not a one-time score.
- **Scope-normalized composite** across a monorepo with per-package denominators that
  don't silently mix (the exact defect that sank v0's credibility).
- **Provenance**: pinned advisory-DB snapshots and tool versions so a demo stays
  falsifiable months later instead of drifting daily.
- **Confidence-rubric reporting** auditors can read: HIGH/MEDIUM/LOW/UNASSESSED with
  the instrument named per row — defensible in a review, not a vibe grade.
- **Support + custom signals** for the org's own languages and smells.

The buyer is a team shipping AI-generated code who needs to *trust* it at the gate.
$1000/seat-year is cheap against one production incident from a hallucinated dependency
or a load-time import cycle that boots fine on the author's machine and crashes in prod.

## What still has to be true to hold the price (no overclaiming)

This doc must not become the next manufactured finding. As of v0.1:
- **Shipped & verified:** the runner, 11 signals routed to real tools, self-tests
  (return-clean + detection + offline-honesty + radon-routing), three corrected demos,
  three new dimensions, FOUNDATIONS composite/confidence/scope model.
- **Not yet shipped (roadmap, must not be sold as present):** CI ratchet templates for
  more than the 2 signals already gated in this repo; mutation-test-effectiveness,
  spec-to-code-traceability, and cognitive-load-budget prompts; a non-Python/JS demo;
  pinned advisory-DB provenance. The Enterprise tier is a *roadmap with a credible
  substrate*, and should be sold as such until those land.

The single highest-leverage next investment is the same one the review named: keep
widening the runner until **every** prompt regenerates its demo from it. Each signal
that moves from prose to executable raises the credibility ceiling — and the price —
by exactly the amount the review docked v0 for being inert.
