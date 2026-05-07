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

## OPEN ITEMS (14 open after convergence pass 2026-05-07 18:08; 5 closed below)

> **Convergence pass executed 2026-05-07 18:00–18:10:** Plan at `~/.claude/plans/yes-write-a-plan-wobbly-cerf.md`. Closed items moved to CLOSED section: BR-001 (cron daemon plist fixed), BR-016 (SOVEREIGN_MANIFEST counts refreshed 514→567), BR-017 (BUILD_SESSION_ENTRYPOINT.md cherry-picked), BR-018 (MEGAFILE_INDEX referenced from CLAUDE.md + README). BR-015 was already CLOSED. Total CLOSED = 5; OPEN = 14.

*(BR-001 moved to CLOSED ITEMS — see below)*

### BR-002 — Central VentureCell loop is open
- **first_observed:** 2026-05-07
- **last_verified:** 2026-05-07
- **age_days:** 0
- **severity:** BLOCKER
- **domain:** runtime
- **root_cause:** Board → VentureCell → gates → dispatch → outcome → witness/algedonic → board feedback path is not closed. Outcomes do not feed back into opportunity_board.json.
- **blast_radius:** Shakti always re-derives from raw signals; opportunity loop is forward-only; "later VentureCells more powerful than earlier" is aspiration, not mechanism.
- **evidence:** `~/.dharma/audit/central_loop_trace_2026-05-07.md`; vision_maps `06_outward_organs.md`; survey synthesis Finding 2.
- **status:** PARTIAL — 2026-05-07 partial closure across two writes:
  1. **Read side (this branch):** `dharma_swarm/shakti_executive/inputs.py` reads TelicSeam `Outcome` / `ValueEvent` / `Contribution`, dispatcher health, campaign manifests, and Darwin sealed-packet archive rows as feedback signals.
  2. **Write side (this commit):** `dharma_swarm/shakti_executive/feedback_writer.py` exposes `update_opportunity_outcome(opp_id, outcome)` that appends realized outcomes to `opportunity_board.json` and updates `learned_score_delta`. Atomic write, idempotent on duplicate `outcome_id`, capped per-outcome score delta. 8/8 tests pass under `tests/test_feedback_writer.py`. **Caller wiring (proposal_id → campaign manifest → opportunity_id resolution) is NOT yet in place** — the writer is a public-API library; the resolver is a follow-up. Full VentureCell polymorphism (BR-008) and full loop closure remain open.

### BR-003 — Apply gate present but closed (self-evolution loop)
- **first_observed:** 2026-05-07
- **last_verified:** 2026-05-07
- **age_days:** 0
- **severity:** BLOCKER
- **domain:** runtime
- **root_cause:** Two parallel apply paths share zero import edge. Build Protocol (`tools/build_protocol/`) self-declared shape-only; DarwinEngine `apply_diff_and_test` at `evolution.py:2156` env-locked closed by `DHARMA_EVOLUTION_SHADOW=1` default. `grep "from dharma_swarm.tools.build_protocol"` returns 0 hits inside `dharma_swarm/dharma_swarm/`.
- **blast_radius:** Self-evolution trace reported 96 dryruns; direct disk check on 2026-05-07 found 9 current dryrun dirs, 4 `proof_packet.json` files, and 0 `applied` markers. Sediment-to-crystallization mechanism remains absent. Kernel + telos_gates static for 6+ weeks.
- **evidence:** `~/.dharma/audit/self_evolution_trace_2026-05-07.md`; `find ~/.dharma/build_protocol/dryruns -mindepth 1 -maxdepth 1 -type d | wc -l` = 9; `find ~/.dharma/build_protocol -name proof_packet.json | wc -l` = 4; vision_maps `05_autopoiesis_evolution.md`.
- **status:** WORKAROUND — 2026-05-07 partial closure: `tools/build_protocol/cli.py` now exposes `dharma-build shadow-apply <dryrun_root>`, which calls `DarwinEngine.apply_sealed_packet(..., shadow=True)` and archives the proof result without live mutation. Live apply remains intentionally gated.

### BR-004 — Cron split-brain (repo vs live)
- **first_observed:** ≤ 2026-05-06
- **last_verified:** 2026-05-07
- **age_days:** 1+
- **severity:** DEGRADED
- **domain:** cron / docs
- **root_cause:** Repo `dharma_swarm/cron_jobs.json` has 17 jobs (schema A); live `~/.dharma/cron/jobs.json` has 484 lines (schema B); 1 shared id; 16 orphaned. `scripts/cron_unify.py:5-9` documents the split. No doc declares which is canonical.
- **blast_radius:** Operator-loop documentation (Slot 8) cannot be written until canonical declared.
- **evidence:** `~/.dharma/audit/cron_split_brain_*.json` (3 snapshots, latest 2026-05-06 22:30); `ten_megafiles_q5_2026-05-07.md`.
- **status:** OPEN.

### BR-005 — Algedonic stream in degenerate steady-state
- **first_observed:** ~2026-05-02 (5 days prior to audit)
- **last_verified:** 2026-05-07 20:30 (post-BR-001-fix verification)
- **age_days:** ~5
- **severity:** DEGRADED
- **domain:** runtime
- **root_cause:** Current last-200 algedonic rows contain only `omega_divergence medium rebalance_priorities`: 116 rows at `0.683`, 84 rows at `0.6527`. Not literally one identical value, but still a low-information steady-state. Consumer side likely dead or under-wired. **POST-BR-001 VERIFICATION**: 2 hours after the cron-daemon plist fix landed (PID 35207 running lf5-venv binary), `tail -50 ~/.dharma/algedonic_signals.jsonl | jq '.value' | sort -u` returns ONLY `0.683` (1 distinct value). Conclusion: BR-005 root cause is NOT the cron daemon path/version drift. Independent issue.
- **blast_radius:** No rich causal feedback into the swarm. EMERGENCY_HOLD never escalates. Algedonic channel is structurally present (`vsm_channels.py:373`, `organism.py:968` — note duplicate types) but operationally inert.
- **evidence:** `tail -200 ~/.dharma/algedonic_signals.jsonl | jq '[.kind,.severity,.action,.value]'` summary on 2026-05-07; `~/.dharma/audit/ten_megafiles_q3_2026-05-07.md`; `vsm_channels.py:373`; `organism.py:968`. Post-fix verification: `launchctl print gui/501/com.dharma.cron-daemon` shows running PID 35207 with lf5-venv binary; algedonic stream still emits one value.
- **status:** OPEN — needs SCOPED INVESTIGATION (likely consumer-side: where does `algedonic_signals.jsonl` get read, and does that reader emit anything OTHER than the one stuck signal?). Not auto-resolved by cron daemon fix.

### BR-006 — Recognition seed stale
- **first_observed:** ~2026-05-01 (6 days prior to audit)
- **last_verified:** 2026-05-07 20:30 (post-BR-001-fix verification)
- **age_days:** 6
- **severity:** DEGRADED
- **domain:** runtime / agent
- **root_cause:** `~/.dharma/meta/recognition_seed.md` is 6 days old despite metabolic-clock doctrine claiming nightly regeneration. Correlates with BR-001 cron LaunchAgent drift; direct causality is not proven because launchd reports the daemon process still running. **POST-BR-001 VERIFICATION**: 2 hours after cron-daemon plist fix landed, `stat -f "%Sm" ~/.dharma/meta/recognition_seed.md` returns `May 1 08:58:32 2026` — seed mtime is UNCHANGED. Conclusion: BR-006 is NOT downstream of BR-001. The cron daemon firing more reliably does not by itself trigger recognition_seed regeneration. Independent issue.
- **blast_radius:** Agents loading context get stale self-model. Recognition is recognition of yesterday's state.
- **evidence:** `~/.dharma/audit/ten_megafiles_q6_2026-05-07.md`; vision_maps `04_recognition_self_model.md`. Post-fix verification: cron daemon PID 35207 running lf5-venv binary; recognition_seed mtime unchanged at May 1.
- **status:** OPEN — needs SCOPED INVESTIGATION (where in the metabolic clock does recognition_seed regeneration happen? `meta_daemon.py:RecognitionEngine`? Is there a separate cron handler that should fire it? The `meta_daemon.py:272-285` hard-coded March 2026 thesis-timing logic — does that gate regeneration?). Not auto-resolved by cron daemon fix.

### BR-007 — Two stores for one self (runtime.db ↔ ontology.db never synced)
- **first_observed:** 2026-05-07
- **last_verified:** 2026-05-07
- **age_days:** 0
- **severity:** BLOCKER (architectural)
- **domain:** runtime / state
- **root_cause:** `runtime.db` (live operational state) and `ontology.db` (typed self-model) are not continuously synchronized. Plus runtime.db itself has path drift: SwarmManager uses `state/runtime.db` for live orchestration but `_record_memory_fact()` writes `db/runtime.db`.
- **blast_radius:** Every gate, audit, and recognition fires against a stale picture. Recognition is commentary instead of causal.
- **evidence:** `~/.dharma/audit/repo_hot_items_scratchpad_2026-05-07.md` (item #2); ten_megafiles synthesis Finding 1.
- **status:** OPEN.

### BR-008 — VentureCell-as-ontology vs VentureCell-as-organ are not the same artifact
- **first_observed:** 2026-05-07
- **last_verified:** 2026-05-07
- **age_days:** 0
- **severity:** BLOCKER (architectural)
- **domain:** runtime
- **root_cause:** Registering a `VentureCell` in `ontology.py:1876` inherits invariants automatically. Creating a running organ (Ginko, Loomwork) re-derives loop, state file, and adapters bespoke. No polymorphism between the two definitions.
- **blast_radius:** "Later VentureCells more powerful than earlier" is aspiration, not mechanism. 0 of named outward organs are full-spine-attached (8 surfaces).
- **evidence:** vision_maps `06_outward_organs.md`; ten_megafiles synthesis Finding 2.
- **status:** OPEN.

### BR-009 — Roadmap is contested (3 docs claim primacy)
- **first_observed:** 2026-05-07
- **last_verified:** 2026-05-07
- **age_days:** 0
- **severity:** DEGRADED
- **domain:** docs
- **root_cause:** `LOOMWORK_v0_MASTER.md` self-declares OPERATIONAL; `2026-05-07-loomwork-design.md` self-declares "draft, awaiting review" but `MEMORY.md:37` says it supersedes the master; `ARJUNA_DIRECTIVE_v1.md` still owns Q2/Q3 sequence.
- **blast_radius:** 47% of in-flight branches have no plan-doc anchor. Strategy ~10x ahead of code. Onboarding agents flip a coin.
- **evidence:** `~/.dharma/audit/ten_megafiles_q4_2026-05-07.md`; `MEMORY.md:37`.
- **status:** OPEN.

### BR-010 — `NAVIGATION.md` exists at non-canonical path; file itself stale
- **first_observed:** ≤ 2026-05-07
- **last_verified:** 2026-05-07 18:00 (REVISED twice)
- **age_days:** generated 2026-03-29 → 39 days stale
- **severity:** STALE
- **domain:** docs
- **root_cause:** **REVISED 3x:** `NAVIGATION.md` DOES exist at `dharma_swarm/docs/architecture/NAVIGATION.md` BUT the file itself was generated 2026-03-29 with old counts and has not been refreshed against current 567-Python-file reality. `CLAUDE.md` now points to both `docs/architecture/NAVIGATION.md` and `make xray`; remaining disagreement is stale static map vs generated live map.
- **blast_radius:** Slot 4 (Limbs Atlas) — substrate exists but stale. Module count drift (370/421/479/500/567 actual) unresolved across sources.
- **evidence:** `find . -maxdepth 4 -name NAVIGATION.md` returns `./docs/architecture/NAVIGATION.md`; codex validation pass at `~/.dharma/audit/ten_megafiles_survey_2026-05-07.md` cites `docs/architecture/NAVIGATION.md:1-7, :88-119` confirming 2026-03-29 generation date and old counts.
- **status:** OPEN — 2026-05-07 partial fix: `CLAUDE.md` now points to `docs/MEGAFILE_INDEX.md`, `docs/architecture/NAVIGATION.md`, and `make xray`; remaining fix is regenerate stale `docs/architecture/NAVIGATION.md` against current 567-file reality.

### BR-011 — `INTERFACE_MISMATCH_MAP.md` self-declared stale
- **first_observed:** ≤ 2026-04-25
- **last_verified:** 2026-05-07
- **age_days:** ~12
- **severity:** STALE
- **domain:** docs
- **root_cause:** Header self-declares "memorial, not battle plan." `CLAUDE.md` calls it "#1 source of runtime failures" but the doc admits ~12/25 entries resolved + ~7 unverified. Mismatch between authority claim and content state.
- **blast_radius:** Slot 5 (Wiring + Loop Ledger) cannot be canonical until refreshed.
- **evidence:** `~/.dharma/audit/ten_megafiles_q2_2026-05-07.md`.
- **status:** OPEN.

### BR-012 — `CYBERNETIC_LOOP_MAP.md` stale (6 days)
- **first_observed:** 2026-05-01
- **last_verified:** 2026-05-07
- **age_days:** 6
- **severity:** STALE
- **domain:** docs
- **root_cause:** `CYBERNETIC_LOOP_MAP.md:196-208` claims recognition seed was never generated. Current code has it (`meta_daemon.py:1-13` + `context.py:1202-1217`). Doc lies; nothing flags the lie.
- **blast_radius:** Agents reading the doc believe loops are closed when runtime says they aren't.
- **evidence:** `~/.dharma/audit/ten_megafiles_q2_2026-05-07.md`; vision_maps `04_recognition_self_model.md`.
- **status:** OPEN.

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
- **status:** OPEN.

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
- **root_cause:** `docs/governance/SOVEREIGN_MANIFEST.md` claims 514 Python files under `dharma_swarm/`. Actual count `find dharma_swarm -name "*.py" -type f | wc -l` = **567**. Drift of 53 files, ~10%.
- **blast_radius:** SOVEREIGN_MANIFEST is named as authority surface in CANONICAL_DOC_STACK; agents reading it for governance scope get a stale picture. Affects Slot 2 (Operational Doctrine) and Slot 4 (Limbs Atlas) consolidation.
- **evidence:** `find dharma_swarm -name "*.py" -type f | wc -l` returns 567 (verified 2026-05-07). Agent C convergence audit cites SOVEREIGN_MANIFEST count claim.
- **status:** **FIXED 2026-05-07 18:08** — `docs/governance/SOVEREIGN_MANIFEST.md` lines 18, 63, 388 refreshed: 514 → 567. Top-level percentage recomputed: 73% → 66% (375/567). Convergence pass action 3.

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

### BR-015 (CLOSED 2026-05-07 18:00) — `.FOCUS` reader
- **Closing evidence:** `dharma_swarm/swarm.py:1514` ("Check .PAUSE, .FOCUS, .INJECT, EMERGENCY_HOLD files."); `:1533-1534` (text read); `:2114, :2122, :2125` (Wire 3 routing governance, GPR routing-bias, RM research-priority boost).
- **Required follow-up:** patch `MASTER_2026-05-07_attractor_closure_synthesis.md` to remove the stale `.FOCUS` claim. Tracked via the synthesis master's own update path, not a BR item.

### BR-016 (CLOSED 2026-05-07 18:08) — SOVEREIGN_MANIFEST.md count drift
- **Closing evidence:** `docs/governance/SOVEREIGN_MANIFEST.md` lines 18, 63, 388 refreshed from 514 → 567. Top-level flat-package percentage recomputed: 73% → 66% (375/567). Verification `grep -n "514" docs/governance/SOVEREIGN_MANIFEST.md` returns no count claims at the three patched locations. Convergence pass action 3.

### BR-017 (CLOSED 2026-05-07 18:06) — BUILD_SESSION_ENTRYPOINT.md cherry-picked
- **Closing evidence:** `git checkout origin/main -- docs/governance/BUILD_SESSION_ENTRYPOINT.md` brought the file into current checkout `feat/brief-to-spec-seam-2026-05-07` (7,837 bytes). Slot 9 of MEGAFILE_INDEX now has the in-repo session-entrypoint pointer it was missing. Convergence pass action 4.

### BR-018 (CLOSED 2026-05-07) — megafile index discoverability
- **Closing evidence:** `CLAUDE.md:146` Navigation now points cold agents to `docs/MEGAFILE_INDEX.md` (closed by user); `README.md:181` "Before Writing Any Code" section also references it (closed 2026-05-07 18:00 by convergence pass action 1).

### BR-001 (CLOSED 2026-05-07 18:08) — cron daemon plist path/version drift
- **Closing evidence:** Backed up plist to `~/.dharma/audit/_backup_com.dharma.cron-daemon.plist.2026-05-07`. Used `plutil -replace ProgramArguments` to update `~/Library/LaunchAgents/com.dharma.cron-daemon.plist` from `/opt/homebrew/bin/dgc cron daemon` to `/Users/dhyana/dharma_swarm_lf5/.venv/bin/dgc cron daemon`. `launchctl bootout gui/501/com.dharma.cron-daemon && launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.dharma.cron-daemon.plist` reloaded the daemon. Verified: old PID 10579 gone; new PID 14989 running with `/Users/dhyana/dharma_swarm_lf5/.venv/bin/dgc cron daemon`; `launchctl print gui/501/com.dharma.cron-daemon` reports state=running, `last exit code = (never exited)`, program = lf5-venv binary.
- **Verified `dgc cron daemon` is valid on lf5-venv:** `dgc cron --help` lists `{add,list,remove,tick,daemon}` subcommands.
- **Dependency note:** metabolic clock now pinned to `dharma_swarm_lf5` worktree. If lf5 is deleted, the daemon breaks. This dependency is intentional per user decision (smallest change, least risk path).
- **Likely auto-resolves:** BR-006 (recognition_seed stale) within 24-48h once metabolic clock fires regeneration. May also un-stick BR-005 (algedonic degenerate steady-state) if consumer was waiting on the daemon.
- **Convergence pass action 7.**

---

## ID Reservation

Next id: `BR-020`. Append below. Do NOT renumber existing items.

---

### BR-019 — Coherence Delta gate enforced honor-system only
- **first_observed:** 2026-05-07
- **last_verified:** 2026-05-07 18:50
- **age_days:** 0 (born today)
- **severity:** DEGRADED
- **domain:** governance
- **root_cause:** The Coherence Delta gate (4 mandatory PR-template fields installed by commit `8e1dccb` on `codex/pr-coherence-delta-template` and PR #154 with rationale doc) is not validated by any tooling. No pre-commit hook checks the field markers; no GitHub Action validates that the colon-fields are non-empty; no review bot flags omissions.
- **blast_radius:** Gate is bypassable. The first sloppy PR breaks the discipline. Architectural intent ("convergence not invention") relies on every PR re-reading the maps and registering its drift; honor-system means a single PR that skips the fields silently disconnects the loop.
- **evidence:** `dharma_swarm/.pre-commit-config.yaml` does not reference template fields; `.github/workflows/*` runs `commit-lint` + tests but no template-body validator; `docs/governance/COHERENCE_DELTA.md` § "Honor-system enforcement, for now" explicitly acknowledges the gap and names three future-hardening paths (CodeRabbit, GitHub Action template-validator, pre-commit hook).
- **status:** OPEN — track CodeRabbit install OR template-validator GitHub Action as future fix. Recommended priority: medium (DEGRADED, not BLOCKER); convert to BLOCKER if any merged PR ships with the four fields un-filled within the next 30 days.

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
