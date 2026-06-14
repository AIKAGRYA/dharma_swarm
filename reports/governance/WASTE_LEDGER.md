# Runtime Spine Landing Waste Ledger

Date: 2026-06-14 JST
Goal: `codex-goal:019ec1bc`
Posture: landing, no commit, no score movement

This ledger inventories files visible in the landing diff that belong to this
runtime-spine review surface or are explicitly excluded lanes. The worktree is a
hot shared workspace; this ledger does not claim sole authorship for every path.

## Keep

Runtime core review slice:

```text
dharma_swarm/agent_runner.py
dharma_swarm/orchestrator.py
dharma_swarm/providers.py
dharma_swarm/runtime_lifecycle.py
dharma_swarm/runtime_provider.py
dharma_swarm/runtime_state.py
dharma_swarm/swarm_health_api.py
dharma_swarm/thinkodynamic_director.py
dharma_swarm/spine/manual_runner.py
scripts/live_claude_code.py
scripts/live_fanout.py
scripts/live_genome_test.py
scripts/live_test.py
scripts/runtime/autonomy_spine.py
tests/test_agent_runner.py
tests/test_agent_runner_routing_feedback.py
tests/test_authority_revenue_loop.py
tests/test_autonomy_spine_cli.py
tests/test_full_loop.py
tests/test_orchestrator.py
tests/test_orchestrator_spine_dispatch.py
tests/test_provider_policy.py
tests/test_runtime_lifecycle.py
tests/test_runtime_provider.py
tests/test_runtime_state_invariants.py
tests/test_spine_adoption_dispatch.py
tests/test_swarm_health_api.py
tests/test_thinkodynamic_director.py
tests/test_manual_spine_runner.py
```

Receipt, provenance, idempotency review slice:

```text
scripts/governance/runtime_receipt_coverage_report.py
scripts/runtime/ds_goal_longrun_preflight.py
scripts/runtime/ds_goal_wrapper_receipt_probe.py
scripts/runtime/runtime_lifecycle_receipt_probe.py
dharma_swarm/operator_core/ds_goal_wrapper_contract.py
tests/test_ds_goal_longrun_preflight.py
tests/test_ds_goal_longrun_preflight_report.py
tests/test_ds_goal_wrapper_receipt_probe.py
tests/test_runtime_lifecycle_receipt_probe.py
tests/test_runtime_receipt_coverage_report.py
```

Live ops and control-surface review slice:

```text
dharma_swarm/operator_core/control_surface_live_ops.py
dharma_swarm/operator_core/live_ops_census_contract.py
scripts/runtime/live_ops_census.py
scripts/governance/agent_onboard.py
scripts/governance/orientation_graph.py
scripts/status_composer_background_loop_tmux.sh
scripts/status_composer_console_tmux.sh
scripts/status_terminal_tui_tmux.sh
dashboard/README.md
dashboard/src/components/cockpit/SystemTruthMatrix.tsx
dashboard/src/lib/controlSurfaceRuntimeEvidence.ts
dashboard/src/lib/controlSurfaceRuntimeEvidence.test.ts
docs/architecture/CONTROL_SURFACE.md
docs/ops/LIVE_OPS_COCKPIT.md
tests/test_agent_onboard.py
tests/test_live_ops_census.py
tests/test_orientation_graph.py
tests/test_tmux_status_surface_honesty.py
```

A2A lifecycle truth review slice:

```text
dharma_swarm/a2a/a2a_bridge.py
dharma_swarm/a2a/a2a_client.py
dharma_swarm/a2a/nats_transport.py
dharma_swarm/a2a/node_gateway.py
reports/a2a/send_receipts/20260614T035438Z-codex_composer-dd41828408dd.json
tests/test_a2a_spec_conformance.py
tests/test_nats_transport.py
```

Governance and rendered evidence review slice:

```text
ACTIVE_SURFACE_MANIFEST.yaml
CLAUDE.md
Makefile
PRODUCT_SURFACE.md
com.dharma.swarm.plist
docs/agent_tasks/2026-06-14_runtime_spine_hardening_goal.md
docs/governance/ACTIVE_TRACK.yaml
docs/governance/ANTI_SLOP_RULES.md
docs/governance/BUILD_SESSION_ENTRYPOINT.md
docs/governance/SOVEREIGN_MANIFEST.md
docs/governance/active_track.schema.cue
docs/governance/hygiene/baselines/2026-06-14.txt
reports/agentops/workhorse_prompts/runtime-spine-production-audit-mega-prompt-20260614.md
reports/governance/active_track_evidence.json
reports/governance/active_track_evidence.md
reports/governance/runtime_spine_dispatch_mode_progress_2026-06-14.md
reports/governance/runtime_spine_hardening_progress_2026-06-14.md
reports/governance/runtime_spine_receipt_coverage_progress_2026-06-14.md
reports/governance/track_portfolio.json
scripts/governance/check_test_hygiene.py
scripts/governance/check_track_status.py
scripts/governance/ds_goal_longrun_preflight_report.py
scripts/governance/render_active_track_includes.py
scripts/governance/spine_bypass_report.py
scripts/governance/spine_dispatch_mode_report.py
tests/conftest.py
tests/test_track_portfolio.py
```

## Keep But Split Before Merge

These files are too broad or too complex to review as one undifferentiated
change:

```text
scripts/runtime/live_ops_census.py
tests/test_live_ops_census.py
scripts/governance/runtime_receipt_coverage_report.py
tests/test_runtime_receipt_coverage_report.py
dharma_swarm/operator_core/control_surface_live_ops.py
scripts/governance/spine_dispatch_mode_report.py
scripts/governance/agent_onboard.py
scripts/governance/orientation_graph.py
```

Recommended seams:

- store/read model: DB queries, receipt parsing, and copied-state gates;
- probes: process/port/tmux/NATS/http observation only;
- projections: live-ops rows, dashboard labels, onboard/orient lines;
- governance gates: score-cap and strict receipt gate logic;
- tests: split fixtures/builders from assertion-heavy scenario tests.

## Composted

No repo files composted.

## Scratch Kept Outside Repo

```text
/private/tmp/runtime-spine-landing-20260614/
/Users/dhyana/Desktop/runtime_spine_longrun_handoff_for_llms_2026-06-14_v13_headless_9h_sprint_checks_and_balances.md
```

## Excluded Separate Lanes

Do not judge, segment, or fix these as runtime-spine landing work:

```text
dharma_swarm/palantir_pilot.py
docs/agent_tasks/2026-06-14_palantir_pilot_longrun_goal.md
docs/agents/palantir_pilot/
scripts/governance/palantir_pilot_audit.py
scripts/governance/register_palantir_pilot.py
tests/test_palantir_pilot.py

dharma_swarm/cybernetics_codex.py
docs/agents/cybernetics_codex/
docs/ops/CYBERNETICS_CODEX.md
scripts/governance/cybernetics_codex_audit.py
scripts/governance/register_cybernetics_codex.py
tests/test_cybernetics_codex.py
```

