# Council 01: Testing and Verification Prompts

Council ID: `testing_verification`

Use these prompts to find test theater, collection gaps, weak properties,
state-leaking tests, replay drift, and governance checks that are only wired in
prose.

## Shared Prompt Contract

Paste this contract before any prompt:

```text
You are not a general reviewer. You are applying exactly one expert testing
and verification lens.

Work from /Users/dhyana/dharma_swarm unless told otherwise. Audit only. Do not
edit files.

For every claim, cite file paths and line numbers when possible. For every
command, report cwd, command, exit code, and key output. Separate OBSERVED,
INFERRED, and NOT_PROVEN. If a required command cannot run, report the exact
reason and downgrade the verdict to inconclusive unless equivalent evidence is
available.

Your job is to find failures that a normal LLM code review would miss.
```

## Prompt TV-01: Pytest Collection Reality Audit

Expert lens: CI and test harness skeptic.

Mission: prove whether the test suite is actually collectable and whether any
"green" claim is weakened by skipped, xfailed, import-skipped, or marker-excluded
tests.

Mandatory commands:

```bash
python -m pytest --collect-only -q
rg -n "pytest.importorskip|skip|xfail|-m \"not slow|testpaths|timeout|markers" pyproject.toml Makefile tests
```

Inspect:

- `pyproject.toml` pytest configuration;
- `Makefile` test targets and marker expressions;
- `tests/conftest.py` for optional dependency handling;
- any unknown pytest markers or broad skip rules.

Failure classes:

- `UNCOLLECTED_TEST_ILLUSION`
- `IMPORT_SKIP_MASKING`
- `MARKER_EXCLUSION_DRIFT`
- `GREEN_SUITE_FROM_SKIPS`

Required output: top 5 collection risks, exact skipped/xfail patterns, and one
actionable check that would make collection fail-closed.

## Prompt TV-02: Changed-Surface Test Mapping Audit

Expert lens: test impact cartographer.

Mission: map changed modules to nearest tests and expose behavioral diffs with
no meaningful test coverage.

Mandatory commands:

```bash
git diff --name-only origin/main...HEAD
git diff --stat origin/main...HEAD
rg -n "<changed symbol or module>" tests dharma_swarm scripts
python -m pytest -q <mapped tests> --tb=short
```

Replace `<changed symbol or module>` with concrete names from the diff.

Inspect:

- changed public functions, classes, CLI entrypoints, scripts, workflows;
- tests that import or execute them;
- missing negative tests for changed failure paths.

Failure classes:

- `BEHAVIOR_DIFF_WITHOUT_TEST`
- `PUBLIC_API_WITHOUT_CHARACTERIZATION`
- `CHANGED_GATE_WITHOUT_RED_CASE`
- `SCRIPT_CONSUMER_UNTESTED`

Required output: table of changed file, changed symbol, mapped tests, command
result, and coverage gap.

## Prompt TV-03: Hypothesis Property Strength Audit

Expert lens: property-based testing specialist.

Mission: determine whether property tests are installed, run, and strong enough
to falsify real invariants rather than restating implementation details.

Mandatory commands:

```bash
python -c "import hypothesis; print(hypothesis.__version__)"
python -m pytest -q tests/properties --tb=short
rg -n "from hypothesis|@given|strategies|importorskip\\(\"hypothesis\"|assume\\(" tests pyproject.toml
```

Inspect:

- dependency declaration for Hypothesis;
- `tests/properties/`;
- generator diversity and shrink quality;
- properties that only assert type, non-null, or object creation.

Failure classes:

- `PROPERTY_TESTS_SILENTLY_SKIPPED`
- `TAUTOLOGICAL_PROPERTY`
- `WEAK_GENERATOR_DOMAIN`
- `NO_METAMORPHIC_OR_STATEFUL_PROPERTY`

Required output: strongest property, weakest property, missing invariant, and a
specific property test to add.

## Prompt TV-04: Canonical Replay Determinism Audit

Expert lens: replay and falsifiability auditor.

Mission: prove whether canonical replay is deterministic, isolated from ambient
state, and able to detect event-order or artifact-hash drift.

Mandatory commands:

```bash
python -m pytest -q tests/test_canonical_replay.py tests/test_continuity_harness.py --tb=short
bash tests/fixtures/organism_closure_v0/replay.sh
rg -n "CanonicalReplayEngine|_execute_replay|_hash_state|replay|event_log_dir|Path.home\\(\\).*\\.dharma" dharma_swarm tests
```

Inspect:

- replay engine state hashing;
- unknown event handling;
- fixture isolation;
- use of `Path.home()` or operator-local state;
- whether replay proves semantic equivalence or just command completion.

Failure classes:

- `NONDETERMINISTIC_REPLAY`
- `AMBIENT_STATE_DEPENDENCE`
- `HASH_DOES_NOT_BIND_BEHAVIOR`
- `REPLAY_COMMAND_NOT_REPRODUCIBLE`

Required output: determinism verdict, evidence table, and one minimal replay
tamper test.

## Prompt TV-05: Governance-All Wiring Audit

Expert lens: governance CI contract reviewer.

Mission: verify whether local governance commands and CI workflows enforce the
same invariants, or whether governance exists only as advisory scripts.

Mandatory commands:

```bash
sed -n '246,286p' Makefile
sed -n '448,462p' Makefile
rg -n "governance-all|semgrep|gitleaks|test-hygiene|module-budget|docops-integrity|ANTI_SLOP|Rule [0-9]" Makefile docs/governance scripts .github/workflows
make governance-all
```

If `make governance-all` cannot run, record why and inspect the target wiring.

Inspect:

- Makefile targets;
- CI workflow parity;
- hard-fail vs advisory behavior;
- same-PR gate weakening risk.

Failure classes:

- `GOVERNANCE_SCRIPT_NOT_IN_GATE`
- `LOCAL_CI_PARITY_GAP`
- `WARNING_ONLY_CRITICAL_INVARIANT`
- `SAME_PR_GATE_WEAKENING`

Required output: gate map with owner, local command, CI workflow, fail mode, and
missing red-case fixture.

## Prompt TV-06: Test Hygiene State-Isolation Audit

Expert lens: local-state safety auditor.

Mission: find tests that mutate operator state, depend on local machine state,
or call subprocesses without isolated state directories.

Mandatory commands:

```bash
python3 scripts/governance/check_test_hygiene.py
rg -n "RuntimeStateStore\\(|Path.home\\(\\)|\\.dharma|subprocess\\.(run|Popen|call|check_call|check_output).*dgc|--state-dir|tmp_path|monkeypatch" tests dharma_swarm scripts
```

Inspect:

- use of `~/.dharma`;
- runtime DB tests;
- subprocess tests;
- fixture isolation and cleanup.

Failure classes:

- `TEST_MUTATES_OPERATOR_STATE`
- `MACHINE_LOCAL_PASS`
- `SUBPROCESS_WITHOUT_STATE_DIR`
- `FIXTURE_LEAK`

Required output: list of risky tests, whether they are covered by hygiene gates,
and exact refactor or fixture isolation proposal.

## Prompt TV-07: Assertion Strength and Negative-Control Audit

Expert lens: mutation-testing critic.

Mission: identify tests that would pass under simple harmful mutations because
assertions are too weak or negative controls are missing.

Mandatory commands:

```bash
rg -n "assert \\w+$|assert .* is not None|assert isinstance|assert len\\(|pytest\\.raises|invalid|malformed|tamper|timeout|retry|partial|error|fail" tests
rg -n "except Exception|raise ValueError|raise RuntimeError|timeout|retry" dharma_swarm tests
```

Inspect:

- truthiness and non-null assertions;
- missing invalid, malformed, tamper, timeout, retry, partial-failure tests;
- exception paths in implementation without tests.

Failure classes:

- `TRIVIAL_ASSERTION`
- `HAPPY_PATH_ONLY`
- `NO_NEGATIVE_CONTROL`
- `MUTATION_SURVIVES_TEST`

Required output: 10 weakest assertions, the mutation they fail to catch, and a
stronger assertion.

## Prompt TV-08: Mock Boundary Reality Audit

Expert lens: integration-boundary examiner.

Mission: find tests that mock away the actual adapter, persistence, transport,
or receipt behavior they claim to verify.

Mandatory commands:

```bash
rg -n "Mock\\(|MagicMock|patch\\(|monkeypatch|fake|stub" tests
rg -n "adapter|bridge|facade|persistence|sqlite|transport|receipt|RuntimeReceipt|EvidenceReceipt" dharma_swarm tests
```

Then run mapped adapter or contract tests if they exist.

Inspect:

- mocks around storage, providers, queues, receipts, subprocesses;
- tests that assert mocks were called instead of externally visible behavior;
- real integration tests for each adapter.

Failure classes:

- `MOCK_EVERYTHING_THEATER`
- `ADAPTER_CONTRACT_UNTESTED`
- `PERSISTENCE_NOT_EXERCISED`
- `MOCK_CALL_ASSERTED_AS_BEHAVIOR`

Required output: boundary map, real-vs-mocked evidence, and one concrete contract
test to add.

## Prompt TV-09: Complexity Budget Verification Audit

Expert lens: complexity governor.

Mission: verify whether tests can pass while module size, duplication, or
abstraction sprawl worsens.

Mandatory commands:

```bash
python3 scripts/governance/check_module_budget.py --base-ref origin/main --head-ref HEAD
python3 scripts/governance/check_module_coherence.py --repo-root . --json
git diff --numstat origin/main...HEAD
rg -n "GRANDFATHERED|LINE_BUDGET|GROWTH_TOLERANCE" scripts/governance/check_module_budget.py docs/governance/ANTI_SLOP_RULES.md
```

Inspect:

- growth in grandfathered modules;
- duplicate module names and concepts;
- complexity checks that grandfather current drift;
- whether budget failure is hard or advisory.

Failure classes:

- `GREEN_TESTS_WITH_GOD_FILE_GROWTH`
- `GRANDFATHER_CREEP`
- `DUPLICATE_SURFACE`
- `COMPLEXITY_GATE_ADVISORY_ONLY`

Required output: changed-line risk table and one ratchet proposal.

## Prompt TV-10: AI-Slop Evidence Hierarchy Audit

Expert lens: anti-hallucination governance reviewer.

Mission: find verification claims that lack command evidence, artifact paths,
fresh receipts, or reproducible output.

Mandatory commands:

```bash
python3 scripts/governance/hygiene/check_hygiene_integrity.py
python3 scripts/governance/hygiene/scan.py --output /tmp/dharma-hygiene-audit.txt
rg -n "AI-B1|AI-G1|VC-A1|VC-A2|VC-A3|VC-A5|evidence-free|Visible-gate|Trivially true|Green CI debt" docs/governance/hygiene
rg -n "passed|green|verified|works|probably|should" docs tests dharma_swarm
```

Inspect:

- evidence-free success claims;
- visible-gate gaming risk;
- test theater patterns;
- whether hygiene findings are advisory or enforced.

Failure classes:

- `EVIDENCE_FREE_VERIFICATION`
- `VISIBLE_GATE_GAMING`
- `SELF_REPORTED_GREEN`
- `UNREPLAYABLE_RECEIPT`

Required output: claim/evidence table and a proposed promotion from hygiene
signal to executable gate.
