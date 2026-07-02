# Evidence Packet: Forge PR 734 Production Contract Harness

Generated for a decorrelated adversarial council run.

## Repository State

- Repo root: `/Users/dhyana/ds_forge_prod_contracts_20260701`
- Branch: `codex/forge-prod-contracts-20260701`
- Base: `origin/main`
- Worktree status before council prompt creation: clean on
  `codex/forge-prod-contracts-20260701...origin/codex/forge-prod-contracts-20260701`
- PR: https://github.com/AmitabhainArunachala/dharma_swarm/pull/734
- PR state from GitHub: open draft PR, mergeable.
- PR title: `feat(forge): add offline production contract harness`
- Commits:
  - `b7d68284a` `feat(forge): add offline production contract harness`
  - `0e57eef7f` `chore(docops): refresh counts for forge contract harness`

## Diff Surface

`git diff --stat origin/main...HEAD` reports 9 files changed, 1000 insertions,
15 deletions:

- Added `dharma_swarm/forge_prod_contracts/__init__.py`
- Added `dharma_swarm/forge_prod_contracts/cli.py`
- Added `dharma_swarm/forge_prod_contracts/receipts.py`
- Added `dharma_swarm/forge_prod_contracts/scoreboard.py`
- Added `dharma_swarm/forge_prod_contracts/taskbed.py`
- Modified `docs/docops/AUTO_INVENTORY.md`
- Modified `docs/governance/SOVEREIGN_MANIFEST.md`
- Added `reports/governance/forge_prod_contracts_2026-07-01.md`
- Added `tests/test_forge_prod_contracts.py`

No active Forge v1/v2, routing, provider, Darwin, or archive-fitness files were
changed by this PR.

## GitHub Checks

`gh pr checks 734 --repo AmitabhainArunachala/dharma_swarm` showed all listed
checks passing, including:

- `pytest (3.11)` pass
- `pytest (3.12)` pass
- `semgrep` pass
- `Semgrep OSS` pass
- `gitleaks` pass
- `CodeQL` pass
- `codeql / python` pass
- `DocOps integrity gate` pass
- `manifest-check` pass
- `Quality ratchet - repo-wide fitness function` pass
- `Rule 10 - module line budget` pass
- `Rules 3 + 5 - test hygiene` pass
- `ACTIVE_TRACK governance gate` pass

PR discussion currently has one GitHub Actions informational comment for Spine
Adoption / Bypass Delta. No human reviews were present in the queried PR data.

## Fresh Local Verification

Commands rerun from `/Users/dhyana/ds_forge_prod_contracts_20260701`:

```text
/Users/dhyana/dharma_swarm/.venv/bin/python -m pytest -q tests/test_forge_prod_contracts.py --tb=short
```

Result:

```text
......                                                                   [100%]
6 passed in 1.84s
```

```text
/Users/dhyana/dharma_swarm/.venv/bin/python -m dharma_swarm.forge_prod_contracts.cli --run-id forge-prod-contracts-council-20260701T-local --output-dir reports/forge/production_contracts/20260701T-council-fresh-run
```

Result:

```text
wrote reports/forge/production_contracts/20260701T-council-fresh-run/scoreboard_report.json
wrote reports/forge/production_contracts/20260701T-council-fresh-run/scoreboard_report.md
wrote reports/forge/production_contracts/20260701T-council-fresh-run/scoreboard_receipt.json
task_count: 3
strong_single: 2/3, average_score 0.6667, tokens_spent 192
same_budget_self_moa: 3/3, average_score 1.0, tokens_spent 237
swarm_topology: 3/3, average_score 1.0, tokens_spent 225
swarm_lift_vs_strong_single: 0.3333
promotion_allowed: false
blocked_gates:
- shadow_only_first_production_contract
- local_task_count_below_confirm_threshold
- no_independent_external_countercheck
- no_frozen_confirm_manifest
```

```text
git diff --check
```

Result: no output, return code 0.

## Fresh Receipt

Receipt path:

`reports/forge/production_contracts/20260701T-council-fresh-run/scoreboard_receipt.json`

Receipt fields:

```json
{
  "artifact_path": "reports/forge/production_contracts/20260701T-council-fresh-run/scoreboard_report.json",
  "artifact_sha256": "sha256:631264ae7f35f87c7dd6d83120845a76d5b463e0aa7778740ba8b06576f0b7a1",
  "authority_attestation": {
    "archive_fitness_mutated": false,
    "darwin_apply_called": false,
    "network_calls": 0,
    "offline": true,
    "provider_keys_read": false,
    "public_benchmark_submission": false,
    "router_mutated": false
  },
  "blocked_gates": [
    "shadow_only_first_production_contract",
    "local_task_count_below_confirm_threshold",
    "no_independent_external_countercheck",
    "no_frozen_confirm_manifest"
  ],
  "contamination_state": "fresh_private_local_generated",
  "equal_budget": true,
  "execution_graded": true,
  "promotion_allowed": false,
  "receipt_sha256": "sha256:1a73c9dbf6ec7f96f5faf7d1ef5ecd23d4b89a6d42a3aafb65a483af855b4581",
  "run_id": "forge-prod-contracts-council-20260701T-local",
  "schema_version": "forge_prod_contracts.receipt.v1",
  "task_manifest_sha256": "sha256:28246fd7c9152fe4f0cd632304bfa3653165971a4fffbdd7260097025044cd79"
}
```

## Implementation Facts

Taskbed:

- `dharma_swarm/forge_prod_contracts/taskbed.py:14-17` defines the schema,
  deterministic seed, contamination state, and local-private-fixture externality.
- `taskbed.py:65-80` exposes a visible manifest entry with hashes, but excludes
  the hidden test body.
- `taskbed.py:97-113` returns exactly three deterministic tasks.
- `taskbed.py:127-155` grades candidate source by writing `solution.py` and
  `test_hidden.py` into a temporary directory, running Python with a 10 second
  timeout, and returning binary pass/fail score.
- `taskbed.py:163-266` contains the three generated tasks and their hidden tests.

Scoreboard:

- `dharma_swarm/forge_prod_contracts/scoreboard.py:19-25` defines the schema and
  three arm names.
- `scoreboard.py:28-39` defines a fixed token-budget policy with
  `max_candidates_per_arm`.
- `scoreboard.py:54-56` has `CandidateSubmission.over_budget` return `False`,
  while the actual over-budget branch checks `estimated_tokens > token_budget`
  in `scoreboard.py:193-205`.
- `scoreboard.py:101-139` summarizes per-arm score, tokens, equal budget,
  contamination state, hidden-test withholding, and swarm lift.
- `scoreboard.py:141-156` hard-codes promotion refusal with four blockers.
- `scoreboard.py:176-233` runs every task through every arm and grades with the
  hidden execution grader.
- `scoreboard.py:236-261` builds submissions by deterministic local heuristics,
  not by invoking a real strong model, real self-MoA sampler, or real swarm.
- `scoreboard.py:269-307` patches known string patterns. The compared "arms"
  are therefore current scaffold fixtures, not evidence that actual Forge swarm
  execution outperforms a strong baseline.

Receipts:

- `dharma_swarm/forge_prod_contracts/receipts.py:15-35` writes JSON, Markdown,
  and receipt artifacts.
- `receipts.py:38-65` creates artifact/task hashes and authority attestation.
- Authority attestation fields are code-authored claims. They are useful but not
  independently enforced by a sandbox, syscall monitor, network monitor, or
  external auditor in this PR.

Tests:

- `tests/test_forge_prod_contracts.py:22-34` tests hidden-test withholding and
  seed stability.
- `tests/test_forge_prod_contracts.py:37-49` tests that the execution grader
  rejects a noop and accepts one repair.
- `tests/test_forge_prod_contracts.py:52-76` tests equal-budget claims and
  asserts `swarm_topology` beats `strong_single`.
- `tests/test_forge_prod_contracts.py:79-87` tests promotion refusal.
- `tests/test_forge_prod_contracts.py:89-119` tests receipt repeatability and
  authority-attestation fields.

## Main Evidence Interpretation

Real evidence:

- The PR adds an isolated harness package with tests and green CI.
- The harness executes hidden tests in temporary local directories.
- The candidate arm manifests exclude hidden test bodies.
- The scoreboard records hashes, authority claims, and promotion refusal.
- The PR does not mutate active routing, provider, Darwin, or archive-fitness
  code.

Ceremony or weak evidence:

- The "strong_single", "same_budget_self_moa", and "swarm_topology" arms are
  deterministic string-rewrite fixtures. They are labels for scaffold slots, not
  actual measured model or swarm behavior.
- The taskbed has only three local synthetic tasks.
- The hidden tests are in repo source and are private only relative to the local
  candidate-arm interface, not private from repository readers or future agents
  trained/conditioned on this PR.
- Equal budget is based on a local token estimate, not actual provider usage or
  wall-clock/compute accounting.
- Receipt authority attestations are generated by the harness itself and are not
  externally enforced.
- The result should not support claims stronger than "shadow-only harness
  skeleton exists and refuses promotion."

## External Reference Frame

Sources to use for high-level comparison:

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

Reference implications for this PR:

- Sakana / DGM style work requires archive diversity, genuine selection
  pressure, empirical validation, and sandbox or human oversight. PR #734 has a
  measurement skeleton but no live archive, mutation, selection loop, or real
  agent diversity.
- AlphaEvolve-style work makes objective evaluator quality the bottleneck. PR
  #734 has executable tests, which is directionally right, but the objective is
  tiny, synthetic, and hand-aligned with deterministic patchers.
- RE-Bench / SWE-Lancer / SWE-Bench Pro style evaluations emphasize realistic
  tasks, private or held-out task design, human calibration, contamination
  controls, and baselines. PR #734 currently has three local synthetic tasks and
  no human baseline.
- STOP / Godel Agent / GPTSwarm / Voyager style systems make feedback-loop and
  sandbox-bypass risks central. PR #734 avoids live self-modification, which is
  good, but its grader subprocess is not a hardened sandbox.
- Alignment-faking and preparedness-style concerns imply that promotion gates
  must be adversarially enforced, not merely reported by receipts. PR #734
  refuses promotion, but does not yet provide independent enforcement.
