# L4 Persistent-Agent Readiness Report

Generated: 2026-05-21T06:14:12.207309Z

Exact L4 count: **0**
Rows: **49**

This report is generated from live local state by `scripts/runtime/persistent_agent_census.py`.
It does not wake agents, mutate runtime state, or expose secret values.
L4 evidence booleans require one live TaskClaim/DelegationRun/session chain; unrelated historical rows do not aggregate into promotion.

TaskClaim / ExecutionLease boundary: see `13_ontology_bridge.md`.

## Counts

| Group | Count |
|---|---:|
| L0 | 1 |
| L1 | 18 |
| L2 | 23 |
| L3 | 7 |
| L4 | 0 |
| L5 | 0 |
| L6 | 0 |

| Candidate kind | Count |
|---|---:|
| daemon | 2 |
| framework | 1 |
| persistent_agent_candidate | 2 |
| registered_worker | 36 |
| script | 8 |

## Blocked Candidates

| Name | Tier | Blocking errors |
|---|---|---|
| cartographer | L2 | local tool loop exceeded max rounds |
| codex-primus | L2 | provider credit balance is too low |
| cyber-codex | L2 | local tool loop exceeded max rounds |
| cyber-groq | L2 | provider access denied |
| glm-researcher | L2 | provider credit balance is too low |
| jagat_kalyan | L2 | provider timeout |
| kimi-cartographer | L2 | provider timeout |
| minimax-challenger | L2 | provider model endpoint is gone |
| nim-generalist | L2 | provider credit balance is too low |
| nim-validator | L2 | provider credit balance is too low |
| opus-primus | L2 | provider credit balance is too low |
| qwen-builder | L2 | provider timeout |
| researcher | L2 | provider route has no tool-use-capable endpoint |
| conductor_claude | L3 | [Errno 2] No such file or directory: '/Users/dhyana/.dharma/stigmergy/marks.tmp' -> '/Users/dhyana/.dharma/stigmergy/marks.jsonl'; database disk image is malformed; provider credit balance is too low |
| conductor_codex | L3 | [Errno 2] No such file or directory: '/Users/dhyana/.dharma/stigmergy/marks.tmp' -> '/Users/dhyana/.dharma/stigmergy/marks.jsonl'; database disk image is malformed; provider credit balance is too low |
| cron:yatagarasu-flight | L1 | provider credit balance is too low |
| cron:planetary-reciprocity-pulse | L1 | provider credit balance is too low |
| cron:planetary-reciprocity-cultivation | L1 | provider credit balance is too low |
| cron:telos-mission-scout | L1 | provider credit balance is too low |
| cron:doctor_assurance | L3 | doctor report status=FAIL |
| cron:Ontology-Native Insight Brief | L1 | Unsupported cron handler: insight_brief |

## Readiness Rows

| Name | Kind | Tier | L4? | Missing evidence | Next required action |
|---|---|---|---|---|---|
| 70df573a9bbf7b43 | registered_worker | L2 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | create signed agent passport |
| archeologist | registered_worker | L2 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | create signed agent passport |
| architect | registered_worker | L2 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | create signed agent passport |
| builder | registered_worker | L2 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | create signed agent passport |
| cartographer | registered_worker | L2 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | resolve blocking runtime/provider error |
| claude_composer | registered_worker | L1 | false | wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | create supervised TaskClaim with heartbeat |
| codex-primus | registered_worker | L2 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | resolve blocking runtime/provider error |
| codex_composer | registered_worker | L1 | false | current_process_present | attach candidate to supervised live process |
| cyber-codex | registered_worker | L2 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | resolve blocking runtime/provider error |
| cyber-glm5 | registered_worker | L2 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | create signed agent passport |
| cyber-groq | registered_worker | L2 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | resolve blocking runtime/provider error |
| cyber-kimi25 | registered_worker | L2 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | create signed agent passport |
| cyber-opus | registered_worker | L2 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | create signed agent passport |
| deepseek | registered_worker | L1 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | create signed agent passport |
| garuda | registered_worker | L1 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | create signed agent passport |
| glm | registered_worker | L1 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | create signed agent passport |
| glm-researcher | registered_worker | L2 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | resolve blocking runtime/provider error |
| jagat-kalyan | registered_worker | L2 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | create signed agent passport |
| jagat_kalyan | registered_worker | L2 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | resolve blocking runtime/provider error |
| kimi | registered_worker | L1 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | create signed agent passport |
| kimi-2-6-claw | registered_worker | L1 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | create signed agent passport |
| kimi-cartographer | registered_worker | L2 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | resolve blocking runtime/provider error |
| minimax-challenger | registered_worker | L2 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | resolve blocking runtime/provider error |
| nemotron | registered_worker | L1 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | create signed agent passport |
| nim-generalist | registered_worker | L2 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | resolve blocking runtime/provider error |
| nim-validator | registered_worker | L2 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | resolve blocking runtime/provider error |
| opus-primus | registered_worker | L2 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | resolve blocking runtime/provider error |
| qwen | registered_worker | L1 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | create signed agent passport |
| qwen-builder | registered_worker | L2 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | resolve blocking runtime/provider error |
| researcher | registered_worker | L2 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | resolve blocking runtime/provider error |
| scout | registered_worker | L1 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | create signed agent passport |
| sentinel | registered_worker | L1 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | create signed agent passport |
| setu | registered_worker | L1 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | create signed agent passport |
| surgeon | registered_worker | L2 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | create signed agent passport |
| vajra | registered_worker | L1 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | create signed agent passport |
| validator | registered_worker | L2 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | create signed agent passport |
| conductor_claude | persistent_agent_candidate | L3 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present | repair malformed conductor memory database |
| conductor_codex | persistent_agent_candidate | L3 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present | repair malformed conductor memory database |
| cron:yatagarasu-flight | script | L1 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | exclude from cultivation: not an identity-bearing agent |
| cron:planetary-reciprocity-pulse | script | L1 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | exclude from cultivation: not an identity-bearing agent |
| cron:planetary-reciprocity-cultivation | script | L1 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | exclude from cultivation: not an identity-bearing agent |
| cron:telos-mission-scout | script | L1 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | exclude from cultivation: not an identity-bearing agent |
| cron:doctor_assurance | script | L3 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | exclude from cultivation: not an identity-bearing agent |
| cron:Shakti Executive Opportunity Board | script | L3 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | exclude from cultivation: not an identity-bearing agent |
| cron:Frontier Refill From Opportunity Board | script | L3 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | exclude from cultivation: not an identity-bearing agent |
| cron:Ontology-Native Insight Brief | script | L1 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | exclude from cultivation: not an identity-bearing agent |
| dharma_swarm_orchestrate_live_daemon | daemon | L3 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present | exclude from cultivation: not an identity-bearing agent |
| dharma_swarm_cron_daemon | daemon | L3 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present | exclude from cultivation: not an identity-bearing agent |
| dharmic_agora_agent_frameworks | framework | L0 | false | passport_present, wake_claim_present, runtime_session_present, delegation_run_present, context_bundle_present, routing_decision_present, memory_receipts_present, artifact_present, outcome_present, recent_success_present, current_process_present | exclude from cultivation: not an identity-bearing agent |

## First Cultivation Target

`cyber-glm5` remains the first cultivation target. Its next action is the value in `next_required_action` in `l4_readiness.jsonl`; until that row has passport, wake claim, session, run, context, route, required lease evidence, memory receipts, artifact, recent outcome, and supervised process evidence on one chain, it is not L4.
