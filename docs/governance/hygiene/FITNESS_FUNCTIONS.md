# Governance Fitness Functions

This registry lists executable architecture invariants that must stay coupled
to the codebase. A fitness function is not advisory prose: it has an executable
owner, local test coverage, and CI wiring.

| ID | Name | Scope | Trigger | Local check | CI owner | Classification | Status |
|---|---|---|---|---|---|---|---|
| QL-R1 | Quality ratchet regression | Repo-wide quality counters in `docs/governance/hygiene/ratchet_baselines.json` | Pull request, merge group, push to main, local pytest | `tests/conformance/test_repo_ratchet_holds.py` | `.github/workflows/quality-ratchet.yml` | Holistic, continuous, fail-closed | Enforced; current main has raw-LOC drift awaiting adjudication |

## QL-R1 Promotion

QL-R1 is the Leveson feedback edge for the hygiene ratchet. The ratchet engine
was already fail-closed; this promotion makes the check continuous by running
the same invariant in CI and in pytest.

Blocking command:

```bash
python3 scripts/governance/hygiene/ratchet.py --json
```

Local conformance test:

```bash
python3 -m pytest -q tests/conformance/test_repo_ratchet_holds.py
```

The conformance test intentionally fails on any regressed counter. Do not edit
`ratchet_baselines.json` to make it pass unless the loosened bound is reviewed
as a governance decision and recorded with the reason.
