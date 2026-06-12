# qwen_code A2A Production Readiness Review Attempt

- attempted_at: `2026-06-12T19:10:12Z`
- command_surface: `qwen --prompt`
- model_family_hint: `alibaba`
- production_claim: `false`
- reviewer_record_written: `true`
- target_record_path: `reports/a2a/prod_readiness_quorum/2026-06-13/qwen_code.json`

Raw output:

```json
{
  "schema_version": "dharma.a2a.prod_readiness_reviewer.v1",
  "agent_id": "qwen_code",
  "model_family": "alibaba",
  "role": "adversarial_security_reviewer",
  "readiness_percent": 42,
  "verdict": "not_ready",
  "red_blockers": [
    "Fable/Hermes target-owned handler receipts missing: fable_composer and hermes_m5 reviewer records do not exist; both solicitation messages sit PENDING_DELIVERY in AGNI with no handler ack, domain receipt, or semantic reply from the target agents",
    "Quorum composition fails: only 1 persistent agent ID (codex_composer) of 2 required; only 1 model family (openai) of 3 required; no adversarial/security reviewer record exists",
    "Sole existing reviewer (codex_composer) returned NOT_READY verdict with 5 red blockers — quorum requires zero red blockers across all reviewers",
    "Publish ack is present for quorum solicitation messages but no target-owned agent has consumed them — PUBLISH_ACCEPTED cannot satisfy handler ack, domain receipt, or production readiness, and the delivery-status receipt confirms both Fable and Hermes remain PENDING_DELIVERY",
    "Hermes alert-router broadcast source (~/.hermes/scripts/alert_router.py → a2a_bus.py broadcast) lives outside the repo and can silently repopulate file inboxes even after quarantine passes — this is an ungoverned mutation surface that undermines file-inbox hygiene claims"
  ],
  "evidence_refs": [
    "docs/governance/ACTIVE_TRACK.yaml",
    "docs/governance/active_tracks/a2a-runtime-spine-2026-06/README.md",
    "docs/governance/active_tracks/a2a-runtime-spine-2026-06/PRODUCTION_READINESS_QUORUM.md",
    "reports/a2a/nats_reset/2026-06-13/NATS_COMMON_FAILURES.md",
    "reports/a2a/nats_reset/2026-06-13/A2A_LIVE_HANDLER_REPAIR_PLAN.json",
    "reports/a2a/prod_readiness_quorum/2026-06-13/QUORUM_DELIVERY_STATUS.json",
    "reports/a2a/prod_readiness_quorum/latest.json"
  ],
  "created_at": "2026-06-13T15:00:00Z"
}
```
