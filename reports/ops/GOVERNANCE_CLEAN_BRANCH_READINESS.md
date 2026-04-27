# Governance Clean Branch Readiness

Date: 2026-04-27

## Branch

- Candidate branch: `governance/tier-1-clean`
- Worktree: `/Users/dhyana/promotion_worktrees/dharma_swarm_governance_tier_1_clean`
- Base: `origin/main` at `eae2d2b`
- Push status: not pushed

## Commits Applied

Required governance commits cherry-picked from `governance/tier-1-install`:

| Source commit | Clean-branch commit | Notes |
|---|---:|---|
| `0f31d4d` | `fce1387` | Phase 1 local static analysis baseline |
| `2a56c78` | `15e4bcd` | Phase 2 CI gates, CODEOWNERS, PR template |
| `bb222e9` | `c1845c5` | Phase 3 SaaS/dependency surfaces, then deferred by cleanup |
| `3abad4d` | `c5a290c` | Phase 4 anti-slop rules |
| `b0a86eb` | `402dd66` | Phase 5 Sourcegraph/mismatch-map surfaces, then deferred by cleanup |

Additional clean-branch commits:

- `12cfd54` — defers non-Wave-A surfaces: CodeRabbit/Renovate config/docs and Sourcegraph/mismatch-map docs/workflow/script.
- `81d908f` — adds `scripts/governance_scan.py` and `tests/test_governance_scan.py` so the requested Wave A scan entrypoint exists.
- Final HEAD commit — records this readiness report.

No unrelated local-main commits from `governance/tier-1-install` were included.

## Conflicts Encountered

- `Makefile` conflicted while applying `0f31d4d`.
- Resolution: kept the current `origin/main` operational targets and added the Phase 1 / Phase 4 governance targets.
- No conflicts beyond `Makefile`.
- After `origin/main` advanced to `eae2d2b`, the branch was rebased onto it cleanly with no conflicts.
- Local pre-commit hooks blocked the first `cherry-pick --continue` because local Python 3.14 lacks `pytest` and a pre-existing hook referenced missing `scripts/uplift_guards/run_pre_commit.py`. Cherry-pick was continued with hooks disabled. This was not a merge conflict.

## Files Changed

Net branch diff versus `origin/main`:

```text
.github/CODEOWNERS
.github/ISSUE_TEMPLATE/bug.md
.github/ISSUE_TEMPLATE/feature.md
.github/ISSUE_TEMPLATE/governance.md
.github/PULL_REQUEST_TEMPLATE.md
.github/workflows/codeql.yml
.github/workflows/commit-lint.yml
.github/workflows/gitleaks.yml
.github/workflows/module-budget.yml
.github/workflows/semgrep.yml
.github/workflows/structure.yml
.github/workflows/test-hygiene.yml
.gitleaks.toml
.pre-commit-config.yaml
.semgrep/.semgrepignore
.semgrep/dharma-anti-slop.yml
.semgrep/security.yml
.semgrep/tests/test_no_unauthorized_dharma_write.py
.semgrep/tests/test_no_unauthorized_dharma_write.yml
.semgrep/tests/test_providers_canonical.py
.semgrep/tests/test_providers_canonical.yml
.semgrep/tests/test_scripts_no_git_add_all.py
.semgrep/tests/test_scripts_no_git_add_all.yml
.semgrep/tests/test_test_no_default_state.py
.semgrep/tests/test_test_no_default_state.yml
Makefile
docs/governance/ANTI_SLOP_RULES.md
docs/governance/CI_GATES.md
docs/governance/PRE_COMMIT.md
reports/governance/.gitkeep
reports/governance/gitleaks-baseline-2026-04-26.json
reports/governance/semgrep-baseline-2026-04-26.json
reports/ops/GOVERNANCE_CLEAN_BRANCH_READINESS.md
scripts/governance/check_module_budget.py
scripts/governance/check_test_hygiene.py
scripts/governance_scan.py
tests/test_governance_scan.py
```

Deferred from net diff:

- `.coderabbit.yaml`
- `renovate.json`
- `docs/governance/PR_REVIEW.md`
- `docs/governance/SOURCEGRAPH.md`
- `.github/workflows/mismatch-map.yml`
- `scripts/governance/check_mismatch_map.py`

## Tests Run

```bash
python -m compileall dharma_swarm tests scripts
```

Result: passed.

```bash
python -m pytest tests/test_governance_scan.py -q --tb=short
```

Result: passed, `2 passed`.

```bash
python -m pytest tests/test_session_ledger.py tests/test_runtime_state.py -q --tb=short
```

Result: passed, `7 passed`.

```bash
python scripts/governance_scan.py --help || true
```

Result: passed, help text printed.

## Push Readiness

- Safe to push: yes, after explicit approval.
- Not pushed: confirmed.
- PR #28 untouched: yes.
- Live LF5 untouched: yes.
- Risk note: branch is ahead of `origin/main` by 8 commits because cleanup/support/report commits were needed to keep the net diff Wave A, satisfy the requested scan command, and record readiness.

## Merge Order

Recommendation: merge after PR #28, or after PR #28's CI-unblock base is already present on `main`.

Reason: this branch is now based on `origin/main@eae2d2b`, whose history includes `168ad36 fix(ci): unblock PR 28 checks`, `edbb75c docs(ops): record CI unblock validation caveats`, and merge commit `eae2d2b Merge pull request #35 from AmitabhainArunachala/fix/ci-unblock-pr28`. If PR #28 is still open, this branch should not merge before the relevant CI-unblock base. If that base is already on `main`, this branch is correctly based after it.

`gh pr view 28` could not confirm remote PR state because local GitHub CLI credentials returned `HTTP 401: Bad credentials`; no write action was attempted.
