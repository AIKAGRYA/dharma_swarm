# 08_HOOK_ENV_GAP

## Facts

- The commit hook invoked `/opt/homebrew/opt/python@3.14/bin/python3.14`.
- That interpreter did not have `pytest` installed.
- `pre-commit` reported no config.
- Slice 1 was committed with `--no-verify` only after `compileall` and targeted `pytest` passed.

## Governance Decision

This is a local hook/tooling environment gap, not a Slice 2 runtime-spine issue.

Fix it later in a dedicated CI/tooling branch. Do not spend Slice 2 budget repairing hook configuration or local Python environment drift.
