# DharmaGraph Ascent — five sequential campaigns, one hill-climb (operator-ratified 2026-07-17)

**You are a fresh Claude Code instance on `/home/user/dharma_swarm`.** This is the
master spec for the post-Pregel-core ascent. Predecessor: the Pregel-core
closure (PR #1002, 52.00 → 58.00, all six execution-core cards FULLY_PROVEN,
custody anchor `claude-judge-c83df531c`). Its handoff —
`docs/plans/handoffs/DHARMAGRAPH_HANDOFF_CLAUDE.md` — is the STYLE CONTRACT
for every campaign here: machine-checkable done-blocks, one slice per
iteration, append-only progress ledger, git-is-truth reconciliation, stop
conditions where halting is success, builder/judge seat separation, custody
reseal on every evidence commit. Campaign context:
`docs/plans/DHARMAGRAPH_PHASED_SPEC_2026-07-05.md`; active track
`dharmagraph-engine-2026-07` (`docs/governance/ACTIVE_TRACK.yaml`).

## 0. Operator ratification gate (nothing runs before this)

This spec has NO authority until the operator:

1. Adds it and the per-campaign surfaces to the track's `owned_surfaces`
   (or opens a sibling track): this file, `docs/plans/handoffs/DHARMAGRAPH_ASCENT_*.md`,
   `tests/oracle_support/scenarios.py`, `tests/oracle_support/outcomes.py`,
   `dharma_swarm/graph/journal.py` (C2, new). C1's flag seam inside
   `dharma_swarm/workflow.py` is already owned; `orchestrator.py`/`swarm.py`
   edits are hot-path — see C1's impact-checked rule.
2. Ratifies the two DECLARED HARNESS AMENDMENTS in §C1.4 and §C4.2 (the only
   places this spec touches otherwise-frozen machinery, each with its own
   judge-review requirement).
3. Names the seats: one BUILDER per campaign; the independent judge seat
   signs every reseal. A builder never cites its own judge emission as
   closure evidence.

## 1. The hill and the ledger of record

One number climbs: the judge-receipt score in
`reports/governance/dharmagraph_parity/judge_receipt.json`, measured ONLY by
`python3 scripts/governance/dharmagraph_parity_gauntlet.py --check` at a
clean committed head. Current: **58.00/100**. Frozen-rubric law from the
predecessor spec §7 applies verbatim to V1+V2 until C4 mints V3.

| Campaign | Name | Metric target | Gate to next |
|---|---|---|---|
| C1 | Organism wiring (Phase-2 crown + Art. 12 receipts) | 58.00 → 63.00 (+5.00: APP01–04 to 2/2) AND engine-adoption evidence | operator merge + judge reseal |
| C2 | Reliability ring | 63.00 → 74.00 (+11.00: LG19/20/24/25/26 to 2/2) | operator merge + judge reseal |
| C3 | Frontier scan (research) | dossier with ≥2 independent sources per claim; ≥3 chartered capability cards | operator picks the cards |
| C4 | Rubric V3 @ langgraph 1.2.9 | V3 frozen-before-results; honest re-baseline emitted | operator merge + judge reseal |
| C5 | Moat build (DST chaos, telos primitives) | per-card done-blocks written INTO the C5 handoff at charter time | operator merge |

Campaigns run strictly in order. A campaign is DONE when its done-block
exits 0 (or every unreached target has a STOPPED ledger entry naming the
unsettled question — an honest miss beats a gamed hit, verbatim from the
predecessor). Score numbers above are ceilings computed from the frozen
weights (total weight 100; APP01 w4/APP02 w1/APP03 w2/APP04 w3 currently at
1pt each; LG19 w1, LG20 w2, LG24 w4, LG25 w2 at 0pt; LG26 w4 at 1pt).

## 2. The loop (identical for every campaign, every iteration)

Boris-Cherny discipline: the agent re-derives ALL state from ground truth
each iteration; nothing is remembered, everything is measured.

1. `cd /home/user/dharma_swarm && make onboard` — READY or fix/report.
2. Read the campaign's handoff file (created at campaign S0 from this spec's
   section), then its PROGRESS LEDGER (bottom of the same file, append-only,
   one block per iteration: `slice / result / verify / learned / blocked`).
3. `git log --oneline -15 && git status && git branch --show-current` — git
   is truth, ledger is claim; reconcile, fix the ledger if they disagree.
4. Run the campaign's VERIFY block. **If red, fixing red IS this
   iteration's task.** Never start slice N+1 with slice N red.
5. Else take the FIRST TODO slice whose deps are DONE. Do ONLY it.
6. Verify → commit (`feat(graph): C<N>-S<M> <title>` + ledger in the same
   commit) → score-probe (emit builder receipt, diff ONLY the expected rows,
   `git checkout -- reports/governance/dharmagraph_parity/`) → append ledger
   → push.
7. Stop conditions (halting is success): 3 consecutive failed attempts on
   one facet → STOPPED entry, move on. Metric flat for 2 green iterations →
   the loop is spinning; STOP the campaign, write findings. A fix that
   needs a hot-path file beyond the declared seam, another track's surface,
   a new dependency, or any gate weakening → STOP and document. A design
   question the rubric text + the pinned langgraph source + an empirical run
   cannot settle → STOPPED entry with the question, next slice.

PR discipline per campaign: ONE branch `claude/dharmagraph-ascent-c<N>`,
ONE draft PR opened at S0 with all four Coherence Delta fields substantive,
marked Ready only at the campaign's reseal, **NEVER self-merged**. Custody:
any commit after a receipt emission re-emits builder then judge at the new
head and recommits custody artifacts atomically (predecessor §4-S9 rule —
it fired twice in PR #1002; it will fire here).

Environment invariants (learned the hard way in PR #1002): unshallow the
clone before any gauntlet run; `pip install -e ".[dev,test-oracle]"` with
the debian-cryptography workaround; langgraph pin per campaign (1.2.4 for
C1–C2, 1.2.9 from C4); every new module ≤500 lines (down-only ratchet —
extract BEFORE crossing, as scheduler.py had to twice); cross-axis regression
pins for every reviewer finding (typed×resume and sync×timeout taught us
single-axis workloads miss seam bugs).

---

## C1 — Organism wiring: the engine becomes the substrate (58.00 → 63.00)

**Mission.** The neutral engine is `claim_mode: candidate/test_only` — 58
points of shelf inventory. C1 makes the application oracle and one real
production dispatch path run ON the engine, and lands the receipt rung the
EU AI Act Art. 12 clock (applicable 2026-08-02) is ticking for. All four APP
rows currently fail exactly one facet family: `neutral_engine_integration`
(APP04 adds `domain_isolation`, `memory_isolation`). Flipping them is
+5.00 — and unlike every other row, these points MEASURE production truth.

**Done-block (exit 0 at the campaign head):**

```bash
cd /home/user/dharma_swarm
python3 scripts/governance/dharmagraph_parity_gauntlet.py --check   # PASS
python3 - <<'EOF'
import json, sys
r = json.load(open("reports/governance/dharmagraph_parity/judge_receipt.json"))
rows = {g.get("id"): g for g in r.get("capabilities", [])}
core = ["APP01","APP02","APP03","APP04"]
if not all(c in rows for c in core):
    sys.exit(1)
ok = float(r["score"]["display"].split("/")[0]) >= 63.00
missing = [c for c in core if rows[c].get("points") != 2]
sys.exit(0 if ok and not missing else 1)
EOF
python3 -m pytest tests/test_workflow.py tests/test_graph_effects.py -q  # engine-backed workflow suite green
```

**Slices.**

- **C1-S0** — branch, handoff file `docs/plans/handoffs/DHARMAGRAPH_ASCENT_C1.md`
  (copy this section + ledger skeleton), draft PR, baseline probe. STOP THE
  CAMPAIGN if `--check` is not PASS at 58.00 on clean main.
- **C1-S1** — Read `tests/oracle_support/scenarios.py` + `outcomes.py` end to
  end; write (in the handoff, not code) the mapping from each swarm/
  supervisor scenario primitive to the engine surface that serves it
  (handoff → interrupt/Command, agent turn → node, transfer → goto,
  isolation → schema projections + subgraph). Any primitive with NO engine
  surface → the gap list that drives S2's order. No code this slice.
- **C1-S2..S4** — Port `run_dharma_swarm` / `run_dharma_supervisor` (and the
  isolation scenarios) to build on `TypedStateGraph`/`CompiledGraph` instead
  of the clone lineage — semantics pinned by the EXISTING outcome diffs
  (`diff_outcomes` already compares against the real langgraph arm; those
  comparisons are the frozen referee and may not be edited). One scenario
  family per slice.
- **C1-S5** — Production seam: `dharma_swarm/workflow.py` gains an
  engine-backed execution path behind `DHARMA_GRAPH_ENGINE=1` (default off),
  shadow mode first: run legacy AND engine, compare final states, emit a
  divergence receipt under `~/.dharma/` (never git). The seam stays inside
  `workflow.py` (owned); if it genuinely cannot land without editing
  `orchestrator.py`/`swarm.py`, that slice carries `[impact-checked]`, the
  packet-bound preflight (`make agent-build-preflight`), and the minimal
  call-site diff — or STOPs.
- **C1-S6** — Receipt rung (Art. 12): every engine-executed superstep emits
  its `GraphRunEvent` into the spine receipt log via the EXISTING
  `derive_graph_side_effect_key` vocabulary (`durable_invoker`) — no new
  truth stores; wire, don't invent. Evidence: a replayed run's receipt chain
  digest-matches the checkpoint chain.
- **C1-S7** — Reseal + Ready (predecessor §4-S9 verbatim).

**C1.4 — DECLARED HARNESS AMENDMENT (operator + judge review required).**
`_finalize_rows` in `tests/oracle_support/dharmagraph_gauntlet.py`
unconditionally appends the APP caveat "Existing application oracle
exercises the clone lineage… row is capped below 2." Once the oracle runs
the neutral engine, that sentence becomes FALSE. The amendment: make the
caveat conditional on the `neutral_engine_integration` facet actually
failing. This is a scoring-adjacent edit and therefore forbidden by default;
it may land ONLY as its own commit, reviewed by the judge seat in the PR,
with a before/after receipt diff showing the ONLY change is the caveat
string on rows whose facets independently prove 2/2. Any other diff = revert
and STOP.

**C1 stop conditions (additional).** Shadow-mode divergence that traces to a
LEGACY bug: document in the PR's Discovered section, do not fix the legacy
side, do not "fix" the engine to reproduce a legacy bug — parity is with
langgraph and with correct outcomes, not with legacy defects.

---

## C2 — Reliability ring (63.00 → 74.00)

**Mission.** Close the five rows production dispatch will lean on hardest:
LG24 retry policies (w4), LG25 timeouts/heartbeats (w2), LG19 static
interrupts (w1), LG20 dynamic-interrupt suite (w2), LG26 remainder
(`error_handler`, `sibling_cancellation`, `user_cancellation`; w4 at 1pt).
+11.00 total — the largest remaining coherent block, and every facet is an
execution-core-adjacent semantic the S2/S6/S7 primitives already carry.

**Slice 0 is the debt, not a feature:** the identity-preserving pending-write
journal (new `dharma_swarm/graph/journal.py`, ≤500): records
`(channel, value, node_id, task_seq)` so failure-resume replays in canonical
interleave order and Send-multiplicity partial records stop degrading to
re-execution — the two recorded deviations from PR #1002. Retry/timeout
semantics stress exactly these paths; build on the fixed floor. Property 3
tightens from "converges" to "byte-identical trace" in the same slice.

**Then, in strict order (riskiest first, one row per slice, the
pregel-core recipe verbatim):**

- **C2-S1** — LG24 retries: derive `RetryPolicy` semantics empirically from
  the pin (max_attempts, backoff, jitter, retry_on selection); jitter MUST
  route through `effects.random()` (DST law: no ambient entropy). Two-arm
  workload with a deterministic failure schedule.
- **C2-S2** — LG25 timeouts: node/step timeout + heartbeat refresh + idle
  timeout on the S6 `asyncio.timeout` + `to_thread` base.
- **C2-S3** — LG19 `interrupt_before`/`interrupt_after` (compile-time static
  interrupts) on the S7 interrupt substrate.
- **C2-S4** — LG20 dynamic suite: multiple interrupts, interrupt ordering,
  node re-execution discipline, resume-value routing — the S7 frames already
  key by full task identity; this slice proves the full matrix.
- **C2-S5** — LG26 remainder: `error_handler` hooks, sibling cancellation
  observability, user cancellation (CancelledError path is already clean —
  prove it two-arm).
- **C2-S6** — properties 6–8 from the predecessor §3 land here (version
  monotonicity/exactly-once, quiescence, replay determinism) — they were
  deferred then; the reliability ring is where they earn their keep.
- **C2-S7** — Reseal + Ready.

Done-block: same shape as C1's with
`core = ["LG19","LG20","LG24","LG25","LG26"]` and `>= 74.00`. Harness
additions remain APPEND-ONLY; region 1580–1720 and all existing workloads
untouched, error-parity-is-not-parity rule in every new applier.

---

## C3 — Frontier scan (research campaign; no engine code)

**Mission.** Map the 5–10 systems in this atmosphere and extract what the
ORGANISM needs — not what langgraph has. Survey set (operator may amend at
S0): Temporal, Restate, DBOS, Inngest, Hatchet (durable execution);
AutoGen, CrewAI, OpenAI Agents SDK, Pydantic-AI, Mastra (agent
orchestration); plus one wildcard the scan itself surfaces.

**Loop shape (research variant of §2):** each iteration = one system:
(a) primary-source sweep (docs, source, changelogs — no marketing pages as
sole source); (b) capability extraction against a fixed comparison frame
(durability model, failure semantics, human-in-loop, timers/events,
multi-agent topology, observability, compliance story); (c) adversarial
pass: for every "they have X we lack" claim, attempt to REFUTE it from
their source or our receipt (we may already have X); (d) ledger entry with
citations. Citation-or-silence applies with full force: every claim carries
a URL/file:line or a runnable probe; uncited claims carry zero weight.

**Deliverables (the done-block is their existence + review):**

1. `docs/plans/DHARMAGRAPH_FRONTIER_DOSSIER_<date>.md` — per-system cards,
   ≥2 independent sources per load-bearing claim, explicit refuted-claims
   section (what we feared they had and they don't — as valuable as gaps).
2. ≥3 **chartered capability cards**, each in done-block form (mission,
   metric, verify command, owned surfaces, stop conditions) ready to drop
   into C5 — ranked by organism need: the standing candidates to beat are
   durable timers, external event waits, and human-task queues.
3. A proposed V3 rubric addendum list for C4 (new rows the scan justifies,
   with per-row weight arguments) — proposals only; C4 freezes.

**Timebox:** hard cap 10 iterations. STOP conditions: a system with no
primary sources reachable → one ledger line, skip; scan finding "we need
architecture change X" → charter card, never inline work.

---

## C4 — Rubric V3 against langgraph 1.2.9 (honest re-baseline)

**Mission.** Re-pin the oracle to the current release (1.2.9 at authoring —
S0 re-verifies latest on PyPI and pins THAT) and mint the V3 overlay. Prior
scores are VOID on rubric edit by frozen-rubric law — this campaign
re-earns the number honestly rather than dragging a stale pin.

**Slices.**

- **C4-S0** — pin + drift audit: install the new pin in a scratch venv; run
  EVERY existing workload arm pair; commit
  `reports/governance/dharmagraph_parity/DRIFT_AUDIT_<ver>.md` classifying
  each divergence as (i) langgraph behavior change (cite changelog/source),
  (ii) our recorded deviation now stale, or (iii) new bug on either side.
  No rubric edit until the audit is complete — the audit DECIDES the V3
  content, not vice versa.
- **C4-S1** — author V3 overlay: base = V2, plus drift corrections, plus
  C3's ratified addendum rows. Status `FROZEN_BEFORE_V3_RESULTS`, weighting
  assertion recomputed, operator signs the freeze commit BEFORE any arm
  runs against it. **C4.2 DECLARED AMENDMENT:** the gauntlet script's
  custody constants (`_ORACLE_PIN`, rubric path, freeze-commit declaration)
  are trust-root edits, forbidden by default; they land as ONE reviewed
  commit whose diff touches ONLY the pin string, the V3 path, and the
  declared freeze SHA — judge-reviewed like C1.4.
- **C4-S2** — full two-arm re-run + builder/judge reseal on V3. The new
  score is whatever it honestly is; if drift LOWERED a previously-proven
  row, that row gets a STOPPED-or-fix decision in the ledger, never a
  silent workload adjustment (existing workloads stay frozen; drift fixes
  go through NEW workloads or engine changes).
- **C4-S3** — retire the 1.2.4 pin everywhere (`pyproject.toml`
  `test-oracle` extra, oracle test skip-guards), one commit, full suite.

Done-block: `--check` PASS on V3 at the campaign head + drift audit
committed + operator freeze signature in the ratification registry.

---

## C5 — Moat build (what none of them have)

**Mission.** Spend the parity dividend on capabilities where this repo is
structurally ahead. Charter at S0 from: (a) the two standing candidates
below, (b) C3's chartered cards, operator picks 2–3 total. Each card
becomes its own handoff with a done-block BEFORE any code — this section
deliberately does not pre-write them; C5-S0's first deliverable is the
handoff files, reviewed by the operator, in the predecessor's format.

**Standing candidate 1 — DST chaos gauntlet.** Grow `SimulatedEffects` into
a fault-injection harness (torn checkpoint, crash-between-journal-and-apply,
interrupt-during-retry, clock skew) with seeded, replayable fault schedules
— Antithesis discipline on our own engine. Metric shape: N seeded fault
schedules × M workloads, zero invariant violations (§3 properties as the
invariant set), every violation a replayable seed. This also productizes
C1's receipt rung: deterministic chaos evidence + Art. 12 receipts is a
compliance story none of the frameworks in C3's set carry.

**Standing candidate 2 — Telos-gated execution.** Gates as first-class
graph primitives: a node/edge can require a `TelosGatekeeper` verdict, with
the gate check itself receipted in the run's chain. Read
`docs/architecture/EVOLUTION_PROPOSAL_GATE_CONTRACT.md` FIRST (WS4
hard-reject semantics); the gate battery count comes from `telos_gates.py`,
never prose.

**Explicit wall:** topology evolution (DarwinEngine mutating graph
topologies) stays OUT of C5 — the Phase-6 wall is operator-gated per the
track's claim boundary and `organism-rewire` D4. If a C5 card drifts toward
it, that is a STOP, not a stretch goal.

---

## 3. Definition of done (whole ascent)

C1, C2, C4 merged with resealed custody at ≥74.00 on V2-lineage and an
honest V3 baseline; C3 dossier + ≥3 chartered cards delivered; C5's
chartered cards merged with their own done-blocks green; every campaign's
ledger reconciles with `git log`; zero self-merges; every unclosed target
carries a STOPPED entry naming the unsettled question. The organism runs
its application scenarios on the engine it owns — that, not the score, is
what the hill was for.
