# Lane C — Governed Self-Evolution Deep Read
**Date:** 2026-06-10 · **Reader:** Lane C subagent · **Question:** how close is "the system improves itself under conscience" to being real?

**Verdict in one line:** Every organ of a governed self-evolution loop now exists somewhere on this machine and most of them RUN — but they live in five different worktrees that have never been merged into one pipeline, and the live-main loop still records evolution it does not perform. The distance to one real governed self-change is a *reconciliation*, not a build.

---

## 0. Ground truth re-verified (2026-06-10, this session)

| Claim | Verified value | Evidence |
|---|---|---|
| Archive has 0% lineage | total=11,203 entries, parent_id set on **0** | direct scan of `~/.dharma/evolution/archive.jsonl` |
| Real diffs ~1% | 116/11,203 = **1.04%** non-empty diff | same scan |
| Status distribution | candidate 8,180 / **applied 2,624** / test 245 / tested 97 / observed 57 | same scan |
| WS4a exists | `~/ds_ws4` branch `governance/ws4-gate-pep`, HEAD 5d333431e "telos: enforce gate on REVIEW-decision self-mods (WS4a)" | `git log` |
| WS3 merged | live main HEAD dc72312f0 "spine: route orchestrator dispatch through invoke_agent behind flag (WS3) (#557)" | `~/dharma_swarm_live` git log, branch `runtime/live` |

---

## 1. The five axes, mapped

Axes used: **A1 Propose+Lineage** (DGM loop) · **A2 Conscience** (gate decision) · **A3 Enforcement** (apply-time PEP) · **A4 Verification** (evaluate/preflight/self-check) · **A5 Evidence & human-held promotion** (archive, receipts, mirrors).

### A1 — Propose + Lineage

**Live main (`~/dharma_swarm_live`)** — RUNS, but lineage is severed at two points:
- `dharma_swarm/dgm_loop.py:330` sets `result.parent_id = getattr(parent_entry, 'id', None)` on the *GenerationResult*, but `auto_evolve()` is called at `dgm_loop.py:387-393` **without any parent_id**, so proposals (and hence archive entries) never carry it. The child-detection at `dgm_loop.py:404-411` then searches for entries with `parent_id == result.parent_id` — which by construction never match. Self-consistent dead circuit; explains parent_id=0/11,203.
- `dharma_swarm/evolution.py:3196-3200` shadow mode does `p.diff = ""` ("Strip diffs so sandbox doesn't apply them") **before** `run_cycle`, so the archive stores empty diffs for every shadow proposal. Explains 1.04% real diffs.
- DGM protected-target refusal **is** on main: `dgm_loop.py:351-357` rejects telos/governance boundary files. RUNS.

**Repair worktree (`~/cleanup_worktrees/dharma_swarm_repair_pr323`, branch `repair/pr-323-dkeys`)** — WIRED-BUT-DORMANT (not merged):
- `dgm_loop.py` gains injectable `source_root` / `provider` / `test_command` (constructor + per-call), removing the hardcoded `Path.home()/"dharma_swarm"` and env-only provider — this is what makes the DGM step *testable offline* (diff vs main: +57 lines). It does **not** fix the parent_id→proposal drop; that gap persists in all copies.

### A2 — Conscience (gate decision)

**Live main** — RUNS but advisory-shaped:
- `evolution.py:1396-1513 gate_check()`: only `GateDecision.BLOCK` → REJECTED (`:1460-1466`); **REVIEW → GATED → flows to apply** (`:1467-1468`). This is the verified REVIEW→applied bypass.
- `evolution.py:1769-1773`: `gates_passed=["ALL"]` recorded whenever decision != BLOCK — the archive *narrates* "all gates passed" for REVIEW-decision proposals. Narration-outruns-build encoded in the data model itself.

**ds_ws4 (`~/ds_ws4`, PR #558, open)** — RUNS in worktree, operator-gated:
- WS4a: `evolution.py:1530-1543` — `GateDecision.REVIEW` on a self-mod change_type now → REJECTED with witnessed receipt (`:1437-1452`, outcome `SELF_MOD_REVIEW_BLOCKED`). Commit message itself states it's a PARTIAL fix. Known residual (operator memory, WS4b): the **ALLOW path remains keyword-evadable** — semantic classifier not yet built; WS5 live self-mod hard-blocked behind it.

### A3 — Enforcement at apply (the PEP)

**Live main** — GAP: nothing at apply-time re-checks the gate decision. The decision and the enforcement are fused at gate_check; once GATED, `run_cycle_with_sandbox` applies.

**repair_pr323** — WIRED-BUT-DORMANT, and this is the most valuable unmerged code in this lane:
- `evolution.py:200-205` `PROTECTED_EVOLUTION_DIFF_TARGETS = {telos_gates.py, dharma_kernel.py, evolution.py, config.py}`.
- `evolution.py:2414-2429` (inside `run_cycle_with_sandbox`, def at `:2346`): refuses any non-shadow apply whose unified diff touches a protected target (`_paths_from_unified_diff`, `:140`).
- `evolution.py:2431-2442`: **"Non-shadow diff apply requires ALLOW gate decision"** — REVIEW/unknown decisions are REJECTED *at the apply point*, with circuit-breaker trip. This is the PDP/PEP split the 2026-06-01 audit asked for, already written, sitting unmerged since the PR-323 repair lane.
- It is **complementary to WS4a, not redundant**: WS4a blocks REVIEW self-mods at decision time; repair blocks non-ALLOW at apply time and protects gate-defining files from any diff. Together they close both ends.

**diff_applier.py — split-brain finding (both directions):**
- Live main `diff_applier.py` has the spine tollbooth + ExecutionIdentity receipts (`require_execution_tollbooth`, `record_self_mod_receipt_sync` on apply/fail/applied) — newer WS work — but resolves targets as bare `self.workspace / patch.target_path` with **no path-escape guard**.
- repair_pr323 `diff_applier.py` has `_resolve_target()` (`:183-203`): rejects absolute paths, Windows drive/root, `..` components, and verifies the resolved path stays under the workspace — but **lacks** the identity/receipt plumbing.
- Neither copy is complete. The merged form (tollbooth receipts + `_resolve_target` + the tab-metadata-stripping `_strip_diff_prefix`) is a ~30-line reconciliation.

### A4 — Verification

- **Live main sandbox eval** — RUNS (run_cycle_with_sandbox executes tests in sandbox), but its outputs are then mislabeled by A5 (below).
- **`verify_before_done` (opus_identity worktree, `~/dharma_swarm_opus_identity`, branch `opus-identity-levelup`, WIP commit 724061970)** — RUNS in worktree, WIRED into the act path: `agent_memory_manager.py:898-1030` (structural check for non-code; decorrelated `DualAudit` for code, blocking on critical/high agreements; verdict recorded as EPISODIC memory + dock `last_receipt.json`), called from `agent_runner.py:1828` and `:2987` with `_verification_code_targets(task)` (`agent_runner.py:1373`). This is the per-agent verification loop the seat lacked. NOT on main (agent_memory_manager diff vs main: 1,332 lines).
- **`scripts/prod_preflight.py` (memory_kernel_preflight worktree)** — RUNS, 214 lines read end-to-end. Deliberately "an orchestrator around existing gates, not a new source of truth": runs memory-kernel-readiness, operator-prod-smoke, docops, test-hygiene, module-budget, git diff --check, focused recursive+operator pytest, optional semgrep/gitleaks; emits JSON report with stdout/stderr tails, exit 1 on any required failure. NOT on main.
- **`memory_kernel/readiness.py` tiers (same worktree, 525 vs main's 381 lines)** — adds explicit m0–m5 readiness tiers where **m3 (context preview), m4 (governed write receipts), m5 (live promotion) are hardcoded False with named blockers** ("operator_burn_in_required", "write_receipt_burn_in_required"). Honest anti-over-claim engineering: "ready" cannot be over-read as full power. WIRED-BUT-DORMANT (not merged). `facade.py` adds 9 bespoke surface adapters (memory_db, router_audit_log, conversations, knowledge_root/staging, quality_gates, evals, artifacts, kaizen_ops).
- **`swarm_integrity_benchmark.py` (recursive_evolution worktree, 359 lines, read end-to-end)** — RUNS, but is **tautological by construction**: `evaluate_swarm_integrity_case()` (`:285-300`) returns the outcome by switching on the case's own `failure_mode` label. It cannot fail except by editing the fixture list. To its credit it says so itself — report warnings include `"deterministic_fixture_benchmark_not_model_eval"` (`:257`). Value: it pins the *schema* (9 named failure modes incl. evaluator_editing, agent_collusion, benchmark_gaming, unsafe_self_edit) and the event/receipt plumbing — the slot where a real model-eval would plug in. Grade: RUNS as plumbing proof, ASPIRATION as an actual integrity eval.
- **`.github/workflows/governed-recursive-preflight.yml` (governed_memory_recursive_integration, untracked)** — ASPIRATION→WIRED: a real PR-gate workflow running `prod_preflight.py --quick` with `DHARMA_EVOLUTION_SHADOW=1`, `DGC_AUTONOMY_LEVEL=0`. Exists only as an uncommitted file.

### A5 — Evidence, lineage, human-held promotion

- **Live main archive write** — RUNS but lies: `evolution.py:1768` `status="applied"` is a **literal constant** for every archived proposal regardless of whether anything was applied (hence 2,624 "applied" entries vs the known 787 self_improve cycles applying nothing; `self_improve.py` present on main, 798 lines). `:1769-1773` `gates_passed=["ALL"]` for anything not BLOCKed. `parent_id` field exists in the model (`:1761`) and is faithfully copied — it's just never populated upstream (A1).
- **`recursive_discovery.py`** — the strongest artifact in this lane.
  - **On main: a 329-line subset** (receipt models + Recorder + `load_recursive_receipts` + fixtures + counts). Callers on main: `evaluation_registry.py`, `board/models.py`, `operator_core/control_surface{_models}.py` — projection/read-only only. RUNS but inert: nothing in the evolution path emits these receipts.
  - **In `~/dharma_swarm_governed_recursive_proof`: the full 1,000-line version** (read end-to-end). Adds: `validate_minimum_receipt_chain()` (`:303-325`) which **fails any chain containing `decision == "promote_to_pr"`** — "autonomous promotion not allowed" is a validator error, i.e. the no-self-promotion boundary is machine-checked, not prose; `build_recursive_shadow_run_receipts()` (6-receipt linked chain: limitation → generated_eval → candidate_diff (must carry rollback_pointer) → experiment_result (must carry commands) → witness_verdict → promotion_decision, decision always `hold`); `run_shadow_evolution_foundry()` (`:558-695`) writing real `ArchiveEntry`s **with parent_id lineage** (`:608`, `parent_archive_id` threaded `:639`) into a sandbox archive; and crucially `receipts_from_sealed_packet_result()` + `record_sealed_packet_recursive_receipts()` (`:725-829`) — **the bridge that converts a real DarwinEngine sealed-packet outcome into the receipt chain**. Note honestly: the foundry's variants are deterministic synthetic patches against a README with synthesized exit codes (`_foundry_variant_command:698-705` forces every 5th to fail) — it proves the *pipeline*, not real discovery.
  - Receipt hygiene is real: content-hash verification on load (`:296-298` drops tampered receipts), `files_touched` validator rejects absolute/`..` paths (`:106-113`).
- **`control_surface_recursive.py` (recursive_evolution worktree, 181 lines, read end-to-end)** — operator-visible projection of the above: rows render `shadow_only` + `human_promotion_required` gap codes when receipts exist (`:64-66`), `declared_only`/`recursive_discovery_evidence_missing` when they don't (`:84-85`). Coherence-state vocabulary (bound/partial/declared_only/drifted) is exactly the anti-narration instrument. NOT on main.
- **`recursive_proof_ontology.py` + `validate_recursive_proof.py` + tests (governed_memory_recursive_integration, untracked)** — mirrors receipt chains into ontology Experiment/KnowledgeArtifact/WitnessLog/GateDecision objects, explicitly "evidence projections rather than authorities." WIRED-BUT-DORMANT (uncommitted on branch `feat/governed-recursive-proof-tightening`, commit history shows 5 staged commits ending 8dca25eab).
- **ADR-0002 (`repair_pr323/docs/architecture/adr/0002-trace-coverage-gate.md`, exists nowhere else, read in full)** — the governance pattern for tightening: DEGRADED-finding-first, hard gate only via explicit follow-up with witness evidence; "enforcement tightens only where the runtime contract is proven." This is the right template for promoting any of the above from soft to hard.
- **boot-sub-swarm dry-run plan (`repair_pr323/docs/plans/2026-05-28-boot-sub-swarm-dry-run-plan.md`, exists nowhere else, read in full)** — explicitly sequenced **after** "the DGM path has a green baseline for proposal, gate, evaluation, archive lineage" — i.e. the repo's own plan already names archive lineage as the prerequisite. ASPIRATION (docs-only by declaration: "no code changes in this pass").

### Clean negatives (first-class)

1. **`~/.qwen/worktrees/holon-agent` has NO `dharma_swarm/holon/` module and no holon tests.** Only `docs/sovereign_holons/` (README + dossier + build guide), whose own README states "Status: brainstorm → design (no implementation yet)" (2026-06-08). Grade: ASPIRATION, self-declared. Anyone citing a holon implementation is citing a document.
2. **swarm_integrity_benchmark cannot detect anything** — fixture-label echo (above). Its warnings field admits this.
3. **The foundry discovers nothing** — synthetic patches, synthesized exit codes. Pipeline proof only.
4. **dgm_loop parent_id drop is NOT fixed in any worktree examined** — the repair adds testability, ds_ws4 adds gating; nobody yet threads parent_id from `parent_entry` into the `Proposal`/`ArchiveEntry`. The only code that writes real lineage is the foundry's sandbox archive (`recursive_discovery.py:608,639`), which doesn't run against the live archive.
5. **recursive shadow CLI, control_surface_recursive, swarm_integrity_benchmark, prod_preflight, readiness tiers, ontology mirror, CI workflow: none are on main** (checked file-by-file against `~/dharma_swarm_live`).

---

## 2. Grading summary

| Component | Where | Grade |
|---|---|---|
| DarwinEngine gate_check (BLOCK-only) | main `evolution.py:1396-1513` | RUNS (advisory-shaped) |
| WS4a REVIEW-self-mod block | ds_ws4 `evolution.py:1530-1543` (PR #558) | RUNS in worktree / operator-gated |
| Apply-time ALLOW + protected-targets PEP | repair_pr323 `evolution.py:200,2414-2442` | WIRED-BUT-DORMANT |
| diff_applier path-escape guard | repair_pr323 `diff_applier.py:183-203` | WIRED-BUT-DORMANT (main lacks it) |
| diff_applier identity receipts | main `diff_applier.py` | RUNS (repair lacks it) |
| DGM loop (propose) | main `dgm_loop.py` | RUNS, lineage severed `:387` |
| DGM testability injection | repair_pr323 `dgm_loop.py` | WIRED-BUT-DORMANT |
| Archive write | main `evolution.py:1711-1806` | RUNS, mislabels (`:1768`,`:1769`) |
| Shadow diff retention | main `evolution.py:3200` | BROKEN BY DESIGN (strips before archive) |
| recursive_discovery receipt subset | main (329 lines) | RUNS, inert (no emitter in evolution path) |
| Full receipt chain + no-promote validator + sealed-packet bridge | governed_recursive_proof (1,000 lines) | WIRED-BUT-DORMANT |
| Shadow foundry + CLI | recursive_evolution worktree | RUNS (synthetic content) |
| Swarm integrity v0 | recursive_evolution worktree | RUNS as plumbing / ASPIRATION as eval |
| Control-surface recursive rows | recursive_evolution worktree | WIRED-BUT-DORMANT |
| prod_preflight + readiness tiers m0–m5 | memory_kernel_preflight worktree | WIRED-BUT-DORMANT |
| Ontology mirror + proof validator + CI workflow | governed_memory_recursive_integration (uncommitted) | WIRED-BUT-DORMANT |
| verify_before_done + runner wiring | opus_identity worktree | RUNS in worktree (WIP commit) |
| Sovereign holons | ~/.qwen/worktrees/holon-agent | ASPIRATION (docs only, self-declared) |
| boot_sub_swarm | repair_pr323 docs/plans | ASPIRATION (correctly sequenced after DGM baseline) |

---

## 3. Shortest path to ONE real governed self-change end-to-end

The pieces compose into a complete loop with ~5 small merges and 2 micro-fixes. Ordered:

1. **Land WS4a** (PR #558, already dual-audited SHIP per operator memory) — closes REVIEW→applied at decision time. GATE 2 is the operator's call.
2. **Port the repair_pr323 apply-time PEP** (`PROTECTED_EVOLUTION_DIFF_TARGETS` + "non-shadow apply requires ALLOW", ~40 lines at `run_cycle_with_sandbox`) onto main. Independent of WS4a; defense at the enforcement point. Also merge `diff_applier._resolve_target` into main's receipt-bearing copy (~30 lines).
3. **Two micro-fixes on main, ~10 lines total:**
   a. Thread `parent_id` from `parent_entry.id` into the proposals `auto_evolve` creates (fixes `dgm_loop.py:387` drop → archive lineage becomes real).
   b. Derive `ArchiveEntry.status` from the actual apply outcome instead of the `"applied"` literal at `evolution.py:1768`, and record real `gates_passed` instead of `["ALL"]`. Optionally retain `proposal.diff` in a `shadow_diff` field instead of stripping at `:3200`.
4. **Wire the sealed-packet receipt bridge**: merge the full `recursive_discovery.py` (governed_recursive_proof version — main already has the 329-line prefix, so this is additive) and call `record_sealed_packet_recursive_receipts()` from the DGM/apply path. `validate_minimum_receipt_chain` then machine-enforces no-autonomous-promotion.
5. **Adopt `prod_preflight.py` + the governed-recursive-preflight workflow** as the PR gate for evolution-touching changes (it already pins `DHARMA_EVOLUTION_SHADOW=1`, `DGC_AUTONOMY_LEVEL=0` in CI).

Then the one real governed self-change is: DGM generation on a **non-protected** target with a real test_command (repair's injectable `test_command` makes this runnable), `shadow=False`, under WS4a + the apply PEP → archive entry with real parent_id, real diff, real status → 6-receipt chain in the EventLog → promotion_decision `hold` → **human opens the PR**. Every step has an existing implementation; none of it requires new code beyond the ~10 micro-fix lines.

**Hard boundary that stays:** WS4b (semantic classifier for the keyword-evadable ALLOW path) is still missing — tripwire tests exist in `tests/test_telos_self_mod_enforcement.py` (ds_ws4 lane). Until it lands, "governed" means *human-held promotion* (which the receipt validator enforces), not autonomous apply to governance-adjacent code. The readiness-tier pattern (m4/m5 hardcoded False with named blockers) and ADR-0002's prove-then-tighten rule are the correct templates for that promotion.

**Effort estimate:** items 2–4 are one focused day plus dual-audit (evolution.py is hot-path); item 1 is operator decision; item 5 is CI plumbing. The bottleneck is merge sequencing across worktrees, not engineering.

---

## 4. Files read (end-to-end unless noted)

1. `~/cleanup_worktrees/dharma_swarm_repair_pr323/docs/architecture/adr/0002-trace-coverage-gate.md` (48 ln)
2. `~/cleanup_worktrees/dharma_swarm_repair_pr323/docs/plans/2026-05-28-boot-sub-swarm-dry-run-plan.md` (49 ln)
3. `~/dharma_swarm_governed_recursive_proof/dharma_swarm/recursive_discovery.py` (1,000 ln)
4. `~/cleanup_worktrees/dharma_swarm_recursive_evolution_20260516/dharma_swarm/swarm_integrity_benchmark.py` (359 ln)
5. `~/cleanup_worktrees/dharma_swarm_recursive_evolution_20260516/dharma_swarm/operator_core/control_surface_recursive.py` (181 ln)
6. `~/cleanup_worktrees/dharma_swarm_recursive_evolution_20260516/scripts/recursive_shadow_foundry.py` (64 ln)
7. `~/cleanup_worktrees/dharma_swarm_memory_kernel_preflight_20260516/scripts/prod_preflight.py` (214 ln)
8. `~/dharma_swarm_governed_memory_recursive_integration/.github/workflows/governed-recursive-preflight.yml` (49 ln)
9. `~/dharma_swarm_live/dharma_swarm/evolution.py` — full gate_check, archive_result, auto_evolve shadow path, run_cycle_with_sandbox regions (:1390-1520, :1700-1820, :3140-3260) + full diff vs repair_pr323
10. `~/dharma_swarm_live/dharma_swarm/dgm_loop.py` :330-440 + full diff vs repair_pr323
11. `diff_applier.py` — full main↔repair diff (135 diff lines)
12. `memory_kernel/readiness.py`, `facade.py` — full main↔preflight-worktree diffs
13. `~/dharma_swarm_opus_identity/dharma_swarm/agent_memory_manager.py` :898-1064 (verify_before_done) + structure scan; `agent_runner.py` diff vs main (wiring at :1373, :1828, :2987)
14. `~/dharma_swarm_governed_memory_recursive_integration/dharma_swarm/assurance/recursive_proof_ontology.py` :1-60 + git status of 5-commit branch
15. `~/.qwen/worktrees/holon-agent/docs/sovereign_holons/README.md` (negative verification)
