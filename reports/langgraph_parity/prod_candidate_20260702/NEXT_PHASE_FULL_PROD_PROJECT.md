# Next Phase Project: LangGraph Runtime To Full Production

- UTC: 2026-07-01T15:08:33Z
- candidate_track_id: `langgraph-runtime-prod-20260702`
- current_branch: `codex/langgraph-prod-candidate-20260702`
- target: production-trusted LangGraph runtime cockpit, not just local parity proof.

## Objective

Turn the current candidate into a production-ready runtime substrate where multi-agent LangGraph execution, memory context, provider truth, A2A readiness, operator controls, and cockpit inspection all run through one audited spine.

## Definition Of Done

1. One branch is mergeable against current `main`.
2. CI reports checks for the branch and all required checks pass.
3. Local `make agent-build-closeout` passes with semgrep either installed or explicitly covered by CI.
4. Runtime cockpit proof includes a browser-driven dashboard smoke against a running server, not only direct FastAPI route handlers.
5. A real or hermetic NATS/A2A production-matrix decision is made and recorded.
6. `ACTIVE_TRACK.yaml` either opens `langgraph-runtime-prod-20260702` as ACTIVE or records why it remains a candidate.
7. Operator can start from the worktree README/report and know exactly what command verifies each claim.

## Project Phases

### Phase 1: Branch Truth And CI

- Push `codex/langgraph-prod-candidate-20260702`.
- Open a new draft PR or supersede PR #732.
- Confirm GitHub checks appear.
- Resolve any CI-only failures before adding feature scope.

Acceptance:

- PR is not reported as `CONFLICTING`.
- CI has visible checks.
- `git status --short` is clean locally.

### Phase 2: Browser Cockpit Proof

- Launch API/dashboard in a controlled local test harness.
- Seed or run a blocking `SUPERVISOR` graph through the canonical runtime DB.
- Use Playwright to load `/dashboard/runtime`.
- Assert active run, active agent, topology state, checkpoint, and event rows are visible while the graph is still running.
- Exercise approve/reject/resume controls where applicable.

Acceptance:

- Browser proof fails if dashboard reads a side store.
- Browser proof fails if the graph is only visible after completion.
- Screenshot or JSON receipt is committed under `reports/langgraph_parity/prod_candidate_20260702/`.

### Phase 3: NATS/A2A Decision

- Re-run the NATS live-production proof from `ca297f584`.
- Resolve conflicts in `Makefile`, `ACTIVE_TRACK.yaml`, governance projections, `a2a_send.py`, and NATS tests with operator-approved semantics.
- If NATS is a dependency, fold it into this candidate.
- If NATS is a sibling, record a dependency edge and keep this branch focused.

Acceptance:

- No unresolved governance projection conflict.
- NATS decision is captured in a receipt.
- A2A strict readiness remains green or has a precise blocker.

### Phase 4: Runtime Hardening

- Add migration/backfill checks for `RuntimeStateStore` schema additions.
- Add restart/resume proof over a persisted DB path owned by the repo test harness.
- Add failure-path proof: failed agent run, timeout, checkpoint recovery, and operator cancellation.
- Add load-bound smoke: multiple concurrent runs with active graph summaries remaining correct.

Acceptance:

- Runtime graph surfaces survive fresh process, failed runs, completed runs, and concurrent active runs.
- No dashboard-only state is introduced.

### Phase 5: Production Gate

- Run focused Python suites.
- Run dashboard unit, lint, and build.
- Run Playwright cockpit proof.
- Run `make agent-build-closeout`.
- Run active-track status checks.
- Update `ACTIVE_TRACK.yaml` and generated reports only after the previous gates pass.

Acceptance:

- Candidate can honestly move from `CANDIDATE_ACTIVE_TRACK` to `ACTIVE` or `SHIPPABLE`.
- The operator has one PR, one branch, one worktree, and one receipt chain.

## Current Risks

- Current candidate is local until pushed.
- The old PR #732 remains conflicting and should be superseded or rebased.
- NATS production evidence is related but not merged because it conflicts with governance and runtime surfaces.
- Browser-level cockpit proof is still missing.
- CI signal for this candidate has not run yet.

## First Command Set

```bash
cd /Users/dhyana/ds_langgraph_prod_candidate_20260702
git status --short --branch
.venv/bin/python -m pytest -q tests/test_runtime_live_cockpit_probe.py tests/test_runtime_graph_api.py --tb=short
npm run lint -- --quiet --prefix dashboard
npm run build --prefix dashboard
make agent-build-closeout
```
