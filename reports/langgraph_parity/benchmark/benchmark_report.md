# LangGraph Parity Isolation Benchmark

Suite: `langgraph_parity_isolation_distractors`
Provider/model: `local` / `deterministic-isolation-harness-v1`
Distractor domains: 8
Tasks: 4

## Summary

| Mode | Avg score | Tokens | Cost USD | Failure classes |
| --- | ---: | ---: | ---: | --- |
| single_agent | 0.875 | 345 | 0.000069 | missing_required_domain |
| swarm | 1.000 | 459 | 0.000092 | none |
| supervisor | 1.000 | 539 | 0.000108 | none |

## Results

| Task | Mode | Score | Tokens | Cost USD | Latency ms | Handoffs | Agents | Failures |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| climate_finance_multihop | single_agent | 0.500 | 90 | 0.000018 | 19 | 0 | climate_agent | missing_required_domain |
| climate_finance_multihop | swarm | 1.000 | 174 | 0.000035 | 38 | 1 | climate_agent, finance_agent | none |
| climate_finance_multihop | supervisor | 1.000 | 194 | 0.000039 | 51 | 2 | climate_agent, finance_agent | none |
| security_patch_review | single_agent | 1.000 | 78 | 0.000016 | 19 | 0 | security_agent | none |
| security_patch_review | swarm | 1.000 | 88 | 0.000018 | 25 | 0 | security_agent | none |
| security_patch_review | supervisor | 1.000 | 108 | 0.000022 | 38 | 1 | security_agent | none |
| contract_policy_check | single_agent | 1.000 | 85 | 0.000017 | 19 | 0 | legal_agent | none |
| contract_policy_check | swarm | 1.000 | 95 | 0.000019 | 25 | 0 | legal_agent | none |
| contract_policy_check | supervisor | 1.000 | 115 | 0.000023 | 38 | 1 | legal_agent | none |
| supply_eta_risk | single_agent | 1.000 | 92 | 0.000018 | 19 | 0 | supply_agent | none |
| supply_eta_risk | swarm | 1.000 | 102 | 0.000020 | 25 | 0 | supply_agent | none |
| supply_eta_risk | supervisor | 1.000 | 122 | 0.000024 | 38 | 1 | supply_agent | none |
