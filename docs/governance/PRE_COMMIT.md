# Pre-commit Hooks (dharma_swarm)

dharma_swarm currently runs pre-commit safety through test hygiene, gitleaks,
semgrep, and generic file hygiene hooks. Legacy uplift guards are deferred until
their entrypoint is promoted back into `.pre-commit-config.yaml`.

1. **`scripts/governance/check_test_hygiene.py`** — local test hygiene guard
   for known test anti-patterns.
2. **`gitleaks`** — secret-scan staged content with allowlists tuned
   for the dharma_swarm false-positive surface (see `.gitleaks.toml`).
3. **`semgrep`** — `.semgrep/` rules: a curated security pack plus
   the dharma anti-slop rules (Phase 4 expands these).

A few hygiene hooks (trailing whitespace, EOF newline, large-file guard,
YAML/TOML syntax) round out the chain.

## Install

```bash
make precommit-install
# or:  pre-commit install --install-hooks
```

This writes `.git/hooks/pre-commit` and downloads pinned hook
implementations into `~/.cache/pre-commit/`.

## Run on demand

```bash
make precommit-run                        # all files
pre-commit run --files path/to/changed.py # specific files
pre-commit run gitleaks --all-files       # specific hook
```

## Capture or refresh baselines

```bash
make governance-baseline
```

Writes `reports/governance/{semgrep,gitleaks}-baseline.json`.
Commit baseline JSON only when intentional, e.g. after
addressing all real findings and the remaining set is allowlisted.

## Bypass (rare, with justification)

```bash
SKIP=semgrep git commit -m "msg

Skipping semgrep: refactor staged in pieces; full scan in follow-up PR."
```

Acceptable bypass reasons:

- Hot-fix where the incident-response PR needs to land before all
  rules pass; follow-up PR closes the gap within 24 hours.
- Mass file rename / move where individual rules can't disambiguate.
- Tool failure on the CI runner that the local hook reproduces.

Avoid bypassing configured security hooks without a written justification in the
commit message. If uplift guards are restored in a later commit, update this
document and the bypass policy in the same PR.

## When a new false positive appears

For gitleaks, edit `.gitleaks.toml`:

- Prefer the **shortest possible** path or regex allowlist that
  covers the false positive.
- Document the reason inline (one-line comment above the entry).
- Re-run `make gitleaks` and confirm the noise drops.

For semgrep, prefer adjusting the rule's `paths.exclude` or adding a
`metavariable-pattern` over inline `# nosemgrep`. Inline suppressions
should be a last resort and must include a `reason=` justification.

## Phase 1 baseline (2026-04-26)

- **semgrep**: 416 findings — 412 are the proof-of-life
  `print()`-in-runtime warning (replaced in Phase 4); 3 `subprocess shell=True`
  and 1 `eval/exec` are real and tracked in `reports/governance/`.
- **gitleaks**: 0 findings after allowlist tuning. The 23 raw matches were
  all false positives (class names matching token regex, test fixtures with
  documented fake tokens, old `.dharma_psmv_hyperfile_branch*` log dumps).

## Cleanup follow-ups (open as governance issues)

- **`.dharma_psmv_hyperfile_branch{,_v2}/`**: committed log artifacts
  that should be removed from the repo. Currently allowlisted in
  `.gitleaks.toml`; once removed, that allowlist line can be deleted.
- **3 `subprocess shell=True` sites + 1 `eval/exec` site**: real
  semgrep findings tracked separately, fix in their own micro-PRs
  before Phase 4 hard-fails the rules.
