# Sublimation Foundry — Operator Unblocks

**Role:** reference (operator checklist). No runtime/merge/governance authority.
Subordinate to `docs/governance/ACTIVE_TRACK.yaml` (track `organism-rewire-2026-07`,
next-item 15) and the Foundry plan. Owned by that track.
**Audience:** the operator. You do not need to write or read code to do any of this.

This is the complete list of things only a human with accounts and money can do.
Everything else the Foundry builds and runs itself. Each item is reversible and
takes minutes. Nothing here spends more than the confirmed budget ($300/mo model
spend + $200/mo benchmark compute).

## 1. Four free/cheap accounts (about 30 minutes, all reversible)

Do these in order. The first four unblock roughly 2,000 free candidate
generations per day before any per-token spend.

1. **OpenRouter** — one-time $10 to lift the free-model limit from 50/day to
   1,000/day, forever. Create an account, add $10 of credit.
   <https://openrouter.ai> · then paste the API key where the setup asks
   (`OPENROUTER_API_KEY`).
2. **Groq** — free tier, no card needed to start; adding a card (spends $0)
   raises limits 10x. Fast lane for the "judge" models.
   <https://console.groq.com/keys> · key goes in `GROQ_API_KEY`.
3. **Cerebras** — free, no card: ~1,000,000 tokens/day, very fast. The
   second decorrelated free lane. <https://cloud.cerebras.ai> ·
   key goes in `CEREBRAS_API_KEY`.
4. **NVIDIA build.nvidia.com** — free developer signup, 1,000 model credits
   (up to 5,000 on request). Hosts Nemotron 3.5 Lightning and others.
   <https://build.nvidia.com> · key goes in `NVIDIA_NIM_API_KEY`.

Keys are stored as Cloud Agent secrets (Dashboard > Cloud Agents > Secrets),
never in the repo. If a key is missing the Foundry simply uses fewer lanes; it
never stops.

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
- No running servers or daemons — the CI lane runs on a schedule.
- No live-capital account and no trading account — the Foundry never trades.
- Live capital, if ever, comes last and only by a separate explicit grant.

## Recurring (a few minutes, most days)

- Glance at the daily walking brief on your phone; merge or reject the
  draft PRs marked walk-ready.
- Keep the four provider credits topped up if they run low.
- Emergency stop, if ever needed: run the `loop-emergency-stop` GitHub Action.
