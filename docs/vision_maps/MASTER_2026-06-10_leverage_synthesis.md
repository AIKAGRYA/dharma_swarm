# MASTER SYNTHESIS — 2026-06-10 — Leverage Seams for Closing the Recognition Loop

**Provenance**: 33-agent verification workflow `wf_c54d96cf` (2.88M tokens, 1,691 tool calls, 35.8 min),
6 parallel subsystem readers → per-finding independent cross-checkers → 3-lens ranking panel.
Run journal + full agent transcripts: `~/.claude/projects/-Users-dhyana/5a77dde9-4737-41f2-83af-4962dec6903b/`.
Raw structured result (188KB): `reports/recovery_wf_c54d96cf_2026-06-10.json`.
**Caveat**: Reader C (Evolution/Gates/Nativeness) crashed before emitting structured output; its F4/F5/Q3
verdicts below are reconstructed from its 47 completed tool calls' evidence (transcript
`agent-a0f5c2234d162939d.jsonl`) — labels inferred from evidence, not the agent's own words.
**Evidence discipline**: every claim SUPPORTED / PARTIAL / CONTRADICTED / UNKNOWN with file:line,
matching `MASTER_2026-05-07_attractor_closure_synthesis.md`.

---

## 0. The headline (10 lines)

1. **The thesis holds, sharpened**: recognition is commentary, not cause — but via *miscalibration + dormant bridges + deploy-split*, not absence of machinery.
2. **All three ranking lenses independently converge on the same #1 seam**: the live daemon does not run the code anyone audits or merges.
3. Verified: pid 90717's python3.11 editable install maps `dharma_swarm` → `~/dharma_swarm_cashclaw` (branch `cashclaw/revenue-hydra-v1`, 5 behind origin/main) — **not** `~/dharma_swarm` (on `qwen/spine-adoption`, itself 8 behind), **not** main.
4. Therefore #555 (multi-track governance), #556 (archive flock), #557 (spine dispatch) are **merged-but-not-running**; `DHARMA_SPINE_DISPATCH` is absent from all live code.
5. F1–F6 SUPPORTED, F7 PARTIAL: three ontology↔runtime bridges exist and are ALL dormant; the lodestone seeded zero objects ever (swallowed TypeError); the recognition seed asserts "0d to abstract (crunch)" for a conference 76 days dead.
6. The DarwinEngine archive is **vacuously positive, not flat**: shadow strips every diff (`evolution.py:3200`), empty diffs auto-pass at 1.0 (`:2216-2217`), status hardcoded "applied" (`:1768`) — 2,585 "applied" rows, 116 real diffs (1.04%), 0 lineage.
7. A second, unmapped inward loop (`self_improve.py`, hourly, no shadow gate) has run 787 cycles and **never applied a single diff** (proposals always carry `diff=""`).
8. All 11 telos gates are keyword heuristics; Tier-C failures yield advisory REVIEW; on main, REVIEW-decision proposals still archive as "applied" (`evolution.py:1460-1474` + `:1768`); the WS4a enforcement exists only in the ds_ws4 worktree (PR #558, open).
9. The smallest first PR: a `dgc status` running-package-provenance check (~60 lines, `manifest_health.py` + `dgc_cli.py`) + one ops repoint of the editable install — converts three merged PRs from dead weight into live behavior.
10. Revenue remains $0 lifetime with zero external-reader receipts; the Jun-9 consolidator audit diagnosed "diagnosis addiction" in writing and then kept auditing — the system can produce accurate self-description it cannot act on. That is the wound, measured.

---

## 1. Thesis verdict

> *"dharma_swarm is a telos-gated Darwin–Gödel machine whose recognition is currently commentary, not cause, because (a) ontology.db and runtime.db are two unsynchronized stores, and (b) the inward self-evolution loop is structurally present but its apply-gate is CLOSED and its fitness signal is flat."*

**Verdict: SUPPORTED, with three sharpenings.**

- (a) is understated: not two stores but **multiple diverging instances of each** (X5) — `ontology_runtime.py:36-39` prefers `cwd/.dharma/ontology.db` while `ontology_hub.py:31` hardcodes `~/.dharma/ontology.db`; both exist and both are large (100MB vs 14.7MB). `runtime.db` exists 4×, one empty instance touched today by an active writer at a wrong path.
- (b)'s "fitness flat" is wrong in an important direction: the signal is **vacuously inflated** — 96.7% of 11,164 archive entries sit in [0.42, 0.47] because empty diffs auto-earn pass_rate 1.0 and status="applied" is hardcoded. The organism actively records becoming that never happened.
- (c) NEW, and rank-1: even where merged code fixes (a) and (b), **the running daemon cannot load it** — the deploy layer is itself a third, unaudited tree.

---

## 2. F1–F7 verdicts

| F | Verdict | Sharpened claim (file:line) |
|---|---------|------------------------------|
| **F1** two unsynchronized stores | **SUPPORTED** | Three bridges exist, all dormant: `engine/store_sync.py` cron `enabled:false` live + daemon path requires `DHARMA_FRACTAL_ROOMS=1` (disabled, `orchestrate_live.py:1793-1800`); 0/1,357 artifact_records have `ont-` prefix vs 3,031 Outcomes. Reverse bridge `ontology.py:818,:952` fires only with `execution_identity+runtime_state` passed — 0 ontology receipts ever. Spine seam `persist_receipt` (`spine/persistence.py:50`) has **zero production callers**; 0/3,495 delegation_runs carry receipt_json. |
| **F2** recognition seed stale | **SUPPORTED** | Seed is FRESH and INJECTED (2h loop live, `orchestrate_live.py:966-1007`; injected at context position 1, `context.py:1248-1267`) but calibrated against a dead calendar: `meta_daemon.py:273-287` hardcodes COLM 2026 deadlines, clamps to 0, asserts "crunch" since ~2026-03-19 for a shelved paper. Injection is also provider-gated (`agent_runner.py:982`) to exactly the CLAUDE_CODE agents currently failing on ANTHROPIC_API_KEY in --bare mode. |
| **F3** lodestone inert | **SUPPORTED, stronger** | Never seeded anything: boot flag records `{stigmergy_marks:0, concept_nodes:0, telos_objectives:0, task_seeds:0}` (Apr 10), all four seeders swallow exceptions and return 0 (`gnani_lodestone.py:455,465,494,544,587`); verified root cause: `ConceptGraph(telos_dir=...)` vs signature `__init__(self, state_dir=None)` (`graph_nexus.py:117`) — instant TypeError, swallowed. Flag-file existence reads as green in `swarm_health_api.py:74` and `guardian_crew.py:351`. |
| **F4** apply-gate closed, fitness flat | **SUPPORTED** *(reconstructed)* | Env-lock: shadow default ON + requires `DGC_AUTONOMY_LEVEL>=2` (`orchestrate_live.py:612-615`, `dgm_loop.py:289-291`); live daemon env has neither var set. Shadow strips diffs (`evolution.py:3196-3200`); status hardcoded "applied" + `gates_passed=["ALL"]` (`:1768-1773`); parent_id dropped at the dgm_loop→auto_evolve seam (`dgm_loop.py:387-393`). Archive: 0% lineage, 1.04% real diffs, 96% correctness exactly zero, weighted fitness stdev 0.029. The consumer for a real benchmark already exists: `apply_diff_and_test` (`evolution.py:2193`) + 11,201 collected tests. |
| **F5** gates advisory/keyword | **SUPPORTED** *(reconstructed)* | All 11 gates substring/keyword (`telos_gates.py:250-261`); BHED_GNAN is a literal hard-pass (`:539`); WITNESS's mandatory-phase block is converted to PASS by its own reroute scaffold (`:948-971`); Tier-C FAIL → advisory REVIEW (`:693-728`); `gate_check` maps REVIEW → GATED → archived "applied" (`evolution.py:1460-1474`). The SELF_MOD_SEMANTIC gate exists in live `gate_proposals.jsonl` but `status:"proposed"` — `_load_custom_gates` loads only approved (`telos_gates.py:166,271-285`), so the highest-stakes gate is inert. WS4a enforcement lives only in ds_ws4 (PR #558, open). Companions fail open: `dharma_attractor.py:174-178` (proceed-on-exception), `witness.py:1-16` (retrospective only), `persistent_agent.py:492` (X4: gate returns None on exception, None proceeds). |
| **F6** canon renders one track behind | **SUPPORTED** | And the canon itself is forked: local `qwen/spine-adoption` declares spine-adoption ACTIVE (commit c28951d5b, never pushed), origin/main's v2 (#555) declares a different portfolio not containing that track at all. Renderer check wired only into CI on PR-to-main (`.github/workflows/active-track.yml:21,65`), not pre-commit, so local drift is free. |
| **F7** sprawl below dispatch layer | **PARTIAL** | Real but every number moved: 81 worktrees (not 92), dirty 236 → **43,467** (42,513 staged-never-committed; 30,045 under `reports/revenue_wedge`, 12,135 under `reports/forge`). The dominant sprawl relocated from worktrees into the primary index — no lane-map category names it. |

## 3. Q1–Q5 answers

| Q | Verdict | Answer |
|---|---------|--------|
| **Q1** any loop closed in production? | **PARTIAL** | The month-old "42/42 all dispatch_dropoff" is CONTRADICTED: 3,495 delegation_runs, 1,444 completed. But "fully closed" remains unproven: latest non-test burst (Jun 9) was 100% dispatch_dropoff; **today: 0 delegation_runs, 0 task_claims** despite daemon restart 10:40:32. The Jun-9 `gate1-*` completions carry execution_identity — #557's GATE 1 was real, on the merged branch the daemon doesn't run. |
| **Q2** organs spine-attached? | **SUPPORTED (still zero)** | 0 organs attached to all 8 surfaces; best is operator_brief at 2/8 strict. Darshan's 13 modules exist only in an unmerged commit; main has zero tracked venture_cell files. Attachment is migrating from the doctrinal 8-surface rubric to the runtime-receipts spine without the rubric ever being re-audited. |
| **Q3** nativeness: 81.2% vs 10–15%? | **SUPPORTED — two spines** *(reconstructed)* | (a) 10–15% = informal whole-runtime ontology-nativeness, **asserted-not-derived** (its cited source `000_MASTER_COHERENCE_SYNTHESIS.md` contains no percentage at all); (b) the metric = static pattern-presence over 16 pre-declared spine surfaces, currently **93.8** on origin/main (81.2 was a transient snapshot in the 75.0→81.2→93.8 auto-refresh history). Different numerators, denominators, methods. The metric is real and test-covered but counts "adapter-ready" in the numerator and measures code presence, not runtime flow. |
| **Q4** receipt invariant by construction? | **PARTIAL** | Holds by convention and tests only: `invoke_agent` (`spine/invoke.py:36-55`) is a pure pass-through — nothing constructs/validates/persists; `persist_receipt` has zero production callers; live orchestrator calls `runner.run_task` directly (zero invoke_agent callsites in the running tree). |
| **Q5** phantom-fix implemented? | **PARTIAL** | A real 28-module memory_kernel exists with surface-level provenance (TruthState, AuthorityLevel, promotion gate requiring human review); `~/.claude/projects` is classified RAW/LOW/HIGH-risk. But per-ENTRY operator-vs-agent provenance on the memory files Claude actually consumes remains unimplemented prose. |

---

## 4. New findings (X1–X10) — what neither prior map saw

| X | Verdict | Finding |
|---|---------|---------|
| **X1** | SUPPORTED, **corrected by cross-check** | **The daemon runs a third tree.** Initial reading (plist cd's into `~/dharma_swarm` on qwen/spine-adoption) was refuted on the mechanism: the daemon is `/opt/homebrew/bin/dgc` on python3.11, whose editable install (`__editable___dharma_swarm_0_1_0_finder.py`) maps the package to `~/dharma_swarm_cashclaw` (`cashclaw/revenue-hydra-v1`, 25d1e2c27, Jun 8, 5 behind origin/main). The `.venv` pth pointing at `~/dharma_swarm` is python3.13 — never activated by the daemon. Functional conclusion unchanged: #555/#556/#557 not running, `DHARMA_SPINE_DISPATCH` absent from live code. |
| **X2** | SUPPORTED, **corrected by cross-check** | **A second inward loop nobody mapped**: `SelfImprovement` (`self_improve.py`, hourly via `orchestrate_live.py:2156`, no shadow gate, DiffApplier aimed at the real working tree). Correction: across all 787 lifetime cycles it has **never applied a diff** — proposals always carry `diff=""` and `self_improve.py:380-381` gates apply on non-empty. The "rolled back" lesson strings are unconditional boilerplate (`:424-426`). Structurally a live in-place applier; operationally a test-runner that measures but never mutates. |
| **X3** | SUPPORTED | The freshest build lane — **sovereign holons** (Jun 8–10, 27 docs, 19 verify receipts, new runtime code) — exists only staged/untracked in the stale worktree. Its own verifier was edited mid-run by the builder, in a lane whose LAUNCH.md declares self-certification a hard failure mode. |
| **X4** | SUPPORTED | Persistent-agent wake loop's gate fails open (`persistent_agent.py:492` returns None on exception; None proceeds at :408-410); two conductor agents run through it today. AutonomyPolicy validated at registration, never read at runtime; only 5 hardcoded PRESET_AGENTS reachable while 46 registered selves are inert data. |
| **X5** | SUPPORTED | Store multiplication: 2 ontology.db instances (100MB live + 14.7MB repo-local), 4 runtime.db instances — one empty, touched today by an active writer at a wrong path. Path resolution differs per module (`ontology_runtime.py:36-39` vs `ontology_hub.py:31`). |
| **X6** | SUPPORTED | `~/.dharma/witness/chetana`: **346,076 flat per-event files** in a 1.4GB tree; chetana launchd jobs exit 124 (timeout) — output that degrades its own consumers. |
| **X7** | SUPPORTED | launchd loop fleet degraded: nine `com.dhyana.loop.*` exit 1; budget ledger machinery failing; two contradictory caps in one script ($3 comment vs $25 var); LAUNCH.md: "Do not rely on launchd." |
| **X8** | SUPPORTED | Forge: convergence-forge cron fixed Jun 9 (WS1) and producing nightly syntheses; the arena's latest measurement: **cost_normalized_lift = −0.100**, CI [−0.30, 0.0], n=3 — the swarm currently loses to its best single agent, at very low power. |
| **X9** | SUPPORTED | The Jun-9 consolidator audit (14 rounds, ~200k tokens, 0 code changes) concluded "diagnosis addiction is structural… STOP AUDITING. Execute." — then the system kept auditing. It also recommended cherry-picking already-merged #557 because it read the wrong tree. Strongest single evidence for commentary-not-cause. |
| **X10** | PARTIAL | Prior-claim reconciliation: p1 (#555 merged) ✓, p2 (#557 merged, flag default-OFF) ✓ on main / absent live, p3 (#558 open; live `:1768` still hardcodes) ✓, p4 mechanisms confirmed structurally, p5 not findable by grep that day (resolved by Reader C reconstruction above: two spines), p6 confirmed. |

---

## 5. Where this read DISAGREES with the ground brief (the map of where truth is)

1. **`~/dharma_swarm` is not "the main worktree"** — it is `qwen/spine-adoption`, ahead 3 / behind 8; and the *running* package is a third tree (cashclaw). Any disk-level "main" conclusion from either is stale.
2. **"Both DBs written today" masks an ~11h divergence**: ontology.db's today-writes are daemon-startup identity/gate objects (01:43Z); runtime.db's dispatch-truth tables last wrote Jun 9 14:38Z.
3. **BR-007 register entry is asserted-not-real**: register says store_sync cron enabled; live `jobs.json` says `enabled:false` — a claimed-CLOSED item whose mechanism was silently disabled. 29/32 live cron jobs disabled since Jun 7 (credit exhaustion): the metabolic layer is mostly arrested.
4. **"Fitness flat" → "fitness vacuously inflated"** — stronger support for the thesis than flatness (see §1).
5. **"Recognition seed dormant" → "fresh, injected, and permanently false"** — the causal break is miscalibration + provider-gating to agents that can't act, not dormancy.
6. **Pulse-count provenance**: "2,369 entries" matches no on-disk file (pulse.log has 18,870 text lines / 2,272 anchors; pulse_log.jsonl has 4) — the figure comes from a dgc-internal store. Status surfaces and disk diverge even on telemetry.
7. **The dominant sprawl is not worktrees** (81, shrinking) but **42,513 staged files in the primary index** — produced by autonomous loops whose output nothing consumes.
8. **The lane map is 4 days old, not a month** — and already stale on every measured axis. Staleness-rate, not staleness, is the finding.

---

## 6. Leverage ranking — 3-lens convergence

Three independent ranking lenses (engineering-leverage, operator-reality, recognition-causality) each ranked the seams. **All three put the same seam first** — a unanimity that did not occur for any other rank.

### Rank 1 — Deploy-truth: make the daemon provably run known-current code (cost: S)
- **The seam**: pin/repoint the python3.11 editable install; add `running_package_provenance()` to `manifest_health.py` (resolve `importlib.util.find_spec('dharma_swarm').origin`, git HEAD of resolved dir, ahead/behind vs origin/main; FAIL on drift) and surface it in `dgc status` (`dgc_cli.py:265`). ~60 lines + test, no hot-path files.
- **Why first**: it closes few findings directly but is the precondition for *all* of them — every merged fix (#555/#556/#557, #558 when merged) is inert until the running interpreter resolves it. Two adversarial audit passes misidentified which tree runs; without an instrumented currency check every future seam-PR risks the same fate. Highest leverage-per-line available.
- **Ops companion (not a PR)**: `pip3.11 install -e <canonical worktree>` for the /opt/homebrew python, fast-forward the canonical tree, restart `com.dharma.swarm`.

### Rank 2 — F1 store-sync: wake one of the three already-built bridges (cost: S–M)
Enable the `store_sync` cron (or the daemon room-health path) and/or give `persist_receipt` its first production caller. All code exists; 0 rows have ever flowed. First receipt with `receipt_json` populated = recognition becoming causal at the data layer.

### Rank 3 — F2 seed truth: fix the dead-calendar research line (cost: XS)
`meta_daemon.py:273-287` — replace hardcoded COLM dates with ACTIVE_TRACK-derived objectives. The seed is already injected at position 1; making it true is the cheapest recognition-causality win in the estate.

### Rank 4 — F5/#558: land the gate PEP where it runs (cost: M, operator-gated)
Merge #558 (REVIEW-decision self-mod enforcement) *after* Rank 1, so it actually reaches the daemon; approve SELF_MOD_SEMANTIC in the gate registry (it is proposed, not approved, hence inert).

### Rank 5 — F4 lineage: pass parent_id through the dgm_loop→auto_evolve seam (cost: XS)
`dgm_loop.py:387-393` — one parameter. Without it, lineage is structurally impossible regardless of shadow state.

### Deliberately NOT ranked high
- Worktree consolidation / index cleanup (F7): symptom, not seam — the producers (loops with no consumers) are the cause; X6/X7 hygiene fixes are operational, not architectural.
- New gates, new audits, new synthesis docs: X9 is the standing instruction. The next artifact after this one should be a PR diff.

---

## 7. Confidence caveats

- Reader C's F4/F5/Q3 are evidence-reconstructed post-crash; not gathered before its crash: `dogma_gate.py`/`steelman_gate.py` internals, the gauntlet dict-bug sub-claim, a fresh local run of `spine_adoption_metric.py`.
- Live `.env` was permission-denied twice; "daemon env defaults govern" is consistent with `ps eww` output but not double-confirmed.
- Forge lift n=3 — candidate evidence only, per the result file's own warning.
- This synthesis was written by a successor session after the original conductor thread was terminated by an automated content-policy false positive (twice: once inside Reader C, once on the main thread — both triggered by adversarial-security phrasing in prompts, not by any actual content issue). All data was recovered from the persisted workflow journal and transcripts; nothing was reconstructed from memory.
