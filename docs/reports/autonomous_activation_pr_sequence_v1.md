# Activation PR Sequence v1

**Purpose.** Brutally practical PR plan to activate the Minimal Metabolic Loop (see `autonomous_activation_minimal_metabolic_loop_v1.md`) by wiring the eleven stages in `autonomous_activation_map_v1.md`. Additive only. No new persistence surface. No new governance island. Behind feature flags. Active-track-defending.

**Sequencing principle.** Each PR ships only after the previous PR's acceptance test passes in CI and the operator has read its KaizenReview. No PR runs autonomously on the cron until **PR-A6** lands. No PR alters `evolution.py` defaults.

**Track-defense.** None of these PRs should land while `runtime-truth-spine-2026-06` blockers are open unless the operator declares `autonomous-activation-2026-07` as a parallel track in `ACTIVE_TRACK.yaml`. Default posture: **wait for truth-spine to close**.

**Total scope:** 6 PRs, ~640 LOC new code, 6 thin modules, all docs already landed.

---

## Global PR conventions

Every PR in this sequence carries the same gate row in its description:

| Gate | Required value |
|---|---|
| Branch | `devin/<YYYY-MM-DD>-<pr-slug>` |
| Onboarding receipt | Updated `docs/reports/autonomous_activation_onboarding_receipt_<date>.md` for that PR's scope |
| `~/.dharma` writes | None (Rule 1) |
| Root markdown additions | None (Rule 8) |
| Grandfathered module edits | None (Rule 10) |
| New persistence | None |
| New governance doc | None |
| `ACTIVE_TRACK.yaml` | Untouched OR explicitly extended for parallel track per CI |
| `ACTIVE_SURFACE_MANIFEST.yaml` | Declare the one new module if applicable |
| Feature flag | `DHARMA_<feature>_ENABLED` (default `false`) |
| Test fixtures | Under `tests/fixtures/<pr-slug>/` |
| Acceptance test | `tests/test_<module>.py` with green/red fixture pair |
| `evolution.py` defaults | Untouched (`shadow_mode=True`) |
| Welfare assessment | One paragraph per `Jagat Kalyan Constraint` |
| Replay command | Declared in PR description |

PRs labeled **WAIT** require an explicit external event before they can land.

---

## PR-A1 — VentureCell FSM Driver (Stage 2)

**Slug:** `devin/<date>-venture-cell-fsm`
**Stage:** 2 (Venture Cell Instantiation)
**LOC:** ~150
**Feature flag:** `DHARMA_VENTURE_CELL_FSM_ENABLED`
**Depends on:** Nothing (lands first)

### Owner surfaces

- **Reads:** `dharma_swarm/fractal/fractal_room.py` (FractalRoom, VentureCellV1, `evaluate_kill_conditions`, `evaluate_spinout_conditions`)
- **Reads:** `docs/governance/VENTURE_CELL_REVENUE_WEDGE.md` (YAML config)
- **Writes:** New file `dharma_swarm/fractal/venture_cell_fsm.py`
- **Emits:** `runtime_state.SessionEventRecord` (existing table, append-only)

### Touched files

- `dharma_swarm/fractal/venture_cell_fsm.py` — **NEW** (~150 LOC)
- `tests/test_venture_cell_fsm.py` — **NEW**
- `tests/fixtures/venture_cell_fsm/{green,red}.json` — **NEW**
- `ACTIVE_SURFACE_MANIFEST.yaml` — declare module under `services`

### Behavior

Pure FSM with explicit transitions: `proposed → activating → autonomy_1 → autonomy_2 → autonomy_3 → autonomy_4 → autonomy_5 | dissolved`. Each tick reads current cell KPIs, evaluates kill+spinout conditions, **proposes** transition. Proposals appended to `runtime_state.SessionEventRecord` as event type `venture_cell_fsm_proposal`. **Operator must approve via `operator_actions` table before transition lands.**

### Kill condition (for the FSM itself, not the cells)

- If `runtime-truth-spine-2026-06` track shows blockers in `ACTIVE_TRACK.yaml` `next_blockers`: FSM evaluator skips with reason `"deferred_to_active_track"`.
- If `DHARMA_VENTURE_CELL_FSM_ENABLED != "1"`: FSM evaluator skipped.
- If FSM proposes >3 transitions in 7 days for the same cell: auto-disable + alert (`shakti_warrant` pressure signal).

### Rollback strategy

- Single new module. `git revert <commit>`.
- Feature flag default off — even if module lands, no behavior change until operator flips flag.
- No data migration. No persistence schema change.

### Benchmark / KPI

- **Pass:** FSM correctly classifies green fixture → proposes `autonomy_1 → autonomy_2`; red fixture (revenue=0, days_active=70) → proposes `dissolved`.
- **Fail:** FSM proposes transition not justified by KPI; FSM writes to any persistence other than `SessionEventRecord`; FSM auto-applies transition without operator approval.

### Acceptance criteria

1. `pytest tests/test_venture_cell_fsm.py -q` exits 0
2. Green/red fixture pair produces opposite `NextDecision` from `closure_v0.decide_next` (provable difference, like `closure_v0` proofs)
3. CI semgrep finds no `~/.dharma` writes from new module
4. No edits to `fractal_room.py` (read-only consumer)
5. `ACTIVE_SURFACE_MANIFEST.yaml` declares new module

### Ecological cost awareness

One evaluator function call per cron tick (e.g., daily). Pure-function evaluation; no I/O beyond reading cell YAML + appending one event. Estimated compute: <100ms/day. **Negligible.**

### Welfare assessment

This PR enables the kill-condition machinery — explicitly anti-bloat. Welfare-positive: cells that fail to produce value will be dissolved promptly rather than lingering and draining budget.

### Replay command

```bash
pytest tests/test_venture_cell_fsm.py::test_green_path_progresses tests/test_venture_cell_fsm.py::test_red_path_dissolves -q
```

---

## PR-A2 — WorkPacket Proposer (Stage 4)

**Slug:** `devin/<date>-work-packet-proposer`
**Stage:** 4 (Task Generation)
**LOC:** ~120
**Feature flag:** `DHARMA_WORK_PACKET_PROPOSER_ENABLED`
**Depends on:** PR-A1 merged

### Owner surfaces

- **Reads:** `closure_v0.WorkPacket` schema, `closure_v0.TelosObjective`, `closure_v0.VentureCellRef`
- **Reads:** noticer outputs (`reports/agentops/<noticer>/` proposal cards) — if any present
- **Writes:** New file `dharma_swarm/operator_core/work_packet_proposer.py`
- **Writes:** Packet JSON files to `agentops_packets/<date>/<packet_id>.json` (new directory, but it is *operator-facing input directory* for AgentOps runner, NOT a runtime persistence surface — same pattern as existing AgentOps usage)

### Touched files

- `dharma_swarm/operator_core/work_packet_proposer.py` — **NEW** (~120 LOC)
- `tests/test_work_packet_proposer.py` — **NEW**
- `tests/fixtures/work_packet_proposer/{green,red}.json` — **NEW**
- `ACTIVE_SURFACE_MANIFEST.yaml` — declare module

### Behavior

Takes a `CardProposal` dict (from noticer; for v0 may be operator-handed JSON) and constructs a valid `closure_v0.WorkPacket` with: correlation_id (generated), telos_objective (`jagat_kalyan`), cell_id (passed), allowed_paths (passed), forbidden_paths (always includes spine surfaces + `~/.dharma/**` + `dharma_swarm/telos_gates.py`), acceptance_test (required), rollback_plan (required), review_tier (defaults `review`). Writes packet JSON to `agentops_packets/<date>/<packet_id>.json`. **Does not run packet**; only writes file for operator to run via AgentOps.

### Kill condition

- If proposer generates >10 packets/day on same cell: auto-disable + alert.
- If feature flag off: proposer skipped.
- If `objective_id != "jagat_kalyan"`: refuse to generate.

### Rollback strategy

- Single new module + new directory `agentops_packets/`. Empty directory rollback by `rm -rf agentops_packets/` if needed.
- Feature flag default off.

### Benchmark / KPI

- **Pass:** Green fixture (valid card) → valid `WorkPacket` JSON; rejected card (missing acceptance_test) → raises `ClosureContractError`.
- **Fail:** Packet generated with overlap in allowed/forbidden paths; packet missing correlation_id; packet writes outside `agentops_packets/`.

### Acceptance criteria

1. `pytest tests/test_work_packet_proposer.py -q` exits 0
2. Proposer cannot generate packet that would mutate spine/telos/economic-engine surfaces (CI test asserts all `forbidden_paths` include these)
3. Generated packet round-trips through `WorkPacket(**json.load(...))` without raising
4. CI semgrep finds no `~/.dharma` writes

### Ecological cost awareness

JSON generation; <50ms per packet. **Negligible.**

### Welfare assessment

Welfare-positive: every packet carries explicit rollback_plan and forbidden_paths; reduces probability of agentic runs touching wrong surfaces.

### Replay command

```bash
pytest tests/test_work_packet_proposer.py -q
```

---

## PR-A3 — Kaizen Auto-Publisher (Stage 7)

**Slug:** `devin/<date>-kaizen-auto-publisher`
**Stage:** 7 (Benchmark / KPI Evaluation)
**LOC:** ~80
**Feature flag:** `DHARMA_KAIZEN_AUTO_PUBLISH_ENABLED`
**Depends on:** PR-A2 merged (so there are packet runs to review)

### Owner surfaces

- **Invokes (subprocess):** `scripts/governance/kaizen_review_from_agentops.py`
- **Reads:** `reports/agentops/<job>/<ts>/report.json`
- **Writes:** New file `dharma_swarm/operator_core/kaizen_publisher.py`
- **Writes:** `reports/kaizen/<job>/kaizen_review.{json,md}` (existing destination)
- **Writes:** `reports/kaizen/index.json` (existing pattern; lock-protected append)

### Touched files

- `dharma_swarm/operator_core/kaizen_publisher.py` — **NEW** (~80 LOC)
- `tests/test_kaizen_publisher.py` — **NEW**
- `tests/fixtures/kaizen_publisher/{green,red}/` — **NEW** (mirror existing kaizen fixtures)
- `ACTIVE_SURFACE_MANIFEST.yaml` — declare module

### Behavior

When a new `reports/agentops/<job>/<ts>/report.json` lands, invoke `kaizen_review_from_agentops.py` via subprocess with declared args. Append a one-line entry to `reports/kaizen/index.json` with file lock. **No new persistence schema** — uses existing kaizen output dir.

### Kill condition

- Subprocess timeout >60s → abort; log via runtime_state event.
- If kaizen review writes outside `reports/kaizen/`: refuse to record in index.
- If feature flag off: publisher skipped.

### Rollback strategy

- Single new module. `git revert <commit>`.
- Index JSON has no schema (just append-only list); rollback safe.

### Benchmark / KPI

- **Pass:** Green AgentOps report → kaizen_review.json with `gate_state="green"`; red report → `gate_state="red"` and `next_recommendation` differs.
- **Fail:** Auto-publisher promotes a packet on red report; auto-publisher writes outside `reports/kaizen/`.

### Acceptance criteria

1. `pytest tests/test_kaizen_publisher.py -q` exits 0
2. Subprocess invocation argv asserted in test
3. Index file uses fcntl/portalocker file lock (or skipped if not available — degrades to no-index, not corrupt-index)
4. No `evolution.py` invocation from this module

### Ecological cost awareness

One subprocess per AgentOps report; existing kaizen review script is fast (<5s on prior fixtures). **Low cost.**

### Welfare assessment

Welfare-positive: makes every AgentOps run produce a human-readable review, increasing operator situational awareness. Reduces probability of unaudited runs accumulating.

### Replay command

```bash
pytest tests/test_kaizen_publisher.py -q
```

---

## PR-A4 — Operator Brief Publisher (Stage 8) — THE WEDGE

**Slug:** `devin/<date>-operator-brief-publisher`
**Stage:** 8 (Value Generation)
**LOC:** ~150
**Feature flag:** `DHARMA_OPERATOR_BRIEF_PUBLISHER_ENABLED`
**Depends on:** PR-A1, PR-A2, PR-A3 all merged

### Owner surfaces

- **Reads:** `daily_operating_brief.render_markdown()` output
- **Reads:** Existing `closure_v0.EvidenceReceipt` references (by `receipt_id`)
- **Reads:** Allowlist config (declared inline + extensible by operator: `_PUBLIC_SAFE_FIELDS`)
- **Writes:** New file `dharma_swarm/revenue/operator_brief_publisher.py`
- **Writes:** `revenue/publications/<date>/draft.md` + `manifest.json`
- **Writes:** Stages requiring approval → operator writes `approved.json` / `rejected.json` *manually* (no auto-write)

### Touched files

- `dharma_swarm/revenue/operator_brief_publisher.py` — **NEW** (~150 LOC)
- `tests/test_operator_brief_publisher.py` — **NEW**
- `tests/fixtures/operator_brief_publisher/internal_brief.md` — **NEW**
- `tests/fixtures/operator_brief_publisher/expected_redacted.md` — **NEW**
- `ACTIVE_SURFACE_MANIFEST.yaml` — declare module

### Behavior

Converts internal `daily_operating_brief` markdown to a publication-safe candidate:

1. Section allowlist: only `"What happened"`, `"Value produced"` (numbers redacted to ratios), `"Hot items: next-move"` (sanitized). Sections excluded: `"Burn / cost signals"` (absolute), `"Human YDS ratings"` (private), `"What should stop"` (internal).
2. Path redaction: strip every `~/.dharma/...` and `dharma_swarm/...` reference; replace with `<receipt:abc123>` footnote.
3. Customer/contact redaction: regex-strip emails, GitHub handles not on allowlist.
4. Receipt footnote attachment: for every cited fact, append `[^receipt-id]` footnote with just `receipt_id` + `correlation_id`.
5. Writes `draft.md` + `manifest.json` (cited receipts, redaction hash, source `daily_brief.md` hash).

### Kill condition

- Redaction allowlist test fails → block publication (test asserts no `~/.dharma`, no `/Users/`, no `dharma_swarm/spine/` in output).
- Manifest receipt count == 0 → block (require at least 1 receipt reference per issue).
- Feature flag off → skipped.
- Welfare gate red (a `kaizen_review.json` showing `welfare_tons < 0` in last 7 days) → block.

### Rollback strategy

- Single new module; new directory `revenue/publications/`. `git revert <commit>` + `rm -rf revenue/publications/`.
- No external account creation in this PR; publish is operator-manual.

### Benchmark / KPI

- **Pass:** internal_brief.md fixture → matches expected_redacted.md byte-for-byte; no leaked paths; manifest contains ≥ 1 receipt; STEELMAN gate input (counterargument paragraph) present.
- **Fail:** any leaked path; any failure of redaction allowlist; manifest missing receipt.

### Acceptance criteria

1. `pytest tests/test_operator_brief_publisher.py -q` exits 0
2. Fixture round-trip equality (byte-for-byte after normalized newlines)
3. CI semgrep rule asserts no `subprocess.run` to external services in this module
4. `forbidden_paths` declared on the AgentOps packet that runs this module includes all internal substrate

### Ecological cost awareness

Text processing only; <500ms per brief. **Negligible.**

### Welfare assessment

**This is the welfare-critical PR.** Jagat Kalyan Constraint applies. Publication is the first artifact reaching real readers. Welfare-positive iff: (a) every claim is receipt-grounded; (b) no harmed party named; (c) no clickbait/adtech patterns; (d) STEELMAN gate enforces counterargument inclusion; (e) free issues first; pricing only after demonstrated reader value. Mitigated by mandatory human approval before publish.

### Replay command

```bash
pytest tests/test_operator_brief_publisher.py -q
```

---

## PR-A5 — World-Model Witness Adapter (Stage 10)

**Slug:** `devin/<date>-world-model-witness`
**Stage:** 10 (World-Model Update)
**LOC:** ~60
**Feature flag:** `DHARMA_WORLD_MODEL_WITNESS_ENABLED`
**Depends on:** PR-A3 merged

### Owner surfaces

- **Reads:** `closure_v0.NextDecision`, `closure_v0.VSMProjection`, `closure_v0.KaizenReviewLink`
- **Writes:** `runtime_state.SessionEventRecord` event type `world_model_witness`
- **Writes:** New file `dharma_swarm/operator_core/world_model_witness.py`

### Touched files

- `dharma_swarm/operator_core/world_model_witness.py` — **NEW** (~60 LOC)
- `tests/test_world_model_witness.py` — **NEW**
- `tests/fixtures/world_model_witness/triple.json` — **NEW**

### Behavior

Takes the (VSMProjection, KaizenReviewLink, NextDecision) triple after each `decide_next` call and emits a single `SessionEventRecord` of type `world_model_witness` with the three IDs and timestamp. **No payload duplication** — only refs by ID. Consumable by `subconscious_v2.run_dream_cycle` (already reads `runtime_state` events). No schema migration.

### Kill condition

- If feature flag off: skip.
- If any of the three refs is missing/empty: refuse to emit (raise `ClosureContractError`).

### Rollback strategy

- Single new module. Event records are append-only and forgiving of unknown event types — old consumers won't break if module is reverted.

### Benchmark / KPI

- **Pass:** Triple fixture → exactly one `SessionEventRecord` row of type `world_model_witness` with three correct IDs; subsequent `dream_cycle` test (mocked) can read the event.
- **Fail:** Witness writes outside `runtime_state`; witness writes payload (only refs allowed).

### Acceptance criteria

1. `pytest tests/test_world_model_witness.py -q` exits 0
2. Asserts no payload in event record (refs only)
3. No mutation of any existing event row

### Ecological cost awareness

One row per decision; <10ms. **Negligible.**

### Welfare assessment

Welfare-neutral with positive long-term effect: increases world-model coherence by linking decisions to projections and reviews. Cannot publish or extract; safe.

### Replay command

```bash
pytest tests/test_world_model_witness.py -q
```

---

## PR-A6 — Cron Scheduler Registration **(WAIT)**

**Slug:** `devin/<date>-operator-brief-cron`
**Stage:** Composition (Trigger for the loop)
**LOC:** ~30
**Feature flag:** `DHARMA_OPERATOR_BRIEF_CRON_ENABLED`
**Depends on:** PR-A1 through PR-A5 merged, AND `runtime-truth-spine-2026-06` track closed OR operator explicitly opened `autonomous-activation-2026-07` as parallel track. **WAIT until then.**

### Owner surfaces

- **Reads/Writes:** `~/.dharma/cron/jobs.json` (existing scheduler) — appends one job entry
- **Reads:** `cron_runner.py` registry — registers handler `operator_brief_publish`
- **Touches:** Existing `cron_runner.py` to register handler (only adds to `_HANDLERS` dict; no logic edits)

### Touched files

- `dharma_swarm/cron_runner.py` — **MODIFIED** (single line: handler registration; +1 LOC)
- `tests/test_operator_brief_cron.py` — **NEW**

### Behavior

Registers cron handler `operator_brief_publish` which: (1) reads internal brief; (2) generates publication candidate via PR-A4 module; (3) writes draft + manifest. **Does NOT publish externally**; operator still approves manually.

### Kill condition

- Feature flag off → cron handler is registered but no-ops.
- If `revenue-wedge.autonomy_stage < 2` → handler aborts.
- If last 3 KaizenReviews on operator_brief_publish show `gate_state="red"` → handler aborts (3-strike rule).
- If `truth-spine` active-track blockers re-open → handler aborts.

### Rollback strategy

- Cron daemon reads `jobs.json` on next tick; remove job entry to disable. Module change is one line; `git revert <commit>` reverses cleanly.

### Benchmark / KPI

- **Pass:** Handler invokes PR-A4 module; produces draft; respects 3-strike kill.
- **Fail:** Handler publishes externally without approval; handler bypasses feature flag; handler edits any file outside `revenue/publications/<date>/`.

### Acceptance criteria

1. `pytest tests/test_operator_brief_cron.py -q` exits 0
2. CI test asserts `cron_runner.py` change is exactly handler registration (no logic edits)
3. CI test asserts handler honors all 4 kill conditions
4. Welfare assessment row in PR description

### Ecological cost awareness

One scheduled invocation per week (Sunday 09:00). Estimated compute per run: <30s (text rendering + git operations). **Low.**

### Welfare assessment

Welfare-positive iff PR-A4's welfare gate holds: this PR only schedules; the welfare-critical surface is PR-A4. Mandatory human-approval gate before any external publication remains in place.

### Replay command

```bash
pytest tests/test_operator_brief_cron.py -q
```

---

## What this sequence does NOT do (forbidden actions audit)

| Forbidden action (per Master Prompt) | Status |
|---|---|
| Build AGI | ❌ Not proposed. 6 PRs to wire one revenue wedge. |
| Uncontrolled self-modification | ❌ Not proposed. `evolution.py` shadow_mode=True; no PR alters this. Darwin proposer is explicitly out of this sequence (Stage 11 in map, deferred). |
| Autonomous capital deployment | ❌ Not proposed. `economic_engine.record_revenue` records only; payments human-approved. |
| Autonomous external messaging | ❌ Not proposed. Publication is operator-manual; scout_daemon already enforces human-approval for outreach. |
| Deceptive memetic engineering | ❌ Not proposed. STEELMAN gate mandates counterargument; receipt footnotes per claim. |
| Parallel governance systems | ❌ Not proposed. Three docs under `docs/reports/`; no claims over owned facts. |
| Vague recursive architecture prose | ❌ Not proposed. Every PR names files + LOC + tests. |
| New substrate creation | ❌ Not proposed. 6 thin modules, all composers. |
| Another giant meta-framework | ❌ Not proposed. ~640 LOC total. |

---

## CI gate matrix (across all PRs)

| Check | All PRs must pass |
|---|---|
| `scripts/governance/check_track_status.py` | ✅ (active-track defended) |
| `.semgrep/dharma-anti-slop.yml` Rule 1 (`~/.dharma` writers) | ✅ (none added) |
| Rule 8 root markdown allowlist | ✅ (no root markdown) |
| Rule 10 grandfathered ceilings | ✅ (no edits to those modules) |
| `make memory-kernel-readiness` | ✅ (no kernel changes) |
| `tests/test_<module>.py` green/red pair | ✅ |
| `evolution.py shadow_mode=True` invariant | ✅ |
| New `ACTIVE_SURFACE_MANIFEST.yaml` entries declared | ✅ |
| New module `forbidden_paths` includes spine + telos_gates + `~/.dharma` | ✅ |
| Operator approval point exists for every external action | ✅ |

---

## What this sequence buys (yield)

If all 6 PRs land and the cron is opt-in enabled:

- **+1 weekly external artifact** (operator brief), each one citing real receipts
- **+9 receipts per loop iteration** (kaizen, agentops, evidence, manifest, transactions, YDS, session events)
- **+1 first paying-reader gate** at issue 4 (if ≥ 50 free subs)
- **First measurable welfare signal** from outside the closed loop
- **Stage 11 unlocks conditionally** after 5 green issues — but `evolution.py` defaults stay frozen
- **First VentureCell with kill conditions running live**

If at 60 days the kill condition `no_revenue_after_60_days` trips, the wedge dissolves cleanly:

- Cell archived under `revenue_wedge/`
- Unspent budget returned to core-ops
- Modules remain (feature flags stay off)
- Receipts retained as learning

That is the correct, telos-preserving outcome. **The organism that cannot survive contact with the world should dissolve.**

— Devin (Roaming) `AGT-DEVIN_ROAMING_2987D222`, 2026-05-28
