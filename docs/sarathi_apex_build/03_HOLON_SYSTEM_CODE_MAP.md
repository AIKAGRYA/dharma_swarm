# 03 — Holon-System Code Map (Hermes-class organs → our code)

**Custody: VERIFIED 2026-07-06 (symbols grepped from the named files).**

This is the numbered front-door version of the organ map. The longer prose lives
in `HOLON_SYSTEM_CODE_ORGANIZATION.md`; this file is the fast lookup table.

## The thesis in one line

`holon_system = identity + provider routing + persistent wake kernel + governed
runtime + orchestration + A2A transport + semantic responders + gateway +
observability + packaging/CLI + proof gates`. **Sarathi is the apex occupant of
this system, not the system.**

## Organ → code map

Status legend: **EXISTS** (real, importable), **PARTIAL** (works but incomplete),
**SCATTERED** (real but spread across runtime scripts, no clean lib), **MISSING**.

| Hermes-class organ | Our canonical code | Facade | Status |
|---|---|---|---|
| identity / registry | `agent_registry.py` (`AgentRegistry`), `external_agent_registration.py`, `holon_bridge.load_holon` | `holon_system/identity` | EXISTS |
| providers / model routing | `runtime_provider.py`, `model_hierarchy.py` (`resolve_top_available_at_wake` for `@frontier`) | `holon_system/runtime/provider.py` | EXISTS |
| persistent runtime | `persistent_agent.py` (`PersistentAgent`), `autonomous_agent.py` (`AutonomousAgent`) | — | EXISTS (ancestor lineage) |
| living kernel | `operator_core/living_agent_kernel.py` (`LivingAgentKernel`) | `holon_system/kernel/living` | EXISTS |
| governed runtime | `holon_runtime.py` (`holon_wake_cycle`, `run_holon_loop`), `holon_bridge.py`, `holon_persistence.py` | `holon_system/runtime/*` | EXISTS |
| orchestration | `holon_orchestrate.py` (`run_holon_orchestration`), `orchestrator.py`, `agent_runner.py`, `intent_router.py` | `holon_system/orchestration/holon_orchestrate` | EXISTS (no 2nd orchestrator) |
| authority / leases / reversibility | `operator_core/execution_lease.py`, `operator_core/reversibility_gate.py` | `holon_system/authority/*` | EXISTS |
| memory / receipts / observability | `holon_health.py`, `holon_canonical_state.py`, `holon_persistence.py` | `holon_system/observability` | EXISTS (read-only projection) |
| A2A transport | `scripts/runtime/a2a_send.py`, `a2a_inbox_bridge.py`, `a2a_domain_reply_worker.py`, `a2a_reply_capture.py`, `dharma_swarm/a2a/*` | `holon_system/transport` (pointer only) | SCATTERED |
| semantic responders | `scripts/runtime/*semantic_responder.py`, `codex_composer_semantic_inbox_drain.py` | `holon_system/responders` (pointer only) | SCATTERED |
| scheduler / cron / launchd | `scripts/runtime/*wake_loop.py` (WakeProfile), `cron_jobs.json`, launchd plists | `holon_system/gateway` (pointer only) | PARTIAL (lease-gated wake shell; no standing scheduler) |
| gateway (chief-of-staff loop) | `scripts/runtime/codex_composer_wake_loop.py` wake shell | `holon_system/gateway` (pointer only) | PARTIAL (wake shell yes; read→classify→one-lane→brief loop NO) |
| operator UI / API | `api/routers/holon.py`, dashboard | `holon_system/api` (pointer only) | EXISTS |
| packaging / CLI | `dharma_swarm/dgc_cli.py` (`agent list` / `agent status`) | `holon_system/cli` (pointer only) | EXISTS |
| tests | `tests/test_holon_*.py`, `test_reversibility_gate.py`, `test_holon_system_imports.py` | — | EXISTS |
| docs | `docs/sarathi_apex_build/` | — | EXISTS (this normalization) |
| apex holon (Sarathi) | `holon_system/sarathi/` package | — | MISSING impl (specified; gated) |

## How to read this

- **EXISTS** organs have a `holon_system/` facade you can import today; the
  facade re-exports the canonical symbol (proven by `test_holon_system_imports.py`).
- **SCATTERED / PARTIAL** organs have a `holon_system/` subpackage that is an
  honest *pointer* to the runtime-script owners — no fabricated library. Promote
  to a real facade only when a stable import surface is agreed.
- **MISSING** = the Sarathi apex modules (`gateway/pulse/roster/brief/scoreboard`)
  are specified in `05_SARATHI_APEX_MAP.md`, gated by `06_PROOF_GATES.md`.

## The rule

No new orchestrator, model router, task store, A2A bus, or receipt spine
(constraint #9). New code for these organs is a *facade or a wrapper over the
canonical owner above*, never a second implementation. `sprawl_guard.py`
enforces the singletons (`load_holon`, `holon_wake_cycle`).
