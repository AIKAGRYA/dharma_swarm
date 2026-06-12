# FEEDBACK — Spine-Adoption Lane Continuation (2026-06-11, overnight)

**Lane:** `~/dharma_swarm`, branch `qwen/spine-adoption` (verified: `git branch --show-current` → `qwen/spine-adoption`, HEAD `717a53340`)
**Continuing:** the Claude Code session that died at 100% context mid-round-5 fold.
**Author:** lane-continuation agent (one of four parallel; see SILO MAP for the others).

---

## 1. RECONSTRUCTED STATE — claims vs verified ground truth

**What the dying transcript claimed:** round-5 divergence returned DRY on blocker/major; the session was folding 2 MINOR findings and died MID-EDIT on `scripts/governance/gate1_witness.sh`, with a "suspicious diff" that appeared to both keep the old sha line and add a new `SHOW_SHA` fallback version.

**Verified ground truth — the session got further than its transcript suggested:**

- The fold **completed and was committed** before death: commit `717a53340` "spine: fold round-5 minors — guarded show_new sha + surface-split note in narrative" (2026-06-11 00:52:17 +0900), touching `gate1_witness.sh` (+2/−1), `SPINE_ADOPTION_NARRATIVE.md` (+7), and two docops files.
- The "suspicious duplicate diff" was a **misread of a normal unified diff**: the kept-old-line was the `-` (removed) side, the SHOW_SHA lines were the `+` side. The working-tree file contains ONLY the single fallback-guarded version (lines 32–34), no duplication. Evidence: full read of the file; `git diff --stat -- scripts/governance/gate1_witness.sh` → empty; `bash -n scripts/governance/gate1_witness.sh` → exit 0 (`BASH_SYNTAX_OK`).
- **Both round-5 minors are identified and folded** (no hunt needed — the commit message names them): (1) `show_new()`'s sha pipeline guarded with the UNAVAILABLE fallback, mirroring the artifact writer; (2) the orchestrator/A2A surface split stated in the narrative, not only in code docstrings. There is **no uncommitted lane-owned change anywhere** — every dirty file in the tree (313 per `make onboard`) belongs to other sessions (routing/key consolidation, holon work, chetana, capital_lab; see SILO MAP).
- Commit series since merge base `1caf91715`: `f506352b8` → `040355e41` → `60d7736c7` → `da68adb90` → `717a53340`. Net code diff: `orchestrator.py` +37, `spine/persistence.py` +22, `gate1_witness.sh` +111, two new test files (+163), narrative (+109).
- `make onboard` independently confirms the session's "5/8" claim: track `runtime-truth-spine-adoption-2026-06` shows 5/8 criteria green; missing: `agent_runner_calls_spine`, `bypass_allowlist_empty`, `gate1_witnessed` (the operator gate).
- Branch is **ahead of `origin/qwen/spine-adoption` by 18 commits, ahead of `origin/main` by 11 / behind 1**. Nothing was pushed (guardrail respected by the prior session too).

**Open todos inherited (untouched tonight, by instruction):** B5 (recover PGE parts onto fresh branch — optional), Phase 2 (truth-auditor loop — scoped in §6 below), Phase 3 (signal digester — scoped in §6 below). B4 (loop_detector PreToolUse deny) was completed by the prior session.

---

## 2. CONTINUED TONIGHT — work completed, with verifier evidence

1. **Coherence check of the feared half-edit** — `bash -n scripts/governance/gate1_witness.sh` → exit 0; full-file read confirms single, fallback-guarded sha display. **No repair was needed**; the prior session finished the edit and committed it.
2. **Second round-5 minor identified** — from commit `717a53340`'s own message + diff: the surface-split note in `SPINE_ADOPTION_NARRATIVE.md`. Not invented; cited.
3. **Verifiers run (all green):**
   - Un-staled NATS test suite: `.venv/bin/python -m pytest tests/test_spine_adoption_metric.py -q` → **13 passed in 3.45s** (includes `test_nats_is_scoped_out`, the test `da68adb90` un-staled).
   - Targeted sweep: `.venv/bin/python -m pytest tests/ -k "spine or witness or nats" -q --ignore=tests/test_a2a_readiness_gate.py --ignore=tests/test_autonomous_agent.py` → **231 passed, 3 skipped, 11003 deselected in 9.62s**. The two ignores are collection-time ImportErrors from OTHER lanes' uncommitted working-tree state, not spine code: `test_a2a_readiness_gate.py` (untracked file) imports a module `dharma_swarm.operator_core.a2a_task_lifecycle` that doesn't exist on this branch; `test_autonomous_agent.py` (modified by the routing session) imports `_resolve_agent_model_override` which doesn't exist in `autonomous_agent.py` here. Recorded honestly; not spine regressions.
   - Named dispatch + invariant tests: `pytest tests/test_orchestrator_spine_dispatch.py tests/test_spine_adoption_dispatch.py tests/test_spine_persistence_invariant.py -q` → **22 passed in 2.38s**.
   - `python scripts/governance/spine_bypass_report.py` → exit 0, "All .submit() sites classified. 5 intentional bypass(es) remain on the migration allowlist."
   - `python scripts/uplift_guards/check_spine_ownership.py` → exit 0, "spine ownership clear (importable + all sqlite users declared)".
4. **No commit made** — the conditional in the task ("if verifiers pass, commit the minor fixes") was moot: the minors were already committed as `717a53340`. Committing anything else from this working tree would have swept in other lanes' uncommitted files. Nothing pushed.
5. **Round-6 confirmation run** — see verdict below.

### ROUND 6 VERDICT: **DRY** (zero blocker/major). Two consecutive quiet rounds → convergence termination rule satisfied.

Fresh-eyes review of the full series diff (`git diff 1caf91715..HEAD`, 12 files, +517/−22), hunting specifically for regressions INTRODUCED by the round-4/round-5 fixes:

- **Freshness guard (`gate1_witness.sh`, round-4 fix):** logic traced sound — stale baseline (current > baseline) resets and warns; `watch_started` recorded; baseline advances on success so re-runs can't re-trigger; `count()` ERR path exits before any baseline write, so the baseline file can't be poisoned with "ERR".
- **Orchestrator persist block (round-3/4 fix):** `record_delegation_run(..., status="claimed")` at orchestrator.py:2039 precedes the persist at ~:2244–2267, so the row exists before the `UPDATE`; fail-open wrapper can never break dispatch; 2s bounded `busy_timeout` is intentional and documented (vs 5s default stall, empirically reproduced per commit `60d7736c7`).
- **0-row guard (`persistence.py`):** `rowcount == 0` raises into the caller's fail-open warning — correct loudness without dispatch breakage.
- **Un-staled NATS test:** assertion widened to `("joined", "missing", "quarantine")` — correct per the 2026-05-31 doctrine amendment; not a weakening (the spine-adoption non-goal text stands).
- **Narrative claims cross-checked against live verifiers:** 5/8 matches onboard; "5 intentional bypasses" matches `spine_bypass_report.py` output exactly.

**Residual minors observed (recorded, NOT fixed — below the blocker/major bar, and round 6 is a confirmation round, not a fold round):**

- M-a: the `SHOW_SHA`/`LATEST_SHA` UNAVAILABLE fallback fires only when the pipeline output is empty. If `sqlite3` fails mid-flight but `shasum` is present, the displayed value is the sha-of-empty-string (`e3b0c44298fc1c14` — a recognizable constant), not "UNAVAILABLE". Narrow race (count() succeeded against the same DB seconds earlier) and fail-safe in direction; fix would be checking sqlite3's exit status separately.
- M-b: a baseline *above* the current count (DB rotated/reset) is not handled — the watch would silently never fire. Fail-safe (no false witness possible) and pre-existing before round 4; not introduced by the fixes.

---

## 3. OPERATOR-GATED — only John can take these, ranked

1. **GATE 1 live run** (highest value, ~5 min): `dgc down` → `export DHARMA_SPINE_DISPATCH=1 && dgc up --background` → `bash scripts/governance/gate1_witness.sh --watch`. This flips `gate1_witnessed` (criterion 8) and is the track's non-proxy completion gate. The kit is freshness-guarded and round-5/6-audited; it is ready.
2. **M1 reconciliation decision — DUPLICATE PERSISTENCE WIRES (new finding tonight, see SILO MAP):** the receipts-vault lane (`~/ds_stitch_receipts`, commit `e59b70398`, PRs #560–562) independently built receipt persistence into the SAME function (`Orchestrator._run_task_via_spine`) and the SAME module (`spine/persistence.py`) with a **conflicting design**: theirs has `persist_receipt` return rows-updated + a never-raises `persist_receipt_to_store()` wrapper; this lane's `persist_receipt` raises on 0 rows + inline fail-open in the orchestrator with a 2s lock budget. These will conflict at merge in `orchestrator.py`, `spine/persistence.py`, and `tests/test_orchestrator_spine_dispatch.py`. **Decision needed: which error-semantics wins** (recommendation: this lane's loud 0-row raise + bounded lock budget is the stronger invariant; the vault lane's `persist_receipt_to_store()` wrapper is a nice caller convenience that can be layered on top). One lane must rebase onto the other before either merges.
3. **Push / PR the lane branch** (18 unpushed commits on `qwen/spine-adoption`) — after deciding #2, since pushing both as-is creates a guaranteed conflict pair.
4. **Working-tree triage**: 313 dirty files in `~/dharma_swarm` from at least three other workstreams (routing/key consolidation, holon, chetana/capital_lab). Two of them currently break pytest collection (`test_a2a_readiness_gate.py`, `test_autonomous_agent.py`). Decide: commit to their own branches, stash, or discard.
5. **B5 (optional inherited todo):** recover PGE parts onto a fresh branch — operator call on whether it's still wanted.

---

## 4. SILO MAP — where this lane was context-blind

**What this lane did NOT know and needed to:**

- **Receipts-vault lane (`~/ds_stitch_receipts`, `feat/persist-evidence-receipts`, PRs #560–562) built the same wire.** Its HEAD `e59b70398` "first production callers for persist_receipt" targets `Orchestrator._run_task_via_spine` + `spine/persistence.py` — exactly the surfaces this lane's `f506352b8`/`040355e41` modified, with incompatible error semantics (their commit even asserts "persist_receipt had zero callers before this change", which was already false on this branch). Neither session's transcript shows awareness of the other. This is the single most expensive blindness: ~2 sessions of duplicated work plus a guaranteed merge conflict.
- **Living-Thread / seat lane (`~/dharma_swarm_live`, `organ/03-seat`) touches the same DB-contention seam.** Its commit `2e613fc54` "busy_timeout on runtime.db connections — settle-vs-cron lock race" addresses the same `~/.dharma/state/runtime.db` WAL lock contention this lane bounded with `timeout=2.0` / `PRAGMA busy_timeout=2000`. Its `SeatedCheckpoint` (`2c88e6cd3`) gates live evolution on the dispatch path. If both merge, busy-timeout policy should be unified in one place, not sprinkled per-callsite.
- **AGNI writing-empire lane:** no overlap detected with spine surfaces; lowest cross-lane risk.
- **Shared working tree as silent channel:** other sessions' uncommitted edits in this checkout broke this lane's test collection (two ImportErrors above). The stalled session's "35/35 green" claims were implicitly conditioned on which dirty files were present at run time — a reproducibility hole.

**What shared state/doc would have prevented this:** the repo already has the skeleton — `reports/governance/parallel_lane_map.{md,json}` + `scripts/governance/render_parallel_lane_map.py` exist (untracked). What's missing is **surface-level claim enforcement**: each active lane declares `(branch, files-it-will-touch)` in the lane map, and `make onboard` warns when your declared surfaces intersect another lane's. A 5-line check in `agent_onboard.py` against `parallel_lane_map.json` would have flagged "ds_stitch_receipts also claims orchestrator.py + spine/persistence.py" before either lane wrote a line. Same mechanism as ACTIVE_TRACK `owned_surfaces`, applied per-lane instead of per-track.

---

## 5. STANDING LOOP PROPOSAL — long-horizon loops to keep this lane healthy

1. **`spine-truth-auditor`** (Phase 2 made into a loop — see scope in §6)
   - Trigger: launchd, every 6h (or `/schedule` post-merge-to-main event).
   - Verifier command: `python scripts/governance/check_track_status.py && python scripts/governance/spine_bypass_report.py && python scripts/uplift_guards/check_spine_ownership.py` — exit-code AND, plus diff of the rendered claims vs the previous run.
   - Budget: free (no LLM) for the verifier pass; ≤$0.10/run Haiku-tier only when a drift is detected, to write the human-readable delta note.
2. **`lane-collision-sentinel`**
   - Trigger: launchd, every 12h, scans all registered lane worktrees (`git -C <wt> diff --name-only <base>...HEAD`) and intersects file sets across lanes.
   - Verifier command: `python scripts/governance/render_parallel_lane_map.py --check-collisions` (extend the existing untracked script with an intersection check; output non-zero on overlap).
   - Budget: free. Tonight's PRs-#560-562-vs-this-lane collision is the existence proof of value.
3. **`gate1-readiness-watch`**
   - Trigger: launchd, daily at 04:25 (before the 04:30 wake briefing).
   - Verifier command: `bash -n scripts/governance/gate1_witness.sh && sqlite3 ~/.dharma/state/runtime.db "SELECT COUNT(*) FROM delegation_runs WHERE receipt_json IS NOT NULL"` — confirms the kit still parses and reports the witness count into the morning briefing, so the operator sees GATE-1 state daily without asking.
   - Budget: free. Retire the loop once GATE 1 is witnessed and the track ships.

---

## 6. SCOPED (NOT BUILT) — Phase 2 & Phase 3 half-page designs

### Phase 2 — Standing truth-auditor loop (claims vs ground truth)

**Problem:** narrative docs and commit messages assert state ("5/8", "35/35 green", "5 bypasses") that decays silently as the repo moves. Tonight's session validated such claims by hand; a loop should do it.

**Grounded in what exists:** `scripts/governance/check_track_status.py` already evaluates ACTIVE_TRACK criteria mechanically; `spine_bypass_report.py` already classifies every `.submit()` site against `_INTENTIONAL_BYPASS`; `check_spine_ownership.py` already verifies sqlite-user declarations; `gate1_witness.sh` already demonstrates the pattern of "claim must carry a DB-checkable hash".

**Design:** a thin runner (`scripts/governance/truth_audit.py`, ~100 lines, no new store) that (a) executes the three verifiers above, (b) extracts the machine-checkable claims from `SPINE_ADOPTION_NARRATIVE.md` (criterion count, bypass count, test-suite names) via the same regex style `check_track_status.py` uses, (c) diffs each claim against verifier output, (d) appends one JSONL line per run to `reports/governance/truth_audit.jsonl` and writes a delta note only when claim ≠ ground truth. No LLM in the loop; the doc's claims become structured assertions the way ACTIVE_TRACK criteria already are. Output feeds the morning briefing. Explicit non-goal: do not let it auto-edit the narrative (read-model, not authority — the reconciliation track's doctrine line applies).

### Phase 3 — Signal digester + garbage collection for fleet output

**Problem:** the fleet floods `reports/agentops/work_packets/` (200+ untracked forge-cycle JSONs visible tonight), `~/.dharma/stigmergy/marks.jsonl`, and witness logs. High-signal items (a failed verifier, a new bypass site) drown in cycle-status noise; nothing expires.

**Grounded in what exists:** stigmergy marks are append-only JSONL with established schema (`dharma_swarm/stigmergy.py`); work packets are uniform JSON; chetana already has a decay/revival philosophy and a staging area (`~/.dharma/knowledge/staging/`); `signal_bus.py` exists for loop-to-loop signaling.

**Design:** two small pieces, no daemon. **(1) Digester** (`scripts/governance/signal_digest.py`): reads the last N hours of work packets + stigmergy marks, buckets by `(source, kind)`, applies static severity rules first (verifier-failed / new-bypass / receipt-gap → surface; cycle-heartbeat → count only), emits one digest markdown per day to `reports/agentops/digests/<date>.md`; an optional Haiku pass summarizes only the surfaced bucket (≤$0.10/day). **(2) GC**: a manifest-driven sweep that moves work packets older than 14 days whose `status` is terminal into `reports/agentops/_archive/<month>/` (move, never delete — consistent with the no-delete guardrail and chetana's stale-is-a-trigger-not-exile stance). Wire the digest into the 04:30 morning briefing. Explicit non-goal: not a new truth store; the digest is a projection of existing JSONLs.

---

*Evidence trail: every claim above cites the command and output produced tonight in-session. Nothing was pushed; no PRs touched; no files deleted; one file written (this memo).*
