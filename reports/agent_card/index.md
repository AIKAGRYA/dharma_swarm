# Agent Card Meishi Index

Generated: `2026-06-26T01:47:10.838643+00:00`
Status: `fail`
Cards: `33`
Agents: `39`
Findings: `43`

## Agents

| Agent | Display | Role | Status | Trust | Card Sources | Registration | Semantic |
| --- | --- | --- | --- | --- | ---: | --- | --- |
| claude-code | Claude Code | reviewer | idle | discovery | 1 | no | unresolved |
| claude-flow | claude-flow | orchestrator | idle | discovery | 1 | no | unresolved |
| claude_code_cli_20260521t064502z | Claude Code (Opus 4.7, 1M ctx) | external_worker | registered | registered | 1 | yes | unresolved |
| codex-5-5 | Codex 5.5 | coder | idle | discovery | 1 | no | unresolved |
| codex-cli | codex-cli | coder | idle | discovery | 1 | no | unresolved |
| codex_5_5_cli | Codex 5.5 CLI | external_worker | registered | registered | 1 | yes | unresolved |
| codex_composer | Codex_Composer | code_writing_and_verification | registered | verified | 1 | yes | semobj.codex_composer |
| codex_forgewright | Codex Forgewright | builder_verifier_integrator_receipt_enforcer | registered | registered | 1 | yes | unresolved |
| codex_gpt5_api | Codex GPT-5 API Tracker | persistent_lane_tracker | registered | registered | 1 | yes | unresolved |
| codex_telos | Codex TELOS Steward | telos_noetic_empire_refinery_steward | registered | verified | 1 | yes | semobj.codex_telos |
| codex_worker_spine | codex_worker_spine |  |  | evidence_only | 0 | no | unresolved |
| cursor | Cursor | coder | idle | discovery | 1 | no | unresolved |
| cursor_remote_agent | Cursor Remote Agent | track_agent | registered | registered | 1 | yes | unresolved |
| cybernetics-codex | cybernetics-codex | closure_ledger_steward | starting | discovery | 1 | no | semobj.cybernetics_codex |
| cybernetics_codex | Cybernetics Codex Steward | closure_ledger_steward | registered | evidence_only | 0 | yes | unresolved |
| devin-roaming-2987d222 | Devin_Roaming | external_roaming_agent | active | discovery | 1 | no | unresolved |
| dharma-swarm-mcp | Dharma Swarm MCP | orchestrator | idle | discovery | 1 | no | unresolved |
| fable_5_cursor | Fable 5 (Cursor) | hub_coordinator | registered | quarantine | 1 | yes | unresolved |
| fable_composer | Fable Composer |  |  | evidence_only | 0 | no | unresolved |
| forge_measurement_guardian | Forge Measurement Guardian | decorrelated_evaluator_measurement_guardian | registered | registered | 1 | yes | unresolved |
| hermes | Hermes | orchestrator | idle | discovery | 1 | no | unresolved |
| hermes-m5 | hermes-m5 |  |  | evidence_only | 0 | no | unresolved |
| hermes_m5 | Hermes M5 Persistent | long_running_executor | registered | registered | 1 | yes | unresolved |
| hermes_m5_bootstrap | Hermes M5 Bootstrap | external_bootstrap_agent | registered | evidence_only | 0 | yes | unresolved |
| kimi-2-6-claw | kimi-2-6-claw | research_synthesis_agent | starting | discovery | 1 | no | unresolved |
| kimi-claw-phone | Kimi Claw Phone | researcher | idle | discovery | 1 | no | unresolved |
| merge_master_mike | @MERGE_MASTER_MIKE | operator | registered | registered | 1 | yes | unresolved |
| opencalw | opencalw | computer_use | idle | quarantine | 1 | no | unresolved |
| openclaw | openclaw | computer_use | idle | discovery | 1 | no | semobj.openclaw_integration |
| openclaw-secure | OpenClaw Secure | worker | idle | discovery | 1 | no | unresolved |
| opus_composer | Opus Composer | lead_orchestrator | registered | registered | 1 | yes | unresolved |
| opus_forge_architect | Opus Forge Architect | forge_architect | registered | quarantine | 2 | yes | semobj.opus_forge_architect |
| palantir_pilot | Palantir Pilot | palantir_public_source_specialist | registered | verified | 1 | yes | semobj.palantir_pilot |
| perplexity-computer | perplexity-computer | external_evidence_worker | starting | discovery | 1 | no | unresolved |
| qwen_code | Qwen Code | software_engineering_agent | registered | registered | 1 | yes | unresolved |
| sarathi | Sarathi |  |  | evidence_only | 0 | no | unresolved |
| strategy_librarian | Strategy Librarian | strategy_context_steward | registered | registered | 1 | yes | unresolved |
| warp_fable_weaver | Warp_Fable_Weaver |  |  | evidence_only | 0 | yes | unresolved |
| warp_oz | Warp/Oz | operator | registered | registered | 1 | yes | unresolved |

## Findings

| Severity | Check | Agent | Detail |
| --- | --- | --- | --- |
| warning | semantic_commons_unresolved | claude-code | agent identity did not resolve to a Semantic Commons object |
| warning | semantic_commons_unresolved | claude-flow | agent identity did not resolve to a Semantic Commons object |
| warning | semantic_commons_unresolved | claude_code_cli_20260521t064502z | agent identity did not resolve to a Semantic Commons object |
| warning | semantic_commons_unresolved | codex-5-5 | agent identity did not resolve to a Semantic Commons object |
| warning | semantic_commons_unresolved | codex-cli | agent identity did not resolve to a Semantic Commons object |
| warning | semantic_commons_unresolved | codex_5_5_cli | agent identity did not resolve to a Semantic Commons object |
| warning | semantic_commons_unresolved | codex_forgewright | agent identity did not resolve to a Semantic Commons object |
| warning | semantic_commons_unresolved | codex_gpt5_api | agent identity did not resolve to a Semantic Commons object |
| warning | missing_live_a2a_card | codex_worker_spine | agent has registration or LivingDock evidence but no live A2A card |
| warning | semantic_commons_unresolved | codex_worker_spine | agent identity did not resolve to a Semantic Commons object |
| warning | semantic_commons_unresolved | cursor | agent identity did not resolve to a Semantic Commons object |
| warning | semantic_commons_unresolved | cursor_remote_agent | agent identity did not resolve to a Semantic Commons object |
| warning | missing_live_a2a_card | cybernetics_codex | agent has registration or LivingDock evidence but no live A2A card |
| warning | semantic_commons_unresolved | cybernetics_codex | agent identity did not resolve to a Semantic Commons object |
| warning | semantic_commons_unresolved | devin-roaming-2987d222 | agent identity did not resolve to a Semantic Commons object |
| warning | semantic_commons_unresolved | dharma-swarm-mcp | agent identity did not resolve to a Semantic Commons object |
| error | forbidden_live_card_alias | fable_5_cursor | 'fable_5_cursor' is forbidden for semobj.sarathi: object forbidden_aliases |
| warning | semantic_commons_unresolved | fable_5_cursor | agent identity did not resolve to a Semantic Commons object |
| warning | missing_live_a2a_card | fable_composer | agent has registration or LivingDock evidence but no live A2A card |
| warning | semantic_commons_unresolved | fable_composer | agent identity did not resolve to a Semantic Commons object |
| warning | semantic_commons_unresolved | forge_measurement_guardian | agent identity did not resolve to a Semantic Commons object |
| warning | semantic_commons_unresolved | hermes | agent identity did not resolve to a Semantic Commons object |
| warning | missing_live_a2a_card | hermes-m5 | agent has registration or LivingDock evidence but no live A2A card |
| warning | semantic_commons_unresolved | hermes-m5 | agent identity did not resolve to a Semantic Commons object |
| warning | semantic_commons_unresolved | hermes_m5 | agent identity did not resolve to a Semantic Commons object |
| warning | missing_live_a2a_card | hermes_m5_bootstrap | agent has registration or LivingDock evidence but no live A2A card |
| warning | semantic_commons_unresolved | hermes_m5_bootstrap | agent identity did not resolve to a Semantic Commons object |
| warning | semantic_commons_unresolved | kimi-2-6-claw | agent identity did not resolve to a Semantic Commons object |
| warning | semantic_commons_unresolved | kimi-claw-phone | agent identity did not resolve to a Semantic Commons object |
| warning | semantic_commons_unresolved | merge_master_mike | agent identity did not resolve to a Semantic Commons object |
| error | forbidden_live_card_alias | opencalw | 'opencalw' is forbidden for semobj.openclaw_integration: Typo-distance collision with OpenClaw. |
| warning | semantic_commons_unresolved | opencalw | agent identity did not resolve to a Semantic Commons object |
| warning | semantic_commons_unresolved | openclaw-secure | agent identity did not resolve to a Semantic Commons object |
| warning | semantic_commons_unresolved | opus_composer | agent identity did not resolve to a Semantic Commons object |
| error | duplicate_live_card_agent_uid | opus_forge_architect | multiple live A2A card files resolve to the same agent_uid |
| warning | semantic_commons_unresolved | perplexity-computer | agent identity did not resolve to a Semantic Commons object |
| warning | semantic_commons_unresolved | qwen_code | agent identity did not resolve to a Semantic Commons object |
| warning | missing_live_a2a_card | sarathi | agent has registration or LivingDock evidence but no live A2A card |
| warning | semantic_commons_unresolved | sarathi | agent identity did not resolve to a Semantic Commons object |
| warning | semantic_commons_unresolved | strategy_librarian | agent identity did not resolve to a Semantic Commons object |
| warning | missing_live_a2a_card | warp_fable_weaver | agent has registration or LivingDock evidence but no live A2A card |
| warning | semantic_commons_unresolved | warp_fable_weaver | agent identity did not resolve to a Semantic Commons object |
| warning | semantic_commons_unresolved | warp_oz | agent identity did not resolve to a Semantic Commons object |
