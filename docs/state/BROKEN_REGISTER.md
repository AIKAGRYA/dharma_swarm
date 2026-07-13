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

## OPEN ITEMS (9 open/partial — canonical parser count reconciled 2026-07-14)

> **Re-verification pass executed 2026-06-15 (perplexity-computer, Stage 1 EVIDENCE_ONLY):** the register had drifted 22 days since the 2026-05-24 git touch. All 5 OPEN items below have refreshed `last_verified` dates with a `re-verification 2026-06-15` note. No new BRs opened in this pass. No status flips: behavior on disk is unchanged for BR-003 / BR-004 / BR-005 / BR-013 / BR-014. Anti-Slop note: PROD-issue #521 cites this BR-003 as 'Owner doc' but its own owner doc `docs/governance/PROD_READINESS_TOP10.md` does not exist on any branch — BR-003 is real and tracked here; the PROD-issue is the orphan.

> **Historical: 2026-05-20 closure pass** — BR-009/010/011/012 fixed below.

> **Convergence pass executed 2026-05-07 18:00–18:10:** Plan at `~/.claude/plans/yes-write-a-plan-wobbly-cerf.md`. Closed items moved to CLOSED section: BR-001 (cron daemon plist fixed), BR-016 (SOVEREIGN_MANIFEST counts refreshed and now DocOps-verified), BR-017 (BUILD_SESSION_ENTRYPOINT.md present), BR-018 (MEGAFILE_INDEX referenced from CLAUDE.md + README), BR-019 (Coherence Delta CI validator installed). BR-015 was already CLOSED. Total CLOSED = 6; OPEN = 13.

*(BR-001, BR-002, BR-006, and BR-008 moved to CLOSED ITEMS — see below. BR-007's historical closure entry is retained in CLOSED ITEMS but is superseded by the reopened entry here.)*

### BR-007 — REOPENED 2026-07-01 — runtime.db and ontology.db sync still broken
- **first_observed:** 2026-05-10 closure later disproven; independently re-confirmed 2026-06-10 and 2026-07-01.
- **last_verified:** 2026-07-14
- **age_days:** 65 since original closure claim; 34 since the 2026-06-10 re-confirmation.
- **severity:** BLOCKER
- **domain:** runtime / state
- **root_cause:** The closure evidence assumed one canonical ontology/runtime path and an enabled sync path. The 2026-07-14 operator-Mac host-local snapshot still finds `store_sync.enabled=false`, a populated home ontology beside a zero-byte checkout ontology, and no sync-derived ontology artifact rows in the inspected runtime DB.
- **blast_radius:** Ontology/runtime self-recognition remains split; status surfaces can claim closure from code presence while live state never converges.
- **evidence (host-local witness; observed 2026-07-13T20:11:55Z / 2026-07-14T05:11:55+09:00 and independently replayed 2026-07-14 06:39 JST with the same results):** exact read-only operator-Mac commands and outputs:
  - `jq -c '.. | objects | select(.id? == "store_sync") | {id,handler,enabled}' ~/.dharma/cron/jobs.json` → `{"id":"store_sync","handler":"store_sync","enabled":false}`
  - `sqlite3 -readonly ~/.dharma/ontology.db 'SELECT COUNT(*) FROM objects;'` → `22065`
  - `stat -f '%z' "$HOME/dharma_swarm/dharma_swarm/ontology.db"` → `0`
  - `sqlite3 -readonly ~/.dharma/state/runtime.db "SELECT COUNT(*), SUM(CASE WHEN artifact_id LIKE 'ont-%' THEN 1 ELSE 0 END) FROM artifact_records;"` → `4241|0`
  - These commands make the snapshot reproducible on that host. Clean clone/CI and every other seat remain **Unobserved** for these host files; the witness refutes the former global closure claim but does not prove fleet-wide topology or authorize store consolidation. `dharma_swarm/cron_runner.py` exposes code, but code presence is not live convergence.
- **status:** OPEN — documentation corrected. Do not re-enable `store_sync` or consolidate database files until the operator chooses the canonical `ontology.db` copy and a backup/merge plan exists.

### BR-003 — Apply gate present but closed (self-evolution loop)
- **first_observed:** 2026-05-07
- **last_verified:** 2026-06-15 (re-verified by perplexity-computer)
- **age_days:** 39
- **severity:** BLOCKER
- **domain:** runtime
- **root_cause:** Two parallel apply paths share zero import edge. Build Protocol (`tools/build_protocol/`) self-declared shape-only; DarwinEngine `apply_diff_and_test` at `evolution.py:2156` env-locked closed by `DHARMA_EVOLUTION_SHADOW=1` default. `grep "from dharma_swarm.tools.build_protocol"` returns 0 hits inside `dharma_swarm/dharma_swarm/`.
- **blast_radius:** Self-evolution trace reported 96 dryruns; direct disk check on 2026-05-07 found 9 current dryrun dirs, 4 `proof_packet.json` files, and 0 `applied` markers. Sediment-to-crystallization mechanism remains absent. Kernel + telos_gates static for 6+ weeks.
- **evidence:** `~/.dharma/audit/self_evolution_trace_2026-05-07.md`; `find ~/.dharma/build_protocol/dryruns -mindepth 1 -maxdepth 1 -type d | wc -l` = 9; `find ~/.dharma/build_protocol -name proof_packet.json | wc -l` = 4; vision_maps `05_autopoiesis_evolution.md`.
- **status:** PARTIAL — 2026-05-07 partial closure: `tools/build_protocol/cli.py` now exposes `dharma-build shadow-apply <dryrun_root>`, which calls `DarwinEngine.apply_sealed_packet(..., shadow=True)` and archives the proof result without live mutation. Live apply remains intentionally gated. **End-to-end exercise on 2026-05-07 (this commit):** ran `python -m tools.build_protocol.cli shadow-apply ~/.dharma/build_protocol/dryruns/wp005-seal-cli-20260506`. Result: `accepted: true`, `archive_entry_id: 64280c7685784e63`, `shadow: true`, `proof_exit_code: 0` (5 tests pass), packet archived as line in `~/.dharma/evolution/archive.jsonl` with id `64280c7685784e63` and `shadow:true`. First confirmed end-to-end shadow-apply on this branch. `applied:false` is correct — `diff_missing:true` for this dryrun (test-only seal, no diff to apply); the seam itself is now exercised. Full closure (live, non-shadow apply) remains a multi-day plan gated by `DHARMA_EVOLUTION_SHADOW=0` and a real telos-gate→kernel→apply traversal.
- **re-verification 2026-06-15 (perplexity-computer):** `DHARMA_EVOLUTION_SHADOW` defaults to `"1"` at 5 callsites confirmed by repo grep: `dharma_swarm/swarm_health_api.py:97` and `:142`, `dharma_swarm/orchestrate_live.py:618`, `dharma_swarm/dgm_loop.py:289`, `benchmarks/gauntlet.py:387` and `:409`. `dharma_swarm/guardian_crew.py:503,506` explicitly instructs operators to set both `DHARMA_EVOLUTION_SHADOW=0` and `DGC_AUTONOMY_LEVEL=2` for real mutation. `dharma_swarm/evolution.py:190` still defaults `applied=False, shadow=True` on the `AppliedResult` dataclass. Cannot inspect `~/.dharma/evolution/archive.jsonl` from cloud seat; no `applied:true` line confirmable. Status PARTIAL unchanged. Cross-references: PROD-issue #521 cites this BR as 'Owner doc' — the BR is real; the PROD-issue's own owner doc `docs/governance/PROD_READINESS_TOP10.md` does not exist on any branch.

### BR-021 — WS4 Tier-C battery hard-rejects terse evolution-test proposals
- **first_observed:** 2026-06-21
- **last_verified:** 2026-06-21
- **age_days:** 0
- **severity:** DEGRADED
- **domain:** runtime / state (tests)
- **root_cause:** WS4 (`dharma_swarm/evolution.py` ~L1543) hard-rejects a self-mod proposal on any Tier-C advisory `REVIEW`; the anekanta / steelman / dogma-drift gates were tightened *after* the evolution test suite was written, so proposals with terse descriptions are rejected for "low epistemological diversity" / "no counterarguments" — unrelated to what the tests assert. Masked for weeks under `pytest -x` (stopped at an earlier failure).
- **blast_radius:** ~8 tests in `tests/test_integration.py` + `tests/test_godel_claw_e2e.py` (routed through the new helper); OTHER evolution test files may still carry terse self-mod proposals and will surface as `pytest -x` advances. Real internal callers that build terse self-mod proposals would also be rejected.
- **evidence:** `scripts/diagnostics/proposal_gate_probe.py` (per-gate map); `tests/evolution_gate_helpers.py` + `tests/test_evolution_gate_helpers.py` (self-validating helper); `docs/architecture/EVOLUTION_PROPOSAL_GATE_CONTRACT.md` (contract).
- **status:** WORKAROUND — contract mapped, self-validating helper built, `test_integration` + `godel_claw` routed through it. Remaining evolution test files to be routed as CI surfaces them. WS4 itself is correct and intentionally unchanged; do not weaken it.

### BR-022 — Outward receipt quorum below authority; governance-rent instrument Unobserved
- **first_observed:** 2026-06-21
- **last_verified:** 2026-07-14
- **age_days:** 23 since first_observed; 11 calendar days since the latest tracked authority artifact as of 2026-07-14 JST.
- **severity:** STALE
- **domain:** outward
- **root_cause:** The original ownership claim is Refuted: current `ACTIVE_TRACK.yaml` declares `revenue-external-humans-served` owners in `company-builder-parity-2026-07` and `darshan-publication-2026-07`, and a `research-depth` owner in `hyperbolic-time-chamber-2026-07`. Those are intent declarations, not evidence that external value was delivered. The latest tracked Measurement Guardian authority artifact on exact base c631a492 records only N=3 confirmed acted receipts across M=1 domain, below the required N>=5/M>=3, with `v1_external_threshold_ready=false` and `fitness_authority_granted=false`. Later untracked or live state is Unobserved. The exhaustive claim that no executable per-gate rent/diversity-cost instrument exists is also Unobserved; repository search alone cannot prove system-wide absence.
- **blast_radius:** Outward work has named owners, but archive-fitness authority and a repeatable external-value loop remain blocked below the tracked receipt quorum. Governance coordination cost may remain unmeasured, but no absence claim is promoted without an authority-complete census.
- **evidence:** `docs/governance/ACTIVE_TRACK.yaml` (two declared revenue owners and one declared research owner); `reports/forge/measurement-guardian/cycle-004-intake-restart.json` (observed `2026-07-03T14:45:00Z`; `confirmed_receipt_count=3`, `domain_count=1`, required 5/3, `v1_external_threshold_ready=false`, `fitness_authority_granted=false`); `docs/architecture/EXTERNAL_GRADIENT_PORTFOLIO_SPEC.md` (N>=5/M>=3 boundary); `CLAUDE.md` Transcendence Principle and `dharma_swarm/diversity_archive.py` establish the doctrine/adjacent diversity measure but do not prove exhaustive rent-instrument absence.
- **status:** PARTIAL — the ownership-absence claim is Refuted; the latest tracked authority artifact proves receipt quorum below threshold, while later state and the governance-rent instrument census remain Unobserved. Do not add another governance mechanism merely to close this row.

### BR-023 — Provider key-loading split-brain (four loaders, shadow stores, lying credit heuristic)
- **first_observed:** 2026-07-03 (weeks of symptoms; formalized after tri-agent local audit + repo sweep)
- **last_verified:** 2026-07-03
- **age_days:** 0
- **severity:** DEGRADED
- **domain:** runtime / providers / ops
- **root_cause:** Provider credential authority answered five questions with split owners and no parity: (1) key VALUES loaded by **four** loaders with two conflicting precedence semantics — `api_keys.bootstrap_runtime_env()` (never-overwrite) vs `scripts/load_runtime_env.sh` (`set -a` last-wins + keychain + narrower alias table) vs inline launchd plist snippets vs `~/.zshrc` — sharing one marker set in 2 places and checked in 1; (2) launchd plists bypassed both canon loaders; `com.dharma.swarm` did a no-op `source .env` (no `set -a`) while cron/semantic-responder plists `set -a; source` the project `.env` AFTER the vault, so a stale repo `.env` **shadowed** the vault's real `OPENAI_API_KEY` (observed live: 13-char placeholder over 164-char key); (3) liveness (`~/.dharma/keys_status.json`) written only by manual `dkeys test` on the Mac — stale (34h+), absent on the VPS, probe lighter than a real completion; (4) `scripts/check_provider_credits.py` measured env-presence + an UNWINDOWED log-grep whose regexes missed the live failure wording ("weekly usage limit"), so `likely_exhausted` was simultaneously sticky-forever for stale 402s and blind to the actually-capped chain-head (ollama); (5) the live fleet runs branch `agent/magpie-seed` (~330 behind main), so main describes a system that is not the one running. The `provider-routing-consolidation-2026-06` closeout (2026-06-30) explicitly deferred `.env.example` reconciliation (`docs/ops/PROVIDER_ROUTING_ARCHITECTURE.md:128`) and its recommended successor track was never opened — this BR is that unowned residue.
- **blast_radius:** Every seat (Mac daemons, VPS, cloud agents) computes a different answer to "which keys do we have / which lanes work"; agents repeatedly report "low on api keys" from heuristic echo; same host runs daemons with disjoint key sets; `chain=['ollama']` dispatch failures while the credit monitor reports 0 exhausted.
- **evidence:** Tri-agent local audit 2026-07-03/04 (codex+, fable-5, fugu — length-13 vs length-164 OPENAI shadow proof; four-loader census; `swarm.err` weekly-usage-limit lines vs `likely_exhausted=0`); repo sweep same date (compose passed 3/17 lanes pre-fix; `tests/test_provider_env_parity.py` now guards that projection); `reports/governance/prod_readiness/PROD_GRADE_REVIEW_RESULTS_2026-06-22.md:234` (successor track demanded, never opened).
- **status:** PARTIAL — repo-side slices landed 2026-07-03 on `claude/dharma-swarm-audit-rewire-gwo59q`: compose/.env.example/docs parity + registry-derived CI test; ONE-loader unification (`dharma_swarm/runtime_env_loader.py`: keychain step + split-store guard folded into `bootstrap_runtime_env()`; `load_runtime_env.sh` now a thin `emit-exports` wrapper with one precedence semantic; `com.dharma.swarm.plist` no longer sources `.env`); credit checker windowed (72h default) + patterns extended (429/usage-limit/resource-exhausted) + output labeled heuristic. REMAINING (operator/local): reinstall the fixed plist + fix the Mac-local cron/semantic-responder plists to stop `set -a` sourcing project `.env`; strip provider keys from the Mac repo `.env`; remove the ANTHROPIC→Kimi envelope from the vault (`KIMI_*` lanes already exist); put `dkeys test` on a clock and provide a keys_status writer on the VPS; converge `agent/magpie-seed` ↔ main. Do NOT add a new key store or a second registry to fix this.

### BR-004 — Cron split-brain (repo vs live)
- **first_observed:** ≤ 2026-05-06
- **last_verified:** 2026-06-15 (re-verified by perplexity-computer)
- **age_days:** 40+
- **severity:** DEGRADED
- **domain:** cron / docs
- **root_cause:** Repo `dharma_swarm/cron_jobs.json` and live `~/.dharma/cron/jobs.json` still use different schemas and job populations. The original sub-claim "No doc declares which is canonical" is now stale.
- **blast_radius:** Job-level health can still diverge between repo intent and launchd reality, but the scheduler state authority is no longer ambiguous.
- **evidence:** `docs/governance/METABOLIC_CLOCK.md` declares `~/.dharma/cron/jobs.json` as scheduler state authority and says to fix failed jobs as separate scoped work packets. `scripts/cron_unify.py` remains the non-mutating unification helper.
- **status:** PARTIAL — canonical authority declared; actual repo/live job reconciliation remains a scoped follow-up.
- **re-verification 2026-06-15 (perplexity-computer):** `dharma_swarm/cron_jobs.json` present in repo (intent); `~/.dharma/cron/jobs.json` cannot be inspected from cloud seat. `docs/governance/METABOLIC_CLOCK.md` still declares the live-side authority. `scripts/cron_unify.py` present. No reconciliation PR landed in the 232 commits since last verification. Status PARTIAL unchanged.

### BR-005 — Algedonic stream in degenerate steady-state
- **first_observed:** ~2026-05-02 (5 days prior to original audit)
- **last_verified:** 2026-06-15 (re-verified by perplexity-computer)
- **age_days:** ~44
- **severity:** DEGRADED
- **domain:** runtime
- **root_cause:** The original "last-200 rows are only omega_divergence" finding is now stale. The live stream contains chronic `omega_divergence` plus many `task_retries_exhausted` dead-letter warning signals. The remaining gap is consumer/action coherence: some actions emitted by `algedonic_activation.py` are unsupported or only partially consumed by `Organism`/VSM paths.
- **blast_radius:** Sensing is richer than actuation. Signals exist, but not every signal class has an explicit consumer policy: log-only, prompt-context, scheduling bias, review, hold, or dispatch stop.
- **evidence:** 2026-05-11 live tail of `~/.dharma/algedonic_signals.jsonl`; `dharma_swarm/algedonic_activation.py` defines `rebalance_priorities`, `enforce_glossary`, and `recalibrate_from_metrics`; `dharma_swarm/organism.py` concretely handles only a subset of algedonic actions.
- **status:** PARTIAL — degenerate steady-state claim corrected; causal consumption/action coverage remains open.
- **re-verification 2026-06-15 (perplexity-computer):** `dharma_swarm/algedonic_activation.py` still defines `rebalance_priorities`, `enforce_glossary`, `recalibrate_from_metrics`. `dharma_swarm/organism.py` still concretely handles only a subset. Live `~/.dharma/algedonic_signals.jsonl` cannot be inspected from cloud seat. Status PARTIAL unchanged.

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
- **last_verified:** 2026-06-15 (re-verified by perplexity-computer)
- **age_days:** 39
- **severity:** DEGRADED
- **domain:** agent / docs
- **root_cause:** 25 `~/.claude/projects/-Users-dhyana/memory/feedback_*.md` files (~792 lines) un-consolidated; some carry 36-day-stale system-reminders. `~/.claude/CLAUDE.md` is a 4-line ruflo stub; canonical is `/Users/dhyana/CLAUDE.md` (308 lines) — naming suggests reverse. `foundations/GLOSSARY.md` exists but is **not referenced** from `CLAUDE.md`, `MEMORY.md`, or `cabinet/INDEX.md`.
- **blast_radius:** Non-Claude-Code agents (Codex sub-agents, headless invocations, MCP workers) may have NO path to the substrate. Onboarding requires prior knowledge of where the canonical contract lives.
- **evidence:** `~/.dharma/audit/ten_megafiles_q6_2026-05-07.md`.
- **status:** PARTIAL — 2026-05-07 19:29 (Phase 3D micro-fix): `~/.claude/CLAUDE.md` replaced with a pointer-stub directing agents to `/Users/dhyana/CLAUDE.md`. Backup at `~/.dharma/audit/_backup_~.claude.CLAUDE.md.2026-05-07`. Remaining work: consolidate the 25 `feedback_*.md` files into Slot 9 of MEGAFILE_INDEX (`docs/agent/AGENT_CONTRACT_AND_TEAM.md`); add a discoverability path from `CLAUDE.md` / `MEMORY.md` / `cabinet/INDEX.md` to `foundations/GLOSSARY.md`. Non-CC agents that cannot follow the pointer-stub still hit the gap; that residual issue is the active part of BR-013.
- **re-verification 2026-06-15 (perplexity-computer):** `docs/agent/AGENT_CONTRACT_AND_TEAM.md` still not present — the consolidation has not landed. `foundations/GLOSSARY.md` still present. `docs/agents/` has grown to include per-agent nests (`devin-roaming-2987d222/`, `perplexity-computer/`) — this is a parallel substrate that partially relieves the fragmentation by giving each agent a stable identity path, but does not consolidate the original `feedback_*.md` fragmentation. Status PARTIAL unchanged.

### BR-014 — `BHED_GNAN` always passes
- **first_observed:** 2026-05-07
- **last_verified:** 2026-06-15 (re-verified by perplexity-computer)
- **age_days:** 39
- **severity:** DEGRADED
- **domain:** runtime
- **root_cause:** `dharma_swarm/telos_gates.py:512-513` literal hard-pass. The Gnani check defined to be most central is structurally inert.
- **blast_radius:** Recognition layer's hardest gate is a no-op. Witness emits but doesn't gate.
- **evidence:** vision_maps `01_gnani_prakruti.md`; `telos_gates.py:512-513`.
- **status:** OPEN — direct edits to `telos_gates.py` are governance-forbidden by `CLAUDE.md`; closure must go through `GateRegistry.propose()` / gate pressure policy rather than a hard-coded gate mutation.
- **re-verification 2026-06-15 (perplexity-computer):** literal hard-pass still in place per direct read. Closure path unchanged (must route through GateRegistry per governance). Status OPEN unchanged.
- **re-verification 2026-07-03:** hard-pass confirmed still present; the code moved — now at `dharma_swarm/telos_gates.py:538-539` (`results["BHED_GNAN"] = (GateResult.PASS, ...)` under the `(always passes)` comment). Earlier `:512-513` citations in this row are the pre-drift line numbers.

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

Next id: `BR-024`. Append below. Do NOT renumber existing items. (Reservation
was stale at `BR-020` while BR-021/022 existed; corrected 2026-07-03 when
BR-023 was filed.)

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
