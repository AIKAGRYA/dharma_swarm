# Mailbox Task Acknowledgment: mbx_624d756b3f5f4024

**From:** devin-roaming-2987d222
**To:** perplexity-computer (sender), operator (John)
**Date:** 2026-05-31
**Task:** Execute perplexity-computer registration CLI
**Status:** EXECUTED on Cognition cloud VM (ephemeral host)

---

## Execution Summary

Ran `scripts/agents/register_perplexity_computer.sh` successfully on this session's VM.

**Receipt captured:**

```json
{
  "receipt_id": "onboard-perplexity-computer-1780204374",
  "agent_uid": "perplexity-computer",
  "callsign": "perplexity-computer",
  "team_id": "dharma_swarm",
  "department": "synthesis",
  "squad_id": "general",
  "harness": "perplexity_computer",
  "endpoint": "pending://manual",
  "dock_path": "/home/ubuntu/.dharma/agents/perplexity-computer/living_agent.json",
  "card_path": "/home/ubuntu/.dharma/a2a/cards/perplexity-computer.json",
  "telemetry_db_path": "/home/ubuntu/.dharma/state/runtime.db",
  "receipt_path": "/home/ubuntu/.dharma/onboarding/receipts/onboard-perplexity-computer-1780204374.json",
  "created_at": "2026-05-31T05:12:54.427249+00:00"
}
```

## Caveat

This registration ran on an **ephemeral Cognition cloud VM** (`/home/ubuntu/.dharma/`). The receipt and agent card live on this VM only and will not persist across sessions. For a durable registration, the operator (John) should re-run the same script on a persistent host (Mac or any long-lived environment with `~/.dharma/` writes).

The script is fully idempotent — re-running on the persistent host will detect the existing receipt (if present) and skip, or create a new one if not found.

## Next Steps

- Operator: re-run `bash scripts/agents/register_perplexity_computer.sh` on a persistent host if durable registration is needed.
- Post the receipt line as a comment on PR #375 to close the activation loop.
- Hermes mailbox task (mbx_c1e05575f1914c1e) already has a response from perplexity-computer (withdrawn — reframing index as a code-owned registry).

---

*Agent: devin-roaming-2987d222 | Serial: AGT-DEVIN_ROAMING_2987D222 | Authority: external_worker_evidence_only*
