# Devin A2A Fleet Plan — Complementary Workstreams

**Date:** 2026-05-28
**Plan version:** v1
**Plan owner:** devin-roaming-2987d222
**Authority:** working_plan (subordinate to Claude's v2 fleet plan)
**Complements:** Claude opus_composer A2A persistent fleet plan v2

---

## Relationship to Claude's Plan

Claude's plan owns the **core executor scaffolding**: building
`dharma_swarm/a2a/executors/`, wiring launchd/systemd persistence,
deploying the VPS registry, writing the 8 executor modules, cost
guardrails, and the conductor pass A2A streaming upgrade.

This plan owns **everything Devin can do that Claude cannot** — and
everything Claude's plan explicitly defers, under-specifies, or needs
a second agent to validate. The two plans share zero overlapping
deliverables. Where Claude builds, Devin verifies. Where Claude
deploys locally, Devin stress-tests from outside.

---

## What Devin Uniquely Owns

### 1. The devin-roaming Integration (Devin's Own Executor)

Claude's plan describes `devin_executor.py` from the Mac side —
writing inbound JSON, polling outbound, synthesizing SSE heartbeats.
But the **other half** of the git-rendezvous lives inside Devin's VM.
Only Devin can build, test, and validate this half.

**Devin deliverables:**

- **`dharma_swarm/a2a/devin_rendezvous.py`** — The Devin-side pickup
  daemon. Watches `inter_agent/devin/inbound/` for A2A task files,
  executes the task (or dispatches to Devin's own toolchain), writes
  the result to `inter_agent/devin/outbound/<task_id>.json`, and
  commits+pushes. This is the counterpart to the Mac-side
  `devin_executor.py` SSE poller.

- **Claim protocol hardening:** Implement the ULID-based atomic claim
  that Claude's plan references (risk N8). The claim sentinel
  (`inbound/<task_id>.claim`) prevents double-pickup when multiple
  Devin sessions run concurrently. Use `os.link` for atomic creation.

- **Heartbeat integration:** When Devin is actively working a task,
  write periodic status updates to
  `inter_agent/devin/outbound/<task_id>.heartbeat.json` so the
  Mac-side SSE pump has real signal (not just synthetic 5s ticks).

- **Schema contract:** Define the JSON schemas for inbound task files
  and outbound result files as Pydantic models in `devin_rendezvous.py`.
  These schemas are the API contract between Mac and Devin — both
  sides must agree.

**Timeline:** Aligns with Claude's Day 4 (opus/codex/devin executors).
Devin starts building the pickup daemon on Day 3 so it's ready for
end-to-end testing on Day 4.

---

### 2. A2A Integration Test Suite

Claude's plan includes per-agent smoke tests (curl commands, the
Sid Buddhisara 4-step formula). But there is no **automated test
suite** that runs in CI and catches regressions.

The existing `tests/test_a2a.py` (842 lines) covers AgentCard, CardRegistry,
A2AServer, A2AClient, and A2ABridge — all in-process, no HTTP, no
executors, no registry HTTP endpoints. The new executor layer has zero
CI coverage in Claude's plan.

**Devin deliverables:**

- **`tests/test_a2a_executors.py`** — Unit tests for the executor
  ABC compliance. Verify every executor implements `execute()` and
  `cancel()` per a2a-sdk v1.0.3. Mock the underlying LLM calls.
  Test the `server_bootstrap.py` Starlette wiring, the
  streaming-only enforcement middleware, and the per-executor token
  budget rejection.

- **`tests/test_a2a_registry_http.py`** — Integration tests for the
  HTTP advertise/discover endpoints that Claude adds to
  `node_registry.py`. Test bearer-token auth, registration,
  deregistration, and discovery. Use `httpx.AsyncClient` with the
  FastAPI TestClient pattern — no real VPS needed.

- **`tests/test_a2a_cross_agent.py`** — End-to-end test that
  instantiates two executors in-process, registers them with a local
  registry, and verifies the cross-agent round-trip: agent A
  delegates to agent B via `a2a_client.delegate_via_http()`, receives
  SSE events, and gets an artifact back. This is the CI-automated
  version of Claude's Day 4 "cross-agent round-trip" verification.

- **`tests/test_devin_rendezvous.py`** — Tests for the Devin-side
  pickup daemon. Write a mock inbound task, verify claim protocol,
  verify outbound result file, verify heartbeat writes.

**Timeline:** Tests land on Days 2-5, matching each executor as
Claude ships it. CI catches regressions from Day 2 onward rather
than relying on manual curl.

---

### 3. Observability Layer

Claude's plan mentions a "tiny aggregator" at `log_tail.py` (risk N11)
but it's buried in Day 11 slack and explicitly deferred. Devin builds
the observability layer earlier so the fleet has eyes from Day 5.

**Devin deliverables:**

- **`dharma_swarm/a2a/fleet_status.py`** — Fleet status aggregator.
  Queries all registered agents via their Agent Card URLs, collects
  health status, latency, last-task timestamps, and error counts.
  Returns a structured `FleetStatus` Pydantic model. This is the
  programmatic backbone for both CLI and dashboard display.

- **`dgc fleet` CLI subcommand** — Wire `fleet_status.py` into the
  existing `dgc` CLI (`dharma_swarm/dgc_cli.py`). Output: table of
  agents with status, latency, last-seen, error count. Replaces the
  "tail 8 log files" anti-pattern from Day 1.

- **Dashboard fleet widget** — Add a `/api/fleet/status` endpoint
  to `api/routers/` that returns the `FleetStatus` JSON. Wire a
  minimal React component in the dashboard that renders the fleet
  table. The operator sees agent health at a glance instead of
  SSHing into the VPS.

- **`dharma_swarm/a2a/fleet_metrics.py`** — Structured metrics
  collection. Each executor emits task_count, error_count,
  latency_p50, latency_p99, tokens_consumed to a JSONL file at
  `~/.dharma/a2a_bus/fleet_metrics.jsonl`. The verifier and
  dashboard read from this. Replaces the "read 8 server logs"
  approach with structured telemetry.

**Timeline:** `fleet_status.py` lands Day 5 (after 4 Mac agents are
live). Dashboard widget lands Day 7-8 (after VPS agents). CLI
subcommand lands Day 5.

---

### 4. External Validation & Adversarial Testing

Claude builds the fleet. Devin tries to break it. This is the
Transcendence Principle in action — decorrelated error detection.

**Devin deliverables:**

- **Registry stress test:** After Day 3, Devin (from its external VM)
  hits the VPS registry with rapid registration/deregistration cycles,
  malformed bearer tokens, oversized payloads, and concurrent writes.
  Verify the registry doesn't corrupt `node_registry.json` (risk N12).

- **Cross-tier latency baseline:** Devin's VM is a different network
  path than Bali Mac. Run the same registry discovery + agent
  round-trip from Devin's VM to establish an independent latency
  baseline. Compare with Claude's Mac-based measurements for
  triangulation.

- **Executor crash recovery audit:** After Day 5, Devin sends
  malformed A2A JSON-RPC requests to each executor endpoint. Verify
  that executors return proper error responses (not 500s or crashes)
  and that the Starlette middleware rejects invalid requests before
  they reach the executor.

- **Cost ledger verification:** After Day 9, Devin independently
  reads `monthly_subscription_burn.jsonl` and the per-executor
  token logs. Cross-check against known subscription costs. Flag
  any drift between projected and actual.

**Timeline:** Adversarial testing starts Day 4 (first executor live)
and continues through Day 11.

---

### 5. Documentation & DocOps

Claude's plan creates 15+ new files. The repo's DocOps governance
requires these to be indexed, documented, and manifest-registered.
Claude's plan doesn't include this work.

**Devin deliverables:**

- **Update `ACTIVE_SURFACE_MANIFEST.yaml`** — Register the new
  `dharma_swarm/a2a/executors/` directory, `server_bootstrap.py`,
  `agent_card_a2a_sdk_bridge.py`, `verifier.py`, and the fleet
  status modules as declared surfaces.

- **Update `INTERFACE_MISMATCH_MAP.md`** — Document the new
  interfaces between executors ↔ server_bootstrap, executors ↔
  a2a_task_lifecycle, executors ↔ CardRegistry. Verify no
  mismatches at integration time.

- **Update `NAVIGATION.md`** — Add the executors layer to the
  module map. Currently `dharma_swarm/a2a/` is documented but
  the executors subdirectory doesn't exist yet.

- **Update `DEVIN.md` §5.2 rendezvous protocol** — Extend with
  the new A2A-based task format (JSON-RPC inbound files replace
  the current markdown convention for A2A tasks).

- **Broken Register entries** — If any integration surface is
  incomplete at the end of each phase, file BR entries per
  `docs/state/BROKEN_REGISTER.md` convention. Don't let known
  gaps go undocumented.

**Timeline:** DocOps updates land same-day as each deliverable.
Final sweep on Day 11.

---

### 6. Devin Environment Blueprint

Future Devin sessions need to work with the A2A fleet
infrastructure without re-discovering the setup.

**Devin deliverables:**

- **Blueprint update** — Add `a2a-sdk==1.0.3` to the Devin
  environment blueprint's maintenance step so future sessions
  have the SDK pre-installed.

- **Knowledge note** — Persist A2A fleet architecture context
  (agent ports, registry URL, executor module paths, test
  commands) as a Devin knowledge note so future sessions
  don't need to re-explore.

- **Devin skill** — Create `.agents/skills/a2a-fleet-test/SKILL.md`
  with the step-by-step procedure for verifying the fleet from
  Devin's perspective: run tests, check registry, send test
  tasks, verify rendezvous.

**Timeline:** Blueprint update Day 2. Knowledge note Day 5.
Skill Day 9.

---

## Day-by-Day Alignment with Claude's Plan

| Day | Claude Does | Devin Does |
|-----|------------|------------|
| 0 | Pre-flight checklist (VPS, SDK, keys) | Pull main, read inbound, review Claude's plan artifacts |
| 1 | Fix hermes cancel() + smoke | Write devin_rendezvous.py schemas (Pydantic models) |
| 2 | Consolidate executor scaffold + hermes_executor | Write `test_a2a_executors.py` stubs; blueprint update |
| 3 | Registry HTTP endpoints on VPS | Write `test_a2a_registry_http.py`; start devin_rendezvous.py pickup daemon |
| 4 | opus/codex/devin executors + cross-agent round-trip | Write `test_a2a_cross_agent.py`; end-to-end rendezvous test |
| 5 | Persistence verification + verifier + cost ledger | `fleet_status.py` + `dgc fleet` CLI; `test_devin_rendezvous.py` |
| 5.5 | Slack | Registry adversarial test from Devin VM |
| 6 | 24h soak + cross-tier verification | External latency baseline from Devin VM |
| 7 | hermes-vps + gemini-flash-worker | Dashboard fleet widget + `/api/fleet/status` |
| 8 | ollama-frontier + kimi executors | `fleet_metrics.py` structured telemetry |
| 9 | opus_alt + verifier-to-cron | Devin skill creation; cost ledger cross-check |
| 10 | Conductor pass A2A streaming | Executor crash recovery audit |
| 11 | Slack/hardening | DocOps sweep: manifest, nav, mismatch map, BR entries |

---

## Verification — How Devin Proves Its Work

Each deliverable has a testable claim:

| Deliverable | Verification |
|-------------|-------------|
| devin_rendezvous.py | `pytest tests/test_devin_rendezvous.py -q` passes |
| Claim protocol | Write two concurrent claims → only one succeeds |
| test_a2a_executors.py | All executor ABCs pass in CI |
| test_a2a_registry_http.py | Registry HTTP tests pass with no VPS |
| test_a2a_cross_agent.py | In-process cross-agent round-trip completes <5s |
| fleet_status.py | `dgc fleet` returns structured status for mock agents |
| Dashboard widget | `/api/fleet/status` returns JSON with agent array |
| fleet_metrics.py | JSONL file grows with each executor task |
| DocOps | `make xray` shows no unregistered surfaces |
| Knowledge note | `list_knowledge_notes` shows A2A fleet note |
| Devin skill | `.agents/skills/a2a-fleet-test/SKILL.md` exists and is runnable |

---

## Risks Devin Watches (Complementary to Claude's 14)

Claude's plan identifies 14 risks. Devin adds its own perspective:

**D1. Git rendezvous race under A2A load.** The current rendezvous
uses `git commit + push`. Under A2A fleet load (multiple agents
delegating to Devin simultaneously), push conflicts will spike.
Mitigation: devin_rendezvous.py uses branch-per-task
(`devin/task/<task_id>`) instead of committing to a shared branch.
Each task gets its own atomic branch. Mac-side polling checks all
`devin/task/*` branches.

**D2. Devin session ephemerality.** Devin sessions expire. If a task
is in-flight when the session dies, the Mac-side SSE pump waits
forever. Mitigation: devin_rendezvous.py writes a session-start
sentinel (`inter_agent/devin/outbound/<session_id>.alive`). If the
sentinel isn't updated for 10 minutes, Mac-side treats all in-flight
tasks as FAILED.

**D3. Test isolation from production state.** Tests must not touch
`~/.dharma/` production state. All test fixtures use `tmp_path`.
Existing `test_a2a.py` follows this pattern — new tests must too.

**D4. CI time budget.** Adding 4 new test files could push CI past
timeout. Mitigation: mark slow integration tests with
`@pytest.mark.slow`; CI runs fast tests by default, slow tests on
merge to main only.

**D5. Dashboard build breakage.** Adding a fleet widget to the Next.js
dashboard could break the existing build. Mitigation: fleet widget is
a standalone component with no imports from existing dashboard code.
Run `make dashboard-lint` before committing.

---

## What This Plan Does NOT Do

- Does NOT build executors (Claude owns all 8 executor modules)
- Does NOT deploy to VPS (Claude owns VPS deployment)
- Does NOT write launchd plists or systemd units (Claude owns persistence)
- Does NOT modify the conductor pass (Claude owns the streaming upgrade)
- Does NOT touch `~/.hermes/` or hermes CLI (Claude owns hermes integration)
- Does NOT create or modify `server_bootstrap.py` (Claude owns the shared Starlette wiring)
- Does NOT set cost caps or budget guardrails (Claude owns cost agent mitigations)

Devin's plan is purely additive: tests, observability, documentation,
external validation, and the Devin-side rendezvous daemon. Nothing
here blocks Claude's plan if Devin falls behind. Nothing Claude builds
blocks Devin's plan if Claude falls behind. The plans are designed to
be independently valuable and jointly complete.

---

Plan version 1. Owner: devin-roaming-2987d222. Complements Claude
opus_composer A2A persistent fleet plan v2. Zero deliverable overlap.
Ready for operator review.
