# Agent Task — Register perplexity-computer as Roaming Agent

Date: 2026-05-29
Requester: John Shrader (operator) + perplexity-computer (self-dispatch)
Repo: AmitabhainArunachala/dharma_swarm
Priority: P1
Recipient: any roaming agent with Mac-shell access, OR the operator directly

## Mission

Materialize the runtime presence of `perplexity-computer` by running the
roaming-onboarding CLI on a host that writes to `~/.dharma/` on John's
Mac.

PR #375 lands the filesystem identity (the nest). This task lands the
**runtime identity** (the kaizenops receipt + agent card + external-agent
surface).

## What to run

```bash
cd <dharma_swarm repo root>
bash scripts/agents/register_perplexity_computer.sh
```

The script is **idempotent** — it greps the receipt file for the
callsign and exits 0 if already registered. Safe to re-run.

## What gets stamped

| Artifact | Purpose |
|---|---|
| `~/.dharma/onboarding/receipts/receipts.jsonl` | kaizenops witness trail (the witness John named explicitly) |
| `~/.dharma/external_agents/perplexity-computer/` | external-agent runtime surface |
| `~/.dharma/a2a/cards/perplexity-computer.json` | A2A agent card for discovery |
| `~/.dharma/agents/perplexity-computer/living_agent.json` | living-agent runtime record |

## Bound parameters

- callsign: `perplexity-computer`
- harness: `perplexity_computer`
- authority: `external_worker_evidence_only` (Stage 1)
- department: `synthesis`

These match `docs/agents/perplexity-computer/SOUL.md` exactly. Do not
change without amending the nest.

## Who should run this

In priority order:

1. **devin-roaming-2987d222** — has the deterministic-wake Cognition VM
   pattern; this is a one-shot infra task matching the precedent that
   landed Devin's own nest (PR #330). Mailbox task
   `mbx_624d756b3f5f4024` is addressed to Devin for this.
2. **John, directly** — open Terminal on the Mac, `cd` into the repo,
   run the script. Takes ~30 seconds.
3. **Any codex / claude-code / openclaw session with repo + venv access**
   — same one-liner, idempotent.

## Verification

After the script runs, the operator (or the executing agent) can
confirm with:

```bash
grep "perplexity-computer" ~/.dharma/onboarding/receipts/receipts.jsonl | tail -1
```

The expected line is a JSON object containing the callsign, the
authority, the department, and a UTC timestamp. Paste it as a comment
on PR #375 to close the loop.

## What this does not do

- It does **not** merge PR #375. Identity papers stay on the PR until
  review.
- It does **not** grant authority above Stage 1. The receipt records
  the declared authority; the swarm enforces it.
- It does **not** create new governance surfaces. The mailbox task,
  the receipt file, and the existing `~/.dharma/` tree are all the
  surfaces involved.
- It does **not** wake a long-running agent. The receipt is a stamp,
  not a daemon.

## After registration

`perplexity-computer` becomes available for first work-under-authority.
Mailbox task `mbx_c1e05575f1914c1e` to Hermes proposes
perplexity-computer contribute to the persistent-agent-index task as
evidence-only synthesis, with Hermes retaining ownership of the index.

Alternative first work: GUARDIAN duplicate dedup (#311–#353).

## References

- [PR #375](https://github.com/AmitabhainArunachala/dharma_swarm/pull/375)
- `docs/agents/perplexity-computer/SOUL.md`
- `docs/agents/perplexity-computer/CAPABILITIES.md`
- `dharma_swarm/external_agent_registration.py` (registration API)
- `dharma_swarm/roaming_onboarding.py` (CLI entry point)
- `scripts/agents/register_perplexity_computer.sh` (idempotent helper)
- `roaming_mailbox/tasks/mbx_624d756b3f5f4024.json` (mailbox dispatch to Devin)
- `roaming_mailbox/tasks/mbx_c1e05575f1914c1e.json` (mailbox coordination to Hermes)
