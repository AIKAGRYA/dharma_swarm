# Live Ops Cockpit

Status: active runbook for the read-only operator cockpit.

## Purpose

The Live Ops Cockpit gives the operator one deterministic view of local swarm
operations after restarts, travel, or multi-agent drift. It does not start,
stop, kill, message, spend, merge, or mutate anything. It reads the existing
owner files and runtime evidence, writes a census receipt, and projects that
evidence into `/dashboard/cockpit`.

## Authority Stack

Read in this order:

1. `/dashboard/cockpit`
2. `make onboard`
3. `docs/governance/ACTIVE_TRACK.yaml`
4. `ACTIVE_SURFACE_MANIFEST.yaml`
5. `docs/state/LIVE_OPS_DASHBOARD.md`
6. `docs/state/BROKEN_REGISTER.md`
7. `docs/governance/SOVEREIGN_MANIFEST.md`
8. `docs/governance/ANTI_SLOP_RULES.md`
9. `docs/governance/CANONICAL_DOC_STACK.md`
10. `docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md`
11. `docs/ops/TMUX_AGENT_SUBSTRATE.md`

`/dashboard/cockpit` is the human front door. `make onboard` is the agent
intake door: it renders the same authority stack for agents, but it is not the
operator UI. The files above own intent, declared surfaces, operating state,
known breaks, doctrine, anti-duplication rules, transport boundaries, and
terminal-persistence boundaries.

## Census Receipt

Run:

```bash
python3 scripts/runtime/live_ops_census.py --write
```

Receipt:

```text
~/.dharma/ops/live_process_census.json
```

The census is read-only. Its probes inspect process names, listening ports,
tmux sessions, and known receipt files. It records status, desired state,
evidence, authority refs, restart command text, stop policy text, freshness,
operator-authority flags, VPS-candidate flags, and local-heavy-load flags.

## Dashboard

Open:

```text
/dashboard/cockpit
```

The route uses the operator-coherence API:

```text
/api/operator-coherence/report
```

The cockpit highlights:

- Live
- Stopped
- Stale
- Blocked
- Needs John
- VPS Candidate
- Heavy Local Load

The runbook panel displays commands and stop policies as text only. It does
not execute commands.

## Before Flight Mode

Use the top runbook strip before travel or sleep:

Keep alive:

- Dharma daemon
- local NATS JetStream when A2A contact is needed
- dashboard API and web

Keep blocked unless explicitly approved:

- CashClaw / revenue outreach
- AGNI real-money or trading action
- Merge Master Mike automerge authority

Review or refresh:

- AGNI watcher receipts and feed freshness
- Forge Hydra latest handoff and heartbeat
- tmux cockpit lanes
- terminal TUI only if it is the active operator surface

Optional local load:

- Colima / OpenClaw VM, if not being actively used

## Guardrails

- NATS is live transport, not workflow truth.
- tmux is terminal persistence, not task truth.
- Filesystem mirrors are evidence, not authority.
- RuntimeStateStore owns durable runtime facts.
- Operator approval is required for money, outreach, merges, process killing,
  VPS changes, and external actions.
- Kill nothing immediately. Classify, quarantine, or recommend.

## Verification

Run:

```bash
make onboard
/Users/dhyana/dharma_swarm/.venv/bin/python scripts/runtime/live_ops_census.py --write
/Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_live_ops_census.py -q
/Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_control_surface.py::TestDashboardControlSurfacePage -q
/Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_control_surface.py::TestControlSurfaceAPI -q
/Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_control_surface.py -q
/Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_agent_onboard.py::test_onboard_renders_required_sections -q
/Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_agent_onboard.py::test_onboard_does_not_write_to_owners -q
/Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_agent_onboard.py -q
bun test dashboard/src/lib/dashboardNav.test.ts
/Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_live_ops_census.py tests/test_agent_onboard.py tests/test_control_surface.py -q
git diff --check
```

If the dashboard API is already running, restart it only with explicit operator
approval. Without a restart, direct Python/API tests still prove the branch
projection, but the running process may show the old code until reload.

Dashboard lint/build require dashboard dependencies in the clean worktree. If
`dashboard/node_modules` is missing, `npm run lint` and `npm run build` fail at
tool bootstrap (`eslint` / `next` not found), not at cockpit source validation.
Do not use a symlinked `node_modules` as build evidence; Turbopack rejects it.
