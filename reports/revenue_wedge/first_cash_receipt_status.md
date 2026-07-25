# Revenue Wedge — First Cash Receipt Status

**Status:** NO CASH RECEIPT. Recorded revenue: **$0**. This file is the gate-evidence surface named by `docs/plans/FABLE5_CAMPAIGN_ROADMAP_2026-07-03.md` (Campaign 3) and stays honest at $0 until a real receipt exists.
**Owner surface:** `reports/revenue_wedge/` (report projection; authority stays with RevenueSpine records and One Wire guardian receipts).
**Last updated:** 2026-07-05 (receipt-lane close-out, Metabolic Loop Ignition plan).

## What exists on our side (code criterion: "nothing on our side blocks a paid engagement")

- Audit kit v0 (first slice): `scripts/revenue_wedge/audit_kit.py` — target-repo-agnostic, stdlib-only; `scan` emits a sealed JSON receipt, `render` produces the ranked slop/provenance report as a pure function of that receipt. Proven end-to-end in CI against the committed fixture repo (`tests/fixtures/revenue_wedge_target_repo/`, `tests/test_revenue_wedge_audit_kit.py`).
- Offer document: `docs/offers/agentic-code-governance-sprint.md` ($5K–$25K, 3–7 days).
- Engagement receipts path: `RevenueSpine` (`dharma_swarm/revenue/`), human-approver-gated outreach preserved.

## What flips this file (in order)

1. Operator ratifies the wedge (offer, pricing, outreach policy) — operator gate, open.
2. One approved outreach → one signed engagement.
3. Payment received → receipt recorded through RevenueSpine with counterparty evidence.
4. The receipt enters archive fitness ONLY via the One Wire guardian path (stratified fields: domain=`paid_governance_engagement`, counterparty, value/risk, independence, transfer). No self-attestation counts.

## Why this file matters beyond revenue: the path to One Wire quorum

Guardian cycle-004 (2026-07-03, `~/.dharma/forge_measurement_guardian/cycle-004-intake-restart.json`) verified quorum at **N=3/5 confirmed receipts, M=1/3 domains** — all confirmed receipts sit in `external_code_contribution`, and cycle-004's key finding is that **domain diversity, not receipt count, is the binding constraint** (4 further code-contribution merges exist; admitting them all would still leave M=1/3).

- **Domain 2 — paid work (this wedge).** First cash receipt = second domain. Cheapest verifiable first step: operator ratification + one outreach against the fixture-proven kit. Stratified fields: counterparty = paying client; value/risk = engagement fee; independence = client is not dharma-swarm-controlled; transfer = report delivered and accepted.
- **Domain 3, option (a) — ecological/GAIA pilot intake.** One real external counterparty entering the GAIA/Jagat Kalyan intake → qualification → proof-packet path. Stratified fields: counterparty = pilot participant/landholder; value/risk = restoration claim staked; independence = participant not operator-controlled; transfer = qualified claim packet accepted by the counterparty. Cheapest verifiable first step: operator selects one pilot counterparty; intake receipt is emitted by the existing `gaia_platform` pipeline.
- **Domain 3, option (b) — externally-reviewed research artifact.** The R_V P0 bridge run reviewed/replicated by a non-controlled external party (venue review or independent replication receipt). Cheapest verifiable first step: run Rung 1 + P0 co-test locally (CPU-startable), then submit to the operator-chosen venue. Slower than (a); higher narrative value.

Either domain-3 option plus this wedge's first cash receipt reaches M=3/3; N reaches 5/5 with those same two receipts (3+2). Quorum then grants archive-fitness authority — the metabolic unlock the whole plan aims at.
