# DharmaGraph Handoff — CLAUDE LANE (Pregel Execution Core Closure, one PR)

**You are a fresh Claude Code instance on `/home/user/dharma_swarm` (main).** This spec is self-contained and replaces the prior Claude-lane handoff (Phase 0b/1, completed via PRs #914/#974). Campaign context: `docs/plans/DHARMAGRAPH_PHASED_SPEC_2026-07-05.md` §1–§3. Your work lands under active track `dharmagraph-engine-2026-07` (`docs/governance/ACTIVE_TRACK.yaml`). Verify any file you touch against that track's `owned_surfaces` before editing.

## 0. Before ANYTHING else (non-negotiable)

```bash
cd /home/user/dharma_swarm
make onboard   # renders live session/track state — trust it over any doc's PROSE (including this one) for live state only; owner files (docs/governance/ACTIVE_TRACK.yaml, the frozen rubric, the receipts) remain authoritative for scope, ownership, and policy (docs/AGENTS.md)
```

Then read: `CLAUDE.md` (behavioral rules), `INTERFACE_MISMATCH_MAP.md` (check every module pair you touch), `docs/governance/BUILD_SESSION_ENTRYPOINT.md`.

## 1. Mission — machine-checkable goal

Close all six **execution-core gap cards** of the frozen DharmaGraph parity rubric: **LG01 (schemas), LG04 (sequence), LG06 (superstep atomicity), LG07 (send_timeout), LG08 (command_parent/resume), LG09 (remaining_steps)**. Current judge-signed score: 52.00/100 (`reports/governance/dharmagraph_parity/judge_receipt.json`, seed 20260711, langgraph pinned 1.2.4). These six cards carry weight 12, currently earning 6.0; closing all six to 2/2 yields **58.00/100** — the execution-core ceiling. Closure condition per card (receipt `gaps[].closure_condition`): "All frozen facets prove 2/2 in an independent judge rerun."

**Done means this exits 0 on the branch head:**

```bash
cd /home/user/dharma_swarm
python3 scripts/governance/dharmagraph_parity_gauntlet.py --check   # must print {"check": "PASS", "findings": []}
python3 - <<'EOF'
import json, sys
r = json.load(open("reports/governance/dharmagraph_parity/judge_receipt.json"))
rows = {g.get("id"): g for g in r.get("capabilities", [])}
core = ["LG01","LG04","LG06","LG07","LG08","LG09"]
if not all(c in rows for c in core):
    sys.exit(1)  # any core row not located == FAIL, never a pass
ok = float(r["score"]["display"].split("/")[0]) >= 58.00
missing = [c for c in core if rows[c].get("points") != 2]
sys.exit(0 if ok and not missing else 1)
EOF
```

(Verified against the committed receipt 2026-07-17: `capabilities` is a root-level list of 41 rows keyed by `id` with integer `points`; the block exits 1 on the current 52.00 receipt with all six core rows located, and 0 on a simulated all-2/2 ≥58.00 receipt.) You may adjust the JSON paths in this checker ONLY if the receipt schema itself changes and ONLY so that all six core rows are actually located; the script MUST hard-fail (`sys.exit(1)`) if any of the six ids cannot be found. Never weaken the `>= 58.00` or `points == 2` conditions.

Prerequisite mechanics: a `missing` facet closes only when (a) the Dharma public surface resolves at `dharma_swarm.graph:<facet>` or via `_DHARMA_SUPPORTED_SURFACE` (`tests/oracle_support/dharmagraph_gauntlet.py:1089-1112`) AND (b) new **executed two-arm evidence** is applied to it in `dharmagraph_gauntlet.py`. A `_DHARMA_SUPPORTED_SURFACE` entry may only target a surface introduced or wired this run AND exercised by an executed two-arm workload applied to that same facet in the same slice. The harness is inside the sealed `RELEVANT_SOURCE_ROOTS` digest (`scripts/governance/dharmagraph_parity_gauntlet.py:57-70`), so harness extension + commit + builder/judge reseal is the only closure path. The two `fail` facet clusters (LG06 step atomicity via `x_after_failed_step`, `dharmagraph_gauntlet.py:1695-1699`; barrier overlap `:1670-1686`) close by fixing engine semantics until the existing seeded workloads match.

## 2. Context re-entry protocol (fresh iteration, < 5 minutes, in order)

1. `cd /home/user/dharma_swarm && make onboard`
2. Read this file: `docs/plans/handoffs/DHARMAGRAPH_HANDOFF_CLAUDE.md`
3. Read the **PROGRESS LEDGER section at the bottom of this same file** (created in S0; append-only, one block per iteration: `slice / result / verify / learned / blocked`)
4. `git log --oneline -15 && git status && git branch --show-current` — git is truth, ledger is claim; reconcile, fix ledger if they disagree. Expected branch: `claude/dharmagraph-pregel-core`.
5. Run the VERIFY-SLICE block (§4.0). If red, fixing red IS this iteration's task.
6. Else pick the first TODO slice whose deps are DONE. Do ONLY it. One slice per iteration; never start slice N+1 with slice N red.

## 3. Global invariants (MUST-HOLD, checked every slice)

From Pregel/BSP theory and langgraph 1.2.4 source. All `pregel/*` line references below are against `langgraph==1.2.4`; after S0 installs the `test-oracle` extra, read the source from the installed package: `python3 -c "import langgraph, inspect, os; print(os.path.dirname(inspect.getfile(langgraph)))"`. Behaviors tagged "empirical" were verified 2026-07-17 by running minimal graphs against langgraph 1.2.4 directly; re-derive any of them the same way if in doubt — never guess semantics.

- **Barrier visibility.** Channel updates from superstep N are visible only in N+1; channels immutable for the duration of a step; nodes read a snapshot fixed at step start (`pregel/main.py:2930-2934`). Conditional edges mid-step see snapshot + own writes only (`pregel/_algo.py:188-224`).
- **Determinism.** Write application sorted by stable task path, never by completion order (`pregel/_algo.py:253-256`); task ids deterministic in (checkpoint_id, ns, step, path); Send merge order = emission order (`_algo.py:294-323`). No clock/uuid/rng in reducers.
- **Checkpoint placement.** One checkpoint per superstep, written only at the boundary AFTER all writes applied (`pregel/_loop.py:676-714`); never mid-step.
- **Error atomicity.** A regular task exception cancels remaining tasks and aborts the superstep: zero channel updates applied, no loop checkpoint; successful siblings' writes are PERSISTED as pending writes but NOT applied; on resume, succeeded tasks are not re-executed — only failed tasks re-run (`pregel/_runner.py:574-636`; `pregel/_loop.py:654-657`; empirical).
- **Version monotonicity.** One global version bump per step stamped on every touched channel; node scheduled iff a trigger channel version exceeds `versions_seen` (`pregel/_algo.py:271-282, 1264-1275`); each (node, channel-version) pair triggers at most one execution.
- **Recursion off-by-one.** With `recursion_limit` N, exactly N supersteps execute before `GraphRecursionError`; a graph needing S supersteps requires limit ≥ S+1 (out-of-steps check precedes done check, `pregel/_loop.py:599-602`; empirical).

**Property-based tests (Hypothesis, new file `tests/test_graph_pregel_properties.py`, added incrementally across slices — property_test_files is an UP-ratchet, this helps).** Bound every property: `@settings(max_examples=25, deadline=None)` or tighter, explicitly seeded, <10s locally — tests.yml enforces a 30s per-test timeout; precedent is #974's bounded Hypothesis slice.

1. Permutation invariance: any task-completion order within a superstep yields byte-identical final channel values and checkpoints.
2. Isolation: two parallel nodes reading a shared channel each observe only the pre-step value.
3. Step atomicity: if any task fails, channel values and versions equal pre-step values; resume reruns only failed tasks and converges to the never-failed result.
4. Checkpoint-resume equivalence: kill after any superstep k, resume from checkpoint k → final state identical to uninterrupted run.
5. Reducer batching invariance: `reduce(reduce(s,xs),ys) == reduce(s, xs+ys)` for all batchings.
6. Version monotonicity / exactly-once: versions strictly increase; `versions_seen <= channel_versions`; no double-trigger.
7. Quiescence: halt exactly when a plan selects zero tasks; a later external write reactivates exactly the subscribers.
8. Replay determinism: identical input + seed ⇒ identical (step, sorted task ids, writes) trace.

## 4. Slices (dependency order; one commit per slice)

### 4.0 VERIFY-SLICE (run after every slice before committing; committed receipts stay untouched)

```bash
cd /home/user/dharma_swarm
python3 -m pytest tests/test_graph_neutral_core.py tests/test_graph_neutral_routing.py tests/test_graph_neutral_cycles_resume.py tests/test_graph_checkpoint.py tests/test_graph_persistence_kernel.py tests/test_graph_durable_invoker.py tests/test_graph_reconciler.py tests/test_graph_pregel_properties.py -q --tb=short
python3 -m pytest tests/test_langgraph_differential_oracle.py tests/test_graph_neutral_langgraph_oracle.py tests/test_dharmagraph_parity_gauntlet.py tests/test_graph_effects.py -q --tb=short --timeout=120
python3 scripts/governance/check_module_budget.py --base-ref origin/main --head-ref HEAD
python3 scripts/governance/hygiene/ratchet.py --max-baseline-age-days 45
make test-fast
```

Omit `tests/test_graph_pregel_properties.py` from the first pytest line until S2 creates it — pytest exits 4 on a missing path and that red is not a task.

**Score probe** (after the slice commit, working tree clean — do NOT commit these receipts mid-run):

```bash
python3 scripts/governance/dharmagraph_parity_gauntlet.py --emit --role builder
git diff reports/governance/dharmagraph_parity/PARITY_MATRIX.md    # confirm ONLY the target rows flipped
git checkout -- reports/governance/dharmagraph_parity/
```

### S0 — Environment, branch, ledger

- depends_on: none. touches: `pyproject.toml`/`uv.lock` only if the oracle extra install demands it (it should not).
- Do: `pip install -e ".[dev,test-oracle]"`; verify `python3 -c "from importlib.metadata import version; print(version('langgraph'))"` prints `1.2.4`; `python3 scripts/governance/dharmagraph_parity_gauntlet.py --check` → PASS on clean main; `git checkout -b claude/dharmagraph-pregel-core`; append a `## PROGRESS LEDGER` section to the bottom of THIS file; open Draft PR immediately with the §5 body skeleton — all four Coherence Delta fields substantively filled at draft-open time (describe S0's actual state), never stubbed ("TBD"/"n/a" placeholders fail the gate).
- **S0 failure = STOP THE ENTIRE RUN:** if the oracle extra won't install, the version is not 1.2.4, or `--check` is not PASS on clean main — create no branch, no PR, commit nothing; report the findings as your final message to the operator and end.
- done_when: `--check` PASS JSON recorded in the ledger; draft PR exists.

### S1 — Extract `graph/executor.py` (pure refactor)

- depends_on: S0. touches: `dharma_swarm/graph/executor.py` (new, ≤500 lines), `dharma_swarm/graph/scheduler.py` (shrink — it sits at exactly 500, zero headroom), `dharma_swarm/graph/__init__.py`.
- Contract: move task-execution internals (`_execute` path around `scheduler.py:277-306`) into `executor.py` with NO behavior change. Every later slice depends on this headroom. Precedent: PR #914 split `scheduler.py` → `persistence_runtime.py` before sealing receipts.
- done_when: VERIFY-SLICE green; score probe shows every capability row (ids, points, facet verdicts) and the total score unchanged vs main. The embedded `stable_digest` lines WILL differ — any `graph/**` edit changes `RELEVANT_SOURCE_ROOTS` (`dharmagraph_parity_gauntlet.py:57-69`) — that is expected, not a failure; compare rows and score, never whole-file bytes.

### S2 — LG06: concurrent supersteps + failure atomicity (riskiest first)

- depends_on: S1. touches: `dharma_swarm/graph/executor.py`, `dharma_swarm/graph/scheduler.py`, `dharma_swarm/graph/state.py`, `dharma_swarm/graph/persistence_runtime.py`, `dharma_swarm/graph/errors.py`, tests.
- Contract (MUST-HOLD): (1) all ready tasks of a superstep execute concurrently (`asyncio.gather` over the task set — today they are sequentially awaited, `scheduler.py:277-306`), with snapshot isolation preserved and write application in canonical commit-key order, never completion order; (2) on task failure: cancel siblings, apply zero channel writes, write no loop checkpoint, persist successful siblings' writes as pending writes, and on resume replay pending writes so succeeded tasks never re-execute (§3 Error atomicity). This is the single engine divergence behind the three executed `fail` facets — the gauntlet field `x_after_failed_step` in `seeded_error_atomicity` (`dharmagauntlet.py:1689-1699` — verify exact lines on your clone) plus `seeded_barrier_parallel_overlap` (`:1670-1686`) must now match LangGraph byte-for-byte.
- Verify: VERIFY-SLICE + score probe shows LG06 → 2 pts and LG26.atomic_writes → pass (free side-effect; LG26 stays partial — note it, don't chase it). Add properties 1–4 to `tests/test_graph_pregel_properties.py`. Add a paired dharma/langgraph failure-atomicity graph to `tests/test_graph_neutral_langgraph_oracle.py`.
- done_when: score probe shows LG06 row at 2.00 earned (2/2).

### S3 — LG01: typed state/input/output/context schemas

- depends_on: S1. touches: `dharma_swarm/graph/schema.py` (new, ≤500), `dharma_swarm/graph/channels.py` (346 lines, ~150 headroom: add generic reducer channel), `dharma_swarm/graph/compiler.py` (457 — minimal additions only), `dharma_swarm/graph/executor.py` (context injection), `dharma_swarm/graph/__init__.py` (export `typed_state_schema`, `input_schema`, `output_schema`, `context_schema` surfaces or register them in `_DHARMA_SUPPORTED_SURFACE` under the §1 constraint), gauntlet + tests.
- Contract: typed schema (TypedDict/dataclass/Pydantic) compiles to one channel per annotated key; `Annotated[T, reducer]` → reducer channel with batching-invariant fold; unannotated → last-value with `InvalidUpdateError` on >1 concurrent write (empirical). Input/output schemas are projections (validate/filter on seed, filter on result). Context schema: runtime context injected into nodes, never part of state, never checkpointed. Partial updates already exist (`routing.py:200-220`) — do not rebuild.
- Verify: new seeded two-arm workload(s) in `tests/oracle_support/dharmagraph_gauntlet.py` exercising typed schema + I/O projection + context on BOTH runtimes; evidence appliers mapping to the four LG01 facets. Property 5 lands here.
- done_when: score probe shows LG01 at 4.00 earned (2/2).

### S4 — LG04: `sequence` surface

- depends_on: S3. touches: `dharma_swarm/graph/compiler.py` or `dharma_swarm/graph/schema.py` (thin `add_sequence` helper), `__init__.py`, gauntlet.
- Contract: read the frozen facet text in `docs/langgraph_parity/DHARMAGRAPH_PARITY_GAUNTLET_RUBRIC_V2.json` first; mirror langgraph `add_sequence` (chain of nodes with implicit edges) with two-arm executed evidence extending the linear workload.
- done_when: score probe shows LG04 at 2.00 earned (2/2).

### S5 — LG09: `remaining_steps`

- depends_on: S3. touches: `dharma_swarm/graph/schema.py` (managed value), `dharma_swarm/graph/scheduler.py`/`executor.py`, `__init__.py`, gauntlet.
- Contract: a schema-annotated managed value injecting the remaining superstep budget at plan time; MUST reproduce the off-by-one (§3 Recursion): limit N ⇒ N supersteps execute; S-superstep graph fails at limit S, passes at S+1 (empirical). Budget resets on resume (`pregel/_loop.py:1676-1677`).
- done_when: score probe shows LG09 at 1.00 earned (2/2).

### S6 — LG07: `send_timeout`

- depends_on: S2. touches: `dharma_swarm/graph/executor.py`, `dharma_swarm/graph/routing.py` (281 lines, headroom), `__init__.py`, gauntlet.
- Contract: read the rubric facet text FIRST, then derive exact semantics from langgraph 1.2.4 installed source. Send tasks are isolated PUSH tasks with deepcopied args executing in superstep n+1 (`pregel/_algo.py:962-997`; already implemented, `routing.py:73-90`) — add only the timeout behavior the rubric names. If the rubric text plus lg source do not settle the behavior: STOP-condition (§7), document, move on.
- done_when: score probe shows LG07 at 1.00 earned (2/2), or a documented STOP entry.

### S7 — LG08a: `command_resume`

- depends_on: S2. touches: `dharma_swarm/graph/interrupts.py` (new, ≤500), `dharma_swarm/graph/routing.py` (`resume` field — currently explicitly deferred at `routing.py:100-102`), `dharma_swarm/graph/executor.py`, `dharma_swarm/graph/persistence_runtime.py`, `__init__.py`, gauntlet.
- Contract: `Command(resume=v)` without a checkpointer → error (`pregel/_loop.py:893-896`); any Command input operates on checkpointed state and does not re-trigger START edges (empirical); resume re-executes the interrupted node from the top with recorded values returned by call order, task-scoped (`types.py:811-934`); interrupt id deterministic from checkpoint namespace. Implement interrupt-as-write minimally (reserved channel + typed raise) — ONLY what `command_resume` evidence requires; full LG20 is out of scope, but the primitive must be real and engine-wired, not probe-only.
- done_when: score probe shows the `command_resume` facet pass.

### S8 — LG08b: `command_parent` (heaviest, most design risk — last)

- depends_on: S7. touches: `dharma_swarm/graph/subgraph.py` (new, ≤500), `dharma_swarm/graph/compiler.py`, `dharma_swarm/graph/executor.py`, `dharma_swarm/graph/routing.py`, `__init__.py`, gauntlet.
- Contract: minimal subgraph-as-node with namespaced execution; `Command(graph=Command.PARENT)` raises inside the task and bubbles exactly one level (`pregel/_retry.py:618-631`); parent applies `update` through the PARENT's reducers and `goto` to parent nodes (empirical); no parent ⇒ `InvalidUpdateError("There is no parent graph")` (`pregel/_io.py:58-59`). Scope to what the two LG08 facets measure — do not build general subgraph composition (LG23 is out of scope).
- done_when: score probe shows LG08 at 2.00 earned (2/2), or documented STOP.

### S9 — Receipt reseal + PR ready (custody pattern from PRs #914/#974)

- depends_on: all prior slices resolved (DONE or STOPPED-and-logged). touches: `reports/governance/dharmagraph_parity/{builder_receipt.json,judge_receipt.json,PARITY_MATRIX.md}`, `docs/langgraph_parity/DHARMAGRAPH_JUDGE_RATIFICATIONS_V1.json`.
- Order of operations, at the FINAL head, working tree clean:

```bash
cd /home/user/dharma_swarm
python3 scripts/governance/dharmagraph_parity_gauntlet.py --emit --role builder --latest-drift
DHARMA_JUDGE_ID="claude-judge-$(git rev-parse --short=9 HEAD)" python3 scripts/governance/dharmagraph_parity_gauntlet.py --emit --role judge
python3 -c "import json; print(json.load(open('reports/governance/dharmagraph_parity/judge_receipt.json'))['judge']['signature'])"
# Append {judge_id: attestation digest} to docs/langgraph_parity/DHARMAGRAPH_JUDGE_RATIFICATIONS_V1.json
# (registry is measurement-excluded by design — ratification cannot alter the evidence it authorizes)
git add reports/governance/dharmagraph_parity/ docs/langgraph_parity/DHARMAGRAPH_JUDGE_RATIFICATIONS_V1.json docs/plans/handoffs/DHARMAGRAPH_HANDOFF_CLAUDE.md   # custody artifacts + this file's S9 ledger entry, one atomic commit
git commit -m "evidence: reseal DharmaGraph parity custody anchor at pregel-core head"
python3 scripts/governance/dharmagraph_parity_gauntlet.py --check   # paste PASS JSON into PR body
```

- If the judge emission fails reconciliation (`--emit --role judge` exits 1 on reconciliation != MATCH): do not retry blindly — re-emit builder first, then rerun judge once; if it still fails MATCH, STOP, commit nothing from S9, and mark the run ended with findings in the ledger and PR body.
- If ANY commit lands after emission (CI fixes, main sync): re-emit builder then judge at the new head in the same working tree and recommit all custody artifacts atomically (precedent chain `6644d579` → `3d9bf640` → `ba5acb7e`).
- done_when: EITHER **COMPLETE** — the §1 goal block exits 0 — OR **STOPPED-SHORT** — the reseal is committed at the honestly achieved score AND every unclosed core card has an explicit STOPPED ledger entry naming the unsettled question. In both terminal outcomes the PR is marked Ready for Review; the S9 reseal runs at whatever score was reached.

## 5. One-PR discipline

- One branch: `claude/dharmagraph-pregel-core`. One Draft PR opened at S0, marked ready only at S9. Never open a second PR. **NEVER merge — the operator merges.**
- One commit per completed slice: `feat(graph): S<N> <title>` (conventional form; never use phrases matching `wholesale restore|restore from lf5|whole.?file restore|copy entire from lf5|sync all from lf5` — hard commit-lint fail). Ledger update rides in the same commit. Green VERIFY-SLICE is the permission slip to commit.
- `[impact-checked]` token: required ONLY if a hot-path file is touched (`dharma_swarm/shakti_warrant.py:183-196` list: `swarm.py, orchestrator.py, agent_runner.py, dgc_cli.py, runtime_state.py, telic_seam.py, api/main.py, api/routers/chat.py, api/ws.py, .pre-commit-config.yaml`). `dharma_swarm/graph/**` is NOT hot. This spec touches no hot path; if a fix seems to require one → STOP condition.
- **No-drive-by rule:** zero refactors, renames, formatting, or improvements outside the current slice's `touches` list — even obvious ones. Do not touch `durable_invoker.py` (over budget — not your problem this run).
- **Discovered-bug protocol:** out-of-scope bugs get one line in the PR body's "Discovered (not fixed)" section — `file:line`, repro command. DO NOT FIX.
- PR body (prewritten skeleton, kept current every slice): **Why** (execution-core closure, 52→58, six cards) / **Surface** (files per slice) / **Coherence Delta** with all four fields substantively answered — `Organ touched`, `Declared-vs-actual gap closed`, `Proof that re-reads the map`, `New drift introduced` (placeholders like "TBD"/"n/a" fail the gate, `scripts/governance/check_pr_coherence_delta.py:21-58`) / **Verification** (pasted `--check` PASS JSON, matrix row diffs, test counts) / **Impact attestation** (n/a — no hot paths) / **Honest boundaries** (facets stopped/skipped, residual 42.00 unreachable without non-core cards) / **Pre-flight BR check** (search open PRs for any BR-id you cite — `gh pr list --state open --search "BR-NNN"` or the GitHub MCP equivalent; if none cited, say so) / **Discovered (not fixed)** / DocOps impact / Risk + rollback.

## 6. Gates you WILL hit (local reproduction before push)

- **Module budget + ratchet:** hard cap 1000/module, but `modules_over_500_lines` is a DOWN-only counter — **every new module must stay ≤500 lines**; a new >500 module fails quality-ratchet unless offset. `scheduler.py`/`persistence.py`/`reconciler.py` are AT 500: extract before adding.
- **Test hygiene:** no bare `RuntimeStateStore()` in tests (pass `db_path=tmp_path/...`); no `dgc` subprocess without `--state-dir`. No new silent `except: pass` anywhere (down-counter + delta-ratchet).
- **tests.yml:** every new test <30s, no network; `ruff check dharma_swarm/ --select=E9,F63,F7,F82` clean.
- **langgraph-oracle.yml:** path-triggered by `dharma_swarm/graph/**` and the receipts — runs the oracle suites plus `--check` custody replay. **This check WILL be red on every push between S1 and S9** (each slice changes the sealed source digest, so the committed receipts no longer replay) — that is expected and is NOT a stop condition. Never commit receipts before S9 to green it; the S9 reseal is the one and only fix.
- **Dependencies:** none needed. If one genuinely is: import-provenance allowlist + pyproject + `uv lock` regen — treat as a STOP-condition question first.
- **Onboarding admission parity:** `make onboard` must exit clean at PR head.
- Full local battery: §4.0 plus `make docops-integrity`, `make semgrep-strict`, `PR_BODY="$(cat /tmp/pr_body.md)" python3 scripts/governance/check_pr_coherence_delta.py` (keep the live PR body mirrored at `/tmp/pr_body.md`), `pre-commit run --all-files`.

## 7. Forbidden actions & stop conditions

**Frozen-rubric law.** `docs/langgraph_parity/DHARMAGRAPH_PARITY_GAUNTLET_RUBRIC_V1.json` and `..._V2.json` are UNTOUCHABLE (V2 is `FROZEN_BEFORE_V2_RESULTS`; prior scores VOID on edit). The 41-row set and per-row facet sets are immutable. The N/A exclusion registry stays empty — no operator, no exclusions.

**Judge-gaming, defined concretely — all forbidden:**
- Editing scoring, reconciliation, custody, or trust-root logic in `scripts/governance/dharmagraph_parity_gauntlet.py`. Harness additions live ONLY in `tests/oracle_support/dharmagraph_gauntlet.py`, ONLY as new seeded two-arm workloads/probes plus their evidence appliers.
- **Existing harness content is append-only:** existing `_WORKLOAD_ARMS` entries, seeded workload builders, compared fields, and facet mappings (`dharmagraph_gauntlet.py:1580-1720`) may not be edited, renamed, field-removed, or re-seeded. The LG06 `fail` facets close by fixing the ENGINE until existing workloads match — never by touching the workloads.
- Any probe that special-cases outcomes: no hardcoded facet verdicts, no `if facet == X` shortcuts, no expected-output constants. Every executed probe builds the identical seeded workload on BOTH runtimes and compares canonical JSON (`_compare_workload` pattern, `dharmagraph_gauntlet.py:867`).
- Error-parity is NOT parity: `_compare_workload` converts matching exceptions on both arms into identical `probe_error` objects that compare equal (`dharmagraph_gauntlet.py:867-883`), so a facet could "pass" without either runtime executing. Every NEW evidence applier MUST require both arms error-free before emitting a passing facet; identical errors are a FINDING to document, never a pass.
- Test-only shims: a surface exported from `dharma_swarm.graph` that exists solely to satisfy the surface probe and is not wired into the engine's `invoke()` path is gaming. Surfaces must be load-bearing.
- Weakening/deleting/`xfail`-ing existing tests; touching CTRL01 (the broken comparator MUST still mismatch).

**File-creation boundary.** The ledger lives in THIS file (owned surface). `tests/test_graph_pregel_properties.py` and `tests/test_graph_neutral_langgraph_oracle.py` are listed in the track's `owned_surfaces` (`docs/governance/ACTIVE_TRACK.yaml`) — verify that listing before creating/editing them; ownership comes from the track file, never from this handoff. Create no other new file outside `dharma_swarm/graph/**`, `tests/oracle_support/dharmagraph_gauntlet.py` (append-only, per above), and `reports/governance/dharmagraph_parity/**` (S9 only).

**Other hard limits:** no files outside track-owned surfaces (check `owns:` globs in `CLAUDE.md` / `docs/governance/ACTIVE_TRACK.yaml` — other tracks' tests, `orchestrator.py`, `swarm.py` seams are off-limits this run); no new truth stores (sqlite etc. — if unavoidable, `# spine: <role>` header per `docs/governance/ANTI_SLOP_RULES.md` Rule 2, but it should be avoidable); langgraph stays oracle-only, NEVER an engine dependency (`pyproject.toml`); runtime receipts under `~/.dharma/`, never git; no force-push, no `--no-verify`, no CI-config edits, no secrets; never edit this spec's §1 goal.

**Stop conditions (halting is success, not failure):**
- S0 failure (oracle extra won't install, version != 1.2.4, or `--check` not PASS on clean main) → STOP THE ENTIRE RUN: no branch, no PR, nothing committed; report findings to the operator and end.
- A design question the frozen rubric text + langgraph 1.2.4 source do not settle → STOP that slice, write the question in the PR body ("Open design questions") + ledger, mark slice STOPPED, move to the next slice.
- **3 consecutive failed attempts** on one facet across iterations → mark STOPPED, log what was tried, move on. A 56 or 57 with honest STOP entries beats a gamed 58.
- A fix requires a hot-path file, another track's surface, a new dependency, or weakening any gate → STOP and document.
- Verify green but score probe unchanged for 2 consecutive iterations → loop is spinning; STOP, write findings, end the run.

## 8. Definition of done (whole run)

Branch `claude/dharmagraph-pregel-core` pushed; ONE PR, Ready for Review, all §5 body fields filled, `--check` PASS JSON pasted; terminal outcome recorded as **COMPLETE** (§1 goal block exits 0: judge receipt ≥ 58.00, LG01/LG04/LG06/LG07/LG08/LG09 all 2/2) or **STOPPED-SHORT** (§1 block exits nonzero AND every unclosed core card has an explicit STOPPED ledger entry with the unsettled question — an honest 56 with STOPPED entries is a valid terminal state, a gamed 58 is not); custody artifacts + judge ratification entry committed atomically at final head; the PROGRESS LEDGER section below reconciles with `git log`; zero commits on main; PR left UNMERGED for the operator.

## PROGRESS LEDGER

Append-only. One block per iteration: `slice / result / verify / learned / blocked`.
Branch note: the remote session harness assigned `claude/dharmagraph-pregel-core-700a4x`
(suffix added by the session infrastructure); it is this spec's
`claude/dharmagraph-pregel-core` branch for all §2/§8 purposes.

### Iteration 1 — S0 (environment, branch, ledger)

- slice: S0
- result: DONE. `pip install -e ".[dev,test-oracle]"` succeeded after two environment repairs: (a) debian-owned `cryptography` 41.0.7 blocked uninstall — resolved with `pip install --ignore-installed cryptography`; (b) the session checkout was a shallow clone, so `git log -1 -- <V1 rubric>` returned the shallow boundary and `--check` failed custody ("V1 base rubric commit does not match the V2 overlay declaration") — resolved with `git fetch --unshallow origin`. Neither repair touched the repo.
- verify: `langgraph == 1.2.4`; `--check` on clean checkout (09b1a400a8fe = origin/main): `{"check": "PASS", "findings": [], "gaps": 34, "replay_stable_digest": "e865481c9ea8ee0350a50aafdaa1b0bfd5b143a31ceea6da65e9bf5dd40952b7", "score": "52.00/100", "stored_digest": "9783f9cbce333d8eabb27964ee2cd402051ec2828d0e27cc68d0217505af5917"}`
- learned: baseline matches spec §1 exactly (52.00, 34 gaps). Shallow-clone custody failure is an environment gotcha for any future remote seat — unshallow before running the gauntlet.
- blocked: nothing.

### Iteration 2 — S1 (extract graph/executor.py, pure refactor)

- slice: S1
- result: DONE. `dharma_swarm/graph/executor.py` (new, 274 lines): `_Task`, `SuperstepExecutor` with `prepare_tasks` / `run_tasks` / `trigger_writes` / `branch_writes` and private `_execute_node` / `_writes_from_result` / `_validated_dispatch_order`, all moved verbatim from `scheduler.py` (attribute access rebound via `self._graph`). `scheduler.py` 500 → 297 lines; invoke() now constructs one `SuperstepExecutor` and delegates; commit barrier, seeding, resume, checkpoints stay put. No behavior change by construction.
- verify: graph suites 159 passed; oracle+gauntlet suites 48 passed; ruff clean; module budget OK; hygiene ratchet OK. Full `tests/` sweep (30s timeout, no fail-fast): 13764 passed, 8 failed — ALL environmental in this container, pre-existing on the clean tree at 09b1a400a8fe: 6× `test_docker_sandbox.py` + 2× `test_evolution_safety.py` (no docker daemon here), plus 2× `test_chamber_gym_git_history.py` (fixture-repo scoring; fails identically with S1 changes stashed). `make test-fast` additionally flakes on `tests/conformance/test_repo_ratchet_holds.py` — pytest-timeout kill >10s under full-suite load; passes in 7s isolated; CI's own budget is 30s.
- learned: nothing outside `scheduler.py` referenced the moved internals (grep-verified), so the extraction is invisible to every consumer. Score probe deferred to just after this commit (clean-tree requirement).
- blocked: nothing.

### Iteration 3 — S2 (LG06: concurrent supersteps + failure atomicity)

- slice: S2
- result: DONE. (1) `executor.run_tasks` now runs every ready task as a concurrent asyncio task (`asyncio.wait` + FIRST_EXCEPTION); task START order = `dispatch_order` (still exactly one call/superstep); proposals are assembled in dispatch order and stable-sorted by the canonical commit key, so committed state is completion-order-invariant and byte-identical to the former sequential trace. On first failure: remaining tasks cancelled, zero commits, succeeded siblings' identities+writes attached to the raised `GraphRuntimeError` (`succeeded_*`, class defaults in `errors.py`); node-raised `CancelledError` still propagates unwrapped. (2) Scheduler `_persist_failure_remains`: journals surviving writes as a partial pending-write record (kernel path) and emits a pending-VIEW `RunCheckpoint` via `on_checkpoint` (kernel-less path) — langgraph `get_state`-after-failure parity, verified empirically (x=54 = initial+1 on both arms). (3) Failure resume: `persistence_runtime.pending_replay_plan` classifies a recovered record as full (existing replay) / partial (execute ONLY uncovered tasks against the restored pre-step snapshot, merge recorded writes ahead of live writes at the barrier — succeeded tasks never re-execute) / ambiguous (Send-multiplicity partly covered → degrade to full re-execution, stale record cleared at next checkpoint).
- verify: error arm parity True (x_after_failed_step 54/54), barrier arm parity True (overlap True/True) at seed 20260711. Graph+property suites 163 passed; oracle suites 49 passed (incl. new `test_failed_step_sibling_writes_survive_and_resume_parity`: both arms — after-failure view {"x":11,"log":["a_saw_10"]}, resume re-runs only the failed task against the PRE-step snapshot, call counts {"a":1,"b":2} equal). New `tests/test_graph_pregel_properties.py` with §3 properties 1–4, bounded (`max_examples=15, deadline=None, derandomize=True`), 4 passed in 0.7s. Module budget OK, ratchet OK. Score probe after commit.
- learned: langgraph 1.2.4 failure-resume re-enters the SAME superstep — the re-run failed node sees the PRE-step snapshot (`b_saw_10`, not 11) and succeeded siblings never re-execute; a naive "apply pending writes then re-plan" design would diverge (b would see 11). Also: the journal schema (`(channel, value)` tuples) loses per-write task identity, so a reducer channel fed by BOTH a recorded and a live task in the same failed step may interleave in recorded-then-live order rather than the never-failed canonical order — semantically convergent, byte-order refinement needs an identity-preserving journal schema (noted in PR body, not fixed; persistence.py schema is out of S2 touches). Spec nit: §4-S2 says "property_test_files is an UP-ratchet, this helps" but that counter only counts `tests/properties/`; the spec-mandated path `tests/test_graph_pregel_properties.py` (also the owned surface) leaves it flat — followed the spec path.
- blocked: nothing.

### Iteration 4 — S3 (LG01: typed state/input/output/context schemas)

- slice: S3
- result: DONE. New `dharma_swarm/graph/schema.py` (273 lines): `typed_state_schema` (schema class → channel factories; `Annotated[T, reducer]` → `ReducerChannel`, else `LastValueChannel`; TypedDict/dataclass/Pydantic-v2 supported), `input_schema`/`output_schema` (key-set projections — langgraph 1.2.4 FILTERS undeclared input keys, does not reject: verified empirically), `context_schema` (validated context type), `TypedStateGraph`/`TypedCompiledGraph` (typed front door over GraphBuilder; context injected per-invoke via a ContextVar into nodes declaring a second positional parameter — asyncio task context inheritance keeps concurrent invokes isolated). `channels.py` + `ReducerChannel` (pure associative left-fold, batching-invariant). All four facet names exported from `dharma_swarm.graph` so the default surface probe path resolves — no `_DHARMA_SUPPORTED_SURFACE` entry needed. Gauntlet: appended `seeded_typed_schema_projection` two-arm workload (typed state + I/O projection + context + unannotated-conflict rejection on BOTH runtimes) + `_apply_typed_schema_evidence` (fail-closed: probe_error on either arm keeps facets failing) + one applier call in `run_capability_probes`; nothing existing edited.
- verify: workload parity True at the derived seed (projected_output {"x":7,"log":["a","b"]} equal, all five compared fields equal). Full probe preview: LG01 → 2 points FULLY_PROVEN (all five facets pass). Graph+property suites 164 passed (property 5 reducer batching invariance added, 5 properties total); oracle suites 49 passed; module budget OK; ratchet OK; ruff clean. Score probe after commit.
- learned: langgraph's typed front door maps cleanly onto the channel substrate — the only genuinely new engine primitive was `ReducerChannel`; projections and context are wrapper concerns, load-bearing through `TypedCompiledGraph.invoke`. Empirical gotcha worth keeping: `StateGraph(input_schema=...)` silently drops non-schema seed keys (no error), so the dharma arm must filter, never validate-reject.
- blocked: nothing.
