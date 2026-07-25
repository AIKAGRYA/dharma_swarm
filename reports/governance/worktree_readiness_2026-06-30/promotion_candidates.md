# Promotion Candidates First Pass

Generated: 2026-06-30 JST
Scope: read-only assessment of seven named branches against current local `origin/main` (`bd121c827`).
Write constraint observed: only this receipt was written. Candidate branches were not checked out, edited, fetched, pushed, merged, or rebased.

## Global Coordination Notes

- Current primary worktree `/Users/dhyana/dharma_swarm` is dirty on `agent/magpie-seed`; this receipt was produced using ref-based git commands only.
- Candidate linked worktrees found:
  - `/private/tmp/ds_loop` -> `ratchet/loop-phases-1-3`, clean.
  - `/Users/dhyana/ds_forge_v1_scoreboard` -> `forge-v1/tokenbroker-scoreboard-20260620`, dirty WIP.
  - `/Users/dhyana/ds_supplychain_slice` -> `loop-closure/supplychain-bronze-20260620`, dirty WIP.
  - `/Users/dhyana/dharma_swarm_cashclaw` -> `cashclaw/revenue-hydra-v1`, dirty WIP.
  - `/Users/dhyana/dharma_swarm_slice_roast` -> `slice/roast-skill`, clean.
  - `/Users/dhyana/ds_semantic_commons_100` -> `codex/semantic-commons-livingdock-composer-100`, dirty WIP.
- Tests were not run in this first pass because the task explicitly restricted writes to this single file; even narrow pytest normally writes `.pytest_cache` / `__pycache__` and several candidate verifiers produce receipts. Exact next test commands are listed per candidate.

## Ranked Top Candidates

1. `slice/roast-skill` — disposition: `PR_NOW`. Tiny, clean, already has draft PR #716. Production value is moderate but readiness is highest. Needs CI rerun/fix for one recorded `pytest (3.11)` failure.
2. `ratchet/loop-phases-1-3` — disposition: `REBASE_FIRST`. Highest governance/production-readiness value, very well tested by branch-local tests, clean linked worktree. Needs rebase because it is 23 behind and based on semantic commons.
3. `loop-closure/supplychain-bronze-20260620` — disposition: `PRESERVE_WIP`. Small committed branch with clear full-chain verifier value, but remote tracking branch is gone and linked worktree has dirty follow-on WIP.
4. `origin/codex/pudgala-autopoiesis-protostar-20260626` — disposition: `REBASE_FIRST`. High anti-slop governance value and PR #704 exists with green checks in snapshot, but merge state was DIRTY and it overlaps heavily with main changes.
5. `forge-v1/tokenbroker-scoreboard-20260620` — disposition: `PRESERVE_WIP`. High strategic value but old, 212 behind, and linked worktree contains dirty/uncommitted v2/provider work. Promote only after isolating the offline scoreboard slice.
6. `cashclaw/revenue-hydra-v1` — disposition: `SPLIT_FIRST`. Potentially high revenue value, but the branch is enormous and artifact-heavy: 581 files / 471,444 insertions, with live action code requiring strict human gates.
7. `codex/semantic-commons-livingdock-composer-100` — disposition: `ARCHIVE_AFTER_APPROVAL`. Committed branch has no remaining `origin/main...branch` diff; its tip is already contained in `origin/main`. Preserve or triage linked-worktree WIP separately.

## 1. slice/roast-skill

Disposition: `PR_NOW`
Production value: Medium. Adds an anti-sycophancy `roast` skill for adversarial decision review before spend/build/launch decisions.
Readiness: High. Clean linked worktree; tiny diff; existing draft PR #716.
Conflict risk: Low to medium. Only shared overlap observed is `docs/docops/assertions.yaml`; PR snapshot says merge state `UNSTABLE`, with `pytest (3.11)` failure and `pytest (3.12)` success.

Verifier facts:

```text
git merge-base origin/main slice/roast-skill
50c8e2b7556258d80839e9860065dad488d855cc

git rev-list --left-right --count origin/main...slice/roast-skill
10	2

git status --short --branch  # in /Users/dhyana/dharma_swarm_slice_roast
## slice/roast-skill...origin/slice/roast-skill

git diff --stat origin/main...slice/roast-skill
 .warp/skills/roast/SKILL.md | 77 +++++++++++++++++++++++++++++++++++++++++++++
 docs/docops/assertions.yaml |  2 +-
 2 files changed, 78 insertions(+), 1 deletion(-)
```

Next commands:

```bash
git -C /Users/dhyana/dharma_swarm_slice_roast status --short --branch
git -C /Users/dhyana/dharma_swarm_slice_roast diff --check origin/main...slice/roast-skill
gh pr checks 716 --watch
python -m pytest -q --strict-markers
```

## 2. ratchet/loop-phases-1-3

Disposition: `REBASE_FIRST`
Production value: Very high. Adds cybernetic loop ratchet gates, deterministic audit pipeline stages, anti-gaming checks, warrant validation, CI wiring, and broad tests.
Readiness: Medium-high. Linked worktree is clean and branch has extensive tests, but it is 23 behind / 19 ahead and merge-base is `c53721d5f`, the semantic commons tip, so it depends on work now already in `origin/main`.
Conflict risk: Medium. Mostly additive, but `pyproject.toml` overlaps with main.

Verifier facts:

```text
git merge-base origin/main ratchet/loop-phases-1-3
c53721d5f8aa713db88b5647b06682fa8ea50e98

git rev-list --left-right --count origin/main...ratchet/loop-phases-1-3
23	19

git status --short --branch  # in /private/tmp/ds_loop
## ratchet/loop-phases-1-3...origin/main [ahead 19, behind 23]

git diff --stat origin/main...ratchet/loop-phases-1-3
 .github/workflows/loop-ratchet-gates.yml           |  83 ++
 OUTPUT_TEMPLATE.md                                 |  53 ++
 councils/01_testing_verification/PROMPTS.md        | 351 ++++++++
 councils/02_architecture_complexity/PROMPTS.md     | 299 +++++++
 .../03_runtime_distributed_reliability/PROMPTS.md  | 227 +++++
 councils/04_ai_slop_prompt_security/PROMPTS.md     | 229 +++++
 councils/05_governance_evidence_fitness/PROMPTS.md | 230 +++++
 pyproject.toml                                     |   7 +
 schemas/expert_audit_output.schema.json            |  82 ++
 scripts/governance/loop/__init__.py                |   1 +
 scripts/governance/loop/agent_backend.py           | 517 +++++++++++
 scripts/governance/loop/anti_gaming.py             | 296 +++++++
 scripts/governance/loop/councils.py                | 118 +++
 scripts/governance/loop/oracle.py                  | 243 ++++++
 scripts/governance/loop/prompt_audit_learn.py      | 716 +++++++++++++++
 scripts/governance/loop/prompt_audit_reaudit.py    | 666 ++++++++++++++
 scripts/governance/loop/prompt_audit_remediate.py  | 671 +++++++++++++++
 scripts/governance/loop/prompt_audit_run.py        | 172 ++++
 scripts/governance/loop/prompt_audit_triage.py     | 340 ++++++++
 scripts/governance/loop/runs.py                    | 395 +++++++++
 scripts/governance/loop/scoper.py                  | 296 +++++++
 scripts/governance/loop/validate_audit.py          | 136 +++
 scripts/governance/loop/warrant.py                 | 371 ++++++++
 scripts/governance/loop/wire_ci_gate.py            | 227 +++++
 tests/governance/loop/__init__.py                  |   1 +
 tests/governance/loop/test_agent_backend.py        | 176 ++++
 tests/governance/loop/test_agentized_e2e.py        | 542 ++++++++++++
 tests/governance/loop/test_anti_gaming.py          | 394 +++++++++
 tests/governance/loop/test_councils.py             | 132 +++
 tests/governance/loop/test_oracle.py               | 424 +++++++++
 tests/governance/loop/test_pipeline_e2e.py         | 955 +++++++++++++++++++++
 tests/governance/loop/test_prompt_audit_learn.py   | 604 +++++++++++++
 tests/governance/loop/test_prompt_audit_reaudit.py | 807 +++++++++++++++++
 .../governance/loop/test_prompt_audit_remediate.py | 861 +++++++++++++++++++
 tests/governance/loop/test_prompt_audit_run.py     | 397 +++++++++
 tests/governance/loop/test_prompt_audit_triage.py  | 595 +++++++++++++
 tests/governance/loop/test_runs.py                 | 376 ++++++++
 tests/governance/loop/test_scoper.py               | 293 +++++++
 .../governance/loop/test_scoper_glob_regression.py | 208 +++++
 tests/governance/loop/test_validate_audit.py       | 180 ++++
 tests/governance/loop/test_warrant.py              | 379 ++++++++
 tests/governance/loop/test_wire_ci_gate.py         | 316 +++++++
 42 files changed, 14366 insertions(+)
```

Next commands:

```bash
git -C /private/tmp/ds_loop status --short --branch
git -C /private/tmp/ds_loop rebase origin/main
PYTHONPATH=. python -m pytest -q tests/governance/loop --strict-markers
PYTHONPATH=. python scripts/governance/check_test_hygiene.py
PYTHONPATH=. python scripts/governance/hygiene/check_hygiene_integrity.py
```

## 3. loop-closure/supplychain-bronze-20260620

Disposition: `PRESERVE_WIP`
Production value: High. Adds `frontier_council.py` and closes bronze supply-chain intake into verifier/archive receipts with a full-chain test.
Readiness: Medium. Committed diff is small, but linked worktree is dirty and its upstream is gone.
Conflict risk: Medium. Overlap detected on `docs/ontology/semantic_objects.yaml`; worktree WIP modifies unrelated tests and governance receipts.

Verifier facts:

```text
git merge-base origin/main loop-closure/supplychain-bronze-20260620
64a9c2b36d435ac460ea29862851d913905c8682

git rev-list --left-right --count origin/main...loop-closure/supplychain-bronze-20260620
193	1

git status --short --branch  # in /Users/dhyana/ds_supplychain_slice
## loop-closure/supplychain-bronze-20260620...origin/loop-closure/supplychain-bronze-20260620 [gone]
 M reports/governance/active_track_evidence.json
 M reports/governance/active_track_evidence.md
 M reports/governance/track_portfolio.json
 M tests/test_canonical_replay.py
 M tests/test_constitutional_size_check.py
 M tests/test_ginko_evolution.py
 M tests/test_godel_claw_e2e.py
 M tests/test_organism_boot.py
 M tests/test_phase3_integration.py
?? reports/governance/track_acceptance_strength.json
?? reports/governance/track_acceptance_strength.md
?? reports/loop_closure/RETROSPECTIVE.md
?? scripts/governance/track_acceptance_strength_report.py
?? tests/test_track_acceptance_strength_report.py

git diff --stat origin/main...loop-closure/supplychain-bronze-20260620
 dharma_swarm/frontier_council.py                   | 358 +++++++++++++++++++++
 dharma_swarm/world_radar/cli.py                    |  29 ++
 docs/ontology/semantic_objects.yaml                |  28 ++
 ...NCE_SUPPLY_CHAIN_FULL_CHAIN_RECEIPT_20260620.md |  74 +++++
 tests/test_frontier_council_supply_chain.py        | 127 ++++++++
 5 files changed, 616 insertions(+)
```

Next commands:

```bash
git -C /Users/dhyana/ds_supplychain_slice status --short --branch
git -C /Users/dhyana/ds_supplychain_slice switch -c promote/supplychain-bronze-frontier-council
git -C /Users/dhyana/ds_supplychain_slice rebase origin/main
PYTHONPATH=. python -m pytest -q tests/test_frontier_council_supply_chain.py --strict-markers
```

## 4. codex/pudgala-autopoiesis-protostar-20260626

Disposition: `REBASE_FIRST`
Production value: High. Adds graded evidence gates, claim/evidence binding, mutation score gate, and anti-slop governance track machinery.
Readiness: Medium. Remote branch exists; no local branch. PR #704 exists and snapshot checks were green, but PR merge state was `DIRTY`.
Conflict risk: High. Since merge-base is semantic commons tip, nearly every touched file also changed on main; overlap includes `Makefile`, governance docs, `pyproject.toml`, active track evidence, governance scripts, and tests.

Verifier facts:

```text
git merge-base origin/main origin/codex/pudgala-autopoiesis-protostar-20260626
c53721d5f8aa713db88b5647b06682fa8ea50e98

git rev-list --left-right --count origin/main...origin/codex/pudgala-autopoiesis-protostar-20260626
23	1

git branch -r --list origin/codex/pudgala-autopoiesis-protostar-20260626
  origin/codex/pudgala-autopoiesis-protostar-20260626

git diff --stat origin/main...origin/codex/pudgala-autopoiesis-protostar-20260626
 Makefile                                           |  21 +-
 dharma_swarm/memory_kernel/writer_specs.py         |  10 +
 dharma_swarm/operator_core/runtime_truth.py        |  19 +
 dharma_swarm/spine/receipt.py                      | 127 +++++-
 docs/docops/AUTO_INVENTORY.md                      |  14 +-
 docs/docops/assertions.yaml                        |   1 +
 docs/governance/CANONICAL_DOC_STACK.md             |   1 +
 docs/governance/FORGE_NAMING_BOUNDARY.md           |  57 +++
 docs/governance/SOVEREIGN_MANIFEST.md              |  14 +-
 docs/governance/evidence_grades.yaml               | 143 +++++++
 docs/governance/hygiene/AUDIT_PROMPT.md            |   9 +
 docs/governance/hygiene/CATALOGUE.md               |   4 +
 docs/governance/hygiene/patterns/AI-M1.yaml        |  17 +
 ...slop-pudgala-autopoiesis-protostar-2026-06.yaml | 107 +++++
 pyproject.toml                                     |   7 +-
 reports/governance/active_track_evidence.json      | 463 ++++++++++++++-------
 reports/governance/active_track_evidence.md        |  24 +-
 reports/governance/track_portfolio.json            | 463 ++++++++++++++-------
 requirements-dev.txt                               |   1 +
 scripts/governance/check_claim_evidence_binding.py | 181 ++++++++
 scripts/governance/check_track_status.py           | 347 ++++++++++++++-
 scripts/governance/run_mutation_score.py           | 173 ++++++++
 .../governance/track_acceptance_strength_report.py |  32 +-
 scripts/workflows/antislop-evolve.js               | 248 +++++++++++
 tests/test_claim_evidence_binding.py               | 366 ++++++++++++++++
 tests/test_forge_naming_boundary.py                |  48 +++
 26 files changed, 2574 insertions(+), 323 deletions(-)
```

Next commands:

```bash
git -C /Users/dhyana/dharma_swarm fetch origin codex/pudgala-autopoiesis-protostar-20260626
git -C /Users/dhyana/dharma_swarm worktree add /Users/dhyana/worktrees/pudgala_rebase_20260630 origin/codex/pudgala-autopoiesis-protostar-20260626
git -C /Users/dhyana/worktrees/pudgala_rebase_20260630 switch -c promote/pudgala-autopoiesis-protostar-20260630
git -C /Users/dhyana/worktrees/pudgala_rebase_20260630 rebase origin/main
PYTHONPATH=. python -m pytest -q tests/test_claim_evidence_binding.py tests/test_forge_naming_boundary.py --strict-markers
PYTHONPATH=. python scripts/governance/check_claim_evidence_binding.py --warn-only
```

## 5. forge-v1/tokenbroker-scoreboard-20260620

Disposition: `PRESERVE_WIP`
Production value: Very high. Adds a Forge v1 scoreboard, TokenBroker equal-budget enforcement, sandbox verifier, best-of-N comparison, SWE-bench hooks, provider bridge, and RunPod runbook.
Readiness: Medium-low. Committed slice is mostly additive, but old and 212 behind; linked worktree has substantial dirty provider/model-pool/v2 work that must not be mixed into promotion.
Conflict risk: Low for committed files; high coordination risk because of active dirty worktree.

Verifier facts:

```text
git merge-base origin/main forge-v1/tokenbroker-scoreboard-20260620
86418541a99c265c09040b9bfc064625c6d59994

git rev-list --left-right --count origin/main...forge-v1/tokenbroker-scoreboard-20260620
212	9

git status --short --branch  # in /Users/dhyana/ds_forge_v1_scoreboard
## forge-v1/tokenbroker-scoreboard-20260620...origin/main [ahead 9, behind 212]
 M dharma_swarm/api_keys.py
 M dharma_swarm/evolution_roster.py
 M dharma_swarm/forge_v1/providers.py
 M dharma_swarm/forge_v1/run_real.py
 M dharma_swarm/key_oracle.py
 M dharma_swarm/model_defaults.py
 M dharma_swarm/model_hierarchy.py
 M dharma_swarm/model_pool.py
 M dharma_swarm/models.py
 M dharma_swarm/providers.py
 M dharma_swarm/runtime_provider.py
 M reports/governance/active_track_evidence.json
 M reports/governance/active_track_evidence.md
 M reports/governance/track_portfolio.json
 M scripts/load_runtime_env.sh
 M tests/test_api_keys.py
 M tests/test_env_alias_normalization.py
 M tests/test_forge_v1_providers.py
 M tests/test_model_pool.py
 M tests/test_providers_quality_track.py
 M tests/test_runtime_provider.py
?? dharma_swarm/forge_v1/autoloop.py
?? dharma_swarm/forge_v1/canonical.py
?? dharma_swarm/forge_v1/forge_v2/
?? tests/test_forge_v2.py
?? tests/test_forge_v2_critic.py

git diff --stat origin/main...forge-v1/tokenbroker-scoreboard-20260620
 dharma_swarm/forge_v1/__init__.py          |  30 ++
 dharma_swarm/forge_v1/coding_swarm.py      | 167 ++++++++
 dharma_swarm/forge_v1/coding_swarm_demo.py |  92 ++++
 dharma_swarm/forge_v1/demo.py              |  42 ++
 dharma_swarm/forge_v1/demo_full.py         |  64 +++
 dharma_swarm/forge_v1/evolution.py         | 100 +++++
 dharma_swarm/forge_v1/fixtures.py          |  47 +++
 dharma_swarm/forge_v1/harness.py           | 275 ++++++++++++
 dharma_swarm/forge_v1/models.py            |  48 +++
 dharma_swarm/forge_v1/providers.py         | 157 +++++++
 dharma_swarm/forge_v1/run_real.py          | 646 +++++++++++++++++++++++++++++
 dharma_swarm/forge_v1/smoke_live.py        |  48 +++
 dharma_swarm/forge_v1/smoke_swebench.py    |  83 ++++
 dharma_swarm/forge_v1/swarm.py             |  99 +++++
 dharma_swarm/forge_v1/swebench.py          | 154 +++++++
 dharma_swarm/forge_v1/swebench_real.py     | 248 +++++++++++
 dharma_swarm/forge_v1/tracking.py          |  72 ++++
 docs/RUNPOD_SWEBENCH_RUNBOOK.md            |  50 +++
 scripts/runpod_swebench_setup.sh           |  61 +++
 tests/test_forge_v1.py                     | 129 ++++++
 tests/test_forge_v1_full.py                |  89 ++++
 tests/test_forge_v1_providers.py           |  84 ++++
 tests/test_forge_v1_swarm_live.py          |  43 ++
 tests/test_forge_v1_swebench.py            | 102 +++++
 24 files changed, 2930 insertions(+)
```

Next commands:

```bash
git -C /Users/dhyana/ds_forge_v1_scoreboard status --short --branch
git -C /Users/dhyana/ds_forge_v1_scoreboard diff --stat
git -C /Users/dhyana/dharma_swarm worktree add /Users/dhyana/worktrees/forge_v1_scoreboard_promote_20260630 forge-v1/tokenbroker-scoreboard-20260620
git -C /Users/dhyana/worktrees/forge_v1_scoreboard_promote_20260630 rebase origin/main
PYTHONPATH=. python -m pytest -q tests/test_forge_v1.py tests/test_forge_v1_full.py tests/test_forge_v1_providers.py tests/test_forge_v1_swebench.py --strict-markers
```

## 6. cashclaw/revenue-hydra-v1

Disposition: `SPLIT_FIRST`
Production value: High but high-risk. Adds revenue scouting/intake, action gateway, claim tracking, hydra evolution, and human approval token gates.
Readiness: Low as a single promotion. The branch is huge and dominated by generated/run artifacts under `reports/revenue_wedge/evolution/*`. Linked worktree also has dirty WIP.
Conflict risk: Low path overlap on committed branch, but high review/security risk due action/PR/claim code and artifact volume.

Verifier facts:

```text
git merge-base origin/main cashclaw/revenue-hydra-v1
9362e4efe24278c95ebe9b5a6c50775385acd67c

git rev-list --left-right --count origin/main...cashclaw/revenue-hydra-v1
374	10

git status --short --branch  # in /Users/dhyana/dharma_swarm_cashclaw
## cashclaw/revenue-hydra-v1...origin/cashclaw/revenue-hydra-v1
 M dharma_swarm/claude_cli.py
?? reports/revenue_wedge/evolution/20260610T193223Z/
?? reports/revenue_wedge/evolution/20260611T073905Z/
?? reports/revenue_wedge/evolution/20260611T154212Z/
?? reports/revenue_wedge/evolution/20260611T194323Z/
?? reports/revenue_wedge/evolution/20260611T234419Z/
?? reports/revenue_wedge/evolution/20260612T034600Z/
?? reports/revenue_wedge/evolution/20260612T074726Z/
?? reports/revenue_wedge/evolution/20260612T155034Z/
?? reports/revenue_wedge/evolution/20260612T195220Z/
?? reports/revenue_wedge/evolution/20260613T035510Z/
?? reports/revenue_wedge/evolution/20260613T075727Z/
?? reports/revenue_wedge/evolution/20260613T115830Z/
?? reports/revenue_wedge/evolution/20260613T201327Z/
?? reports/revenue_wedge/evolution/20260614T001505Z/
?? reports/revenue_wedge/evolution/20260614T041649Z/
?? reports/revenue_wedge/evolution/20260614T081808Z/
?? reports/revenue_wedge/evolution/20260614T122148Z/

git diff --stat origin/main...cashclaw/revenue-hydra-v1
 dharma_swarm/revenue/action_gateway.py             |   467 +
 dharma_swarm/revenue/action_gateway_models.py      |   167 +
 dharma_swarm/revenue/cashclaw_autopilot.py         |  1399 +
 dharma_swarm/revenue/cashclaw_employees.py         |   390 +
 dharma_swarm/revenue/cashclaw_evolution.py         |   312 +
 dharma_swarm/revenue/idea_gauntlet.py              |   447 +
 dharma_swarm/revenue/live_intake.py                |   582 +
 dharma_swarm/revenue/live_intake_models.py         |   359 +
 dharma_swarm/revenue/live_intake_sources.json      |    83 +
 dharma_swarm/revenue/live_intake_sources.py        |   505 +
 scripts/revenue/cashclaw_breed_variants.py         |   143 +
 scripts/revenue/cashclaw_claim_and_do.py           |   460 +
 scripts/revenue/cashclaw_claim_tracker.py          |   143 +
 scripts/revenue/cashclaw_evolution_runner.py       |   195 +
 scripts/revenue/cashclaw_hydra_run_manifest.py     |   180 +
 scripts/revenue/cashclaw_hydra_watchdog.py         |   511 +
 scripts/revenue/cashclaw_lease_packet_quality_audit.py | 202 +
 scripts/revenue/cashclaw_live_intake.py            |    96 +
 scripts/revenue/cashclaw_local_executor_sidecar.py |   224 +
 scripts/revenue/cashclaw_multi_platform_scan.py    |   182 +
 scripts/revenue/cashclaw_revenue_hydra.py          |  1804 +
 scripts/revenue/cashclaw_v3_presence_digest.py     |   224 +
 scripts/revenue/dogfood_cashclaw_autopilot.py      |   637 +
 tests/test_cashclaw_action_gateway.py              |   420 +
 tests/test_cashclaw_autopilot.py                   |   386 +
 tests/test_cashclaw_dogfood.py                     |    53 +
 tests/test_cashclaw_evolution.py                   |   115 +
 tests/test_cashclaw_hydra_run_manifest.py          |    98 +
 tests/test_cashclaw_hydra_watchdog.py              |   275 +
 tests/test_cashclaw_lease_packet_quality_audit.py  |   132 +
 tests/test_cashclaw_live_intake.py                 |   608 +
 tests/test_cashclaw_local_executor_sidecar.py      |   113 +
 tests/test_cashclaw_revenue_hydra.py               |  1075 +
 ... plus many committed reports/revenue_wedge/evolution/* artifact files ...
 581 files changed, 471444 insertions(+)
```

Next commands:

```bash
git -C /Users/dhyana/dharma_swarm_cashclaw status --short --branch
git -C /Users/dhyana/dharma_swarm_cashclaw diff --stat
git -C /Users/dhyana/dharma_swarm worktree add /Users/dhyana/worktrees/cashclaw_gateway_promote_20260630 cashclaw/revenue-hydra-v1
git -C /Users/dhyana/worktrees/cashclaw_gateway_promote_20260630 rebase origin/main
PYTHONPATH=. python -m pytest -q tests/test_cashclaw_action_gateway.py tests/test_cashclaw_live_intake.py tests/test_cashclaw_revenue_hydra.py --strict-markers
```

Recommended split order:

1. Safety/action gateway plus tests only.
2. Live intake models/sources plus tests.
3. Hydra/evolution runtime without generated reports.
4. Generated receipt/archive data only if explicitly approved.

## 7. codex/semantic-commons-livingdock-composer-100

Disposition: `ARCHIVE_AFTER_APPROVAL`
Production value: Already realized in main for committed branch tip.
Readiness: Do not promote committed branch; `origin/main...branch` is empty. Linked worktree has dirty WIP that should become a new named branch if still desired.
Conflict risk: None for committed branch; high for linked WIP if recovered without splitting.

Verifier facts:

```text
git merge-base origin/main codex/semantic-commons-livingdock-composer-100
c53721d5f8aa713db88b5647b06682fa8ea50e98

git rev-list --left-right --count origin/main...codex/semantic-commons-livingdock-composer-100
23	0

git status --short --branch  # in /Users/dhyana/ds_semantic_commons_100
## codex/semantic-commons-livingdock-composer-100...origin/main [behind 23]
 M Makefile
 M dharma_swarm/fs_substrate/okf.py
 M dharma_swarm/persistent_agent.py
 M docs/ontology/semantic_aliases.yaml
 M docs/ontology/semantic_objects.yaml
 M reports/governance/active_track_evidence.json
 M reports/governance/active_track_evidence.md
 M reports/governance/track_portfolio.json
 M tests/test_okf_projection.py
?? dharma_swarm/living_dock_verifier.py
?? dharma_swarm/verify/d_score.py
?? docs/agents/codex_telos/
?? docs/agents/factory_droid/
?? docs/agents/operator_guide_cursor/
?? docs/agents/sarathi/
?? docs/architecture/AGENT_HIERARCHY_MATURITY_MAP.md
?? docs/architecture/APEX_HOLON_LONG_RUNNING_GOAL_SPEC.md
?? docs/ontology/pkm_projection.yaml
?? docs/ontology/retrieval_scope.yaml
?? docs/ontology/session_orientation.yaml
?? docs/ops/AGENT_ADMISSION.md
?? docs/plans/2026-06-26-semantic-commons-livingdock-codex-composer-100-goal-spec.md
?? docs/sovereign_holons/CODEX_COMPOSER_WAKE_LOOP.md
?? reports/agents/
?? reports/governance/semantic_commons_livingdock_codex_composer_scorecard_2026-06-26.md
?? scripts/governance/agent_admission.py
?? scripts/governance/agent_admission_projection.py
?? scripts/governance/d_score_verifier.py
?? scripts/governance/living_dock_verifier.py
?? scripts/governance/name_drift_preflight.py
?? scripts/runtime/codex_composer_wake_loop.py
?? tests/test_agent_admission.py
?? tests/test_codex_composer_wake_loop.py
?? tests/test_d_score_verifier.py
?? tests/test_living_dock_verifier.py
?? tests/test_name_drift_preflight.py
?? tests/test_semantic_commons.py
?? tests/test_semantic_commons_projection.py

git diff --stat origin/main...codex/semantic-commons-livingdock-composer-100
# no output
```

Next commands:

```bash
git -C /Users/dhyana/ds_semantic_commons_100 status --short --branch
git -C /Users/dhyana/ds_semantic_commons_100 diff --stat
git -C /Users/dhyana/ds_semantic_commons_100 ls-files --others --exclude-standard
```

If approved, archive the branch pointer after preserving or discarding WIP by explicit operator decision.
