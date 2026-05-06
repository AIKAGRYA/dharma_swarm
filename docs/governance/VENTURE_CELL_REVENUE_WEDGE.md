# Revenue Wedge — Venture Cell v0

> The first VentureCell instance in Dharma Swarm. Its purpose is to find
> and prove the first self-funding wedge before capital runs out.

## Identity

| Field | Value |
|---|---|
| id | `revenue-wedge` |
| kind | `venture_cell` |
| parent | `core-ops` |
| purpose | Find and ship the first self-funding offer |
| status | `proposed` |
| operator | `dhyana` |
| memory_namespace | `revenue_wedge` |

## Roster

| Agent | Type | Authority |
|---|---|---|
| `codex.local` | internal | code_generation |
| `claude.local` | internal | analysis, drafting |
| `devin.cloud` | external | code_generation, testing |

## Economy

| Metric | Value |
|---|---|
| budget_tokens | 50,000 |
| revenue_target | 10,000 |
| monthly_burn_target | 2,000 |
| current_known_burn | 0 (pre-launch) |

## Allowed Work

- AgentOps work packets scoped to revenue discovery
- Customer research and outreach drafts (human-approved only)
- Product prototyping and MVP builds
- Pricing experiments
- Daily Operating Brief generation
- YDS ledger entries (human-authored only)
- BurnReport generation
- KaizenReview cycles

## Forbidden Work

Inherited from Core Ops room + additional constraints:

- Dashboard expansion
- Ontology refactor
- Memory consolidation
- Live autonomy / unsupervised agent deployment
- Broad v3 architecture implementation
- Any external outreach without human approval
- Any spending without human approval

## Human Approval Required For

1. **Spending money** — any financial commitment
2. **External outreach** — any customer/partner contact
3. **Merge to main** — all code changes
4. **Authoritative YDS rating** — human-only quality signal
5. **Budget increase** — must show revenue proof first
6. **Sub-cell spawn** — must prove hypothesis with evidence

## Gates

| Gate | Description |
|---|---|
| `scope_gate` | Work must be in allowed_work list |
| `test_gate` | All code changes must pass tests |
| `burn_awareness` | Every packet must estimate cost before execution |
| `human_approval_external` | External actions blocked until human approves |
| `revenue_proof_gate` | Budget increase requires revenue evidence |

## Kill Conditions

The Revenue Wedge room will be dissolved if:

1. **no_revenue_after_60_days** — 60 calendar days with zero revenue
2. **budget_exceeded** — burn exceeds budget_tokens by >20%
3. **operator_override** — human operator decides to pivot

Kill triggers dissolution: agents return to Core Ops pool, unspent
budget returns to parent, memory archived under `revenue_wedge/`.

## Spinout Conditions

The Revenue Wedge room may graduate to independent status if:

1. **revenue_exceeds_burn** — 3 consecutive months of revenue > burn
2. **operator_approval** — human operator approves graduation
3. **customer_validation** — 3+ paying customers or equivalent proof

## Jagat Kalyan Constraint

> "Revenue without welfare is extraction."

The Revenue Wedge must demonstrate that its product/service creates
genuine value for customers — not just extracts money. Each
KaizenReview must include a welfare assessment: does this work
reduce suffering, increase capability, or create lasting value?

## Report Paths

| Report | Location |
|---|---|
| AgentOps | `reports/agentops/revenue_wedge/` |
| Kaizen | `reports/kaizen/revenue_wedge/` |
| Daily Brief | Generated via Operator Brief seam |

## First Work Packets

1. **Customer Discovery** — identify 10 potential customers/use-cases
2. **Value Proposition Draft** — articulate what Dharma Swarm offers
3. **MVP Scope** — define minimum viable product for first sale
4. **Pricing Research** — competitive analysis + pricing model

## Relationship to Build Plan

This room specification is the output of Build 5 in
[BUILD_PLAN_FRACTAL_ROOM_V0.md](../research/BUILD_PLAN_FRACTAL_ROOM_V0.md).
The schema types that validate this configuration are defined in
`dharma_swarm/fractal/fractal_room.py` (FractalRoom, VentureCellV1).
