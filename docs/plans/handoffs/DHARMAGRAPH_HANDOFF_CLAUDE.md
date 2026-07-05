# DharmaGraph Handoff — CLAUDE LANE (Phase 0b durable_invoker + Phase 1 oracle/DST)

**You are a fresh Claude Code instance on a remote VM with a fresh clone of `AmitabhainArunachala/dharma_swarm` (main).** This brief is self-contained; the full campaign spec is `docs/plans/DHARMAGRAPH_PHASED_SPEC_2026-07-05.md` — read §1, §2, and §3 Phases 0b/1 before writing code. Your work lands under the active track `dharmagraph-engine-2026-07` (`docs/governance/ACTIVE_TRACK.yaml`).

## Before ANYTHING else (non-negotiable)

```bash
make onboard   # renders live tracks, trust check, next command — TRUST ITS OUTPUT over any doc, including this one
make orient    # whole-system orientation graph
```

Then read: `CLAUDE.md` (behavioral rules), `INTERFACE_MISMATCH_MAP.md` (check every module pair you touch), `docs/governance/BUILD_SESSION_ENTRYPOINT.md`, and `.agents/skills/testing-spine/SKILL.md` (environment + verdict conventions).

## Coordination contract (Devin runs SIMULTANEOUSLY)

Devin owns: dead-engine deletion (`workflow_graph.py`, `durable_execution.py`), `dharma_swarm/graph/checkpoint.py`, `dharma_swarm/graph/reconciler.py`, the `swarm.py` reconciler wiring, and their tests. **You own:** `dharma_swarm/graph/durable_invoker.py`, the minimal `orchestrator.py` seam call, `tests/test_graph_durable_invoker.py`, the `[test-oracle]` extra, `tests/test_langgraph_differential_oracle.py`, the oracle CI job, and the DST seed. If `dharma_swarm/graph/__init__.py` doesn't exist, create it minimal; whoever lands second rebases. Branch naming: `claude/dharmagraph-phase0b-invoker`, `claude/dharmagraph-phase1-oracle`. One PR per slice. Never push to main directly.

## Task 1 — Phase 0b: the durable invoker (exactly-once dispatch)

**The seam (verified 2026-07-05; re-verify line numbers on your clone):** `_orch_invoker` inside `orchestrator._run_task_via_spine` (`orchestrator.py:2471-2524`); the provider call is `runner.run_task` awaited at `:2477`; `side_effect_key = f"invoke_agent:{task_id}:{agent_id}"` already computed at `:2467`. The `AgentInvoker` protocol (`spine/invoke.py:19-33`) explicitly permits wrapper invokers doing arbitrary pre/post work — zero signature changes. Do NOT touch `a2a/spine_adapter.py`'s `_a2a_invoker` (it has its own idempotency path).

Build `dharma_swarm/graph/durable_invoker.py` (new module — `orchestrator.py` is at its module-budget ceiling, ~3,221 lines vs ~3,215 allowed; you may add ONLY the wrapper call there):

1. `wrap_invoker(inner: AgentInvoker, *, store, identity, side_effect_key) -> AgentInvoker` returning a contract-compatible invoker that:
   - **Memo check first:** if a receipt already exists for this key (read `delegation_runs.receipt_json` / the idempotency record), return the prior `EvidenceReceipt` WITHOUT calling the provider. This is the read path that turns the write-only audit trail into effectively-once execution.
   - **Begin/complete:** wrap the inner call with the EXISTING machinery — `try_begin_idempotent_side_effect` / `complete_idempotent_side_effect` (see `runtime_lifecycle.py:177-201` for the exact usage pattern on claims; idempotency DDL at `runtime_state.py:269-283`). Do not build new idempotency plumbing — it exists, it's just never been applied to the dispatch call itself.
   - **Key derivation for graph runs (forward-compat):** support `sha256(run_id:superstep:node_id:retry_count)` as the key form for Phase 3; today's `side_effect_key` string remains valid for the flat dispatch path.
2. Wire it in `_run_task_via_spine` as a one-to-three-line change: `invoker = wrap_invoker(_orch_invoker, ...)` before the `invoke_agent(...)` call at `:2527-2533`.
3. Tests (`tests/test_graph_durable_invoker.py`, ≥8 cases): memo hit returns prior receipt with zero inner calls (count with a stub invoker); concurrent double-begin loses one cleanly; inner exception → idempotency record not falsely completed → retry re-executes; receipt persisted once; A2A path untouched (regression import test); key stability across retries increments correctly.
4. **Joint chaos receipt with Devin's reconciler:** once both PRs are up, run the kill -9 → reboot → reconcile scenario and assert zero double provider calls end-to-end. Coordinate in PR comments; the track's Phase-0b gate needs BOTH halves.

## Task 2 — Phase 1: the differential oracle (net-new — the parity harness canNOT be promoted)

Ground truth you must internalize: `dharma_swarm/langgraph_parity/` is a deterministic CLONE that "intentionally avoids importing LangGraph" (its own docstrings, `swarm_runtime.py:1-6`); langgraph 1.2.4 is locked in `uv.lock` but not installed and imported by nothing. Its tests assert dharma-vs-hand-written expectations — self-graded. You are building the first real oracle.

1. **Dependency:** add a `test-oracle` optional extra to `pyproject.toml` pinning `langgraph==1.2.4` (+ `langgraph-checkpoint`, already resolved in uv.lock). It must NOT enter core dependencies — non-goal in the track: langgraph is oracle only, never the engine.
2. **Harness** (`tests/test_langgraph_differential_oracle.py` + a small `tests/oracle_support/` package if needed):
   - Take the ≥12 existing parity scenarios (swarm handoff accept/reject, handoff-tool visibility, transfer receipts, unknown-agent rejection, supervisor last_message/full_history output modes, routing-message hiding, isolation/distractor cases — see `tests/test_langgraph_parity_swarm.py` and `..._supervisor.py` for the scenario inventory).
   - Run each scenario through BOTH engines: the dharma parity runtime (`langgraph_parity.swarm_runtime` / `supervisor_runtime`) AND a real langgraph `StateGraph` built with `langgraph-swarm`-style handoff tools / supervisor pattern (construct minimal equivalents with stub "models" — deterministic callables, no API keys, no network).
   - **Diff SEMANTIC outcomes, not text:** final active agent, message-visibility sets, transfer-receipt sequence, final state shape. Emit a machine-readable diff report artifact (JSON) per run.
   - Divergences are FINDINGS, not failures to hide: each one is either a spec bug (our clone misread LangGraph semantics) or a deliberate deviation to document in `docs/langgraph_parity/LANGGRAPH_PARITY_CONTRACT.md`. Adjudicate each in the PR body.
3. **CI:** a new workflow job (advisory first — `continue-on-error: true`; flips to blocking once it's been green for a week) that installs the extra and runs the oracle suite, uploading the diff report as an artifact. Model it on the existing nightly lane (`.github/workflows/nightly-tests.yml`).
4. **DST seed (small, honest scope):** introduce the fault-injection seam ONLY — a `graph/effects.py` with an injectable clock/rng/dispatch-order provider (protocol + default live implementation), used by `durable_invoker`. One seeded test that replays a recorded fault sequence (task death mid-dispatch) deterministically. The full DST harness is later work; do not gold-plate.
5. Acceptance: oracle runs ≥12 scenarios in CI with diff artifact; ≥1 real divergence found and adjudicated (either answer is a win); DST seed test replays a fault from a seed. Track criterion to flip: `phase1_oracle_tests_pass`.

## Gates you WILL hit

- **Hot-path ack:** `orchestrator.py` is on `HOTPATH_FILES` (`scripts/uplift_guards/hotpath_guard.py:16-42`) — your seam-call commit needs `[impact-checked]` in the message or `DHARMA_UPLIFT_ACK=impact-checked`.
- **Module budget:** `orchestrator.py` is at ceiling — if the guard trips on your seam call, shrink it (the wrapper call is one line + import).
- **Spine guard:** your modules live in `dharma_swarm/graph/` (outside the spine sqlite gate) but carry the convention header anyway: `# spine: memoizes EvidenceReceipt by idempotency key (owner: runtime_state) — no new store`.
- **Library floor applies to `graph/` from your first module** (spec §2): full type hints, `__all__`, tests alongside; this package is the one that gets mypy-strict later — don't create the debt.
- **No new truth stores; no gate weakening; never commit credentials; runtime receipts under `~/.dharma/`.** Pre-commit: `SKIP=semgrep-local pre-commit run --all-files`.

## Definition of done (whole lane)

Two PRs merged (invoker; oracle+DST seed), each with baseline-diffed test results and PR bodies citing `dharmagraph-engine-2026-07` + the spec section. The joint chaos receipt exists (with Devin's reconciler). The oracle CI job is live in advisory mode. Track criteria flipped: `phase0b_durable_invoker_tests_pass`, `phase1_oracle_tests_pass`.
