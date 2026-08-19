# Offer — Agent Behavior Verification ("Did this agent do what it claimed?")

**Role:** offer (reference). No runtime/merge/governance authority. Owned by
`organism-rewire-2026-07` (next-item 15). Sibling of
`docs/offers/agentic-code-governance-sprint.md` — same receipt machinery, a
different lens.
**Status:** outreach-gated. Nothing is sent to anyone until the operator ratifies
the offer, the price, and a named prospect list (gate 1 in
`reports/revenue_wedge/first_cash_receipt_status.md`).

---

## What the buyer gets

A sealed, independently-reproducible verdict on whether a specific AI agent
behaves as claimed under adversarial pressure — delivered as:

1. A **sealed receipt** (`foundry_improvement.v1`) — the evidence record.
2. A **rendered report card** (pure function of that receipt) with a
   **mandatory published-misses appendix** — the readable deliverable.

The verdict is produced by the same three-ring method the Foundry uses on
open-source code, pointed at the buyer's agent:

- **Ring 1 — blind, tripwired testing.** The behavioral suite runs in isolation
  the agent cannot read, with tripwires for scope violations, escape-hatch
  calls, nondeterministic results, and implausibly fast passes.
- **Ring 2 — held-out re-verification.** Claims are re-checked on scenarios the
  agent never saw, and we report the survival rate.
- **Ring 3 — external confirmation.** Where the buyer permits, the record is
  posted to a venue neither of us controls; otherwise the buyer holds the
  reproducible receipt and can re-run it.

## Price and scope

- **Fixed fee: ~$2,500** for a single-agent verification engagement (below the
  $5K floor of the governance sprint; a fast, concrete first receipt).
- Optional **$2,000/month continuous re-verification** retainer (the same card,
  re-run on a schedule as the agent and the threat landscape change).
- Scope is one agent, an agreed claim set, and an agreed behavioral suite. No
  source access is required; black-box behavioral testing is the default.

## What it is NOT

- Not a certification or a compliance sign-off. It is an independent, honest,
  reproducible measurement with the misses shown.
- Not a pass-guarantee. If the agent fails, the report says so — that honesty is
  the product.
- Not a security-vulnerability service. (The Foundry never files AI-generated
  security reports; that is a hard non-goal.)

## Why this and not a vendor's own eval

Every serious failure in this field — the retracted CUDA-Engineer speedups, the
MLX kernel that was actually slower, the fabricated benchmark logs — happened
because a number was trusted before an independent party re-ran it. The buyer's
own eval grades its own homework; this offer is the outside witness with a
public track record and published misses. See
`docs/foundry/anatomy/2026-08-18_when_the_kernel_lied.md`.

## Where the first dollar goes (for the operator)

The first paid engagement is the **domain-2 One Wire receipt** — the receipt in
a second, distinct domain that (with the existing external-code-contribution
receipts and one more domain) moves the swarm's blocked self-improvement loops
toward quorum. The money is real income; the receipt is the metabolic unlock.
Every sale is recorded through RevenueSpine with the stratified fields
(counterparty, value/risk, independence, transfer).
