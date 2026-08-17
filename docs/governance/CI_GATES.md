# CI Gates (dharma_swarm)

Phase 2 of the governance install adds three GitHub Actions workflows:

| Workflow | File | Triggers | Hard-fail? |
|---|---|---|---|
| Fourfold Shakti Warrant | `.github/workflows/fourfold-warrant.yml` | PRs to main/promote/governance/codex | Yes on BLOCK/HOLD; WARN is surfaced but non-blocking |
| CodeQL | `.github/workflows/codeql.yml` | PRs to main/promote/governance, weekly schedule | No (observe-only first 2 weeks) |
| Semgrep | `.github/workflows/semgrep.yml` | PRs, push to main, weekly schedule | Yes on local `.semgrep/` ERRORs; advisory on registry packs |
| Gitleaks | `.github/workflows/gitleaks.yml` | Push and PR | Yes on any finding |

The existing `tests.yml` workflow is untouched.

## What each gate does

### CodeQL
GitHub's semantic security scanner. Runs `security-extended` queries on
Python. Findings go to the **Security** tab (Code scanning alerts).
We do **not** fail the build on findings during the first observation
window; ratchet to fail-on-high in a follow-up PR after triaging the
baseline.

### Fourfold Shakti Warrant
Runs `scripts/governance/check_shakti_warrant.py` against the PR diff using
`--diff-scope base` and the pull request base SHA. The check hard-fails on
BLOCK or HOLD verdicts and allows WARN so teams can see weak evidence without
turning every thin dimension into a merge blocker.

The workflow writes both text and JSON warrant artifacts under
`reports/governance/fourfold-warrant.*` and appends the text report to the
GitHub Step Summary. Hot-path diffs require explicit impact acknowledgement:
include `[impact-checked]` in the PR title or body when the blast radius has
actually been reviewed.

### Semgrep
Two modes:
1. **Advisory pass** — runs `.semgrep/` + Semgrep registry packs
   (`p/python`, `p/owasp-top-ten`, `p/security-audit`), uploads SARIF
   to the Security tab. Does not fail.
2. **Strict pass** — runs only `.semgrep/` (our owned rules) with
   `--error`. Any ERROR-severity finding fails the build.

### Gitleaks
Scans full git history (`fetch-depth: 0`). Any finding fails the build.
Allowlists live in `.gitleaks.toml` (committed at repo root).

## Branch protection

Branch-protection changes are intentionally deferred from this Wave A
branch because they require repo-owner web UI action. This branch only
adds the workflow files and review metadata needed for later activation.

## Adding a workflow status badge

Once Phase 2 lands and the workflows have run at least once,
add status badges to `README.md`:

```markdown
[![tests](https://github.com/AIKAGRYA/dharma_swarm/actions/workflows/tests.yml/badge.svg)](https://github.com/AIKAGRYA/dharma_swarm/actions/workflows/tests.yml)
[![codeql](https://github.com/AIKAGRYA/dharma_swarm/actions/workflows/codeql.yml/badge.svg)](https://github.com/AIKAGRYA/dharma_swarm/actions/workflows/codeql.yml)
[![semgrep](https://github.com/AIKAGRYA/dharma_swarm/actions/workflows/semgrep.yml/badge.svg)](https://github.com/AIKAGRYA/dharma_swarm/actions/workflows/semgrep.yml)
[![gitleaks](https://github.com/AIKAGRYA/dharma_swarm/actions/workflows/gitleaks.yml/badge.svg)](https://github.com/AIKAGRYA/dharma_swarm/actions/workflows/gitleaks.yml)
[![fourfold-warrant](https://github.com/AIKAGRYA/dharma_swarm/actions/workflows/fourfold-warrant.yml/badge.svg)](https://github.com/AIKAGRYA/dharma_swarm/actions/workflows/fourfold-warrant.yml)
```

Defer badge additions until the workflows have run cleanly on `main`.

## Troubleshooting

**A workflow is failing on a known false positive.**
Update the local config (`.gitleaks.toml` allowlist, `.semgrep/`
exclude path, etc.) — never disable the workflow itself.

**Semgrep registry packs flag noise we don't want.**
Lower the registry-pack severity to advisory by removing them from
the `Run Semgrep CI` step's `--config`. The strict gate uses only
`.semgrep/` so registry-pack noise won't block PRs.

**CodeQL scanning takes too long.**
Cap `paths-ignore` in `.github/workflows/codeql.yml` more aggressively.
30 minutes is the workflow's hard timeout; if reached, prune scan paths.

## Promotion to fail-fast

After ~2 weeks of observation:

1. Triage CodeQL findings in the Security tab. Fix or allowlist.
2. Promote CodeQL to fail-on-high by setting
   `actions/upload-sarif` `wait-for-processing: true` and adding a
   downstream step that exits non-zero on `error`-severity findings.
3. Promote registry Semgrep packs to fail mode if findings stayed flat.
4. Phase 4 promotes the dharma anti-slop rules to ERROR locally; CI
   has them at ERROR already via the strict-gate step.
