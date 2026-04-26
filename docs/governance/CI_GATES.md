# CI Gates (dharma_swarm)

Phase 2 of the governance install adds three GitHub Actions workflows:

| Workflow | File | Triggers | Hard-fail? |
|---|---|---|---|
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

## Branch protection (manual setup)

These workflows only enforce gates if branch protection requires them.
**The repo owner must do this once, in the GitHub web UI**:

1. Repo → Settings → Branches → Add rule.
2. Branch name pattern: `main`. Repeat for `promote/**`.
3. Enable: "Require status checks to pass before merging".
4. Required checks: `tests`, `codeql`, `semgrep`, `gitleaks`.
5. Enable: "Do not allow bypassing the above settings" (off for solo
   to allow emergency override; on once collaborators exist).
6. Forbid force-push to `main`.

## Adding a workflow status badge

Once Phase 2 lands and the workflows have run at least once,
add status badges to `README.md`:

```markdown
[![tests](https://github.com/AmitabhainArunachala/dharma_swarm/actions/workflows/tests.yml/badge.svg)](https://github.com/AmitabhainArunachala/dharma_swarm/actions/workflows/tests.yml)
[![codeql](https://github.com/AmitabhainArunachala/dharma_swarm/actions/workflows/codeql.yml/badge.svg)](https://github.com/AmitabhainArunachala/dharma_swarm/actions/workflows/codeql.yml)
[![semgrep](https://github.com/AmitabhainArunachala/dharma_swarm/actions/workflows/semgrep.yml/badge.svg)](https://github.com/AmitabhainArunachala/dharma_swarm/actions/workflows/semgrep.yml)
[![gitleaks](https://github.com/AmitabhainArunachala/dharma_swarm/actions/workflows/gitleaks.yml/badge.svg)](https://github.com/AmitabhainArunachala/dharma_swarm/actions/workflows/gitleaks.yml)
```

Defer until after Phase 3 (CodeRabbit + Renovate land their own surfaces).

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
