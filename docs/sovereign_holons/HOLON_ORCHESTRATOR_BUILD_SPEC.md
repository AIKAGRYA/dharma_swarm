# HOLON ORCHESTRATOR — executable e2e build spec (corrected; supersedes the drifted single-model specs)

**Date:** 2026-06-09 · **Why this exists:** an independent review found the prior build DRIFTED — it built
a *single-model wake loop* ("an Opus costume on a free-cron-loop") when the mission is a **sovereign holon
that ORCHESTRATES a subagent fleet**, Opus at the helm. This spec corrects the target and is structured to
be driven to completion by `/goal` + `/longrun` + workflows, with anti-drift discipline baked in.

**SUPERSEDES (drifted, single-model):** `02_FIRST_BRICK_SPEC.md`, `BUILD_QUEUE.md` (U1–U11), `ROADMAP_TO_PROD.md`.
Their *governance/persistence/kill/budget/compass* code is reusable; their *single-model architecture* is wrong.

> **⚠️ REUSE MAP (adversarial spec-review, 2026-06-09 — the engine ALREADY EXISTS; build only the wiring):**
> The orchestration substrate is **already built and tested** — do NOT rebuild it:
> - **fan-out / fan-in** decompose→dispatch→aggregate: `orchestrator.py` (`fan_out`/`fan_in`, `TopologyType.FAN_OUT`), tested in `test_orchestrator.py::test_dispatch_fan_out`.
> - **agent fleet spawn/manage:** `agent_runner.AgentPool`.
> - **task decomposition:** `intent_router.decompose()` / `SwarmManager.decompose_task()` (regex-based today).
> - **declared-first model order:** `model_hierarchy.CANONICAL_SEED_ORDER` (Opus already at top) + `runtime_provider.resolve_runtime_provider_config()`.
> - **governance/persistence:** the green `holon_*` modules.
>
> **The ONLY genuinely-missing thing is the THIN WIRING (~one new file `holon_orchestrate.py`):** parse the
> holon's (Opus) decomposition → structured `Task`s → `orchestrator.fan_out()` to cheaper-model agents →
> `fan_in()` → Opus **synthesizes** (reconciles, not concatenates) the aggregated reply. The pumps and pipes
> exist; build the plumbing. My earlier "build the orchestration organ" was drift — corrected below.

---

## The corrected target (what a sovereign holon actually is)

A registered agent (flagship **opus_composer**) that is ALL of:
1. **A being you talk to as itself** — own identity/soul/memory/voice/continuity (the talk surface — built ✓).
2. **Runs on its OWN model, auto-shifting** — declared model (**Opus 4.8**) preferred/main, with **automatic
   live-fallback** to other models on unavailability/failure/cost, via existing `runtime_provider.model_hierarchy`
   (declared-FIRST, not free-first — the exact bug to fix).
3. **An ORCHESTRATOR (the missing core)** — at the helm (Opus), it *decomposes work and dispatches a fleet of
   cheaper-model subagents* within its telos boundary, then aggregates their results. Like Claude Code / the
   maestro pattern — NOT a single model answering a fixed prompt. **This is the heart of "holon."**
4. **Governed — "sovereign within the banks"** — kill-switch, budget (enforced across the whole fleet), telos
   gate/compass, per cycle.
5. **Persistent** — survives restart, resumes, memory continuity (built ✓).
6. **The full 12-organ harness** — not just bridge+talk: also verification loop, reliability (`pass^k`),
   sleep-time compute, pilot→prod triad.

---

## THE /goal (the single, locked, verifiable finish line — the thing I never set)

> **Run `holon opus_composer` and prove, on a LIVE run with real models (not stubs):** it loads its own
> identity + model (Opus-preferred, **auto-shifts** to the next hierarchy tier when Opus is down); you talk
> to it as itself; it **wakes, has Opus decompose a real task, dispatches ≥2 subtasks to cheaper agents on
> ≥2 different model-tiers via the existing `orchestrator.fan_out`, and Opus SYNTHESIZES the aggregated
> results into a coherent reply (reconciling, not concatenating; on a subagent failure it retries/rephrases,
> not just appends the error)**; every cycle is **governed** — kill + **fleet-budget = SUM of Opus + all
> subagent spend** + telos, fail-closed where required — and **persisted** (survives restart + resumes); it
> runs a **verification check on its own output** (refuses unbacked "done"), and logs **`pass^k` reliability**
> over repeated runs.

`/goal` judges this against the live transcript/receipts; **self-certification is never accepted.**

---

## /longrun build phases (each: TDD → objective verifier → fresh-context verify → adversarial detonate → fix)

| P | Organ | Builds | Reuses | Objective verifier (exit-0) |
|---|-------|--------|--------|------------------------------|
| **P0** 🔒 | funded-Opus path | add OpenRouter/Anthropic credit OR re-auth Max | — | `holon_talk opus_composer` replies on **real Opus** (operator action) |
| **P1** | model resolution (small fix, NOT a build) | fix `holon_run.py` free-first bug → call `get_holon_provider(holon)` / the existing `CANONICAL_SEED_ORDER` (declared-first ALREADY exists) | `model_hierarchy`, `runtime_provider` | test: loads Opus when up, **auto-shifts to next tier** when Opus down, never ignores `identity.model` |
| **P3** | governance hardening (couple BEFORE P2) | fail-closed gate option; **fleet-budget = SUM(Opus+subagents)** tracked inside fan-out | `holon_budget_guard`, `telos_gates`, `holon_runtime` spend_fn | test: forbidden action blocked; summed fleet spend ≥ cap → halt |
| **P2** | **WIRE the orchestrator (the core — glue, NOT engine)** | one new `holon_orchestrate.py`: Opus decompose → parse to `Task`s → `orchestrator.fan_out()` (cheaper-tier agents) → `fan_in()` → Opus **synthesizes** (reconcile, retry-on-fail) | **REUSE** `orchestrator.fan_out/fan_in`, `agent_runner.AgentPool`, `intent_router.decompose` (do NOT rebuild) | co-verified with P4: wake cycle has Opus decompose a complex task → ≥2 subtasks dispatched to ≥2 model-tiers → results synthesized coherently → verification confirms completeness |
| **P4** | verification loop (organ 8) | holon verifies its OWN output; refuses unbacked "done" | `everything-claude-code:verification-loop`, `holon_compass` | test: a "done"-claiming cycle with no artifact is caught/refused |
| **P5** | reliability (organ 10) | `pass^k` instrumentation replacing empty `fitness_history` | τ-bench `pass^k` pattern | test: `pass^k` computed over N repeated runs, persisted |
| **P6** | sleep-time compute (organ 11) | idle-cycle memory reorganization | `AgentCronScheduler`, MemoryKernel | test: an idle cycle reorganizes memory (Letta pattern) |
| **P7** | pilot→prod triad (organ 12) | observability + HITL + cost discipline + launchd durability | `control_surface`, `holon_health`, launchd | test: runs durably; health/kill/cost surfaces live |

**Anti-drift rules (burned in from this session's failure):**
- Every phase has a NAMED objective verifier *before* code. "Done" = the verifier is green, judged by a
  **fresh-context no-write evaluator**, then **adversarially detonated** for integration/false-greens. Never self-certify.
- Each phase is one workflow (build → verify → detonate → fix-to-green), run under the `/goal` gate.
- Report the real % against the `/goal` only — no shifting numbers.

---

## How it runs (the autonomous machinery, e2e)

```
/goal "<the locked finish line above>" or stop after <N> hours
/longrun  → for each phase P1..P7:
              workflow: build(TDD) → fresh-context verify(exit-0) → adversarial detonate → fix
              halt the phase only on green-verified + dry-detonation
            P0 is operator-gated (funded Opus); P3/P4 governance is the load-bearing organ
fresh-context evaluator gates each phase; obey-detonation finds drift/islands; no self-cert ends it
```

**Status of reusable code (from the drifted build):** `holon_killswitch`, `holon_budget_guard`,
`holon_compass`, `holon_persistence`, `holon_health`, the governed-loop skeleton (`holon_runtime`), the
talk surface (`holon_bridge` + route) — all GREEN and reusable. The **orchestration organ (P2) is the new
heart**, and P1 (declared-first model) + P4/P5/P6/P7 are the genuinely-missing harness.
