# CI Unblock PR #28

## Changed Files

- `.github/workflows/tests.yml`
- `benchmarks/gauntlet.py`
- `dashboard/src/app/dashboard/agents/[id]/config/page.tsx`

## Failure Reasons

### dashboard

The dashboard job failed at `npm ci` because the repo uses React 19 while `@visx/heatmap@3.12.0` declares React 16/17/18 peer ranges. npm's default peer dependency resolver rejects that tree.

After the install was repaired locally, the next hard dashboard gate failed in `npm run lint -- --quiet`: `AgentConfigPage` returned before two `useQuery` hooks, violating React hook ordering.

### gauntlet-tier1

`_t1_telos_gate_enforced` constructed `GateProposal(action=..., content=..., agent_id=...)`. `GateProposal` is currently the custom-gate registry model and accepts `name`, `tier`, `justification`, and `trigger_patterns`, not action-evaluation fields. The current action-evaluation API is `TelosGatekeeper.check(action=..., content=...)`, returning `GateCheckResult.decision`.

## Fixes

### dashboard

- Changed the workflow dashboard install step to `npm ci --legacy-peer-deps`.
- Fixed the exposed dashboard hook-order violation by computing a nullable `agentId`, keeping both `useQuery` calls unconditional, then returning `null` after hooks when `agent` is absent.

### gauntlet-tier1

- Updated stale gauntlet harness calls to use `TelosGatekeeper.check(action=..., content=...)`.
- Replaced stale `result.approved` checks with `result.decision != GateDecision.ALLOW`.
- Updated the same stale construction in the tier-4 adversarial gauntlet path while staying inside `benchmarks/gauntlet.py`.

## Validation

- `python -m compileall dharma_swarm benchmarks tests` - passed
- `python -m pytest tests/test_telos_gates.py -q --tb=short` - 65 passed, 1 warning
- Tier-1 gauntlet workflow snippet with `HOME=/tmp/dharma_swarm_ci_unblock_home` - passed, 2/2 tasks
- `npm ci --legacy-peer-deps` in `dashboard/` - passed
- `npm run lint -- --quiet` in `dashboard/` - passed
- `npm run build` in `dashboard/` - passed

## PR #28 Follow-Up

After this branch is merged to `origin/main`, PR #28 should be rebased onto the new main and pushed normally. The CI workflow repair is on main already; this branch addresses the current failing check bodies.
