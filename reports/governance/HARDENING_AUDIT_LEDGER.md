# HARDENING AUDIT LEDGER — codex-goal:019ec1bc

| Field | Value |
|---|---|
| Goal | `codex-goal:019ec1bc` (runtime-spine hardening final-leg audit) |
| Date | 2026-06-14 / 2026-06-15 JST |
| Mode | One-time bounded audit ledger (NOT a soak; NOT the full suite) |
| Commit | **none** — this audit made no commit, branch switch, merge, or push |
| Shared tree | `~/dharma_swarm` on `telos-ai-seed-v0-from-sandbox`, unchanged. 6 pre-existing dirty files (palantir_*, active_track_evidence*, track_portfolio.json) — none authored by this audit |
| Score cap | **70/100 preserved.** No score claim above 70 is made; the single binding red gate is proven below |

**Binding cap mechanism (re-verified):** `scripts/governance/runtime_receipt_coverage_report.py --strict` exits **1** (70→75 receipt-coverage gate FAIL). `scripts/governance/spine_dispatch_mode_report.py --strict` exits **0** (65→70 dispatch gate PASS). The receipt-coverage red gate is the sole cap at 70.

---

## 1. Per-Agent Results (Agents 1–5)

| Agent | Task | Result | Headline |
|---|---|---|---|
| 1 | A — reproduce PR #602 metamorphic failure | **CONFIRMED** | PR #602 test = exactly **20 failed / 1 passed (exit 1)**; all 20 fail on hash-equality assert at `tests/complexity/test_replay_metamorphic.py:164` — `CanonicalReplayEngine` is order-dependent across causal classes. |
| 2 | B — run metamorphic against REAL 22h-soak stream | **PARTIAL** | V1 helpers ran on the real `first-default-foundry` stream (60 events) and PASSED, but **vacuously**: real stream is a single causal class (zero non-trivial reorderings). The 22h soak left **no** event stream in the engine's default base dir. |
| 3 | D — can CI go red on a failing test | **REFUTED** | CI pytest job **DOES** go red. GitHub's default `-eo pipefail` shell makes `pytest \| tee` propagate the non-zero exit; no `\|\| true` / `continue-on-error` / `set +e` / `shell:` override masks it. Masking-pipe hypothesis refuted. |
| 4 | C — diagnose replay failure + prototype fix | **CONFIRMED** | Failure is **option (ii)**: test over-specifies hash-equality on the order-SENSITIVE internal fold, not on the engine's real order-INVARIANT contract. Re-scoped prototype passes **20/20 (exit 0)** and still catches the real defect class via injection. Recommend (ii). |
| 5 | STRESS — full PASS1/2/3 re-verification | **CONFIRMED** | 70-cap unbypassable; all 5 preserved blockers CONFIRMED against copied DB. **TWO new regressions:** the 192-test "green" slice is no longer green (1 fail, exit 1 — time-bomb test) and PR #602 MR1 is violated 20/21 seeds. |

---

## 2. Per-MR Status (MR1..MR8 — from Agent 5)

The literal label set **"MR1".."MR8" does not exist** as 8 authored metamorphic relations. Agent 5 grepped the convergence plan (`CONVERGED_PLAN_codex-goal-019ec1bc_20260614.md` = 0 hits), the 277KB progress report (0 hits), and `tests/`/`reports/` for `metamorphic` (0 hits). Exactly **ONE** metamorphic relation is authored anywhere — on unmerged PR #602.

| MR | Status | Evidence |
|---|---|---|
| MR1 | **VIOLATED** | Replay invariance under causal-class-preserving reorder. PR #602 `tests/complexity/test_replay_metamorphic.py` → exit 1, 20 failed/1 passed; hash diverges at line 164 (Base `680e350c` ≠ Reordered `70775bc7`, seed 0). `canonical_replay.py` byte-identical HEAD vs PR #602 (git diff 0 lines), so this is the engine's real fold-order dependence, not a test-branch artifact. |
| MR2 | **definition-not-found** | No second metamorphic relation authored in plan, report, or repo. (Gap, not silent pass.) |
| MR3 | **definition-not-found** | As above. |
| MR4 | **definition-not-found** | As above. |
| MR5 | **definition-not-found** | As above. |
| MR6 | **definition-not-found** | As above. |
| MR7 | **definition-not-found** | As above. |
| MR8 | **definition-not-found** | As above. |

> **Gap, stated explicitly:** the goal references an MR1–MR8 set that was never authored. MR2–MR8 are NOT "holds" — there is no relation to evaluate. Only MR1 exists, and it is violated.

---

## 3. Confirmed-vs-Refuted Blockers

### The 5 preserved production-readiness blockers — ALL CONFIRMED (Agent 5, copied DB, executable)

| # | Blocker | Verdict | Executable check (exit code) |
|---|---|---|---|
| 1 | Latest major task receipts do not all carry provider/model payloads | **CONFIRMED** | `runtime_receipt_coverage_report.py --strict --json --db <copy>` → `summary.latest_major_task_receipts_provider_model_percent=3.73`, `provider_model_coverage_complete=False` (exit 1) |
| 2 | Latest major receipts lack provider/model provenance beyond probe-selected metadata | **CONFIRMED** | same report → `latest_major_task_receipts_provider_model_provenance_percent=59.63` (grounded ~58.79; DB advanced live), `provider_model_accounted_complete=False` |
| 3 | Installed `ds-goal` wrapper default target ≠ audited checkout | **CONFIRMED** | `~/.dharma/bin/ds-goal` elif targets `$HOME/dharma_swarm_main` when `autonomy_spine.py` exists there — and it does (`/Users/dhyana/dharma_swarm_main/scripts/runtime/autonomy_spine.py`, 32631 bytes), not the audited `/Users/dhyana/dharma_swarm` |
| 4 | Wrapper target lacks sync side-effect-key hardening | **CONFIRMED** | `grep side_effect\|sync\|hardening ~/.dharma/bin/ds-goal` → exit 1 (0 matches); wrapper is a bare `exec python3 scripts/runtime/autonomy_spine.py "$@"` |
| 5 | Daemon health self-report missing `runtime_dispatch` | **CONFIRMED** | `DHARMA_RUNTIME_DB=<copy> spine_dispatch_mode_report.py --strict --json` → `daemon_health.state='missing_runtime_dispatch'`, evidence `'health JSON did not include runtime_dispatch'`, live read-only GET `http://127.0.0.1:7433/health` http_status 200 |

**Copied-DB corroboration (read-only, md5 `892151a8…` unchanged after all reads):** `runtime_receipts=8040` (grounded 8027; live daemon advanced +13), `side_effect_key` NULL/empty `7026/8040`, `delegation_run(major)=3569`, major↔idempotency join `66/3569` (grounded 44–46), `idempotency_records` total `90`. Failing strict components: `core_runtime_receipt_fields` (`missing=side_effect_key:7026`), `major_idempotency_join` (`46/3569`), `latest_major_mission_payload` (`29/161`), `artifact_or_explicit_no_artifact` (`968/3569`). `active_head_side_effect_key` PASSED.

**REFUTED:** none of the 5 preserved blockers were refuted. The one refuted hypothesis in this audit is **separate** — Task D's "CI cannot go red / masking pipe" premise (refuted by Agent 3; CI does go red).

---

## 4. NEW Defects (not among the 5 known blockers)

| # | file:line | Defect | Repro |
|---|---|---|---|
| N1 | `tests/test_spine_dispatch_mode_report.py:270` (+ `scripts/governance/spine_dispatch_mode_report.py:817-822`, short-circuit at `:766`) | **Time-bomb test broke the 192-slice.** `test_dispatch_mode_report_includes_live_census_source_gaps` now fails: asserts `live_census_state == "proof_gaps_present"`, gets `"receipt_stale"`. Test hardcodes `generated_at='2026-06-13T21:25:05Z'` (~2 days stale vs 2026-06-15) with no clock-freeze/monkeypatch of `census_payload_freshness`; `_live_census_summary` short-circuits to `receipt_stale` before evaluating proof-gap surfaces. Passed at landing 2026-06-14, rots by wall-clock. The 192-slice the conductor recorded as exit 0 is now **exit 1 (1 failed, 191 passed in 32.78s)**. | `cd ~/dharma_swarm && PYTEST_ADDOPTS='-p no:cacheprovider' python3 -m pytest -q tests/test_spine_dispatch_mode_report.py::test_dispatch_mode_report_includes_live_census_source_gaps` → exit 1 |
| N2 | `dharma_swarm/canonical_replay.py:135` (`_execute_replay`) surfaced via `tests/complexity/test_replay_metamorphic.py:164` (PR #602, unmerged) | **MR1 replay order-dependence.** `_execute_replay` folds events in raw stream order; the only order-sensitive output is `state["event_types"]` (append-ordered list, `canonical_replay.py:159/170`, serialized at `:226` `json.dumps(..., sort_keys=True)`) — every load-bearing reducer (runtime/memory/actions/audits) is already order-invariant (Agent 4 field-diff). On the production path `replay_session`→`read_envelopes` canonically re-sorts by `(emitted_at, event_id)`, so the engine's real contract holds; the test over-asserts on the pre-sort internal fold. On UNMERGED PR #602 → NOT part of the 70-cap. | `git show origin/complexity-stress/replay-metamorphic-v1:tests/complexity/test_replay_metamorphic.py > /tmp/mr1.py && PYTHONPATH=~/dharma_swarm PYTEST_ADDOPTS='-p no:cacheprovider' python3 -m pytest -q /tmp/mr1.py` → exit 1, 20 failed/1 passed |
| N3 | PR #602 `causal_class()` (key on `payload.agent_id`/`payload.source`) | **Metamorphic test is vacuous on real data.** Real runtime envelopes carry `agent_id`/`source` at TOP level (`payload.agent_id` is None), so every real event collapses to one causal class → `reorder_preserving_causal_class` yields only the identity permutation (`distinct_orderings_over_20_seeds=1`). The invariant cannot catch order-dependence on any real stream. | Import V1 helpers; load `~/.dharma/events/recursive_discovery.jsonl` (60 events, `session_id=first-default-foundry`); `causal_class` on each → all `('action.event','')`. |
| N4 | `dharma_swarm/canonical_replay.py:77,249,266` (reader) vs `operator_core/living_agent_kernel.py:52,862` (writer) | **No production writer feeds the stream replay reads.** `canonical_replay` reads `stream="runtime"` → `~/.dharma/events/runtime.jsonl`, but the only kernel writer emits to `KERNEL_EVENT_STREAM="kernel_events"`. `~/.dharma/events/runtime.jsonl` does not exist; the 22h soak persisted to `runtime.db`, not the EventLog JSONL the replay engine reads. | `ls ~/.dharma/events/runtime.jsonl` → exit 1 (No such file or directory). `grep -rn 'append_envelope.*runtime'` → no writer. |
| N5 | `scripts/governance/runtime_receipt_coverage_report.py`, `scripts/runtime/live_ops_census.py`, `scripts/governance/spine_dispatch_mode_report.py`, `dharma_swarm/orchestrator.py` | **Lint/dead-code (non-blocking).** 14 ruff errors (5 F401, 3 E402, 3 E702, 2 F541, 1 E741); 5 vulture ≥80% dead-code hits (`orchestrator.py:514`, `live_ops_census.py:34`). | `ruff check <5 hot files>` → exit 1 (14 errors); `vulture <5 files> --min-confidence 80` → exit 3 |

> N1 is the one defect that materially changes the conductor's recorded state: the "green" 192-slice is no longer green. It is a flaky/time-dependent test, not a runtime regression of shipped behavior, but it must be fixed (freeze clock / monkeypatch freshness) before the slice can be re-asserted green.

---

## 5. Files to Split (>500 lines) — Agent 5

| File | Lines | Worst-rank function (radon `-n B`) |
|---|---|---|
| `scripts/governance/runtime_receipt_coverage_report.py` | 3209 | `_print_text` F(144), `build_report` F(70) |
| `dharma_swarm/orchestrator.py` | 3028 | `Orchestrator._execute_task` F(58), `_assign_dispatch` E(36) |
| `scripts/runtime/live_ops_census.py` | 2625 | `build_live_ops_census` F(132), `_runtime_receipt_coverage_state` F(56) |
| `scripts/governance/spine_dispatch_mode_report.py` | 1279 | `_format_runtime_receipt_coverage` E(40), `_live_census_summary` E(32) |

`dharma_swarm/canonical_replay.py` = 356 lines, no D/E/F functions — clean, not a split candidate.

> Methodology note (Agent 5): radon `-n C` in the task brief is a footgun — it filters to rank C-or-simpler and HIDES the D/E/F functions. Use `-n B` (or no filter) to surface high complexity.

---

## 6. DocOps Coherence

| Check | Exit | Result |
|---|---|---|
| `python3 scripts/governance/check_track_status.py` | **0** | 11 tracks rendered, INFO only |
| `python3 scripts/governance/render_active_track_includes.py --check` | **0** | no diff |

**No test-file changes were made by this audit** (a failing test IS the finding; `canonical_replay.py`, `test_canonical_replay.py`, and the metamorphic test were all left unmodified). Therefore **no DocOps resync was triggered** — the §4.3 handoff resync requirement applies only when a test is added/changed, which did not happen here.

---

## 7. No-Excluded-Lane Confirmation

**Palantir and cybernetics_codex were NOT touched by this audit.** No `*alantir*` or `*cybernetics*` worktree directories exist at `~/dharma_swarm` root (verified, `ls` no-match). The pre-existing dirty files `scripts/research/palantir_*.py` and `tests/test_palantir_pilot.py` are operator-side working-tree changes that predate and are independent of this audit — no agent read, edited, ran, or committed them.

---

## 8. Replay Disposition (Task C)

The PR #602 MR1 failure is a real **fold-order dependence** on the internal `_execute_replay` path, driven solely by the cosmetic `event_types` list; every load-bearing reducer is already order-invariant, and the production entry point `replay_session` canonically re-sorts before folding (Agent 4 field-diff, exit 0).

| Option | Meaning | Verdict |
|---|---|---|
| (i) | Genuine replay bug — fix the engine | **REFUTED.** No load-bearing state changes under reorder; `tests/test_canonical_replay.py` stays green (14 passed). |
| (ii) | Test over-specifies — re-scope assertion to `replay_session` end-to-end disk-order-invariance | **CONFIRMED & RECOMMENDED.** Agent 4 prototype passes **20/20 (exit 0)** against the real engine; a defect-injection run (drop the canonical sort in `read_envelopes`) makes it go RED — proves it is not a vacuous green and still guards the real defect class. Land a re-scoped test as a NEW file under `tests/complexity/` with the DocOps resync handoff §4.3 requires. |
| (iii) | MR mis-stated — rewrite the causal-class relation / change the engine hash (sorted-multiset `event_types`, `max()` `final_timestamp`) | **Secondary, NOT recommended now.** Collapses into (ii): re-anchoring to `replay_session` makes the same relation true without a hot-path change. A pure (iii) rewrite alters the canonical hash for EVERY session — **requires operator approval**; NOT implemented. |

**Recommendation to John:** Approve **option (ii)**. Land Agent 4's re-scoped end-to-end test; do **NOT** merge PR #602 as-is. Defer any (iii) engine hash change to explicit operator approval. Independently, fix N3/N4 if the metamorphic guard is meant to run against real runtime data (it currently cannot — no multi-class real stream exists).

---

## 9. CI Integrity (Task D)

**CI can go red on a failing test — YES.** `/Users/dhyana/dharma_swarm/.github/workflows/tests.yml`, pytest step lines 76–83:
```
77  python -m pytest tests/ -q --tb=short \
78    -x \
81    2>&1 | tee pytest_output.txt
```
GitHub Actions default `run:` shell is `bash --noprofile --norc -eo pipefail {0}`. tests.yml sets **no** `shell:` override (`grep shell: tests.yml` → exit 1) and **no** `defaults.run.shell`. Under `pipefail` the `pytest | tee` pipe takes pytest's non-zero exit; under `errexit` the script aborts before the line-83 `tail` can swallow it. The only `|| true` in the file is the **ruff lint** step (line 66), a different non-blocking step. A failing test → pytest non-zero (with `-x`, stops at first failure) → job red.

**Fragility-by-convention note (no defect, hardening suggestion):** the red-on-fail behavior relies entirely on GitHub's implicit `-eo pipefail`. If a future edit adds `shell: sh` or a `defaults.run.shell` without pipefail, `| tee` would silently start masking failures. Recommended: add explicit `set -o pipefail` as the first line of the run block, OR `shell: bash`, to self-document the dependency. (Static analysis is sufficient to refute the masking hypothesis; a canary-push proof was NOT run — operator said no pushes this session.)

---

## 10. Landing Verdict

**Honest state for the operator:**
- The 70→75 receipt-coverage strict gate is **RED** and unbypassable (exit 1).
- All **5 preserved production-readiness blockers stand CONFIRMED** (side_effect_key missing on 7026/8040 receipts; provider/model coverage 3.73%; provenance 59.63%; ds-goal wrapper targets the wrong checkout with no sync hardening; daemon health missing `runtime_dispatch`).
- A **NEW regression (N1)** silently un-greened the 192-test slice the conductor recorded as exit 0.
- The score cap holds at **70/100** with no executable green gate to raise it.

**COMMIT-READY: no**

Conditions that would flip it to yes (each needs an executable green gate):
1. `runtime_receipt_coverage_report.py --strict` exits **0** — requires backfilling `side_effect_key` on the ~7026 receipts and getting `core_runtime_receipt_fields` + `major_idempotency_join` + `latest_major_mission_payload` + `artifact_or_explicit_no_artifact` to PASS.
2. Blocker #1 cleared: `latest_major_task_receipts_provider_model_percent` reaches the gate threshold (currently 3.73%, `provider_model_coverage_complete=True`).
3. Blocker #2 cleared: provider/model provenance beyond probe metadata reaches threshold (currently 59.63%, `provider_model_accounted_complete=True`).
4. Blocker #3+#4 cleared: `~/.dharma/bin/ds-goal` re-pointed at the audited checkout AND given sync side-effect-key hardening (currently `grep` exit 1, targets `dharma_swarm_main`).
5. Blocker #5 cleared: daemon `/health` self-report includes `runtime_dispatch` (currently `missing_runtime_dispatch`).
6. N1 fixed: 192-test slice back to exit 0 (freeze clock / monkeypatch `census_payload_freshness` so `test_dispatch_mode_report_includes_live_census_source_gaps` stops rotting by wall-clock).
7. (Separate, replay track) land the option-(ii) re-scoped metamorphic test green instead of merging PR #602 as-is.
