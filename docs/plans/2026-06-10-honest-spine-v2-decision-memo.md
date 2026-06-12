# Honest Spine v2 — Decision Memo (Subtract, Wire, Measure)

**Date:** 2026-06-10
**Status:** AWAITING OPERATOR APPROVAL — nothing in this memo is built; this document confers no completion claims
**Authors:** Fable 5 (Cursor session), restructured after independent review by GPT-5.5 (adversarial/code) and Grok Build (strategic), grounded by four repo-verification agents and a full Forge Hydra architecture map
**Anti-theater clause:** No agent may cite this memo as evidence of progress. Progress = the receipts named in each phase's DONE line, on disk, verified.

---

## 1. Verdict that produced this memo

Both independent reviewers returned **RESTRUCTURE** on Honest Spine v1. Convergent findings (accepted):

- Git consolidation proves nothing about what *running daemons* execute → Phase 0 must establish **runtime provenance**, not just merge branches.
- "self_improve.py as sole fitness writer" is technically incoherent → enforcement belongs at the **archive boundary** (`EvolutionArchive.add_entry`), and `meta_evolution.py`'s `auto_apply` back-door must be closed.
- "Freeze-flag 15 scaffolds" is narrative subtraction → **delete with revival protocol + sunset**, count bytes removed in the receipt.
- The v0 measurement arms are **protocol-confounded** (different model families/roles per arm), not cost-matched; n=3→30 still underpowered for 0.1 lift without a pilot + power analysis.
- Honesty-infrastructure before measurement is the **correct order** (measuring on a rotten substrate manufactures sophisticated theater).
- This plan itself must run as a **declared parallel lane** under ACTIVE_TRACK rules, with receipts, or it becomes the next narrative artifact.

Operator decisions already made: **instruction-layer cleanup is Phase 0** ; deliverable is this memo before any build.

## 2. Ground truth this memo stands on (verified, file-cited in session)

- Evolution archive: 11,164 records, 0% parent links, 98.96% empty diffs, 0 commit hashes; `status="applied"` written without application.
- Only honest closed loop: `self_improve.py` + `ecc_eval_harness` (ran 2026-06-10, applied, failed tests, rolled back).
- Telos gate is keyword-based; 5/12 adversarial self-mods pass as ALLOW (test on unmerged `governance/ws4-gate-pep`). Live self-mod hard-OFF (`DHARMA_EVOLUTION_SHADOW=1` default).
- Swarm lift: **-0.10** (2026-06-06), n=3, CI [-0.30, 0], degraded swarm arm. Candidate evidence only — but *consistent with literature* (Self-MoA arXiv:2502.00674; MAST arXiv:2503.13657).
- **Forge Hydra ended honestly**: `internal_exhausted_external_gated`, stop policy written instead of fabricated cycles. 3 external GitHub PR merges Guardian-confirmed (cycle-001; cycle-76 reverified 4). Quorum N≥5 receipts / M≥3 domains **unmet** (3 receipts, 1 domain).
- The designed-but-never-built piece is the **5th packet of the Forge Council's own build order**: `dgm-consumes-receipt-wire` (`EvolutionReceipt` type, `FitnessScore.from_external_receipt()`). Most forge runtime scripts absent from current tree.
- `persist_receipt` exists with **zero production callers**; `DHARMA_SPINE_DISPATCH` default OFF; receipt fill rate 0/3495. This is the ACTIVE_TRACK's own unfinished seam.

## 3. The fitness ruling (resolves the reviewer fork + the SWE-bench question)

Three-tier signal hierarchy — **already implied by the system's own canon**, now made explicit:

| Tier | Signal | Role | Can touch `ArchiveEntry.fitness`? |
|---|---|---|---|
| 1 — dense | eval harness, sealed gauntlet, SWE-bench-style scores | training/measurement signal | **Never** (`training_signal_not_fitness_authority`) |
| 2 — sparse | external ACTED receipts (GitHub merges today), transfer-gated, Guardian-countersigned, quorum N≥5/M≥3 | fitness | **Yes — only entrance** |
| 3 — telos | verified welfare/ecological deltas | fitness, as additional *domains* satisfying M≥3 breadth | Yes, same wire as Tier 2 |

- **SWE-bench**: belongs in Tier 1 (measurement lane). The six-agent synthesis (2026-06-05) already ruled public benchmarks contamination-prone as primary signal; DGM's own objective-hacking history confirms. The v3 baseline packet's minimum unit — *one official SWE-bench Verified instance through the official Docker harness* — is `not_run` and becomes a Phase C deliverable.
- **GitHub merges** (Codex position): correct Tier-2 bootstrap — they exist, they're unfakeable.
- **Welfare deltas** (Grok position): not a replacement but the required *domain breadth* — the quorum cannot complete on tooling-PRs alone. First welfare-domain receipt becomes an explicit Phase B+ goal, not a blocker on building the wire.

## 4. Restructured phases

Lane declaration (per ACTIVE_TRACK parallel-lane rule): **owner:** operator (Dhyana) + session agent · **branch:** fresh worktree `honest-spine-v2` off consolidated main · **allowed surfaces:** listed per phase below · **verification:** per-phase DONE lines · **receipt path:** `reports/agentops/work_packets/honest-spine-v2-phase-{0,A,B,C}.json`

### PHASE 0 — Truth at the roots (instruction layer + runtime provenance) — ~2 days
1. **Instruction-layer cleanup** (operator-gated, biggest item): one consolidation pass over `~/dharma_swarm/CLAUDE.md`, `~/CLAUDE.md`, `AGENTS.md` — remove stale/contradictory AI-written accretion, mark every claim either VERIFIED (with source) or ASPIRATION (labeled). The ACTIVE_TRACK block must match `make onboard` reality (currently 0/7 criteria complete).
2. **Runtime provenance**: extend `make onboard` / `dgc status` to report, for each live daemon, the branch+commit it is actually executing; FAIL loudly on mismatch. (Codex's strongest addition — without it every later phase can be "built but not running.")
3. **Git consolidation**: merge `origin/main` (WS2 flock, WS3 spine receipts) into the lane worktree; commit the orphaned `pulse.py` API-key guard.
- **DONE when:** onboard shows runtime provenance per daemon; instruction files carry a dated consolidation receipt; lane worktree green on `make test-smoke`.

### PHASE A — Archive boundary + subtraction — ~2-3 days
1. **Archive boundary enforcement** (replaces v1's "sole writer"): `ArchiveEntry` gains `entry_type ∈ {fitness, observation}` and `fitness_authority ∈ {eval_harness, operator_external_receipt}`. `EvolutionArchive.add_entry` **rejects** `fitness`-type entries lacking non-empty diff + declared authority. All existing writers (DarwinEngine grind, AutoProposer, meta_evolution) demoted to `observation` — not hard errors, so the suite survives.
2. **Close the meta_evolution back-door**: `auto_apply=False` default; meta entries are observations.
3. **Tombstone the epoch**: all 11,164 pre-epoch records flagged `untrusted_epoch=true` in one migration; downstream consumers (`dgc evolve trend`, dashboards, selector) must exclude or label them.
4. **Delete, don't freeze**: dormant scaffolds with zero runtime state (DiversityArchive file-never-created, dream stack, Foreman, Ginko evolution, Cascade code-mutate stub, DGM loop wrapper) get a deletion PR each with a one-line revival protocol ("restore from git tag `pre-spine-v2` if needed") — receipt counts LOC/bytes removed. Anything with ambiguous liveness gets a 30-day sunset note instead.
5. **Receipts ON**: flip `DHARMA_SPINE_DISPATCH` default; wire `persist_receipt` into the dispatch path (this *is* the ACTIVE_TRACK's declared work, not an exception).
6. **Silent-death alerting via existing surfaces** (not a new launchd daemon): a check inside the existing cron/onboard surface that flags any truth-critical loop (self_improve, convergence_forge, receipt stream) silent >24h into the morning-brief/operator-brief row.
- **DONE when:** adversarial test proving a fitness entry without diff+authority is rejected; receipt fill rate >0 and rising; deletion receipt with byte counts; pytest green.

### PHASE B — The One Wire (the Forge Council's own 5th packet) — ~2-3 days
1. Implement `EvolutionReceipt` (schema already specified in AGENTS.md: patch_hash, eval_manifest_hash, score, cost, exit_codes, external_confirmed + stratified fields) and `FitnessScore.from_external_receipt()`.
2. Build `dgm-consumes-receipt-wire`: Guardian-confirmed receipt files → transfer gate → archive boundary → `fitness`-type entry. Quorum logic (N≥5, M≥3) enforced; below quorum the wire runs in **dry-run** and emits `candidate_for_human_review` only.
3. **Replay verification**: the 3 Guardian-confirmed June-1 merges replay through the wire in dry-run → exactly 3 candidate entries, 0 fitness mutations (quorum unmet), 0 without operator flag.
4. Welfare-domain receipt template defined (what would count, who verifies) — opens Tier 3 without blocking on it.
- **DONE when:** replay produces exact expected output; forged-receipt test rejected; archive hash unchanged until quorum + operator lease; live self-mod still OFF.

### PHASE C — The Measurement (redesigned) — ~4-5 days, after A/B
1. **Pilot first** (5 tasks) to validate scorers, arm parity, and cost accounting; then power analysis to set n (expect n≈50-80 for 0.1 lift detection, not 30).
2. **De-confounded arms**: same model family available to every arm; arms differ *only* in protocol (single-shot / self-MoA k-samples / swarm decomposition), matched on dollar cost, wall-time cap, tool access, and context budget.
3. **Decomposition metrics**: per-agent accuracy, pairwise error correlation, **oracle gap** (defined per-task as: does any candidate output in the pool score ≥ the single-arm output under the deterministic scorer).
4. **One official SWE-bench Verified instance** through the official Docker harness — the v3 baseline's declared-but-never-run minimum unit — as the external-comparability anchor.
5. Pre-registered, hashed protocol before first scored run; weekly rerun via existing cron surface; results into one report row the morning brief reads.
- **DONE when:** protocol hash matches; pilot + powered run complete with CIs; decomposition table exists; SWE-bench Verified official result (even one instance, even a failure) recorded.

## 5. Explicitly NOT doing (anti-busywork, reaffirmed)

- No semantic-LLM safety gate work (door is welded shut; structural rails + human gate remain the rail). WS4a merge is allowed as hygiene; WS4b deferred.
- No fixing of evolution plumbing for the 11k legacy records (tombstone, never curate).
- No new daemons, stores, dashboards, read-models, or docs beyond the per-phase receipts and this memo.
- No chetana landfill processing this lane (separate decision; ingestion volume should be capped but that is its own lane).
- No overnight autonomous marathons; every phase boundary is an operator gate.
- No model-roster expansion, no new agent types.

## 6. Decision gates after Phase C (pre-committed)

- **Lift > 0 with CI excluding 0** at matched cost → swarm configuration validated; consider gated Tier-2 evolution with operator lease.
- **Oracle gap large but lift ≤ 0** → aggregation is the bottleneck; one pre-registered aggregation experiment allowed.
- **Oracle gap small and lift ≤ 0** → diversity is not real at current roster; descope swarm to orchestration tool; DarwinEngine stays observation-only indefinitely.
- In all cases: inward-work budget capped (operator sets hours/week); NeurIPS + revenue threads retain priority.

## 7. Confidence (updated)

- Highest-ROI build within dharma_swarm: **~85%** (up from 75% — the Hydra map showed Phase B is the system's own declared next packet, not an invention; and runtime provenance removes the largest unknown).
- Highest-ROI for the operator's whole stack: **~60%** (up from 55% — instruction-layer cleanup at Phase 0 addresses the pathology generator; remainder of uncertainty is genuinely about NeurIPS/revenue opportunity cost, not the plan's content).

---

## 8. Folded lane: debt audit plan (89a993cc) integration

The Cursor plan `~/.cursor/plans/dharma_swarm_debt_audit_89a993cc.plan.md` (10 debt categories, 6 phases) is folded into this build as follows. **Caution discovered 2026-06-10:** that plan marks `phase0`, `providers-fix`, `terminal-bridge-fix` as *completed*, but the current worktree still contains 7 unfixed `msg.content or ""` sites in `providers.py`, no `degraded` key in `terminal_bridge.py`, and no `[tool.ruff]` in `pyproject.toml`. Its statuses are claims without receipts — treat all of them as UNVERIFIED until re-checked in the consolidated lane worktree.

**Fold mapping:**

| Debt plan item | Folds into | Rationale |
|---|---|---|
| Phase 0 (hook fix, ruff/coverage config, baseline) | **Spine Phase 0**, step 4 | Tooling truth = instruction-layer truth; baseline numbers are receipts |
| Re-verify "completed" items (providers content-drop, terminal_bridge guard, async refs, leaks) | **Spine Phase 0**, step 5 | Verify-then-trust; finish in lane if actually unfinished |
| Phase 2 CI safety nets (ruff blocking, except-pass ban, strict markers, coverage diff gate) | **Spine Phase A**, step 7 | These ARE anti-theater enforcement — a Semgrep rule banning silent `except: pass` is the code-level twin of the archive boundary |
| BR-020 3-line fix + register reconciliation (INTERFACE_MISMATCH_MAP, BROKEN_REGISTER) | **Spine Phase A**, step 8 | Same claims-vs-reality reconciliation work |
| Phase 3 (DI singletons, router collapse) | **Deferred — post-Spine lane** | Orthogonal; high churn risk during Spine |
| Phase 4 (god-module splits: evolution.py, orchestrator.py, swarm.py...) | **Deferred — post-Spine lane, HARD ORDERING** | Conflict rule: NO splitting of `evolution.py` / `archive.py` / `orchestrator.py` until Spine A/B lands — Spine edits their boundaries first |
| Phase 5 cleanup (organism_* merge, tui_legacy deprecation) | Merged into **Spine Phase A step 4** deletion sweep where dormant; rest deferred |
| Tooling modernization (uv + lockfile, pyright gating, pip-audit) | **Deferred — post-Spine**, except ruff which rides Phase 0 | Valuable, not truth-critical |

**Net effect:** Spine Phase 0 grows by ~1 day (tooling baseline + re-verification of falsely-completed items); Phase A grows by ~0.5 day (CI safety nets + BR-020). Debt phases 3-5 become the natural *next* lane after Phase C's decision gate, ordered behind it so god-module splits never race the archive-boundary work.

---

**Approval needed from operator:** (1) approve lane declaration, (2) approve Phase 0 scope (now including debt-plan re-verification + tooling baseline), (3) confirm Tier-2 bootstrap-on-GitHub-receipts ruling, (4) set inward-work weekly hour cap.
