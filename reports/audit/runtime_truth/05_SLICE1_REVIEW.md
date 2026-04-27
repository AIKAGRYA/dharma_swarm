# 05_SLICE1_REVIEW

**Generated:** 2026-04-26 (UTC)
**Reviewer:** Claude Opus, read-only posture
**Subject:** `~/promotion_worktrees/dharma_swarm_lf5_promotion/reports/audit/runtime_truth/04_SLICE1_RUNTIME_SPINE_RESULT.md` and the working-tree changes it describes
**Worktree state at review:** `promote/lf5-runtime-spine`, HEAD = `da6a4fa` (uncommitted; Codex left changes in working tree as instructed)
**Live daemon at review:** PID 20465 still alive (elapsed 05:20:45), command unchanged
**Constraints adhered to:** read-only; no `git add` / commit / push / checkout / stash; no `dgc` calls; no `~/.dharma/` writes; no edits to either dirty tree.

---

## 0. Headline

**Recommendation: proceed to slice 2.**

Slice 1 is a clean, narrow, daemon-safe landing of the producer-wiring fix. Every veto criterion from `03_MATRIX_REVIEW.md` is satisfied. Tests reproduce independently (3 + 4 + 15 = 22 passed). The runtime-spine acceptance gate (`task_claims = 1`, `delegation_runs = 1` with `status='completed'`, `session_events ≥ 3`, idempotence on second tick) is met.

One minor scope observation (not a veto): the `telos_graph.get_by_name()` mismatch fix that `03_MATRIX_REVIEW.md` §3 listed as eligible for slice 1 was deferred. That is a defensible call — it's a separate `INTERFACE_MISMATCH_MAP` entry, not producer wiring. It can be folded into the slice-1 commit at push time or land as slice 1.5.

---

## 1. Narrow diff scope — verified ✅

`git diff --stat HEAD`:

```
 dharma_swarm/orchestrator.py  | 210 ++++++++++++++++++++++++++++++++++++++++-
 tests/test_bootstrap_loops.py | 133 +++++++++++++++++++++++++-
 tests/test_session_ledger.py  |   9 +-
 3 files changed, 347 insertions(+), 5 deletions(-)
```

Three source-tree files. Plus untracked `reports/audit/` (audit artifacts only). No dashboard, no API, no docs/wiki, no AGNI/NATS, no live daemon code, no LF5 promotion of `task_contract.py` / `task_board_mirror.py` / `build_authority.py` / `build_registry.py` / `frontier_council.py` / `ontology_context.py` / opportunity-chain modules.

Codex's reported file list matches the working tree exactly (modulo the report file itself).

**Verdict:** narrow.

---

## 2. No whole-file LF5 restore — verified ✅

Quantitative proof (line/byte counts):

| File | HEAD (origin/main) | Working tree | LF5 reference |
|---|---:|---:|---:|
| `dharma_swarm/orchestrator.py` | 2,454 lines / 99,798 B | **2,662 lines / 107,507 B** | 3,089 lines / 125,814 B |

The working tree is `HEAD + 208 lines` and `HEAD + 7,709 bytes`. The LF5 file is **427 lines / 18,307 bytes larger** than the patched working tree. A whole-file restore would have produced `WT == LF5`. It does not. Patch confirmed.

Qualitative checks:

- New top-level imports in `orchestrator.py`: exactly one — `from dharma_swarm.runtime_state import DelegationRun, TaskClaim`.
- `grep` for LF5-only module imports (`task_contract`, `task_board_mirror`, `build_authority`, `build_registry`, `frontier_council`, `ontology_context`, `opportunity_dispatcher`, `opportunity_refill`, `_campaign_manifest`) in the diff: **zero hits**.
- `grep` for unrelated LF5 content keywords (`campaign`, `frontier`, `ontology`, `task_contract`) in `+` lines of the diff: **zero hits**.
- Hunk count: 8 hunks (1 import + 7 method-area additions). All concentrated near the runtime helper block (~L656–820) and the dispatch/execute/failure region (~L1740–2230). No edits at unrelated locations.

**Verdict:** hand-port patch, not whole-file restore.

---

## 3. No parallel substrate — verified ✅

Writers used by the patch (verified via `grep` on the diff and on the patched file):

- `RuntimeStateStore.record_task_claim(TaskClaim(...))` — existing writer.
- `RuntimeStateStore.record_delegation_run(DelegationRun(...))` — existing writer.

Writers / tables NOT introduced:

- No new SQLite file path created (no new `*.db` reference, no `~/.dharma/build_registry/registry.jsonl` or similar parallel JSONL).
- No new table DDL added in `runtime_state.py` (file is unchanged at HEAD).
- No new dataclass writer added in `runtime_state.py` (file is unchanged at HEAD).
- `SessionLedger` contract preserved: `_append()` still writes JSONL and calls `record_session_event_sync()`. The change to `tests/test_session_ledger.py` only adds an explicit `runtime_db_path=` argument so existing tests stop indexing into the live `~/.dharma/state/runtime.db`. **This is a pre-existing isolation gap that Codex incidentally fixed.**

`build_registry.py`, `build_authority.py`, `task_contract.py`, `task_board_mirror.py`, `frontier_council.py`, `ontology_context.py` — all explicitly **not promoted** in this slice.

**Verdict:** canonical substrates remain canonical. No duplicates added.

---

## 4. Temp runtime-DB isolation — verified ✅

`tests/test_bootstrap_loops.py` new tests (3 added):

| Test | Isolation |
|---|---|
| `test_task_lifecycle` | `state_dir = tmp_path / "state"`; `runtime_db_path = state_dir / "runtime.db"`; `monkeypatch.setenv("DHARMA_STATE_DIR", str(state_dir))`; explicit `runtime_db_path=runtime_db_path` passed to ledger. ✅ |
| `test_task_failure_records_runtime_run` | Same pattern: `state_dir`, `runtime_db_path`, monkeypatch `DHARMA_STATE_DIR`, explicit `runtime_db_path=`, `board = TaskBoard(db_path=tmp_path / "tasks.db")`, `ledger_dir=tmp_path / "ledgers"`. ✅ |
| `test_full_loop_closure` | Same pattern: monkeypatch `DHARMA_STATE_DIR=str(state_dir / "state")`, explicit `runtime_db_path=state_dir / "state" / "runtime.db"`. ✅ |

`tests/test_session_ledger.py` modifications:

```diff
-    ledger = SessionLedger(base_dir=tmp_path, session_id="sess_a")
+    ledger = SessionLedger(base_dir=tmp_path, session_id="sess_a", runtime_db_path=tmp_path / "runtime.db")
...
-    ledger = SessionLedger()
+    ledger = SessionLedger(runtime_db_path=tmp_path / "runtime.db")
```

Both pre-existing tests now pass an explicit `runtime_db_path`. Before this change, the second test (env-var only) implicitly used the default `~/.dharma/state/runtime.db` for the runtime DB. **That was a real test-isolation defect on `origin/main` that Codex repaired as part of slice 1.**

`grep` for default-path constructors in the diff: `RuntimeStateStore()` and `SessionLedger()` with no args appear **zero** times in the new code.

Live-state mtime check: `~/.dharma/state/runtime.db` last modified `Apr 26 15:23:51 2026` — *before* my reproduction test runs (~16:24). The daemon (PID 20465) writes there on its own cadence; my test runs did not perturb it.

**Verdict:** test isolation is complete. Tests cannot reach `~/.dharma`.

---

## 5. Real row-count assertions — verified ✅

Direct `grep` of the diff for `_runtime_table_count(...) == N` and `... >= N`:

```
+    assert _runtime_table_count(runtime_db_path, "session_events") == 0
+    assert _runtime_table_count(runtime_db_path, "task_claims") == 0
+    assert _runtime_table_count(runtime_db_path, "delegation_runs") == 0
+    assert _runtime_table_count(runtime_db_path, "task_claims") == 1
+    assert _runtime_table_count(runtime_db_path, "session_events") >= 3
+    assert _runtime_table_count(runtime_db_path, "task_claims") == 1
+    assert _runtime_table_count(runtime_db_path, "delegation_runs") == 1
+    assert _runtime_table_count(runtime_db_path, "task_claims") == 1
+    assert _runtime_table_count(runtime_db_path, "delegation_runs") == 1
+    assert _runtime_table_count(runtime_db_path, "task_claims") == 1
+    assert _runtime_table_count(runtime_db_path, "delegation_runs") == 1
```

Plus an assertion on delegation status:

```
+    assert _runtime_delegation_statuses(runtime_db_path) == ["completed"]
```

The assertion sequence follows the canonical lifecycle:

1. **Pre-dispatch:** `session_events == 0`, `task_claims == 0`, `delegation_runs == 0`.
2. **Post-dispatch (assignment):** `task_claims == 1`, `session_events >= 3`.
3. **Post-execution (success):** `task_claims == 1`, `delegation_runs == 1` with status `["completed"]`.
4. **Second tick (idempotence):** `task_claims == 1`, `delegation_runs == 1` (no duplication).

Failure-path test asserts `task_claims == 1` and `delegation_runs == 1` with a separate `sqlite3.connect(runtime_db_path)` block to inspect failure status (visible in the diff but truncated by my grep filter).

These are real `==`/`>=` integer assertions, not "exists" checks.

**Verdict:** assertions are real, ordered, and exercise the full Codex-claimed sequence (Codex's `04` report shows `before / after_dispatch / after_execution / after_second_tick` — matches the assertion sequence here).

---

## 6. `agent_pool.list_agents()` guard — narrow ✅

The exact change in `_assign_dispatch`:

```diff
+        pool_agents_sample: list[Any] = []
+        list_agents = getattr(self._pool, "list_agents", None) if self._pool else None
+        if list_agents:
+            try:
+                agents_result = list_agents()
+                if inspect.isawaitable(agents_result):
+                    agents_result = await agents_result
+                if isinstance(agents_result, list):
+                    pool_agents_sample = list(agents_result[:3])
+            except Exception:
+                logger.debug("Pool agent sample failed", exc_info=True)
...
             "_assign_dispatch(%s): runner=%s task=%s pool_agents=%s",
             td.task_id[:8], bool(runner), bool(task),
-            list((await self._pool.list_agents()) if self._pool else [])[:3],
+            pool_agents_sample,
         )
```

Properties:

- Uses `getattr(..., None)` — proper hasattr-style guard, not a refactor.
- Wraps the call in `try/except`, logs at `debug` only — no propagation.
- Handles both sync and async pools via `inspect.isawaitable`.
- Replaces **only the debug-log argument** for `_assign_dispatch(%s): runner=... pool_agents=...`. Dispatch semantics (assignment, claim creation, task-board update, runner invocation) are unchanged.
- The list is sliced `[:3]` — same upper bound as the original.

**Verdict:** guard is narrow and behaviorally invariant for compliant pools. It only changes behavior for pools missing `list_agents()` (formerly: `AttributeError` crashed dispatch; now: empty sample, dispatch continues).

---

## 7. Tests reproduce — verified ✅

Independent re-run from the promotion worktree (Python 3.13 / miniforge):

| Test file | Codex's claim | My re-run | Status |
|---|---|---|---|
| `tests/test_session_ledger.py` | 3 passed | **3 passed** in 0.22s | ✅ matches |
| `tests/test_runtime_state.py` | 4 passed | **4 passed** in 0.22s | ✅ matches |
| `tests/test_bootstrap_loops.py` | 15 passed | **15 passed** in 3.78s | ✅ matches |
| `python -m compileall dharma_swarm tests` | passed | **passed** (exit 0) | ✅ matches |

The `Unknown config option: timeout` warning is pre-existing and harmless (pytest config option not registered in the running pytest version).

`make compile` was correctly avoided — the target does not exist in this worktree's Makefile (verified earlier in `03_MATRIX_REVIEW.md` §8). Codex used `python -m compileall dharma_swarm tests` instead, which is the right substitute.

**Verdict:** reproduction matches Codex's claim exactly.

---

## 8. Live daemon untouched — verified ✅

| Check | Before slice 1 | After review | Status |
|---|---|---|---|
| PID 20465 alive | yes (elapsed 23:55 at first inspection) | **yes (elapsed 05:20:45)** | ✅ same process, just older |
| Process command line | `dgc orchestrate-live` from `~/dharma_swarm_lf5/.venv` | unchanged | ✅ |
| `~/.dharma/daemon.pid` | removed during shutdown attempt (`00C`) | still removed | ✅ no new race |
| `~/.dharma/state/runtime.db` mtime | (not measured pre-slice-1) | `Apr 26 15:23:51` (daemon-driven, before my test runs at 16:24) | ✅ tests did not write here |
| Operator API (PID 95582) | alive (3-day elapsed) | unchanged | ✅ |

No `dgc` commands run. No `~/.dharma/` writes. No SIGTERM/SIGINT/SIGKILL. Tests use `tmp_path` exclusively — verified by source inspection (§4) and confirmed by `runtime.db` mtime predating the test runs.

**Verdict:** daemon untouched.

---

## 9. Method-placement spot check — verified ✅

Each new producer method is defined at expected helper-block locations, and each call site is in one of the three target methods (`_assign_dispatch`, `_execute_task`, `_handle_task_failure`):

| Line | Enclosing method | Role |
|---:|---|---|
| 685 | `_ensure_runtime_run_id` (def) | helper |
| 719 | `_record_runtime_task_claim` (def) | helper |
| 765 | `_record_runtime_delegation_run` (def) | helper |
| 1743 | `_handle_task_failure` | mark claim `failed` |
| 1750 | `_handle_task_failure` | mark run `failed` |
| 2006 | `_assign_dispatch` | record initial claim `claimed/assigned` |
| 2094 | `_assign_dispatch` | update claim to `running` |
| 2149 | `_execute_task` | record run `running` |
| 2222 | `_execute_task` | update claim to `completed` |
| 2227 | `_execute_task` | update run to `completed` |

No call sites in unrelated methods. **Verdict:** placement is exactly per `02_STRUCTURED_TABLE_PRODUCER_GAP.md` §4–§5.

---

## 10. Open follow-ups (not blocking slice 1)

### Minor scope observations on slice 1

1. **`telos_graph.get_by_name()` deferred.** `03_MATRIX_REVIEW.md` §3 listed it as eligible for slice 1 because it closes a known `INTERFACE_MISMATCH_MAP` DEGRADED entry. Codex omitted it, scoping slice 1 strictly to producer wiring. Defensible. Suggestion: either fold the `get_by_name` 4-line addition into the slice-1 commit before push, or land it as slice 1.5 with `tests/test_telos_graph.py`.
2. **Public `runtime_state` accessor on `SessionLedger` deferred.** `03_MATRIX_REVIEW.md` §3 / `IDLE_REVIEW_PROMOTION_RISK.md` §3 noted private coupling to `_runtime_state`. Codex added `_runtime_state_store` on `Orchestrator` instead (still private, but at the consuming side). Acceptable as long as the test coverage holds the contract. Cleanup target for a later slice.
3. **Python interpreter mismatch persists.** Slice 1 reproduces under Python 3.13 (the worktree's `.venv` / miniforge default). LF5 daemon runs Python 3.14. Slice 1's correctness is proven only on 3.13. Recommendation: pin a CI gate or add a `tox`/`nox` 3.13+3.14 matrix before push.
4. **Algedonic legacy in `_handle_task_failure`.** Codex's report §7 notes "a fully exhausted `_handle_task_failure` path still contains legacy home-directory algedonic persistence." The new tests do not exhaust retries, so this code path is not exercised by slice 1. If algedonic writes go to `~/.dharma/`, this is a latent test-isolation hole. Worth a flag for slice 3 (LEDGER_WATCHER) or a small targeted patch with a temp algedonic dir.
5. **`lancedb` warning.** Codex's standalone proof emits `lancedb not installed`. Non-fatal; flagging for completeness.
6. **No commit yet.** Slice 1 is uncommitted in the working tree. Recommend committing before slice 2 begins so the slice boundary is preserved in git history (and so any slice-2 regression can be bisected). Per the standing rule, no `git add` / commit happens here without explicit approval.

### What slice 2 must do

Per `02_STRUCTURED_TABLE_PRODUCER_GAP.md` §6 and `03_PRODUCER_WIRING_RESULT.md` "Next Structured Table Still Empty":

1. Wire `Orchestrator._persist_result()` to call `RuntimeStateStore.record_artifact()` for the provenance JSON and shared-notes / shared-markdown artifacts that `_persist_result` already writes.
2. Extend `tests/test_bootstrap_loops.py::test_task_lifecycle` to assert `artifact_records >= 1` after success.
3. Optionally add a memory-fact emission path (slice 2.5 or slice 3) — `_record_session_digest` etc.

Do **not** in slice 2:

- Promote `build_registry.py` (parallel JSONL substrate; quarantine until governance slice).
- Promote `task_contract.py` / `task_board_mirror.py` / `build_authority.py` (still slice ≥4/5).
- Touch the live daemon's `~/.dharma/`.

### What slice 3 must do (LEDGER_WATCHER)

Still unwritten. Spec from `CLAUDE_SEMANTIC_TRUTH.md` §10 + `03_MATRIX_REVIEW.md` §10. New `LEDGER_WATCHER` check in `guardian_crew.py`:

- **BLOCKER** if `session_events > 1000 ∧ task_claims = 0`.
- **DEGRADED** if `session_events > 100 ∧ task_claims = 0`.
- **WARNING** for new `~/.dharma/<feature>/` directories without registration.
- **WARNING** for stale `GUARDIAN_REPORT.md` (>24h).
- Tests must use `state_dir=tmp_path` and `create_issues=False`.

Note: now that slice 1 produces non-zero `task_claims` and `delegation_runs`, the LEDGER_WATCHER will not false-alarm at first run.

---

## Final recommendation

**PROCEED to slice 2.**

Slice 1 is a textbook narrow producer-wiring landing:

- 3-file diff (orchestrator + 2 tests).
- +209/-1 in orchestrator (vs 3,089-line LF5 file → patch, not restore).
- One new import, no LF5-only imports.
- Helper methods + call sites scoped to `_assign_dispatch` / `_execute_task` / `_handle_task_failure` only.
- Narrow `list_agents()` guard, debug-log-only.
- Real row-count assertions across 4 lifecycle stages including idempotence.
- Test isolation complete; pre-existing isolation gap in `test_session_ledger.py` incidentally fixed.
- Tests reproduce 3 + 4 + 15 = 22 passed under Python 3.13.
- Daemon (PID 20465) untouched; live `runtime.db` not perturbed by tests.

The producer gap that has been the recurring "we need a work ledger" complaint across multiple model conversations is now closed for `task_claims` and `delegation_runs`. `artifact_records`, `memory_facts`, `context_bundles`, and `operator_actions` remain at zero rows and are slice-2/3/4 work.

*End of review.*
