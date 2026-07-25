# LIVE OPS DASHBOARD — Morning Brief

**Path:** `docs/state/LIVE_OPS_DASHBOARD.md`
**Snapshot date:** 2026-06-15
**Status:** HISTORICAL SNAPSHOT (2026-06-15, main `9c76b210`) — the track portfolio it describes has since turned over (the runtime-truth tracks it lists as ACTIVE closed 2026-06-30..07-03). For live state run `make onboard`; trust it over any line below.
**Read first if tired:** this is the place to learn what shipped, where the live swarm is running, and what not to rediscover tomorrow.

The previous 2026-05-29 dashboard was archived to `docs/state/_archive/LIVE_OPS_DASHBOARD_2026-05-29.md`.

---

## What This Is

This file is the morning briefing for agents.

It is not a feature spec and not a final architecture document. It is the current operational truth: what is on `main`, what the live runtime is actually running, what was merged, and what remains unsafe or unfinished.

This is related to, but not the same as, `ACTIVE_SURFACE_MANIFEST.yaml`:

| File | Audience | Job |
|---|---|---|
| `ACTIVE_SURFACE_MANIFEST.yaml` | Code / dashboard / API | Machine-readable declared surface map. The Manifest Health API reads it and compares declaration vs reality. |
| `docs/governance/ACTIVE_TRACK.yaml` | Governance / CI | Machine-verified portfolio (6 co-equal ACTIVE tracks; criteria graded by `check_track_status.py`). The authoritative roadmap. |
| `docs/state/LIVE_OPS_DASHBOARD.md` | Human operators / next agents | Plain-language morning brief: what changed, what is live, what matters, and what to do next. |

Short version: `ACTIVE_TRACK.yaml` is the structured truth; the manifest is the declared surface; this dashboard is the operator handoff explaining the current situation.

## Biggest So What

**Spine adoption is no longer aspirational — it is wired and 7/8 SHIPPABLE.**

PR #574 (qwen/spine-adoption integration lane) and PR #585 (holon/spine-v1) landed the runtime wiring the 2026-05-29 dashboard's "biggest so what" said was still missing. Concretely:

- `dharma_swarm/agent_runner.py:55-62` now imports `invoke_agent` and `EvidenceReceipt` directly, with a doc-block stating the "core execution (run_task) is the leaf invoked by spine-wrapped callers (Orchestrator._run_task_via_spine, A2ABridge.submit_via_spine)."
- `ACTIVE_TRACK.yaml`'s `runtime-truth-spine-adoption-2026-06` track grades **7/8** by `check_track_status.py`, with all 7 wiring criteria passing:
  - ✓ `invoke_agent_defined` · ✓ `a2a_bridge_calls_spine` · ✓ `orchestrator_calls_spine` · ✓ `agent_runner_calls_spine` · ✓ `dispatch_emits_evidence_receipt` · ✓ `zero_dropoff_sources` · ✓ `gate1_witnessed`
- The single remaining ✗ is a cosmetic regex check in `scripts/governance/spine_bypass_report.py` (`bypass_allowlist_empty` — looks for the literal empty-dict declaration). One-line fix flips the track to SHIPPABLE.

Five of six co-equal active tracks are SHIPPABLE (`runtime-truth-reconciliation-2026-06`, `runtime-truth-nats-2026-06`, `truth-graph-platform-2026-06`, `composer-holon-spine-longrun-2026-06`, and one criterion away `runtime-truth-spine-adoption-2026-06`). `loop-closure-2026-06` is 3/5 (Phase 1 closure receipt + retrospective still missing).

**Operator decision needed:** Whether to (a) close the SHIPPABLE tracks and declare the next portfolio cohort, or (b) hold them ACTIVE while the apply gate (BR-003 / DGC live-apply) closes — since several SHIPPABLE tracks were closure-bound by reconciliation rather than apply proof.

---

## 1. Main / CI

**Current main:** `9c76b210`
**Total commits:** 933
**Latest main:** `Merge pull request #585 from AmitabhainArunachala/holon/spine-v1` (2026-06-12)

| Workflow | Notes |
|---|---|
| pytest (3.11, 3.12) | gated; PR #607 in flight to fix pipefail so failures actually fail |
| semgrep / CodeQL / gitleaks | gated; CodeQL alerts on PR #574 closed via security rounds 1-4 |
| DocOps integrity | gated; canonical-guard registered for receipt/handoff/initiative trees |
| Active-Track gate | new — `check_track_status.py` runs on every PR |
| Coherence-Delta gate | gated (PR #579 hardened malleability) |
| Module-Budget gate | gated; Rule 10 grandfather backlog tracked via #547/#581/#582/#587 |
| PR-CI-Health | auto-triage report (issue #342) |

22 workflows total under `.github/workflows/`. Full list: `ls .github/workflows/`.

---

## 2. What Shipped Since Last Dashboard (2026-05-29)

232 commits, 27 merge commits in this window. Major items:

| PR | What |
|---|---|
| #585 | **holon/spine-v1** — Verified Composer Command Spine + Sovereign Holon Orchestrator (living_agent_kernel, holon_runtime, holon_orchestrator_spec). Adds 5 oversized modules grandfathered under #587. |
| #574 | **qwen/spine-adoption integration** — spine adoption, chetana, security rounds 1-4, provider+status work. The wiring PR that put `invoke_agent` into `agent_runner.py`. |
| #579 | Coherence-Delta malleability hardening |
| #577 | Devin provider hardening |
| #573 | Onboard WHY section + venv-aware Makefile + `make orient` whole-system orientation graph |
| #575 | Loop-closure 2026-06 track Phase 0 Research Dossier (PR-zero of 13-loop wiring campaign) |
| #563 | Onboard single-door v2 — portfolio regressions fixed, parallel-lane scanner, fleet receipt, `--fast`/`--json` |
| #561 | Provider honesty fix |
| #557 | Orchestrator spine flag |
| #556 | Archive flock |
| #549 | Canonical vibe-code hygiene catalogue + scan + onboard wire-in |
| #489 | ACI CI truth (Mike) |
| #490 | DocOps autorefresh feeder |
| #487 | Runtime truth projector v1 |
| #486 | Provider parser content fix |
| #470 | Spine + A2A hardening |
| #468 | Runtime Truth Spine plan + VEL RFC |
| #453 | PR janitor session |
| #449 | Andon restack |
| #446 | Combined production grounding |
| #436 | Spine adoption slice C — mapping receipts |
| #435 | Spine adoption slice B — adapter saturation |
| #430 | Spine adoption slice A — legacy bypass closure |

---

## 3. Active Portfolio Status

**6 co-equal ACTIVE tracks (WIP warn at 5, max 10). All serve `substrate-nativeness` spine objective.**
**Gaps with no active track:** `revenue-external-humans-served`, `research-depth`.

| Track | Status | Criteria |
|---|---|---|
| `runtime-truth-reconciliation-2026-06` | **SHIPPABLE** | 14/14 ✓ |
| `runtime-truth-nats-2026-06` | **SHIPPABLE** | 3/3 ✓ |
| `runtime-truth-spine-adoption-2026-06` | ACTIVE | 7/8 ✓ (one regex fix in `spine_bypass_report.py`) |
| `loop-closure-2026-06` | ACTIVE | 3/5 ✓ (LOOP1_CLOSURE_RECEIPT.md + RETROSPECTIVE.md missing) |
| `truth-graph-platform-2026-06` | **SHIPPABLE** | 15/15 ✓ |
| `composer-holon-spine-longrun-2026-06` | **SHIPPABLE** | 9/9 ✓ |

Evidence is machine-graded by `scripts/governance/check_track_status.py`. Re-render evidence: `make active-track-check` or `python3 scripts/governance/check_track_status.py`.

---

## 4. Hot Modules (post-#585, fresh x-ray)

From `xray_report.md` (refreshed this commit):

| Module | LOC | Notes |
|---|---|---|
| `thinkodynamic_director.py` | 5,186 | up from 4,757 |
| `telos_substrate.py` | 4,512 | up from 4,324 |
| `runtime_state.py` | 3,797 | issue #428 tracks split |
| `evolution.py` | 3,465 | apply gate lives here (BR-003) |
| `agent_runner.py` | 3,367 | spine-wired (see §Biggest So What) |
| `swarm.py` | 3,227 | issue #525 tracks `tick` cc-88 split |
| `providers.py` | 3,046 | issue #525 tracks decomposition; PR #389/#390/#391 scaffolds |
| `orchestrator.py` | 2,923 | issue #582 (grandfather bump 2,525→2,923 from #585); #548 superseded |
| `operator_core/living_agent_kernel.py` | 2,921 | new from holon lane; #587 tracks |
| `tui/app.py` | 2,520 | up from 2,254 |

Counts: **739 Python modules · 702 test files · 566 docs/ files · 22 workflows.**

---

## 5. Open Operational Risks

(Cross-referenced with `docs/state/BROKEN_REGISTER.md` and `INTERFACE_MISMATCH_MAP.md`.)

- **BR-003 (BLOCKER, runtime):** DGC apply gate still env-locked closed. `DHARMA_EVOLUTION_SHADOW` defaults to `"1"` across `swarm_health_api.py:97/142`, `orchestrate_live.py:618`, `dgm_loop.py:289`, `gauntlet.py:387/409`. Shadow-apply seam exercised end-to-end 2026-05-07 but no `applied:true` row yet in `~/.dharma/evolution/archive.jsonl`.
- **BR-004 (DEGRADED, cron):** Cron split-brain partial — `~/.dharma/cron/jobs.json` declared canonical authority in `METABOLIC_CLOCK.md`; per-job reconciliation still scoped follow-up.
- **BR-005 (DEGRADED, runtime):** Algedonic stream consumer/action coherence gap — `algedonic_activation.py` emits actions `Organism` does not concretely handle.
- **NEW-07 (INTERFACE_MISMATCH PARTIAL+):** trace_id propagation across 54 stores — 7 named stores instrumented; CorrelationContext auto-populates memory_palace/economic_engine/ai_reciprocity_ledger.
- **NEW-08 (PARTIAL+):** 12 independent `record_outcome()` paths — TelicSeam SignalBus subscriber pattern added; fanout not universal.
- **NEW-12 (GUARDED 2026-06-12):** cross-lane test↔module drift — guarded with `pytest.importorskip` until holon/spine-v1 lane lands (now landed via #585; gate may auto-clear).

---

## 6. Orphan Surfaces (Anti-Slop Rule 1)

The 2026-06-15 onboard-doc-refresh audit identified one Anti-Slop Rule 1 violation:

- **`docs/governance/PROD_READINESS_TOP10.md` does not exist on any branch.** 10 GitHub issues (#521, #523, #525, #527, #529, #531, #535, #537, plus #547 umbrella and #548 superseded-by-#582) reference it as their "Track" and "owner doc." The named `prod-readiness-top10` track does not exist in `ACTIVE_TRACK.yaml`. These issues are stranded — they describe real work but have no on-disk anchor and no live portfolio slot.

**Resolution path (separate follow-up PR):** Comment-and-close the orphan issues, cross-referencing the live tracks/issues that subsume them (#582/#587 for module decomposition, BR-003 for apply gate, NEW-07 for trace_id, #607 for pytest gating).

---

## 7. Next Operator Actions

In rough priority (matches Open Risks + Operator Decision above):

1. **One-line spine-bypass regex fix** — flip `runtime-truth-spine-adoption-2026-06` from 7/8 to SHIPPABLE. File: `scripts/governance/spine_bypass_report.py`, criterion `bypass_allowlist_empty`. Highest ROI in the repo.
2. **BR-003 / DGC live-apply** — one canonical proposal with `DHARMA_EVOLUTION_SHADOW=0` + `DGC_AUTONOMY_LEVEL=2`, rollback receipt landed in `~/.dharma/evolution/archive.jsonl`.
3. **Loop-closure Phase 1 receipt + retrospective** — close `loop-closure-2026-06` to SHIPPABLE.
4. **Orchestrator decomposition** — issue #582 supersedes #548. Failure-classification cluster (~100 LOC) is the recommended first cut.
5. **Open the next portfolio cohort** — `revenue-external-humans-served` and `research-depth` have no ACTIVE track. Operator call whether to seed.

---

*This dashboard refreshed 2026-06-15 by `perplexity-computer` under Stage 1 EVIDENCE_ONLY. See PR for the full audit and reconciliation map.*
