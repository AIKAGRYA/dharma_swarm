# Runtime Truth Spine Command Cutover Goal

Date: 2026-06-12
Status: goal handoff spec
Role: long-running /goal instruction file

## Objective

Run a long, receipt-driven cutover and enforcement pass proving that live
command surfaces obey the existing Runtime Truth Spine. Do not build a new
spine. The repo already has the canonical substrate:

- `dharma_swarm/spine/identity.py` - `ExecutionIdentity`
- `dharma_swarm/spine/receipt.py` - dispatch `EvidenceReceipt`
- `dharma_swarm/spine/invoke.py` - blessed `invoke_agent` path
- `dharma_swarm/spine/tollbooth.py` - fail-closed gate
- `dharma_swarm/runtime_state.py` - `RuntimeStateStore`, `RuntimeReceipt`,
  idempotency records
- runtime truth / spine adoption reports and metrics

The goal is to make command surfaces, dashboards, onboard output, and
governance docs tell the truth: which paths are spine-native, adapter-ready,
opt-in only, legacy, quarantined, AMBER, RED, or fake-green risk.

## Core Doctrine

- No new `WorkCommand`, `WorkRun`, `WorkReceipt`, `command_runs`, or
  `work_runs` substrate.
- No new command ledger or table unless it is only a projection over existing
  `RuntimeStateStore`, `EvidenceReceipt`, and `RuntimeReceipt`.
- Existing Runtime Truth Spine remains canonical.
- Dashboards, file reports, OTel spans, AgentOps reports, and cards are
  projections, not authority.
- Transport publish, handler delivery, domain receipt, semantic reply, and
  work completion are separate states.
- If a surface cannot be cut over, label it AMBER or RED with exact receipt
  gaps instead of narrating completion.
- Preserve dirty unrelated work. Do not revert user or agent changes.
- No standing autonomy activation.
- No protected composer identity, SOUL, or persona mutation.

## Phase 0 - Baseline Receipt

Run:

```bash
make onboard
git status --short --branch
git log --oneline -12
```

Inspect `reports/governance/spine_adoption_metric.json` if present.

Write a baseline receipt under `reports/governance/` or
`reports/runtime_truth/` recording:

- branch and HEAD truth
- dirty worktree truth
- active tracks
- runtime-truth claims
- AMBER and RED claims
- known cutover targets
- whether active substrate tracks are already shippable
- whether revenue and research tracks are absent

## Phase 1 - Cutover Spec And Matrix

Create or update:

- `docs/governance/RUNTIME_TRUTH_COMMAND_CUTOVER.md`

It must state:

- This is enforcement of the existing spine, not a new spine.
- `spine.EvidenceReceipt` is dispatch proof.
- `RuntimeReceipt` is persisted runtime proof.
- `IdempotencyRecord` is the exactly-once substrate.
- `receipt_json`, file reports, dashboard cards, and onboard rows are
  projections.

Build a command-surface matrix for at least:

- ds-goal
- A2A send, bridge, reply, and domain-reply
- AgentOps work packets
- registered holon wake
- dashboard and control-surface cards
- discovered overnight, forge, or cron command surfaces

For each surface record:

- default path or opt-in path
- `ExecutionIdentity` present?
- dispatch `EvidenceReceipt` emitted?
- `RuntimeReceipt` written or associated?
- idempotency checked before side effects?
- operator UI distinguishes sent, delivered, domain receipt, semantic reply,
  and completed?
- current state: JOINED, ADAPTER_READY, OPT_IN_ONLY, LEGACY, QUARANTINE,
  AMBER, or RED
- next receipt required

## Phase 2 - First-Token Truth Layer

If missing, add or prepare:

- `docs/governance/SWARM_GENOME.md`
- `docs/governance/REALITY_DEBT_LEDGER.md`

`SWARM_GENOME.md` is a short front-door map, not a live-state owner. Keep it
compact and sourced.

`REALITY_DEBT_LEDGER.md` is the anti-overclaim firewall with this table:

```text
claim | current custody | proof missing | owner | next receipt | allowed language
```

Seed guarded claims for:

- self-funding / economically alive
- external humans served
- R_V or consciousness thesis proven
- self-evolution autonomous or metabolic
- runtime truth fully saturated
- deployed/live system equals audited main
- MemoryKernel as production first-token orientation
- Chetana main-owned canon metabolism
- Capital Lab / Ginko live trading authority
- Forge/Hydra runnable or fitness-authoritative
- market comparator figures verified

Wire lightly only:

- `make onboard` may print a tiny first-token seed.
- `make onboard` may print a one-line reality-debt count.
- Do not make onboarding noisy.
- Register new docs in DocOps if changed.

## Phase 3 - ds-goal Cutover

Use ds-goal as the first concrete cutover lane if the code surface is present.

Requirements:

- Use existing `ExecutionIdentity`.
- Use `RuntimeStateStore` as the persisted truth owner.
- Put idempotency or claim acquisition before kernel dispatch.
- A duplicate mission or run cannot dispatch twice.
- `mission_id` cannot escape its state root.
- Decide and document whether ds-goal emits `spine.EvidenceReceipt` directly
  or associates `RuntimeReceipt` to the canonical dispatch receipt model.
- Add or update tests for mission containment, duplicate dispatch, and
  concurrent runners.

If the real ds-goal runner is not present in the checkout, classify it as
AMBER or external/unproven and record the missing path.

## Phase 4 - A2A Evidence Semantics

Harden A2A evidence language:

- Untyped payloads never imply semantic collaboration.
- Forged or mismatched ack/reply evidence is rejected or marked RED.
- Transport publish, handler delivery, domain receipt, semantic reply, and
  task completion are separated in receipts and cards.
- A2A send should use `ExecutionIdentity` and `RuntimeStateStore`
  idempotency before publish if edited.
- Existing file ack receipts remain projections, not authority.

## Phase 5 - Holon Wake Boundary

- Registered holon names preserve prompt continuity.
- Unknown holon names fail closed by default, or require explicit reviewed
  generic fallback mode.
- Prove registered holon wake does not grant broad default tools.
- Do not edit protected composer identity, SOUL, or persona files.

## Phase 6 - Dashboard And Control-Surface Honesty

Update projections so:

- `done` is never derived from transport or handler ack alone.
- AMBER and RED states are visible.
- source errors are visible.
- cards distinguish sent, delivered, domain receipt, semantic reply, and
  completed.
- AgentOps green gates without runtime refs cannot project as fully bound or
  done.

## Phase 7 - Governance Gate And Final Receipt

- Refresh spine adoption metric if the repo supports it.
- Add or update a command-cutover metric that measures default-path adoption,
  not only adapter readiness.
- Add a static guard test banning parallel command-spine abstractions:
  `WorkCommand`, `WorkRun`, `command_runs`, `work_runs`, and new command
  ledger tables.
- Final after-action must list every remaining bypass and classify it.

## Focused Tests

Run the relevant tests that exist in the checkout. Do not invent passing
claims for missing tests; mark missing tests as absent and create the narrowest
useful ones when in scope.

Runtime truth:

- `tests/test_runtime_truth_spine_v2_evidence.py`
- `tests/test_runtime_state_invariants.py` or closest runtime-state invariant
  tests
- `tests/test_spine_persistence_invariant.py`
- `tests/test_autonomy_spine_cli.py` if present
- `tests/test_ds_goal_board_adapter.py` if present

A2A:

- `tests/test_a2a_send.py`
- `tests/test_a2a_inbox_bridge.py`
- `tests/test_a2a_reply_capture.py`
- `tests/test_a2a_domain_reply_artifact.py`
- `tests/test_a2a_send_board_adapter.py`

Control surface:

- `tests/test_control_surface.py`
- `tests/test_control_surface_ds_goal_cards.py`
- `tests/test_control_surface_a2a_cards.py`
- `tests/test_runtime_truth_projection_fields.py`

Required new or updated tests:

- untyped A2A reply is non-semantic
- forged or mismatched ack/reply is rejected or marked RED
- duplicate ds-goal run does not dispatch twice
- invalid `mission_id` cannot escape state root
- unknown holon wake fails closed
- card status does not show completion from handler ack alone
- no new parallel command-spine abstractions

## Completion Criteria

The goal is complete only when:

- A clear command-cutover matrix exists.
- The highest-risk fake-green projection is fixed or marked RED/AMBER.
- At least one bounded command path is improved or proven already safe.
- Dashboard/card language no longer collapses delivery into completion.
- Reality debt / allowed language prevents overclaiming, or the remaining
  missing anti-overclaim doc is explicitly listed as the next blocking gap.
- Tests pass, or exact blockers are documented.
- The final receipt names changed files, commands run, remaining bypasses, and
  the next PR slice.

