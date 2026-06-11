# MASTER (INTEGRATION) — Anatomy & Altitude
**Date:** 2026-06-10
**Location:** `dharma_swarm/docs/vision_maps/MASTER_2026-06-10_anatomy_altitude_integration.md`
**Mode:** Read-only integration of six lane reports at `reports/anatomy_altitude_2026-06-10/lane_{A..F}_*.md`. No plans executed. No new code. Grades RUNS / WIRED-BUT-DORMANT / ASPIRATION; clean negatives first-class; file:line or URL on every entry, per the discipline of `MASTER_2026-05-07_attractor_closure_synthesis.md`.

**Provenance:** Lane A (economic engine), Lane B (truth fabric), Lane C (governed self-evolution), Lane D (spine & canon dock-map), Lane E (organism & vision anatomy), Lane F (world triangulation). All six read end-to-end. Sibling map: `MASTER_2026-06-10_leverage_synthesis.md` (same morning, 33-agent verified) — where the two disagree, the lane evidence here is newer for the surfaces the lanes touched.

---

## 0. Ten plain-language lines for the operator

1. The organism's skeleton is real in exactly one place: every action now carries an identity tag (ExecutionIdentity) written to a live database — 1,570 rows, last write today — and that one vertebra genuinely runs through 14+ organs. Everything else called "spine" is either dormant code waiting for a switch, or a document.
2. The system's diary lies in three known ways: it records evolutions as "applied" that never happened, writes "all gates passed" when gates weren't checked, and on main it can report a model "said nothing" when the model spoke. All three are small, located fixes.
3. The self-evolution engine — the part canon now calls the five-alarm fire — has every organ built, but spread across five unmerged worktrees; the distance to one real, conscience-gated self-change is reconciliation plus about ten lines, not new construction.
4. The money engine runs (real bounty PRs, fresh scans daily) but has earned $0 lifetime, and it operates entirely outside the system's own governance — no track, no cell entry, its conscience-gates never imported.
5. Where this is world-class: the honesty culture. It measured that its own swarm loses to its best single agent (−0.10) and recorded it. No comparable system (Polsia's 4.4× claims gap is documented) records its own failures like this.
6. Where this is world-class (second): the empty seat it is closest to occupying — no surveyed self-improving system on Earth ships a meaning-level conscience gate over self-modification; one classifier (WS4b) stands between this codebase and credibly holding that seat.
7. Where it is not world-class: contact. Of the ~11 audited outward organs, most have real code that is dormant and unattached to governance (only 2 are literally codeless) — but none has an external user, and there is no customer, billing, or funnel surface anywhere [corrected 2026-06-10 post-verification: original overstated as 'ten of twelve have no code at all']; the canonical metric — one human outside the house measurably better off — reads zero.
8. First move: make the running daemon provably run the code you audit (it currently imports a third, un-audited worktree), and apply the ~10-line fix that makes the evolution diary honest — real lineage, real status.
9. Second move: wire the one missing call that makes dispatch receipts durable, and land the already-written provider-honesty fix so the system stops silently dropping model output.
10. Third move: bring the money work inside the body — resolve the conflicted track file, open a revenue track, register cashclaw as a cell, set the one missing token — then point the receipt spine at the first earned dollar so revenue is born attested.

---

## 1. THE ANATOMY CHART

### 1.1 How many spines? The true number, as evidence shows it

Canon does not declare one spine. It declares **five distinct referents named "spine"** (Lane E §1.1), and within the first of them, **six generations** exist on disk of which one is canonical (Lane B Tension 1). Forcing these into one object would itself be a narration error. The chart:

| # | Spine | Declared at | Code reality | Grade |
|---|---|---|---|---|
| S1 | **Runtime Truth Spine** (dispatch + receipts) | closed track `runtime-truth-spine-2026-06` "one invariant, one invocation path, one receipt"; package `dharma_swarm/spine/` (8 modules, ~900 LOC; doctrine `spine/__init__.py:5-29`) | Six generations: G1 command-spine (`operator_core/command_spine.py`, 587L, never merged), G2 `SWARM_SUBSTRATE.md` (833L, never merged), G3 v1 (uncommitted in worktree), G4 v2 ledger (**merged** — `runtime_state.py:211/234/252`), G5 `dharma_swarm/spine/` on main (**canonical**), G6 honest-spine-v2 (Jun 10 WIP, uncommitted). Identity layer RUNS; dispatch layer dormant (`orchestrator.py:2286` flag-off; `a2a_bridge.py:78` 0 callers; `spine/persistence.py:50` 0 callers, 0/3,495 `delegation_runs.receipt_json`) | **Split grade: identity RUNS / dispatch WIRED-BUT-DORMANT** |
| S2 | **8-surface organ-attachment rubric** | `2026-05-07_attractor_closure/06_outward_organs.md:30` (kernel, gates, witness, ontology, VSM, identity TCS, stigmergy, signal bus) | Audit rubric only; "0 organs with full 8-surface attachment" (`06_outward_organs.md:47`); attachment doctrine migrating to S1 without re-audit (D1) | RUNS as rubric; 0 organs attached |
| S3 | **Economic Spine** | wiki `concepts/economic-spine.md:1-15`; `economic_spine.py` + `economic_engine.py`; ledger `dharma_swarm/revenue/spine.py` (RevenueSpine) | Code + tests exist; $0 lifetime revenue live-verified (Lane A §0); cell portfolio shows zero live cash | WIRED-BUT-DORMANT economically |
| S4 | **Contemplative safety spine** | `ARJUNA.md:26` — "the spine that keeps the weapon from being a weapon for the wrong things" (kernel axioms, telos gates, witness, viveka) | RUNS degraded: all 11 gates keyword/substring (`telos_gates.py:250-262`), BHED_GNAN literal hard-pass (`telos_gates.py:538-539`, BR-014), witness explicitly non-blocking (`witness.py:1-16`) | RUNS, degraded |
| S5 | **Three spine objectives** (governance portfolio) | `docs/governance/ACTIVE_TRACK.yaml` v2 (live:56-68): `substrate-nativeness` / `revenue-external-humans-served` / `research-depth` | Schema RUNS (PR #555 merged); 2 of 3 objectives have **no active track** — declared in the render itself (SOVEREIGN_MANIFEST.md:26-27) | RUNS as schema; coverage 1/3 |

**The one live vertebra across all five:** `ExecutionIdentity` (`spine/identity.py:28-172`) — the only artifact shared by all six S1 generations and the only one with production writes today (`execution_identities`: 1,570 rows, latest 2026-06-10 13:44 UTC; Lane B §Headline). Adopted by 14+ production modules (`message_bus.py:31-32`, `task_board.py:18-22`, `ontology.py:42-43`, `diff_applier.py:20-21`, `tool_registry.py:27-28`, `artifact_store.py:15-16`, `opportunity_dispatcher.py:36`, `a2a/a2a_server.py:38`, `a2a/nats_transport.py:28`, …; Lane D §2.5).

### 1.2 Organs — declared vs. audited

**Declared:** 12 Krishna self-organs + 12 Arjuna venture-cell organs (`foundations/THE_ORGANISM.md:49,52`, canonical 2026-06-06). Identity sentence: "self-evolving emergent organism (Krishna); outward action (Arjuna) … only valid when rooted in inward coherence" (`THE_ORGANISM.md:8`).

**Code reality (Lane E §1.2):** roughly **2 of 12 Arjuna organs have any audited code surface** — clean negative. Krishna self-organ grades: self-onboarding RUNS (`make onboard`); self-governance RUNS degraded (keyword gates; PDP/PEP only in unmerged PR #558); self-memory-curation RUNS degraded (346,076 flat witness files, launchd exit 124); self-observability WIRED-BUT-DORMANT (S1 dispatch); self-eval WIRED-BUT-DORMANT (Forge `swarm_lift = −0.10`, honest negative); self-treasury ASPIRATION ($0; 29/32 crons disabled since Jun 7 credit exhaustion); self-ontology-maintenance WIRED-BUT-DORMANT (0 ontology receipts ever); self-model-training ASPIRATION (no code surface — clean negative).

**Audited outward organs** (06_outward_organs 2026-05-07, updated by Jun-10 evidence): Loomwork ASPIRATION (dir does not exist); wiki_loom WIRED-BUT-DORMANT; insight_brief RUNS-as-of-May-7 (cron arrest caveat); Ginko WIRED-BUT-DORMANT (revenue_usd current=0, `ontology.py:2219`); Opportunity Loop RUNS forward-only; jagat_kalyan ASPIRATION (zero importers); planetary pulses WIRED-BUT-FAILING (ANTHROPIC_API_KEY error); GAIA WIRED-BUT-DORMANT; welfare_ton_mrv ASPIRATION (`__pycache__` only); Darshan ASPIRATION on main (13 modules in unmerged commit); **CashClaw RUNS off-main** — and it is the tree the daemon actually imports (D8).

### 1.3 Surfaces — the 16 canonical load-bearing surfaces

Per `MASTER_2026-05-07_attractor_closure_synthesis.md:128-149`, re-graded by Lane E §1.3: Kernel RUNS · Gates RUNS-degraded · Corpus/Policy RUNS · Ontology RUNS-as-schema/PARTIAL (2 diverging ontology.db, 100MB vs 14.7MB) · Ontology Gateway RUNS-where-used · Runtime State RUNS (but 4 runtime.db instances, one with an active writer at a wrong path) · VSM RUNS-partial · Heartbeat/Gnani-HOLD RUNS · **Recognition Seed RUNS-permanently-false** (hardcoded dead COLM deadlines) · Stigmergy RUNS · Shakti RUNS · **Darwin RUNS-vacuously** (0% lineage, status hardcoded "applied" `evolution.py:1768`, shadow strips diffs `:3200`) · Witness RUNS-retrospective (non-blocking) · Cascade RUNS · Catalytic Graph WIRED-BUT-DORMANT · Outward Organs per §1.2.

### 1.4 Discrepancies flagged (canon vs. canon, and canon vs. code)

| ID | Discrepancy | Evidence |
|---|---|---|
| D1 | "Spine" = 5 referents, no reconciling doc; organ doctrine audits against S2 while engineering migrates to S1 | Lane E §2 D1 |
| D2 | ARJUNA 05-07 lock's "overrides any prior framing" sentence never struck after the 06-06 Krishna Inversion demoted it to the outward limb | `ARJUNA.md:4` vs `:153`; `THE_ORGANISM.md:4` |
| D3 | Three incompatible organ vocabularies; THE_ORGANISM's 12 Arjuna organs overlap the 12 audited organs on ~2 items | Lane E D3 |
| D-FORK | **Governance fork is live and physical**: origin/main runs ACTIVE_TRACK v2 (multi-track); `~/dharma_swarm` (qwen/spine-adoption) ran v1 with a spine-adoption track main never opened, and its CLAUDE.md carried unresolved `<<<<<<< HEAD` markers in the rendered track block at survey time | Lane D §1.3. *Note: the CLAUDE.md rendered for this session shows 3 active tracks including `runtime-truth-spine-adoption-2026-06` (ported 2026-06-10 into v2) — the fork appears mid-resolution; verify `git status` before track work* |
| D-DEPLOY | **The deploy split (D8): the anatomy that runs is none of the anatomies audited** — the live daemon's editable install maps `dharma_swarm` → `~/dharma_swarm_cashclaw` (5 behind origin/main) | `MASTER_2026-06-10_leverage_synthesis.md:18-19,:70`; Lane E D8. Qualifies every RUNS grade in this document |
| D5 | GNANI_LODESTONE declares "wired into boot" (`GNANI_LODESTONE.md:151`); verified never-seeded — TypeError swallowed at `gnani_lodestone.py:455,465,494,544,587`, root cause `ConceptGraph(telos_dir=...)` vs `graph_nexus.py:117` signature; flag-file existence reads green in `swarm_health_api.py:74`, `guardian_crew.py:351` | CONTRADICTED |
| D6 | Witness doctrine ("upstream, before capability") vs code ("does not block operations") — declared-and-unclosed, not hidden | `GNANI_LODESTONE.md:43` vs `witness.py:1-16` |
| D7 | Substrate-nativeness numbers are two different spines: "~10–15%" still printed in `~/dharma_swarm/CLAUDE.md` and `SOVEREIGN_MANIFEST.md:11` vs 81.2% (runtime-spine definition, 2026-06-09) / 93.8 (16-surface static metric) | Lane B Axis 4; Lane E D7 |
| D9-D11 | diversity_archive asserted canonical, archive file absent / metabolic clock arrested (29/32 crons) / `mutations.jsonl` declared, absent on disk | Lane E D9–D11 |
| D-NARR | The archive narrates: `status="applied"` literal (`evolution.py:1768`), `gates_passed=["ALL"]` for any non-BLOCK (`:1769-1773`) — narration-outruns-build encoded in the data model | Lane C A5 |

---

## 2. PER-CLUSTER FIVE-AXIS MAPS

### 2.1 Cluster — ECONOMIC ENGINE (Lane A)

**Headline:** $0 lifetime, live-verified (all 6 bounty PRs OPEN/unmerged via `gh pr view` 2026-06-10). Three horizons exist as three disconnected organs sharing only a worldview.

- **a. Working-code docks:** hermes scheduler runs 5 live cashclaw jobs (`~/.hermes/cron/jobs.json`, all `last_status: ok`); scan fresh 06-10 (`~/.cashclaw/latest_scan.json`); claim tracker writes live PR state to `~/.cashclaw/evolution.db`; Hydra 21/21 tests (branch `cashclaw/revenue-hydra-v1`, 8 ahead of main); capital_lab 33/33 tests (`~/dharma_capital_lab`, 127 ahead, NOT on main — `git ls-tree origin/main` empty); main's `dharma_swarm/revenue/` scout cron registered (`cron_runner.py:183,:876-877`) but **256 cycles / 233 failed "GITHUB_TOKEN not set"** (`~/.dharma/revenue_scout/cycle_log.jsonl`).
- **b. Vision docks:** ARJUNA contact metric ("one human outside this house measurably better off", `ARJUNA.md:139`) — current score = merged-PR count = **zero**. Clean negative: ARJUNA.md contains no "revenue/fund/money/trading" (grep verified). Portfolio One Law (`VENTURE_CELL_PORTFOLIO.yaml:14`); **cashclaw has no cell entry**; `revenue-external-humans-served` objective has **no active track**.
- **c. Anatomy test:** Hydra gate is real and layered (dry_run at `cashclaw_revenue_hydra.py:176`; lease preflight `:488-593`; killshot `:1455-1532`; exact approval phrase `:1655`, never granted). Claim-and-do `--push-token` is **dead code** — parsed `cashclaw_claim_and_do.py:380`, never read; the gate holds positionally (no push code exists). Telos/witness docking: **clean negative — zero imports** of telos_gates/dharma_kernel/witness in any cashclaw or capital_lab surface; cashclaw runs its own parallel Darwin (`cashclaw_evolution.py`, separate from `~/.dharma/evolution/archive.jsonl`).
- **d. Ecosystem position:** stigmergy + signal bus genuinely docked (`scout_daemon.py:352-388`). Otherwise outside the organism's nervous system. capital_lab's own honesty is exemplary: `LIVE_READINESS = 0` hardcoded (`broker_paper_membrane.py:24-27`); "No market data. No validated strategy. No real broker. No capital." (`ROADMAP_TO_PARITY.md`).
- **e. Inventory:** scanner v2 RUNS · claim-and-do RUNS (6 live PRs) · push-token enforcement ASPIRATION · Hydra RUNS-dry-run / external arm WIRED-BUT-DORMANT-by-design · scout daemon RUNS-ON-EMPTY · intelligence.py RUNS-low-signal · campaign-xray HELD (28/100, $0) · capital_lab fixture library RUNS / alpha_evidence WIRED-BUT-DORMANT (41/100, 25 blockers) / live trading ASPIRATION-by-design · grants/Mercor bets ASPIRATION (listed, no artifacts) · **lifetime revenue $0**.

### 2.2 Cluster — TRUTH FABRIC (Lane B)

**Headline:** two systems wearing one name; one alive. Identity/ledger layer RUNS (1,570 identities + 583 `runtime_receipts`, 6 organ writers: `runtime_lifecycle.py:265,347,454`, `message_bus.py:850`, `task_board.py:271`, `artifact_store.py:155`, `a2a/a2a_server.py:370`, `a2a/nats_transport.py:164-282`). Dispatch-evidence layer WIRED-BUT-DORMANT.

- **a. Working-code docks:** `ExecutionIdentity` RUNS (writes today); `record_receipt_for_identity` (`runtime_state.py:2398`) RUNS; adapters over 10 carrier shapes (`spine/adapters.py:155+`) RUNS; `runtime_truth.py` read-only projector RUNS; `spine_bypass_report.py` executed live — 7 `.submit()` sites: 1 spine-adopted, 5 allowlisted bypasses, warning-only; `RuntimeTruthPacket` contract (`operator_core/contracts.py:125`) + `render_runtime_truth` (`agent_onboard.py:614`) RUNS.
- **b. Vision docks:** "the one blessed agent invocation path" (`spine/invoke.py:2,44-48`) — at PR A, flag-off; "OTel is an EXPORT ADAPTER… the receipt itself is the canonical record" (`receipt.py:4-6`) — a canonical record never durably recorded; SWARM_SUBSTRATE's strongest clause "Completion requires at least one receipt" (`SWARM_SUBSTRATE.md:499`) — enforced nowhere (`orchestrator.py:2333-2337`).
- **c. Anatomy test:** clean negative re-verified: `delegation_runs.receipt_json` = **0/3,495**; `persist_receipt` (`spine/persistence.py:50-57`) zero production callers; WS3 EvidenceReceipt lives only in `self._last_evidence_receipt` (`orchestrator.py:2232`), consumed only by tests. `DHARMA_SPINE_DISPATCH` set in no persistent surface (zshrc/cron/launchd/Makefile clean). `submit_via_spine` (`a2a_bridge.py:78-207`) 0 callers. GATE 1's Jun-9 verification rows landed in the *runtime ledger* while the EvidenceReceipt died in process memory. `delegation_runs.trace_id` populated 110/3,495 (3.1%); 58% of all delegation runs ever are `failed`.
- **d. Ecosystem position:** owned by two ACTIVE tracks (reconciliation @operator, NATS @codex) with surface separation as the safety boundary. Provider honesty: **8 of ~11 provider classes silently convert reasoning-only responses to ""** on main (`providers.py:1363,1437,1511,1585,1659,1733,1800` + `:556` + `providers_extended.py:86,152,213`); G6 WIP fixes 7, uncommitted. Stale "~10–15%" line sits in the fabric's own onboarding doc (D7).
- **e. Inventory:** identity+ledger RUNS · adapters RUNS · projector RUNS · bypass accounting RUNS-warning-only · BoardStore RUNS (not load-tested) · InterruptGate fail-closed RUNS · WS3 dispatch WIRED-BUT-DORMANT · submit_via_spine WIRED-BUT-DORMANT · persist_receipt ASPIRATION · idempotency_records ASPIRATION-at-runtime (0 rows) · provider honesty ASPIRATION-on-main · receipt-completion mandate ASPIRATION · G1 command spine + G2 spec doc orphaned.

### 2.3 Cluster — GOVERNED SELF-EVOLUTION (Lane C)

**Headline:** every organ exists and most RUN — across five unmerged worktrees. Live main records evolution it does not perform. "The distance to one real governed self-change is a *reconciliation*, not a build."

- **a. Working-code docks (per axis A1–A5):** A1 propose RUNS, lineage severed twice (`dgm_loop.py:387-393` parent_id never passed → dead child-detection `:404-411`; `evolution.py:3196-3200` strips diffs pre-archive) → archive ground truth: **11,203 entries, parent_id on 0, real diffs 116 (1.04%), 2,624 falsely "applied"**. A2 gate RUNS advisory-shaped (only BLOCK→REJECTED `evolution.py:1460-1466`; REVIEW flows to apply `:1467-1468`); WS4a (PR #558, `~/ds_ws4` `evolution.py:1530-1543`) blocks REVIEW self-mods with witnessed receipt — operator-gated. A3 apply-time PEP: **the crown jewel sits unmerged in repair_pr323** — `PROTECTED_EVOLUTION_DIFF_TARGETS` (`evolution.py:200-205`) + "non-shadow apply requires ALLOW" (`:2431-2442`) — complementary to WS4a (decision-time vs apply-time). diff_applier split-brain: main has tollbooth receipts but no path-escape guard; repair has `_resolve_target` (`:183-203`) but no receipts; ~30-line merge. A4 verification: `verify_before_done` RUNS in opus_identity worktree (`agent_memory_manager.py:898-1030`, wired at `agent_runner.py:1828,:2987`); `prod_preflight.py` (214L) + readiness tiers m0–m5 (m3–m5 hardcoded False with named blockers) WIRED-BUT-DORMANT; swarm_integrity_benchmark tautological-by-construction (`:285-300` echoes fixture labels, admits it at `:257`). A5 evidence: full 1,000-line `recursive_discovery.py` (governed_recursive_proof) machine-enforces no-autonomous-promotion — `validate_minimum_receipt_chain()` (`:303-325`) **fails any chain containing `promote_to_pr`**; 6-receipt chain; sealed-packet bridge (`:725-829`); foundry writes real parent_id lineage (`:608,:639`) but only to a sandbox archive with synthetic patches. Main carries only a 329-line read-only subset.
- **b. Vision docks:** Krishna Inversion makes this the declared five-alarm fire ("the organism's primary function failing", `ARJUNA.md:165`); THE_ORGANISM Krishna·Mechanisms (DGM loop, AlphaEvolve-style evolution, verifier-gated synthesis, `THE_ORGANISM.md:37-44`) — all ASPIRATION; the disease they would cure is verified current. ADR-0002 (repair_pr323, exists nowhere else): "enforcement tightens only where the runtime contract is proven" — the promotion template.
- **c. Anatomy test:** clean negatives — holon worktree has NO code (docs self-declare "no implementation yet"); the parent_id drop is fixed in **no** worktree examined; recursive CLI / control_surface_recursive / prod_preflight / readiness tiers / ontology mirror / CI workflow: none on main (checked file-by-file).
- **d. Ecosystem position:** works inside the highest-risk debt zone (6-module circular evolution cycle, SOVEREIGN_MANIFEST A7 `:137-143`); BR-003 live-apply env-locked by design; BR-014 BHED_GNAN hard-pass; gate growth must route `GateRegistry.propose/approve` (`telos_gates.py:116-166`); WS4b semantic classifier still missing — ALLOW path keyword-evadable, tripwired in `tests/test_telos_self_mod_enforcement.py`; WS5 live self-mod HARD-BLOCKED until it lands.
- **e. Inventory:** gate_check RUNS-advisory · WS4a RUNS-in-worktree · apply-PEP WIRED-BUT-DORMANT · path-escape guard WIRED-BUT-DORMANT · DGM propose RUNS-lineage-severed · archive write RUNS-mislabels · shadow diff retention BROKEN-BY-DESIGN · receipt subset RUNS-inert · full receipt chain WIRED-BUT-DORMANT · foundry RUNS-synthetic · integrity benchmark RUNS-as-plumbing/ASPIRATION-as-eval · prod_preflight WIRED-BUT-DORMANT · verify_before_done RUNS-in-worktree · holons ASPIRATION.

---

## 3. CROSS-CLUSTER DEPENDENCY GRAPH

Where the three clusters need each other — every edge cites the dock that already exists:

```
                    ┌─────────────────────────────┐
                    │  SPINE (ExecutionIdentity)   │  the one live vertebra
                    │  spine/identity.py:28-172    │  1,570 rows, writes today
                    └──────┬───────────┬──────────┘
              identity     │           │     identity + tollbooth
        ┌──────────────────┘           └──────────────────┐
        ▼                                                  ▼
  TRUTH FABRIC ◄──────────── needs ────────────── SELF-EVOLUTION
  (receipts, ledger,         honest archive       (propose/gate/apply)
   provider honesty)         + self-mod receipts
        ▲                                                  ▲
        │ needs receipts to                  needs budget/ │
        │ prove revenue                      selection     │
        │ (EV-1, EV-3)                       pressure      │
        ▼                                                  ▼
  ECONOMIC ENGINE ◄────── credit exhaustion arrests ──────┘
  (cashclaw, capital_lab,    the metabolism (29/32 crons off)
   revenue/ on main)
```

1. **Economic → Truth:** revenue cannot be *proven* without the receipt spine. The named open slot already exists: `EvidenceReceipt.input_tokens/output_tokens/cost_usd` (`spine/receipt.py:66-69`) with "Future work: wire cost_tracker.py into the receipt" (`a2a_bridge.py:89-92`). The Polsia exceed-vector (receipted revenue, Lane F EV-1) is exactly this edge. Today's clean negative: zero economic component imports any truth/gate surface (Lane A §3b).
2. **Self-Evolution → Truth:** a self-change is governed only if it is *evidenced*. The sink exists on main (`runtime_state.py:2605 record_self_mod_receipt`); the chain validator exists unmerged (`recursive_discovery.py:303-325`); the archive currently testifies falsely (`evolution.py:1768-1773`). Until the archive is honest, the evolution cluster cannot verify its own claims — and per Sakana's marker-removal incident, **lineage is the safety system**, so the broken parent_id chain is a safety gap (Lane F 3a).
3. **Truth → Self-Evolution:** provider honesty gates the evaluator. An evolution loop scoring agent output cannot hill-climb while 8 provider classes can return "" for a model that spoke (`providers.py:1363-1800`). The Forge's honest −0.10 is only as trustworthy as the extraction path beneath it.
4. **Economic → Self-Evolution:** the metabolism funds the evolution. Credit exhaustion disabled 29/32 cron jobs Jun 7 (`MASTER_2026-06-10_leverage_synthesis.md:87`) — the economic failure literally arrested the metabolic clock. Conversely, selection pressure with stakes (Numerai vector, Lane F EV-5) requires an economic primitive (stake/burn) that is a clean negative today.
5. **Self-Evolution → Economic:** cashclaw runs its own parallel Darwin (`cashclaw_evolution.py`, separate archive) — two evolution systems, no shared archive (Lane A §3b). Reconciling them is how bounty-loop fitness becomes organism fitness.
6. **Everything → Spine:** all three clusters already carry ExecutionIdentity where they touch main (`opportunity_dispatcher.py:36`, `diff_applier.py:20-21`, `a2a/*`); none yet flows through `invoke_agent` (PR A, flag-off). The spine is the only surface on which "one organism" is currently true rather than declared.
7. **Everything → Governance (S5):** the portfolio covers only `substrate-nativeness`. Cluster 1 serves an objective with no track; Cluster 2 (the operator-declared first priority) is not a spine objective at all. **The declared anatomy ranks Krishna first, contact second, substrate third-as-precondition — the governance portfolio currently covers only the third** (Lane E §3, the inversion-of-the-inversion).
8. **Everything → Deploy truth (D-DEPLOY):** no edge above is causally verified until the daemon provably runs known-current code (3-lens unanimous Rank 1, `MASTER_2026-06-10_leverage_synthesis.md:100-103`).

---

## 4. INCUMBENT TABLE

Capture / miss / exceed per comparable (Lane F, condensed; every external claim carries its URL there):

| Comparable | Their load-bearing mechanism | dharma_swarm CAPTURED | dharma_swarm MISSED | EXCEED vector (horizon) |
|---|---|---|---|---|
| **Cofounder** (cofounder.co) | Org-chart agent departments; exception-based human approval; MCP extensibility | Deeper orchestration (370 modules; blessed path `spine/invoke.py:36`, WIRED-BUT-DORMANT); stricter typed gating (`telos_gates.py:116` GateRegistry) RUNS | The entire outward-facing half: no customer/billing/funnel surface anywhere (clean negative, dir-verified); no go-to-market state machine | Auditable business-runner: every economic action emits an EvidenceReceipt (`receipt.py:36-80`) — structurally impossible for vibes-based approval (scrappy) |
| **Polsia** (polsia.com; zilla.so/blog/polsia-review) | 9 agents end-to-end on $49/mo + 20% rev-share; ~$10M ARR claimed; **documented 4.4× claims-to-reality gap** | Honest-measurement culture (Forge recorded `swarm_lift = −0.10` rather than burying it) | Distribution, pricing, retention — everything that turns agents into ARR (clean negative) | **Receipted revenue / "honest ARR" as a category** — incumbents cannot follow without exposing their gap (scrappy→mid-game, EV-1) |
| **Numerai** (docs.numer.ai) | Stake-and-burn: weight ∝ skin-in-the-game; $500M JPMorgan allocation | Fitness-scored agent population (archive 11k+ entries) — WIRED-BUT-DORMANT, 4 wiring breaks | **The stake**: no staking/burn/slashing primitive in the tree (clean negative) | Staked agent *actions* (not just predictions) settled by the gate, burns witnessed — Dharmic Agora shape (mid-game, EV-5) |
| **Agentic funds 2026** (arxiv.org/abs/2605.19337; digiqt.com) | Hierarchical veto (risk above alpha); regulator-mandated Traceable Decision Chains | Gate-above-generator built from conviction (`evolution.py:1460`); `to_otel_span()` (`receipt.py:80`) emits what regulators mandate | Capital, market connectivity, backtests, PIT data hygiene — entire execution substrate (clean negative) | Post-settlement *published* witnessed decision chains — funds can't disclose (alpha decay) (strategic, EV-8; prereq: any revenue) |
| **Palantir Foundry/AIP** (palantir.com/docs/foundry/action-types/overview) | Actions-as-the-only-write-path; writeback datasets; LLM sandboxed inside typed action space | Palantir-shaped ontology layer (`ontology.py:287,319,331,381,387`) — RUNS as schema, ~10–15% runtime-native | **Writeback**: runtime mutates state directly, ontology observes after the fact; no per-object dynamic security (clean negative) | **Self-governing ontology**: schema evolves only through its own witnessed gate — `GateRegistry.propose` already proved gate-governed gate-evolution (PR #558); Foundry's ontology is human-admin config (mid-game, EV-4) |
| **SLSA / in-toto / Sigstore-Rekor** (slsa.dev; docs.sigstore.dev/logging/overview) | Signed attestations + append-only public transparency log | Receipt-as-attestation shape present (`receipt.py:36-80`, subject+predicate+lineage, OTel) RUNS-at-chokepoint; witness culture RUNS (`~/.dharma/witness/`) | **Crypto signing + append-only structure**: receipts are mutable plain files — "a receipt you can silently edit is a diary, not an attestation" (clean negative) | **Attested cognition / SLSA-for-decisions**: hash-chain → keyless signing → public gate-decision log; incumbents attest artifacts, not judgment (scrappy→strategic, EV-3) |
| **Sakana DGM** (sakana.ai/dgm; arxiv.org/abs/2505.22954) | Archive + diverse parent sampling + empirical eval; safety = sandbox + **transparent lineage** (caught the marker-removal sabotage) | Direct DGM-lineage implementation (`dgm_loop.py:35,:81`); live self-mod HARD-BLOCKED behind gate+operator — stricter than DGM's one-off supervision | Working empirical loop: 0% lineage (parent_id dropped `dgm_loop.py:387`), gauntlet evaluates empty diffs — a *safety* gap by DGM's own lesson | **Pre-application meaning-level gate** — the layer DGM's incident proves missing; WS4b classifier is the gate to the whole row (strategic, EV-7) |
| **AlphaEvolve** (deepmind.google/blog/alphaevolve) | Prompt sampler + LLM ensemble + automated evaluator + program DB; power = machine-checkable score | Component map exists; measurement runner RUNS with honest negative (`swarm_lift = −0.10`) | Closed selection loop: Forge→evolution open BY DESIGN; no breadth/depth ensemble policy (clean negative) | **Two-axis evolution**: fitness evaluator + conscience gate with witnessed veto — structurally anti-Goodhart; compass prototype staged-uncommitted (`_apply_compass_pull`, branch `trust-build-compass`) (mid-game→strategic, EV-6) |
| **SWE-agent / SICA / Live-SWE** (arxiv.org/abs/2405.15793; arxiv.org/pdf/2511.13646) | Agent-Computer Interface; constrained-change-surface + tests-pass-before-adoption | ACI at fleet level (typed invoke_agent + receipt) WIRED-BUT-DORMANT; SICA-discipline stronger at proposal layer (PR #558, 117 tests) | Mid-run self-adaptation; external scoreboard (no SWE-bench-style validity) (clean negatives) | Run one SICA-style self-edit through gate+receipt+adversarial-eval and **publish the trace** — the literature recommends and never ships this (scrappy, EV-2) |
| **Field state 2025–26** (arxiv.org/pdf/2507.21046; arxiv.org/html/2602.17753v1) | Governance = sandboxes, allowlists, human review; **nobody ships a semantic policy layer for self-mod** | Attempting precisely the unshipped layer (PDP/PEP + typed gates + classifier) | WS4b classifier — the single blocking item | The seat is genuinely unoccupied (Lane F clean negative #7) (strategic) |

---

## 5. TOP 7 MOVES

Ranked by anatomy-leverage × smallest-diff. Each extends an existing surface (no new substrate, per Lane D §4), names files, names the verifier, and names the incumbent gap it closes.

| # | Move | Tag | Existing surface extended | Files touched | Verifier (green = done) | Incumbent gap closed |
|---|---|---|---|---|---|---|
| 1 | **Deploy truth: make the daemon run known-current code.** Re-point the editable install from `~/dharma_swarm_cashclaw` to the audited tree (or merge that tree); record the resolution. | scrappy | Existing daemon install + worktree estate (D-DEPLOY) | the daemon's editable-install mapping; `~/dharma_swarm_cashclaw` branch disposition | `pip show`/`python -c "import dharma_swarm; print(dharma_swarm.__file__)"` from the daemon's env resolves to the audited tree; `dgc status` healthy after restart | None directly — it is the precondition that makes every other RUNS grade causal (3-lens Rank 1, leverage_synthesis:100-103) |
| 2 | **Archive honesty micro-fixes (~10 lines).** Thread `parent_id` from `parent_entry.id` into `auto_evolve`'s proposals; derive `ArchiveEntry.status` from actual apply outcome instead of the `"applied"` literal; record real `gates_passed`; retain `proposal.diff` as `shadow_diff` instead of stripping. | scrappy | DarwinEngine archive write path (Lane C §3.3) | `dgm_loop.py:387-393`; `evolution.py:1768-1773`, `:3196-3200` | One shadow cycle then re-scan `~/.dharma/evolution/archive.jsonl`: new entries carry parent_id, non-"applied"-literal status, retained diff; existing evolution tests green | Sakana DGM — "lineage is the safety system"; closes the 0%-lineage safety gap (Lane F 3a) |
| 3 | **Make the canonical record durable: one call to `persist_receipt`.** Invoke `persist_receipt(receipt, db)` from the WS3 invoker and from `submit_via_spine`. | scrappy | spine persistence sink + existing `delegation_runs.receipt_json` column (Lane B rank-1) | `orchestrator.py:2232` region; `a2a_bridge.py:78-207`; `spine/persistence.py:50` (unchanged, gains callers) | `sqlite3 ~/.dharma/state/runtime.db "SELECT SUM(receipt_json IS NOT NULL) FROM delegation_runs"` > 0 after a flag-on dispatch; `tests/test_orchestrator_spine_dispatch.py` extended to assert the row | SLSA/Sigstore — turns the attestation-shaped receipt from in-memory diary into durable record; prerequisite for EV-1/EV-3 |
| 4 | **Land G6 provider honesty.** Commit honest-spine-v2's provider diff; finish the three unconverted sites in `providers_extended.py`. | scrappy | Existing `_extract_openai_compatible_message_text` extractor (`providers.py:154-163`) routed to all families | `providers.py:1363,1437,1511,1585,1659,1733,1800,:556`; `providers_extended.py:86,152,213`; `tests/test_providers_quality_track.py` | `tests/test_providers_quality_track.py` green incl. "reasoning-only content must never collapse to ''" cases | Closes the only path by which the system actively misreports model output — integrity floor under every evaluator (AlphaEvolve-class loops require honest extraction) |
| 5 | **Close both ends of the self-mod gate.** Operator lands WS4a (PR #558); port repair_pr323's apply-time PEP (PROTECTED_EVOLUTION_DIFF_TARGETS + "non-shadow apply requires ALLOW", ~40 lines); merge the two diff_applier halves (`_resolve_target` + tollbooth receipts, ~30 lines). Dual-audit required (hot-path). | mid-game (strategic successor: WS4b classifier via `GateRegistry.propose`) | gate_check PDP (`evolution.py:1396`) + `run_cycle_with_sandbox` apply junction + diff_applier | `evolution.py:1530-1543` (WS4a), `:200-205`, `:2414-2442` (repair port); `diff_applier.py:183-203` ↔ main's receipt plumbing | `tests/test_telos_self_mod_enforcement.py` (incl. tripwires) + 117-test surface green; adversarial probe: REVIEW self-mod rejected at decision AND a forged non-ALLOW apply rejected at the PEP | Sakana DGM + field-wide: decision-time and apply-time enforcement together are the layer no surveyed self-improving system ships (Lane F 3d); WS4b remains the gate to the full seat |
| 6 | **Bring the economic engine inside the body.** Verify/finish the governance-fork resolution in `~/dharma_swarm/CLAUDE.md` (D-FORK); open an `active_tracks:` node serving `revenue-external-humans-served` (insert after live ACTIVE_TRACK.yaml:238); add a cashclaw cell row to VENTURE_CELL_PORTFOLIO.yaml; set `GITHUB_TOKEN` in the scout cron env; fix `~/.cashclaw/claims.json` leading comma + empty-PK evolution.db row. | scrappy | ACTIVE_TRACK v2 portfolio (1–10 co-equal tracks by design) + existing cell index + existing scout cron (`cron_runner.py:876-877`) | `docs/governance/ACTIVE_TRACK.yaml`; `docs/governance/VENTURE_CELL_PORTFOLIO.yaml`; cron env surface; `~/.cashclaw/claims.json` | `scripts/governance/check_track_status.py` green; `make onboard` renders the revenue track; next scout cycles in `~/.dharma/revenue_scout/cycle_log.jsonl` nonzero; `json.load(claims.json)` parses | Cofounder/Polsia — the only live revenue work stops being structurally homeless; ARJUNA contact metric gets an owner; kills 233/256 scout failures with one env var |
| 7 | **Receipted revenue, first leg of attested cognition.** Set `DHARMA_SPINE_DISPATCH=1` in one persistent surface (daemon env/launchd) after GATE review; point the receipt path at the CashClaw claim/PR events so the first earned dollar carries a receipt chain; add hash-chaining over receipt/witness files (the membrane already demonstrates the pattern: `broker_paper_membrane.py:519-537` hash-chained `parent_receipt_id`). | mid-game | WS3 dispatch chokepoint (`orchestrator.py:2286`) + EvidenceReceipt cost fields (`receipt.py:66-69`) + the named slot "wire cost_tracker.py into the receipt" (`a2a_bridge.py:89-92`) + witness store | env surface for the flag; the cashclaw claim-tracker write path; a small chain-verify script under `scripts/governance/` extending the existing verifiers | A live `runtime_receipts`/`receipt_json` row correlated (same `correlation_id`) with a real bounty-PR event; chain-verify script detects a deliberate tamper in a test fixture | Polsia's 4.4× gap (EV-1: revenue numbers a third party can verify) + first leg of SLSA-for-decisions (EV-3); incumbents structurally cannot follow |

**Not in the seven, explicitly sequenced after:** WS4b semantic classifier (strategic — the field's open seat; gated on move 5), the Numerai stake primitive (EV-5, needs an economic unit of account first), Sigstore keyless signing + public log (EV-3 legs 2–3), the Forge→evolution selection-pressure loop (EV-6, needs moves 2+4 so the evaluator and archive are honest first).

---

## 6. HONEST CONFIDENCE

### 6.1 Graded ASPIRATION (or worse) while docs present it as real

| Doc claim | Reality | Evidence |
|---|---|---|
| GNANI_LODESTONE "Active seed — wired into boot sequence" (`GNANI_LODESTONE.md:151`) | Never seeded anything; TypeError swallowed; green status reads flag-file existence | CONTRADICTED (`gnani_lodestone.py:455-587`; `graph_nexus.py:117`) |
| Archive `status="applied"`, `gates_passed=["ALL"]` | Literal constants regardless of outcome — 2,624 false "applied" rows | `evolution.py:1768-1773` |
| "Completion requires at least one receipt" (`SWARM_SUBSTRATE.md:499`) | Doc never merged; clause enforced nowhere | `orchestrator.py:2333-2337` |
| `spine/persistence.py:8` "writes to the existing canonical store" | Writes to nothing — 0 callers, 0/3,495 | Lane B Tension 2 |
| Recognition seed (system self-model) | "fresh, injected, and permanently false" — hardcoded dead deadlines | leverage_synthesis:47,:89 |
| `--push-token` human gate (cashclaw docstring `cashclaw_claim_and_do.py:20-23`) | Parsed at `:380`, never checked — dead code; gate is positional | Lane A §1c |
| "wired into boot" claims generally + substrate-nativeness "~10–15%" in first-read docs | Two different spine definitions (81.2% runtime-spine vs 93.8 static vs the stale prose number) | D7 |
| THE_ORGANISM's 12 Arjuna organs; Krishna·Mechanisms entries | ~2 of 12 have audited code; Mechanisms all ASPIRATION while the disease is verified current | Lane E §1.2,:119 |
| Sovereign holons | Docs only, self-declared "no implementation yet" | Lane C clean negative #1 |
| `mutations.jsonl`, `diversity_archive.json` declared in CLAUDE.md | Absent on disk / zero importers | D9, D11 |
| Grants / Mercor / expert-network revenue bets | Listed in `~/cashclaw/README.md`, no artifacts | Lane A §4.3 |
| swarm_integrity_benchmark as an integrity eval | Tautological fixture-echo; admits it in its own warnings | `swarm_integrity_benchmark.py:285-300,:257` |

### 6.2 What remains UNKNOWN

- **Whether any bounty platform actually pays.** SecureBananaLabs looks like a demo repo (payouts unproven); xevrion/claude-builders payout behavior untested until a first merge. The entire H1 thesis is unfalsified in both directions.
- **The daemon's actual runtime behavior** under the deploy split — every grade in this document is about audited trees; the running organism imports `~/dharma_swarm_cashclaw` (D-DEPLOY). Until move 1, RUNS means RUNS-in-some-tree.
- **insight_brief and other cron-borne organs' current status** post the Jun-7 cron arrest (29/32 disabled) — last verified good 2026-05-07.
- **Whether `runtime/live` being 2 commits behind origin/main matters** — Lane D judged the missing commits (#542/#543) non-dock-altering, not re-verified here.
- **BoardStore under load; idempotency substrate at runtime** (0 `idempotency_records` rows ever — helpers exist and are tested, never exercised).
- **Cofounder internals** — all architecture inferences SPECULATIVE beyond the landing page (Lane F clean negative #6).
- **The fork-resolution state of `~/dharma_swarm/CLAUDE.md`** — Lane D observed live conflict markers; the file as rendered for this session shows a clean 3-track v2 portfolio including the ported spine-adoption track. The fork appears resolved or mid-resolution between survey and synthesis; verify `git status` + `check_track_status.py` before relying on either snapshot.
- **Whether the honest −0.10 swarm_lift generalizes** — n=3, one task family, System A only.

### 6.3 What this map is not

Per the standing guard (`feedback_narration_outruns_build.md`, bound into ARJUNA Amendment 2026-05-30): this document is itself narration. The next artifact after this one should be a diff — move 1 or move 2.

---

*Lane sources: `reports/anatomy_altitude_2026-06-10/lane_A_economic.md` · `lane_B_truth.md` · `lane_C_evolution.md` · `lane_D_spine_canon.md` · `lane_E_organism_vision.md` · `lane_F_world.md`. External URLs inline in §4 and in Lane F's source list.*
