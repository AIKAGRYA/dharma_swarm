# DharmaGraph Handoff — DEVIN LANE (Phases 0a + 0b-reconciler)

**You are Devin, on a fresh VM with a fresh clone of `AmitabhainArunachala/dharma_swarm` (main).** This brief is self-contained; the full campaign spec is `docs/plans/DHARMAGRAPH_PHASED_SPEC_2026-07-05.md` — read §1 (current-state truth) and §3 Phases 0a/0b before writing code. Your own prior review of this repo was adjudicated into that spec; your recovery-pattern finding is the backbone of this lane.

## Before ANYTHING else (non-negotiable)

```bash
make onboard   # renders live tracks, trust check, next command — TRUST ITS OUTPUT over any doc, including this one
make orient    # whole-system orientation graph
```

Then: read `CLAUDE.md` (behavioral rules bind you), `INTERFACE_MISMATCH_MAP.md` (check every module pair you touch), and the testing playbooks in `.agents/skills/` — especially `testing-spine` and `testing-provenance` (they define your environment setup, verdict format, and do-nots). Your work lands under the active track `dharmagraph-engine-2026-07` (see `docs/governance/ACTIVE_TRACK.yaml`) — cite it in your PR body.

## Coordination contract (another agent runs SIMULTANEOUSLY)

A Claude instance is concurrently building `dharma_swarm/graph/durable_invoker.py` and the langgraph differential oracle. File-ownership split — do not cross it:

| Yours | Theirs |
|---|---|
| `dharma_swarm/graph/checkpoint.py` (new) | `dharma_swarm/graph/durable_invoker.py` (new) |
| `dharma_swarm/graph/reconciler.py` (new) | `tests/test_graph_durable_invoker.py`, oracle harness |
| deletions: `workflow_graph.py`, `durable_execution.py` + tests | `[test-oracle]` extra in pyproject |
| `swarm.py` reconciler wiring (small, hot-path ack) | `orchestrator.py` seam call (small, hot-path ack) |
| `tests/test_graph_checkpoint.py`, `tests/test_graph_reconciler.py` | CI workflow for the oracle |

If `dharma_swarm/graph/__init__.py` doesn't exist yet, create it minimal (docstring + explicit `__all__`); whoever lands second rebases. Branch naming: `devin/dharmagraph-phase0a` and `devin/dharmagraph-phase0b-reconciler`. One PR per phase slice. Never push to main directly.

## Task 1 — Phase 0a: delete the dead engines (do this first; it's your warm-up)

1. Verify (fresh grep, don't trust this doc): `dharma_swarm/workflow_graph.py` and `dharma_swarm/durable_execution.py` have zero non-test importers. Known importers at spec time: `workflow_graph.py:25` imports durable_execution; tests `test_workflow_graph.py`, `test_durable_execution.py`, `test_runtime_truth_spine_recovery.py:6`. (`tools/spine_adoption_metric.py` references them as scan strings only — update its string list if needed.)
2. ABSORB before deleting — into new `dharma_swarm/graph/checkpoint.py` (keep it under 500 lines):
   - the atomic fsync'd checkpoint/restore mechanism (`durable_execution.py:218-308`) — tmp+rename+fsync, full-state restore;
   - the `_record_runtime_receipt` spine hook (`durable_execution.py:324-345`) — ties checkpoints to `ExecutionIdentity`/`RuntimeReceipt`.
   - Do NOT absorb the `LoopCheckpoint` schema from `dharma_swarm/checkpoint.py` — it's loop/fitness-shaped, wrong for dispatch. You're taking the *pattern*, defining a dispatch-shaped record (run_id, superstep, node_id, state_ref, created_at).
3. Port the absorbed code's test coverage into `tests/test_graph_checkpoint.py`; fix `test_runtime_truth_spine_recovery.py` imports; delete the two modules + their two dedicated test files.
4. Acceptance: repo-wide grep shows zero imports of the deleted modules; new tests green; `python3 -m pytest tests/ -q` shows no new failures vs a baseline run you did BEFORE changing anything (never compare to remembered counts).

## Task 2 — Phase 0b: the run-level boot reconciler (the real work)

**Problem:** an in-flight `delegation_runs` row orphans on `kill -9` — dispatch lives only as a detached asyncio task (`orchestrator.py:2403-2407`). Nothing reconciles at boot. `recovered_at` on `task_claims` has no writer on this path.

**Do NOT hand-roll.** Generalize the existing pattern you yourself found: `operator_bridge.recover_stale_tasks` (`operator_bridge.py:748-818`) + `_mirror_runtime_recovered` (`:1359-1415`, writes `status="recovered"` at `:1372`). Also study the sibling idiom `SwarmManager.reap_orphaned_tasks` (`swarm.py:1774-1843`) — same shape, wrong database (tasks.db, not runtime.db).

Build `dharma_swarm/graph/reconciler.py`:
1. **Boot scan** (single-host daemon ⇒ anything in-flight at boot is orphaned by definition):
   - `delegation_runs`: `status IN ('claimed','running') AND (quarantined_at IS NULL OR quarantined_at='')`
   - `task_claims`: `status IN ('claimed','running') AND recovered_at IS NULL AND stale_after < :now`
   - Compare timestamps tz-aware in Python (the `parse_ts` convention, `loop_closure_quarantine.py:48-59` — 'Z' vs '+00:00' drift is a known trap).
2. **Classify with the EXISTING vocabulary** (`orchestrator._classify_failure`, `orchestrator.py:831-848`): never-started → `failure_code='claim_timeout'` requeue; started-and-died with retries left → requeue mirroring `_handle_task_failure` (`:1987-2055`), incrementing `retry_count`; retry-exhausted → quarantine stamp exactly per `dharma_swarm/loop_closure_quarantine.py` doctrine (rows stay auditable, tally always reported, never hidden). Write `recovered_at = now` on every reconciled claim.
3. **Torn-window rule:** `receipt_json` present but claim non-terminal ⇒ the crash hit between receipt-write and claim-completion — complete the claim FROM the receipt (the receipt is ground truth).
4. **Owner wiring** (hot-path — see gates below): call once at the end of `SwarmManager.init()` (`swarm.py:551` area, after `_task_board`/orchestrator construction `:633-656`) and periodically from `SwarmManager.tick()` next to the existing `reap_orphaned_tasks` call (`swarm.py:2289`). NOT the API lifespan (it's best-effort/cancellable, `api/main.py:157-166`); NOT a cron (second process fights the single-writer discipline).
5. **Heartbeat:** wire the orphaned `heartbeat_claim_sync` (`runtime_state.py:2062`, currently zero production callers) so executing tasks heartbeat at cadence ≤ stale_after/3. Promote `last_heartbeat` out of metadata only if it doesn't force a schema change beyond an idempotent ALTER (follow `loop_closure_quarantine.py:70-82` precedent).
6. **Swallow triage, THIS path only:** any `except Exception: pass` in dispatch/persist/reconcile code you touch gets a logged, classified handler. The global swallow cleanup is Phase 5 — don't boil the ocean.

**The acceptance gate is a CHAOS RECEIPT, not a green unit suite:**
```
1. Start the runtime with isolated state: DHARMA_STATE_DIR=$PWD/.e2e_state/chaos uvicorn api.main:app ...
2. Dispatch work; kill -9 the process mid-dispatch (while delegation_runs has status='running').
3. Restart. Assert: orphan requeued-or-quarantined; recovered_at stamped; ZERO double provider calls
   (assert via idempotency records / provider-call counter in a stub runner); receipts intact.
4. Capture the full command log + assertions as the PR's evidence block.
```
Plus ≥7 unit tests in `tests/test_graph_reconciler.py` (fixture DBs, per the `testing-provenance` playbook style). A PR that claims done without the chaos receipt will be rejected — this repo's whole doctrine is receipts over narrative.

## Gates you WILL hit (read before your first commit)

- **Hot-path ack:** `swarm.py` is on the `HOTPATH_FILES` list (`scripts/uplift_guards/hotpath_guard.py:16-42`). Commits touching it need the commit-message tag `[impact-checked]` or env `DHARMA_UPLIFT_ACK=impact-checked`.
- **Module budget:** new modules hard-capped at 1000 lines (`scripts/governance/check_module_budget.py:56`); keep them under 500 per CLAUDE.md. `orchestrator.py` is AT its ceiling — do not add code there (that's the other lane's one-line seam call anyway).
- **Spine ownership guard:** `scripts/uplift_guards/check_spine_ownership.py` — new sqlite-importing files under `dharma_swarm/spine/` need `# spine: <role>` headers; your files live in `dharma_swarm/graph/` (outside that gate) but follow the convention anyway: first line `# spine: reconciles delegation_runs/task_claims (owner: runtime_state) — no new store`.
- **No new truth stores. No gate weakening. Runtime receipts under `~/.dharma/`, never in git.** Pre-commit: `SKIP=semgrep-local pre-commit run --all-files` if semgrep is missing.
- Before opening a PR citing any BR-id: `gh pr list --state open --search "BR-NNN"` per CLAUDE.md pre-flight.

## Definition of done (whole lane)

Phase 0a PR merged + Phase 0b PR merged, each with: baseline-diffed full-suite results, the chaos receipt (0b), zero new gate failures, PR bodies citing `dharmagraph-engine-2026-07` and the spec section implemented. Track criteria that must flip green from your work: `phase0a_dead_engines_deleted`, `phase0b_reconciler_tests_pass`.

---

# TRANCHE 2 — Persistence/Resume Kernel (LG14–LG18) — issued 2026-07-13

**Status of the lane above: COMPLETE.** Phase 0a/0b landed (PRs #798/#799/#800; `tests/test_graph_chaos_receipt.py` passes; track ledger `docs/governance/ACTIVE_TRACK.yaml` next_items 2–4 marked DONE). Do NOT redo it. This tranche builds ON that machinery: `dharma_swarm/graph/checkpoint.py`, `graph/reconciler.py`, `graph/durable_invoker.py`, `graph/effects.py`.

## Mission

Close the five highest-weight durability gaps from the judge-signed parity gauntlet as ONE coherent persistence/resume kernel — not five scattered card fixes. Judge-signed baseline: **31.00/100, verdict NOT_FINISHED** (`reports/governance/dharmagraph_parity/PARITY_MATRIX.md`; receipts digest-sealed under `reports/governance/dharmagraph_parity/`). Closing this tranche moves the trajectory toward ~52 — do not claim any score; only a fresh judge-run gauntlet grades.

## Vision constraints (operator-confirmed 2026-07-12; seed doc in PR #909 — read it from that branch if unmerged)

- **Workload-agnostic, always.** No first-passenger specialization; never tune the engine for one demo, agent, provider, or model.
- **Verification is permanent; ratification dissolves.** Every capability lands behind a receipt + a falsification test (a test that would CATCH the capability lying), not a human babysitter.
- Engine requirements, verbatim: durable complexity; multi-day campaign bearing; provider/model/agent-agnostic organizing intelligence.

## The five cards (weights and unproven facets from PARITY_MATRIX.md — the facet lists ARE the work breakdown)

| Card | Weight | Now | Unproven facets (each needs a proving scenario) |
|---|---|---|---|
| LG18 process-restart durability | 10 | 1/2 | durability_sync, durability_async, durability_exit, persistent_process_restart, pending_write_recovery, delta_channel_durable_history |
| LG15 thread-scoped resume | 9 | 0/2 | thread_id, checkpoint_id, thread_resume, checkpoint_parent, multi_turn_state |
| LG17 update/fork/time-travel | 8 | 1/2 | update_state, bulk_update_state |
| LG14 checkpoint protocol | 4 | 1/2 | sync_saver, async_saver, pending_writes, serializer, delete_thread, delete_for_runs, copy_thread, prune, get_delta_channel_history, async_checkpoint_lifecycle |
| LG16 state/history/replay | 2 | 1/2 | get_state, get_state_history, async_state_api |

Gap ids: `parity-gap-lg18-process-restart`, `-lg15-thread-resume`, `-lg17-fork-time-travel`, `-lg14-checkpoint-protocol`, `-lg16-history` (`ACTIVE_TRACK.yaml` next_items; the 100/100 bar blocker is next_item 6).

## Acceptance oracle (uncharmable — never self-grade)

- DoD per card: the gap flips to 2/2 **in a fresh gauntlet run**: `bash scripts/governance/run_python_with_repo_env.sh scripts/governance/dharmagraph_parity_gauntlet.py` against rubric `docs/langgraph_parity/DHARMAGRAPH_PARITY_GAUNTLET_RUBRIC_V2.json`. Independent judge rerun required before any closure claim; self-declared N/A scores 0 (operator ratification only).
- **Environment trap (verified 2026-07-13):** two track criteria (`phase1_oracle_tests_pass`, `parity_gauntlet_check_passes`) fail on any host without real langgraph — `--check` exits 2 with `langgraph_version: installed='NOT_INSTALLED' expected='1.2.4'`. Install the `[test-oracle]` extra FIRST and record it in your entry receipt; those two must be green on your VM before you write code, or your baseline is meaningless.
- **Rubric files are read-only for this tranche.** `DHARMAGRAPH_PARITY_GAUNTLET_RUBRIC_V2.json` and the gauntlet script are track surfaces, but moving the score by editing the rubric or grader is a governance violation — closure comes from capabilities only.

## Guardrails

- Track `dharmagraph-engine-2026-07`; stay inside its owned surfaces (`ACTIVE_TRACK.yaml:897-921`). New code goes in `dharma_swarm/graph/` modules (<500 lines each); `orchestrator.py` is at its module-budget ceiling — minimal seam edits only, with hot-path ack (`[impact-checked]`) for `swarm.py`/`orchestrator.py` per `scripts/uplift_guards/hotpath_guard.py`.
- **Do NOT start Phase 2 crowning** (routing `_dispatch_topology_genome` through the graph engine): that is separately gated on the oracle CI flipping to blocking plus an operator go (`ACTIVE_TRACK.yaml` next_item 4 note).
- Adjacent ring (LG25 heartbeat/timeout, LG24 retry, LG30 config/context, APP01 neutral-engine handoff) is NEXT tranche — only pull one in if it falls out of this kernel for free.
- No new truth stores; runtime receipts under `~/.dharma/`, never git. One PR per coherent slice, draft PRs, independent review, never self-merge. Branch naming: `devin/dharmagraph-tranche2-<slice>`.
- On entry: `make onboard`, re-derive the parity baseline at YOUR entry SHA, cite file:line for every claim in PR bodies.
