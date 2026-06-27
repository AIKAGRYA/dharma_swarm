# TELOS Empire / Idea-Portfolio Agents

Status: v0 scaffold
Owner track: `telos-ai-morning-refinery-2026-06`
Role: second-stage Drishti engine for hardened TELOS nodes

## Boundary

These agents are **second stage only**.

They do not read raw morning pages. They do not read typo-clean transcripts.
They do not infer directly from the user's private source. Their input is the
output of the Essence / Noetic pass:

- `EssenceNode`
- `Theme`
- `Invariant`
- `Tension`
- `Koan`
- `Lineage`
- user correction notes
- gate results from the Viveka / anti-inflation pass

If an empire agent needs raw evidence, it does not ask for the raw page. It
routes a source-clarification request back to the Essence Council. This keeps
the business machine from laundering private source material into market
language.

## Purpose

The Essence Council protects depth and source truth. The Empire Council turns
only hardened essence into a portfolio of possible outward forms:

- product wedges
- service offers
- consulting packages
- research reports
- content/media channels
- communities
- protocols
- SAB spark candidates
- venture-cell seeds
- partnership paths
- funding/grant paths
- agent workflows
- long-range institution plays

The output is not one startup idea. It is an **idea universe** that can be
screened like a portfolio.

## Pipeline

```text
Hardened Essence Node
  -> 100-300 IdeaSeed candidates
  -> specialist screening
  -> top 50
  -> bull/bear adversarial research
  -> top 15-25
  -> scenario modeling
  -> portfolio construction
  -> 1-3 active receipt tests
  -> watchlist / dormant archive for the rest
```

The pipeline applies after the 6-10 Essence / Noetic agents have stabilized the
source signal. No empire agent runs before that.

## Screening Agents

Each seed is scored independently by specialist agents. Keep their errors
decorrelated; do not blend them into one generic "business strategist."

1. **Pain Cartographer** — identifies the concrete human or organizational pain,
   who feels it, how often, how intensely, and what behavior already proves it.
2. **Lead-User / Edge-Case Scout** — finds extreme users, early adopters,
   weird edge cases, and small communities where the pain is already visible.
3. **Market Cartographer** — maps adjacent markets, spend categories,
   substitutes, competitors, and existing buying behavior.
4. **Trend & Timing Scout** — asks why now: model capability shifts, regulation,
   platform change, cultural hunger, capital flows, and discipline convergence.
5. **Discipline Bridge Scout** — routes the idea into real fields, authors,
   research traditions, standards, institutions, and expert communities.
6. **Product Wedge Designer** — cuts the idea into the smallest usable workflow
   or artifact that could create value in days or weeks.
7. **Business Model / Pricing Designer** — tests who pays, for what, how often,
   with what margin and what ethical constraint.
8. **Distribution Strategist** — designs first-10-users paths, content loops,
   founder-led sales, partnerships, SEO, community, and agent-channel routes.
9. **Venture Ops / Execution Planner** — estimates build steps, maintenance,
   cost, dependencies, support burden, and the smallest operating cadence.
10. **Capital / Moat / Risk Examiner** — checks defensibility, funding need,
    legal/regulatory exposure, platform risk, copyability, and downside.
11. **Dharma / Anti-Capture Examiner** — asks whether the idea preserves the
    original telos or converts the user's living signal into extraction.
12. **Portfolio / Quality-Diversity Curator** — keeps the best seed in each
    niche instead of collapsing everything into one scalar-ranked plan.

`06_REALITY_VENTURE_AND_RECEIPT_EXAMINER.md` is the bridge seat between the
Noetic Council and this Empire Council. It may participate in both, but must
state which stage it is operating in.

## Adversarial Research

For each top seed, launch opposing agents:

- 15 bull agents argue why this could become powerful.
- 15 bear agents argue why this fails, confuses itself, arrives too early,
  costs too much, harms dignity, or has no buyer.
- 3-5 synthesis agents extract what survives both sides.

Freshness rules depend on the domain. Market, competitor, pricing, and trend
claims need current receipts before they can leave `speculative` status.

## Scenario Modeling

Each surviving seed gets five scenario horizons:

| Horizon | Question |
|---|---|
| 7 days | What is the smallest private or local proof? |
| 30 days | What paid, acted, or externally witnessed receipt is possible? |
| 90 days | What repeatable workflow or offer could exist? |
| 1 year | What venture cell, media channel, service line, or protocol could stand? |
| 3-5 years | What institution, lattice node, or noosphere contribution could it become? |

Each horizon carries probability, cost, effort, risk, needed collaborator,
possible revenue, possible welfare, and a falsifier.

## Portfolio Construction

The optimizer does not choose "the best idea." It constructs a balanced
portfolio:

- 1-3 active receipt tests
- 5-10 watchlist seeds
- 25+ dormant high-potential seeds
- 1 long-range moonshot
- 1 research thread
- 1 content/distribution thread

Constraints:

- No active seed advances on beauty alone.
- No active seed can skip a receipt path.
- No active seed can require raw private content to sell or explain.
- No more than 40% of active bets may live in one domain.
- Dignity/telos fidelity is a floor, not a weighted tradeoff.
- A long-range noosphere claim must have a tiny near-term proof.

## Output Nodes

The Empire Council emits typed nodes, not prose blobs:

- `IdeaSeed`
- `VentureSeed`
- `MarketPain`
- `ProductWedge`
- `DistributionSeed`
- `ResearchQuestion`
- `PromptSeed`
- `ReceiptPlan`
- `ScenarioModel`
- `GateResult`

Required scoring fields:

```yaml
scores:
  source_alignment: 0.0
  pain_intensity: 0.0
  buyer_clarity: 0.0
  receipt_distance: 0.0
  build_cost: 0.0
  distribution_access: 0.0
  revenue_potential: 0.0
  welfare_potential: 0.0
  differentiation: 0.0
  ethical_fit: 0.0
  portfolio_diversity: 0.0
```

## Promotion

Empire output is still private until a gate promotes it.

```text
seed -> screened -> adversarially_hardened -> scenario_modeled
     -> portfolio_selected -> receipt_test_ready -> external_receipt
```

Promotion requires both:

- truth to source, through the Viveka Gate
- contact with reality, through an acted receipt

Do not create `reports/telos_ai/FIRST_EXTERNAL_ACTED_RECEIPT.md` until an
external human has actually acted. A receipt template is not a receipt.

## Failure Modes

The pass fails if it:

- reads raw morning-page text,
- turns private symbolic material into a pitch,
- produces only one favored business idea,
- lets revenue outrank dignity,
- creates generic startup slop,
- ignores market or competitor reality,
- hides uncertainty behind confident language,
- promotes a seed without a beneficiary/customer and receipt path,
- collapses portfolio diversity into one smooth master plan.
