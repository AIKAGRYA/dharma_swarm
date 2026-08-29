# Foundry Outreach — scaffolding (operator-approval-gated)

**Role:** reference (operator scaffolding). No runtime/merge/governance
authority. Owned by `organism-rewire-2026-07` (next-item 15).

**Hard rule:** nothing in this folder sends anything. Outreach is operator
hands only. The swarm may *draft* a prospect list and messages here; a human
approves the policy once, then approves each specific list before any send.
This mirrors the revenue-wedge outreach policy and the CLAUDE.md rule that
publishing to the outside world is an operator decision.

## The sequence (per the plan, PR #1384 verdict)

1. Publish the anatomy article
   (`docs/foundry/anatomy/2026-08-18_when_the_kernel_lied.md`) so outreach has a
   credible public artifact to point at.
2. Operator ratifies the offer + price + policy
   (`docs/offers/agent-behavior-verification.md`).
3. Draft ~20 real prospects in `PROSPECTS.md` (use `PROSPECTS_TEMPLATE.md`).
4. Operator approves the list. Then, and only then, send the approved message
   to the approved names — by the operator's hand.
5. First reply/engagement → record through RevenueSpine; first payment is the
   domain-2 One Wire receipt.

## Files

- `PROSPECTS_TEMPLATE.md` — the columns to fill (one row per prospect).
- `OUTREACH_TEMPLATE.md` — the message template (fill the brackets; keep it
  short, lead with the receipt, never spam).

Create `PROSPECTS.md` (gitignored / operator-held if it contains real contact
details — do not commit personal data) from the template when ratified.
