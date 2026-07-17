# LOOP-1 CLOSED_LIVE — Cybernetic Loop Closure Work-Packet Spec

**Version**: v0.3, 2026-07-11 (Asia/Tokyo) — v0.1 adversarially reviewed by 3
independent lenses (14 defects salvaged → v0.2); v0.3 incorporates the
discovery that the historical dropoff quarantine ALREADY RAN 2026-07-03 on the
then-daemon host (commit `a9d6f6a6b`), plus operator ratifications of
2026-07-11. **Status**: RATIFIED (D-LC2 learning wire = YES; D-LC3 restart
authorized, date open); WP-LC0 admission PR in flight.
**Track**: `loop-closure-2026-06` (outcome owner) | **Carrier**: `organism-rewire-2026-07` (D1)
**Baseline**: spec facts verified at `94a3877c7` + #863/#864 deltas, re-verified at `origin/main == 802ed21cb`
**Repo home**: `docs/plans/LOOP1_CLOSURE_SPEC_2026-07-11.md` (admitted by WP-LC0)

---

## §0 Admission and use of this specification

**Session-entry update (2026-07-17):** the One-Door hardening campaign is
closed. Its packet prefix and shared-surface conventions have no continuing
authority. New work follows `docs/governance/BUILD_SESSION_ENTRYPOINT.md`.

1. This spec was admitted through a **governance-only PR (WP-LC0)** that amends the existing ACTIVE track
   `loop-closure-2026-06` (new `next_items` for WP-LC1..LC5, four new files added
   to `owned_surfaces`, refreshed `verified_at`, §7.3 edges), regenerates the two
   managed blocks via `python3 scripts/governance/render_active_track_includes.py`,
   runs the mechanical DocOps refresh
   `python3 scripts/docops/check_docops_integrity.py --write-manifest-counts --write-auto-sections`,
   and proves `check_track_status.py` exit 0 plus a fresh surface-collision analysis.
2. There is no onboarding shared-surface exception. The renderer owns only the
   marked blocks in `CLAUDE.md` and `docs/governance/SOVEREIGN_MANIFEST.md`;
   `BUILD_SESSION_ENTRYPOINT.md` is a stable contract, not a portfolio render.
3. **Never widen the envelope in flight.** A mid-implementation conflict stops
   work and returns an `[AMENDED <date>]` governance PR (#859/#860/#864 pattern).
4. No new track is opened: the portfolio sits at the `max_active: 10` hard
   ceiling and this work belongs to an already-ACTIVE track. This entry is the
   admission record; this spec is the detail authority. Edit ACTIVE_TRACK.yaml
   intentionally and regenerate its marked projections; never hand-edit those
   generated blocks.

## §1 Baseline evidence (verified 2026-07-10/11; re-verified by 3 adversarial lenses)

**Runtime truth — MeghaDharma, read-only probes 14:56Z / 15:03Z 2026-07-10:**
- Container `dharma-swarm` running ~29h; `python -m dharma_swarm.orchestrate_live`
  is the live process. Docker healthcheck flapped `healthy`→`unhealthy` between
  probes while HTTP `/health` returned ok both times (cause unestablished; WP-LC2 item 4).
- Generic `swarm` loop: 1,459→1,461 ticks, 0 errors. **All 14 named loops: 0
  ticks**, rendered `OK` by `dgc loop-status`.
- Newest spine receipt `2026-07-10T04:33:58Z` — receipt flow stalled ~10.5h at probe time.
- Fail-closed env verified on host: `DHARMA_SPINE_DISPATCH=1`,
  `DHARMA_SELF_IMPROVE=0`, `DHARMA_EVOLUTION_SHADOW=1`,
  `DHARMA_ALLOW_LIVE_MUTATION=0`, `DGC_AUTONOMY_LEVEL=1`. **This spec changes none of them.**
- Host checkout `0beef7584…` (07-09 forensics) — the deployed daemon does NOT
  run current main. Every host claim is typed `needs_host` until re-proven on
  the host at a recorded SHA.
- **Exposure hazard (load-bearing for §8):** origin/main `docker-compose.yml:84`
  publishes `"7433:7433"` (0.0.0.0 world bind). The exposure was closed on the
  host only by an **uncommitted local loopback patch** — a clean redeploy from
  main REOPENS it. See §5.7 and §8 preconditions.

**Code truth (bytes verified at the pinned SHAs):**
- `dharma_swarm/loop_supervisor.py:34` `last_tick: float = 0.0`; `:50-54`
  `is_stalled` returns False when `last_tick == 0`; `:44-48` `stale_seconds`
  returns 0.0 for never-started; `:457` CLI collapses to binary
  `"STALLED" if … else "OK"`; `:327` the watchdog alert keys off the same
  `is_stalled` — never-started loops can never alarm; `:200-201` `record_tick`
  **silently no-ops for unregistered names**.
- Registration happens at `orchestrate_live.py:2117-2129` from `_loop_intervals`
  (15 loops incl. `swarm`, plus conditional room-health). Only `run_swarm_loop`
  receives the supervisor handle (`:2132`) and ticks (`:334`). **Five additional
  factory loops — archaeology, guardian, health-api, gauntlet, world-model
  (`:2150-2162`) — are never registered at all**, so they are invisible even as
  NEVER_STARTED. Three named loop bodies are imported modules:
  `context_agent.py`, `training_flywheel.py`, `self_improve.py`.
- `pulse` has a **pre-loop early return** under `CLAUDECODE`
  (`orchestrate_live.py:388-390`; harness expects it —
  `optional_clean_exit={'pulse'}` at `:2170`); `self_improve`'s guard is
  per-iteration (`self_improve.py:760-773`). These two guard shapes need
  different honesty treatments (WP-LC1).
- Real task-liveness surface: `$DHARMA_STATE/ops/loop_liveness.json`
  (`running`/`abandoned`) — distinct from `loop_supervisor/state.json` which
  `dgc loop-status` renders.
- Loop 1 = **Swarm Task Loop (provider chain + dispatch)**. Codex audit verdict:
  HARNESS_PROVEN, "not CLOSED_LIVE: dispatch_dropoff=2191"
  (`reports/loop_closure/cybernetics_codex/latest_audit.md:82`).
- **The real provider-selection seam**: the shared `ModelRouter`
  (`dharma_swarm/providers.py:2105`), built by `create_default_router()` at
  `swarm.py:139`, attached to every agent at `swarm.py:898`. It already carries
  `routing_memory`, `learning_enabled`/`learning_alpha`, and a
  `CircuitBreakerRegistry` (`providers.py:2108-2135`), with outcome feedback via
  `AgentRunner._record_router_feedback` (`agent_runner.py:2807`).
  `runtime_provider.resolve_runtime_provider_config()` only resolves
  per-provider config inside `create_default_provider_map` — it does **no**
  inter-provider ordering at dispatch time.
- The only orchestrator `EvidenceReceipt` fill site is
  `dharma_swarm/orchestrator.py:2494-2523` — **a dharmagraph-engine-2026-07
  owned surface at its module-budget ceiling. Hands-off** (see WP-LC3 seam rule).
  `attributes.run_id` is minted **per invocation** (`spine/identity.py:80`),
  not per process → P4 requires a `boot_id`.
- `make orient`'s "Loop 1 LIVE" bar (`scripts/governance/orientation_graph.py:677-727`)
  = latest completed `delegation_runs.receipt_json` carries provider+model.
  That is a receipt-freshness check, **far weaker** than CLOSED_LIVE. This spec
  never treats `orient: LIVE` as closure evidence.
- Spine pulse reader: `dharma_swarm/operator_core/spine_tail.py:155-196`
  (`receipts_last_hour`, `last_receipt_age_seconds`, `dispatch_dropoff_count`),
  read-only `mode=ro` (`:45`).

**Governance truth:**
- Track claim_boundary: `CLOSED_LIVE 0/13; HARNESS_PROVEN 11/13; BLOCKED 2/13`,
  machine-pinned by four criteria against
  `reports/loop_closure/cybernetics_codex/latest_audit.json`. **Any real closure
  requires the staged criteria transition in §7 — the counts are load-bearing
  and will fail the checker the moment the audit honestly improves.**
- `ship_vetoes`: any HARNESS_PROVEN loop (threshold 0) vetoes a live-ship claim.
  With 10 loops remaining HARNESS_PROVEN after Loop-1 closes, **the track stays
  not-live-shippable. Loop-1 CLOSED_LIVE ≠ track live ship. Preserved, not gamed.**
- `depends_on` is a real, validated schema field (`check_track_status.py:44`
  EDGE_KINDS; unresolved-edge ERROR + cycle detection) with **zero edges among
  the 10 ACTIVE tracks**. WP-LC0 adds the first (§7.3). Note: edges are
  structure-validated, not operationally gating — the spec claims typing only.
- Track `next_items` id 1 (blocker) — **substantively already executed**:
  the quarantine ran 2026-07-03T14:38Z on the **then-daemon host (the Mac,
  `db_path /Users/dhyana/.dharma/state/runtime.db`)** with cutoff
  `2026-07-02T00:00:00Z` (strictly after the newest dropoff row
  `2026-07-01T16:45:35Z`, before the #755 spine-fix merge `2026-07-02T19:49Z`):
  `quarantined_now=2191`, `dropoff_live_after=0`, dry-run/execute rowid-sha256
  identical. Repo witness: commit `a9d6f6a6b`,
  `reports/loop_closure/2026-07-03_dispatch_dropoff_quarantine.json`. The
  commit itself flags the host-delegation for operator ratification — WP-LC0's
  merge provides it. Residual: verify the **current** daemon host's container
  DB (organism moved to MeghaDharma ~07-03; its DB postdates the fix). Also
  note `latest_audit.json` was observed `2026-07-02T13:47Z` — pre-quarantine,
  from the Mac DB — so the committed audit is stale on two axes. Id 3
  (blocker): promotion only after the live owner-surface criterion passes
  **on the daemon branch that actually runs**.

## §2 Definitions

**The five closure predicates** (all must hold; each maps to a checkable artifact):

| P | Predicate | Checkable artifact |
|---|-----------|--------------------|
| P1 | A live cycle produces a typed output with a durable receipt | `EvidenceReceipt` row in `delegation_runs.receipt_json` + chained projection in `~/.dharma/witness/claim_evidence_receipts.jsonl` |
| P2 | A **later** live cycle consumes that specific output | consumption record citing the exact `trace_id`(s) of prior-cycle receipts |
| P3 | Consumption changes a decision observably | recorded decision delta (routing order differs from default, reason cites consumed evidence) |
| P4 | The causal chain survives process/container restart | producer and consumer receipts carry different `boot_id`s AND verify from volume-backed stores after restart |
| P5 | A disjoint code path verifies; the producer cannot self-certify | the checker is a separate read-only process on a separate surface; the producing loop's code path writes no verdict. **Claimed as process/code-path disjointness only** — owner disjointness is provided procedurally by §6 WP-LC5's non-author merge + host-binding keys (§7.2), not "by construction" |

**Loop-health states** (WP-LC1): `NEVER_STARTED | RUNNING | STALLED | DISABLED`.
`NEVER_STARTED` is not healthy: a registered loop that has never ticked within
`2 × expected_interval` of its **registration time** alarms exactly like a stall.
`DISABLED` (env-gated, decidable at registration: e.g. pulse under `CLAUDECODE`)
renders distinctly and is exempt from stall alarms — "intentionally idle" must be
visible and must not cry wolf.

**Type rule (RSI boundary, unchanged):**
```text
RSI output: Candidate | BENCHMARK_VERIFIED
not assignable to: AuthorizedChange | ADAPTING_LIVE
Promotion requires: independent evidence + later-cycle consumption proof + verify_promotion
```
The consumption wire in WP-LC3 exercises **existing routing authority over
provider selection** — it mutates no code, no prompt, no archive, and no config
file, and it extends an adaptive mechanism (`ModelRouter` routing memory /
circuit breakers) that already exists and is already authorized.

**`needs_host` vocabulary** (per the Session Entry contract): any predicate
provable only on the daemon host is typed `needs_host` and reported as a gap,
never as pass, until a host receipt exists.

## §3 Target state

A fresh `cybernetics_codex` audit, run **on the daemon host against its real
stores** (§8 step 5), honestly reports **Loop 1 = CLOSED_LIVE** with
`dropoff_live=0`, `dropoff_quarantined_historical≈2191`, a verified P1→P5 chain,
and the track's criteria updated in the same atomic PR to `CLOSED_LIVE 1/13;
HARNESS_PROVEN 10/13; BLOCKED 2/13`. `dgc loop-status` tells the truth about
never-started, disabled, and unregistered loops on every host. Env flags
unchanged. Port 7433 loopback-bound in committed config. Ship veto still
active. Nothing else claims anything.

## §4 Packet discipline (Session Entry)

Per implementation PR, one **Session Entry Packet** (AgentOps v0 +
`dharma_swarm.session_entry.v1`), authored **externally** under `DHARMA_OPS_DIR`,
validated with `python3 scripts/governance/run_agent_work_packet.py --packet
"$PACKET" --inspect` at exact clean `HEAD == base_ref`, then copied
byte-for-byte to the tracked path as the first non-code diff. Packet id MUST
equal `loop-closure-WP-LC<N>` and `session_entry.work_packet` MUST equal
`WP-LC<N>`. `run_agent_work_packet.py` derives the
tracked filename from `packet.id`, giving
`reports/agentops/work_packets/loop-closure-WP-LC<N>.json`. Default-deny
`allowed_files`; `forbidden_files` ⊇
every sibling track's `owned_surfaces` + the minimum-forbidden set;
`packet_digest` via `memory_kernel.write_receipts.stable_digest` (no other
digest primitive); gates shlex-parsed, no shell tokens, no mutating git, **no
live/autonomy tokens** (`orchestrate-live`, `live_swarm`, `autonomy-daemon`,
`autonomous-daemon`). Reports go only to an external `--report-root`.

The former `WP-O*`-only constraint was removed on 2026-07-17. The evaluator
now accepts conservative generic `WP-*` identifiers bound to the packet id;
`WP-LC<N>` is a normal validated identity, not a procedural exception.

Session flow per packet: `make onboard` → clean tree →
`make agent-build-preflight PACKET="$PACKET"` → implement inside the envelope →
`make agent-build-closeout PACKET="$PACKET"` before PR
(expect the stale-NATS gate may fail on non-live hosts; owned elsewhere —
record, don't chase).

## §5 Safety invariants (violating any = stop and return to operator)

1. Env flags on any host stay exactly: `DHARMA_SELF_IMPROVE=0`,
   `DHARMA_EVOLUTION_SHADOW=1`, `DHARMA_ALLOW_LIVE_MUTATION=0`,
   `DGC_AUTONOMY_LEVEL=1`. Never flip a flag to make a criterion green.
2. `verify_promotion`, the promotion gate (`dharma_swarm/promotion_gate.py`),
   One-Wire blocks on loops 12/13, and every Sovereign Safety TCB surface: untouched.
3. Hands-off surfaces (other lanes): `dharma_swarm/coordination/arena/**`,
   `dharma_swarm/chamber/**`, `dharma_swarm/forge_lab/**` (PR #863 cards),
   Session Entry evaluator/tests, `scripts/governance/arena_truth_report.py`,
   **`dharma_swarm/orchestrator.py` (dharmagraph-owned, module-budget ceiling)**.
   Re-run the open-PR collision check at each packet's authoring time.
4. No packet gate ever launches the daemon or any live/autonomy target. Live
   evidence enters only as receipts written by the host and verified read-only.
5. Exactly **three** mutating operator actions on MeghaDharma, each receipted
   with rollback: quarantine `--execute`, one redeploy, one deliberate
   `docker restart` (the P4 leg). Everything else on the host is read-only.
   All three are coordinated with the RSI lane before touching the host.
6. Receipts prove persistence and integrity, **never external correspondence**
   (a valid digest does not make content true) — the audit recomputes from raw
   stores, not from receipt claims.
7. **No redeploy while the committed compose still world-binds :7433.** Redeploy
   is blocked until either organism-rewire (compose owner) lands the loopback
   binding (`127.0.0.1:7433:7433`) on main, or the host firewall provably denies
   7433 — verified and recorded in the host session receipt (§8 precondition).

## §6 Work packets

### WP-LC0 — Governance admission (S, governance-only)
**Closes**: legal admission of WP-LC1..LC5; first typed `depends_on` edges.
**Diff**: `docs/governance/ACTIVE_TRACK.yaml` (loop-closure entry: new
next_items; `owned_surfaces` += `scripts/governance/loop1_consumption_check.py`,
`tests/test_loop_supervisor_tristate.py`, `tests/test_loop1_consumption.py`,
`tests/test_loop1_consumption_check.py`; `verified_at` refresh; §7.3 edges)
+ this spec at `docs/plans/LOOP1_CLOSURE_SPEC_2026-07-11.md` + regenerated
managed blocks + mechanical count refresh.
Nothing else.
**Also records as next_items**: (a) `needs-owner` → organism-rewire lane:
commit the :7433 loopback binding to main **before any
LC2 redeploy** (§5.7, blocker on D-LC3); (b) pre-declaration: if WP-LC3's
non-owned seam (below) proves insufficient, a coordinated ≤2-line
`orchestrator.py` edit will be requested via dharmagraph-owner sign-off in an
`[AMENDED]` PR — declared now so the conflict resolves at admission, not mid-flight.
**Gates**: `check_track_status.py` exit 0; `render --check` 0;
`make docops-integrity` 0; collision analysis clean.
**Kill criterion**: operator declines the consumption-edge choice (§9 D-LC2) —
then only WP-LC1+LC2 (honesty repairs) proceed and LC3..LC5 are struck.

### WP-LC1 — Observation honesty: 4-state health + full registration + ticks (M)
**Closes**: the structural lie (never-started renders OK; named loops cannot
tick; five live loops invisible even to registration).
**Allowed files**: `dharma_swarm/loop_supervisor.py`,
`dharma_swarm/orchestrate_live.py`, `dharma_swarm/context_agent.py`,
`dharma_swarm/training_flywheel.py`, `dharma_swarm/self_improve.py` (tick call
+ optional `supervisor=None` kwarg ONLY in the latter three),
`tests/test_loop_supervisor_tristate.py` (new), + mechanical count refresh.
**Collision note**: verified sibling-unowned at 802ed21cb; re-verify at packet time.
**Behavior (failing-first, in order)**:
1. `LoopHealth` records `registered_at`; a `state` property returns
   `NEVER_STARTED` when `last_tick == 0`, escalating to alarm (same channel as
   LOOP_STALL, `loop_supervisor.py:327`) once
   `now - registered_at > 2 × expected_interval`.
2. `DISABLED` state: `supervisor.mark_disabled(name, reason)` set at
   registration time when the env-gate is already decidable (pulse under
   `CLAUDECODE` — its guard is a pre-loop early `return`,
   `orchestrate_live.py:388-390`, expected by `optional_clean_exit={'pulse'}`
   at `:2170`). Rendered distinctly; exempt from stall alarms. **Never tick a
   pre-loop-return body** — that would manufacture a permanent false STALLED.
3. Per-iteration-guarded loops (e.g. `self_improve.py:760-773`) tick **before**
   their skip so "alive but intentionally idle" is visible: thread the
   supervisor handle through the factories (`orchestrate_live.py:2131-2163`),
   one `supervisor.record_tick("<name>")` per loop iteration (~20 one-line edits).
4. **Register the five factory-only loops** (archaeology, guardian, health-api,
   gauntlet, world-model, `:2150-2162`) in `_loop_intervals` with honest
   intervals — `record_tick` silently no-ops for unregistered names
   (`loop_supervisor.py:200-201`), so without this they stay invisible.
5. `cmd_loop_status` renders the 4-state; `NEVER_STARTED` is never `OK`;
   `to_dict()` carries `state` alongside `is_stalled` (compat).
**Gates**: `python3 -m pytest tests/test_loop_supervisor_tristate.py -q` (new,
red-first); `python3 -m pytest tests/ -q -k "loop_supervisor or orchestrate"`
(no regression); negative control: a `LoopHealth(last_tick=0)` fixture asserted
`OK` must FAIL (expected_exit nonzero).
**Rollback**: revert the single PR.
**Kill criterion**: if threading the handle requires touching `SwarmManager`
internals beyond a kwarg, stop — that is organism-rewire D5 territory.

### WP-LC2 — Daemon-host truth session (S, ops, operator-executed, `needs_host`)
**Closes**: track blocker next_item 1 (the ~2,191 historical dropoffs) + the
deploy-drift and health-signal unknowns.
**Steps (exact commands in §8)**:
1. Record host-checkout SHA and container image digest (closes the `0beef758`
   vs main drift question; the image itself has no `.git`).
2. **Historical debt already drained** (§1): the 2,191-row quarantine ran
   2026-07-03 on the then-daemon host (Mac), receipt committed `a9d6f6a6b`.
   On the CURRENT daemon host, only **verify**: count `dispatch_dropoff` rows
   in the container's volume DB. Any live dropoffs there postdate the #755
   spine fix and are **real signal — investigate, never stamp**.
3. Emit the host-verification receipt off-host **before any redeploy/restart**:
   a wrapper that embeds the 2026-07-03 receipt verbatim, adds the
   current-host fields (`observed_at`, `host_sha`, `container_image_digest`,
   `db_path`, `delegation_runs_row_count`, current `dropoff_live_after`),
   wrapped through the `stable_digest` two-digest pattern, committed as
   `reports/loop_closure/quarantine_receipt_2026-07.json` (satisfies every
   §7.2 required key).
4. Capture the container healthcheck definition
   (`docker inspect -f '{{json .Config.Healthcheck}}'`) and reconcile
   unhealthy-vs-`/health`-ok; file the finding (fix only if it is a
   healthcheck-definition bug; anything deeper returns to operator).
5. **Precondition §5.7 verified, then** redeploy at a pinned SHA ≥ the WP-LC1
   merge (operator-gated, RSI-lane-coordinated). Run the codex audit + WP-LC4
   checker on-host (docker-cp pattern, §8 step 5) against the volume stores.
   Verify: named loops ticking, 4-state honest, receipts flowing — then one
   deliberate restart (P4 leg) and re-verify, with a pre-restart
   `sqlite3 … ".backup"` copied off-host (zero off-host backup exists today).
**Evidence**: committed quarantine receipt + host session receipt
(`reports/loop_closure/host_session_2026-07.json`, two-digest pattern, recording
SHAs, image digest, binding check, commands, exits).
**Rollback**: quarantine stamps columns, deletes nothing; redeploy rollback =
previous image tag; restart is self-healing (container `restart: unless-stopped`).

### WP-LC3 — The consumption wire (M)
**Closes**: P2+P3+P4 — a later cycle consuming specific prior receipts and
observably changing a decision, across restarts.
**The real seam (Architect's Gate, verified):** the shared `ModelRouter`
(`dharma_swarm/providers.py:2105`; built by `create_default_router()` at
`swarm.py:139`, attached to agents at `swarm.py:898`) **already** has
`routing_memory`, learning, and a `CircuitBreakerRegistry`, with outcome
feedback via `AgentRunner._record_router_feedback` (`agent_runner.py:2807`).
The wire is implemented as an **extension of that existing feedback loop** —
receipt-grounded ordering input — not a parallel router, and not in
`runtime_provider` (which does per-provider config resolution, no ordering).
**Behavior**: at selection time the router additionally reads recent
`EvidenceReceipt` outcomes **only from `delegation_runs.receipt_json`**
(read-only, `mode=ro`, bounded window) and applies the already-authorized
ordering rule. Boundedness (all four are hard requirements with tests):
1. Deprioritization **reorders within the authorized hierarchy — never
   excludes** a provider.
2. At most N providers demoted per decision (small constant, tested).
3. Only spine-written `delegation_runs.receipt_json` rows count — never
   free-form stores (the store is unauthenticated; limiting the read surface
   bounds poisoning).
4. Any read/parse error → **default order** (fail-open to default), with the
   empty-`consumed_trace_ids` negative control.
**Evidence plumbing (non-owned seam):** `consumed_trace_ids`, the route delta,
and a per-process `boot_id` (uuid4 at startup; `attributes.run_id` is
per-invocation — `spine/identity.py:80` — so unusable for P4) are carried on
`RoutingDecision` (`dharma_swarm/model_routing.py`, verified unowned) and
surface into the receipt through the existing routing-attributes pass-through.
**`dharma_swarm/orchestrator.py` is not edited** (dharmagraph-owned); if the
pass-through proves insufficient, stop and invoke the WP-LC0-pre-declared
dharmagraph sign-off route (§6 WP-LC0 item c).
**Allowed files**: `dharma_swarm/providers.py` (router extension),
`dharma_swarm/model_routing.py`, `dharma_swarm/agent_runner.py`
(feedback-loop extension only), `tests/test_loop1_consumption.py` (new),
+ mechanical count refresh.
**Gates**: `python3 -m pytest tests/test_loop1_consumption.py -q` — red-first:
(a) synthetic store with a failing provider's receipts → order differs from
default and the decision cites the consumed `trace_id`s; (b) no recent
failures → default order, empty `consumed_trace_ids` (no fabricated
consumption); (c) restart simulation: producer receipts under `boot_id` A,
consumer decision under `boot_id` B, chain verifies; (d) poisoning bound: with
M providers' receipts all failing, no more than N are demoted and none excluded.
No live tokens in any gate.
**Forbidden**: any write path into archives, prompts, code, or config; every
§5.3 surface.
**Kill criterion**: if the extension cannot land without restructuring
**`ModelRouter`'s public interface**, stop and return a design note — do not
fork routing (THE ONE WAY).

### WP-LC4 — Disjoint verification (S/M)
**Closes**: P5 — the verdict is computed by a non-producer code path from raw stores.
**Behavior**: extend the cybernetics_codex audit lane (owned surface
`reports/loop_closure/**`) with a read-only checker
`scripts/governance/loop1_consumption_check.py`: opens `runtime.db` read-only
(`mode=ro`, the `operator_core/spine_tail.py:45` pattern) + the witness chain;
validates P1..P4 (produce → cite → delta → cross-`boot_id` + chain integrity
via the canonical digest recompute); emits
`reports/loop_closure/loop1_consumption_receipt.json` (two-digest pattern,
**carrying `observed_at` ISO-8601 UTC** — the freshness key
`check_track_status._receipt_timestamp` reads — plus the §7.2 host-binding
keys) and supports `--check` replay (the `frontier_ledger.py --check` contract).
The producing loop's code path contains no call into this checker and cannot
write its receipt. In CI (no host stores) `--check` exits with a typed
`needs_host` gap on host-only legs — never a fabricated pass.
**Gates**: `python3 -m pytest tests/test_loop1_consumption_check.py -q`
(fixture DBs: passing chain, broken chain, self-citation spoof — spoof must
FAIL); `python3 scripts/governance/loop1_consumption_check.py --check` (<60s, CI-safe).

### WP-LC5 — The closure claim (S, governance-only, atomic, human-merged)
**Closes**: the honest flip to `CLOSED_LIVE 1/13`.
**Preconditions**: WP-LC1..LC4 merged; host session (§8) complete; fresh codex
audit **run on the host** shows Loop 1 CLOSED_LIVE with `dropoff_live=0`.
**Diff (one atomic PR, or the checker breaks)**: refreshed
`reports/loop_closure/cybernetics_codex/latest_audit.{json,md}` + §7.2 criteria
transition + claim_boundary `"CLOSED_LIVE 1/13; HARNESS_PROVEN 10/13; BLOCKED 2/13"`
+ managed blocks + count refresh. Ship veto stays.
**Anti-gaming (mandatory, because every §7.2 gate verifies author-producible
artifacts):** (a) all three receipts carry the §7.2 host-binding keys;
(b) `latest_audit.json`'s inputs digest must chain to the operator-executed
`host_session_2026-07.json` receipt (cross-receipt rule, checked by the WP-LC4
`--check`); (c) **non-author merge required; the bot-PR/automerge label is
forbidden on this PR** (Mike's automerge lane waives receipts for bot-labeled
PRs — that path is explicitly closed here); (d) the PR body carries a
one-command reviewer spot-check (ssh + recount of `dropoff_live`).
**Kill criterion**: audit reports anything but an honest CLOSED_LIVE for
Loop 1 → no PR; findings go back into next_items. `orient: LIVE` alone is
never sufficient (§1).

## §7 Governance bindings (exact, for WP-LC0/LC5)

### 7.1 New criteria at WP-LC0 — appended to `completion_criteria`
**(NEVER `prerequisites` — a failed `command_passes` prerequisite is a hard CI
ERROR/exit 1; failing completion criteria on an ACTIVE track are INFO-only.)**
```yaml
- id: loop_supervisor_tristate_honest
  kind: command_passes            # RED until WP-LC1
  command: ["python3", "-m", "pytest", "tests/test_loop_supervisor_tristate.py", "-q"]
- id: loop1_consumption_unit_proof
  kind: command_passes            # RED until WP-LC3
  command: ["python3", "-m", "pytest", "tests/test_loop1_consumption.py", "-q"]
- id: loop1_consumption_check_replays
  kind: command_passes            # RED until the host receipt lands (post WP-LC2/LC4)
  command: ["python3", "scripts/governance/loop1_consumption_check.py", "--check"]
  timeout_s: 60
```
### 7.2 Criteria transition at WP-LC5 (same atomic PR as the refreshed audit)
```yaml
# cybernetics_codex_closed_live_count_zero  → id: cybernetics_codex_closed_live_count, expected: 1
# cybernetics_codex_harness_proven_count_11 → expected: 10
# verdict map: loop "1" → CLOSED_LIVE; loops 2–11 HARNESS_PROVEN; 12–13 BLOCKED
- id: loop1_host_quarantine_receipt_valid
  kind: receipt_valid
  file: reports/loop_closure/quarantine_receipt_2026-07.json
  expect_digest: true
  requires_keys: [tool, cutoff, executed, dropoff_live_after, quarantined_rowids_sha256,
                  observed_at, host_sha, container_image_digest, db_path, delegation_runs_row_count]
- id: loop1_consumption_receipt_valid
  kind: receipt_valid
  file: reports/loop_closure/loop1_consumption_receipt.json
  expect_digest: true
  fresh_ttl_days: 30
  requires_keys: [schema, observed_at, producer_trace_id, consumer_trace_id, consumed_trace_ids,
                  decision_delta, producer_boot_id, consumer_boot_id, chain_verified,
                  host_sha, container_image_digest, db_path, delegation_runs_row_count,
                  content_digest]
- id: loop1_host_session_receipt_valid
  kind: receipt_valid
  file: reports/loop_closure/host_session_2026-07.json
  expect_digest: true
  requires_keys: [observed_at, host_sha, container_image_digest, port_binding_check,
                  commands, content_digest]
```
(`observed_at` is mandatory everywhere `fresh_ttl_days` may ever apply —
`_receipt_timestamp` reads exactly six keys and fails permanently without one.
Host-binding keys make the receipts host-fingerprinted rather than
author-producible-anywhere. Slow/live proofs bind through committed receipts —
the G1 pattern — keeping the checker inside its 60s convention.)

### 7.3 First typed edges (WP-LC0)
```yaml
# on loop-closure-2026-06:
depends_on:
  - organism-rewire-2026-07        # D1 standing daemon is the carrier
# (validated: EDGE_KINDS includes depends_on; target is a declared ACTIVE track;
#  acyclic. Structure-typed, not operationally gating — honest claim only.)
```

## §8 Host runbook (operator, `needs_host`, corrected for the real image topology)

The image contains **only** `dharma_swarm/` (+ pyproject/README); no `scripts/`,
no `.git`. Scripts enter via `docker cp`; provenance comes from the host
checkout and image digest.

```sh
# 0. PRECONDITION (§5.7): verify binding before anything mutating
ssh -o BatchMode=yes meghadharma '
  docker inspect -f "{{json .HostConfig.PortBindings}}" dharma-swarm
  sudo iptables -L -n 2>/dev/null | grep 7433 || true
'
# 1. Truth: what actually runs (read-only)
ssh -o BatchMode=yes meghadharma '
  date -u
  docker inspect -f "{{.State.StartedAt}} {{.State.Health.Status}} {{.Image}}" dharma-swarm
  docker inspect -f "{{json .Config.Healthcheck}}" dharma-swarm
  git -C ~/dharma_swarm rev-parse HEAD 2>/dev/null || echo "host checkout path differs — record actual"
'
# 2. Quarantine — copy tool in, dry-run, review, then execute (cutoff = D-LC1)
ssh meghadharma '
  docker cp ~/dharma_swarm/scripts/runtime/dispatch_dropoff_quarantine.py dharma-swarm:/tmp/
  docker exec dharma-swarm python3 /tmp/dispatch_dropoff_quarantine.py --before "<CUTOFF-ISO8601>" --dry-run
'
ssh meghadharma 'docker exec dharma-swarm python3 /tmp/dispatch_dropoff_quarantine.py \
  --before "<CUTOFF-ISO8601>" --execute --reason "pre-spine-fix historical dropoffs (loop-closure next_item 1)"'
# 3. Receipt OFF-HOST BEFORE any redeploy/restart (default receipt dir is the volume)
ssh meghadharma 'docker exec dharma-swarm sh -c "cat /root/.dharma/loop_closure/dispatch_dropoff_quarantine_*.json"' > quarantine_raw.json
#    → wrap with stable_digest (+observed_at, host_sha, image digest, db_path, row count) → commit to reports/loop_closure/
# 4. Redeploy at pinned SHA >= WP-LC1 merge (D-LC3: operator window, RSI-lane coordinated, §5.7 green)
# 5. On-host verification (docker-cp pattern for audit + checker)
ssh meghadharma '
  docker cp ~/dharma_swarm/scripts/governance/loop1_consumption_check.py dharma-swarm:/tmp/
  docker exec dharma-swarm dgc loop-status          # 4-state honest, named loops ticking
  docker exec dharma-swarm dgc spine tail --limit 5 # receipts flowing
  docker exec dharma-swarm python3 /tmp/loop1_consumption_check.py --check
'
# 6. P4 restart leg — backup FIRST, then one deliberate restart, re-verify
ssh meghadharma 'docker exec dharma-swarm sh -c "sqlite3 /root/.dharma/state/runtime.db \".backup /root/.dharma/state/runtime.db.bak\""'
ssh meghadharma 'docker cp dharma-swarm:/root/.dharma/state/runtime.db.bak ./runtime.db.bak' && scp meghadharma:runtime.db.bak ~/dharma_recover_backups/meghadharma_runtime_$(date +%Y%m%d).db
ssh meghadharma 'docker restart dharma-swarm && sleep 30 && docker exec dharma-swarm dgc loop-status && docker exec dharma-swarm python3 /tmp/loop1_consumption_check.py --check'
```
Never print secrets; never leave the container stopped; the codex audit re-run
follows the same docker-cp pattern. Litestream off-host backup remains a
separate open risk (env empty — outside this envelope, flagged, not fixed here;
step 6's manual backup is the interim mitigation).

## §9 Open operator decisions

| id | Decision | Status (2026-07-11) |
|----|----------|---------------------|
| D-LC1 | Quarantine cutoff | **RESOLVED** — `2026-07-02T00:00:00Z`, already used by the 2026-07-03 execution (`a9d6f6a6b`); operator ratifies the host-delegation by merging WP-LC0 |
| D-LC2 | The consumption/learning wire (bounded per §6 WP-LC3) | **RATIFIED** by operator, 2026-07-11 |
| D-LC3 | One redeploy+restart of the daemon host | **AUTHORIZED** 2026-07-11; date open; **§5.7 loopback-commit precondition stands** |
| D-LC4 | Generalize Session Entry packet identity beyond a campaign prefix | **RESOLVED 2026-07-17** — conservative generic `WP-*` grammar accepts packet-bound `WP-LC<N>` identities |
| D-LC5 | Dharmagraph sign-off route for a ≤2-line `orchestrator.py` edit if the RoutingDecision pass-through proves insufficient | **PRE-APPROVED** as fallback |

## §10 Non-goals

No self-improvement unlock, no `DHARMA_*` flag changes, no archive/MAP-Elites
work (organism-rewire D6), no `Organism` composition-root work (D5), no
DarwinEngine/D4 anything, no arena/chamber/TAM edits (PR #863 lane), no track
live-ship claim, no second router, no new digest primitive, no new receipt
store, no edits to Session Entry evaluator surfaces or dharmagraph-owned
`orchestrator.py`. Loops 12/13 stay BLOCKED behind One Wire. Chamber and RSI
compound on top of this — they are downstream consumers of closure, not part of it.

---
*Verification chain: runtime probes 2026-07-10T14:56Z/15:03Z; code recon at
pinned 94a3877c7 (3 agents, file:line receipts); #863/#864 deltas at 802ed21cb;
v0.1→v0.2 adversarial review by 3 independent lenses (onboard-compliance /
code-mechanics / safety-collision): 14 CONFIRMED_DEFECTs all salvaged in place
(most severe: ModelRouter seam correction, :7433 redeploy-reopen gate,
orchestrator.py ownership collision, WP-LC5 merge-time gameability), key OK
verdicts: WP-LC packet filename non-colliding, RED-criteria CI-safe under
completion_criteria, depends_on real+validated, verified_at refresh legal,
quarantine tool interface exact, §7.2 transition matches the live track block.*
