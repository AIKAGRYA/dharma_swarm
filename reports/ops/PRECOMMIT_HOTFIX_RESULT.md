# Pre-commit Missing Hook Hotfix Result

## Scope

Branch: `fix/precommit-missing-hooks`

Issue: `#31 Tooling pre-commit env mismatch / missing hook refs`

This hotfix only changes local pre-commit wiring. It does not touch runtime code,
dashboard code, provider/routing code, LF5, or live state.

## Changed Files

- `.pre-commit-config.yaml`
- `reports/ops/PRECOMMIT_HOTFIX_RESULT.md`

## Root Cause

Fresh `origin/main` contained pre-commit hooks that referenced files which are
not present on `main`:

- `tests/test_contracts.py`
- `tests/test_private_access.py`
- `scripts/uplift_guards/run_pre_commit.py`

Because the two hooks were marked `always_run: true`, local commits could fail
before reaching the active governance hooks.

## Patch

- Removed the two missing legacy hooks from `.pre-commit-config.yaml`.
- Documented the deferred hook entrypoints in the config header so they can be
  restored only after the referenced files are actually promoted.
- Kept the active governance hooks:
  - `dharma-test-hygiene`
  - `gitleaks`
  - `semgrep-local`
  - standard pre-commit hygiene hooks
- Made `semgrep-local` match its existing comment and local Phase 1 policy by
  running in warn-only mode:

```yaml
entry: bash -c 'semgrep --config .semgrep --quiet --metrics=off || true'
```

This is not a new weakening of an enforcing gate: the hook was already documented
as "warn-only in Phase 1" because CI owns strict Semgrep enforcement.

## Validation

YAML parse:

```bash
python -c "import pathlib, yaml; yaml.safe_load(pathlib.Path('.pre-commit-config.yaml').read_text())"
```

Result: passed.

Compileall:

```bash
python -m compileall dharma_swarm tests scripts
```

Result: passed.

Governance scan tests:

```bash
python -m pytest tests/test_governance_scan.py -q --tb=short
```

Result: `2 passed, 1 warning`.

Pre-commit missing-reference verification:

```bash
pre-commit run --all-files
```

Result: no failure from missing `tests/test_contracts.py`,
`tests/test_private_access.py`, or `scripts/uplift_guards/run_pre_commit.py`.
The run did surface an unrelated existing repository hygiene issue: the generic
`trailing-whitespace` and `end-of-file-fixer` hooks rewrote many legacy files on
`main`. Those out-of-scope rewrites were reverted.

Non-mutating pre-commit verification:

```bash
SKIP=trailing-whitespace,end-of-file-fixer pre-commit run --all-files
```

Result: passed.

## Remaining Risk

`pre-commit run --all-files` still performs a broad whitespace/EOF formatter
sweep against existing files on `main`. That is unrelated to the missing hook
references and should be handled as a separate repository hygiene cleanup if the
team wants all-files pre-commit to be clean without skips.

## PR Recommendation

Merge this hotfix before asking contributors to rely on local pre-commit from a
fresh `origin/main` checkout. After merge, restore the deferred legacy hooks only
in the same PR that promotes their actual files.
