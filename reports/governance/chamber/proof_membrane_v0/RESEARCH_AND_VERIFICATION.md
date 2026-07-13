# Hyperbolic Chamber Proof Membrane V0 — Research and Verification

Date: 2026-07-14 (Asia/Tokyo)
Frozen base: `2d2de7b1bfdd982b09334b7154e3e26425c55211`
Committed implementation: `df435af863e651287de3f637509a45d59b133ad3`
Track: `hyperbolic-time-chamber-2026-07`
Claim ceiling: `HARNESS_PROVEN` for the exact replay manifest only

## Verdict

The chamber should be a bounded proof membrane, not a general-purpose
simulation platform. External engines may propose worlds or discover candidate
failures. Only the local data-only replay contract, fresh-process verifier, and
evaluator-owned capability may produce the V0 evidence used at a promotion
boundary.

MiroFish belongs outside that boundary. It can help imagine social worlds; it
cannot decide whether Dharma code satisfied a runtime property, whether a
forecast is calibrated, or whether production may change.

## Evidence ledger

| ID | Typed claim | Authority and durable locator | Counterevidence / limit | Falsifier or next proof |
|---|---|---|---|---|
| HC-001 | `Claim<ScenarioCandidate, Generated, MiroFish@96096ea, inspected_public_tree>` | Upstream workflow, runner, LLM client, and report-agent source linked below | No live MiroFish run was performed; repository popularity and self-description are not validation | A pinned adapter can emit a frozen candidate fixture, but it remains `Generated` |
| HC-002 | `Claim<NoExactReplayContractObserved, Inspected, MiroFish@96096ea, four_named_paths>` | README workflow, parallel runner, LLM client, and report-agent paths linked below expose stochastic/concurrent/model-driven inputs, but no complete exact-replay contract was observed in those paths | This is not an exhaustive absence claim; uninspected OASIS/provider internals or later upstream versions may add such a contract | A pinned contract capturing entropy, schedules, model exchanges, environment versions, and repeated semantic hashes falsifies this bounded observation |
| HC-003 | `Claim<AntithesisUsefulForSearchAndReplay, Documented, vendor_docs, documented_scope>` | Antithesis deterministic-simulation and fault-injection documentation | Vendor execution cannot define Dharma's semantic proposition or evaluator permission | Export and reproduce one vendor-found failure under a Dharma exact-scope verifier |
| HC-004 | `Claim<HypothesisUsefulForGenerationAndShrinking, Documented, official_docs, stateful_testing>` | Hypothesis stateful testing documentation | Its seed/database is not the canonical replay bundle and does not grant authority | Minimize a later registered Dharma world into the data-only bundle schema |
| HC-005 | `Claim<Refutes<fork_parent_isolated>, Reproduced, RuntimeVerifier, scope:8f29d827...>` | Committed bundle and `verification_receipt.json` in this directory; 100 unique child PIDs carry one replay-payload digest and exact loaded-source digests | Demonstrates one current defect, not general determinism, a repaired graph, or OS attestation | DharmaGraph owner repairs it; a new repair-oriented bundle must then obtain an exact-scope `Satisfies` claim |
| HC-006 | `Claim<PromotionGateMechanics, Tested, local_pytest, owned_test_scope>` | `tests/test_chamber_traces.py`; wrong proposition, scope, modality, arm, candidate, effect binding, property, control, authority shape, evaluator instance, duplicate mint, and reuse are rejected | Trusted-process semantic boundary only; Python privacy, frozen dataclasses, and underscores are not a hostile-code security boundary | Bind a later production gate to a durable principal and transactional effect protocol without widening V0 |

## Engine placement

| Engine family | Chamber role | Authority ceiling |
|---|---|---|
| MiroFish, OASIS, Concordia, SOTOPIA, AgentSociety | Outer world foundry for social, collusion, deception, and policy scenarios | `Generated<ScenarioCandidate>` |
| Hypothesis | Generate and shrink explicit choices/faults | Candidate/minimization evidence |
| FoundationDB simulation and TigerBeetle VOPR patterns | Design prior art for injected time, entropy, faults, and same-code testing | Architectural prior art |
| Maelstrom | Later message-history and transport-adapter pattern | Harness evidence |
| Jepsen | Later live-cluster anomaly and consistency evidence | `Observed`, not proof of absence |
| Antithesis | Later whole-container schedule/fault search and vendor replay | `VendorReproduced` until locally discharged |
| rr | Optional Linux trace/debug attachment | Recorded execution only |
| TLA+, P, Apalache | Later abstract protocol obligations and bounded model checks | `ModelChecked` for the declared abstract scope |
| SimPy, Mesa, Determinator, a new whole-swarm scheduler | No V0 role | Avoid: would create a second execution semantics |

This table is admission policy, not an assertion that every named engine was
audited. MiroFish was inspected at the pinned commit and the linked primary
sources were read for Antithesis, FoundationDB, Maelstrom, and Hypothesis.
Grouped social/RL/debugging engines remain `not_inspected_for_admission` until
a separately pinned adapter dossier exists.

The adapter boundary is deliberately one-way:

```text
external engine / Forge / MiroFish
        -> untrusted ScenarioCandidateV1
        -> explicit human/policy selection
        -> frozen data-only WorldV1
        -> source-exact registered Dharma seam
        -> ReplayBundleV1 + isolated fresh-process verifier
        -> candidate-and-arm-bound typed claim
        -> evaluator-owned exact obligation/effect-binding capability
```

Claimed confidence, consensus, candidate identity, or authority fields are
stripped at the first arrow. No external process, model, report, score, or
serialized payload can mint the final capability through the supported API.

## V0 executable evidence

The registered specimen executes the committed `graph/types.py` bytes from the
validated manifest without importing the broad graph package initializer. It
calls the source-exact `RunCheckpoint.fork` method and appends to a nested child
channel. The parent changes too, so the activated property is false. The
distinct, bundle-bound deep-copy control candidate leaves the parent unchanged
and satisfies the property.

Each child starts through a stdlib-only worker. The receipt records the exact
six repository files loaded by that worker, their byte digests, Python and Git
identity, PATH, a fresh HOME, exit/timing/PID data, the parsed replay-payload
digest, and stdout/stderr digests. The bundle bytes travel over stdin, so a
later path replacement cannot change child input.

Durable artifacts:

- `dharmagraph_fork_alias.replay_bundle.v1.json`
  - source revision: `df435af863e651287de3f637509a45d59b133ad3`
  - bundle and scope digest: `8f29d8279aa5cd4a99f4861fb0df557356c9942b88112673b26f1568e1c91085`
  - specimen candidate: `dharmagraph.run_checkpoint.current-fork-specimen.v1`
  - control candidate: `dharmagraph.run_checkpoint.deepcopy-control-fixture.v1`
  - failing specimen semantic digest: `7e215b28cc0ad055f2dc12a32246f1cb99c4bbb960162d3b356fa0d354928673`
  - passing control semantic digest: `c750b3470d9af1a54e1177a63b2bd4f8dd031f75f55fc19a2f70a60db3edb3e6`
- `verification_receipt.json`
  - 100 requested, 100 completed, 100 unique child PIDs
  - common per-run semantic digest: `5babd79576f0eea166eb8d82e956658b2022a83ef44e2365331a18803404b267`
  - semantic receipt digest: `71535e6240641b661fbef84aec7a25e7c492939be65639f5be40184ce9962c38`
  - transcript digest: `0aff471449b66fe826e6deb88ace9edd7d94ed873f6bb238b972377350d9e271`
  - whole receipt digest: `052402a0b03a68f3f78539b00c427aa5a6d9ae276f26cacd9d849535457296b9`
  - Python: `/Users/dhyana/dharma_swarm/.venv/bin/python`, CPython 3.13.12
  - Git: `/usr/bin/git`, SHA-256 `179301dcb41ea78accc3fa0048a7e6f6710d891945a751a34addd622020c1818`

Checks completed before this ledger was written:

```text
pytest -q tests/test_chamber_traces.py
33 passed in 18.05s

pytest -q tests/test_graph_checkpoint.py tests/test_graph_neutral_cycles_resume.py
22 passed in 0.20s

PATH=<repository .venv first> pytest -q <all seven owned chamber suites>
102 passed in 44.49s

pytest -q tests/test_chamber_traces.py -k <semantic negative selection>
22 passed, 11 deselected in 2.08s

ruff check <five proof/replay modules> tests/test_chamber_traces.py
All checks passed

git diff --check; py_compile; AgentOps packet parse/digest; commit hooks
passed (including gitleaks, semgrep warn-only, docops, hygiene, contracts)

standalone bundle/receipt digest and transcript validator
0 errors; 100 transcript rows verified
```

An earlier broad-suite invocation without the repository virtual environment
at the front of `PATH` produced two errors in the pre-existing Git-history gym:
its scrubbed scorer intentionally calls `python3`, which resolved to macOS
system Python without pytest. The final 102/102 run used the governed repository
environment. This is a disclosed host invocation requirement, not a product
regression.

## Adversarial iteration record

The first six-lane council did **not** close: five lanes returned 100, while
MiniMax returned 45/revise, so the runner emitted `hold_blockers`. Its useful
objections were missing attached manifest sources, an underspecified process
transcript, and an easily misunderstood governance negative control.

Independent code reviewers then found deeper issues that the five approving
lanes missed: the normal graph import executed unmanifested package
initializers; direct dataclass bundles bypassed the serialized contract; a
caller could relabel control evidence as any candidate; duplicate capabilities
could repeat an effect; nested receipt state was mutable; and a capability's
dataclass fields were not sufficient registry state. Those findings caused the
isolated worker, strict direct-object validation, bundle-bound candidate/arm,
single-mint registry, effect-binding ID, deep-freeze, and executed-source digest
changes now present. A fresh internal review found no remaining V0 code blocker
and explicitly retained the limitations below.

Round 2 also did **not** close: five lanes returned 100 while Qwen returned
85/revise. Its objections were that direct object construction lacked explicit
executable evidence and that PM0-10 was not already demonstrated. The gate
already failed direct claims and unissued authorization objects, but the tests
showed adjacent attacks rather than those literal constructors. The revised
suite now directly constructs a copied `FreshProcessVerification`, copied
`Claim`, serialized authority dictionary, and private authorization shape and
requires zero effects. The specification also makes PM0-10 non-circular and
matches the all-six runner policy.

Round 3 reviewed the amended commit and full untruncated evidence packet. All
six required lanes returned pass/approve at 100, with zero blockers; the
runner emitted `pass_fullness`. The persistent `palantir-pilot` witness was
running and fresh at 25 seconds. The requested Kimi 2.7 route reached actual
model `kimi-k2.5`, which is disclosed in the durable summary rather than
treated as identity-equivalent. No earlier approval was inherited. This closes
the external review gate, not the runtime proof gate: the executable replay and
local checks remain the authority for the bounded harness claim.

## Primary research locators

- [MiroFish upstream workflow](https://github.com/666ghj/MiroFish/blob/96096ea0ff42b1a30cbc41a1560b8c91090f9968/README.md#L86-L92)
- [MiroFish random activation and runner](https://github.com/666ghj/MiroFish/blob/96096ea0ff42b1a30cbc41a1560b8c91090f9968/backend/scripts/run_parallel_simulation.py#L1040-L1080)
- [MiroFish LLM client temperature](https://github.com/666ghj/MiroFish/blob/96096ea0ff42b1a30cbc41a1560b8c91090f9968/backend/app/utils/llm_client.py#L35-L68)
- [MiroFish report generation](https://github.com/666ghj/MiroFish/blob/96096ea0ff42b1a30cbc41a1560b8c91090f9968/backend/app/services/report_agent.py#L1290-L1320)
- [OASIS upstream](https://github.com/camel-ai/oasis)
- [Antithesis deterministic simulation testing](https://antithesis.com/docs/resources/deterministic_simulation_testing/)
- [FoundationDB simulation testing](https://apple.github.io/foundationdb/testing.html)
- [Maelstrom upstream](https://github.com/jepsen-io/maelstrom)
- [Hypothesis stateful testing](https://hypothesis.readthedocs.io/en/latest/stateful.html)

## Non-claims and kill criteria

V0 does not claim whole-organism determinism, crash-safe effects, automatic root
cause analysis, production readiness, human forecasting validity, live A2A
closure, or parity with Antithesis. If the next slice requires a new scheduler,
truth store, broker, live provider, container platform, or MiroFish runtime,
stop and return the work to ordinary defect repair or a separately governed
adapter proposal.

The verifier assumes trusted Python and a non-adversarial local filesystem for
the duration of invocation. The worker minimizes and records repository-source
execution, but it is not an OS sandbox, interpreter/stdlib image attestation,
cryptographic principal, or proof against a precisely timed hostile source
swap. Python-private seals and frozen dataclasses enforce supported-API
semantics, not security against arbitrary code already inside the evaluator.
Authorization is in-memory and single-evaluator only; handler code is not
attested, concurrent mint/promote is not a free-threaded protocol, and handler
failure after capability consumption is not transactionally retryable. No
production handler is wired: the sole allowed positive effect is a synthetic
test recorder.

Checksums prove artifact integrity only. Model agreement is review evidence
only. Neither is independent operational authority.
