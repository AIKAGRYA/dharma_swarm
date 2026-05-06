# BUILD SESSION ENTRYPOINT

**Status:** canonical current repo truth and build-session pointer layer.
**Last refreshed:** 2026-05-06 from current `origin/main` plus this truth-refresh branch.
**Owner of:** the current operating picture, mandatory read order, current-track boundary, and next-step queue for build agents.
**Subordinate to:** [`CLAUDE.md`](../../CLAUDE.md) for behavior and [`SOVEREIGN_MANIFEST.md`](SOVEREIGN_MANIFEST.md) for durable architecture. If this file disagrees with code, verify the code and update this file.

This is the single page to read before touching the repo. It is intentionally plain: what exists, what is dirty, what not to merge, and what to do next.

---

## 0. Current Code Truth

As of 2026-05-06, `origin/main` is `e007eaf docs(research): add fractal room venture cell foundations`. This branch (`chore/current-truth-refresh`) is ahead of that with the DocOps integrity work cherry-picked and this documentation refresh.

The repo is no longer at the old "Operator Brief is only a spec" state:

- **Operator Brief v0 exists on main.** The code lives under `dharma_swarm/operator_brief/`, runs through cron via `dharma_swarm/cron_runner.py`, persists ontology artifacts, records `RuntimeStateStore.artifact_records`, and has tests in `tests/test_operator_brief_insight_brief.py`.
- **First live tick is witnessed.** See [`reports/witness/2026-05-05-operator-brief-first-tick.md`](../../reports/witness/2026-05-05-operator-brief-first-tick.md). It captured `KnowledgeArtifact`, `ActionProposal`, four `GateDecisionRecord` ids, `Outcome`, `ValueEvent`, and materialisation witness ids.
- **Operator Brief silence is guarded.** `dharma_swarm/operator_brief/watchdog.py` feeds `guardian_crew.py` with DEGRADED/BLOCKER findings when cron ticks do not produce `artifact_records`.
- **The first value read exists.** `dgc value-events --since <date>` is implemented by `dharma_swarm/operator_brief/value_events.py` and wired in `dharma_swarm/dgc_cli.py`.
- **Trace Attractor is in shadow implementation, not just spec.** `dharma_swarm/trace_attractor/` defines typed packets, a pure projector, read-only store readers, and tests. It is still a rebuildable read model, not a mutable source of truth and not an autonomy/dashboard trigger.
- **DocOps integrity is staged on this branch.** `scripts/docops/check_docops_integrity.py`, `tests/test_docops_integrity.py`, `docs/docops/`, the pre-commit hook, and the GitHub workflow are present here. Merge this branch before treating DocOps as mainline governance.

Verified during this refresh:

- `pytest tests/ --collect-only -q`: 9,729 tests collected, exit 0.
- ContextPlus semantic identifier search was attempted and timed out after 120 seconds, so this refresh is grounded in local source reads, git state, and executable checks.

---

## 1. Current Dirty / Unmerged Work

Do not treat every worktree as merge-ready. The current hot lanes are:

| Lane | State | What it means |
|---|---|---|
| `/Users/dhyana/dharma_swarm` | dirty on `chore/phase2-governance-isolation`, behind its remote | Contains API/dashboard/hypernode/opportunity WIP. Do not merge or cherry-pick without a separate quarantine/integration pass. |
| `/Users/dhyana/dharma_swarm_action_authority_spec` | dirty, ahead 5 and behind 24 | Broad Action Authority runtime edits across API, runner, cron, sandbox, telic seam, tests. High-risk integration branch, not ready for main. |
| `/Users/dhyana/dharma_swarm_integrate_chetana` | untracked Core Four docs and `.gitnexus/` | Valuable architecture material, but not mainline code truth until curated and registered through DocOps. |
| `/Users/dhyana/dharma_swarm_authority_ptr_rollup` | clean, ahead 8 and behind 19 | PTR/AAG rollup exists but is stale against current `origin/main`. Rebase/re-review before any integration. |
| `/Users/dhyana/dharma_swarm_current_truth_refresh` | ahead of `origin/main` | Current safe branch for DocOps plus truth refresh. This is the branch to merge first if verification stays green. |

Historical Phase 2 checkpoint and rollup worktrees are superseded by current `origin/main` unless a commit is explicitly named in a new integration task.

---

## 2. Mandatory Read Order

Read in this order before code changes:

1. [`CLAUDE.md`](../../CLAUDE.md) - behavior, commands, and engineering rules.
2. This file - current repo truth, locks, and next-step queue.
3. [`docs/governance/SOVEREIGN_MANIFEST.md`](SOVEREIGN_MANIFEST.md) - architecture, domain map, invariants, measured state.
4. [`docs/governance/CANONICAL_DOC_STACK.md`](CANONICAL_DOC_STACK.md) - document authority and DocOps rules.
5. [`docs/governance/REPO_GOVERNANCE_AUDIT.md`](REPO_GOVERNANCE_AUDIT.md) - contradiction and staleness ledger.
6. The active spec for your lane:
   - Operator Brief status: [`docs/plans/ONTOLOGY_NATIVE_OPERATOR_BRIEF_MASTER_SPEC.md`](../plans/ONTOLOGY_NATIVE_OPERATOR_BRIEF_MASTER_SPEC.md)
   - Substrate queue: [`docs/plans/NEXT_10_SUBSTRATE_TODO.md`](../plans/NEXT_10_SUBSTRATE_TODO.md)
   - Trace Attractor boundary: [`docs/plans/TRACE_ATTRACTOR_LEDGER_MASTER_SPEC.md`](../plans/TRACE_ATTRACTOR_LEDGER_MASTER_SPEC.md)

---

## 3. What "Ontology-Native" Means Here

A flow is ontology-native when all of these are true:

1. Outputs are typed `OntologyObj` instances persisted through `OntologyRegistry`.
2. Shared-state changes go through typed action or runtime substrates, not ad hoc files.
3. Gateable decisions create `GateDecisionRecord` plus `WitnessLog`.
4. Artifacts are linked to their producing proposal/outcome/witness context.
5. Value-bearing outcomes emit `ValueEvent`; attributable work emits `Contribution`.
6. Failure modes are visible as records, not silent logs.
7. Tests fail if any of the above regress.

The Operator Brief seam is the first proven example. Most of the runtime is still not ontology-native. Do not generalize one shipped seam into a claim that the whole swarm is now substrate-native.

---

## 4. Current Decision Boundary

The highest-ROI next move is consolidation, not a new grand subsystem.

Merge order:

1. **Merge this truth-refresh branch** after DocOps and focused tests pass. It gives agents a current map and a doc integrity gate.
2. **Clean or quarantine dirty main WIP** before any more checkpoint rollups. The main worktree has API/dashboard/hypernode/opportunity changes that need their own integration plan.
3. **Decide the Trace Attractor next step.** The shadow read model exists. Runtime/dashboard/autonomy wiring waits until either:
   - `dgc value-events` has been used against real operator data for seven calendar days, or
   - an explicit Fourfold Action Warrant explains why waiting is worse.
4. **Rebase and re-review PTR/AAG only after the above.** PTR must remain negative-authority/shadow unless explicitly promoted. AAG is broad and dirty; it needs a focused merge plan, not opportunistic cherry-picks.
5. **Curate Core Four docs through DocOps.** The large v3/Core Four material can inform architecture, but only registered docs can carry repo-level authority.

---

## 5. What Not To Do

- Do not merge dirty Interop/dashboard/API/hypernode WIP into this branch.
- Do not treat `dharma_swarm_action_authority_spec` as merge-ready.
- Do not turn Trace Attractor into a new source of truth. It projects existing stores.
- Do not add new routers, bridges, adapters, ledgers, registries, or memory stores before checking the existing substrates.
- Do not create new root Markdown. New docs need a DocOps role and an authority boundary.
- Do not cite old counts or old collection errors. Re-run the command.

---

## 6. Immediate Verification Commands

For docs/current-truth work:

```bash
/Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/ --collect-only -q
/Users/dhyana/dharma_swarm/.venv/bin/python -m pytest -q tests/test_docops_integrity.py tests/test_operator_brief_insight_brief.py tests/test_value_events_cli.py tests/test_guardian_crew.py tests/test_trace_attractor_projection.py tests/test_trace_attractor_readers.py
python3 -m compileall scripts/docops/check_docops_integrity.py dharma_swarm/operator_brief dharma_swarm/trace_attractor tests/test_docops_integrity.py
make docops-report
git diff --check
```

Use broader suites only when the change touches runtime behavior.
