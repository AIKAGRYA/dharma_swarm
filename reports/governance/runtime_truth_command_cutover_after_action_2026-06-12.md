# Runtime Truth Command Cutover After-Action

Generated: 2026-06-12
Worktree: `/Users/dhyana/dharma_swarm_main`
Branch: `holon/spine-v1`
HEAD at verification: `f0d03ffaf4`

## Summary

This pass enforced the existing Runtime Truth Spine. It did not create a new
command spine, command ledger, `WorkCommand`, `WorkRun`, `WorkReceipt`,
`command_runs`, or `work_runs`.

## Implemented

- Added `docs/governance/SWARM_GENOME.md` as the compact first-token map.
- Added `docs/governance/REALITY_DEBT_LEDGER.md` with the required
  `claim | current custody | proof missing | owner | next receipt | allowed language`
  table.
- Added `docs/governance/RUNTIME_TRUTH_COMMAND_CUTOVER.md` with the command
  matrix, default-path adoption metric, evidence semantics, and bypass list.
- Wired `SWARM_GENOME.md` into the max-five first-read stack and registered
  the new governance docs in DocOps.
- Updated onboarding to show runtime `mission_id`, artifact-ref count, the
  first-token map, and the reality-debt count.
- Updated runtime truth summaries to include `mission_id` and `artifact_refs`.
- Updated AgentOps projection so green gates plus clean scope are only `bound`
  when runtime truth refs are present.
- Cut over A2A direct send to `ExecutionIdentity` and `RuntimeStateStore`
  idempotency before direct NATS publish, with a command-level `RuntimeReceipt`.
- Removed unsafe JetStream-to-core fallback after ambiguous publish errors and
  made A2A send receipt file creation atomic under concurrent retries.
- Added the first Runtime Warrant layer in `dharma_swarm/spine/warrant.py`.
  A2A direct send now requires a pre-publish warrant, and ds-goal run now
  requires a pre-kernel-wake warrant. Warrant denial blocks the side effect.
- Refined Runtime Warrant criteria after a broader connection pass: claim names
  are normalized, unknown surface/action pairs fail closed, blank claim
  boundaries fail closed, and idempotency now requires a matching
  RuntimeStateStore row rather than a boolean flag alone.
- Added direct `EvidenceReceipt` association for A2A direct send and ds-goal.
  Each command builds a `spine.EvidenceReceipt` and embeds its JSON plus compact
  ref inside the existing command `RuntimeReceipt` payload. This intentionally
  does not create a `dispatch_evidence` runtime receipt row or a second receipt
  hierarchy.
- Hardened A2A reply capture so untyped replies are non-semantic and
  untyped `domain_receipt: true` self-assertions cannot escalate evidence tier.
- Updated A2A BoardStore cards so handler delivery ack projects as `review`,
  not `done`.
- Hardened `ds-goal` so mission IDs and existing symlink mission directories
  cannot escape state root and idempotency is claimed before kernel wake
  dispatch.
- Hardened AgentOps and ds-goal BoardStore projections so local `done` status
  requires runtime or kernel proof refs before projecting as complete.
- Added a static guard test banning parallel command-spine source symbols.
- Refreshed `reports/governance/spine_adoption_metric.json`.
- Added `reports/governance/command_cutover_metric.json`.

## Verification

- `python3 -m compileall` on touched runtime, governance, board, and test files:
  passed.
- Focused first slice:
  `pytest -q tests/test_a2a_send.py tests/test_a2a_reply_capture.py tests/test_control_surface_a2a_cards.py tests/test_autonomy_spine_cli.py tests/test_runtime_truth_projection_fields.py tests/test_operating_facts.py tests/test_runtime_truth_command_cutover.py tests/test_ds_goal_board_adapter.py tests/test_control_surface_ds_goal_cards.py`
  passed: 47 tests.
- Full handoff-listed focused suite:
  `pytest -q tests/test_runtime_truth_spine_v2_evidence.py tests/test_runtime_state_invariants.py tests/test_spine_persistence_invariant.py tests/test_autonomy_spine_cli.py tests/test_ds_goal_board_adapter.py tests/test_a2a_send.py tests/test_a2a_inbox_bridge.py tests/test_a2a_reply_capture.py tests/test_a2a_domain_reply_artifact.py tests/test_a2a_send_board_adapter.py tests/test_control_surface.py tests/test_control_surface_ds_goal_cards.py tests/test_control_surface_a2a_cards.py tests/test_runtime_truth_projection_fields.py tests/test_operating_facts.py tests/test_runtime_truth_command_cutover.py`
  passed: 174 tests, 1 existing FastAPI/Starlette deprecation warning.
- Broader runtime/control-surface slice:
  `pytest -q tests/test_runtime_warrant.py tests/test_runtime_state.py tests/test_spine_mapping_receipts.py tests/test_runtime_truth_spine_v2_evidence.py tests/test_runtime_state_invariants.py tests/test_spine_persistence_invariant.py tests/test_autonomy_spine_cli.py tests/test_ds_goal_board_adapter.py tests/test_a2a_send.py tests/test_a2a_inbox_bridge.py tests/test_a2a_reply_capture.py tests/test_a2a_domain_reply_artifact.py tests/test_a2a_send_board_adapter.py tests/test_control_surface.py tests/test_control_surface_ds_goal_cards.py tests/test_control_surface_a2a_cards.py tests/test_runtime_truth_projection_fields.py tests/test_operating_facts.py tests/test_runtime_truth_command_cutover.py tests/test_agentops_board_adapter.py tests/test_spine_adoption_metric.py`
  passed: 218 tests, 1 existing FastAPI/Starlette deprecation warning.
- Evidence association slice:
  `pytest -q tests/test_a2a_send.py tests/test_autonomy_spine_cli.py`
  passed: 28 tests.
- `make onboard`: passed.
- `make docops-integrity`: passed, including hygiene integrity.
- `python3 scripts/governance/spine_bypass_report.py`: passed as warning-only
  report, 7 `.submit()` sites classified, 0 unknown.
- `python3 tools/spine_adoption_metric.py --output reports/governance/spine_adoption_metric.json`: passed.
- `git diff --check`: passed.
- `make agent-build-closeout`: advanced past hygiene audit, Semgrep, gitleaks,
  governance contract tests, NATS substrate contract/tests, and uplift guards,
  then failed the repo-level module-budget gate because
  `dharma_swarm/context_compiler.py`,
  `dharma_swarm/operator_core/living_agent_kernel.py`, and
  `dharma_swarm/operator_core/runtime_truth.py` exceed the 1000-line budget
  relative to `origin/main`. This is a branch-level merge blocker, not a
  RuntimeWarrant or EvidenceReceipt-association test failure.

## Remaining Bypasses

| Bypass | Classification | Reason | Next PR slice |
|---|---|---|---|
| A2A inbox bridge runtime owner | ADAPTER_READY | bridge file receipt is useful but projection-only | choose bridge RuntimeState owner or explicitly keep projection-only |
| A2A domain reply semantic authority | AMBER | typed domain receipts are distinguished, but semantic reply still depends on payload claims | add source identity and schema validation for semantic reply claims |
| AgentOps reports without runtime refs | AMBER | now projects partial, not bound | require runtime refs in green report promotion path |
| AgentOps/ds-goal cards without runtime closeback | AMBER | local done now projects review, not complete | promote only when runtime or kernel refs exist |
| registered holon wake broad-tool proof | AMBER | not fully audited in this pass | focused test for registered wake tool scope and unknown-name fail-closed |
| Forge/Hydra runnable claims | RED | no fresh run receipt/verifier/artifact hash in this pass | run or quarantine; do not claim runnable |
| live trading authority | RED | requires operator/legal/exchange authority | explicit external warrant before any live path |
| revenue/external-human proof | AMBER | no active track or external receipt here | 72h external human served / first cash sprint |

## Next Slice

The next narrow PR should move to the remaining non-joined side-effect
surfaces: AgentOps runtime refs, registered holon wake scope proof,
overnight/autopilot split, Forge/Hydra quarantine-or-proof, and cron/provider
rotator runtime wrapping. Keep bridge and dashboard surfaces projection-only
unless a single RuntimeState owner is selected.
