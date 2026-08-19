# DHARMAGRAPH PRODUCTION RUNTIME SPEC — v1.2 DELTA REVISION

**Status: DRAFT — PROPOSED_NOT_IMPLEMENTED (unchanged). This document AMENDS, and must be read with, the sealed v1.1 artifact `DHARMAGRAPH_PRODUCTION_RUNTIME_SPEC_v1_1_RECONSTRUCTED.md` (SHA-256 `d8259f9c752104dd918af2041317c6cdd556d29d4b3bd204c4b4c5f718577d3a`, 5,616 lines). The v1.1 bytes are never edited; where this revision and v1.1 conflict, this revision controls. Authority: operator ruling 2026-08-18 ("build it end to end"; bounded revision ordered 2026-08-19) via the campaign charter `~/handoffs/2026-08-18_dharmagraph_endtoend_campaign_charter.md`.**

**Baseline shift**: v1.1 cited `12212397be` (origin/main 2026-08-12). This revision re-baselines to **`1f2419a7d`** (origin/main 2026-08-19).

**Master re-baseline fact (verified 2026-08-19)**: `git diff 12212397be 1f2419a7d -- dharma_swarm/graph/ dharma_swarm/checkpoint.py dharma_swarm/workflow.py` is **empty** — the graded engine surface is byte-identical across the window. Every v1.1 engine citation remains valid verbatim; only governance/report citations drift (Amendment E).

---

## Amendment A — Part 9 labeled canon interaction (AMENDS v1.1 §9 globally; supersedes nothing inside §9's technical content)

v1.1 §9 proposes a persistence architecture (canonical SQL metadata authority, object store, KMS/HSM, external witness, effect journal) that reverses the ratified estate doctrine "snapshot-per-superstep durability over the existing runtime.db tables (zero new truth stores), with the spine receipt log as the side-effect journal" (ACTIVE_TRACK.yaml, dharmagraph-engine block) without naming it. v1.2 labels and resolves this:

**Operator ruling 2026-08-18 (campaign charter §0.3) — the profile-ladder resolution:**
1. §9's normative invariants (DG-DUR-*) and contracts are ratified as build law at every profile.
2. **DG-P0 (lab)** is built fully on the existing `~/.dharma/state/runtime.db` substrate; Litestream-class continuous replication is the P0 durability rung (single-writer SQLite + replication is a production-legitimate tier — Cloudflare Durable Objects mandate, Tailscale precedent — verified 2026-08-13).
3. **DG-P1's canonical-SQL-store substrate** is *prepared* (adapter seam per §9.5; importer per §10.1) but **activated only behind three explicit gates**: (a) an attributed always-on host, (b) the independently verified V3 seal, (c) an explicit operator spend/infra decision. Zero new truth stores exist before that gate opens.
4. Convergence note: an independent 2026-08-18 ruling on the terminal lane (#1388) reached the same law from the other direction — L1 = the existing runtime.db ledger repaired, L2 = rebuildable projection, Postgres only at the multi-host-writers tripwire. Two lanes, one doctrine.

## Amendment B — Q0 owned surfaces correction (AMENDS v1.1 §10.8.Q0)

`docs/governance/ACTIVE_TRACK.yaml` is REMOVED from Q0's agent-owned surfaces. Track cards are operator-merge territory: agents reference the file read-only and propose reconciliations exclusively via draft governance PRs (as executed by PR #1397). §10.1.4 step 6's instruction to "reconcile ACTIVE_TRACK card text" is reinterpreted accordingly: propose-by-PR, never own.

## Amendment C — Q0 executed; findings absorbed (AMENDS v1.1 §10.8.Q0 status; §10.1.4)

Q0 ran on 2026-08-18/19 (branch `agent/q0-evidence-rebaseline-20260818`, draft PR #1397, receipt `reports/governance/dharmagraph_parity/Q0_REBASELINE_20260818.json`). Findings the spec's assumptions must carry forward:
1. The card-vs-matrix discrepancy is LARGER than v1.1 recorded: **five** stale cards, not three (LG14/15/18 plus two more; enumeration in the receipt).
2. The gauntlet's stable semantic digest FAILS on post-seal main — fully attributed to `pyproject.toml`/`uv.lock` changes from #1222/#1284/#1312 (the tuple-restore itself). All 53 other manifest files byte-identical. **Digest re-anchoring belongs to the next seal ceremony**, not to any build packet.
3. The 58.00/100 seal replays exactly; it remains the only scored truth. Branch-level gauntlet runs (e.g. 64.00/100 on `agent/lg24-resurrect-20260818`) are branch evidence, never seals.
4. Environment law for all future packet lanes: fresh worktrees carry no venv; `run_python_with_repo_env.sh` falls back to system Python 3.9 which cannot import the codebase. Every lane dispatch must set `DHARMA_PYTHON` (or equivalent PATH) to a repo-venv interpreter carrying the frozen tuple.

## Open annotations (recorded, unresolved)

- The v1.1 author (remote codex agent) has not responded to the custody handshake (issue #1321) or PR #1332 as of 2026-08-19; the "1,438 lines" interim figure from its early reconstruction report remains unaccounted. These bytes are maintained by the estate's own lanes under the campaign charter meanwhile.
- V4 rubric remains DRAFT-UNRATIFIED with revision inputs enumerated (2026-08-14 review addendum); conformance authority = frozen V3 gauntlet + §8.14 CORE tests as materialized.


## Amendment E — Citation re-baseline (AMENDS every v1.1 `path:line` citation, mechanically)

1. **Engine citations** (`dharma_swarm/graph/**`, `dharma_swarm/checkpoint.py`, `dharma_swarm/workflow.py`): **valid verbatim at `1f2419a7d`** — proven by the empty engine diff above; spot-checks re-read (`graph/__init__.py:1-10`, `state.py:161-176/199-219`, `types.py:47`, `executor.py:124-237`, `routing.py:295-352`).
2. **`docs/governance/ACTIVE_TRACK.yaml` citations: shift +54 lines uniformly** (Mission Control P2/P2.1 admissions inserted above the dharmagraph block; #1325/#1346). Verified: block head 940→994; `target_closure_kind` 990→1044 byte-identical. Apply +54 to every v1.1 ACTIVE_TRACK citation (940-945→994-999; 991→1045; 1101→1155; 1153/1157/1169→1207/1211/1223; 1265-1269→1319-1323).
3. **`reports/governance/dharmagraph_parity/*`**: files reissued by #1312 (oracle-tuple restore) but cited content unchanged where spot-checked (`PARITY_MATRIX.md:1-3` byte-identical — still `58.00/100 … NOT_FINISHED`). The stable semantic digest FAILS on post-seal main (attributed to `pyproject.toml`/`uv.lock`; see Amendment C.2).
4. **`scripts/governance/dharmagraph_parity_gauntlet.py:960-976`**: byte-identical.

## Amendment F — Correction to Wave 0 PR narratives (record-keeping)

W0 resurrection PR bodies (#1394, #1398 et al.) attribute their conflict expectations to "merged Mission-Control-bridge work" in `graph/{channels,scheduler,state}.py`/`checkpoint.py`. **Correction**: no MC-bridge work has merged into the engine — the bridge exists only as open draft PR #1356; Mission Control landed as new top-level `dharma_swarm/mission_control*.py` modules (#1325/#1346) that do not touch `dharma_swarm/graph/`. The lanes' observation ("expected conflicts did not materialize") was accurate; the attribution was stale. PR bodies to be corrected at the post-merge restack.

---

## Amendment D — Reality-map replacement (SUPERSEDES v1.1 §11 in full)

## 11. Current-source reality map

**Revised at baseline `origin/main` @ `1f2419a7d` (2026-08-18, "docs: THE SINGLE TARGET v2 tournament + THE WITNESS ENGINE thesis & elevation prompt (#1383)"), superseding the v1.1 map cited at `12212397be` (2026-08-12, #1185).**

This section distinguishes existing foundations from work prescribed by this specification. It is not a substitute for a fresh implementation audit. Claim discipline is unchanged: everything this specification prescribes remains **PROPOSED_NOT_IMPLEMENTED** unless a specific line citation below says otherwise, and nothing in this section promotes any capability beyond the sealed 58.00/100 grade.

**Governing verified fact for this revision**: the graded engine surface is byte-identical between the old and new baselines. `git diff 12212397be 1f2419a7d -- dharma_swarm/graph/ dharma_swarm/checkpoint.py dharma_swarm/workflow.py` is empty (verified 2026-08-19). The newest commit touching `dharma_swarm/graph/` on `origin/main` is still `e1bb3d7b1` "feat(durable-invoker): mark fail-open dispatch receipts as unprotected (#1056)", which predates both baselines. Consequently **every `path:line` citation in the v1.1 §11 map remains valid verbatim at `1f2419a7d`**; spot-checks re-verified below.

### 11.1 Module inventory (verified at 1f2419a7d)

`dharma_swarm/graph/` contains 27 files, 6,926 lines total (`git show 1f2419a7d:<file> | wc -l`, 2026-08-19):

| File | Lines | File | Lines |
|---|---|---|---|
| `__init__.py` | 152 | `persistence.py` | 500 |
| `_persistence_io.py` | 49 | `persistence_adapter.py` | 130 |
| `_persistence_lock.py` | 37 | `persistence_runtime.py` | 417 |
| `_persistence_state.py` | 64 | `receipt_authority.py` | 172 |
| `channels.py` | 416 | `receipt_chain.py` | 125 |
| `checkpoint.py` | 232 | `reconcile_board.py` | 81 |
| `compiler.py` | 480 | `reconciler.py` | 500 |
| `durable_invoker.py` | 784 | `routing.py` | 353 |
| `effects.py` | 103 | `scheduler.py` | 436 |
| `errors.py` | 78 | `schema.py` | 343 |
| `executor.py` | 434 | `state.py` | 219 |
| `interrupts.py` | 148 | `subgraph.py` | 91 |
| `world.py` | 296 | `telos_bridge.py` | 146 |
| `types.py` | 140 | | |

Adjacent legacy engine files named by this spec's migration boundary (§9.17): top-level `dharma_swarm/checkpoint.py` (421 lines) and `dharma_swarm/workflow.py` (682 lines), likewise untouched in the baseline window.

### 11.2 Existing foundations

(All citations valid at `1f2419a7d`; items marked ✓ were individually re-read at the new baseline, the rest are covered by the empty-diff proof above.)

- ✓ Candidate/test-only status is explicit in `dharma_swarm/graph/__init__.py:1-10` ("candidate / test-only, NOT wired into the production dispatch hot path"), `dharma_swarm/graph/scheduler.py:1-30`, and `dharma_swarm/graph/executor.py:1-16`.
- ✓ User snapshots deep-copy committed channel values in `dharma_swarm/graph/state.py:161-176`; per-task branch views clone channel objects in `dharma_swarm/graph/state.py:199-219`.
- Writes group, validate, and commit by channel in `dharma_swarm/graph/state.py:88-118`; reducer validation and commit are separate executions in `dharma_swarm/graph/channels.py:213-265`.
- Parallel task execution uses `asyncio` and cancels siblings on first failure in `dharma_swarm/graph/executor.py:124-237`.
- Conditional routes reject `None`, invalid types, unmapped keys, `START`, and `Send(END)` in `dharma_swarm/graph/routing.py:295-352`.
- The scheduler accepts checkpoint callbacks and filesystem persistence in `dharma_swarm/graph/scheduler.py:104-197`, restores channels and `versions_seen` in `dharma_swarm/graph/scheduler.py:199-211`, and journals writes before applying them in `dharma_swarm/graph/scheduler.py:380-408`.
- The persistence kernel serializes per-thread checkpoint and pending-write lists under a file lock in `dharma_swarm/graph/persistence.py:148-226` and `dharma_swarm/graph/persistence.py:327-366`.
- `RunCheckpoint` contains run/graph IDs, superstep, state digest, channel snapshots, and `versions_seen` in `dharma_swarm/graph/types.py:111-140`.

### 11.3 Production gaps this specification closes

Unchanged from v1.1 — every gap below was re-confirmed open by the empty engine diff and the ✓ spot-checks:

- ✓ The current public run status vocabulary contains only `completed` (`RunStatus = Literal["completed"]`, `dharma_swarm/graph/types.py:47`); production needs the closed lifecycle defined in §8.9.
- Current quiescence returns `completed` whenever no tasks are ready (`dharma_swarm/graph/scheduler.py:343-418`); production requires a verified `HALT` termination proof.
- Cyclic execution requires a cap but the public argument is not fully canonicalized and durably charged at admission (`dharma_swarm/graph/scheduler.py:172-178`, `343-365`).
- Slow synchronous nodes without a `Send.timeout` execute inline; only timed synchronous sends are moved to a worker thread (`dharma_swarm/graph/executor.py:278-300`, `360-393`).
- File locks serialize one file mutation but do not provide a distributed run lease, never-reused epoch, branch-head CAS, attempt fence, or provider dispatch fence (`dharma_swarm/graph/persistence.py:148-226`).
- The scheduler restores checkpoint state but does not establish a signed graph manifest/topology/schema compatibility proof before execution (`dharma_swarm/graph/scheduler.py:199-211`, `dharma_swarm/graph/types.py:111-140`).
- Auto checkpoint IDs are derived from step and state digest with collision suffixing, not from an authoritative branch-head transaction (`dharma_swarm/graph/persistence.py:480-492`).
- Current low-level route errors inherit `ValueError` (`dharma_swarm/graph/routing.py:56-70`); production persistence must capture every typed routing failure through one durable failure path.

### 11.4 What landed on main between the baselines (12212397be..1f2419a7d)

31 commits landed in the window. **Zero of them touch `dharma_swarm/graph/`, `dharma_swarm/checkpoint.py`, or `dharma_swarm/workflow.py`** (`git log 12212397be..1f2419a7d --oneline -- <those paths>` returns nothing; verified 2026-08-19). What is spec-relevant:

- **`884ee4fa7` — fix(dharmagraph): restore frozen LangGraph oracle tuple (#1312).** Pins the oracle environment (`langgraph==1.2.4` / checkpoint 4.1.1 / checkpoint-sqlite 3.1.0) in `pyproject.toml`/`uv.lock`, adds `tests/test_langgraph_oracle_environment_contract.py` (47 lines), reissues `reports/governance/dharmagraph_parity/{PARITY_MATRIX.md, builder_receipt.json, judge_receipt.json}`, and records a WP-ORACLEPIN packet. This is evidence-plumbing; the score did not move.
- **`94ea91c8d` — fix(memory-plane): stop pairwise idea-link clique creation (#1129).** Touches `dharma_swarm/engine/conversation_memory.py` / `event_memory.py` — the *other* module named "engine", NOT `dharma_swarm/graph/` — plus a `seam_ledger.json` regeneration and `tests/test_graph_seam_ledger.py` adjustment.
- **Mission Control plane: `1366d819c` (#1325) + `bd779ddc1` (#1346).** #1325 adds ten new top-level `dharma_swarm/mission_control*.py` modules plus ~3,500 test lines (8,084 insertions total); #1346 admits Mission Control organism integration into `ACTIVE_TRACK.yaml` / `ACTIVE_SURFACE_MANIFEST.yaml`. **Neither touches `dharma_swarm/graph/`.** This is the future integration surface for the graph engine, not a graph change.
- **MC-bridge status — NOT LANDED (correction).** The Mission-Control-to-graph bridge exists only as open draft PR **#1356** (`agent/mission-graph-authority-hardening-v2-20260815`, "feat(graph): harden shadow Mission Control bridge"), which would add `dharma_swarm/graph/mission_control_bridge.py` + `tests/test_graph_mission_control_bridge.py` and touch `graph/persistence.py`. Discrepancy flag: PR #1398's body asserts "the merged Mission-Control-bridge work lives in `channels.py`/`scheduler.py`/`state.py`/`checkpoint.py`" — **refuted at `1f2419a7d`**: those files are unchanged since #1002/#1056 and `git grep -i mission 1f2419a7d -- dharma_swarm/graph/` finds no bridge code. Any packet citing a merged MC-bridge must first re-verify against main.
- **RSI-dispatch status — NOT FOUND on main.** No commit in the window matches `RSI` or `dispatch` in subject or body, and no RSI-dispatch code exists in the mission_control modules at `1f2419a7d` (grep verified; the only "rsi" hits are the substring inside `SCHEMA_VERSION`). If a handoff claimed an RSI-dispatch landing in this window, treat it as UNVERIFIED; RSI harness work observed only on non-main remotes (`meghadharma/rsi-worldclass-harness-20260810`, `megha-rsi/forge-chassis-v0`), outside this spec's evidence chain.
- Remainder of the window: mike/merge-lane repairs (#1364/#1374/#1375), CI truth registry (#1363), sarathi composition root `e2c545724` (#1219), genome boot packet `fc0fa8d0e` (#1326), docs/vision artifacts, dependency bumps, docops count reconciles — none engine-relevant.

### 11.5 Sealed parity state (unchanged: 58.00/100)

`reports/governance/dharmagraph_parity/PARITY_MATRIX.md` at `1f2419a7d`, header (verified): **"DharmaGraph x LangGraph parity: 58.00/100 — Verdict: NOT_FINISHED. Closeout blocked: true."** Target LangGraph `1.2.4` @ `054a6f3d8b48…`, rubric commit `9fe56ce57deb…`, graded Dharma SHA `4c83660632e8…` (the 2026-08-08 seal). 28 gap rows remain (LG02–LG35 subset, APP01–APP04, PB01).

The in-flight Q0 receipt (`Q0_REBASELINE_20260818.json` on branch `agent/q0-evidence-rebaseline-20260818`, PR #1397 — branch evidence, not merged) adds two facts every downstream packet MUST carry:

1. **Seal integrity HOLDS semantically.** Gauntlet `--check` at main `b11d0a7d4` replays **58.00/100 exactly**, deterministic across two runs; the sole `--check` FAIL finding ("stable semantic digest changed") is fully attributed to 2 of 55 manifest files — `pyproject.toml` and `uv.lock` — changed by post-seal packaging commits `884ee4fa7` (#1312), `1c2b6ddbc` (#1284), `3b2b06a07` (#1222). The other 53 graded source files are byte-identical to the seal.
2. **Card drift is real and undercounted.** Five `ACTIVE_TRACK.yaml` parity cards (LG14–LG18) still carry the earlier 31.00/100-era point values, while the sealed 58.00 receipt scores all five at 2/2. No packet may cite the card distribution without this receipt.

### 11.6 IN-FLIGHT — W0 campaign PRs #1393–#1398 (branch evidence only; nothing merged)

Wave 0 of the end-to-end campaign (charter `~/handoffs/2026-08-18_dharmagraph_endtoend_campaign_charter.md`) is open as six draft PRs, all "operator merges only". Five are **resurrections** of the 2026-08-08 structural-casualty PRs (closed in the PR-flow recovery, never merit-rejected; ancestor tips verified byte-for-byte in the Q0 receipt against shared stack base `a47c110ca`). None of this changes §11.2–§11.5: until an operator merge AND a reseal ceremony, the engine at `1f2419a7d` and the sealed 58.00 grade stand.

| PR | Branch | Resurrects | Claim (gap targets) | Delta vs `b11d0a7d4` (verified) |
|---|---|---|---|---|
| #1393 | `agent/lg11-resurrect-20260818` | #1275 @ `66814cfe7` | LG11 message handling | adds `graph/messages.py` (456 l); 1,159 insertions |
| #1394 | `agent/lg10-resurrect-20260818` | #1276 @ `a07f87235` | LG10 reducers / concurrent-write conflict policy | `channels.py` +443, `state.py`, `scheduler.py`; 1,149 insertions |
| #1395 | `agent/lg30-resurrect-20260818` | #1271 | LG30 runtime config injection (title notes prior "58.00 → 62.00" claim) | adds `graph/runtime.py` (226 l) + `graph/store.py` (189 l); 1,629 insertions |
| #1396 | `agent/lg12-resurrect-20260818` | #1274 @ `f2e5a3fea` | LG12 invocation surfaces (invoke/ainvoke policy) | `scheduler.py` +307, `schema.py`; 877 insertions |
| #1397 | `agent/q0-evidence-rebaseline-20260818` | — (governance lane) | Q0 evidence re-baseline + card reconcile (see §11.5) | receipt-only; sealed artifacts untouched (hashes recorded) |
| #1398 | `agent/lg24-resurrect-20260818` | #1273 @ `bde4a65b0` | LG24 retry policy + LG25 timeout/heartbeat | adds `graph/retry.py` (216 l) + `graph/timeouts.py` (181 l), `executor.py` +220; 2,687 insertions |

**#1398 branch gauntlet replay — 64.00/100, labeled correctly.** At branch head `a3bb2d264`, the builder-role gauntlet run (receipts emitted OUTSIDE the repo tree, nothing committed) reports `score 64.00/100, gaps 26`, with a baseline control run on a detached `origin/main` (`b11d0a7d4`) worktree reproducing `58.00/100, gaps 28`, and a row-table diff showing ONLY LG24 (0→2) and LG25 (0→2) moved — exactly +6.00, no adjacent-row regressions. **This is branch evidence, NOT a new seal**: the branch's own `--check` remains RED pending an integration reseal, the reseal ceremony is an explicitly separate campaign milestone, and the official grade at `1f2419a7d` remains 58.00/100. The branch also resolved one semantic conflict with post-ancestor main law by routing 7 watchdog effect sites through the DST effects seam, holding the seam-ledger ratchet at `bypass_total` exactly 230.

Adjacent in-flight, outside W0 but engine-touching: draft PR #1356 (shadow MC-bridge, §11.4) and PR #1362 (`feat/self-graph-wave0`, self-graph projection organ). Neither is merged; neither is evidence of capability.

### 11.7 Standing rules for consumers of this map

1. Cite the engine only at `1f2419a7d` (or a fresher fetched `origin/main`), never from a W0 branch, until the operator merges.
2. Any score other than 58.00/100 MUST be labeled branch evidence with its branch head SHA and control-run baseline, per §10.0.
3. The next reseal MUST be a full builder+judge ceremony over the merged tree, not an aggregation of per-branch replays.
4. Re-run the two refuted-claim checks (MC-bridge merged? RSI-dispatch landed?) before trusting any packet that repeats them.
