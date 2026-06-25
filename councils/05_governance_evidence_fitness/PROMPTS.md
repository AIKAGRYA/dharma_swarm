# Council 05: Governance, Evidence, and Fitness Prompts

Council ID: `governance_evidence_fitness`

Use these prompts to audit architectural fitness functions, ratchets, baselines,
evidence grading, claim/evidence binding, active-track truth, conformance tests,
hygiene promotion, authority boundaries, and weekly governance.

## Shared Prompt Contract

```text
Work from /Users/dhyana/dharma_swarm. Audit only. Do not edit files.

Cite file paths plus line refs or command output for every claim. Grade each
finding PROVEN, PARTIAL, or UNPROVEN. List commands run. Do not mutate the repo
unless a separate operator task explicitly authorizes implementation.
```

## Prompt GEF-01: Architectural Fitness Function Audit

Expert lens: evolutionary architecture and cybernetic control systems.

Mandatory commands:

```bash
rg -n "fitness|score|threshold|vital_signs|score_gate|GateResult" dharma_swarm scripts tests docs/governance ACTIVE_SURFACE_MANIFEST.yaml
python3 scripts/governance/spine_bypass_report.py
python -m pytest -q tests/test_ecosystem_bridge.py tests/test_phase3_integration.py tests/test_organism_closure_v0.py --tb=line
```

Failure classes:

- `PROSE_ONLY_FITNESS`
- `DETACHED_SCORER`
- `NO_NEGATIVE_TEST`
- `METRIC_NOT_BOUND_TO_GATE`

Required output: fitness-function registry and executable coverage gap.

## Prompt GEF-02: Governance Ratchet and Regression Gate Audit

Expert lens: release engineering and SRE quality gates.

Mandatory commands:

```bash
rg -n "ratchet|baseline|threshold|grandfather|score_gate|regress|fail.*delta" Makefile scripts tests docs/governance
python3 scripts/governance/check_module_budget.py --base-ref origin/main --head-ref HEAD
python -m pytest -q tests/test_runtime_receipt_coverage_report.py tests/test_dogma_gate.py --tb=line
```

Failure classes:

- `WARNING_ONLY_RATCHET`
- `MOVABLE_BASELINE`
- `GRANDFATHER_CREEP`
- `MISSING_FAILURE_FIXTURE`

Required output: ratchet table, fail-open surfaces, and one fail-closed pytest.

## Prompt GEF-03: Baseline Freshness and Drift Audit

Expert lens: measurement systems auditor.

Mandatory commands:

```bash
ls -lt docs/governance/hygiene/baselines reports/governance
python3 scripts/governance/hygiene/scan.py --output /tmp/dharma-hygiene-audit.txt
make hygiene-check
rg -n "baseline|last_verified|next_review|ttl_days|verified_at" docs/governance scripts tests
```

Failure classes:

- `STALE_BASELINE`
- `INCOMPARABLE_SCAN`
- `GENERATED_DOC_DRIFT`
- `NO_REVIEW_CADENCE`

Required output: baseline age map and drift-control proposal.

## Prompt GEF-04: Evidence Grading Calibration Audit

Expert lens: epistemic QA and model-evaluation reviewer.

Mandatory commands:

```bash
rg -n "PROVEN|PARTIAL|NOT PROVEN|confidence|grade|evidence_count|DogmaDrift|GateResult" dharma_swarm scripts tests docs
python -m pytest -q tests/test_dogma_gate.py tests/test_runtime_contract.py tests/test_runtime_truth_closeout.py --tb=line
```

Failure classes:

- `CONFIDENCE_INFLATION`
- `NO_COUNTEREVIDENCE_PATH`
- `UNCALIBRATED_GRADE`
- `SUCCESS_WITHOUT_FRESH_EVIDENCE`

Required output: evidence-grade calibration table.

## Prompt GEF-05: Claim/Evidence Binding and Replay Audit

Expert lens: forensic systems auditor.

Mandatory commands:

```bash
rg -n "claim|evidence_refs|evidence_links|receipt_id|correlation_id|replay_command|artifact_refs|idempotency" dharma_swarm tests scripts docs
python -m pytest -q tests/test_organism_closure_v0.py tests/test_dharma_corpus.py tests/test_runtime_receipt_coverage_report.py --tb=line
```

Failure classes:

- `ORPHAN_CLAIM`
- `ORPHAN_RECEIPT`
- `WEAK_CORRELATION`
- `GENERATED_PROSE_AS_EVIDENCE`

Required output: claim-to-evidence graph and replay gaps.

## Prompt GEF-06: Active-Track Truth and Portfolio Graph Audit

Expert lens: governance control and portfolio integrity.

Mandatory commands:

```bash
python3 scripts/governance/check_track_status.py
python3 scripts/governance/check_track_status.py --warn-only
make onboard
rg -n "ACTIVE_TRACK|active_tracks|SHIPPABLE|closed_tracks|operator lifecycle|owned_surfaces|conflicts_with" docs/governance scripts tests CLAUDE.md
```

Failure classes:

- `STALE_VERIFIED_AT`
- `TTL_BREACH`
- `ACTIVE_ACTIVE_CONFLICT`
- `AGENT_CLOSED_LIFECYCLE`

Required output: track truth table with evidence age and authority boundary.

## Prompt GEF-07: Governance Conformance Test Coverage Audit

Expert lens: contract testing and compliance engineering.

Mandatory commands:

```bash
rg -n "governance-all|test-hygiene|test-contracts|nats-substrate-contract|runtime-truth-ci|hygiene-check" Makefile .github scripts tests
make test-hygiene
make hygiene-check
python -m pytest -q tests/test_contracts_scaffold.py tests/test_operator_core_contracts.py tests/test_runtime_contract.py tests/test_runtime_contract_adapters.py --tb=line
```

Failure classes:

- `GATE_ABSENT_FROM_CI`
- `SMOKE_ONLY_CHECK`
- `INVARIANT_NOT_ASSERTED`
- `NO_RED_CASE_FIXTURE`

Required output: conformance map from invariant to test to CI.

## Prompt GEF-08: Hygiene Lifecycle Promotion Audit

Expert lens: secure SDLC and anti-slop governance reviewer.

Mandatory commands:

```bash
python3 scripts/governance/hygiene/check_hygiene_integrity.py
python3 scripts/governance/hygiene/promote.py --help
rg -n "stage:|severity:|detector:|enforcement:|last_verified|next_review|rollback" docs/governance/hygiene
python3 scripts/governance/hygiene/scan.py --pattern AI-G1 --output /tmp/hygiene-AI-G1.txt
```

Failure classes:

- `ENFORCED_WITHOUT_RULE`
- `PREMATURE_PROMOTION`
- `FLAKY_DETECTOR`
- `ARCHIVED_ID_NOT_PRESERVED`

Required output: lifecycle promotion readiness table.

## Prompt GEF-09: Governance Authority Boundary Audit

Expert lens: source-of-truth architecture and runtime-truth reviewer.

Mandatory commands:

```bash
rg -n "source of truth|SSoT|projection|read model|authority|receipt|archive_fitness_mutation|production_closure_claim" docs dharma_swarm scripts ACTIVE_SURFACE_MANIFEST.yaml
python -m pytest -q tests/test_runtime_truth_closeout.py tests/test_operator_core_contracts.py tests/test_spine_persistence_invariant.py --tb=line
```

Failure classes:

- `PROJECTION_BECOMES_AUTHORITY`
- `DUPLICATE_TRUTH_STORE`
- `INTERNAL_ARTIFACT_MUTATES_ARCHIVE_FITNESS`
- `PRODUCTION_CLAIM_WITHOUT_RECEIPT`

Required output: authority/projection boundary map.

## Prompt GEF-10: Weekly Governance Review Packet Audit

Expert lens: chief-of-staff operations and governance reviewer.

Mandatory commands:

```bash
python3 scripts/governance/repo_status.py
python3 scripts/governance/pr_ci_health.py --dry-run --json
git log --since="7 days ago" --oneline -- docs/governance scripts/governance tests .github
rg -n "WARN|ERROR|BLOCKED|stale|TODO|FIXME" reports docs/state docs/governance
```

Failure classes:

- `NO_WEEKLY_ARTIFACT`
- `UNRESOLVED_WARNING_AGING_OUT`
- `PR_HEALTH_NOT_ROUTED`
- `BLOCKER_LACKS_OWNER`

Required output: weekly governance packet with next owner/action for every high
risk.
