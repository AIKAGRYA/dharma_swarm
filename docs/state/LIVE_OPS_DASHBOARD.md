# LIVE OPS DASHBOARD — Morning Brief

**Path:** `docs/state/LIVE_OPS_DASHBOARD.md`  
**Snapshot date:** 2026-05-11  
**Status:** CURRENT — convergence checkpoint after merge train + runtime realignment  
**Read first if tired:** this is the place to learn what shipped, where the live swarm is running, and what not to rediscover tomorrow.

The previous 2026-05-07 dashboard was archived to `docs/state/_archive/LIVE_OPS_DASHBOARD_2026-05-07.md`.

---

## What This Is

This file is the morning briefing for agents.

It is not a feature spec and not a final architecture document. It is the current operational truth: what is on `main`, what the live runtime is actually running, what was merged, and what remains unsafe or unfinished.

This is related to, but not the same as, `ACTIVE_SURFACE_MANIFEST.yaml`:

| File | Audience | Job |
|---|---|---|
| `ACTIVE_SURFACE_MANIFEST.yaml` | Code / dashboard / API | Machine-readable declared surface map. The Manifest Health API reads it and compares declaration vs reality. |
| `docs/state/LIVE_OPS_DASHBOARD.md` | Human operators / next agents | Plain-language morning brief: what changed, what is live, what matters, and what to do next. |

Short version: the active manifest is the dashboard's structured truth source; this dashboard is the operator handoff explaining the current situation.

## Biggest So What

The repo and live runtime are no longer split across an old cutover branch and a pile of green-but-unmerged PRs.

As of this snapshot:

- GitHub `main` is green at `f2e5fe5`.
- The live launchd runtime is running that same `main` commit from `/Users/dhyana/dharma_swarm_main_cutover`.
- The clean local `main` worktree is `/Users/dhyana/dharma_swarm_tcs_heartbeat`.
- The largest safe merge train has landed.
- Remaining local worktrees are real dirty branches that need deliberate triage, not blind deletion or blind merge.

If you are a new agent tomorrow morning, start from `main` at `f2e5fe5`. Do not restart from the old lf5/cutover worldview.

---

## 1. Live Runtime

**Current live code path:**

| Surface | Current value |
|---|---|
| Live runtime worktree | `/Users/dhyana/dharma_swarm_main_cutover` |
| Live branch | `runtime/main-live-20260511` |
| Live commit | `f2e5fe5` |
| Clean main worktree | `/Users/dhyana/dharma_swarm_tcs_heartbeat` |
| Clean main commit | `f2e5fe5` |
| GitHub branch | `origin/main` |

**Launchd status at refresh:**

| Job | PID at snapshot | Notes |
|---|---:|---|
| `com.dharma.swarm` | `49233` | Live orchestrator launched from `dharma_swarm_main_cutover` |
| `com.dharma.cron-daemon` | `49234` | Cron daemon launched from same worktree |

**Fresh runtime evidence:**

- `dgc --help` works after CLI extraction.
- Manifest health report imports and builds from live checkout.
- Latest swarm log shows `All 19 systems launched (19 loops incl. free-grind)`.
- Known warning still present: `lancedb not installed`; do not treat this as a new regression from the convergence pass.

---

## 2. Main / CI

**Current main:** `f2e5fe5`  
**Latest main CI:** green

| Workflow | Result |
|---|---|
| tests | success |
| semgrep | success |
| CodeQL | success |
| gitleaks | success |

Do not merge additional PRs until checking this dashboard plus the current PR queue.

---

## 3. What Shipped In The Convergence Pass

Merged into `main` during this pass:

- `#198` — high-ROI truth / guardian work
- `#68`, `#76`, `#116`, `#104`, `#133`, `#197`
- `#196` — fleet control plane
- `#186` — ontology-native revenue package
- `#201` — DharmaAttractor / MM-07 / mismatch-map hardening
- `#112` — `dgc_cli` extracted into `dharma_swarm/terminal_commands/`
- `#192` — revenue wedge pipeline, reconciled into `dharma_swarm/revenue/wedge_pipeline.py`
- `#202` — Manifest Health API, declared-vs-observed comparison engine

Closed as superseded:

- `#184` — superseded by `#186`

Two important fixes happened before merge:

- `#112`: local review caught a real `dgc cron list` crash on scheduler records without `name`; fixed before merge.
- `#192`: avoided a new top-level `dharma_swarm/revenue_wedge_pipeline.py`; moved it under the existing revenue organ before merge.

---

## 4. Where The New Pieces Fit

**CLI extraction (`#112`)**

- Old shape: one huge `dharma_swarm/dgc_cli.py`.
- New shape: thin dispatcher in `dgc_cli.py`, command bodies in `dharma_swarm/terminal_commands/`.
- Why it matters: the launchd entrypoint stayed stable, but command logic is now decomposed enough for future agents to work safely.

**Revenue wedge (`#192`)**

- Lives at `dharma_swarm/revenue/wedge_pipeline.py`.
- Belongs to the revenue organ created by `#186`.
- Why it matters: this is not a parallel top-level experiment; it is now inside the canonical revenue package.

**Manifest Health API (`#202`)**

- Core engine: `dharma_swarm/manifest_health.py`.
- API router: `api/routers/manifest.py`.
- Registered in: `api/main.py`.
- Declared truth source: `ACTIVE_SURFACE_MANIFEST.yaml`.
- Why it matters: the dashboard now has a truth layer that compares declared state against observed reality.

---

## 5. Open PR Queue After Convergence

No obvious green merge-train item remains.

Open PRs are mostly draft, stale, conflicting, failing, or based on non-main branches. Treat them as triage, not merge queue.

Examples:

- `#191` KnowledgeOps seed — draft, needs re-evaluation after current main.
- `#190` routing fusion — draft/stale.
- `#183` Go GitHub evidence ingestor — previously green but now needs fresh mergeability review.
- `#182` slop verification — based on `feat/board-feedback-edge`, failing.
- `#181` telos doctrine — based on `feat/board-feedback-edge`, not main.
- `#168`, `#161`, `#158`, `#152`, `#151`, `#149`, `#145`, `#142`, `#131`, `#117` — stale/conflicting/failing; do not blindly merge.

If you want a safe next merge, first re-list PRs and check current `mergeable` + checks:

```bash
gh pr list --repo AmitabhainArunachala/dharma_swarm --state open --limit 100
```

---

## 6. Worktrees

Worktrees were reduced from 24 to 12. Removed dirty state was archived before removal.

Archive root:

```text
/Users/dhyana/worktree_cleanup_archives/2026-05-11/
```

Important archived slices include:

- `dharma_swarm_cutover_integration/`
- `dharma_swarm_doc_convergence/`
- `dharma_swarm_rollup/`
- `dharma_swarm_lf5/`
- `dharma_swarm_closure_v0/`
- `tcs_heartbeat/system_map/latest.json`

Remaining dirty worktrees are not trash. They are unresolved work packets:

| Worktree | Branch | Morning stance |
|---|---|---|
| `/Users/dhyana/dharma_swarm` | `cleanup/mixed-quality-recovery-2026-05-10` | huge mixed recovery bundle; needs decomposition |
| `/Users/dhyana/dharma_swarm_action_authority_spec` | `chore/action-authority-gate-spec` | large authority-gate branch; likely high value but old and conflicty |
| `/Users/dhyana/dharma_swarm_budget_fix` | `chore/opportunity-dispatcher-budget-fix` | small dispatcher split; candidate for focused review |
| `/Users/dhyana/dharma_swarm_runtime_projector` | `feat/runtime-result-projector` | substantial runtime projection work; high risk/high value |
| `/Users/dhyana/dharma_swarm_truth_spine` | `chore/agent-truth-spine` | truth-spine / operating-facts work; likely overlaps merged manifest health |
| `/Users/dhyana/dharma_swarm_go_g06_local_model_inventory` | `feat/go-local-model-runtime-inventory` | Go inventory bridge; likely related to `#183` |

Do not delete these without archiving patches and naming the reason.

---

## 7. What To Do Tomorrow Morning

Recommended order:

1. Verify the live runtime is still on `f2e5fe5` or newer:

```bash
git -C /Users/dhyana/dharma_swarm_main_cutover status --short --branch
launchctl list com.dharma.swarm
launchctl list com.dharma.cron-daemon
tail -n 80 /Users/dhyana/.dharma/logs/swarm.log
```

2. Read this file, then list PRs. Do not trust memory of yesterday's queue.

3. Pick one dirty worktree and decide: merge, split, archive, or abandon. Highest ROI candidates are probably:
   - `dharma_swarm_budget_fix`
   - `dharma_swarm_truth_spine`
   - `dharma_swarm_runtime_projector`

4. Use the manifest health API as the new truth surface:

```bash
PYTHONPATH=/Users/dhyana/dharma_swarm_tcs_heartbeat \
  /Users/dhyana/dharma_swarm/.venv/bin/python -c \
  "from dharma_swarm.manifest_health import build_health_report; print(build_health_report().get('summary'))"
```

At the 2026-05-11 refresh, it reported:

```text
{'total': 35, 'live': 24, 'degraded': 0, 'broken': 1, 'stub': 8, 'unknown': 2}
```

That is the next dashboard truth seam.

---

## 8. Do Not Forget

- The system is more converged than it was, but not finished.
- Live runtime alignment is the big win.
- The merge train is done for now.
- Remaining work is no longer “merge all green things”; it is triage of stale/draft/conflicting branches and dirty local worktrees.
- If you are tired: do not start a new architecture. Read the manifest health summary and pick one small convergence action.

---

## One-Line Verdict

`main` is green, live runtime is on `main`, and the next work is not invention; it is careful cleanup of the remaining dirty worktrees and stale PRs.
