# Runtime Spine Hardening Goal

Date: 2026-06-14 JST
Status: long-running /goal handoff spec
Baseline: 54/100 production-readiness for `runtime-truth-spine-adoption-2026-06`

## Objective

Harden the Dharma Swarm runtime spine from the audited 54/100 baseline into a
coherent, live, governed, tested substrate. Do not inflate the score from
track labels, shippable-pattern checks, or old receipts. Raise it only when a
fresh command, test, runtime DB query, live process check, dashboard/API check,
or receipt proves the next invariant.

The operator has explicitly said the current 11 active tracks are not the
blocker for this phase. Treat WIP count as context, not as the hardening gate.

## Runnable Goal Draft

```text
/goal
Run the Runtime Spine Hardening mission from:

docs/agent_tasks/2026-06-14_runtime_spine_hardening_goal.md

Start from the audited 54/100 runtime-spine production-readiness baseline.
Continue for a long, meticulous hardening pass until the runtime spine is
materially stronger or blocked by a concrete external constraint.

Primary mission:
Make the runtime spine a default, observable, receipted substrate across
orchestrator dispatch, A2A dispatch, runtime receipts, NATS bridge state,
dashboard/control-surface truth, terminal/composer runtime claims, provider
model reporting, and governance declarations.

Rules:
- Code changes are allowed only when they directly harden runtime-spine
  adoption, receipts, live-process truth, or operator-surface honesty.
- Do not create a new truth store, new command spine, new receipt hierarchy, or
  parallel governance surface.
- Preserve unrelated user and agent work.
- Do not treat 11 active tracks as a blocker in this run.
- Do not claim score movement without executable evidence.
- Do not start standing autonomy, external outreach, spending, trading,
  protected identity edits, or destructive cleanup.

Definition of done:
- Active track still records the 54/100 baseline unless fresh gates justify a
  higher score.
- `scripts/governance/spine_bypass_report.py` has fewer production bypasses,
  or remaining bypasses are explicitly quarantined with owner and next receipt.
- Orchestrator/A2A/agent-runner dispatch truth is clearer: default spine path,
  opt-in path, or legacy path is machine-checkable.
- Runtime DB receipt coverage and missing machine fields are measured before
  and after changes.
- Live process truth is reconciled across live_ops census, status scripts,
  process table, ports, and dashboard/API surfaces.
- Dashboard and terminal/composer surfaces cannot show stale or fake-green
  runtime claims without age/source/risk labels.
- Verification commands, DB queries, response bodies, and receipt paths are
  included in the closeout.
```

## Starting Evidence

- Audit verdict: 54/100, not production-ready as a whole-repo runtime substrate.
- Rejected claim: 88/100 production-ready.
- Runtime DB audit at baseline: 4437 delegation runs, 465 with `receipt_json`,
  6625 runtime receipts, 14 idempotency records, 3068 execution identities.
- Known adoption gap: `spine_bypass_report.py` reports 7 submit sites, 1
  spine-adopted, 5 intentional migration bypasses, 0 unknown.
- Live substrate pieces exist: local NATS, dashboard API/web, Dharma daemon,
  Hermes A2A card, Composer Bridge.
- Live truth is split: A2A bridge/process/status surfaces disagree; terminal
  TUI and composer background loop are stopped; some old logs still look green.

## Runtime Invariants

1. Default dispatch invariant: every production dispatch path is either
   spine-native by default or explicitly quarantined as legacy/non-production.
2. Receipt invariant: every side-effecting runtime action has one canonical
   owner receipt, idempotency before side effects, and projection-only
   dashboard/file artifacts.
3. Live truth invariant: live process state, status scripts, ports, runtime DB,
   dashboard API, and onboarding/orientation output cannot disagree silently.

## Phases

### Phase 0 - Reconfirm Baseline

Run and record:

```bash
make onboard
make orient
make hygiene
python3 scripts/governance/check_track_status.py
python3 scripts/governance/render_active_track_includes.py --check
python3 scripts/governance/spine_bypass_report.py
python3 scripts/runtime/live_ops_census.py
git status --short --branch
git worktree list
gh pr list --repo AmitabhainArunachala/dharma_swarm --state open --limit 30 --json number,title,isDraft,mergeable,headRefName,updatedAt,url
```

If `make hygiene` is absent, record that exact failure and run the repo's
advertised substitute checks. Do not edit generated governance reports unless
the run explicitly owns that regeneration.

Also query `/Users/dhyana/.dharma/state/runtime.db` for delegation-run receipt
fill, latest runtime receipts, idempotency records, and execution identities.

### Phase 1 - Governance Truth

- Keep `runtime-truth-spine-adoption-2026-06` marked at 54/100 unless a gate
  below is freshly proven.
- Render downstream docs only if the repo requires generated surfaces to carry
  the baseline.
- Make any `88/100` claim point back to the disputed audit, not to current
  readiness.
- Do not close or demote tracks just to satisfy WIP count.

### Phase 2 - Bypass Drain

- Inspect every `.submit()` path reported by `spine_bypass_report.py`.
- For each bypass, choose one:
  - migrate to `invoke_agent`;
  - keep inner owner and associate canonical receipt;
  - quarantine as legacy/non-production with a test that blocks fake adoption.
- Target for next score movement: intentional production bypasses reduced from
  5 to 0, or all remaining entries have explicit quarantine status.

### Phase 3 - Dispatch Adoption

- Orchestrator: prove whether `DHARMA_SPINE_DISPATCH` is default, opt-in, or
  disabled in the live daemon path.
- A2A bridge: prove whether `submit_via_spine` is used by live ingress, not
  only tests.
- Agent runner: do not count import-only spine references as adoption.
- Provider/model: prove actually served provider/model flows into persisted
  receipts after merge/restart, not only branch tests.

### Phase 4 - Receipt Saturation

- Measure baseline and post-change receipt coverage.
- Add or repair tests for `mission_id`, `idempotency_record`, `artifact_refs`,
  receipt JSON association, and duplicate-dispatch prevention.
- Do not mint a second canonical receipt hierarchy.

### Phase 4a - Installed CLI Target Truth

Treat runtime CLIs as runtime surfaces. In particular, `ds-goal` can produce
major runtime receipts, so the installed wrapper target must be reconciled with
the audited checkout.

Current known risk:

- `/Users/dhyana/.dharma/bin/ds-goal` prefers
  `/Users/dhyana/dharma_swarm_main` when that checkout exists.
- The current audited checkout is `/Users/dhyana/dharma_swarm`.
- The stale target can emit `task_claim` / `delegation_run` receipts without
  `side_effect_key`.

Safe checks:

```bash
python3 scripts/runtime/live_ops_census.py --write
make orient
python3 scripts/governance/ds_goal_longrun_preflight_report.py --strict
make ds-goal-longrun-preflight-check
python3 scripts/runtime/ds_goal_longrun_preflight.py --repo-pin /Users/dhyana/dharma_swarm --json
env -u DHARMA_SWARM_REPO python3 scripts/runtime/autonomy_spine.py init --state-root /private/tmp/ds-goal-preflight-block-proof/state --kernel-store /private/tmp/ds-goal-preflight-block-proof/kernel --mission-id wrapper-proof --goal "Wrapper proof" --json
env -u DHARMA_SWARM_REPO python3 scripts/runtime/autonomy_spine.py run --state-root /private/tmp/ds-goal-preflight-block-proof/state --kernel-store /private/tmp/ds-goal-preflight-block-proof/kernel --mission-id wrapper-proof --max-wakes 1 --json
python3 scripts/governance/ds_goal_longrun_preflight_report.py --strict --prevention-receipt-root /private/tmp/ds-goal-preflight-block-proof/state
DHARMA_SWARM_REPO=/Users/dhyana/dharma_swarm /Users/dhyana/.dharma/bin/ds-goal init --state-root /private/tmp/ds-goal-wrapper-proof/state --kernel-store /private/tmp/ds-goal-wrapper-proof/kernel --mission-id wrapper-proof --goal "Wrapper proof" --json
DHARMA_SWARM_REPO=/Users/dhyana/dharma_swarm /Users/dhyana/.dharma/bin/ds-goal run --state-root /private/tmp/ds-goal-wrapper-proof/state --kernel-store /private/tmp/ds-goal-wrapper-proof/kernel --mission-id wrapper-proof --max-wakes 1 --json
python3 scripts/governance/runtime_receipt_coverage_report.py --db /private/tmp/ds-goal-wrapper-proof/state/.runtime/runtime.db --strict
```

Do not edit `/Users/dhyana/.dharma/bin/ds-goal` or patch
`/Users/dhyana/dharma_swarm_main` without explicit operator approval. Until the
wrapper target is converged or intentionally pinned by environment, keep
`cli.ds_goal` proof gaps visible in live ops, control-surface Runtime Proof, and
dashboard Runtime Proof, and do not raise readiness. A pinned temp proof may
show that current receipts carry `ds_goal_longrun_preflight` context, but that
is receipt-context evidence only; it does not repair the global live DB or make
the installed wrapper default production-ready. An unpinned run should fail
closed with `status=preflight_blocked` before creating runtime DB, idempotency,
or kernel side effects. The preflight report can scan that mission ledger with
`--prevention-receipt-root` and should show `valid_preflight_blocks=1`.

### Phase 5 - Live Bridge And Process Truth

- Reconcile live ops census, status scripts, `ps`, `lsof`, NATS consumers,
  bridge heartbeats, and dashboard API.
- Fix status scripts or census logic if they misclassify a live bridge.
- Do not claim A2A semantic collaboration from transport publish or handler ack
  alone.
- Safe no-start checks for A2A inbox bridge truth:

```bash
python3 scripts/runtime/live_ops_census.py --write
bash scripts/status_a2a_inbox_bridge_tmux.sh
python3 scripts/governance/spine_dispatch_mode_report.py --strict
pytest -q tests/test_live_ops_census.py -k 'a2a_bridge or nats_receipts' --tb=short
```

These checks may inspect the tmux session, heartbeat, latest bridge receipt,
and NATS durable consumer. They must not start the bridge or treat an
inspectable consumer as a semantic reply from a peer model.

### Phase 5a - Controlled Daemon Proof Protocol

This phase requires explicit operator approval because it restarts the standing
daemon. Do not run it automatically during read-only hardening.

Preflight:

```bash
python3 scripts/governance/spine_dispatch_mode_report.py --strict
python3 scripts/runtime/live_ops_census.py --write
make orient
```

Approved restart and proof loop:

```bash
launchctl kickstart gui/$UID/com.dharma.swarm
sleep 5
python3 scripts/runtime/live_ops_census.py --write
python3 scripts/governance/spine_dispatch_mode_report.py --strict
curl --max-time 3 -fsS http://127.0.0.1:7433/health
python3 scripts/runtime/runtime_lifecycle_receipt_probe.py --producer orchestrator-spine --allow-live
python3 scripts/governance/runtime_receipt_coverage_report.py --strict
make onboard
make orient
```

Do not raise the score from 70 to 75 unless all of these are true:

- `spine_dispatch_mode_report.py --strict` still passes and
  `daemon_health_self_report` is `spine_enabled_self_report`.
- `/health` returns a non-secret `runtime_dispatch` block with
  `spine_dispatch_enabled=true`.
- A fresh daemon/default or explicitly equivalent orchestrator-spine receipt is
  persisted and tied to the runtime DB coverage report.
- The 70->75 receipt coverage gate passes, or the report names a narrower,
  operator-accepted scoped gate with exact run id and residual global blocker.

### Phase 6 - Operator Surfaces

- Dashboard/control-surface cards must show source age, source errors, and
  state distinctions: sent, delivered, domain receipt, semantic reply,
  completed.
- Terminal/composer surfaces must be either live with fresh receipts or marked
  stopped/stale. Old `100/100` logs cannot function as current truth.
- Runtime Proof digest checks:

```bash
bun test dashboard/src/lib/controlSurfaceRuntimeEvidence.test.ts
python3 -m py_compile dharma_swarm/operator_core/control_surface_live_ops.py
pytest -q tests/test_live_ops_census.py -k 'ds_goal_live_ops_row_projects_wrapper_state_evidence or a2a_bridge' --tb=short
```

Dashboard/control-surface projection must derive from live-ops census rows.
Do not add a second dashboard truth store for bridge, daemon, receipt, or
provider/model state. `cli.ds_goal` projection must show target mismatch,
receipt hardening state, longrun preflight status, and the safe pin from the
live-ops owner without treating a pin as default-path production readiness.

### Phase 7 - Architecture Hardening

- Keep changes narrow, but identify the extraction plan for `runtime_state.py`
  and `terminal_bridge.py` if they block observability or tests.
- Prefer small store/projection/adaptor seams over new framework layers.
- Run module-budget and focused runtime tests after edits.

## Score Gates

- 54 -> 60: baseline is visible in active governance; no current 88/100 claim
  remains unqualified.
- 60 -> 65: bypass list has no unknowns and every intentional bypass is either
  reduced or quarantined with a test/owner.
- 65 -> 70: orchestrator and A2A live ingress have proven default spine or
  explicitly marked legacy paths.
- 70 -> 75: runtime receipt fields and idempotency proof cover the major
  command/dispatch surfaces.
- 75 -> 80: live process truth agrees across census, status scripts, ports,
  dashboard API, and NATS consumers for one fresh run.
- 80 -> 88: daemon-after-merge/restart receipts prove provider/model truth,
  receipt saturation target is met, no fake-green operator surfaces remain, and
  the spine serves dashboard, terminal, agents, bridges, provider routing,
  longruns, governance, and external-human workflow gates without bypasses.

## Suggested Focused Tests

Run what exists, add only narrow missing tests:

```bash
pytest -q tests/test_spine_adoption_dispatch.py tests/test_spine_persistence_invariant.py tests/test_orchestrator_spine_dispatch.py
pytest -q tests/test_a2a_send.py tests/test_a2a_inbox_bridge.py tests/test_a2a_reply_capture.py tests/test_a2a_domain_reply_worker.py
pytest -q tests/test_runtime_truth_projection_fields.py tests/test_control_surface.py tests/test_operator_core_contracts.py
make nats-substrate-contract
make uplift-guards
make module-budget
make test-hygiene
```

## Closeout Required

Close with:

- starting score and ending score;
- exact score gates passed;
- changed files;
- commands run and exit status;
- runtime DB before/after counts;
- live server/process evidence;
- remaining bypasses;
- remaining blockers before production readiness.
