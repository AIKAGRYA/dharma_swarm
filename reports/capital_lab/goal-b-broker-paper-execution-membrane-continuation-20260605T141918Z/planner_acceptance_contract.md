# Goal B Broker-Paper Execution Membrane Continuation Planner Contract

Mission:
`20260605T141918Z-goal-b-broker-paper-execution-membrane-continuation`

Task:
`20260605T141918Z-goal-b-broker-paper-execution-membrane-continuation-t01-planner`

Generated: `2026-06-05T14:24:50Z`

## Current State

This continuation starts from the Agni read-only evidence produced in
`20260605T134546Z-goal-b-agni-broker-paper-execution` and the partial planner
packet from `20260605T135732Z-goal-b-broker-paper-execution-membrane`.

The continuation discovered that the previously referenced master contract and
packet schema files were not present in the local spec directory, and the
previous report directory referenced by the manifest was also absent. This task
therefore restores the contract files under the allowed `spec-forge` path and
emits a fresh planner contract under the continuation report path.

## Non-Negotiable Status

- `live_readiness=0`
- `live_authority=false`
- `broker_write_authority=false`
- `clean=false`

These values remain false or zero unless every authority, lifecycle,
idempotency, reconciliation, drill, packet, and operator-handoff gate passes
with receipt-backed evidence.

## Acceptance Contract

1. Restore `MASTER_GOAL.md` and `PACKET_SCHEMAS.md`.
2. Treat `/root/hyperliquid-trading-agent` as excluded live-capable authority
   until explicitly fenced or governed by a separate operator lease.
3. Build only a broker-paper adapter path that cannot import or call live
   Hyperliquid Exchange order methods.
4. Require idempotent `client_order_id` values for every paper order.
5. Emit broker-shaped receipts for submit, ack, partial fill, full fill, cancel,
   reject, and expire.
6. Reconcile the local ledger against a broker-paper snapshot and block on any
   mismatch.
7. Run duplicate-order, rejection, cancel, expire, heartbeat, stale-data,
   max-loss, and order-rate/exposure drills.
8. Emit adapter readiness and execution feasibility packets with hashes.
9. Hand off exact blocker and status fields to the operator.
10. Do not claim live collaboration, live readiness, live broker authority,
    external profit, or clean status without evidence.

## Risk Register

- `R1_live_authority_bleed`: Hyperliquid live-capable code and private-key alias
  exist on Agni. Mitigation: deny imports/calls in Goal B adapter and keep
  clean false until quarantined or separately leased.
- `R2_fixture_overclaim`: A local fixture broker can prove lifecycle logic but
  not external broker-paper reliability. Mitigation: mark fixture-only evidence
  and keep live readiness at zero.
- `R3_idempotency_gap`: Duplicate orders can be created if client order ids are
  not durable. Mitigation: deterministic ids plus durable ledger replay test.
- `R4_reconciliation_gap`: Local paper PnL can diverge from broker state.
  Mitigation: snapshot comparison blocks readiness on mismatch.
- `R5_kill_switch_partiality`: Existing heartbeat and loss gates do not prove
  order-rate or exposure halts. Mitigation: require explicit drills.
- `R6_operator_confusion`: "paper" or "live-alpha candidate" wording can be
  misread as live authority. Mitigation: all packets repeat false/zero status.

## Smallest Proof Loop

The next builder should implement a deterministic local proof loop before any
remote or external broker interaction:

1. Static authority guard checks pass.
2. Runtime authority guard blocks live-capable imports or method calls.
3. Fixture broker accepts an order intent with a deterministic
   `client_order_id`.
4. Adapter writes submit and ack receipts.
5. Adapter writes partial-fill and full-fill receipts.
6. Adapter writes cancel, reject, and expire receipts on separate fixtures.
7. Duplicate submit returns the existing order or rejects without a second
   order.
8. Reconciliation succeeds for a matched broker-paper snapshot.
9. Reconciliation mismatch blocks readiness and records why.
10. Kill-switch drills produce pass/fail receipts.
11. Readiness and feasibility packets report `live_readiness=0`,
    `live_authority=false`, and `clean=false`.

## Builder Handoff

The narrowest implementation surface should be under
`dharma_swarm/capital_lab/`, `scripts/runtime/capital_lab_*`, and
`tests/test_capital_lab_*`, matching the builder lease. The planner does not
authorize live keys, live orders, or Agni mutation.

