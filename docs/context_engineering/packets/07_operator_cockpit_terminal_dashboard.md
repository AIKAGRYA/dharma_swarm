# Packet 07: Operator Cockpit, Terminal, Dashboard, And API

Packet ID: `ctx.operator-cockpit-terminal-dashboard`

Use when touching FastAPI routers, dashboard pages/nav, terminal UI, live ops
cockpit, control surfaces, or operator-visible state.

Do not use for backend runtime truth semantics unless the task touches the
runtime owners. Use `ctx.runtime-spine-a2a-nats` for receipt-layer semantics.

## Authority Model

- Surface owner: `ACTIVE_SURFACE_MANIFEST.yaml`
- API owner: `api/main.py` and `api/routers/**`
- Dashboard owner: `dashboard/src/**`
- Terminal owner: `terminal/src/**`, `docs/ops/TMUX_AGENT_SUBSTRATE.md`
- State owner: live ops census, runtime DB, API probes, dashboard tests
- Proof owner: tests, screenshots when UI is involved, live ops receipts

Core invariant: operator surfaces must show truth from owners without becoming
authority themselves.

## Mission

Make the operator see what is real, quickly, without hiding stale state or
mixing authority layers. UI work should be dense, inspectable, and operational,
not decorative.

## First Reads

L0 Safety:

- `make onboard`
- `ACTIVE_SURFACE_MANIFEST.yaml`

L1 Route:

- `docs/ops/LIVE_OPS_COCKPIT.md`
- `docs/architecture/CONTROL_SURFACE.md`
- active tracks for terminal/dashboard/cockpit

L2 Owners:

- `api/main.py`
- relevant `api/routers/*.py`
- `dashboard/src/lib/dashboardNav.ts`
- `dashboard/src/lib/controlPlane*.ts`
- relevant `dashboard/src/app/**`
- `terminal/src/app.tsx`
- `terminal/src/components/**`

L3 Evidence:

- `reports/dashboard/**`
- `reports/terminal/**`
- `/Users/dhyana/.dharma/ops/live_process_census.json`
- frontend test output

L4 Search:

- `rg -n "router|include_router|dashboardNav|control-surface|cockpit|live ops" api dashboard terminal docs reports tests`

L5 Seat:

- No named seat by default. If assigning UI work, route to frontend/cockpit
  builder only with a clean surface list.

## Live Probes

```bash
make onboard
python3 scripts/runtime/live_ops_census.py --help
```

Backend:

```bash
pytest tests/test_pool_router.py tests/test_gaia_platform.py
```

Dashboard/terminal:

```bash
npm --prefix dashboard run test
npm --prefix terminal test
```

When changing visible UI, run the local app and inspect with browser automation
or screenshots before calling it done.

## Retrieval Contract

- Query: "ACTIVE_SURFACE_MANIFEST dashboard_surfaces api_routers health checks"
  Source family: surface manifest and API/router tests.
- Query: "live ops cockpit read-only operations control"
  Source family: live ops docs and census receipt.
- Query: "terminal tmux substrate compact shell golden"
  Source family: terminal docs, tests, golden captures.

## Operating Loop

1. Find the surface in `ACTIVE_SURFACE_MANIFEST.yaml`.
2. Confirm matching API/router/nav/test owners.
3. Inspect current UI/state path.
4. Make the smallest surface change.
5. Run relevant unit tests.
6. For visual changes, run/inspect the UI.
7. Handoff with route, API dependency, and verification.

## Guardrails

- Do not add a dashboard surface without manifest/nav/API agreement.
- Do not use page text to explain how to use the app unless the product surface
  naturally requires it.
- Do not show stale runtime claims without age/freshness.
- Do not collapse state owners into dashboard state.
- Do not leave UI text overflowing or controls unverified on mobile/desktop.
- Do not hardcode mock data into live truth surfaces unless labeled as mock.

## Context Budget

- Tiny: `make onboard`, surface manifest, this packet.
- Standard: tiny plus route/page/router/lib/test files.
- Deep: standard plus live ops docs, census receipt, screenshots/test artifacts.

## Done Criteria

Complete means:

- manifest, API, nav, and page agree;
- tests run for touched stack;
- UI inspected when visual output changed;
- state freshness is visible or documented;
- no new authority surface is created.

## Agent Prompt Block

```text
You are working in Dharma Swarm using context packet ctx.operator-cockpit-terminal-dashboard.
Start with make onboard and ACTIVE_SURFACE_MANIFEST.yaml. For any operator
surface, keep manifest, API router, nav, tests, and rendered page in agreement.
Do not make dashboards authority. Show freshness and source boundaries. Run
relevant tests and inspect visual changes before handoff.
```

## Handoff Receipt Shape

```json
{
  "packet_id": "ctx.operator-cockpit-terminal-dashboard",
  "surface_id": "",
  "routes": [],
  "api_dependencies": [],
  "files_changed": [],
  "tests_run": [],
  "visual_verification": "",
  "state_owner": "",
  "remaining_ui_risk": ""
}
```
