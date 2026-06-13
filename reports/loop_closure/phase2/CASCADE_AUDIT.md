# Loop-Closure Phase 2 — Cascade Audit (honest per-loop LIVE / NOT-LIVE)

**Generated:** 2026-06-13 (UTC) · **Track:** `loop-closure-2026-06` · **Owner surface:** `reports/loop_closure/**`, `CYBERNETIC_LOOP_MAP.md`
**Source of verdicts:** `scripts/governance/orientation_graph.py` (`build_loop1_closure` + `build_loop_closures`), run read-only against live `~/.dharma/` receipt surfaces. No surface was written.

This audit reports the *fed-cascade* batch — Loops `[6, 2, 5, 9, 3, 4, 7, 8, 10, 11]` — plus the Loop 1 trunk for context. Each verdict below was reproduced live and matches the orientation-graph output exactly. **No loop overclaims LIVE today.** Every LIVE/PARTIAL verdict reads a fresh real surface; every NOT-LIVE verdict has a named structural blocker. Verdicts are honest in the non-overclaiming direction: a loop will report NOT-LIVE when fresh real data is absent, never LIVE off stale or fixture data (with one out-of-batch caveat noted at the bottom).

## Verdict summary

| Verdict | Count | Loops |
|---|---|---|
| LIVE | 2 | 1 (trunk), 5 |
| PARTIAL | 2 | 6, 2 |
| NOT-LIVE | 7 | 9, 3, 4, 7, 8, 10, 11 |

LIVE-or-better (LIVE + PARTIAL) sense/constrain arms: 4. Fully closed sense→adapt cycles on real data: **0** — every adapt arm is gated behind the still-unclosed Loop 1 continuous provider chain.

## Per-loop table

| Loop | Name | Verdict | Receipt surface (read) | Non-closing / closure-ceiling reason |
|---|---|---|---|---|
| 1 | Loop 1 Trunk (provider chain + dispatch) | LIVE | `~/.dharma/state/runtime.db` → `delegation_runs.receipt_json` (latest by `started_at`) | Closes today: latest dispatch receipt carries `provider=ollama model=mistral:latest`, real OllamaProvider dispatch routed through the spine. **Caveat:** the check has no freshness guard (see Falsifiability gap below) — truthful only because today's receipt is genuinely fresh (~05:29 UTC). Receipt was produced by an explicit prover (`loop1_e2e_prover` / `prove_loop1_spine_ollama.py`), not yet organic continuous loop traffic. |
| 6 | Witness Auditor | PARTIAL | `~/.dharma/witness/witness_20260613.jsonl` (daily JSONL, `telos_gates.py:792 _log_witness`); audit-finding receipt `~/.dharma/witness/anomaly_signals.jsonl` (`witness.py` WitnessAuditor LLM organ) | SENSE+CONSTRAIN arm is LIVE and fresh (587 rows today; latest PASS ~9 min old; outcomes discriminating PASS/BLOCKED/WARN proving the AHIMSA/SATYA gate constrains; 452/587 real loop-action rows — pulse/dispatch/landscape-probe, not sentinels). Ceiling is PARTIAL: the **ADAPT arm** — WitnessAuditor LLM trace-evaluation in `anomaly_signals.jsonl` feeding evolution fitness — is provider-gated behind the unclosed Loop 1 continuous chain. Check reads row-level `ts`, not the filename, so a stale-row today-named file → NOT-LIVE (falsifiable). |
| 2 | Organism Heartbeat | PARTIAL | `~/.dharma/algedonic_signals.jsonl` (`kind=omega_divergence/telos_drift`, heartbeat-sourced, `swarm.py:1475 _algedonic_handler`); decision store `~/.dharma/organism_memory/entities.jsonl` (`algedonic_event/gnani_verdict`) | SENSE→INTERPRET fired today (fresh `omega_divergence`, value ~0.408, moving across a real multi-value history — a genuine OrganismPulse invariant, not a constant sentinel). ACT/ADAPT does **not** close: the heartbeat-decision store is ~36 h stale, no heartbeat daemon running, and `SIGNAL_HEARTBEAT` lands on an in-memory `SignalBus` with no durable receipt. The bulk of today's algedonic traffic is orchestrator `task_retries_exhausted` dead-letters, not heartbeat output. Check reads the real decision-store timestamp → genuinely stale → PARTIAL (falsifiable). |
| 5 | Zeitgeist Scanner | LIVE | `~/.dharma/meta/gate_pressure.json` (ADAPT-half S3↔S4 receipt, `s4/internal_pressure.py:123 _write_gate_pressure`, read by `telos_gates.py:385/441 _apply_gate_pressure`) | S3↔S4 feedback mechanically closes on real data: `gate_pressure.json` is fresh (mtime ~1 min, `trust_mode_override=external_strict`, not expired, expires_in ~3.3 ks), and the driving witness BLOCKED window contains 9/22 rows carrying real loop-action work (`pulse`), not test fixtures (13 fixture rows correctly excluded). **Honest note:** those 9 BLOCKED rows are `pulse` system-heartbeat actions with `agent_id: null` — genuine non-fixture loop work, but heartbeat-attributed, not agent-attributed. The reason string was corrected this session to say "real loop-action work" rather than "real-agent-attributed" (phrasing overclaim fixed; verdict unchanged and defensible). An expired/stale gate → NOT-LIVE; a fixture-only BLOCKED window → PARTIAL (both falsifiable). |
| 9 | Conductors | NOT-LIVE | `conductor_wake` witness entries + `~/.dharma/shared/conductor_*_notes.md` | Honest NOT-LIVE: **0** `conductor_wake` rows today, and conductor wakes only emit pre-action telos-gate WARN proposals (no provider-backed act/adapt receipt). Conductor work is blocked on an available LLM — i.e. gated behind Loop 1. Named blocker, not laziness. |
| 3 | Evolution Loop | NOT-LIVE | (closing arm: real `FitnessScore` → `~/.dharma/evolution/archive.jsonl`) | `_loop1_gated`: evolution machinery records meta-updates, but real `FitnessScore` computation (ADAPT arm) is blocked on Loop 1 producing **completed** tasks. No closing receipt exists until then. Honest-but-static (will not auto-flip TO live without a code change once Loop 1 closes). |
| 4 | Consolidation Loop | NOT-LIVE | (closing arm: consolidated real agent outputs) | `_loop1_gated`: consolidation + dedup pipeline runs on heartbeat data, but there are no agent-produced outputs to consolidate until Loop 1 closes. |
| 7 | Training Flywheel | NOT-LIVE | (closing arm: scored real agent trajectories) | `_loop1_gated`: quality-gate evaluations run, but trajectory scoring/reinforcement (ADAPT arm) has no real agent trajectories until Loop 1 produces them. |
| 8 | Recognition Loop | NOT-LIVE | (closing arm: eigenform convergence → recognition seed) | `_loop1_gated`: recognition-seed computation is wired, but eigenform convergence over real loop history (ADAPT arm) awaits `LoopEngine` activation, itself gated by Loop 1. |
| 10 | Context Agent | NOT-LIVE | (closing arm: running `AgentRunner` w/ real provider) | `_loop1_gated`: depends entirely on a running `AgentRunner` with a real provider; no closing receipt exists until Loop 1 closes. |
| 11 | Replication Monitor | NOT-LIVE | (closing arm: replication trigger events) | `_loop1_gated`: replication path is structurally correct (MM-02/03 resolved) but no trigger events have fired; closing arm gated behind Loop 1. |

## Why the NOT-LIVE loops are honest

The seven NOT-LIVE verdicts are not failures of this audit's diligence — they are the truthful state of the cascade:

- **Loop 9** has its own named blocker on disk: zero `conductor_wake` rows today and WARN-only proposals, verified live.
- **Loops 3, 4, 7, 8, 10, 11** are hardcoded NOT-LIVE via `_loop1_gated()` with a named structural reason each. This is honest in the non-overclaiming direction — they can *never* falsely show LIVE — and their docstrings correctly state no closing receipt exists until Loop 1 produces completed agent tasks. The only honesty caveat is that they are **honest-but-static**: they will not auto-flip TO live if those loops genuinely close; that would require a code change to give each a real data-driven check once Loop 1 supplies continuous traffic.

All of these await Loop 1's **continuous** data — i.e. the daemon merge + restart that turns the one-shot prover receipt into organic dispatch traffic — or have their own named upstream blocker. Until that lands, the cascade's adapt arms cannot close, and reporting them LIVE would be the overclaim this audit is built to prevent.

## Falsifiability gap (out of Phase 2 batch — recommendation, not a current overclaim)

`build_loop1_closure` (Phase 1b) has **no freshness guard**: it orders `delegation_runs` by `started_at DESC` and only checks `bool(provider and model)` on the newest receipt. A synthetic year-2020 (or year-2027) receipt returns `live=True` (proven empirically with a synthetic db). Today's Loop 1 LIVE claim is still truthful — the real receipt is genuinely fresh (~05:29 UTC, `ollama`/`mistral:latest`, `status=ok`) — but Loop 1 would **not** flip to NOT-LIVE if dispatch went stale.

**Recommendation:** add an age check on `started_at` to `build_loop1_closure` (mirror the `_FRESH_WINDOW_S` 24 h gate the Phase 2 builders already use). This is deliberately *not* applied here: it is Phase 1b code outside the Phase 2 batch, and Loop 1 is not overclaiming today. It is logged so the trunk check gains the same falsifiability the cascade checks already have.

## This session's correction

One phrasing overclaim was found and fixed in `scripts/governance/orientation_graph.py` (`build_loop5_closure`): the LIVE reason string previously read `"… BLOCKED rows are real-agent-attributed"`, but those rows are `pulse` heartbeat actions with `agent_id: null` (genuine non-fixture loop work, but system-heartbeat-attributed). The reason now reads `"… BLOCKED rows carry real loop-action work (pulse/dispatch/landscape-probe), not test fixtures"`. The **LIVE verdict itself was correct and unchanged** — only the evidence wording was tightened to match what is on disk.
