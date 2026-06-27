# A2A Live Repair Receipt

Generated: 2026-06-26T00:16:30Z.
Updated: 2026-06-26T00:30:00Z after A2A claim-boundary and file-mode hardening.

Scope: live Dharma Swarm A2A transport and typed domain-reply evidence for the
standalone Holon Phase 1 audit packet.

## Boundary

This receipt proves live broker delivery, handler ACK, local model-backed
SemanticReceipt generation, target-owned reply artifact validation, and typed
domain receipt publish for three agent identities. Final artifacts and receipts
explicitly mark `semantic_audit_depth=packet_only`, `source_audit_claim=false`,
and `authenticated_target_runtime_claim=false`.

It does not prove a long-running autonomous peer daemon independently inspected
the full source tree. The audit packet carried path references and the Phase 1
receipt, not a full source snapshot. Treat this as A2A semantic receipt repair,
not a final Hermes-grade independent audit.

An attempted `glm-5:cloud` Fable drain was rejected before execution because it
would send private repo context to an external Ollama cloud route. The accepted
semantic drains below used local `mistral:latest`.

## Bridge Sessions

The following tmux bridge sessions were started for live inbox handling:

- `dharma_a2a_inbox_bridge_codex_composer`
- `dharma_a2a_inbox_bridge_hermes_m5`
- `dharma_a2a_inbox_bridge_fable_composer`

## Evidence Matrix

| Agent | Packet | Send receipt | Inbox bridge receipt | Semantic drain | Semantic receipt | Domain publish receipt |
|---|---|---|---|---|---|---|
| `codex_composer` | `2bbba006f775` | `reports/a2a/send_receipts/20260626T000839Z-codex_composer-2bbba006f775.json` | `reports/a2a/inbox_bridge_receipts/20260626T000819Z-codex_composer-2bbba006f775.json` | `reports/a2a/semantic_inbox_drains/20260626T002855Z-codex_composer-2bbba006f775.json` | `reports/agentops/semantic_receipts/20260626T002855Z-ollama-mistral_latest-c432a6f8e570.json` | `reports/a2a/domain_reply_receipts/20260626T002940Z-codex_composer-2bbba006f775.json` |
| `hermes-m5` | `cf4716e01dc7` | `reports/a2a/send_receipts/20260626T000840Z-hermes-m5-cf4716e01dc7.json` | `reports/a2a/inbox_bridge_receipts/20260626T000820Z-hermes-m5-cf4716e01dc7.json` | `reports/a2a/semantic_inbox_drains/20260626T002913Z-hermes-m5-cf4716e01dc7.json` | `reports/agentops/semantic_receipts/20260626T002913Z-ollama-mistral_latest-cf4716e01dc7_hermes-m5_critique.json` | `reports/a2a/domain_reply_receipts/20260626T002942Z-hermes-m5-cf4716e01dc7.json` |
| `fable_composer` | `5aa607b21b57` | `reports/a2a/send_receipts/20260626T000840Z-fable_composer-5aa607b21b57.json` | `reports/a2a/inbox_bridge_receipts/20260626T000820Z-fable_composer-5aa607b21b57.json` | `reports/a2a/semantic_inbox_drains/20260626T002925Z-fable_composer-5aa607b21b57.json` | `reports/agentops/semantic_receipts/20260626T002925Z-ollama-mistral_latest-r-5aa607b21b57.json` | `reports/a2a/domain_reply_receipts/20260626T002943Z-fable_composer-5aa607b21b57.json` |

## Status Claims

- Live transport: `HANDLER_ACKED` for all three packets.
- Semantic drain: `SEMANTIC_INBOX_DRAINED` for all three final drains.
- Semantic model route: local `ollama:mistral:latest`.
- Domain publish: `DOMAIN_REPLY_PUBLISHED` with `DOMAIN_RECEIPTED` for all three packets.
- Semantic claim boundary: `semantic_reply_claim=true` means a validated
  SemanticReceipt exists for the delivered packet. It does not mean the agent
  daemon completed an exhaustive source audit.
- Source audit boundary: all final domain receipts carry
  `semantic_audit_depth=packet_only`, `source_audit_claim=false`, and
  `authenticated_target_runtime_claim=false`.
- File privacy: sampled final prompt, SemanticReceipt, target outbox artifacts,
  and domain publish receipt paths are mode `0600`.
