# Sublimation Foundry — Operator Unblocks

**Role:** reference (operator checklist). No runtime/merge/governance authority.
Subordinate to `docs/governance/ACTIVE_TRACK.yaml` (track `organism-rewire-2026-07`,
next-item 15) and the Foundry plan. Owned by that track.
**Audience:** the operator. You do not need to write or read code to do any of this.

This is the complete list of things only a human with accounts and money can do.
Everything else the Foundry builds and runs itself. Each item is reversible and
takes minutes. Nothing here spends more than the confirmed budget ($300/mo model
spend + $200/mo benchmark compute).

## 1. One currently priced provider route

Provider marketing tiers are not accounting evidence. A key is usable only
when its exact pinned model/endpoint has a current conservative tariff binding.
One admissible route is sufficient; do not provision two keys merely to satisfy
an installer check.

1. Prefer the already staged Z.AI credential if the operator confirms it is
   authorized for the general API. Foundry pins `glm-4.6` at
   `/api/paas/v4`, not the Coding Plan endpoint.
2. OpenRouter's exact `:free` model may be used while its dated built-in tariff
   is current.
3. Groq, Cerebras, and NVIDIA require account-specific upper-bound rate,
   provenance, checked-at, and valid-until fields alongside the key—even when
   the account presently bills zero.

`moonshot-v1-8k` is excluded because it retires on 2026-08-31; the staged
Moonshot route has also returned 429. Do not treat `MOONSHOT_API_KEY` as a live
fallback. Keys and tariff fields stay only in the existing root-owned
`/root/.dharma/foundry.env` described in `RUNNING_NONSTOP.md`, never in the
repository or a copied environment file. If every admissible route fails for
three bounded no-proposal cycles, Foundry persists a terminal KILL.

## 2. Ratify the revenue wedge (one decision)

The first paid product — a ~$2,500 "did this agent do what it claimed"
verification receipt — cannot go out until you say yes to the offer, the price,
and the outreach policy. This is gate 1 in
`reports/revenue_wedge/first_cash_receipt_status.md`, and it currently blocks
the whole revenue lane.

- The offer is written for you at `docs/offers/agent-behavior-verification.md`.
- Say yes/no to: (a) the offer as written, (b) the ~$2,500 price, (c) letting
  approved outreach go out to a named list you approve.
- Nothing sends until you approve both the policy and each specific list.

## 3. Optional: GitHub Secure Open Source Fund (deadline 2026-08-24)

A $10,000 grant for verified open-source security/reliability contributors.
Foundry work (verified improvements to AI-safety and eval tooling) fits the
theme. This is a lottery-ticket, not load-bearing to the plan.

- Apply at the GitHub Secure Open Source Fund page if the deadline is still
  open when you read this. One short application; the swarm can draft it, you
  submit under your name.

## What you do NOT have to do

- No coding, ever.
- No writing work packets — the Foundry lane emits its own.
- One explicit VPS deployment/reconciliation is required; use the versioned
  installer and legacy-quarantine procedure in `docs/foundry/RUNNING_NONSTOP.md`.
  After that, systemd and the repository-owned status cron supervise it.
- No live-capital account and no trading account — the Foundry never trades.
- Live capital, if ever, comes last and only by a separate explicit grant.

## Recurring (a few minutes, most days)

- Glance at the daily walking brief on your phone; merge or reject the
  draft PRs marked walk-ready.
- Review tariff expiry/status and replenish only the route actually authorized.
- Emergency stop, if ever needed: run the `loop-emergency-stop` GitHub Action.
