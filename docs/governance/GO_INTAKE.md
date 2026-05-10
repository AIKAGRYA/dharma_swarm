# GO Intake

GO is the economic-intelligence intake organ for dharma_swarm.

GO is a **bounded context**. Its capability boundary is **ingestion only**.
It may create case cards and candidate opportunity rows, but those rows are
proposals for other organs to evaluate. GO does not route, execute, spend, send,
trade, launch, or rent.

Its bounded-context membrane is:

```text
external primitive -> case card -> dharma mapping -> scored opportunity -> Shakti/opportunity loop
```

It does **not** move funds, launch tokens, trade, send outreach, or rent compute.
Those remain human-approved actions until separate legal, security, and treasury
gates exist.

Every GO case card and GO-derived opportunity row carries:

```json
{
  "bounded_context": "go_intake",
  "capability_boundary": "ingestion_only",
  "mouth": "manual_note",
  "allowed_next_step": "proposal_only",
  "requires_operator_approval": true,
  "forbidden_actions": [
    "fund_movement",
    "trade_execution",
    "token_launch",
    "outbound_outreach",
    "compute_rental",
    "task_dispatch"
  ]
}
```

Future agents should treat those fields as a hard semantic boundary, not a
description of current implementation convenience.

## Mouths

GO can have multiple mouths. A mouth is an ingestion adapter, not a new
capability. All mouths remain inside the same encapsulated ingestion-only organ.

Current allowed mouths:

- `manual_note` - pasted or file-based operator notes
- `repo_doc` - in-repo docs
- `web_research` - sourced external web notes
- `agent_report` - another model's report
- `market_snapshot` - market / pricing / funding snapshot
- `provider_probe` - provider / compute availability observations
- `field_knowledge_base` - curated ecosystem intelligence already in repo
- `inquiry_seed` - docs/inquiry seeds and cross-model chews
- `telic_feedback` - realized Outcome / ValueEvent / Contribution feedback
- `customer_signal` - inbound buyer, user, partner, or design-partner signal
- `grant_call` - grant, RFP, challenge, fellowship, or foundation opportunity
- `bounty_market` - paid issue, marketplace, audit bounty, or scoped service demand
- `competitor_release` - competitor launch, funding, pricing, or benchmark update
- `risk_incident` - scam, exploit, enforcement action, failure postmortem, or regulatory signal
- `social_attention` - attention signal observed only as evidence, never as action authority
- `compute_ledger` - actual spend, savings, provider health, or GPU pricing observation

Forbidden as GO mouths:

- wallet execution
- token launch
- trade execution
- outbound outreach
- compute rental
- PR routing or task dispatch

Those are different organs and must remain outside GO.

## What It Ingests

Examples:

- Bittensor-style incentive markets
- Virtuals-style agent identity / wallet / treasury patterns
- x402-style agent payment rails
- Akash / RunPod / GPU compute markets
- DAO treasury governance
- vertical agent revenue examples
- paid research / model-welfare evaluation outreach
- self-evolution research such as DGM

## Runtime

Use the CLI:

```bash
python scripts/go_intake.py path/to/examples.md
```

Dry-run is the default. To persist case cards:

```bash
python scripts/go_intake.py path/to/examples.md --write
```

To mark the source mouth:

```bash
python scripts/go_intake.py path/to/examples.md --mouth agent_report
```

To also upsert safe, high-scoring experiments into `~/.dharma/meta/opportunity_board.json`:

```bash
python scripts/go_intake.py path/to/examples.md --write --emit-opportunities
```

High-risk cases such as memecoins, trading, token launches, and real-fund wallet autonomy are recorded as case cards but excluded from opportunity-board emission by default.

## Calibration Rule

GO cards are not decisions. They are candidate economic primitives. A card becomes work only when:

1. It is scored by `dharma_swarm/go_intake.py`.
2. It survives high-risk filtering.
3. It is upserted into the opportunity board.
4. `opportunity_refill` derives staged frontier tasks.
5. The dispatcher routes those tasks through gates and TelicSeam records.

This keeps the swarm hungry for income and compute without letting hunger bypass governance.
