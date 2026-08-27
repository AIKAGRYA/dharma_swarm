# Python 3.13 required-check cutover

Do this **after** `pytest (3.13)` is green on `main` (this expand PR merged).

Do **not** drop `pytest (3.11)` / `pytest (3.12)` from YAML until GitHub
already requires `pytest (3.13)` and no longer requires the old names.
Otherwise merge queue waits forever.

## 1. Promote 3.13 (GitHub still also requires 3.11/3.12)

Add `pytest (3.13)` to:

- branch protection required contexts
- ruleset `main-merge-gate` (`20024481`) `required_status_checks`

Move `tests_py313` from `advisory` to `required` in
`docs/governance/CI_TRUTH_CONTRACT.json` and add it to
`scripts/governance/ci_parity_manifest.json` in the **same** commit.

## 2. Shrink (after a green week on three names)

1. GitHub: required contexts become `pytest (3.13)` only (drop 3.11/3.12).
2. Same commit: matrix `["3.13"]`, contract/manifest match, `requires-python = ">=3.13"`.
3. Rebuild `dharma_releases/*_runtime` venv on 3.13 **before** switching launchd.
   Live swarm today is 3.12.13; do not point the plist at 3.13 until that runtime smokes.

CLI `dgc` is a separate switch from the launchd daemon.
