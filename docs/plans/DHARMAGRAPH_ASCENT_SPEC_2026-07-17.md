# DharmaGraph Ascent — parallel lanes, one hill, near-zero operator touch (v2)

**You are a fresh Claude Code instance on `/home/user/dharma_swarm`.** This is
the master spec for the post-Pregel-core ascent. Predecessor: PR #1002
(52.00 → 58.00, six execution-core cards FULLY_PROVEN, merged to main as
`1d45916d`). Its handoff — `docs/plans/handoffs/DHARMAGRAPH_HANDOFF_CLAUDE.md`
— is the STYLE CONTRACT for everything here: machine-checkable done-blocks,
one slice per iteration, append-only ledgers, git-is-truth reconciliation,
stop-conditions-as-success, builder/judge separation, custody reseal on
evidence. Campaign context: `docs/plans/DHARMAGRAPH_PHASED_SPEC_2026-07-05.md`;
active track `dharmagraph-engine-2026-07`.

**Design constraint (operator-declared 2026-07-17): the operator is
time-poor.** Every gate in this spec is therefore designed so that agents
proceed without waiting on a human wherever governance allows, human
attention is batched, and the merge of the PR carrying this spec is itself
the ratification act.

## 0. Ratification = merging this PR

The PR that introduces this file also carries the `ACTIVE_TRACK.yaml`
update (ascent surfaces added to `owned_surfaces`, ascent lanes added to
`next_items`, stale parity items reconciled to the post-#1002 receipt).
**Merging that PR IS the §0 ratification.** No separate YAML surgery, no
signature ceremony. Defaults that apply on merge:

- **Builder seats:** any Claude Code session launched against a lane's
  handoff (human-started or routine-started, §6).
- **Judge seat:** the existing independent hourly verifier. Every reseal
  needs its signature in `DHARMAGRAPH_JUDGE_RATIFICATIONS_V1.json` before
  a lane PR leaves draft; a builder never cites its own judge emission.
- **Merge authority:** the operator, or Merge Master Mike under the
  standing conditions in §6.3. Builders NEVER merge.
- **Declared harness amendments** (§C1.4, §C4.2 — the only two touches of
  otherwise-frozen machinery): pre-authorized in principle by this merge,
  but each still lands as its own judge-reviewed commit with the
  only-this-diff rule; any wider diff = revert + STOP.

## 1. The hill and the lane DAG

One number climbs: the judge-receipt score
(`reports/governance/dharmagraph_parity/judge_receipt.json`), measured ONLY
by `python3 scripts/governance/dharmagraph_parity_gauntlet.py --check` at a
clean committed head. Current: **58.00/100**. Frozen-rubric law (predecessor
§7) applies verbatim to V1+V2 until L-D mints V3.

Lanes are surface-disjoint and run **in parallel** — the serial C1→C5 of v1
is replaced by this dependency DAG:

```
ratification merge
      ├── L-K  kernel extraction        (no deps; 1 slice)
      ├── L-A  organism wiring          (no deps)          58→63
      ├── L-B  reliability ring         (no deps)          63→74 *
      └── L-C  frontier scan            (no deps; research)
                 └── L-D  rubric V3 @ latest langgraph  (needs L-C addenda + L-A/L-B merged)
                 └── L-E  moat build    (needs L-C cards; operator picks)
```

\* Score deltas assume both land; L-A and L-B contribute independently
(+5.00 and +11.00 against the frozen weights: APP01 w4 / APP02 w1 / APP03
w2 / APP04 w3 all at 1pt; LG19 w1, LG20 w2, LG24 w4, LG25 w2 at 0pt; LG26
w4 at 1pt; total weight 100).

| Lane | Branch | Surfaces (disjoint by construction) |
|---|---|---|
| L-K | `claude/dharmagraph-ascent-lk` | `docs/governance/CAMPAIGN_KERNEL.md` (new; promoted from Appendix A) |
| L-A | `claude/dharmagraph-ascent-la` | `tests/oracle_support/scenarios.py`, `tests/oracle_support/outcomes.py`, `dharma_swarm/workflow.py`, `docs/plans/handoffs/DHARMAGRAPH_ASCENT_LA.md` |
| L-B | `claude/dharmagraph-ascent-lb` | `dharma_swarm/graph/**` (engine internals), `tests/test_graph_pregel_properties.py`, `docs/plans/handoffs/DHARMAGRAPH_ASCENT_LB.md` |
| L-C | `claude/dharmagraph-ascent-lc` | `docs/plans/DHARMAGRAPH_FRONTIER_DOSSIER_*.md`, `docs/plans/handoffs/DHARMAGRAPH_ASCENT_LC.md` |
| L-D | `claude/dharmagraph-ascent-ld` | rubric V3 file, gauntlet custody constants (§C4.2), `pyproject.toml` test-oracle pin |
| L-E | `claude/dharmagraph-ascent-le` | chartered per card at L-E S0 |

**Shared-file law (the one real coupling):** `tests/oracle_support/
dharmagraph_gauntlet.py` (append-only extensions) and
`reports/governance/dharmagraph_parity/**` (reseals) are touched by BOTH
L-A and L-B. Rule: lanes develop in parallel, but **evidence commits
serialize through main** — a lane reseals only at its own final head after
rebasing onto current main (the predecessor's any-commit-after-emission
rule already forces exactly this). Harness appends live in clearly bounded,
lane-labeled sections at file end so rebase conflicts stay append/append.
First lane to go Ready merges first; the second rebases, re-runs its
VERIFY, re-emits, reseals. Never resolve a receipt conflict by hand-editing
receipt JSON — always re-emit.

## 2. The loop (every lane, every iteration — the Campaign Kernel)

1. `cd /home/user/dharma_swarm && make onboard` — READY or fix/report.
2. Read the lane handoff (`docs/plans/handoffs/DHARMAGRAPH_ASCENT_<lane>.md`),
   then its PROGRESS LEDGER (bottom of the same file; append-only; one
   block per iteration: `slice / result / verify / learned / blocked`).
   **Bootstrap rule:** if the handoff file does not exist yet, THIS
   iteration IS the lane's S0 — create the handoff from this spec's §3
   lane section (mission, slices, VERIFY block, empty ledger skeleton),
   create the lane branch, open the draft PR, append the first ledger
   entry, and end the iteration there. A missing handoff is the start
   signal, never a blocker.
3. `git log --oneline -15 && git status && git branch --show-current` — git
   is truth, ledger is claim; reconcile, fix the ledger if they disagree.
4. Run the lane's VERIFY block. **Red? Fixing red IS this iteration.**
5. Else take the FIRST TODO slice whose deps are DONE. Do ONLY it.
6. Verify → commit (`feat(graph): <lane>-S<n> <title>`, ledger in the same
   commit) → score-probe where evidence moved (emit builder receipt, diff
   ONLY expected rows, `git checkout -- reports/governance/dharmagraph_parity/`)
   → push.
7. Stop conditions (halting is success): 3 consecutive failed attempts on
   one facet → STOPPED ledger entry naming the unsettled question, move on.
   Metric flat across 2 green iterations → lane is spinning; STOP, write
   findings. A fix needing a hot-path file beyond a declared seam, another
   track's surface, a new dependency, or any gate weakening → STOP and
   document. A question the rubric + pinned langgraph source + an empirical
   run cannot settle → STOPPED entry, next slice.

PR discipline per lane: ONE branch, ONE draft PR opened at S0 (all four
Coherence Delta fields substantive), Ready only after reseal + judge
signature, **never self-merged**.

Environment invariants (paid for in #1002): unshallow before any gauntlet
run; `pip install -e ".[dev,test-oracle]"` (debian-cryptography workaround:
`pip install --ignore-installed cryptography` first); langgraph pin 1.2.4
until L-D re-pins; every module ≤500 lines — extract BEFORE crossing;
cross-axis regression pins for every reviewer finding (typed×resume and
sync×timeout proved single-axis workloads miss seam bugs); reviewer rounds
after Ready are expected — fix, pin, reseal, per the predecessor's review
round.

## 3. Lane specs

### L-K — Campaign Kernel extraction (1 slice; unblocks the whole portfolio)

Promote Appendix A verbatim into `docs/governance/CAMPAIGN_KERNEL.md` with
a short header naming #1002 as the proving run AND an explicit authority
disclaimer: the kernel is REFERENCE material — a proven working pattern,
not doctrine. It sits outside the canonical authority stack
(`docs/AGENTS.md`; `CLAUDE.md` owns behavior, `ACTIVE_TRACK.yaml` owns
scope) and grants nothing: a track adopts the kernel only through its own
owner files and its own operator gates. No pointer edits to any canonical
entrypoint doc (`BUILD_SESSION_ENTRYPOINT.md` is another owner's surface)
— the kernel doc stands alone; adoption is pull, not push. Done-block:
file exists with the disclaimer, `make docops-integrity` green, PR merged.
This is still the 1000x seed — every OTHER track can copy the loop without
touching this campaign — but as an offered pattern, never a shadow
authority surface.

### L-A — Organism wiring: the engine becomes the substrate (+5.00 → APP rows 2/2)

**Mission.** The engine is `claim_mode: candidate/test_only` — 58 points of
shelf inventory. All four APP rows fail exactly the
`neutral_engine_integration` facet family (APP04 adds `domain_isolation`,
`memory_isolation`): the application oracle still runs the clone lineage.
Port it to the neutral engine, add a shadow-mode production seam, land the
Art. 12 receipt rung (EU AI Act Art. 12 applicable **2026-08-02** — the
one true deadline in this spec).

**Done-block (exit 0 at lane head):**

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
python3 -m pytest tests/test_workflow.py -q
```

**Slices.** S0 branch+handoff+draft-PR+baseline (STOP the lane if `--check`
≠ PASS on clean main). S1 read `scenarios.py`/`outcomes.py` end to end and
write (handoff, not code) the primitive→engine-surface map (handoff →
interrupt/Command·resume, agent turn → node, transfer → goto, isolation →
schema projections + subgraph); unmapped primitives become the S2 gap list.
S2–S4 port swarm / supervisor / isolation scenario families one per slice —
the EXISTING `diff_outcomes` comparisons against the real langgraph arm are
the frozen referee and may not be edited. S5 production seam:
`dharma_swarm/workflow.py` engine path behind `DHARMA_GRAPH_ENGINE=1`
(default off), shadow mode: run legacy AND engine, compare final states,
divergence receipts under `~/.dharma/` (never git). If the seam truly
cannot land without `orchestrator.py`/`swarm.py`, that slice carries
`[impact-checked]` + packet-bound preflight + a minimal call-site diff — or
STOPs. S6 receipt rung: engine-executed supersteps emit `GraphRunEvent`
into the spine receipt log via the existing `derive_graph_side_effect_key`
vocabulary (`durable_invoker`) — wire, don't invent; evidence = replayed
run's receipt chain digest-matches its checkpoint chain. S7 reseal + Ready.

**§C1.4 DECLARED HARNESS AMENDMENT (judge-reviewed commit).**
`_finalize_rows` unconditionally appends the APP caveat "Existing
application oracle exercises the clone lineage… row is capped below 2" —
false once the oracle runs the neutral engine. Amendment: make the caveat
conditional on the `neutral_engine_integration` facet actually failing.
Own commit; judge review in-PR; before/after receipt diff must show the
ONLY change is the caveat string on rows whose facets independently prove
2/2. Wider diff = revert + STOP.

**Extra stop condition:** shadow-mode divergence tracing to a LEGACY bug →
Discovered section, do not fix legacy, never bend the engine to reproduce a
legacy defect — parity is with langgraph and correct outcomes.

### L-B — Reliability ring (+11.00 → LG19/20/24/25/26 2/2)

**S0 is the debt, not a feature:** identity-preserving pending-write
journal (`dharma_swarm/graph/journal.py`, new, ≤500) recording
`(channel, value, node_id, task_seq)` — kills both recorded deviations from
#1002 (failure-resume reducer interleave; ambiguous Send-multiplicity
degradation). Property 3 tightens from "converges" to "byte-identical
trace" in the same slice. Retries and timeouts stress exactly these paths;
build on the fixed floor.

**Then one row per slice, riskiest first, the #1002 recipe verbatim
(empirical derivation from the pin → engine change → append-only two-arm
workload → fail-closed applier):**
S1 LG24 retries (`RetryPolicy`: max_attempts, backoff, jitter, retry_on —
jitter MUST route through `effects.random()`, DST law). S2 LG25 timeouts
(node/step timeout, heartbeat refresh, idle timeout on the S6
`asyncio.timeout`+`to_thread` base). S3 LG19 `interrupt_before`/`after`
(static, compile-time, on the S7 substrate). S4 LG20 dynamic suite
(multiple interrupts, ordering, node re-execution, resume routing — frames
already key by full task identity; prove the matrix). S5 LG26 remainder
(`error_handler`, `sibling_cancellation`, `user_cancellation`). S6
predecessor properties 6–8 (version monotonicity/exactly-once, quiescence,
replay determinism) — deferred then, earning their keep here. S7 reseal +
Ready.

Done-block: C1-shape with `core = ["LG19","LG20","LG24","LG25","LG26"]`
and `>= 74.00` — adjust the floor to `69.00` if L-A has not merged yet
(the two lanes' gains are independent; the ledger records which floor was
in force and why). Harness region 1580–1720 and all existing workloads
stay untouched; error-parity-is-not-parity in every new applier.

### L-C — Frontier scan (research; no engine code)

Survey set (amend at S0): Temporal, Restate, DBOS, Inngest, Hatchet
(durable execution); AutoGen, CrewAI, OpenAI Agents SDK, Pydantic-AI,
Mastra (agent orchestration); +1 wildcard the scan surfaces. Loop variant:
each iteration = one system: (a) primary-source sweep (docs/source/
changelogs; marketing pages never sole-source); (b) extraction against a
fixed frame (durability model, failure semantics, human-in-loop,
timers/events, topology, observability, compliance story); (c) adversarial
pass — attempt to REFUTE every "they have X we lack" claim from their
source or our receipts; (d) cited ledger entry. Citation-or-silence with
full force.

Deliverables (their existence + review = done): the dossier
(`docs/plans/DHARMAGRAPH_FRONTIER_DOSSIER_<date>.md`, ≥2 independent
sources per load-bearing claim, an explicit refuted-claims section); ≥3
chartered capability cards in done-block form ready for L-E (standing
candidates to beat: durable timers, external event waits, human-task
queues); a proposed V3 addendum list for L-D (proposals only; L-D
freezes). Hard cap 12 iterations (the survey set is 11 systems —
5 durable-execution + 5 orchestration + 1 wildcard — plus one spare
for a re-visit; trimming the set at S0 lowers the cap with it).

### L-D — Rubric V3 @ latest langgraph (honest re-baseline)

S0: re-verify the latest release on PyPI (1.2.9 at authoring) and pin
THAT; drift audit in a scratch venv — run EVERY existing workload arm pair,
commit `reports/governance/dharmagraph_parity/DRIFT_AUDIT_<ver>.md` (inside
the track's existing `reports/governance/dharmagraph_parity/**` surface)
classifying each divergence as (i) langgraph
behavior change (cite changelog/source), (ii) stale recorded deviation,
(iii) new bug on either side. **The audit decides V3 content, never vice
versa.** S1: author V3 (base V2 + drift corrections + L-C's ratified
addenda), status `FROZEN_BEFORE_V3_RESULTS`, weighting assertion
recomputed; freeze commit lands BEFORE any arm runs against it. **§C4.2
DECLARED AMENDMENT:** the gauntlet script's custody constants (oracle pin,
rubric path, freeze SHA) are trust-root edits — ONE judge-reviewed commit
touching ONLY those strings. S2: full two-arm re-run + builder/judge
reseal; the new score is whatever it honestly is; drift that lowers a
previously-proven row gets a fix-or-STOPPED decision, never a workload
adjustment. S3: retire the old pin everywhere (`pyproject.toml`, oracle
skip-guards), one commit, full suite. Done-block: `--check` PASS on V3 +
committed drift audit + freeze entry in the ratification registry.

### L-E — Moat build (what none of them have)

Charter at S0 from: the standing candidates below + L-C's cards; the
operator picks 2–3 **as part of one batched gate** (§6.4). Each card
becomes its own handoff with a done-block BEFORE any code.

**Standing candidate 1 — DST chaos gauntlet.** Grow `SimulatedEffects`
into seeded fault-schedule injection (torn checkpoint, crash between
journal and apply, interrupt-during-retry, clock skew): N schedules × M
workloads, zero invariant violations (§2-properties as the invariant set),
every violation a replayable seed. With L-A's receipt rung this is a
compliance story (Art. 12 + deterministic chaos evidence) no system in
L-C's survey carries.

**Standing candidate 2 — Telos-gated execution.** Gates as first-class
graph primitives: nodes/edges requiring a `TelosGatekeeper` verdict, the
check itself receipted in the run chain. Read
`docs/architecture/EVOLUTION_PROPOSAL_GATE_CONTRACT.md` FIRST; the gate
battery count comes from `telos_gates.py`, never prose.

**Standing candidate 3 — The strange loop: campaigns as graphs.** Once
L-A's seam is live, run ascent campaigns AS DharmaGraph graphs: operator
gates = `interrupt()` → `Command(resume=)`, flaky slices = L-B retry
policies, the ledger = the receipt chain, seat fan-out = `Send`. Every
campaign iteration then doubles as an integration test of the engine
under its most demanding real workload — the organism building itself
with itself.

**Explicit wall:** topology evolution (DarwinEngine mutating graph
topologies) stays OUT — Phase-6 is operator-gated per the track's claim
boundary and organism-rewire D4. Drift toward it = STOP, not stretch goal.

## 6. Automation: the campaign runs itself

### 6.1 Seat routines (arm AFTER the ratification merge)

One recurring routine per active lane, **fresh session per firing**
(create_new_session_on_fire), cadence 4h staggered, prompt fully
standalone because each firing starts from nothing:

> You are the BUILDER seat for lane <L-x> of the DharmaGraph Ascent.
> Read `docs/plans/DHARMAGRAPH_ASCENT_SPEC_2026-07-17.md` §1 (lane DAG),
> §2 (the loop), and §3 (<L-x>). FIRST verify §1's dependencies for your
> lane are satisfied (deps merged / deliverables exist); if not, exit
> WITHOUT changes — a dependency-blocked lane is idle, not TODO. Then
> execute EXACTLY ONE iteration of the loop: onboard, reconcile ledger
> vs git, verify, then either fix red or do the first TODO slice. If the
> lane handoff file does not exist yet, this firing IS the lane's S0:
> create it per §2's bootstrap rule (handoff + branch + draft PR) and end
> the iteration there.
> Commit, push, update the lane PR body, append the ledger. If the lane
> is DONE or STOPPED, say so in the PR body and stop making changes.
> NEVER merge. NEVER touch another lane's surfaces.

The loop's own ground-truth re-derivation makes fresh-session amnesia
safe — that is what §2 was designed for. A wedged lane self-reports via
its stop conditions instead of spinning (the flat-metric rule).

### 6.2 Judge cadence

The independent hourly verifier already watches the repo. Lane PRs signal
readiness in their body ("reseal at <sha>, awaiting judge"); the judge
signs into the ratifications registry or files findings as PR comments.
Builders react to findings like any review round (#1002 precedent: fix,
pin, reseal).

### 6.3 Merge without waiting (Mike)

Lane PRs carry `mike-watch` while in development (Mike runs the gate
and posts status but never merges — `automerge.yml` sets
`merge_when_clean=false` for this label by design). When a lane goes
Ready for Review with reseal + judge signature in place, the builder
ADDS the `automerge` label (or comments `@mike merge`) — that is the
workflow's actual arming contract; `mike-watch` alone never auto-merges.
Standing conditions the operator sets ONCE in Mike's own config:
auto-merge a lane PR when (a) all required checks green, (b) judge
signature present for any evidence commit, (c) diff confined to the
lane's declared surfaces, (d) no hot-path file. PRs failing (c)/(d)
wait for the human. This spec does not modify Mike; it only formats
lane PRs to be Mike-mergeable.

### 6.4 The operator's whole job (batched, ~15 min/week)

One weekly pass: (1) glance at the scoreboard (§7) and any STOPPED
entries; (2) answer accumulated `Open design questions` sections in lane
PR bodies; (3) the two one-time picks — L-E card selection, L-D addenda
ratification. Everything else proceeds without you; nothing waits on you
except the things only you can decide.

## 7. Scoreboard (definition of done, whole ascent)

- L-K merged: kernel doc exists — the discipline is portable.
- L-A + L-B merged with resealed custody: judge receipt ≥ 74.00, APP rows
  and reliability rows 2/2 (or honest STOPPED entries naming the wall).
- L-C dossier + ≥3 chartered cards delivered and refuted-claims section
  non-empty (an honest "they don't have it either" is a finding).
- L-D: V3 frozen-before-results, drift audit committed, honest new
  baseline emitted.
- L-E: chartered cards merged green against their own done-blocks.
- Every lane ledger reconciles with `git log`; zero self-merges; every
  unclosed target carries a STOPPED entry naming the unsettled question.
- The organism runs its application scenarios on the engine it owns —
  that, not the score, is what the hill was for.

---

## Appendix A — The Campaign Kernel (verbatim source for L-K's promotion)

A campaign is a hill-climb executed by amnesiac agents. It needs exactly
six properties; everything else is decoration:

1. **A machine-checkable done-block.** A script that exits 0 when the
   campaign is done, runnable by anyone, gameable by no one. Never weaken
   its thresholds; adjust only if the measured artifact's schema itself
   moved, and only so the check still finds its targets.
2. **One slice per iteration.** An iteration = re-derive state from ground
   truth (repo status, git log, the ledger), verify, then do the FIRST
   undone slice — never two, never slice N+1 while N is red.
3. **An append-only ledger** in a committed file: one block per iteration
   (`slice / result / verify / learned / blocked`). Git is truth, the
   ledger is claim; every iteration reconciles the two and fixes the
   ledger, never history.
4. **Stop conditions where halting is success.** Three strikes per target
   → STOPPED with the unsettled question. Metric flat two green iterations
   → the loop is spinning; stop and report. Out-of-authority fix (foreign
   surface, hot path, new dependency, gate weakening) → stop and report.
   An honest miss with a named question beats a gamed hit, always.
5. **Evidence custody.** Where the campaign produces evidence (receipts,
   scores, audits), it is emitted by a builder, verified by an independent
   judge, sealed against the source digest, and re-emitted whenever any
   commit follows an emission. Builders never cite their own judge run.
6. **Verification before commitment.** The verify battery runs before
   every commit; the commit message names the slice; the PR body stays
   current every slice; reviewer findings get reproduced first, fixed
   second, pinned with a regression test third.

Proving run: dharma_swarm PR #1002 (52.00 → 58.00 in ten iterations plus
an autonomous ten-finding review round, zero gamed numbers, two honest
recorded deviations). Adopt by copying the loop, not the domain: write the
done-block first, the slices second, the ledger skeleton third — then
hand it to any agent.
