# AGENT ONLINE

Status: canonical agent onboarding node  
Owner: governance layer  
Last updated: 2026-05-11

This is the single pointer you can give any coding agent to get online with
repo hygiene, governance discipline, anti-slop policy, and review protocol.

If this file conflicts with other docs, precedence is:
1. `CLAUDE.md`
2. `docs/governance/SOVEREIGN_MANIFEST.md`
3. this file (`AGENT_ONLINE.md`)

## Mandatory Read Order

1. `CLAUDE.md`
2. `docs/governance/SOVEREIGN_MANIFEST.md`
3. `docs/governance/QUALITY_GATES.md`
4. `docs/governance/ANTI_SLOP_RULES.md`
5. `docs/governance/PRE_COMMIT.md`
6. `docs/governance/CI_GATES.md`
7. `docs/governance/PR_REVIEW.md`
8. `docs/governance/PROMPT_GOVERNANCE.md`
9. `INTERFACE_MISMATCH_MAP.md`

## Hard-Fail Hygiene Surfaces

- `.github/workflows/semgrep.yml` (strict local rules gate)
- `.github/workflows/structure.yml` (root markdown + guardian report policy)
- `.github/workflows/module-budget.yml` (line-budget gate)
- `.github/workflows/gitleaks.yml` (secrets)
- `.semgrep/dharma-anti-slop.yml` (anti-slop rule pack)

## Required Local Verification Commands

Run these before claiming completion:

```bash
python3 scripts/governance/check_agent_online.py
make precommit-run
make quality
python3 scripts/governance/route_quality_findings.py --all
```

If the task is small and `make quality` is too heavy, run at minimum:

```bash
python3 scripts/governance/check_test_hygiene.py
python3 scripts/governance/check_module_budget.py --base-ref origin/main --head-ref HEAD
```

## Prompt / Spec Discipline

- For non-trivial feature work, use a spec-first workflow (requirements ->
  clarify -> plan -> tasks -> implement).
- Spec flow does not override dharma governance; it runs inside these gates.
- No auto-merge, no auto-delete, no authority-surface mutation without review.

## Exemptions

- Exemptions are allowed only when documented in:
  - `docs/governance/ANTI_SLOP_RULES.md` (rule allowlists)
  - `.gitleaks.toml` (secrets false positives)
  - workflow-level allowlists in `.github/workflows/*.yml`
- Any bypass must include a concrete reason and follow-up action.

## Machine Surface

Machine-readable twin for this policy:

- `docs/governance/AGENT_ONLINE.yaml`

Integrity checker:

- `python3 scripts/governance/check_agent_online.py`
