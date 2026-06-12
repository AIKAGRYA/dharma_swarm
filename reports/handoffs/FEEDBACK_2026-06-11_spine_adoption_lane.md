# Feedback Packet — spine-adoption lane, round-6 confirmation (2026-06-11)

**Lane:** `qwen/spine-adoption` @ `/Users/dhyana/dharma_swarm`
**Track:** `runtime-truth-spine-adoption-2026-06` (ACTIVE)
**Author:** resumed session (Cursor agent), continuing the rate-limited Claude Code convergence loop.

---

## (a) Where the stalled session left off

The prior session ran an iterative divergence-round convergence loop on the
5-commit spine series (newest first):

| sha | subject |
|---|---|
| `717a53340` | spine: fold round-5 minors — guarded show_new sha + surface-split note in narrative |
| `da68adb90` | spine: freshness-guarded GATE-1 witness + un-stale NATS test + narrative sync |
| `60d7736c7` | spine: bounded lock budget + injection-proof criteria + GATE-1 wired into completion |
| `040355e41` | spine: receipt persistence writes to the dispatching store + loud 0-row guard |
| `f506352b8` | spine: persist EvidenceReceipt on flagged dispatch + criterion tests + GATE-1 witness kit |

Convergence history: r1: 5 findings → r2: 5 → r3: 4 → r4: 3 → r5: DRY (2 minors,
folded into `717a53340`). Termination rule: 2 consecutive quiet rounds. The
session died mid-stream immediately after committing the round-5 minors (the
guarded `SHOW_SHA` edit in `scripts/governance/gate1_witness.sh`).

**Resume verification:** `git status` shows the spine-series files clean at HEAD
`717a53340` (the dirty/untracked files in the tree all belong to other lanes:
holon, capital_lab, chetana, forge work packets — untouched by this session).
`scripts/governance/gate1_witness.sh` was read in full and is coherent shell:
`bash -n scripts/governance/gate1_witness.sh` → exit 0. The round-5 guarded-sha
edit (lines 33–34: `SHOW_SHA=$(... | cut -c1-16)` with
`${SHOW_SHA:-UNAVAILABLE ...}` fallback) is complete, not mid-flight.

## (b) Round-6 verdict: **DRY** — the convergence loop CLOSES

Round 5 was DRY; round 6 (this round, adversarial fresh-eyes on the full series
`git diff f506352b8^..717a53340`, 12 files / +517 −22) is also DRY. Per the
2-consecutive-quiet termination rule, **the divergence loop is closed**. No
commits were made this round.

### Verifier output (named before judging, all actual command output)

| Verifier | Command | Result |
|---|---|---|
| Series test files | `.venv/bin/python -m pytest tests/test_orchestrator_spine_dispatch.py tests/test_spine_adoption_dispatch.py tests/test_spine_adoption_metric.py tests/test_spine_persistence_invariant.py -q` | **35 passed in 3.94s** |
| All spine-keyword tests | `.venv/bin/python -m pytest tests/ -q -k spine --ignore=tests/test_a2a_readiness_gate.py --ignore=tests/test_autonomous_agent.py` | **116 passed, 3 skipped, 11118 deselected in 14.22s** |
| Dropoff sources | `.venv/bin/python -m pytest tests/test_dispatch_dropoff_sources.py -q` | **11 passed in 0.29s** |
| Bypass report | `.venv/bin/python scripts/governance/spine_bypass_report.py` | **7 sites: 1 spine-adopted, 5 intentional (allowlisted), 1 non-production, 0 unknown** |
| Spine ownership guard | `.venv/bin/python scripts/uplift_guards/check_spine_ownership.py` | **"spine ownership clear (importable + all sqlite users declared)"** |
| Track criteria | `.venv/bin/python scripts/governance/check_track_status.py` | **5/8 completion criteria pass** (matches prior round; the 3 open are agent_runner import, allowlist-drain, gate1_witnessed — correctly open) |
| Witness script syntax | `bash -n scripts/governance/gate1_witness.sh` | **exit 0** |

The two `-k spine` collection excludes are NOT from this series:
`tests/test_a2a_readiness_gate.py` (untracked, another lane —
`ModuleNotFoundError: dharma_swarm.operator_core.a2a_task_lifecycle`) and
`tests/test_autonomous_agent.py` (uncommitted other-lane modification —
`ImportError: cannot import name '_resolve_agent_model_override'`). Both
pre-date this resume and live on surfaces this track does not own.

### Round-6 hunt targets (round-4/5 fixes specifically) — findings

| Target | Finding | Class |
|---|---|---|
| Freshness guard (`C > BASE` reset, gate1_witness.sh:47–52) | Correct: stale-low baselines reset to current so the watch only fires on a receipt landing after watch start. `WATCH_STARTED` captured **after** the reset — correct ordering. | dry |
| Baseline-advance (line 90) | `echo "${N}" > BASELINE_FILE` on success — a re-run of `--watch` cannot re-trigger on the same receipt. | dry |
| Empty-sha guard (`LATEST_SHA`, lines 69–70) | `[[ -z ]]` fallback present; in the fire path ≥1 receipt row exists, so the empty-input-shasum corner is unreachable. | dry |
| `SHOW_SHA` fallback (round-5 fold, lines 33–34) | Complete and coherent; `${SHOW_SHA:-UNAVAILABLE...}` covers sqlite3/shasum failure. | dry |
| Bounded lock budget (orchestrator.py:2264–2265) | `aiosqlite.connect(timeout=2.0)` + `PRAGMA busy_timeout=2000` consistent; whole persist block fail-open (warning, never breaks dispatch); imports inside the try so a missing aiosqlite also fails open. | dry |
| 0-row guard (persistence.py:70–75) | `cur.rowcount == 0` raises after commit (harmless 0-row commit); caller's fail-open turns it into the visible "NOT persisted" warning; covered by `test_spine_dispatch_zero_row_persist_is_loud_not_silent`. Sequencing verified: `record_delegation_run(status="running")` at orchestrator.py:2321 precedes the spine call, so the row exists before persist. | dry |
| Injection-proof criteria regexes (ACTIVE_TRACK.yaml) | Verified live: `check_file_contains` uses `re.search`; `(?m)^\s*from dharma_swarm\.spine` matches a2a_bridge ✓ / orchestrator ✓ / agent_runner ✗ (correctly open); the drained-dict pattern matches `= {}` and `= {\n}` but NOT the populated 5-entry dict (verified by direct re.search test). | dry |
| Surface-split note (round-5 fold) | Present and consistent in three places: gate1_witness.sh header, persistence.py docstring, narrative §"What the spine is". | dry |
| NATS test un-staling (`test_nats_is_scoped_out`) | Now accepts `joined` per the 2026-05-31 doctrine amendment + NATS lane reality; `missing`/`quarantine` still accepted for transport-absent envs. Passes. | dry |
| Flag-off path | orchestrator.py:2332–2336 — flag unset takes the original `asyncio.wait_for(runner.run_task(task), ...)` verbatim. | dry |

**Minor observations, explicitly NOT folded (loop is closed; cosmetic only):**
1. `show_new()` declares `local base="$1"` but never uses it (lint nit; output is `LIMIT 3` regardless).
2. If the baseline file ever holds a value **above** the current count (e.g. the DB was recreated), `--watch` waits against the stale-high baseline and never fires — conservative direction (it can never false-fire), and the documented operator flow (run without `--watch` first) rewrites the baseline to current. Operator escape hatch: `rm ~/.dharma/state/gate1_baseline.txt`.

## (c) Remaining operator-gated steps (exact commands)

1. **GATE 1 — witness one live EvidenceReceipt** (the 8th completion criterion;
   no agent may self-certify it):
   ```bash
   cd ~/dharma_swarm
   bash scripts/governance/gate1_witness.sh          # sets the baseline, prints count
   dgc down
   export DHARMA_SPINE_DISPATCH=1 && dgc up --background
   bash scripts/governance/gate1_witness.sh --watch  # fires when the receipt lands
   # then: commit reports/governance/GATE1_WITNESSED.md to flip the criterion
   ```
2. **Push the lane** (18 local commits ahead of `origin/qwen/spine-adoption`):
   ```bash
   git push origin qwen/spine-adoption
   ```
3. **M1 reconciliation decision** — operator call, deliberately not taken here.

## (d) Relation to the track's remaining next-items

| Track next-item | State after this series |
|---|---|
| a2a_bridge `ingest_trishula_inbox` bypass (a2a_bridge.py:307, Slice 2) | Still allowlisted in `spine_bypass_report.py::_INTENTIONAL_BYPASS`; `submit_via_spine` exists and is test-proven — the production wiring of the trishula path is the next code slice (sync→async bridging; narrative recommends dual-audit). |
| orchestrator `DHARMA_SPINE_DISPATCH` GATE 1 | **Code complete in this series**: flagged dispatch emits exactly one receipt AND persists it to `delegation_runs.receipt_json` of the dispatching store, with loud 0-row guard + bounded 2s lock budget. What remains is purely the operator-witnessed live run (step c.1) — by design no agent can close it. |
| agent_runner migration | Untouched (largest surface, last by design). `agent_runner_calls_spine` criterion correctly fails. |
| Allowlist drain → CI allow-list-at-zero | 5 entries remain (trishula, node_gateway ×2, a2a_client local, nats_transport). The `bypass_allowlist_empty` criterion is now injection-proof: it matches only the literally drained `_INTENTIONAL_BYPASS = {}` form (verified against both drained shapes and the populated form). `test_no_dropoff_sources_remain` additionally enforces allowlist freshness (a stale declared entry fails the test). |

The series also wired `gate1_witnessed` (file_exists on
`reports/governance/GATE1_WITNESSED.md`, written only by the freshness-guarded
watch) into the completion criteria — so the track cannot flip SHIPPABLE on
file/test proxies alone. 5/8 criteria pass today; the 3 open ones map exactly to
the 3 remaining work items above.
