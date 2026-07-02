# BROKEN REGISTER — Slot 7 of MEGAFILE_INDEX
**Path:** `dharma_swarm/docs/state/BROKEN_REGISTER.md`
**Status:** SEEDED
**Mode:** Append-only persistent log of broken / stale / degraded surfaces. Survives across sessions. Replaces the per-session re-discovery cycle.

**How to use:** when you find something broken, append a row. When you fix something, do NOT delete the row — move it to the **CLOSED** section with closing evidence and date. New items get the next available `BR-NNN` id.

**Schema:**
| field | meaning |
|---|---|
| id | `BR-NNN` |
| first_observed | YYYY-MM-DD when the breakage was first witnessed |
| last_verified | YYYY-MM-DD when the breakage was last confirmed still present |
| age_days | last_verified − first_observed |
| severity | BLOCKER / DEGRADED / STALE / NOISE |
| domain | runtime / docs / cron / state / agent / outward |
| root_cause | one-sentence diagnosis with file:line |
| blast_radius | which downstream surfaces are affected |
| evidence | file:line citation(s) |
| status | OPEN / INVESTIGATING / WORKAROUND / FIXED |

---

## OPEN ITEMS (BR-007 reopened 2026-07-01; other open/partial items retained)

> **Convergence pass executed 2026-05-07 18:00–18:10:** Plan at `~/.claude/plans/yes-write-a-plan-wobbly-cerf.md`. Closed items moved to CLOSED section: BR-001 (cron daemon plist fixed), BR-016 (SOVEREIGN_MANIFEST counts refreshed and now DocOps-verified), BR-017 (BUILD_SESSION_ENTRYPOINT.md present), BR-018 (MEGAFILE_INDEX referenced from CLAUDE.md + README), BR-019 (Coherence Delta CI validator installed). BR-015 was already CLOSED. Total CLOSED = 6; OPEN = 13.

*(BR-001, BR-002, BR-006, and BR-008 moved to CLOSED ITEMS — see below. BR-007's historical closure entry is retained in CLOSED ITEMS but is superseded by the reopened entry here.)*

### BR-007 — REOPENED 2026-07-01 — runtime.db and ontology.db sync still broken
- **first_observed:** 2026-05-10 closure later disproven; independently re-confirmed 2026-06-10 and 2026-07-01.
- **last_verified:** 2026-07-01
- **age_days:** 52 since original closure claim; 21 since the 2026-06-10 re-confirmation.
- **severity:** BLOCKER
- **domain:** runtime / state
- **root_cause:** The closure evidence assumed one canonical ontology/runtime path and an enabled sync path. The 2026-07-01 audit found the live `store_sync` cron disabled in `~/.dharma/cron/jobs.json`, no sync-derived rows in the live runtime DB, and two diverged `ontology.db` copies with materially different object populations.
- **blast_radius:** Ontology/runtime self-recognition remains split; status surfaces can claim closure from code presence while live state never converges.
- **evidence:** `docs/governance/AUDIT_2026-07-01.md`; `dharma_swarm/cron_runner.py` still exposes `store_sync`, but live scheduler state has `store_sync.enabled=false`; ontology path resolution remains split between repo-local `dharma_swarm/ontology.db` and `~/.dharma/ontology.db`.
- **status:** OPEN — documentation corrected. Do not re-enable `store_sync` or consolidate database files until the operator chooses the canonical `ontology.db` copy and a backup/merge plan exists.

### BR-003 — Apply gate present but closed (self-evolution loop)
- **first_observed:** 2026-05-07
- **last_verified:** 2026-05-07
- **age_days:** 0
- **severity:** BLOCKER
- **domain:** runtime
- **root_cause:** Two parallel apply paths share zero import edge. Build Protocol (`tools/build_protocol/`) self-declared shape-only; DarwinEngine `apply_diff_and_test` at `evolution.py:2156` env-locked closed by `DHARMA_EVOLUTION_SHADOW=1` default. `grep "from dharma_swarm.tools.build_protocol"` returns 0 hits inside `dharma_swarm/dharma_swarm/`.
- **blast_radius:** Self-evolution trace reported 96 dryruns; direct disk check on 2026-05-07 found 9 current dryrun dirs, 4 `proof_packet.json` files, and 0 `applied` markers. Sediment-to-crystallization mechanism remains absent. Kernel + telos_gates static for 6+ weeks.
- **evidence:** `~/.dharma/audit/self_evolution_trace_2026-05-07.md`; `find ~/.dharma/build_protocol/dryruns -mindepth 1 -maxdepth 1 -type d | wc -l` = 9; `find ~/.dharma/build_protocol -name proof_packet.json | wc -l` = 4; vision_maps `05_autopoiesis_evolution.md`.
- **status:** PARTIAL — 2026-05-07 partial closure: `tools/build_protocol/cli.py` now exposes `dharma-build shadow-apply <dryrun_root>`, which calls `DarwinEngine.apply_sealed_packet(..., shadow=True)` and archives the proof result without live mutation. Live apply remains intentionally gated. **End-to-end exercise on 2026-05-07 (this commit):** ran `python -m tools.build_protocol.cli shadow-apply ~/.dharma/build_protocol/dryruns/wp005-seal-cli-20260506`. Result: `accepted: true`, `archive_entry_id: 64280c7685784e63`, `shadow: true`, `proof_exit_code: 0` (5 tests pass), packet archived as line in `~/.dharma/evolution/archive.jsonl` with id `64280c7685784e63` and `shadow:true`. First confirmed end-to-end shadow-apply on this branch. `applied:false` is correct — `diff_missing:true` for this dryrun (test-only seal, no diff to apply); the seam itself is now exercised. Full closure (live, non-shadow apply) remains a multi-day plan gated by `DHARMA_EVOLUTION_SHADOW=0` and a real telos-gate→kernel→apply traversal.

### BR-004 — Cron split-brain (repo vs live)
- **first_observed:** ≤ 2026-05-06
- **last_verified:** 2026-05-07
- **age_days:** 1+
- **severity:** DEGRADED
- **domain:** cron / docs
- **root_cause:** Repo `dharma_swarm/cron_jobs.json` and live `~/.dharma/cron/jobs.json` still use different schemas and job populations. The original sub-claim "No doc declares which is canonical" is now stale.
- **blast_radius:** Job-level health can still diverge between repo intent and launchd reality, but the scheduler state authority is no longer ambiguous.
- **evidence:** `docs/governance/METABOLIC_CLOCK.md` declares `~/.dharma/cron/jobs.json` as scheduler state authority and says to fix failed jobs as separate scoped work packets. `scripts/cron_unify.py` remains the non-mutating unification helper.
- **status:** PARTIAL — canonical authority declared; actual repo/live job reconciliation remains a scoped follow-up.

### BR-005 — Algedonic stream in degenerate steady-state
- **first_observed:** ~2026-05-02 (5 days prior to audit)
- **last_verified:** 2026-05-07 20:30 (post-BR-001-fix verification)
- **age_days:** ~5
- **severity:** DEGRADED
- **domain:** runtime
- **root_cause:** The original "last-200 rows are only omega_divergence" finding is now stale. The live stream contains chronic `omega_divergence` plus many `task_retries_exhausted` dead-letter warning signals. The remaining gap is consumer/action coherence: some actions emitted by `algedonic_activation.py` are unsupported or only partially consumed by `Organism`/VSM paths.
- **blast_radius:** Sensing is richer than actuation. Signals exist, but not every signal class has an explicit consumer policy: log-only, prompt-context, scheduling bias, review, hold, or dispatch stop.
- **evidence:** 2026-05-11 live tail of `~/.dharma/algedonic_signals.jsonl`; `dharma_swarm/algedonic_activation.py` defines `rebalance_priorities`, `enforce_glossary`, and `recalibrate_from_metrics`; `dharma_swarm/organism.py` concretely handles only a subset of algedonic actions.
- **status:** PARTIAL — degenerate steady-state claim corrected; causal consumption/action coverage remains open.

### BR-009 — Roadmap is contested (3 docs claim primacy)
- **first_observed:** 2026-05-07
- **last_verified:** 2026-05-20
- **age_days:** 13
- **severity:** DEGRADED
- **domain:** docs
- **root_cause:** `LOOMWORK_v0_MASTER.md` self-declares OPERATIONAL; `2026-05-07-loomwork-design.md` self-declares "draft, awaiting review" but `MEMORY.md:37` says it supersedes the master; `ARJUNA_DIRECTIVE_v1.md` still owns Q2/Q3 sequence.
- **blast_radius:** 47% of in-flight branches have no plan-doc anchor. Strategy ~10x ahead of code. Onboarding agents flip a coin.
- **evidence:** `~/.dharma/audit/ten_megafiles_q4_2026-05-07.md`; `MEMORY.md:37`.
- **status:** **FIXED 2026-05-20** — `LOOMWORK_v0_MASTER.md` archived to `docs/loomwork/_archive/`; `ARJUNA_DIRECTIVE_v1.md` no longer exists on disk. The `ACTIVE_TRACK.yaml` mechanism is now the canonical roadmap authority (machine-verifiable, single source). No doc contention remains.

### BR-010 — `NAVIGATION.md` exists at non-canonical path; file itself stale
- **first_observed:** ≤ 2026-05-07
- **last_verified:** 2026-05-20
- **age_days:** generated 2026-03-29 → 52 days stale
- **severity:** STALE
- **domain:** docs
- **root_cause:** **REVISED 3x:** `NAVIGATION.md` DOES exist at `dharma_swarm/docs/architecture/NAVIGATION.md` BUT the file itself was generated 2026-03-29 with old counts and has not been refreshed against current DocOps-measured reality. `CLAUDE.md` now points to both `docs/architecture/NAVIGATION.md` and `make xray`; remaining disagreement is stale static map vs generated live map.
- **blast_radius:** Slot 4 (Limbs Atlas) — substrate exists but stale. Module count drift across older sources remains unresolved; current measured counts live in `docs/governance/SOVEREIGN_MANIFEST.md` and `docs/docops/AUTO_INVENTORY.md`.
- **evidence:** `find . -maxdepth 4 -name NAVIGATION.md` returns `./docs/architecture/NAVIGATION.md`; codex validation pass at `~/.dharma/audit/ten_megafiles_survey_2026-05-07.md` cites `docs/architecture/NAVIGATION.md:1-7, :88-119` confirming 2026-03-29 generation date and old counts.
- **status:** **FIXED 2026-05-20** — Added staleness warning header to `docs/architecture/NAVIGATION.md` noting old counts (500 modules) vs current reality (610+). Directs readers to `make xray` and `SOVEREIGN_MANIFEST.md` for live numbers. Module structure remains directionally correct. Full regeneration deferred as low-ROI.

### BR-011 — `INTERFACE_MISMATCH_MAP.md` self-declared stale
- **first_observed:** ≤ 2026-04-25
- **last_verified:** 2026-05-20
- **age_days:** ~25
- **severity:** STALE
- **domain:** docs
- **root_cause:** Header self-declares "memorial, not battle plan." `CLAUDE.md` calls it "#1 source of runtime failures" but the doc admits ~12/25 entries resolved + ~7 unverified. Mismatch between authority claim and content state.
- **blast_radius:** Slot 5 (Wiring + Loop Ledger) cannot be canonical until refreshed.
- **evidence:** `~/.dharma/audit/ten_megafiles_q2_2026-05-07.md`.
- **status:** **FIXED 2026-05-20** — Updated header: audit date refreshed to 2026-05-20, added explicit status line ("All BLOCKERs resolved. 3 items remain: NEW-05 GUARDED, NEW-07/08 PARTIAL+ — actively monitored, not stale"). Doc is no longer self-contradictory; authority claim in `CLAUDE.md` is accurate for the remaining items.

### BR-012 — `CYBERNETIC_LOOP_MAP.md` stale (6 days)
- **first_observed:** 2026-05-01
- **last_verified:** 2026-05-20
- **age_days:** 19
- **severity:** STALE
- **domain:** docs
- **root_cause:** `CYBERNETIC_LOOP_MAP.md:196-208` claims recognition seed was never generated. Current code has it (`meta_daemon.py:1-13` + `context.py:1202-1217`). Doc lies; nothing flags the lie.
- **blast_radius:** Agents reading the doc believe loops are closed when runtime says they aren't.
- **evidence:** `~/.dharma/audit/ten_megafiles_q2_2026-05-07.md`; vision_maps `04_recognition_self_model.md`.
- **status:** **FIXED 2026-05-20** — Corrected Loop 8 status from "NO" to "PARTIAL" with evidence: `cascade.py:386-491` feeds results back into recognition seed, `shakti_executive/inputs.py:100` reads it, `meta_daemon.py` integrates it. Updated prose section to reflect wired state. Audit date refreshed to 2026-05-20.

### BR-013 — Agent contract fragmented across 8+ surfaces
- **first_observed:** 2026-05-07
- **last_verified:** 2026-05-07
- **age_days:** 0
- **severity:** DEGRADED
- **domain:** agent / docs
- **root_cause:** 25 `~/.claude/projects/-Users-dhyana/memory/feedback_*.md` files (~792 lines) un-consolidated; some carry 36-day-stale system-reminders. `~/.claude/CLAUDE.md` is a 4-line ruflo stub; canonical is `/Users/dhyana/CLAUDE.md` (308 lines) — naming suggests reverse. `foundations/GLOSSARY.md` exists but is **not referenced** from `CLAUDE.md`, `MEMORY.md`, or `cabinet/INDEX.md`.
- **blast_radius:** Non-Claude-Code agents (Codex sub-agents, headless invocations, MCP workers) may have NO path to the substrate. Onboarding requires prior knowledge of where the canonical contract lives.
- **evidence:** `~/.dharma/audit/ten_megafiles_q6_2026-05-07.md`.
- **status:** PARTIAL — 2026-05-07 19:29 (Phase 3D micro-fix): `~/.claude/CLAUDE.md` replaced with a pointer-stub directing agents to `/Users/dhyana/CLAUDE.md`. Backup at `~/.dharma/audit/_backup_~.claude.CLAUDE.md.2026-05-07`. Remaining work: consolidate the 25 `feedback_*.md` files into Slot 9 of MEGAFILE_INDEX (`docs/agent/AGENT_CONTRACT_AND_TEAM.md`); add a discoverability path from `CLAUDE.md` / `MEMORY.md` / `cabinet/INDEX.md` to `foundations/GLOSSARY.md`. Non-CC agents that cannot follow the pointer-stub still hit the gap; that residual issue is the active part of BR-013.

### BR-014 — `BHED_GNAN` always passes
- **first_observed:** 2026-05-07
- **last_verified:** 2026-05-07
- **age_days:** 0
- **severity:** DEGRADED
- **domain:** runtime
- **root_cause:** `dharma_swarm/telos_gates.py:512-513` literal hard-pass. The Gnani check defined to be most central is structurally inert.
- **blast_radius:** Recognition layer's hardest gate is a no-op. Witness emits but doesn't gate.
- **evidence:** vision_maps `01_gnani_prakruti.md`; `telos_gates.py:512-513`.
- **status:** OPEN — direct edits to `telos_gates.py` are governance-forbidden by `CLAUDE.md`; closure must go through `GateRegistry.propose()` / gate pressure policy rather than a hard-coded gate mutation.

### BR-015 — `.FOCUS` writer with stale claim "no reader"
- **first_observed:** 2026-05-07
- **last_verified:** 2026-05-07
- **age_days:** 0
- **severity:** NOISE (stale-claim correction)
- **domain:** docs
- **root_cause:** Synthesis master + 4-recognition-map claimed `.FOCUS` was write-only (`identity._issue_correction` writes; no reader located). **CLOSED 2026-05-07 18:00:** `.FOCUS` IS read in 4 locations in `dharma_swarm/swarm.py:1514, 1533-1534, 2114, 2122, 2125`. Confirmed via direct grep.
- **blast_radius:** Synthesis master at `MASTER_2026-05-07_attractor_closure_synthesis.md` carries the stale claim and needs patching.
- **evidence:** `dharma_swarm/swarm.py:1514` ("Check .PAUSE, .FOCUS, .INJECT, EMERGENCY_HOLD files."); `:1533-1534` (read), `:2114, :2122, :2125` (Wire 3 routing governance use). Agent C convergence audit `~/.dharma/audit/truth_spine_convergence_2026-05-07.md`.
- **status:** **CLOSED** — moved to CLOSED section below.

---

### BR-016 — `SOVEREIGN_MANIFEST.md` count drift
- **first_observed:** 2026-05-07
- **last_verified:** 2026-05-07
- **age_days:** 0
- **severity:** STALE
- **domain:** docs
- **root_cause:** `docs/governance/SOVEREIGN_MANIFEST.md` carried stale Python-file counts. Earlier convergence saw 514 vs 567; after subsequent build-spine merges the current DocOps-measured count is **550**.
- **blast_radius:** SOVEREIGN_MANIFEST is named as authority surface in CANONICAL_DOC_STACK; agents reading it for governance scope get a stale picture. Affects Slot 2 (Operational Doctrine) and Slot 4 (Limbs Atlas) consolidation.
- **evidence:** `python scripts/docops/check_docops_integrity.py --changed-from origin/main` reports `dharma_python_modules=550`, `dharma_top_level_python_modules=385`, and passes against `docs/governance/SOVEREIGN_MANIFEST.md`.
- **status:** **FIXED 2026-05-07 18:08; refreshed again during PR #167 merge resolution** — count-sensitive claims are now checked by DocOps rather than frozen to one audit snapshot.

### BR-018 — `MEGAFILE_INDEX.md` was not referenced from `CLAUDE.md` or `README.md` (discoverability gap)
- **first_observed:** 2026-05-07
- **last_verified:** 2026-05-07 18:00
- **age_days:** 0 (born today)
- **severity:** DEGRADED
- **domain:** docs / discoverability
- **root_cause:** `dharma_swarm/docs/MEGAFILE_INDEX.md` is the locked stable shape for onboarding (10 reserved slot paths) but was not referenced from `dharma_swarm/CLAUDE.md` or `dharma_swarm/README.md` when seeded. `CLAUDE.md` now references it directly.
- **blast_radius:** All 10 slots' onboarding chain breaks at the first hop. The index exists; it is invisible.
- **evidence:** Codex validation pass `~/.dharma/audit/ten_megafiles_survey_2026-05-07.md:21` confirmed the original missing reference; `CLAUDE.md` Navigation now points to `docs/MEGAFILE_INDEX.md`.
- **status:** **FIXED 2026-05-07** — `CLAUDE.md` Navigation now points to `docs/MEGAFILE_INDEX.md`.

### BR-017 — `BUILD_SESSION_ENTRYPOINT.md` exists on origin/main, missing from current checkout
- **first_observed:** 2026-05-07
- **last_verified:** 2026-05-07
- **age_days:** 0
- **severity:** DEGRADED
- **domain:** docs / branch state
- **root_cause:** Agent C's convergence audit identifies `docs/governance/BUILD_SESSION_ENTRYPOINT.md` on **origin/main** as the strongest practical build-session entrypoint — short pointer layer, subordinate to CLAUDE.md and SOVEREIGN_MANIFEST. Verified absent in current branch `feat/brief-to-spec-seam-2026-05-07`.
- **blast_radius:** Slot 9 (Agent Contract) loses its strongest in-repo onboarding pointer; agents in this branch onboard without it.
- **evidence:** `find /Users/dhyana/dharma_swarm -name "BUILD_SESSION_ENTRYPOINT.md"` returns empty in current checkout; Agent C confirms presence on origin/main.
- **status:** **FIXED 2026-05-07 18:06** — `git checkout origin/main -- docs/governance/BUILD_SESSION_ENTRYPOINT.md` cherry-picked the file (7,837 bytes). File now present in current checkout. Convergence pass action 4.

---

## STALE-CLAIM CORRECTIONS (record updates that supersede prior findings)

| date | superseded claim | corrected claim | source |
|---|---|---|---|
| 2026-05-07 | `.FOCUS` is write-only with no reader | **VERIFIED:** read in `swarm.py:1514, 1533-1534, 2114, 2122, 2125` | Agent C + direct grep |
| 2026-05-07 | Orchestrator/agent_runner do not record typed proposal/gate paths | Current code DOES record these (partially superseded) | Agent A scratchpad |
| 2026-05-07 | Shakti → Darwin wiring is missing | SUPPORTED in current source: `orchestrate_live.py:76-110, :797-814`; `evolution.py:3477-3503` | codex master + synthesis §10 |
| 2026-05-07 | Recognition seed was never generated | RecognitionEngine present + context injection wired: `meta_daemon.py:1-13`, `context.py:1202-1217` | codex master + synthesis §9.1 |
| 2026-05-07 | `NAVIGATION.md` is missing entirely | **VERIFIED:** exists at `docs/architecture/NAVIGATION.md`. `CLAUDE.md` pointer fixed 2026-05-07; remaining issue is stale static map vs `make xray`. | Agent C + direct find |
| 2026-05-07 | `jagat_kalyan` has zero imports | **NARROWED:** has ~10 in-repo references (jk_stigmergy_seeds, ecosystem_map, cron_portable_context, context_agent, thinkodynamic_director, telos_substrate, gaia_platform, ontology, autonomous_agent, plus tests/skills). Correct narrower claim: **core engine has no proven live consumer**. | Agent C + direct grep |
| 2026-05-07 | BR-001 cron daemon is simply dead | **NARROWED:** launchd reports PID 10579 running since May 1, but current `/opt/homebrew/bin/dgc` rejects `cron`; this is restart-incoherent path/version drift, not verified daemon death. | direct launchctl + CLI probe |

---

## CLOSED ITEMS

### BR-006 (CLOSED 2026-05-11) — Recognition seed stale
- **Closing evidence:** Live `~/.dharma/meta/recognition_seed.md` was refreshed on 2026-05-10 and now reports current recognition context (`R_V=0.998 static`, archive entries, witness logs, DGC agents, recent cascade loops). `dharma_swarm/meta_daemon.py` owns recognition synthesis and `dharma_swarm/context.py` injects the seed into agent context.
- **Verification:** 2026-05-11 live stat showed `May 10 21:25:11 2026` mtime, replacing the stale May 1 observation. Residual work is not freshness but making recognition more directly causal in routing/gates.

### BR-002 (CLOSED 2026-05-10 via PR #187) — central VentureCell loop feedback
- **Closing evidence:** `dharma_swarm/opportunity_refill.py` promotes canonical Shakti `opportunity_id` rows into `frontier_tasks_pending.jsonl` and now marks board rows `queued`, not falsely `addressed`. `dharma_swarm/orchestrate_live.py` drains the frontier queue into `TaskBoard` entries with `opportunity_id` metadata and typed `TaskPriority`. `dharma_swarm/telic_seam.py` feeds completed outcomes back through `update_opportunity_outcome()`, and `feedback_writer.py` marks successful outcomes as `addressed`.
- **Verification:** `tests/test_br_closures.py` covers canonical `opportunity_id`, malformed scores, queued-not-addressed refill behavior, queue drain into `TaskBoard`, and metadata preservation. `tests/test_feedback_writer.py` verifies successful outcomes clear `queued` and set `addressed`, while failed outcomes clear `queued` without marking addressed.

### BR-007 (CLOSED 2026-05-10 via PR #187) — runtime.db and ontology.db sync
- **Closing evidence:** `dharma_swarm/swarm.py:3061` now writes `_record_memory_fact()` to `self.state_dir / "state" / "runtime.db"`, matching the live runtime path. `dharma_swarm/engine/store_sync.py` materializes ontology `Outcome` objects as runtime `artifact_records` with `artifact_id = f"ont-{outcome.id}"`; sync is idempotent through the runtime primary key and explicit existing-row check. `dharma_swarm/cron_runner.py:577-596` exposes the `store_sync` handler, `cron_jobs.json` registers the enabled `store_sync` interval job, and `dharma_swarm/orchestrate_live.py:1732-1738` runs sync from the room-health loop under a guard.
- **Verification:** `tests/test_br_closures.py::TestStoreSync` covers missing ontology DB, materialization, and idempotent rerun.

### BR-008 (CLOSED 2026-05-10 via PR #187) — VentureCell ontology/organ polymorphism
- **Closing evidence:** `dharma_swarm/fractal/room_bridge.py:375-459` maps `VentureCellV1` rooms to deterministic ontology object IDs using the room ID, updates existing objects through `put_object()`, hydrates ontology objects back to `VentureCellV1`, and preserves original room lifecycle status in `room_status`. `dharma_swarm/orchestrate_live.py:1722-1730` syncs the room registry to ontology and persists the shared registry back to `ontology.db`.
- **Verification:** `tests/test_br_closures.py::TestVentureCellPolymorphism` covers room→ontology, ontology→room, roundtrip, registry batch sync, existing-cell update without duplicates, and all `RoomStatus` values.

### BR-015 (CLOSED 2026-05-07 18:00) — `.FOCUS` reader
- **Closing evidence:** `dharma_swarm/swarm.py:1514` ("Check .PAUSE, .FOCUS, .INJECT, EMERGENCY_HOLD files."); `:1533-1534` (text read); `:2114, :2122, :2125` (Wire 3 routing governance, GPR routing-bias, RM research-priority boost).
- **Required follow-up:** patch `MASTER_2026-05-07_attractor_closure_synthesis.md` to remove the stale `.FOCUS` claim. Tracked via the synthesis master's own update path, not a BR item.

### BR-016 (CLOSED 2026-05-07 18:08) — SOVEREIGN_MANIFEST.md count drift
- **Closing evidence:** `docs/governance/SOVEREIGN_MANIFEST.md` count-sensitive claims are enforced by `scripts/docops/check_docops_integrity.py`; after PR #167 merge resolution the manifest and `docs/docops/AUTO_INVENTORY.md` report `dharma_python_modules=550`, `dharma_top_level_python_modules=385`, `test_files=556`, and `test_def_occurrences=9970`.

### BR-017 (CLOSED 2026-05-07 18:06) — BUILD_SESSION_ENTRYPOINT.md cherry-picked
- **Closing evidence:** `git checkout origin/main -- docs/governance/BUILD_SESSION_ENTRYPOINT.md` brought the file into current checkout `feat/brief-to-spec-seam-2026-05-07` (7,837 bytes). Slot 9 of MEGAFILE_INDEX now has the in-repo session-entrypoint pointer it was missing. Convergence pass action 4.

### BR-018 (CLOSED 2026-05-07) — megafile index discoverability
- **Closing evidence:** `CLAUDE.md:146` Navigation now points cold agents to `docs/MEGAFILE_INDEX.md` (closed by user); `README.md:181` "Before Writing Any Code" section also references it (closed 2026-05-07 18:00 by convergence pass action 1).

### BR-001 (CLOSED 2026-05-07 18:08) — cron daemon plist path/version drift
- **Closing evidence:** Backed up plist to `~/.dharma/audit/_backup_com.dharma.cron-daemon.plist.2026-05-07`. Used `plutil -replace ProgramArguments` to update `~/Library/LaunchAgents/com.dharma.cron-daemon.plist` from `/opt/homebrew/bin/dgc cron daemon` to `/Users/dhyana/dharma_swarm_lf5/.venv/bin/dgc cron daemon`. `launchctl bootout gui/501/com.dharma.cron-daemon && launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.dharma.cron-daemon.plist` reloaded the daemon. Verified: old PID 10579 gone; new PID 14989 running with `/Users/dhyana/dharma_swarm_lf5/.venv/bin/dgc cron daemon`; `launchctl print gui/501/com.dharma.cron-daemon` reports state=running, `last exit code = (never exited)`, program = lf5-venv binary.
- **Verified `dgc cron daemon` is valid on lf5-venv:** `dgc cron --help` lists `{add,list,remove,tick,daemon}` subcommands.
- **Dependency note:** metabolic clock now pinned to `dharma_swarm_lf5` worktree. If lf5 is deleted, the daemon breaks. This dependency is intentional per user decision (smallest change, least risk path).
- **Follow-up verification:** BR-006 did later close after recognition seed regeneration; BR-005 narrowed but did not fully close because signal consumption remains uneven.
- **Convergence pass action 7.**

### BR-019 (CLOSED 2026-05-07) — Coherence Delta gate enforced honor-system only
- **Closing evidence:** `.github/workflows/coherence-delta.yml` runs `scripts/governance/check_pr_coherence_delta.py` against PR bodies and rejects missing, placeholder, or bare-UNKNOWN Coherence Delta fields. PR #167 is the first self-test of the gate.
- **Residual drift:** CI validates field presence and minimum substance, not semantic truth. Treat that residual as reviewer responsibility until a later semantic validator exists.

---

## ID Reservation

Next id: `BR-020`. Append below. Do NOT renumber existing items.

---

## Sources

This register was seeded 2026-05-07 from:
- `~/.dharma/audit/repo_hot_items_scratchpad_2026-05-07.md` (Agent A's 12 hot items)
- `~/.dharma/audit/ten_megafiles_survey_2026-05-07.md` §1 "The Six Major Discoveries"
- `~/.dharma/audit/ten_megafiles_q1..q6_2026-05-07.md` (per-question detail)
- `~/.dharma/audit/system_inventory_2026-05-07.md`
- `~/.dharma/audit/self_evolution_trace_2026-05-07.md`
- `~/.dharma/audit/central_loop_trace_2026-05-07.md`
- `dharma_swarm/docs/vision_maps/MASTER_2026-05-07_attractor_closure_synthesis.md`
- `dharma_swarm/docs/vision_maps/2026-05-07_attractor_closure/01..06_*.md`

Future appends should cite their source in the `evidence` field with file:line where possible.

---

*Append, do not rewrite. The register persists. Each item carries its own age. Closure requires evidence, not declaration.*
