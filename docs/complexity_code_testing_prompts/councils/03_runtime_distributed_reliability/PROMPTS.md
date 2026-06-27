# Council 03: Runtime and Distributed Reliability Prompts

Council ID: `runtime_distributed_reliability`

Use these prompts to audit receipts, idempotency, queues, runtime state,
canonical replay, provider fallback, observability, chaos coverage, board
consistency, and runtime-truth claims.

## Shared Prompt Contract

```text
Apply exactly one distributed reliability lens. Audit only. Do not edit files.

Classify every finding as confirmed, likely, or unproven. Include command
evidence or file:line evidence. For distributed claims, distinguish process
liveness, receipt persistence, semantic success, and operator-facing truth.
```

## Prompt RDR-01: Dispatch Receipt Completeness Audit

Expert lens: distributed workflow auditor.

Mandatory commands:

```bash
rg -n "EvidenceReceipt|persist_receipt|receipt_json|delegation_runs|provider_attempted|error_source" dharma_swarm tests scripts
python -m pytest -q tests/test_orchestrator_spine_dispatch.py tests/test_spine_persistence_invariant.py tests/test_runtime_receipt_coverage_report.py --tb=short
```

Failure classes:

- `UNRECEIPTED_DISPATCH`
- `SILENT_RECEIPT_PERSISTENCE_FAILURE`
- `MISMATCHED_TASK_RUN_ID`
- `RECEIPT_STATUS_MASKS_FAILURE`

Required output: receipt lifecycle map and one missing persistence invariant.

## Prompt RDR-02: Idempotency and Side-Effect Replay Audit

Expert lens: exactly-once and at-least-once systems engineer.

Mandatory commands:

```bash
rg -n "idempotency_key|side_effect_key|idempotency_records|stable_payload_hash|retry_intent_key|dedupe|dedup" dharma_swarm tests scripts
python -m pytest -q tests/test_runtime_state_invariants.py tests/test_runtime_truth_projection_fields.py tests/test_autonomy_spine_cli.py --tb=short
```

Failure classes:

- `DUPLICATE_SIDE_EFFECT`
- `NON_STABLE_IDEMPOTENCY_KEY`
- `REPLAY_CREATES_NEW_WORK`
- `HASH_EXCLUDES_MEANINGFUL_INPUT`

Required output: side-effect inventory and replay safety verdict.

## Prompt RDR-03: A2A/NATS Queue Lifecycle Audit

Expert lens: message broker reliability reviewer.

Mandatory commands:

```bash
rg -n "NATS|consumer|ack|ack_pending|pending|handler_ack|domain_receipt|reply_capture|DELIVERED|JetStream" dharma_swarm tests scripts docs reports
make nats-substrate-contract
```

If local NATS is unavailable, inspect the contract and report `commands_not_run`.

Failure classes:

- `ACK_WITHOUT_DOMAIN_RECEIPT`
- `STUCK_CONSUMER`
- `UNBOUNDED_QUEUE_GROWTH`
- `STALE_HEARTBEAT_REPORTED_LIVE`

Required output: queue lifecycle table with send, ack, receipt, retry, and DLQ
status.

## Prompt RDR-04: Runtime State Persistence Invariant Audit

Expert lens: SQLite and state-machine durability auditor.

Mandatory commands:

```bash
rg -n "runtime.db|runtime_receipts|delegation_runs|task_claims|acked_at|heartbeat_at|stale_after|recovered_at|retry_count" dharma_swarm tests scripts
python -m pytest -q tests/test_runtime_state.py tests/test_runtime_state_recovery.py tests/test_runtime_state_invariants.py --tb=short
```

Failure classes:

- `INVALID_FSM_TRANSITION`
- `LOST_CLAIM_RECOVERY`
- `HEARTBEAT_FRESHNESS_LIE`
- `ORPHANED_RECEIPT`

Required output: state transition graph and missing invariant.

## Prompt RDR-05: Canonical Replay and Determinism Audit

Expert lens: replay and provenance engineer.

Mandatory commands:

```bash
rg -n "replay|canonical_replay|replay_command|fixtures/.*/replay|recorded trace|artifact_id|current_artifact_id" dharma_swarm tests scripts
python -m pytest -q tests/test_canonical_replay.py tests/test_runtime_artifacts.py tests/test_ds_goal_wrapper_receipt_probe.py --tb=short
```

Failure classes:

- `RECEIPT_CANNOT_REPRODUCE_RESULT`
- `REPLAY_DEPENDS_ON_AMBIENT_STATE`
- `ARTIFACT_HASH_DRIFT`
- `REPLAY_OMITS_PROVIDER_FAILURE_PATH`

Required output: replay proof chain and one tamper scenario.

## Prompt RDR-06: Provider Fallback Truth Audit

Expert lens: live-provider failure semantics reviewer.

Mandatory commands:

```bash
rg -n "preferred_runtime_provider|fallback|provider_order|provider_attempted|selected_provider|served_route|provider_unreachable|provider_failed" dharma_swarm tests
python -m pytest -q tests/test_runtime_provider.py tests/test_provider_policy.py tests/test_provider_failure_classes.py tests/test_agent_runner.py --tb=short
```

Failure classes:

- `FALLBACK_HIDDEN_FROM_RECEIPT`
- `SELECTED_ROUTE_DIFFERS_FROM_SERVED_ROUTE`
- `TIMEOUT_NORMALIZED_AS_SUCCESS`
- `PROVIDER_EXCEPTION_LOSES_CLASS`

Required output: provider route evidence and failure-class coverage.

## Prompt RDR-07: Observability and Operator Truth Audit

Expert lens: SRE observability auditor.

Mandatory commands:

```bash
rg -n "runtime_truth|live_ops|telemetry|health|status|readiness|active_head|fresh|stale|dashboard|operator" dharma_swarm api dashboard tests scripts
make runtime-truth-ci
python3 scripts/governance/spine_dispatch_mode_report.py --strict
```

Failure classes:

- `STALE_EVIDENCE_MARKED_HEALTHY`
- `TELEMETRY_OMITS_FAILURES`
- `READINESS_NOT_FALSIFIABLE`
- `PROCESS_LIVENESS_CONFUSED_WITH_SUCCESS`

Required output: operator-facing claim table with evidence freshness.

## Prompt RDR-08: Chaos and Fault-Injection Coverage Audit

Expert lens: chaos engineering test designer.

Mandatory commands:

```bash
rg -n "timeout|cancelled|provider_unreachable|claim_lost|stale|recovered|rollback|fault|chaos|monkeypatch.*raise|raises" tests dharma_swarm
rg -n "class ErrorSource|ErrorSource" dharma_swarm/spine/receipt.py dharma_swarm tests
```

Failure classes:

- `UNTESTED_FAILURE_ENUM`
- `CANCELLATION_RACE_UNMODELED`
- `CRASH_BETWEEN_RECEIPT_AND_PERSISTENCE`
- `STALE_CLAIM_DOUBLE_EXECUTES`

Required output: failure-mode coverage matrix and one fault-injection test.

## Prompt RDR-09: TaskBoard and Board Adapter Consistency Audit

Expert lens: distributed task ledger reviewer.

Mandatory commands:

```bash
rg -n "TaskBoard|BoardEvent|event_id|receipt_id|taskboard_adapter|semantic_receipt|agentops|a2a_send_adapter|requeue" dharma_swarm/board dharma_swarm tests
python -m pytest -q tests/test_task_board.py tests/test_board_facade.py tests/test_taskboard_adapter.py tests/test_a2a_send_board_adapter.py --tb=short
```

Failure classes:

- `BOARD_RUNTIME_DIVERGENCE`
- `DUPLICATE_EVENT_ID`
- `REQUEUE_LOSES_CAUSATION`
- `TASK_STATUS_SKIPS_TERMINAL_STATE`

Required output: board projection consistency verdict.

## Prompt RDR-10: Runtime Truth Claim Falsification Audit

Expert lens: adversarial production-readiness reviewer.

Mandatory commands:

```bash
make onboard
make orient
make runtime-truth-ci
python3 scripts/runtime/runtime_truth_100_audit.py
rg -n "88/100|70/100|production-ready|runtime truth|spine|bypass|allowlist|strict|closeout|burn-in" docs reports scripts tests
```

If a command is absent, mark it `not_run` and inspect nearby runtime-truth
owners.

Failure classes:

- `DECLARED_SCORE_EXCEEDS_EVIDENCE`
- `BYPASS_ALLOWLIST_HIDES_NON_ADOPTION`
- `GLOBAL_LIVE_DB_FAILS_STRICT_GATE`
- `MULTIPLE_TRUTH_SURFACES_DISAGREE`

Required output: truth-claim falsification table and one fail-closed test.
