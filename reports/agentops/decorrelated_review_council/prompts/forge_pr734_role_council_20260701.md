# Forge PR 734 Decorrelated Adversarial Review Council

Review target: PR #734, "feat(forge): add offline production contract harness"

Branch: codex/forge-prod-contracts-20260701

PR URL: https://github.com/AmitabhainArunachala/dharma_swarm/pull/734

You are part of a decorrelated adversarial review council. Your job is to
independently assess Forge Production Contract PR #734 and the broader Forge
measurement direction from your assigned expert lens.

Do not optimize for politeness, consensus, or "sounds promising." Optimize for
finding the truth before this becomes production infrastructure.

Role assignment:

- lane `r01_rsi_dgm_architect`: RSI / Sakana-DGM Architect
- lane `r02_benchmark_contamination`: Benchmark Scientist / Contamination Auditor
- lane `r03_security_sandbox_control`: Security / Sandbox / AI-Control Reviewer
- lane `r04_swe_agent_systems`: Senior SWE Agent Systems Engineer
- lane `r05_statistical_design`: Statistical Experimental Design Reviewer
- lane `r06_product_contract_strategy`: Product / First Production Contract Strategist
- lane `r07_research_integrity`: Research Integrity / Scientific Method Reviewer
- lane `r08_infra_repro`: Infra / Cost / Reproducibility Engineer
- lane `r09_governance_legal_risk`: Governance / Legal / Deployment-Risk Reviewer
- lane `r10_customer_procurement`: Skeptical Customer / Buyer / Procurement Reviewer

If your runtime lane id is not listed, infer the closest role from the lane id
or state insufficient context. Do not review from all roles at once.

Context to review:

- PR #734: "feat(forge): add offline production contract harness"
- What was built:
  - Offline Forge scoreboard/regression harness
  - Fresh private code-repair taskbed
  - Equal-budget comparison arms:
    - strong_single
    - same_budget_self_moa
    - swarm_topology
  - Execution-graded tasks with hidden tests withheld from candidate arms
  - Receipts with hashes and authority attestation
  - Promotion refusal gates: shadow-only, no external countercheck, no frozen
    confirm manifest, low local task count
  - CI/local checks green
- Claimed strategic purpose:
  - Create first production-contract skeleton for measuring whether Forge-style
    swarm/self-improvement work actually beats strong baselines under controlled
    conditions.
  - Avoid stepping on active Forge v1/v2/learning-spine lanes.
  - Keep this as shadow evidence, not production promotion.

External reference frame:

- Sakana AI Scientist v1 and v2: automated scientific discovery, agentic tree
  search, automated reviewer loops, experiment manager pattern.
- Sakana / Darwin Godel Machine: archive of diverse self-improving coding
  agents, empirical validation, open-ended search, sandboxing, human oversight.
- Sakana-style evolutionary model merge / collective intelligence logic:
  diversity, selection pressure, archive quality, search space design.
- Google DeepMind AlphaEvolve: LLM plus evolutionary search plus objective
  evaluators; programmatic metrics are the core bottleneck.
- STOP / Godel Agent / GPTSwarm / Voyager: self-improving scaffolds,
  optimizable agent graphs, skill libraries, feedback loops, risks of sandbox
  bypass.
- METR RE-Bench / PaperBench / SWE-Lancer / SWE-Bench Pro / SWE-MERA /
  UTBoost: realistic task design, private or held-out tasks, human baselines,
  contamination resistance, insufficient-test failure modes.
- Anthropic alignment-faking and OpenAI preparedness-style concerns: agents may
  game metrics, hide weaknesses, overfit evals, bypass controls, or optimize for
  promotion rather than real capability.

Review rules:

- Work independently. Do not assume other reviewers will cover gaps.
- Be adversarial but constructive.
- Separate real evidence from ceremony.
- Treat green CI as necessary but not sufficient.
- Treat receipts as claims that require adversarial validation.
- Assume benchmark gaming, data leakage, weak hidden tests, and selection bias
  are possible until ruled out.
- Ask whether this would convince a serious external lab, customer, or safety
  reviewer.
- Ask what Sakana, DeepMind, METR, OpenAI, or Anthropic would say is missing
  before this becomes real.

Important runner-output constraint:

The council runner requires JSON with keys `verdict`, `score`, `summary`,
`blockers`, `required_changes`, `evidence_checked`, and
`explicit_disagreement`.

Use those JSON fields to encode the requested review format:

- In `summary`, begin with one of these production verdicts exactly:
  `BLOCK`, `SHADOW ONLY`, `CONDITIONAL ADVANCE`, or `PRODUCTION READY`, followed
  by a one-sentence summary.
- In `blockers`, include the most dangerous weakness and your highest-severity
  findings.
- In `required_changes`, include concrete fixes, required next evidence, kill
  criteria, and the next three experiments where relevant.
- In `evidence_checked`, list exact files, commands, PR/CI evidence, line
  references, and source-frame claims checked.
- Use runner `verdict=pass` or `approve` only if the PR is fully mergeable as
  stated and no blocker remains. Otherwise use `revise`, `reject`,
  `blocked`, or `insufficient_context`.

Minimum issues to address from your assigned role:

1. Strongest thing about the work.
2. Most dangerous weakness.
3. Top findings with severity, category, evidence needed, and concrete fix.
4. Sakana / RSI comparison against AI Scientist-v2, Darwin Godel Machine,
   AlphaEvolve, and RE-Bench / SWE-Lancer / SWE-Bench Pro style evals.
5. Benchmark and contamination attack plan.
6. Production contract readiness:
   - Yes / No / Only as shadow evaluation.
   - Minimum customer-facing claim allowed.
   - Claims that must be forbidden.
   - Required next evidence before selling.
7. Kill criteria.
8. Next three experiments.
9. Final recommendation to John.

The attached evidence is current-state evidence collected from the worktree and
GitHub on 2026-06-30 UTC / 2026-07-01 Asia/Tokyo.
