# Pilot-00 Dispatch Plan

Source spec path: `reports/agentic_immune_system_packet_20260511/dryruns/proof-artifact-closure-smoke/source_spec_copy.md`

## Telos

Run Agentic Era Immune System as a whole-organism tracer through lodestones, telos, ThinkodynamicDirector, Shakti, Viveka, MemoryKernel, Kalyan, Agora/SABP, and guarded Evolution without collapsing the organism into one report.

## Allowed Paths

- `reports/agentic_immune_system_packet_20260511/proof_artifact_contract.json`
- `reports/agentic_immune_system_packet_20260511/closure_run_report.json`
- `docs/plans/2026-05-11-global-proof-engine-scratchmap.md`
- `reports/agentic_immune_system_packet_20260511/claims_register.md`
- `reports/agentic_immune_system_packet_20260511/human_operator_brief.md`
- `reports/agentic_immune_system_packet_20260511/organ_wiring_matrix.md`
- `reports/agentic_immune_system_packet_20260511/next_build_spec.md`
- `reports/agentic_immune_system_packet_20260511/agentic_era_immune_system_dossier.md`

## Forbidden Paths

- `dharma_swarm/orchestrate_live.py`
- `dharma_swarm/swarm.py`
- `dharma_swarm/frontier_council.py`
- `dharma_swarm/agent_runner.py`
- `dharma_swarm/guardian_crew.py`
- `dharma_swarm/insight_brief.py`
- `api/**`
- `dashboard/**`

## Hot-File Status

No hot files are in scope.

## Proposed WorkPackets

### wp_001

- Builder: unassigned
- Reviewer: codex-reviewer
- Scope: `reports/agentic_immune_system_packet_20260511/proof_artifact_contract.json`, `reports/agentic_immune_system_packet_20260511/closure_run_report.json`, `docs/plans/2026-05-11-global-proof-engine-scratchmap.md`, `reports/agentic_immune_system_packet_20260511/claims_register.md`, `reports/agentic_immune_system_packet_20260511/human_operator_brief.md`, `reports/agentic_immune_system_packet_20260511/organ_wiring_matrix.md`, `reports/agentic_immune_system_packet_20260511/next_build_spec.md`, `reports/agentic_immune_system_packet_20260511/agentic_era_immune_system_dossier.md`
- Intended change: Run Agentic Era Immune System as a whole-organism tracer through lodestones, telos, ThinkodynamicDirector, Shakti, Viveka, MemoryKernel, Kalyan, Agora/SABP, and guarded Evolution without collapsing the organism into one report.
- Max diff: 50 lines
- Constraints: no_merge, no_push, no_shell_exec, scope_locked

## Gates Required

- `telos`
- `scoped_tests`
- `scope_check`

## Proof Command

```bash
pytest tests/test_proof_artifact_to_spec.py tests/test_build_protocol_cli.py -q
```

## Why This Plan Is Safe

- It targets 8 bounded editable path(s).
- It has a deterministic proof command.
- It does not touch Operator Brief, Daily Insight, ontology, memory consolidation, dashboard, API, providers, routing, AgentRunner, Guardian, or runtime orchestration.
- Pilot-00 creates no worktree, spawns no agent, writes no SQLite state, and edits no source.

## Reasons This Plan Would Be Rejected

- Any editable scope outside the allowed path list.
- Any missing or non-deterministic proof command.
- Any attempt to touch forbidden domains or hot files.
- Any pre-flight answer that is unknown, broad, or unbounded.
- Any generated artifact outside `reports/agentic_immune_system_packet_20260511/dryruns/proof-artifact-closure-smoke`.
