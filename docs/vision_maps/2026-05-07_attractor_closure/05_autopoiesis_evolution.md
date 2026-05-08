# 05 — Autopoiesis & Self-Production Layer

Read-only research note. 2026-05-07. file:line cited; UNKNOWN where unmeasurable.
Anchored to `~/.dharma/audit/self_evolution_trace_2026-05-07.md` ("APPLY GATE PRESENT BUT CLOSED").

---

## 1. Autopoiesis vs Selection

Selection is the immune system: a metabolic filter that ranks, gates, and accepts/rejects candidates that *something else* produces. Autopoiesis is stronger — the organism produces the organism: the boundary that defines what counts as self is itself a product of internal processes (Varela). For an agentic system, the autopoietic test is not "does the runtime have gates that filter proposals?" but "does the runtime *manufacture* the next gate, the next skill, the next organ from a recognized recurring pattern, and durably install it in itself?"

dharma_swarm currently leans **selection-heavy, autopoiesis-thin**. There are extensive selection surfaces — `gate_check` (`evolution.py:1359`), telos+kernel filters, Brier scoring, MAP-Elites cells, Reflexion reflection (`evolution.py:~2148`), four-Shakti warrants (`shakti_warrant.py:1`). Production-of-self surfaces exist as code but are either (a) shadow-mode-locked (`orchestrate_live.py:534`), (b) shape-only (`tools/build_protocol/seal_packet.py:1`), or (c) in-memory-only with no durable substrate (`strange_loop.py:115` — no `mutations.jsonl` file present in `~/.dharma/organism_memory/`). Recognition is alive (witness logs, stigmergy marks, observation streams); crystallization-of-recognition into a new organ is not.

---

## 2. The Two Apply Paths

The audit's central finding stands: two apply paths exist, neither connected to the other.

### Path A — Build Protocol (Sovereign Build Packet)

- Producer: `tools/build_protocol/pilot00_dryrun_generator.py:1-6` ("intentionally shape-only ... no agents, no SQLite, no source edits, no worktree")
- Sealer: `tools/build_protocol/seal_packet.py:1` ("Shape-only ReviewPacket and ProofPacket helpers"); produces a JSON dict with `decision`/`merge_decision="seal"`/`signed_by` fields (`seal_packet.py:54-63`) but no cryptographic signature and no filesystem writer
- Brief seam: `tools/build_protocol/brief_to_spec.py:1` reads morning briefing → spec under `~/.dharma/build_protocol/specs/`
- CLI consumer: `tools/build_protocol/cli.py:11`
- Importers in `dharma_swarm/dharma_swarm/`: **0** — `grep "from dharma_swarm.tools.build_protocol"` returns no in-package consumers (audit §4 confirmed).
- Runtime state (`~/.dharma/build_protocol/`): `dryruns/` 9 subdirs present, `sealed/` does not exist, `applied/` does not exist, `proofs/` does not exist. Drop-off is dryrun → seal: producer with no consumer.

### Path B — DarwinEngine (real diff-and-test)

- Real apply primitive: `evolution.py:2156` `DarwinEngine.apply_diff_and_test` → `DiffApplier.apply_and_test` (atomic fs write + pytest + auto-rollback)
- Generator: `evolution.py:2799` `generate_proposal` (LLM per source file); `evolution.py:2684` `_generate_real_diff`
- Pending bridge: `evolution.py:2989` `load_pending_proposals` ↔ `pending_proposals.py:9` (`~/.dharma/evolution/pending_proposals.jsonl`, currently 0 bytes)
- Live call site: `orchestrate_live.py:519-552`. Default `_shadow = os.environ.get("DHARMA_EVOLUTION_SHADOW", "1") != "0"` (line 534) → shadow ON. Floor `if not _shadow and _autonomy < 2: _shadow = True` (line 537). Overnight verdict overrides: HOLD forces shadow (line 544); ROLLBACK skips entirely (line 506-510).
- Rate limit: `swarm.py:229` `_max_auto_evolves_per_day = 6`.
- Commit step: `commit_if_worthy` (~`evolution.py:3260`) — only ever commits to a `darwin/cycle-N` branch (`orchestrate_live.py:559`), never to the consumed packets.

The two paths share no import edge. Path A produces shape; Path B applies LLM diffs in-process. Sealed BuildPackets are never read by `apply_diff_and_test`.

---

## 3. Catalytic Closure

`catalytic_graph.py:25` `CatalyticGraph` — Tarjan SCC over a directed graph of artifact relationships (`enables`/`validates`/`attracts`/`funds`/`improves`).

- **Does it run?** Yes, modestly. Importers: `orchestrate_live.py:760`, `evolution.py`, `graph_nexus.py`, `bridge_coordinator.py`, `orchestrator.py`. Live ingestion path: `orchestrate_live.py:758-789` — every consolidation tick, recent stigmergy marks are read (50-mark window), agents and observation-topics become nodes, agents that share topics get mutual `validates` edges (line 781-784), then `cg.save()`.
- **Inputs**: marks (agent, action, observation 40-char prefix). Not modules-as-nodes / imports-as-edges — that semantic graph would be the natural autopoietic substrate but is **not** what catalytic_graph operates on. The graph is a *behavioral* graph (who-acted-near-whom) not a *structural* graph (who-imports-whom).
- **Persistence**: `~/.dharma/meta/catalytic_graph.json` — present, 4677 lines.
- **SCC findings consumption**: `detect_autocatalytic_sets` (`catalytic_graph.py:164`), `revenue_ready_sets` (line 258), `loop_closure_priority` (line 213) are *callable* methods, but in `dharma_swarm/dharma_swarm/` there is **no production caller** that reads SCC output and acts on it. `summary()` (line 431) is the only consumer — used in introspection/dashboard. Findings are not piped back into proposal generation.
- **`seed_ecosystem`** (line 278) hardcodes 6 nodes (rv_paper, credibility, mi_consulting, rvm_toolkit, ura_paper, dharma_swarm) and 7 edges — a *narrative* seed for revenue-ready demos, not a measurement of the live system.

Verdict: catalytic graph is a **read sensor**, not a closure mechanism. SCCs are computed but not acted on. UNKNOWN whether `detect_autocatalytic_sets` has ever returned a non-empty set in production (no observable downstream).

---

## 4. Sediment-to-Crystallization

Sediment surfaces:
- `stigmergy.py:96` `StigmergyStore` → `~/.dharma/stigmergy/marks.jsonl`
- `auto_proposer.py:189` observation log → `~/.dharma/auto_proposer/observations.jsonl` (381 KB, 2026-05-01 last write)
- Witness logs → `~/.dharma/witness/`
- `~/.dharma/evolution/archive.jsonl` — 9652 lines
- `~/.dharma/evolution/predictor_data.jsonl` — 9361 lines

Crystallization paths attempted:
- `auto_proposer.py:540-656` `_observation_to_proposal_params` — recurrent observation patterns (FITNESS_DROP, FAILURE_PATTERN, STIGMERGY_HOTSPOT, FITNESS_PLATEAU, TEST_FAILURE_CLUSTER, EVOLUTION_STAGNATION) become `Proposal` objects via `darwin_engine.propose(...)` at `auto_proposer.py:709`.
- `consolidation.py:1006` `export_evolution_proposals` — capability_gap / fitness_gap items from a consolidation outcome are written to `~/.dharma/evolution/pending_proposals.jsonl`.
- That file is currently **0 bytes** (`wc -l`: 0). The crystallization channel exists; it has not been used recently or its output has been consumed and cleared without trace.

What does NOT exist (gap):
- No mechanism that mints a **new gate** from a recognized pattern. `dharma_kernel.py` and `telos_gates.py` are static (audit S8: 0 commits in the last 6 weeks; not on any DarwinEngine editable surface).
- No mechanism that mints a **new skill** from a recognized pattern. Skill creation is via `~/.claude/skills/` and `superpowers:writing-skills` — outside dharma_swarm's runtime.
- No mechanism that mints a **new organ** (module/class) from sediment. Proposals are bounded to existing files (audit S2: "cannot import a new external dependency or scaffold a new module").

Tracing one example: 381 KB of `observations.jsonl` → 91 KB `proposals.jsonl` → 0 bytes pending → archive.jsonl 9652 lines. The crystallization that *did* happen produced LLM-generated diffs to existing files, gated by shadow-mode env vars, never installed (Path B above). No new gate, skill, or organ was crystallized in this trace.

---

## 5. Shakti Executive Loop

Edges, in order:

1. `inputs.py:15` `read_all_signals(state_dir)` — pulls four sources: `meta/zeitgeist.jsonl`, `scouts/*/latest.json`, recognition seed, operator directives. Pure read.
2. `scoring.py` `candidates_from_signals(signals)` — deterministic ranking with internal/revenue/research keyword sets.
3. `executive.py:31` `ShaktiExecutive.run(write=True, top_k=12, min_score=45.0)` → `_merge_board` (line 110) → `_write_board_atomic` (line 133) writes `~/.dharma/meta/opportunity_board.json` (1654 bytes, last write 2026-05-07 09:09 — alive).
4. Schedulers: `scripts/shakti_executive_run.py`, `dharma_swarm/cron_runner.py` — invoked on cadence, not in main organism loop.
5. Consumer: `opportunity_dispatcher.py:1` — Layer B promoter (PR1: scope-stage only). Reads board → creates campaign manifest under `~/.dharma/campaigns/{opp_id}/` → calls `TaskBoard.create` at `task_board.py:214` (referenced `opportunity_dispatcher.py:500-515`) → tasks.db.
6. `opportunity_refill.py:173` `CurriculumEngine().derive_from_opportunity_board(...)` → `~/.dharma/meta/frontier_tasks_pending.jsonl`.
7. Telos gate before dispatch: `telos_gates.py:783` `check_action` (REVIEW silently treated as ALLOW + WARN per `opportunity_dispatcher` PR1 doctrine, lines 416ff).

**Does the loop close back to the executive?** **No.** ShaktiExecutive is purely populator-side: it reads zeitgeist/scouts/recognition/operator and writes the board. There is no feedback edge that takes (a) which board entries were dispatched, (b) which produced ValueEvent/Outcome rows, (c) which the orchestrator marked successful, and feeds those outcomes back into `scoring.py` weights or `inputs.py` source priors. Outcomes are visible to the dashboard / health.json / Telic Seam, not to ShaktiExecutive's next run. The board is a one-way lane; the executive does not learn from what dispatcher did with its output.

Author's docstring confirms: "downstream execution remains owned by existing lanes" (`executive.py:23`). The "open mystery" at `opportunity_dispatcher.py:74` — who else writes the board besides ShaktiExecutive and human seeders — also indicates the producer side is not unified.

---

## 6. Diversity Archive

`diversity_archive.py:85` `DiversityArchive` — MAP-Elites grid keyed by `BehaviorDescriptor.dimensions` ∈ [0,1]. `add` / `sample_diverse` / `coverage` / `best_per_dimension` / `stats`. Persistence path: `~/.dharma/evolution/diversity_archive.json` (`diversity_archive.py:39-41`).

- **Is the archive populated?** **No.** `~/.dharma/evolution/diversity_archive.json` does not exist (verified). `coverage()` would return 0.0.
- **Does anything read from the archive when generating new proposals?** **No production reader.** `grep "from dharma_swarm.diversity_archive"` returns 0 importers in `dharma_swarm/dharma_swarm/`. Tests reference it; live code does not. The MAP-Elites primitive exists; it is unwired to evolution.

This is the canonical example of the "vision/runtime gap" Dhyana logged on May 4 (memory entry 2173): a visionary architecture (MAP-Elites for transcendence diversity, per the CLAUDE.md "Transcendence Principle") with zero runtime importers. The Krogh-Vedelsby diversity term that CLAUDE.md says must be tracked is not being computed in production.

---

## 7. Self-Correction

`dynamic_correction.py:1` — Isara-style monitor + auto-corrector.

- **Activation**: env var `ENABLE_DYNAMIC_CORRECTION` defaults to `"true"` (`dynamic_correction.py:35`).
- **Importer**: only `organism.py:235-251` — initialized at organism boot under try/except, "non-fatal" on init failure (line 253).
- **Drift types** (line 48): QUALITY_DEGRADATION, BUDGET_OVERRUN, STUCK_AGENT, DHARMIC_DRIFT, LOOP_DETECTED, ERROR_CASCADE.
- **Actions** (line 59): WARN, THROTTLE, REROUTE, RESTART, ESCALATE, HIBERNATE, EVOLVE.
- **Persistence**: SQLite (`sqlite3` import at line 21) — UNKNOWN actual table layout from this read; need to read further.
- **Durability of correction**: Per the dataclass at line 76, `DriftSignal.resolved: bool = False` is a state field. Corrections THROTTLE/REROUTE/RESTART/HIBERNATE are runtime-state changes (live in-process) — NOT durable substrate edits. The EVOLVE action *would* trigger a substrate edit; UNKNOWN whether the EVOLVE branch is implemented or aspirational (further read needed).

Verdict: dynamic_correction is a **runtime course-corrector** — it moves the live system within its current parameter space. It does not produce durable substrate change unless EVOLVE is wired to DarwinEngine.propose, which I cannot confirm from this trace.

`canonical_replay.py:47` `CanonicalReplayEngine` reads `~/.dharma/events/` and validates determinism. Provides the proof surface that *would* let a self-correction be safely retried — but is not invoked by `dynamic_correction.py` in any code path I traced.

`strange_loop.py:107` `StrangeLoop` is the closest in-memory version of an autopoietic correction loop: observe→propose→apply→measure→keep/revert (lines 4 docstring). Mutations are stored in `self._mutations: list[Mutation]` (line 118) — **in-memory only**; `~/.dharma/organism_memory/mutations.jsonl` does not exist on disk. `tick()` at line 125 fires every 10 heartbeats (line 121); `_apply_mutation` at line 239 mutates `OrganismConfig` parameters (routing_bias, scaling thresholds, heartbeat_interval — line 39-49) live but does not persist them. On organism restart, all strange-loop learning is lost.

---

## 8. Closure Verdict — Loop-by-Loop

| Loop | Status | Evidence |
|------|--------|----------|
| Sediment → recognition (stigmergy + observations → AutoProposer) | **CLOSED** | `auto_proposer.py:505 observe`, 381 KB observations.jsonl, 91 KB proposals.jsonl |
| Recognition → proposal (observation type → DarwinEngine.propose) | **CLOSED** | `auto_proposer.py:709`; `evolution.py:1228 propose` |
| Proposal → evaluate (gate_check + fitness scoring) | **CLOSED** | `evolution.py:1359 gate_check`; `evolution.py:1480 evaluate` |
| Proposal → seal (Build Protocol) | **OPEN** (no writer) | `seal_packet.py:1` is shape-only; `~/.dharma/build_protocol/sealed/` absent; 0 importers in main package |
| Sealed → proof (run proof_command, score outcome) | **OPEN** (no consumer) | proofs/ dir absent; no `proof_packet` reader exists |
| Proposal → apply (DarwinEngine.apply_diff_and_test) | **BLOCKED** (env-locked) | `orchestrate_live.py:534` shadow=1 default; line 537 autonomy<2 floor; line 544 HOLD override |
| Apply → re-recognize (post-apply outcome → next observation) | **OPEN** | DarwinEngine writes `archive.jsonl` (9652 lines) but archive is not read by `auto_proposer.observe` — observations come from monitor.check_health, not from prior apply outcomes |
| Sediment → new gate / new skill / new organ (crystallization) | **OPEN** | `dharma_kernel.py` and `telos_gates.py` static for 6+ weeks; no mechanism proposes gate edits; skills live outside runtime |
| Catalytic SCC → action | **OPEN** | `detect_autocatalytic_sets` has no production caller |
| Diversity archive → proposal generation | **OPEN** | `diversity_archive.json` absent on disk; 0 in-package importers |
| Strange loop (organism config self-mutation) | **PARTIAL / NON-DURABLE** | In-memory `_mutations` list; `mutations.jsonl` absent; lost on restart |
| Shakti executive → opportunity board → tasks.db | **CLOSED** (forward only) | `executive.py:53 _write_board_atomic`; `opportunity_dispatcher.py:500-515 TaskBoard.create` |
| Tasks.db outcomes → Shakti executive next run | **OPEN** | No outcome → executive feedback edge; executive reads scouts/zeitgeist only |
| Dynamic correction → durable substrate | **OPEN/UNKNOWN** | Runtime parameter changes only confirmed; EVOLVE-action-to-DarwinEngine wiring unverified |
| Consolidation → pending_proposals → DarwinEngine | **CLOSED** in code, **DORMANT** in state | `consolidation.py:1006 export_evolution_proposals`; `pending_proposals.jsonl` 0 bytes |

**The chain breaks first at S6 (apply gate)** — exactly where the audit said. Even where the upstream half is closed (sediment → recognition → proposal → evaluate), the apply step is environment-locked OFF by default. Independently and earlier in the second branch, the chain breaks at "seal" — Path A never produces a sealed packet anyone reads.

---

## 9. Open Questions

1. **What is the canonical apply path?** Path A (Build Protocol) is shape-only; Path B (DarwinEngine) is shadow-locked. There are *two* would-be apply mechanisms and neither has applied a sealed-and-proven packet. Which should be canonical, and is the other dead code or a parallel design that was never collapsed?
2. **What is `~/.dharma/HALT_DARWIN_PROPOSALS`?** Audit notes 0 source references. If this is a kill switch, who writes/reads it? If unimplemented, why does the audit's Section 5 propose it as a "cheap kill switch — currently referenced 0 times" and why hasn't anyone noticed?
3. **Why is `pending_proposals.jsonl` 0 bytes?** `consolidation.py:1006 export_evolution_proposals` exists; `evolution.py:2989 load_pending_proposals` exists. Either consolidation has not run with `outcome` containing capability_gap/fitness_gap items, or the file is being consumed and cleared without leaving a trail. UNKNOWN which.
4. **Is catalytic_graph behavioral when it should be structural?** The graph is keyed on `agent:X` and `obs:topic_prefix` (`orchestrate_live.py:771-774`). For autocatalytic *capability* detection (which skill enables which other skill), the natural keys would be modules/skills/symbols. Was the behavioral choice deliberate (acting subjects matter more than acting tools) or accidental (it was the easy data to ingest)?
5. **Where is `mutations.jsonl`?** `strange_loop.py:107` claims "the simplest possible strange loop" with persist mention in docstring (~line 4); CLAUDE.md `/Users/dhyana/dharma_swarm/CLAUDE.md` lists `~/.dharma/organism_memory/mutations.jsonl` as a state path. The file does not exist. Is `StrangeLoop` actually persisting, or was the persistence layer planned and never written?
6. **Diversity archive: aspiration or abandonment?** CLAUDE.md asserts MAP-Elites is canonical for the Transcendence Principle and "DarwinEngine MUST preserve diversity" via `diversity_archive.py`. The runtime never imports it. Either DarwinEngine's diversity-preservation claim is aspirational, or another mechanism (e.g., `archive.MAPElitesGrid`) does the work and `diversity_archive.py` is the orphaned newer version.
7. **What is the recognition → crystallization missing piece?** A gate-minting mechanism would need: (a) a stable recognized pattern (recurring witness/stigmergy/observation type that survives N consolidation cycles), (b) a generator that proposes a kernel/gate edit as a unified diff, (c) an applier that respects the SHA-256 axiom signature on `dharma_kernel.py`. None of these three currently compose. Is this deliberately deferred (per the safety stance: gates change only by Dhyana's hand) or an unmet requirement?
8. **Does ShaktiExecutive close back via TCS?** `identity-coherence` skill mentions S5 telos coherence tracking computed from gate passage / behavioral swabhaav / research momentum. UNKNOWN whether that signal flows into `inputs.py` of the executive. If it did, the executive would learn from runtime telos drift; if not, the executive remains a one-way zeitgeist→board pipe.

---

## 10. 200-Word Summary

**Closed loops**: sediment-to-recognition (stigmergy + observations → AutoProposer), recognition-to-proposal (observation → DarwinEngine.propose), proposal-to-evaluate (gate_check + Brier scoring), Shakti-executive-to-task-board (opportunity_board.json → tasks.db via opportunity_dispatcher), and consolidation-to-pending-proposals as code (though the file is currently empty).

**Open loops**: Build Protocol's seal step (shape-only producer, no consumer; 9 dryrun dirs, zero sealed/applied), proof-to-apply (no proof_packet reader), apply-to-re-recognize (archive.jsonl is not read by observe), sediment-to-crystallization (no mechanism mints new gates/skills/organs), catalytic-SCC-to-action, diversity-archive-to-proposal-generation (file absent on disk; zero in-package importers), strange-loop persistence (`mutations.jsonl` absent — in-memory only), executive-feedback (outcomes never flow back into Shakti scoring), and dynamic-correction-to-durable-substrate.

**Where the chain breaks first**: edge S6 — the apply gate. `orchestrate_live.py:534` defaults `DHARMA_EVOLUTION_SHADOW=1`, requires `DGC_AUTONOMY_LEVEL>=2`, and overnight HOLD/ROLLBACK verdicts force-shadow. Even when opened, the apply mechanism only consumes freshly-generated LLM diffs in-process, not sealed BuildPackets. The two would-be apply paths are not wired together.

**Top open question**: which of Path A (Build Protocol) and Path B (DarwinEngine) is canonical, and why does the system carry both apply surfaces with no import edge between them?

---
*Read-only research. No source modified. Cite this file when invoking S1-S8 edges or "two apply paths."*
