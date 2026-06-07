# cashclaw-employee-runtime-parity-v0

Telos: Add the first CashClaw Employee Runtime parity slice: an Employee contract wrapper for existing registered agents plus a pure action gateway with single-use approval tokens for external effects.

Allowed paths:
- dharma_swarm/employees/runtime.py
- dharma_swarm/employees/__init__.py
- dharma_swarm/revenue/action_gateway_models.py
- dharma_swarm/revenue/action_gateway.py
- dharma_swarm/revenue/__init__.py
- tests/test_employee_runtime.py
- tests/test_cashclaw_action_gateway.py
- spec-forge/cashclaw-employee-runtime/MASTER_SPEC.md

Forbidden paths:
- dharma_swarm/orchestrate_live.py
- dharma_swarm/swarm.py
- dharma_swarm/frontier_council.py
- dharma_swarm/agent_runner.py
- dharma_swarm/guardian_crew.py
- dharma_swarm/insight_brief.py
- api/**
- dashboard/**
- cron_jobs.json
- dharma_swarm/persistent_fleet_manifest.json

Proof command: pytest -q tests/test_employee_runtime.py tests/test_cashclaw_action_gateway.py

Reviewer: codex-parent

## Notes

This is a spec-forge-style dry-run build spec for the existing Pilot-00 build protocol. It is not an approval to send outreach, accept paid work, perform marketplace actions, spend money, create OAuth grants, or start new daemon processes.
