# receipts/ — sis_steward

Runtime receipts (wake receipts, onboarding receipts, verification footprint records,
A2A acks) are written under **`~/.dharma/agents/sis_steward/`** and are **not committed
to git** (repo doctrine: runtime receipts never enter git; prefer `~/.dharma/`).

This directory is the git-tracked **contract + pointer index** only.

## Where the live receipts are

| Receipt | Path (non-git) |
|---|---|
| Living-agent presence | `~/.dharma/agents/sis_steward/living_agent.json` |
| Last wake / onboarding receipt | `~/.dharma/agents/sis_steward/last_receipt.json` |
| Append-only trajectory log | `~/.dharma/agents/sis_steward/trajectory.jsonl` |
| Registration of record | `~/.dharma/external_agents/sis_steward/registration.json` |
| A2A card | `~/.dharma/a2a/cards/sis-steward.json` |
| Verification footprint records *(prospective, SEED-1)* | `~/.dharma/agents/sis_steward/footprint/*.json` |

## The receipt rule

Every "done" is backed by a verifier (see `PROTOCOLS.md §Verifiers`), not by assertion.
Every verification I eventually produce carries its own estimated energy/carbon
footprint. No internal artifact mints value; only an externally-countersigned receipt
above quorum does (One Wire).
