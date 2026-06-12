{
  "schema_version": "dharma.a2a.prod_readiness_reviewer.v1",
  "agent_id": "gemini_reviewer",
  "model_family": "google",
  "role": "independent_production_reviewer",
  "readiness_percent": 62,
  "verdict": "not_ready",
  "red_blockers": [
    "Target-owned Fable and Hermes reviewer records are missing; consumers exist but are empty.",
    "Quorum currently has only two model families (openai, alibaba) instead of the required three.",
    "Quorum median readiness is 62%, which is below the 80% threshold.",
    "Other reviewers (codex_composer, qwen_code) have reported red blockers."
  ],
  "evidence_refs": [
    "docs/governance/ACTIVE_TRACK.yaml",
    "docs/governance/active_tracks/a2a-runtime-spine-2026-06/README.md",
    "docs/governance/active_tracks/a2a-runtime-spine-2026-06/PRODUCTION_READINESS_QUORUM.md",
    "reports/a2a/nats_reset/2026-06-13/A2A_LIVE_HANDLER_REPAIR_PLAN.json",
    "reports/a2a/nats_reset/2026-06-13/FILE_BUS_GUARD_AFTER_HERMES_DISABLE.json",
    "reports/a2a/hermes_broadcast_guard/2026-06-13/HERMES_ALERT_ROUTER_BROADCAST_GUARD_APPLIED.json",
    "reports/a2a/prod_readiness_quorum/latest.json",
    "reports/a2a/prod_readiness_quorum/latest_delivery_status.json"
  ],
  "created_at": "2026-06-13T12:00:00Z"
}
