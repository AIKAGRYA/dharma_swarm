# Sample Registration Artifacts

These are the **real** artifacts emitted by
`scripts/agents/register_perplexity_computer.sh` when executed in an
isolated sandbox `DHARMA_HOME` on 2026-05-30. Sandbox paths are
inlined so reviewers can see exact shape; production paths will be
`~/.dharma/...` on whatever host actually runs the script.

| File | Source path in sandbox | Production path |
|---|---|---|
| `sample_receipt.json` | `/tmp/dharma_test/.dharma/onboarding/receipts/onboard-perplexity-computer-1780107060.json` | `~/.dharma/onboarding/receipts/onboard-perplexity-computer-<unix-ts>.json` |
| `sample_agent_card.json` | `/tmp/dharma_test/.dharma/a2a/cards/perplexity-computer.json` | `~/.dharma/a2a/cards/perplexity-computer.json` |

The registration also writes:

- `~/.dharma/onboarding/receipts.jsonl` (append-only index)
- `~/.dharma/agents/perplexity-computer/living_agent.json`
- `~/.dharma/agents/perplexity-computer/embodiments.jsonl`
- `~/.dharma/agents/perplexity-computer/last_receipt.json`
- `~/.dharma/state/runtime.db` (telemetry plane row + team roster row)

Purpose: lets reviewers verify that the registration produces a
well-formed agent card + receipt before merging the dispatch PR,
without needing a live Mac session. End-to-end execution of the
helper script in a sandbox was successful and idempotent on re-run.
