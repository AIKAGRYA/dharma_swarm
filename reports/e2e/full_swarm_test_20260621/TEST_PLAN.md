# Full Swarm E2E Organism Gauntlet Test Plan — 2026-06-21

## Setup/access confirmation

- Branch/worktree under test: `/home/ubuntu/pr-work/full-swarm-e2e-20260621`, branch `devin/full-swarm-e2e-test-20260621`, `origin/main` commit `726bc9d4`.
- Local dev auth: API middleware is expected to allow local `/api/*` calls when `DASHBOARD_API_KEY` is unset.
- Available credentials by name only: `DEVIN_API_KEY`, `DEVIN_NATS_URL`, `DEVIN_NATS_USER`, `DEVIN_NATS_PW`.
- Missing/degraded credentials: no repo secrets file and no provider keys found by env-name inventory (`OPENAI_*`, `ANTHROPIC_*`, `OPENROUTER_*`, etc.). Provider-backed execution will be measured as degraded/no-key behavior unless the repo has a local/stub path.
- Dashboard dependencies were installed in this worktree with `npm --prefix dashboard install --legacy-peer-deps`; install completed with Node engine/vulnerability warnings that will be recorded.
- Isolated runtime state root for mutable local runtime state: `/home/ubuntu/pr-work/full-swarm-e2e-20260621/.e2e_state/full_swarm_test_20260621`.
- Permanent evidence root: `reports/e2e/full_swarm_test_20260621/`.
- Safety: no external outreach, payments, production deploys, live GitHub mutation, or non-shadow self-evolution apply. All first-reader/outreach artifacts must say `not sent`.

## Source evidence used to build this plan

- User attachment: `/home/ubuntu/attachments/51cfb88f-c256-4a6d-bb2e-a789da44b9df/pasted-1782049522859.md:1-457`.
- Repo single-door contract and entrypoints: `README.md`, `Makefile`, `run_operator.sh`.
- Owner docs to render/compare: `docs/governance/ACTIVE_TRACK.yaml`, `ACTIVE_SURFACE_MANIFEST.yaml`, `docs/state/LIVE_OPS_DASHBOARD.md`, `docs/state/BROKEN_REGISTER.md`, `docs/governance/SOVEREIGN_MANIFEST.md`, `docs/governance/VENTURE_CELL_PORTFOLIO.yaml`.
- Backend/control surface: `api/main.py`, `api/routers/control_surface.py`, `api/routers/commands.py`, `api/routers/opportunities.py`, `api/routers/health.py`.
- Dashboard paths/hooks: `dashboard/src/app/dashboard/*`, `dashboard/src/hooks/useControlSurface.ts`, `dashboard/src/hooks/useRuntimeControlPlane.ts`, `dashboard/src/hooks/useTasks.ts`, `dashboard/src/hooks/useOverview.ts`, cockpit components under `dashboard/src/components/cockpit/`.
- Runtime/spine/memory/A2A: `dharma_swarm/runtime_state.py`, `dharma_swarm/spine/**`, `dharma_swarm/agent_runner.py`, `dharma_swarm/orchestrator.py`, `dharma_swarm/a2a/**`, `scripts/operator_prod_smoke.py`, `tools/spine_adoption_metric.py`.
- Existing repo skills consulted: `.agents/skills/testing-opportunity-loop/SKILL.md`, `.agents/skills/testing-spine/SKILL.md`, `.agents/skills/testing-provenance/SKILL.md`, `.agents/skills/testing-governance-gates/SKILL.md`.

## Test 1 — Single-door reality landing and organism map

Goal: prove whether `make onboard`/`make orient`/`make status` accurately orient an agent before any deeper action.

Steps:
1. Save raw outputs of `git status --short`, `git rev-parse --show-toplevel`, `git rev-parse HEAD`, `PATH=/home/ubuntu/repos/dharma-swarm/.venv/bin:$PATH make onboard`, `make orient`, and `make status` under `00_preflight/`.
2. Parse owner docs and create `00_preflight/PREFLIGHT_SUMMARY.md` and `01_map/ORGAN_SURFACE_MAP.md`.
3. Compare `make onboard` claims against owner files and actual filesystem paths for at least these organs: active tracks, live ops dashboard, broken register, surface manifest, runtime spine, memory kernel, A2A/NATS, DGC/self-evolution.

Pass/fail criteria:
- Pass if each raw preflight command exits 0 and its output is saved.
- Pass if the map lists at least 10 organs with command/endpoint, owning files, expected evidence, and exercise depth.
- Degraded if a command exits nonzero but outputs enough evidence to continue.
- Fail if onboard/orient cannot run at all or if owner docs required by README are missing.

Evidence:
- `00_preflight/*.txt`
- `00_preflight/PREFLIGHT_SUMMARY.md`
- `01_map/ORGAN_SURFACE_MAP.md`

## Test 2 — Canonical operator boot, API/control-surface truth, and restart survival

Goal: boot the system through the canonical backend path and verify live APIs/control-surface envelopes, source errors, stream behavior, and restart recovery.

Steps:
1. Start backend using `bash run_operator.sh --background` with isolated env vars where respected: `DHARMA_STATE_DIR`, `DHARMA_OPS_DIR`, and `PYTHONPATH` pointing at the worktree.
2. Record PID/log path from `~/.dharma` or the launcher output; copy first/last 200 log lines to `02_operator/`.
3. Hit and save: `/api/health`, `/openapi.json`, `/api/overview`, `/api/control-surface/summary`, `/api/control-surface/rows`, `/api/control-surface/ds-goal/cards`, `/api/control-surface/agentops/cards`, `/api/control-surface/a2a/cards`, `/api/control-surface/semantic-receipts/cards`.
4. Probe `/api/control-surface/stream` for 10 seconds and save emitted text.
5. Create one API task with `POST /api/commands/task`, dispatch with `POST /api/commands/dispatch`, then compare `/api/commands/tasks` and `/api/control-surface/summary` before/after.
6. Restart backend once, then re-hit `/api/health`, `/api/overview`, `/api/control-surface/summary`, and `/api/commands/tasks`.

Pass/fail criteria:
- Pass if backend reaches `Application startup complete`, has a running PID, and `/api/health` returns JSON with `status: "ok"` or explicit non-empty error details.
- Pass if `/openapi.json` contains registered routes for `/api/control-surface/summary`, `/api/commands/task`, and `/api/opportunities/dispatch`.
- Pass if control-surface endpoints return envelopes with `data` plus explicit `source_errors`/`error` fields when sources are degraded.
- Pass if API-created task appears in `/api/commands/tasks` with the exact submitted title and a non-empty `id`.
- Degraded if health is `unknown`, stream emits nothing, or source errors appear, provided they are captured explicitly.
- Fail if backend does not boot, API task creation silently reports success without a retrievable task, or restart loses all local task/runtime state without documented reason.

Evidence:
- `02_operator/*.json`, `02_operator/*.txt`, `02_operator/OPERATOR_BOOT_REPORT.md`

## Test 3 — Dashboard/cockpit/control-plane operator walk with live API comparison

Goal: use the web UI like an operator and verify it reflects API truth rather than static/mocked state.

Steps:
1. Run dashboard scripts and save outputs: `npm --prefix dashboard run lint`, `npm --prefix dashboard run build`, `OPENAPI_URL=http://127.0.0.1:8420/openapi.json npm --prefix dashboard run gen:types:check`.
2. Start dashboard dev server on `127.0.0.1:3420`.
3. Record one focused browser session after setup. Visit `/dashboard`, `/dashboard/control-surface`, `/dashboard/cockpit`, `/dashboard/runtime`, `/dashboard/audit`, `/dashboard/agents`, `/dashboard/evolution`, `/dashboard/ontology`.
4. For `/dashboard`, compare displayed `Agents`, `Tasks`, `Fitness`, and `Health` cards against `/api/overview` exact values.
5. For `/dashboard/control-surface` and `/dashboard/cockpit`, compare visible row/card counts and degraded/source-error states against `/api/control-surface/summary` and `/api/control-surface/rows`.
6. After the API task/opportunity state changes in Tests 2/4, refresh relevant pages and record whether visible state changes or remains stale.

Pass/fail criteria:
- Pass if each page renders without Next runtime error and all key pages are captured by screenshot or recording.
- Pass if dashboard overview card values exactly match `/api/overview` values at capture time.
- Pass if control-surface/cockpit visible counts or empty/degraded states match the saved API envelopes.
- Degraded if a page renders but exposes `unknown`, empty rows, source errors, or stale state; must identify exact API payload causing it.
- Fail if a page shows hard browser error, infinite loading, mocked values that disagree with API truth, or UI hides API source errors.

Evidence:
- `03_dashboard/*.txt`, `03_dashboard/*.json`, screenshots, recording, `03_dashboard/DASHBOARD_TEST_REPORT.md`

## Test 4 — High-level mission: Darshan first-reader packet from intent to artifact without sending

Goal: make the swarm attempt a meaningful high-level mission and trace how far intent becomes runtime activity, receipts, control-surface projection, and a concrete artifact.

Mission text:
> Produce a Darshan first-reader artifact from repo-grounded evidence, pass it through planning/context/memory/gate/receipt surfaces, and prepare—but do not send—a first-reader handoff packet.

Steps:
1. Discover canonical task path from CLI/API help outputs (`dgc --help`, `python -m dharma_swarm.dgc_cli --help`, `python -m dharma_swarm.cli --help`) and saved route map.
2. Submit the mission through the most real safe path available in this order: existing API/CLI task/orchestrator path; if broken, a clearly labeled hermetic harness importing task/orchestrator/runtime modules in the isolated state root.
3. Require the run to create `04_mission/DARSHAN_FIRST_READER_ARTIFACT.md` and `04_mission/DARSHAN_FIRST_READER_RECEIPT_DRAFT.json` with `status: "not_sent"` and no claimed reader response.
4. Record tasks created, task assignment/status transitions, context/memory calls, provider/no-key behavior, receipts emitted, DB rows touched, logs produced, API/control-surface rows changed, and dashboard changes.

Pass/fail criteria:
- Pass if mission produces a repo-grounded artifact with at least 5 file/command evidence citations and a receipt draft explicitly marked `not_sent`.
- Pass if at least one runtime task/claim/receipt/DB row or explicit task API record links to the mission id.
- Degraded if provider execution cannot run due missing keys, but the system reports a clear degraded/no-key state and still produces a safe operator draft through local evidence.
- Fail if the system claims outreach was sent, fabricates reader response, produces an artifact with no repo evidence, or returns success with no task/receipt/log/DB evidence.

Evidence:
- `04_mission/DARSHAN_FIRST_READER_ARTIFACT.md`
- `04_mission/DARSHAN_FIRST_READER_RECEIPT_DRAFT.json`
- `04_mission/MISSION_RUN_REPORT.md`

## Test 5 — Opportunity loop + runtime spine + idempotency/degraded paths

Goal: stress the already-known opportunity loop deeper by proving durable state, economics, receipt/spine participation, and broken-path behavior.

Steps:
1. Save `GET /api/opportunities/stages` and assert exact canonical stages.
2. Dispatch opportunity id `deep-e2e-dispatch-20260621` and verify all six stages return `success: true` with non-empty `task_id`, `claim_id`, `run_id`.
3. Query isolated `runtime.db` for exactly six `task_claims` and six `delegation_runs` containing that opportunity id.
4. Re-submit same id or a controlled idempotency probe where the code supports it; record whether duplicate receipts/claims appear or whether it deduplicates.
5. Refill opportunity id `deep-e2e-refill-20260621` with `estimated_value_usd=1000`; verify 6 stages, `total_provider_cost_usd=0.23`, `total_net_value_usd=999.77`, and revenue packet exists and contains the id.
6. Run `python tools/spine_adoption_metric.py --print` and `make spine-check`.
7. Simulate malformed/missing-field opportunity payloads and provider-degraded mode (`DHARMA_RESEARCH_BACKEND=quarantine` server process if needed) and verify explicit failures/degraded stage statuses.

Pass/fail criteria:
- Pass if canonical stage list exactly equals `scope, validate, deep_research, capability, mvp, first_artifact`.
- Pass if dispatch/refill create the expected six-stage durable state and economics.
- Pass if spine adoption metric exits with parseable output and `make spine-check` prints `spine ownership clear`.
- Degraded if API loop works but `EvidenceReceipt`/runtime receipts are missing or disconnected; must name which receipt layer is absent.
- Fail if dispatch returns success without DB persistence, refill returns wrong economics, malformed payloads silently succeed, or duplicate/idempotency behavior is unbounded/undocumented.

Evidence:
- `05_spine/*.json`, sqlite query outputs, `05_spine/SPINE_TRUTH_REPORT.md`

## Test 6 — Memory kernel/context system readiness and projection

Goal: verify whether memory/context organs participate as runnable checks and whether control surface/dashboard project their state.

Steps:
1. Run and save `make memory-kernel-readiness`, `make memory-kernel-readiness-strict`, and `make operator-prod-smoke`.
2. If the targets document or respect isolated state, run `make memory-kernel-burn-in`, `make memory-kernel-write-receipt-smoke`, `make memory-kernel-promotion-smoke`, and `make memory-kernel-knowledgeops-bridge-smoke`; otherwise mark untested with reason.
3. Capture writer sentinel output, context canary output, promotion queue/readiness state, and hard failure/warning counts.
4. Compare memory row ids from `operator_prod_smoke.py` (`memory.census`, `memory.writer_sentinel`, `memory.context_shadow`, etc.) to `/api/control-surface/rows` and dashboard/cockpit panels.

Pass/fail criteria:
- Pass if readiness targets exit 0 and `operator-prod-smoke` reports required memory rows projected.
- Pass if write-receipt/promotion smokes either run in isolated state or explicitly refuse unsafe non-test promotion.
- Degraded if readiness passes but UI/control-surface does not project memory state, or if canaries intentionally report hard failures.
- Fail if memory targets mutate non-test memory without warning, crash without diagnostics, or dashboard shows memory as healthy while API/checks report hard failures.

Evidence:
- `06_memory/*.txt`, `06_memory/*.json`, `06_memory/MEMORY_KERNEL_REPORT.md`

## Test 7 — A2A/NATS substrate and multi-agent coordination honesty

Goal: verify the A2A/NATS contract and, if safe, a local/dry-run packet receipt path without pretending unavailable transport works.

Steps:
1. Run `make nats-substrate-contract` and save output.
2. Save help/availability for `python scripts/runtime/a2a_send.py --help` and `python scripts/governance/truth_graph_nats_e2e_demo.py --help`.
3. If `DEVIN_NATS_*` connectivity succeeds and scripts support safe local/dry-run send, send a labeled local test packet only; otherwise document unavailable/degraded state.
4. Verify packet schema, send receipt, inbox/bridge receipt, reply receipt if applicable, presence/heartbeat if applicable, and `/api/control-surface/a2a/cards` visibility.

Pass/fail criteria:
- Pass if contract tests exit 0 and any safe send produces receipt files under `reports/a2a/` with the test id.
- Degraded if NATS/live contact is unavailable or credentials cannot be used, provided scripts fail explicitly and local contract tests still verify schema paths.
- Fail if send reports success without receipt files, blocks indefinitely, writes secrets to logs, or control-surface claims A2A health contrary to failed transport evidence.

Evidence:
- `07_a2a/*.txt`, receipt files/excerpts, `07_a2a/A2A_NATS_REPORT.md`

## Test 8 — DGC/self-evolution path in shadow-only mode

Goal: inspect whether self-evolution can run through safe shadow/proof paths while live apply remains closed.

Steps:
1. Run and save `python -m tools.build_protocol.cli --help`, `make verify-corral`, and `make verify-corral-strict`.
2. If an existing sealed packet suitable for shadow apply is present, run shadow apply only with `DHARMA_EVOLUTION_SHADOW=1`; never set live apply env vars.
3. Inspect proof/archive evidence for `shadow:true`, `applied:false`, and archived proof result.
4. Reconcile findings against `docs/state/BROKEN_REGISTER.md` BR-003.

Pass/fail criteria:
- Pass if help/verification commands run and BR-003 status can be reverified with evidence.
- Pass if any shadow apply produces a proof/archive record with `shadow:true` and does not live-apply.
- Degraded if no usable sealed packet exists; must state untested rather than success.
- Fail if live mutation occurs, `applied:true` appears without explicit approval, or BR-003 status in docs contradicts observed evidence.

Evidence:
- `08_dgc/*.txt`, `08_dgc/*.json`, `08_dgc/DGC_SELF_EVOLUTION_REPORT.md`

## Test 9 — Controlled failure/restart/concurrency stress

Goal: reveal degraded/error behavior rather than only happy paths.

Steps:
1. Before and after backend restart, hit `/api/health`, `/api/overview`, `/api/control-surface/summary`, and `/api/commands/tasks` and compare continuity.
2. Submit malformed/missing-field payloads to `/api/commands/task`, `/api/opportunities/dispatch`, `/api/opportunities/refill`, and one invalid control-surface row lookup.
3. Run 3–5 concurrent lightweight probes against `/api/overview`, `/api/control-surface/summary`, `/api/control-surface/rows`, `/api/opportunities/stages`, `/api/commands/tasks`.
4. Check process table/log tail for runaway server, hidden infinite loop, repeated tracebacks, or silent success.

Pass/fail criteria:
- Pass if bad payloads return explicit HTTP 4xx or `status:error` with clear message.
- Pass if concurrent probes all return within 10 seconds and server remains healthy/responding.
- Degraded if errors are explicit but UI does not surface them.
- Fail if invalid inputs return fake success, server hangs/crashes, or restart loses state that should be durable.

Evidence:
- `09_stress/*.json`, `09_stress/*.txt`, `09_stress/STRESS_REPORT.md`

## Test 10 — Governance/DocOps closeout and permanent operator notes

Goal: close the run in a way future agents can trust and rerun.

Steps:
1. Run and save `make docops-report`, `make docops-integrity`, `make hygiene-audit`, `make governance-all`, and `make agent-build-closeout`.
2. Categorize any failures as new regression, pre-existing failure, missing local dependency/tool, external service unavailable, stale test expectation, or genuine runtime bug.
3. Generate `RUN_INDEX.json`, `MASTER_REPORT.md`, and all phase reports 00–10.
4. Update `docs/state/LIVE_OPS_DASHBOARD.md` with section `Full Swarm E2E Test — 2026-06-21`.
5. Update `docs/state/BROKEN_REGISTER.md` only for newly observed broken/degraded surfaces or reverified existing findings; do not delete older rows.
6. Commit report/docs changes on branch `devin/full-swarm-e2e-test-20260621` and open a draft PR, not for merge.

Pass/fail criteria:
- Pass if final branch contains `RUN_INDEX.json`, `MASTER_REPORT.md`, phase reports, and updated live-ops docs.
- Pass if every final claim points to command/file/log/DB/endpoint/screenshot/receipt evidence.
- Degraded if governance commands fail but failures are categorized and linked to raw output.
- Fail if final report hides blocked surfaces, claims success without receipts, mutates external/live systems, or leaves no durable operator notes.

Evidence:
- `10_closeout/GOVERNANCE_CLOSEOUT_REPORT.md`
- `RUN_INDEX.json`
- `MASTER_REPORT.md`
- draft PR link
