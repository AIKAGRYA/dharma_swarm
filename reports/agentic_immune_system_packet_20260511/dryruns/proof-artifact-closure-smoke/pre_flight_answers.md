# Pilot-00 Pre-Flight Answers

1. What files are hot?
   - None for this pilot.

2. What files are forbidden?
   - `dharma_swarm/orchestrate_live.py`
   - `dharma_swarm/swarm.py`
   - `dharma_swarm/frontier_council.py`
   - `dharma_swarm/agent_runner.py`
   - `dharma_swarm/guardian_crew.py`
   - `dharma_swarm/insight_brief.py`
   - `api/**`
   - `dashboard/**`

3. What is the smallest proof of success?
   - `pytest tests/test_proof_artifact_to_spec.py tests/test_build_protocol_cli.py -q`

4. What can a builder edit?
   - `reports/agentic_immune_system_packet_20260511/proof_artifact_contract.json`, `reports/agentic_immune_system_packet_20260511/closure_run_report.json`, `docs/plans/2026-05-11-global-proof-engine-scratchmap.md`, `reports/agentic_immune_system_packet_20260511/claims_register.md`, `reports/agentic_immune_system_packet_20260511/human_operator_brief.md`, `reports/agentic_immune_system_packet_20260511/organ_wiring_matrix.md`, `reports/agentic_immune_system_packet_20260511/next_build_spec.md`, `reports/agentic_immune_system_packet_20260511/agentic_era_immune_system_dossier.md` only.

5. What happens if tests fail?
   - The WorkPacket stays unapproved and requires one scoped FixupPacket or human rejection. Pilot-00 does not run the fixup.

6. Who reviews before merge?
   - `codex-reviewer`; human merge approval remains with Dhyana.
