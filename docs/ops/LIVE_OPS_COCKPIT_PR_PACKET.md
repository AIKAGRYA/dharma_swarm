# Live Ops Cockpit v1 PR Packet

Status: PR-hardening packet for `codex/live-ops-cockpit-v1`.

## Purpose

Live Ops Cockpit v1 gives the operator one read-only cockpit for local swarm
operations after restart, travel, or multi-agent drift. The branch folds the
existing authority stack into a deterministic census receipt and projects that
receipt into the Control Surface dashboard.

This packet is the merge-facing evidence bundle. It is not a supervisor and
does not grant process-control authority.

## Non-Goals

- Do not start, stop, restart, kill, or message live processes.
- Do not call live Palantir, external NATS, Temporal, paid LLMs, or GitHub merge
  APIs.
- Do not make filesystem mirrors source-of-truth.
- Do not make NATS workflow truth.
- Do not make tmux task truth.
- Do not authorize money, outreach, merges, process killing, VPS changes, or
  external actions without the operator.
- Do not add a new substrate or new agents.

## Changed Files

Core:

- `scripts/runtime/live_ops_census.py`
- `dharma_swarm/operator_core/control_surface.py`
- `dharma_swarm/operator_core/control_surface_live_ops.py`
- `dharma_swarm/operator_core/control_surface_models.py`
- `scripts/governance/agent_onboard.py`

Dashboard:

- `dashboard/src/app/dashboard/cockpit/page.tsx`
- `dashboard/src/app/dashboard/control-surface/page.tsx`
- `dashboard/src/components/cockpit/OpsRunbookPanel.tsx`
- `dashboard/src/components/cockpit/SystemTruthMatrix.tsx`
- `dashboard/src/lib/dashboardNav.ts`
- `dashboard/src/lib/dashboardNav.test.ts`

Docs and manifests:

- `ACTIVE_SURFACE_MANIFEST.yaml`
- `docs/architecture/NAVIGATION.md`
- `docs/docops/AUTO_INVENTORY.md`
- `docs/governance/CANONICAL_DOC_STACK.md`
- `docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md`
- `docs/governance/SOVEREIGN_MANIFEST.md`
- `docs/governance/VENTURE_CELL_PORTFOLIO.yaml`
- `docs/ops/LIVE_OPS_COCKPIT.md`
- `docs/ops/LIVE_OPS_COCKPIT_PR_PACKET.md`
- `docs/ops/TMUX_AGENT_SUBSTRATE.md`

Tests:

- `tests/test_agent_onboard.py`
- `tests/test_control_surface.py`
- `tests/test_live_ops_census.py`

## Current Census Snapshot

Latest receipt:

```text
~/.dharma/ops/live_process_census.json
```

Current surfaces from the latest local receipt:

- Live: `substrate.dharma_daemon`, `transport.nats`,
  `evidence.a2a_mirrors`, `evidence.nats_receipts`,
  `external.hermes_a2a`, `dashboard.local`
- Stale: `remote.agni`
- Blocked: `revenue.cashclaw_gate`
- VPS candidate: `remote.agni`
- Operator authority required: `revenue.cashclaw_gate`, `remote.agni`,
  `agent.merge_master_mike`, `load.colima_openclaw`

These are observations from the local machine. They are not promises that a
different checkout, laptop state, or VPS state has the same status.

## Verification Commands

Required before PR handoff:

```bash
make onboard
/Users/dhyana/dharma_swarm/.venv/bin/python scripts/runtime/live_ops_census.py --write
/Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_live_ops_census.py -q
/Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_control_surface.py::TestDashboardControlSurfacePage -q
/Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_agent_onboard.py::test_onboard_renders_required_sections -q
/Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_agent_onboard.py::test_onboard_does_not_write_to_owners -q
/Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_agent_onboard.py -q
bun test dashboard/src/lib/dashboardNav.test.ts
/Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_control_surface.py -q
/Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_live_ops_census.py tests/test_agent_onboard.py tests/test_control_surface.py -q
git diff --check
```

Dashboard verification:

```bash
cd dashboard
npm run lint
npm run build
```

## Latest Verification Results

Last verified locally on the clean branch worktree:

```text
make onboard
  PASS — renders LIVE OPS COCKPIT with 15 surfaces, 4 operator gates, 1 VPS candidate

/Users/dhyana/dharma_swarm/.venv/bin/python scripts/runtime/live_ops_census.py --write
  PASS — wrote /Users/dhyana/.dharma/ops/live_process_census.json

/Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_live_ops_census.py -q
  PASS — 13 passed

/Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_control_surface.py::TestDashboardControlSurfacePage -q
  PASS — 9 passed

/Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_control_surface.py::TestControlSurfaceAPI -q
  PASS — 6 passed in 244.43s

/Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_control_surface.py -q
  PASS — 91 passed in 884.70s

/Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_live_ops_census.py tests/test_agent_onboard.py tests/test_control_surface.py -q
  PASS — 111 passed in 972.67s after restack onto current origin/main

/Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_agent_onboard.py::test_onboard_renders_required_sections -q
  PASS — 1 passed

/Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_agent_onboard.py::test_onboard_does_not_write_to_owners -q
  PASS — 1 passed

/Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_agent_onboard.py -q
  PASS — 7 passed in 141.54s

bun test dashboard/src/lib/dashboardNav.test.ts
  PASS — 4 passed

/Users/dhyana/dharma_swarm/.venv/bin/python scripts/docops/check_docops_integrity.py --write-auto-sections
  PASS — refreshed DocOps auto inventory and updated governed count assertions

direct control-surface projection smoke
  PASS — live_ops_rows=15, has_live_ops_source=True, human_decision_rows=7

curl http://127.0.0.1:3420/dashboard/cockpit
  PASS — already-running dashboard route responds

curl http://127.0.0.1:8420/api/control-surface/summary
  STALE-RUNTIME — already-running API responds, but sources_consulted does not
  include live_ops_census; do not use this process as branch evidence without
  an operator-approved restart

adapter extraction smoke
  PASS — control_surface.py reduced to 1009 LOC; live ops adapter isolated in control_surface_live_ops.py

git diff --check
  PASS

Context+/MCP static analysis
  BLOCKED — contextplus/run_static_analysis returned Transport closed

/Users/dhyana/dharma_swarm/.venv/bin/python -m ruff check <changed Python files>
  BLOCKED — repo venv has no ruff module

/Users/dhyana/dharma_swarm/.venv/bin/python -m mypy <changed Python files>
  BLOCKED — repo venv has no mypy module
```

Dashboard dependency commands from the clean worktree:

```text
test -d dashboard/node_modules
  node_modules_missing

cd dashboard && npm run lint
  FAIL — sh: eslint: command not found

cd dashboard && npm run build
  FAIL — sh: next: command not found
```

Those dashboard failures are dependency/bootstrap failures in the clean worktree,
not cockpit source failures. Reusing the primary checkout by symlinking
`node_modules` is not acceptable evidence because Turbopack rejects the symlink:

```text
TurbopackInternalError: Symlink node_modules is invalid, it points out of the filesystem root
```

The merge packet therefore treats static route tests and direct control-surface
projection smoke checks as the available local evidence until the
clean-worktree dashboard dependency bootstrap is fixed.

## Read-Only Evidence

The hardened tests assert:

- `subprocess.run` is centralized inside `live_ops_census._run`.
- The census does not use `shell=True`, `subprocess.Popen`, `subprocess.call`,
  `os.system`, `os.kill`, or related process-control APIs.
- `_run` call sites only invoke `git`, `pgrep`, `lsof`, or `tmux`.
- `build_live_ops_census()` and CLI execution without `--write` do not create a
  receipt file.
- The only write calls in `scripts/runtime/live_ops_census.py` are inside the
  explicit `write_census()` function.
- The Control Surface live-ops adapter has no file write/delete/mkdir calls.
- The census emits the full 15-surface contract with stable fields,
  authority refs, operator-authority flags, and VPS flags.
- Displayed `restart_command` and `stop_policy` strings are not executed during
  census construction.
- Control-surface rows preserve status, evidence, source refs,
  `restart_command`, `stop_policy`, `vps_candidate`, and
  `human_authority_required`.
- `make onboard` renders the cockpit section and does not mutate owner files.
- `/dashboard/cockpit` exists and aliases the control-surface page.
- `OpsRunbookPanel` has no click handler, fetch call, browser command call, or
  child-process execution token.
- The Control Surface page and runbook panel do not import the pre-existing
  `controlPlaneShell` helper.
- The static dashboard nav and manifest both advertise Cockpit.

## Risks

- The dashboard build gate remains weaker than desired until clean-worktree
  dashboard dependencies are installed or scripted.
- Adversarial grep finds pre-existing command strings in
  `dashboard/src/lib/controlPlaneShell.ts`; the new `/dashboard/cockpit` and
  `OpsRunbookPanel` path does not import that shell.
- The cockpit is only as fresh as the latest local receipt when the dashboard API
  reads the cache.
- The already-running local dashboard/API process appears stale relative to this
  worktree: HTTP responds, but the live API summary did not include
  `live_ops_census`. Source/tests/direct Python projection are the branch
  evidence unless the operator approves a restart.
- `/dashboard/cockpit` reuses the existing Control Surface route; this is good
  for avoiding duplicate UI, but it means Control Surface regressions affect the
  cockpit.
- Process pattern matching can produce false positives or false negatives; the
  census records evidence, not authority.
- The branch imports NATS/TMUX/VentureCell authority docs from the previously
  dirty lane. They are now explicit docs in this branch, but they should still
  be reviewed as operator-facing doctrine.
- `make onboard` still reports the existing missing correlation-spine
  `A2ATaskReceipt` layer. This PR surfaces operating state; it does not close
  that runtime-truth-spine gap.

## Rollback Plan

1. Remove `/dashboard/cockpit` route and the Cockpit nav/manifest entries.
2. Remove `OpsRunbookPanel` from the Control Surface page.
3. Remove `_live_ops_census_rows` from `build_control_surface_rows`.
4. Remove `render_live_ops_cockpit()` from `agent_onboard.py`.
5. Keep or delete `docs/ops/LIVE_OPS_COCKPIT.md` depending on whether the
   operator wants the runbook retained as a plan.

No database migration or external service rollback is required.

## Operator Merge Checklist

- Confirm the branch is still based on the intended `origin/main`.
- Review that no UI code executes process-control commands.
- Review the NATS/TMUX/VentureCell docs for doctrine fit.
- Run the verification commands above.
- Confirm no `node_modules` symlink, `.next`, `__pycache__`, or timestamp-only
  generated evidence files are present.
- Confirm generated receipt writes only to `~/.dharma/ops/live_process_census.json`.

## Exactly Three Next Slices

1. Add a clean-worktree dashboard dependency/bootstrap verifier so `npm run
   build` can be run without symlink hacks.
2. Add operator-approved action packets for start/stop/restart as explicit
   proposals, while keeping the cockpit UI read-only.
3. Add a VPS migration planner that uses the census to recommend AGNI, Forge,
   CashClaw, Mike, and heavy local compute placement without executing moves.
