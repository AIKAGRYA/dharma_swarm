# LangGraph Parity Isolation Benchmark

Suite: `langgraph_parity_isolation_distractors`
Provider/model: `local` / `deterministic-isolation-harness-v1`
Distractor domains: 8
Tasks: 26

## Summary

| Mode | Avg score | Tokens | Cost USD | Failure classes |
| --- | ---: | ---: | ---: | --- |
| single_agent | 0.763 | 2224 | 0.000444 | missing_required_domain |
| swarm | 1.000 | 3438 | 0.000689 | none |
| supervisor | 1.000 | 3958 | 0.000793 | none |

## Results

| Task | Mode | Score | Tokens | Cost USD | Latency ms | Handoffs | Agents | Failures |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| climate_finance_multihop | single_agent | 0.500 | 90 | 0.000018 | 19 | 0 | climate_agent | missing_required_domain |
| climate_finance_multihop | swarm | 1.000 | 174 | 0.000035 | 38 | 1 | climate_agent, finance_agent | none |
| climate_finance_multihop | supervisor | 1.000 | 194 | 0.000039 | 51 | 2 | climate_agent, finance_agent | none |
| climate_checkpoint_reload | single_agent | 1.000 | 83 | 0.000017 | 19 | 0 | climate_agent | none |
| climate_checkpoint_reload | swarm | 1.000 | 93 | 0.000019 | 25 | 0 | climate_agent | none |
| climate_checkpoint_reload | supervisor | 1.000 | 113 | 0.000023 | 38 | 1 | climate_agent | none |
| finance_legal_pipeline | single_agent | 0.500 | 91 | 0.000018 | 19 | 0 | finance_agent | missing_required_domain |
| finance_legal_pipeline | swarm | 1.000 | 173 | 0.000035 | 38 | 1 | finance_agent, legal_agent | none |
| finance_legal_pipeline | supervisor | 1.000 | 193 | 0.000039 | 51 | 2 | finance_agent, legal_agent | none |
| security_legal_retry_patch | single_agent | 0.500 | 82 | 0.000016 | 19 | 0 | security_agent | missing_required_domain |
| security_legal_retry_patch | swarm | 1.000 | 164 | 0.000033 | 38 | 1 | security_agent, legal_agent | none |
| security_legal_retry_patch | supervisor | 1.000 | 184 | 0.000037 | 51 | 2 | security_agent, legal_agent | none |
| supply_finance_fan_in | single_agent | 0.500 | 92 | 0.000018 | 19 | 0 | supply_agent | missing_required_domain |
| supply_finance_fan_in | swarm | 1.000 | 176 | 0.000035 | 39 | 1 | supply_agent, finance_agent | none |
| supply_finance_fan_in | supervisor | 1.000 | 196 | 0.000039 | 51 | 2 | supply_agent, finance_agent | none |
| supply_finance_legal_send | single_agent | 0.333 | 94 | 0.000019 | 19 | 0 | supply_agent | missing_required_domain |
| supply_finance_legal_send | swarm | 1.000 | 250 | 0.000050 | 52 | 2 | supply_agent, finance_agent, legal_agent | none |
| supply_finance_legal_send | supervisor | 1.000 | 270 | 0.000054 | 64 | 3 | supply_agent, finance_agent, legal_agent | none |
| travel_finance_pipeline | single_agent | 0.500 | 84 | 0.000017 | 19 | 0 | travel_agent | missing_required_domain |
| travel_finance_pipeline | swarm | 1.000 | 168 | 0.000034 | 38 | 1 | travel_agent, finance_agent | none |
| travel_finance_pipeline | supervisor | 1.000 | 188 | 0.000038 | 51 | 2 | travel_agent, finance_agent | none |
| growth_finance_broadcast | single_agent | 0.500 | 85 | 0.000017 | 19 | 0 | growth_agent | missing_required_domain |
| growth_finance_broadcast | swarm | 1.000 | 169 | 0.000034 | 38 | 1 | growth_agent, finance_agent | none |
| growth_finance_broadcast | supervisor | 1.000 | 189 | 0.000038 | 51 | 2 | growth_agent, finance_agent | none |
| medical_interrupt_resume | single_agent | 1.000 | 81 | 0.000016 | 19 | 0 | medical_agent | none |
| medical_interrupt_resume | swarm | 1.000 | 91 | 0.000018 | 25 | 0 | medical_agent | none |
| medical_interrupt_resume | supervisor | 1.000 | 111 | 0.000022 | 38 | 1 | medical_agent | none |
| a2a_blocker_queue | single_agent | 1.000 | 83 | 0.000017 | 19 | 0 | security_agent | none |
| a2a_blocker_queue | swarm | 1.000 | 93 | 0.000019 | 25 | 0 | security_agent | none |
| a2a_blocker_queue | supervisor | 1.000 | 113 | 0.000023 | 38 | 1 | security_agent | none |
| vendor_timeout_cancellation | single_agent | 1.000 | 92 | 0.000018 | 19 | 0 | supply_agent | none |
| vendor_timeout_cancellation | swarm | 1.000 | 102 | 0.000020 | 25 | 0 | supply_agent | none |
| vendor_timeout_cancellation | supervisor | 1.000 | 122 | 0.000024 | 38 | 1 | supply_agent | none |
| security_patch_review | single_agent | 1.000 | 78 | 0.000016 | 19 | 0 | security_agent | none |
| security_patch_review | swarm | 1.000 | 88 | 0.000018 | 25 | 0 | security_agent | none |
| security_patch_review | supervisor | 1.000 | 108 | 0.000022 | 38 | 1 | security_agent | none |
| climate_broadcast_measurement | single_agent | 1.000 | 84 | 0.000017 | 19 | 0 | climate_agent | none |
| climate_broadcast_measurement | swarm | 1.000 | 94 | 0.000019 | 25 | 0 | climate_agent | none |
| climate_broadcast_measurement | supervisor | 1.000 | 114 | 0.000023 | 38 | 1 | climate_agent | none |
| finance_fan_in_variance | single_agent | 1.000 | 92 | 0.000018 | 19 | 0 | finance_agent | none |
| finance_fan_in_variance | swarm | 1.000 | 102 | 0.000020 | 25 | 0 | finance_agent | none |
| finance_fan_in_variance | supervisor | 1.000 | 122 | 0.000024 | 38 | 1 | finance_agent | none |
| contract_policy_check | single_agent | 1.000 | 85 | 0.000017 | 19 | 0 | legal_agent | none |
| contract_policy_check | swarm | 1.000 | 95 | 0.000019 | 25 | 0 | legal_agent | none |
| contract_policy_check | supervisor | 1.000 | 115 | 0.000023 | 38 | 1 | legal_agent | none |
| growth_provider_fallback | single_agent | 1.000 | 80 | 0.000016 | 19 | 0 | growth_agent | none |
| growth_provider_fallback | swarm | 1.000 | 90 | 0.000018 | 25 | 0 | growth_agent | none |
| growth_provider_fallback | supervisor | 1.000 | 110 | 0.000022 | 38 | 1 | growth_agent | none |
| travel_memory_isolation | single_agent | 1.000 | 83 | 0.000017 | 19 | 0 | travel_agent | none |
| travel_memory_isolation | swarm | 1.000 | 93 | 0.000019 | 25 | 0 | travel_agent | none |
| travel_memory_isolation | supervisor | 1.000 | 113 | 0.000023 | 38 | 1 | travel_agent | none |
| medical_tool_boundary | single_agent | 1.000 | 78 | 0.000016 | 19 | 0 | medical_agent | none |
| medical_tool_boundary | swarm | 1.000 | 88 | 0.000018 | 25 | 0 | medical_agent | none |
| medical_tool_boundary | supervisor | 1.000 | 108 | 0.000022 | 38 | 1 | medical_agent | none |
| security_subagent_tool_review | single_agent | 0.500 | 83 | 0.000017 | 19 | 0 | security_agent | missing_required_domain |
| security_subagent_tool_review | swarm | 1.000 | 165 | 0.000033 | 38 | 1 | security_agent, legal_agent | none |
| security_subagent_tool_review | supervisor | 1.000 | 185 | 0.000037 | 51 | 2 | security_agent, legal_agent | none |
| climate_finance_budget_retry | single_agent | 0.500 | 85 | 0.000017 | 19 | 0 | climate_agent | missing_required_domain |
| climate_finance_budget_retry | swarm | 1.000 | 169 | 0.000034 | 38 | 1 | climate_agent, finance_agent | none |
| climate_finance_budget_retry | supervisor | 1.000 | 189 | 0.000038 | 51 | 2 | climate_agent, finance_agent | none |
| supply_broadcast_inventory | single_agent | 1.000 | 87 | 0.000017 | 19 | 0 | supply_agent | none |
| supply_broadcast_inventory | swarm | 1.000 | 97 | 0.000019 | 25 | 0 | supply_agent | none |
| supply_broadcast_inventory | supervisor | 1.000 | 117 | 0.000023 | 38 | 1 | supply_agent | none |
| legal_finance_fan_out_policy | single_agent | 0.500 | 92 | 0.000018 | 19 | 0 | legal_agent | missing_required_domain |
| legal_finance_fan_out_policy | swarm | 1.000 | 176 | 0.000035 | 39 | 1 | legal_agent, finance_agent | none |
| legal_finance_fan_out_policy | supervisor | 1.000 | 196 | 0.000039 | 51 | 2 | legal_agent, finance_agent | none |
| growth_finance_command_send | single_agent | 0.500 | 79 | 0.000016 | 19 | 0 | growth_agent | missing_required_domain |
| growth_finance_command_send | swarm | 1.000 | 163 | 0.000033 | 38 | 1 | growth_agent, finance_agent | none |
| growth_finance_command_send | supervisor | 1.000 | 183 | 0.000037 | 51 | 2 | growth_agent, finance_agent | none |
| travel_finance_a2a_operator | single_agent | 0.500 | 87 | 0.000017 | 19 | 0 | travel_agent | missing_required_domain |
| travel_finance_a2a_operator | swarm | 1.000 | 171 | 0.000034 | 38 | 1 | travel_agent, finance_agent | none |
| travel_finance_a2a_operator | supervisor | 1.000 | 191 | 0.000038 | 51 | 2 | travel_agent, finance_agent | none |
| climate_cancellation_watch | single_agent | 1.000 | 82 | 0.000016 | 19 | 0 | climate_agent | none |
| climate_cancellation_watch | swarm | 1.000 | 92 | 0.000018 | 25 | 0 | climate_agent | none |
| climate_cancellation_watch | supervisor | 1.000 | 112 | 0.000022 | 38 | 1 | climate_agent | none |
| supply_eta_risk | single_agent | 1.000 | 92 | 0.000018 | 19 | 0 | supply_agent | none |
| supply_eta_risk | swarm | 1.000 | 102 | 0.000020 | 25 | 0 | supply_agent | none |
| supply_eta_risk | supervisor | 1.000 | 122 | 0.000024 | 38 | 1 | supply_agent | none |
