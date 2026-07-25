# Forge PR 734 Adversarial Council Synthesis

Source prompt:
`/Users/dhyana/.codex/attachments/2ffc7861-9953-4012-80b6-733ac57b3159/pasted-text-1.txt`

Council artifacts:

- Prompt: `reports/agentops/decorrelated_review_council/prompts/forge_pr734_role_council_20260701.md`
- Evidence packet: `reports/agentops/decorrelated_review_council/evidence/forge_pr734_evidence_20260701.md`
- Council JSON: `reports/agentops/decorrelated_review_council/20260630T225421Z-forge-pr734-production-contract-role-council-hold_blockers.json`
- Council Markdown: `reports/agentops/decorrelated_review_council/20260630T225421Z-forge-pr734-production-contract-role-council-hold_blockers.md`

## 1. Verdict

SHADOW ONLY

## 2. One-sentence Summary

PR #734 is a useful shadow harness skeleton with honest promotion refusal, but
it does not measure Forge swarm, self-MoA, RSI, or production capability because
the compared arms are deterministic patch fixtures over three synthetic tasks.

## 3. Strongest Thing About The Work

The strongest feature is the bounded shape: isolated package, focused tests,
fresh local receipt, green CI, hidden-test interface separation, and hard-coded
promotion refusal gates. That is the right governance posture for a first
measurement scaffold.

## 4. Most Dangerous Weakness

The labels `strong_single`, `same_budget_self_moa`, and `swarm_topology` look
like real baselines, but `scoreboard.py:236-307` implements them as deterministic
string-rewrite patchers. The reported `swarm_lift_vs_strong_single=0.3333` is
therefore a fixture artifact, not evidence that Forge beats any strong baseline.

## 5. Top 10 Findings

1. Severity: Critical. Category: eval.
   Evidence needed: Real model/swarm execution traces for each arm.
   Concrete fix: Rename current arms to mock/fixture arms or replace them with
   real adapters before any comparative metric is emitted.

2. Severity: Critical. Category: research.
   Evidence needed: A test suite that does not assert the desired ranking.
   Concrete fix: Remove the test assertion in
   `tests/test_forge_prod_contracts.py:52-76` that requires swarm to beat
   strong single; test structural invariants instead.

3. Severity: Critical. Category: stats.
   Evidence needed: A preregistered analysis plan, task-count justification,
   uncertainty intervals, and failure analysis.
   Concrete fix: Do not report lift as evidence with `n=3`; expand to a frozen
   taskbed and report effect sizes with uncertainty.

4. Severity: High. Category: contamination.
   Evidence needed: Proof that hidden tests are not visible to candidate agents
   or future training/context paths.
   Concrete fix: Move hidden tests out of repo source, use a frozen manifest
   with hashes, and document the threat model.

5. Severity: High. Category: security.
   Evidence needed: Hardened execution evidence for untrusted candidate code.
   Concrete fix: Run grading in a locked-down container or VM with no network,
   resource limits, read-only inputs, and syscall/file/network monitoring.

6. Severity: High. Category: governance.
   Evidence needed: Independent attestation of offline execution and no router,
   Darwin, archive, or provider mutation.
   Concrete fix: Add an external countercheck or signed observer receipt; do not
   rely on self-authored receipt constants.

7. Severity: High. Category: product.
   Evidence needed: A customer-safe claim matrix.
   Concrete fix: Add forbidden claims to docs and CLI output: no "Forge beats
   strong baselines", no "production ready", no "self-MoA improves", and no use
   of current scores in sales or marketing.

8. Severity: Medium. Category: infra.
   Evidence needed: Reproducible runs from a second runner/operator.
   Concrete fix: Add a third-party or separate-host rerun that verifies the
   scoreboard artifact hash and receipt hash.

9. Severity: Medium. Category: implementation.
   Evidence needed: Actual budget accounting.
   Concrete fix: Replace word/character token heuristics with measured provider
   tokens, wall-clock, and cost once real arms are added.

10. Severity: Medium. Category: governance.
    Evidence needed: A sunset or redesign rule if this remains a fixture.
    Concrete fix: Add kill criteria to the governance report and enforce them in
    track status checks.

## 6. Sakana / RSI Comparison

AI Scientist-v2: Forge is behind. PR #734 has no experiment manager loop, no
automated paper/reviewer loop, and no genuine research iteration. It is
orthogonal as a local harness shell.

Darwin Godel Machine: Forge is behind. There is no archive of diverse agents, no
mutation, no empirical selection pressure, and no sandboxed self-improvement
loop.

AlphaEvolve: Forge is directionally aligned on executable evaluators, but far
behind on evaluator scale, objective rigor, and real evolutionary search. The
current objective is tiny and hand-aligned with the fixtures.

RE-Bench / SWE-Lancer / SWE-Bench Pro style evals: Forge is behind on realism,
private held-out task design, human baselines, task count, contamination
resistance, and independent grading. It is ahead only in refusing promotion
instead of overselling the evidence.

## 7. Benchmark And Contamination Attack Plan

- Task leakage: read hidden tests directly from `taskbed.py:163-266`.
- Hidden test weakness: generate trivial patches specialized to the two tests
  per task.
- Arm unfairness: exploit that the swarm fixture composes more patch functions
  than the strong-single fixture.
- Budget unfairness: show that `_estimate_tokens` is not real token, latency, or
  dollar cost accounting.
- Prompt leakage: include task/source/hidden-test hashes in future prompts and
  see whether agents infer fixtures.
- Scoring overfit: add a task whose correct repair is not expressible by string
  replacement and observe fixture collapse.
- Synthetic task bias: compare against real repo bugs with multi-file context.
- Non-representative taskbed: require tasks from at least three real code
  domains and bug families.
- Receipt forgery: mutate `receipts.py` authority constants and confirm no
  external monitor catches it.
- Sandbox bypass: run malicious candidate code that reads host files, opens
  sockets, forks, or writes outside the temp directory.

## 8. Production Contract Readiness

Would I let this support a first paid production contract?

Only as shadow evaluation.

Minimum customer-facing claim allowed:

"Forge now has a local shadow harness scaffold that can run deterministic
fixture arms over three synthetic code-repair tasks, produce receipts, and
refuse promotion."

Claims that must be forbidden:

- Forge swarm beats strong baseline.
- Self-MoA improves over single agent.
- The harness is production ready.
- The taskbed is externally private or contamination resistant.
- Receipt authority attestations prove offline/no-network execution.
- Current scores support customer procurement or deployment decisions.

Required next evidence before selling:

- Real strong-single, self-MoA, and swarm adapters.
- Frozen private confirm manifest outside repo source.
- At least 200 realistic held-out tasks across multiple bug families.
- Human or external baseline.
- Independent grading and signed external attestation.
- Hardened sandbox evidence.
- Preregistered statistical plan and kill criteria.

## 9. Kill Criteria

- Stop or redesign if real arms are not wired after the next milestone.
- Stop or redesign if hidden tests remain in repo source for any confirm set.
- Stop or redesign if the independent grader disagrees with the harness grader
  on more than 5 percent of cases.
- Stop or redesign if any receipt authority claim is found unverifiable or
  forgeable.
- Stop or redesign if the harness keeps reporting lift from fixture arms.
- Stop or redesign if a sandbox escape, host-file read, network call, or
  unbounded resource use is possible during candidate grading.
- Stop or redesign if customer-facing language cites current scores as
  capability evidence.

## 10. Next 3 Experiments

1. Experiment name: Real-arm adapter smoke.
   Hypothesis: The harness can execute actual strong-single, self-MoA, and
   swarm arms under measured equal budget without leaking hidden tests.
   Minimum task count: 30.
   Baseline: strongest configured single model.
   Success threshold: all arms produce auditable traces, real token/cost logs,
   and no hidden-test access; no capability claim yet.
   Failure interpretation: the harness is still a fixture scaffold.

2. Experiment name: Frozen private confirm set.
   Hypothesis: Forge-style topology beats the strong-single baseline on
   realistic held-out repairs after preregistration.
   Minimum task count: 200.
   Baseline: strongest single model with the same measured budget.
   Success threshold: statistically significant lift with confidence intervals,
   no contamination finding, and independent grader agreement above 99 percent.
   Failure interpretation: no production claim; inspect task classes and arm
   traces before changing the system.

3. Experiment name: Control and sandbox red-team.
   Hypothesis: Candidate execution and receipt generation resist leakage,
   exfiltration, and forged authority claims.
   Minimum task count: 50 adversarial submissions plus receipt mutation tests.
   Baseline: current subprocess/tempdir grader.
   Success threshold: no host-file reads, no network, enforced resource limits,
   and external attestation catches receipt mutation.
   Failure interpretation: no untrusted code execution in this harness until
   isolation is redesigned.

## 11. Final Recommendation To John

Keep the PR only as a shadow scaffold after tightening the language. The next
highest-leverage move is not more synthetic tasks; it is to replace fixture arms
with a real adapter boundary, remove the baked-in swarm-win assertion, and add a
small private confirm set outside repo source with an independent grader. Do not
sell, promote, or cite the current `0.3333` lift.

## Verification Performed

- Read the pasted prompt file.
- Used `codex-composer-decorrelated-review-council` skill.
- Reran focused tests: `6 passed in 1.84s`.
- Reran CLI scoreboard and generated a fresh receipt:
  `receipt_sha256=sha256:1a73c9dbf6ec7f96f5faf7d1ef5ecd23d4b89a6d42a3aafb65a483af855b4581`.
- Confirmed GitHub PR checks were green.
- Ran 10 role-specific council critics; result:
  `conviction_gate=hold_blockers`, `score_min=18`, `score_avg=46.2`,
  persistent `palantir-pilot` witness fresh.
- Closeout impact check: local diffs against
  `f84f40344cbdfab9d236239b0d3ec00718e10bf9` and `origin/main...HEAD`
  showed the Forge production-contract package, two governance/docops files,
  council artifacts, one governance report, and the focused Forge test; no
  active runtime router, provider, Darwin apply, archive-fitness, or active
  Forge v1/v2 scheduler files were touched.

## Sources

- Sakana AI Scientist: https://arxiv.org/abs/2408.06292
- AI Scientist-v2: https://arxiv.org/abs/2504.08066
- Darwin Godel Machine: https://arxiv.org/abs/2505.22954
- AlphaEvolve: https://arxiv.org/abs/2506.13131
- STOP: https://arxiv.org/abs/2310.02304
- GPTSwarm: https://arxiv.org/abs/2402.16823
- Voyager: https://arxiv.org/abs/2305.16291
- RE-Bench: https://arxiv.org/abs/2411.15114
- SWE-Lancer: https://arxiv.org/abs/2502.12115
- SWE-Bench Pro: https://arxiv.org/abs/2509.16941
- UTBoost: https://arxiv.org/abs/2506.09289
- Alignment faking: https://arxiv.org/abs/2412.14093
