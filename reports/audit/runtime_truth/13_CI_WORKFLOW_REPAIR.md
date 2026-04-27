# 13_CI_WORKFLOW_REPAIR

## Scope

Branch: `fix/ci-tests-yaml`

Base: `origin/main` at `da6a4fad8fae677627449e190880839b59e1e3a3`

Goal: restore GitHub Actions check registration by fixing YAML validity only.

## Files Changed

- `.github/workflows/tests.yml`
- `reports/audit/runtime_truth/13_CI_WORKFLOW_REPAIR.md`

## Finding

`.github/workflows/tests.yml` was not valid YAML. The inline Python block in the `gauntlet-tier1` job was not indented under the `run: |` scalar, so YAML parsers treated `import asyncio, json, sys` as a top-level simple key and failed with:

`could not find expected ':'`

## Repair

Indented the inline Python block under the existing `run: |` section.

No workflow jobs were added or removed. No governance/tier-1 install logic was imported. No runtime code was touched.

## Validation

Local YAML parser checks passed:

- `python -c "import yaml, pathlib; yaml.safe_load(pathlib.Path('.github/workflows/tests.yml').read_text()); print('pyyaml ok')"`
- `ruby -e "require 'yaml'; YAML.load_file('.github/workflows/tests.yml'); puts 'ruby yaml ok'"`

`actionlint` and `yq` were not available locally.

## Deferred

Semgrep, Gitleaks, CodeQL, and broader CI hardening are intentionally deferred. This branch fixes only the workflow YAML validity needed for GitHub Actions to register checks again.

