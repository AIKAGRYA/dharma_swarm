# Go Idea Spark Ingest Spine Master Build Spec

Status: implementation master spec
Owner surface: Go ingest family, Python bridges, Autonomy Spine, PGE harness
Primary model target: Codex with gpt-5.5 for planner, evaluator, and hard integration turns
Delivery: PR stack, not one mega PR
Transport default: receipt files plus durable spool; NATS optional and gated by ack proof

## 1. Mission Summary

Build a single receipt-first ingest spine for the Dharma Swarm Go ingest family.
The current Go surfaces are useful but split across file payload adapters,
world signal JSONL flow, Python projection bridges, and separate operator
receipt views. This build unifies them without violating the existing language
boundary.

The target flow is:

```text
source connector
  -> Go normalizer / adapter
  -> tools/go_sdk receipt contract
  -> durable idempotent file spool
  -> Python receipt projection
  -> deterministic Idea Spark triage
  -> R/D bundle and promotion surfaces
  -> economic ingest-cost event
  -> optional NATS publish only when enabled and ack-verified
```

The build is complete only when the active runtime path and the operator receipt
path consume the same canonical receipt contract. A sidecar receipt bridge is
not enough.

## 2. Authority Boundary

Go may:

- collect public/source evidence;
- normalize payloads into typed receipts;
- compute hashes, stable IDs, and receipt IDs;
- spool receipts for replay and backpressure;
- expose health and metrics-like summaries;
- optionally transport receipts after a Python-owned authority check.

Go must not:

- write ontology, runtime, memory, or trusted semantic state directly;
- choose telos, policy, gates, promotion, or economic decisions;
- dispatch agents or mutate protected runtime authority;
- claim NATS liveness from port-open checks;
- become a second control plane.

Python remains the authority for:

- telos and policy gates;
- runtime and ontology writes;
- receipt projection into operator surfaces;
- economic ledger decisions;
- Idea Spark triage;
- R/D harness promotion and verification;
- NATS authority status.

## 3. Current-State Audit Inputs

The build starts from these verified audit conclusions:

- Main has four Go binaries plus one shared Go SDK:
  `tools/evidence_ingestor_go`, `tools/github_ingestor_go`,
  `tools/world_signal_ingestor_go`, `tools/world_scout_go`, and `tools/go_sdk`.
- `tools/world_scout_go` is not covered by `make go-ci`.
- The world runtime uses `world_signal_ingestor_go` JSONL mode, while the
  operator bridge expects receipt JSON files under `go_receipts/world`.
- `github_ingestor_go` is a payload-file adapter, not a live GitHub crawler.
- Receipt SDK deterministic identity is the strongest existing contract.
- Economics exist elsewhere in Python but are not wired into Go ingest runs.
- NATS exists as a governed substrate elsewhere, but ingest must not make it
  default authority until existing ack verifiers prove live delivery.
- Stale branches with Go/sense/world names are evidence sources only. They must
  not be merged as-is.

## 4. Target Runtime Contract

Every ingestor emits or can be wrapped into this minimum contract:

```text
receipt_id          deterministic identity for this exact source/event/payload
event_uid           deterministic upstream event identity
correlation_id      run or mission correlation
source              canonical source family
source_url          source locator, file URL, or upstream URL
observed_at         UTC timestamp
content_hash        deterministic payload hash
schema_version      receipt schema version
status              accepted or rejected
rejected_reason     non-empty when rejected
payload             normalized source payload, or null for rejected failures
```

The spool adds delivery metadata outside the receipt payload:

```text
spool_id            stable receipt_id-based key
state               pending, delivered, failed, or quarantined
attempt_count       integer
first_seen_at       UTC timestamp
last_attempt_at     UTC timestamp or null
last_error          string or null
consumer            projection or transport target
```

Backward compatibility rule: old `go_evidence_receipt.v0` receipts must still
load. Add optional fields only if readers tolerate absence.

## 5. PR Stack

### PR 1 - CI and Build Truth

Goal:
Make Go CI cover every production Go module, including `tools/world_scout_go`.

Implementation:

- Add `tools/world_scout_go` to the Makefile Go module loop or add an explicit
  scout test target that `go-ci` invokes.
- Decide one Go version policy for this repo surface. Prefer aligning scout
  with the existing Go CI version unless a documented exception is needed.
- Keep this PR mechanical and behavior-preserving.

Verification:

- `make go-ci`
- `go test ./...` inside `tools/world_scout_go` until `go-ci` proves it covers it.

Done:

- CI fails if `world_scout_go` tests fail.
- No runtime behavior changes.

### PR 2 - Durable Receipt Spool

Goal:
Add a minimal, file-native, idempotent spool under `tools/go_sdk`.

Implementation:

- Add append/list/mark/replay primitives.
- Use atomic writes and deterministic receipt identity.
- Store delivery metadata separately from receipt payload.
- Provide a narrow CLI or test helper only if needed for verification.

Verification:

- Unit tests for append, duplicate receipt, replay ordering, mark delivered,
  failed/quarantined state, and corrupted entry handling.
- `make go-ci`

Done:

- Replaying the same spool twice does not duplicate projected events.
- Corrupt entries are quarantined or reported without blocking valid receipts.

### PR 3 - World Runtime Receipt Unification

Goal:
Make the active world runtime use canonical receipts, not a separate
authoritative JSONL path.

Implementation:

- Update `world_signal_ingestor_go` so normal world signal output can be
  represented as receipts.
- Update `dharma_swarm/world_radar/go_bridge.py` to consume world receipts via
  the existing receipt bridge before building board, brief, inbox, and R/D
  artifacts.
- Preserve compatibility with existing JSONL artifacts as derived/cache outputs.

Verification:

- Go adapter tests for accepted and rejected world receipts.
- Python bridge tests proving runtime projection from receipt files.
- World radar bridge tests proving promoted/incubating signals still appear.

Done:

- There is one canonical world signal contract.
- JSONL outputs are derived artifacts, not the authoritative ingest path.

### PR 4 - Robustness and Backpressure

Goal:
Remove concrete ingestion fragility before adding higher-level intelligence.

Implementation:

- Add `bufio.Scanner` buffer sizing or switch to a reader that supports large
  JSONL rows.
- Thread `context.Context` through adapters and world scout HTTP requests.
- Add bounded retry/backoff and `Retry-After` handling for `world_scout_go`.
- Preserve partial source success. A failed source should not erase valid
  observations from other sources.

Verification:

- Large JSONL fixture test.
- Fake HTTP server tests for 429, Retry-After, timeout, 5xx, and partial success.
- `make go-ci`

Done:

- Ingest fails loudly and boundedly for malformed input.
- Valid source output survives unrelated source failure.

### PR 5 - Observability and Economic Hook

Goal:
Make ingest runs visible and economically accountable without inventing a
pricing model.

Implementation:

- Add ingest run summaries with duration, source count, byte count, accepted
  count, rejected count, retry count, error samples, and freshest receipt.
- Record one idempotent economic/cost event from Python per ingest run.
- Use conservative neutral compute units until the operator defines a real
  token/compute conversion.

Verification:

- Tests for summary shape.
- Test that repeated projection of the same run does not duplicate economic
  events.
- Existing bridge tests.

Done:

- Operator surfaces can answer what ran, what was accepted/rejected, what it
  cost in provisional units, and where the receipts are.

### PR 6 - Idea Spark V0 Triage

Goal:
Introduce the first deterministic Idea Spark gate.

Implementation:

- Add a Python triage tuple:
  novelty, telos_fit, tractability, source_confidence.
- Feed promotion/incubation from the tuple plus existing source evidence.
- Keep this deterministic first. Do not require model calls for the v0 gate.

Verification:

- Unit tests for obvious promote, incubate, reject, and insufficient-evidence
  cases.
- Regression tests proving old world board behavior is either preserved or
  explicitly updated.

Done:

- Promotion is not raw keyword score alone.
- Every promoted idea carries a triage tuple.

### PR 7 - Optional NATS Receipt Adapter

Goal:
Allow hot transport without making it authority.

Implementation:

- Add optional receipt publish/drain path behind `DHARMA_INGEST_NATS=1`.
- Reuse existing NATS ack verifier surfaces for truth claims.
- File spool remains replay truth even when NATS is enabled.

Verification:

- Flag-off tests prove no NATS dependency or network call.
- Flag-on tests use a fake or explicitly ack-verified local surface.
- Status must distinguish `ack_verified`, `ack_unverified`, and unavailable.

Done:

- No default NATS dependency.
- No live-transport claim without ack evidence.

### PR 8 - Final Integration and Branch Hygiene

Goal:
Land the system as one coherent build line.

Implementation:

- Update docs and operator surfaces to point at the receipt-first flow.
- Document stale branches as do-not-merge or cherry-pick-only.
- Remove or demote duplicate stale surfaces only when tests prove coverage.
- Prepare final integration PR description with receipts and rollback notes.

Verification:

- Full PR-stack verifier set.
- `make onboard`
- `make go-ci`
- bridge/world pytest set in the repo venv.
- autonomy mission verification.

Done:

- Final integration PR can be reviewed from receipts, tests, and docs without
  relying on chat history.

## 6. Agent Orchestration

Use this hierarchy:

```text
Codex 5.5 /goal
  -> ds-goal mission ledger
  -> long-harness PGE scaffold
  -> context quorum gate
  -> PR-scoped builder lanes
  -> evaluator/adversary lanes
  -> codex-loop verifier receipts
```

Initial commands:

```bash
make onboard
make autonomy-goal GOAL="Wire Dharma Go ingestors into receipt-first Idea Spark ingest spine"
make long-harness-init RUN_ID=go-idea-spark-ingest-spine MODE=brownfield RISK=Q3 GOAL="Receipt-first Go ingest spine with spool, triage, economics, and gated NATS"
make context-quorum-check AGENT=codex_planner RISK=Q3 QUESTION="Go ingest spine architecture and protected runtime boundaries"
```

Run mission:

```bash
make autonomy-run MISSION_ID=<mission-id> ARGS="--duration-hours 8 --dispatch-mode tmux --verify-every-minutes 20 --agents codex_planner,codex_builder,codex_evaluator,codex_reporter"
make autonomy-status MISSION_ID=<mission-id>
make autonomy-verify MISSION_ID=<mission-id>
make autonomy-brief MISSION_ID=<mission-id>
```

Use `codex-loop-*` inside each PR when a verifier needs its own receipt:

```bash
make codex-loop-init NAME=<loop-id> GOAL="<verifier goal>" MODE=verification VERIFIER_COMMAND="<command>"
make codex-loop-validate LOOP_ID=<loop-id> PHASE=ready
make codex-loop-record LOOP_ID=<loop-id> STATUS=pass EVIDENCE="<command result summary>"
make codex-loop-validate LOOP_ID=<loop-id> PHASE=complete
```

## 7. Agent Roles

Planner:

- owns architecture, PR boundaries, non-goals, and rollback plan;
- must not implement;
- must record file scopes and verifier expectations.

Builder:

- implements one PR at a time;
- declares file scope before edits;
- runs the narrowest meaningful tests;
- cannot self-close without evaluator review.

Evaluator:

- reviews for correctness, authority drift, security, missing tests, and stale
  branch hazards;
- must cite file paths, commands, or receipts;
- should fail work that passes tests but violates the Go/Python boundary.

Reporter:

- maintains mission brief, PR descriptions, receipts, and final status;
- keeps the operator-facing summary short and evidence-backed.

Recommended model policy:

- gpt-5.5 high reasoning for planner/evaluator and cross-PR integration;
- gpt-5.5 medium reasoning for builders;
- lower-cost/faster agents only for read-heavy scans and summaries;
- use fast mode only when the operator explicitly accepts the credit tradeoff.

## 8. Verification Matrix

Baseline checks:

```bash
make onboard
make go-ci
go test ./...
```

Python bridge/world checks:

```bash
./.venv/bin/python -m pytest -q \
  tests/test_go_adapter_contracts.py \
  tests/test_go_evidence_ingestor_bridge.py \
  tests/test_go_github_ingestor_bridge.py \
  tests/test_go_world_signal_bridge.py \
  tests/test_world_radar_go_bridge.py \
  tests/test_revenue_scout_daemon.py
```

New checks to add:

- spool append/replay/idempotency tests;
- world runtime receipt consumption tests;
- large JSONL tests;
- fake-server source retry/backoff tests;
- economic ledger idempotency tests;
- NATS flag-off and ack-classification tests.

Completion evidence:

- command output summaries;
- receipt paths;
- PR links;
- mission brief path;
- rollback notes;
- evaluator signoff.

## 9. Non-Goals

- No Go ontology, trusted memory, runtime DB, or dispatch writes.
- No default NATS dependency.
- No live NATS authority without ack verifier proof.
- No one-shot mega PR.
- No stale branch merge as-is.
- No invented token pricing or revenue math.
- No multi-model council in the first milestone.
- No 2x to 10x compute reallocation until receipt/spool/economics are green.

## 10. Branch Hygiene Rule

Branches with names implying Go, sense, ingest, scout, world, signal, or
evidence are not trusted by name. Before using any branch:

1. Diff it against current main.
2. Check whether it deletes current main Go/bridge surfaces.
3. Cherry-pick only the useful hunks.
4. Record the branch and commit in the PR description.

Known stale-risk branches from the audit:

- `feat/go-evidence-sense-organ-v0`
- `feat/world-radar-shakti-safe-convergence-2026-05-13`

These must be treated as cherry-pick-only unless a fresh audit proves otherwise.

## 11. Definition of Done

The full build is done when:

- all production Go ingest modules are under Go CI;
- the active world runtime emits and consumes canonical receipts;
- receipt spool replay is idempotent;
- rejected receipts are represented consistently;
- source fetch failure is bounded and partial success survives;
- ingest summaries and provisional cost events are visible;
- deterministic Idea Spark v0 triage drives promotion/incubation;
- NATS remains optional and truth-checked;
- stale branch risk is documented;
- each PR has tests, receipts, and evaluator signoff;
- the `ds-goal` mission verifies with no open build tasks.

## 12. Short Instantiation Goal

Use this prompt to start the build:

```text
/goal Read docs/specs/GO_IDEA_SPARK_INGEST_SPINE_MASTER_BUILD.md completely, then execute it as the controlling build spec for the Dharma Swarm Go Idea Spark ingest spine.

Use Codex gpt-5.5-level reasoning for planning, architecture, hard integration, and evaluator work. Start with make onboard, then attach the repo-native mission surfaces: autonomy spine, context quorum, and long-harness PGE. Treat the spec file as authority unless it conflicts with repo governance or current code evidence.

Build as a PR stack, not a mega PR. Use receipts plus durable file spool as the first production transport. Keep NATS optional and disabled by default unless existing ack verifiers prove live delivery. Preserve the boundary: Go may collect, normalize, hash, spool, observe, and transport evidence; Python owns telos, policy, gates, ontology/runtime writes, and economic decisions.

Implement in order: 1. put world_scout_go under Go CI; 2. add receipt spool and replay idempotency; 3. unify world runtime around canonical receipts; 4. add JSONL, context, retry/backoff, and partial-failure robustness; 5. add observability and one idempotent ingest-cost ledger event; 6. add deterministic Idea Spark v0 triage; 7. add optional NATS adapter only behind a flag; 8. finalize docs, stale-branch hygiene, receipts, and PR integration.

For every PR: declare file scope, implement narrowly, add tests, run the narrowest meaningful verifier, record evidence, and have a separate evaluator pass review before closure. Required checks include make go-ci, world_scout_go tests until folded into go-ci, and venv pytest for Go bridge/world radar tests. Do not mark done from inspection alone. If blocked, write the blocker with exact command output or file evidence.
```
