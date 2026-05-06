# Semgrep SARIF Permission Hotfix

Date: 2026-04-27
Branch: `fix/semgrep-sarif-permissions`

## Problem

Latest `main` CI failed in the Semgrep workflow after the scan completed. The failing step was SARIF upload:

```text
Resource not accessible by integration
```

The workflow uses `github/codeql-action/upload-sarif@v3`, but its workflow-level permissions did not include `security-events: write`.

## Patch

Changed:

- `.github/workflows/semgrep.yml`

Added workflow permission:

```yaml
permissions:
  contents: read
  pull-requests: write
  security-events: write
```

No Semgrep rules were changed. No runtime, dashboard, or governance scan rule files were changed.

## Validation

Passed:

```bash
ruby -e "require 'yaml'; YAML.load_file('.github/workflows/semgrep.yml')"
python -c "import yaml; yaml.safe_load(open('.github/workflows/semgrep.yml'))"
```

Remote validation target:

- Open PR from `fix/semgrep-sarif-permissions`
- Confirm Semgrep workflow is green on the PR
