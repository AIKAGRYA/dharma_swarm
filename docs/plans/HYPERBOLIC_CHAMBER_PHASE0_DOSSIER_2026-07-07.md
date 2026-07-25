# Hyperbolic Time Chamber — Phase 0 Dossier (2026-07-07)

**Role:** the ratification dossier for THE SEAL
(`docs/vision_maps/MASTER_2026-07-07_hyperbolic_time_chamber.md` §7).
Phase 0 ships THIS dossier plus its two measurement instruments; build begins
only after operator ratification. Authority: subordinate to
`docs/vision_maps/NORTH_STAR.md` and the chamber doctrine file; if this file
disagrees with `make onboard`, `docs/governance/ACTIVE_TRACK.yaml`, or any
receipt, trust those.

**Trust rule:** every claim below is a command run on 2026-07-07 on this
session host (branch `claude/hyperbolic-chamber-phase-0-ok27i3`, base
`d0a2c5d` = merge of PR #829) or a file:line read this session.
Unverifiable-on-this-host = UNKNOWN, never green.

**Scope firewall (unchanged from doctrine §2):** afferent-open,
efferent-closed. Ingestion is read-only world contact; actions INTO the world
are out of scope entirely. Gym gradients drive autoresearch loops; archive
fitness for self-modification still requires the One Wire external quorum
(N≥5, M≥3). No gate, ratchet, or quorum is weakened by anything here.

---

## 0. Sublation record — what the sibling already shipped, verified

The seal's sublation clause was executed first. Findings, each verified this
session:

- The earlier "Inward Ascent" sibling (Devin lane) **completed and merged**
  its Phase-0 output: PR #828 (`2128e7a` on `origin/main`) landed
  `docs/plans/INWARD_ASCENT_PHASE0_DOSSIER_2026-07-07.md` (read in full),
  `scripts/governance/inward_ascent_baseline.py`, and the digest-stamped
  `reports/governance/inward_ascent/baseline_receipt.json`. The branch
  `devin/1783399112-inward-ascent-phase0` no longer exists on the remote
  (`git fetch` → `couldn't find remote ref`); its work is absorbed via main.
- No Inward-Ascent track was applied to `docs/governance/ACTIVE_TRACK.yaml`
  (grep this session: no match) — the sibling correctly left its track entry
  as a draft awaiting ratification (§(e) of its dossier).
- The chamber doctrine itself (PR #829, `d0a2c5d`) merged AFTER the sibling's
  dossier and names what the seal adds over that prompt (doctrine §6).

**Division of labor in this dossier (absorb, extend, never duplicate):**

| Seal deliverable | Status |
|---|---|
| (a) Ingest map | ABSORBED — Inward-Ascent §(a) stands as written; chamber deltas in §1 below |
| (b) Gym spec 3–4 envs | ABSORBED — G1/G2/G3 + operator-gated G4 with adversary red-team stand; chamber deltas (envs 9–15 triage, compute-ROI, substrate ruling) in §2 below |
| (c) Frontier Ledger spec + first render | **NEW, this session** — §3 |
| (d) 10x Baseline Scoreboard | ABSORBED + verified on this host — §4 |
| (e) The door | **NEW, this session** — §5 |
| Draft ACTIVE_TRACK.yaml entry | SUPERSEDED — one chamber track absorbing the sibling's draft — §7 |
| Operator decision queue | MERGED — doctrine §8 + sibling §(f) — §8 |

---

## 1. (a) Ingest map — chamber deltas over the absorbed map

The four-class ingest map (zeitgeist / code-world / knowledge-world / market),
landing doctrine (Go organs → Bronze quarantine → Chetana
ingest→stage→gate→promote → MemoryKernel/ontology, **no new truth stores**),
schemas, cadences, and sequencing are owned by
`INWARD_ASCENT_PHASE0_DOSSIER_2026-07-07.md` §(a) and are not restated. The
zeitgeist path was verified live-capable there (HN Algolia fetch → bronze
landing, zero credentials). Chamber doctrine adds three welds:

**1a. Demand-driven consumer bindings (discipline 4, made explicit).** No
source turns on without this table having a filled row; a source whose scorer
does not move within its first review window is turned OFF (hoarding is the
mirror wearing a new mask):

| Source class | Named consumer loop | Scorer that must move | Hoarding check |
|---|---|---|---|
| Zeitgeist | Gym G2 (forecasting) prediction emission; Loop 5 sensing | resolved-prediction Brier (`ginko_brier.compute_brier_score`) | bronze-consumption ratio (landed vs consumed-by-G2) rendered per cycle |
| Code-world | Frontier Ledger field column (§3); gym G1 external-repo expansion | ledger rows flipping UNKNOWN→number with receipt URLs | ledger UNKNOWN count must fall; flat = hoarding |
| Knowledge-world | Gym G3 (retrieval/memory + ontology arms) | G3 arm-A hit-rate / arm-B precision@k | QA-pairs-generated per corpus batch > 0 |
| Market | operator funding brief only (firewalled) | none (by doctrine — never a fitness input) | automated check: no market receipt hash in any gym taskpack (sibling §(a) col 4) |

**1b. The immune system (discipline 5).** Already partially coded — verified
this session in `dharma_swarm/world_radar/bronze.py`: payloads carry
`payload_must_not_be_executed`, W3C-PROV-minimal provenance, corroboration
`required_k=2`. Chamber welds on top: (i) no bronze text is ever interpolated
into an agent instruction stream unlabeled — promotion through the Chetana
gate is the ONLY path from bronze to any context an agent reads; (ii)
AHIMSA/SATYA screening runs at the Chetana gate, not after; (iii) provenance
tags travel with every promoted fact to the MemoryKernel/ontology.

**1c. BR-004 cron split-brain** is prerequisite plumbing for any always-on
cadence and is already queued under organism-rewire's D1/VPS item — the
chamber does NOT own it (surface discipline); it is decision-queue item 3.

**Surface ownership:** `tools/*_go/**` and `dharma_swarm/world_radar/**`
remain owned by `organism-rewire-2026-07`. Chamber ingest work lands via that
track's next-items or as NEW fetcher/consumer modules on chamber surfaces.

---

## 2. (b) Gym spec — chamber deltas over the absorbed battery

The picked battery stands as specified and adversarially red-teamed in
Inward-Ascent §(b): **G1 git-history repo gym** (doctrine env 2), **G2
forecasting gym** (env 3), **G3 retrieval/memory + ontology gym** (envs 4+6
merged), **G4 runtime-history replay** (env 1, operator-gated on a sanitized
`runtime.db` snapshot), with the gate red-team gym (env 5) deferred-not-killed
until its attack corpus is imported, self-model (env 7) folded into G1 as a
later scorer arm, and differential-oracle expansion (env 8) owned by the
dharmagraph track. Every environment: frozen sha-pinned taskpack,
deterministic scorer, held-outs + rotation, per-scorer gaming table with kill
criteria. Nothing here reopens those specs.

**2a. Triage of doctrine envs 9–15** (the seal's additions the sibling's
prompt did not contain):

| Env (doctrine §3.2) | Disposition | Why |
|---|---|---|
| 9 paper-to-patch | Phase 2+, gated on knowledge-world ingest being live | its gradient source (arXiv full-text) does not exist until the mouth eats; highest ceiling, wrong first move |
| 10 time-lagged external PR gym | Phase 2+, cheapest reality-graded expansion after G2 | same time-lagged class as G2 (the world grades us, zero exposure); needs code-world ingest of live issues; SUBMITS NOTHING (efferent stays sealed) |
| 11 shadow efferent mode | Phase 2+, spec'd with the door (§5) | its output is the release corpus for door-opening day; premature before any gym closes |
| 12 trace distillation | Phase 2+, unlocks the 10,000x arithmetic | needs a volume of real traces the gym must first produce; its cost number is already a ledger row (§3) |
| 13 digital-twin chaos gym | defer to dharmagraph track boundary | extends `graph/effects.py` (dharmagraph-owned surface); propose via that track's next-items, not here |
| 14 benchmark-forge | Phase 2+, the flywheel's growth organ | consumes ingest that must exist first |
| 15 public coding benchmarks | operator-gated (decision queue 5: compute budget) | the literal C2 bar; needs strict held-out discipline + budget-parity controls per arena doctrine |

**2b. Compute-ROI ledger (discipline 9).** Rule welded now: **every
environment declares cost-per-scored-iteration before its first evolution
run**, and the flywheel routes compute by score-per-dollar. Day-one estimates
(order-of-magnitude, to be replaced by measured numbers in each env's first
receipt): G3 ≈ near-zero marginal (exact-match over content-addressed
receipts); G2 ≈ near-zero scoring, bounded prediction-emission inference; G1 ≈
one pytest run + one bounded agent generation per task (the expensive one —
inference-bound, which is exactly why the substrate ruling says no Rust here
yet); G4 ≈ cheap replay over ~2k rows once the snapshot exists. The aggregate
renders as the `distilled_seat_cost_per_iteration` ledger row (UNKNOWN today,
honestly).

**2c. Substrate ruling applied (doctrine §3.6).** The environment protocol is
**language-agnostic by construction from day one**: an environment is a
process speaking JSONL receipts across a narrow boundary — the contract the
Go organs already prove (`world_radar/go_invoke.py` pattern:
toolchain-checked invocation, structured `needs_host` errors, never an
exception into the caller). Phase-1 build codifies this as the environment
interface spec (stdin: task JSON; stdout: JSONL result rows carrying
`digest`; nonzero exit = structured error row, never a traceback). Python
stays the composition root — gates, spine, Chetana, receipt ownership are
never reimplemented elsewhere. Rust/C++ is **earned per component**: the
named candidates are (i) the sandbox jail for executing untrusted evolved
code (G1's leak-free worktree sandbox is the first place this becomes
safety-critical), (ii) hot scoring kernels only after a specific environment
MEASURES as iteration-bound rather than inference-bound (G4 row-replay at
future volume is the plausible first case), (iii) digest/Merkle chains at
volume. No default rewrite; each carve-out arrives with its own measured
justification in the compute-ROI ledger.

**2d. RSI-lab boundary contract (doctrine §3.7).** The RSI/arena lab
(operator Mac + maharaja VPS) owns C2 measurement and the arena surfaces
(`dharma_swarm/coordination/**`, `council/**`, `reports/governance/arena/**`).
The chamber: disjoint surfaces (§7's track entry lists them), shared
fitness-receipt format (digest conventions identical to
`check_track_status._recompute_digest`, verified this session) and MAP-Elites
descriptors (`archive.py`), no duplicated C2 measurement — the ledger (§3)
READS trust-gate C2; it never computes it. Discipline 3 (fix C2 first) is
honored by sequencing: the chamber's volume scaling (env 12/15 class) waits
on or feeds the RSI lab's coordination fix; G1–G3 measure substrate, not
swarm-lift.

---

## 3. (c) The Frontier Ledger — spec + first render (NEW, built this session)

**What it is (doctrine §3.4):** the machine-maintained owned surface
answering, per capability: our measured number (from gym/baseline receipts)
vs. the field's published number (from ingest; seeded today from NORTH_STAR
§10's receipted comparators), delta, commensurability, receipts — plus the
door panel (§5) and the chamber-drift slot (discipline 11). It replaces
hand-curated NORTH_STAR §10 as the living instrument and gives trust-gate C2
a live denominator.

**Owner (new, this session):** `scripts/governance/frontier_ledger.py` →
`reports/governance/chamber/frontier_ledger_receipt.json` (digest-stamped,
`check_receipt_valid(..., expect_digest=True)` verified passing this session:
"digest intact, fresh") + `reports/governance/chamber/FRONTIER_LEDGER.md`
(the one page). Both committed alongside this dossier.

**Replay contract:** `--check` verifies (i) the tamper seal recomputes
(checker-compatible digest), (ii) the pinned sha256 of the baseline-receipt
input still matches the committed baseline receipt (input drift = failure),
(iii) the markdown page re-renders **byte-for-byte** as a pure function of
the committed receipt. A refresh (no flag) re-reads the live owners
(trust-gate script, baseline receipt) and re-stamps. Run this session: render
OK, `--check` OK.

**First render honesty line:** 2/9 capabilities measured, 7/9 UNKNOWN; door
CLOSED (C1 AMBER, C2–C5 RED); exactly one field number carries a receipt
(DGM 50.0% SWE-bench-verified, arXiv:2505.22954). One measured number is
negative (swarm lift −0.1, `reports/anatomy_altitude_2026-06-10/`, marked
NOT-commensurable per the trust-gate admissibility rule). **A sparse, mostly
UNKNOWN, honestly negative first render is the point** — F5 said no
comparative world-model exists; now the empty instrument exists and every
UNKNOWN is a named debt.

**Rules welded in:** field numbers REQUIRE receipt URLs (no receipt → renders
`UNKNOWN_PENDING_INGEST`, never remembered prose); internal lift is never
presented as benchmark-commensurable (C2 admissibility rule respected in the
`commensurable` column); the ledger is `authority: projection_only` — it owns
no fact.

**Self-red-team (discipline 1 applied to the instrument itself):**

| Gaming vector | Mitigation in the shipped design |
|---|---|
| cherry-picked field comparators (compare only where we look good) | field rows are keyed to the SAME capability list as our ratchet surfaces; a capability without a field number renders UNKNOWN — visible, not omitted |
| stale field numbers presented as current | every field row carries its receipt URL; refresh cadence is the ingest lane's closure check (§1a code-world row); staleness is auditable against the URL |
| incommensurable comparison laundering (internal gym score next to a benchmark number as if same scale) | explicit `commensurable` boolean per row; Δ only computes when true; the one commensurable row today is honestly UNKNOWN on our side |
| hand-editing the committed page to look better | page must re-render byte-for-byte from the sealed receipt; `--check` fails on any edit |
| drift suppression (never running reality-graded envs so chamber-drift can't alert) | drift slot renders UNVALUED with its `requires` condition visible; a permanently UNVALUED drift row on a page with rising gym numbers is itself the alert the operator reads |

---

## 4. (d) The 10x Baseline Scoreboard — absorbed + verified on this host

The scoreboard is owned by `scripts/governance/inward_ascent_baseline.py`
(sibling, on main) and its committed digest-stamped receipt. Verified this
session on this host:

- The script RUNS and emits a digest-stamped receipt (fresh run this
  session: `measured=2 unknown=7`, checker-compatible seal).
- The COMMITTED receipt's `--check` reports CONTENT MISMATCH here — fully
  explained and expected: `owner` fields embed absolute home paths
  (`/home/ubuntu` on the producing host vs `/root` here), devin-box had an
  empty-but-present `runtime.db` where this host has none, and 6 commits
  landed after its pinned snapshot sha. The tamper seal (`digest`) — the
  thing governance criteria verify — is intact. **Finding, not a defect:**
  `content_digest` is a same-host replay identity, not a cross-host one;
  the receipt's own text says so. Improvement queued for Phase 1 (not done
  now — Phase 0 ships no build code): normalize `owner` paths to
  `~`-relative so cross-host content replay becomes possible.
- The one seal-required surface the sibling's scoreboard lacks
  (**distilled-seat cost-per-iteration**) is now carried as a Frontier
  Ledger row (§3) rather than by editing the sibling's committed instrument
  — absorb-and-extend, no rewrite.
- Baseline values stand as committed (git substrate frozen at the receipt's
  pinned sha; 2/9 measured, 7/9 UNKNOWN — "10x" on a surface becomes
  claimable only after its first non-UNKNOWN number exists).

---

## 5. (e) The door — exit machinery designed before entry

**5a. The scoreboard IS the trust gate.** The ledger's door panel renders
C1–C5 from `scripts/governance/trust_gate_status.py` (the §8 owner) on every
refresh — the chamber phase ends when that gate opens on measured numbers,
never on gym scores directly. Verified this session: door CLOSED (C1 0.725
AMBER, C2 0.05 RED, C3 0.30 RED, C4 0.31 RED, C5 0.20 RED).

**5b. The 30-day review page.** The review IS `FRONTIER_LEDGER.md` — one
page, refreshed before each review: door panel, capability deltas, drift
status, honesty line. Next-review date renders `PENDING_OPERATOR` until
decision-queue item 6 sets it; the cadence (30 days) is already on the page.

**5c. Chamber-drift metric (discipline 11).** Designed and rendered as a
first-class ledger slot: gym-score trend vs time-lagged reality-graded trend
(G2/G10-class receipts). Status UNVALUED until ≥2 gym receipts on one
environment and ≥1 reality-graded receipt share a window; alert rule (gym ↑
while reality-graded flat/falling over 14 days ⇒ CHAMBER DRIFT alert on the
page) is printed on the page itself so degradation of the door is visible on
the same surface the operator already reads.

**5d. The daily delta receipt (discipline 12) — design, Phase-1 build.** One
receipt per day proving the system behaves measurably differently today
*because of* yesterday's ingest and gym outcomes. Schema
(`dharma_swarm.chamber_daily_delta.v1`, digest-stamped, chainable via
`prev_digest` per the existing `expect_chain` checker support — verified this
session in `check_track_status.py::check_receipt_valid`):
`{date, yesterday: {bronze_receipts_landed, bronze_consumed, gym_runs:
[{env, taskpack_sha, score}]}, today_delta: {behavior_changed: [{surface,
before, after, caused_by_receipt}], ledger_rows_moved}, digest, prev_digest}`.
Owner surface: `reports/governance/chamber/daily_delta/` (chained JSONL).
Closure check: a `receipt_valid` criterion with `expect_chain: true` +
freshness TTL — a missing or delta-empty day is a visible flatline, not a
silent skip. This is the heartbeat that converts the self-fed harness loops
into loops fed by imported reality — the completion of loop-closure, not a
detour.

**5e. Overstay warning.** The chamber differs from the ARJUNA anti-pattern in
exactly three checkable ways: a scoreboard (§4), time-lagged reality grading
(G2 now, env 10 later), and a door (this section). All three render on the
one page; if any degrades, the page itself is the alert.

---

## 6. The 12 disciplines — where each is welded (compliance map)

| # | Discipline | Welded at |
|---|---|---|
| 1 | scorer ungameability, adversarially proven | absorbed per-env gaming tables (Inward-Ascent §(b)); ledger self-red-team §3; standing rule: adversary agent per env before first evolution run |
| 2 | held-outs + rotation everywhere | absorbed per-env specs; "an environment without held-outs is a slower mirror — rejected by construction" |
| 3 | C2 first | §2d sequencing; ledger reads C2, never computes it |
| 4 | demand-driven ingest | §1a consumer-binding table + hoarding checks |
| 5 | immune system | §1b; `bronze.py` policy verified in code |
| 6 | One Wire + evolution shadow + BR-003 | scope firewall (header); track non-goals §7 |
| 7 | diversity preservation | env decorrelation rationale absorbed; MAP-Elites via `archive.py` (D6a consolidation already on main); RSI-lab decorrelation §2d |
| 8 | expect_digest on everything new | ledger receipt verified `expect_digest=True` this session; track criteria §7 use `receipt_valid` + digests; daily-delta uses `expect_chain` |
| 9 | compute-ROI ledger | §2b rule + ledger row |
| 10 | oracle rule | G2 spec (absorbed): resolver consumes only fetcher-organ bronze rows, corroboration k≥2; self-authored resolution = incident |
| 11 | chamber-drift metric | §5c, rendered slot + alert rule |
| 12 | daily delta receipt | §5d design + closure check |

---

## 7. Draft ACTIVE_TRACK.yaml entry (NOT applied — ratification artifact)

Supersedes (absorbs) the sibling's draft `inward-ascent-2026-07` entry, which
was never applied — ONE chamber track, not two. Applied only after operator
ratification, then `python3 scripts/governance/render_active_track_includes.py`.
Serves `research-depth` (the uncovered spine objective; the gym is the
research instrument — same justification the sibling gave, now under the
doctrine's name).

```yaml
  - id: hyperbolic-time-chamber-2026-07
    name: Hyperbolic Time Chamber — afferent ingest, gym battery, Frontier Ledger
    status: ACTIVE
    opened_at: "2026-07-07"
    verified_at: "2026-07-07"
    ttl_days: 21
    owner: "@AmitabhainArunachala"
    serves: research-depth
    complements:
      - organism-rewire-2026-07
      - orchestration-arena-v1-2026-06
      - loop-closure-2026-06
    owned_surfaces:
      - docs/vision_maps/MASTER_2026-07-07_hyperbolic_time_chamber.md
      - docs/plans/HYPERBOLIC_CHAMBER_PHASE0_DOSSIER_2026-07-07.md
      - docs/plans/INWARD_ASCENT_PHASE0_DOSSIER_2026-07-07.md
      - scripts/governance/inward_ascent_baseline.py
      - scripts/governance/frontier_ledger.py
      - reports/governance/inward_ascent/**
      - reports/governance/chamber/**
    moves_vital_signs:
      - eval_coverage
      - quality_gates
    target_closure_kind: CLOSED_NOT_PROD
    claim_boundary: >-
      Phase 0 proves only the dossier + two replayable instruments (baseline
      scoreboard, Frontier Ledger). Gym results are internal-gym numbers,
      never benchmark or capability claims; C2 stays owned by the RSI/arena
      lab. Archive fitness remains behind the One Wire external quorum.
    description: |
      Operator-ratified chamber doctrine (vision map 2026-07-07): seal the
      efferent edge, open the afferent edge wide, evolve at machine speed
      against imported and time-lagged reality (class-2 signal only) until
      the trust gate opens on measured numbers. Phase 0 = dossier +
      instruments; Phase 1+ (post-ratification) = zeitgeist ingest live,
      then ONE gym environment end-to-end with its autoresearch loop and
      daily delta receipt. All 12 disciplines welded; substrate ruling
      (language-agnostic env protocol, Python composition root, Rust/C++
      earned per component) enforced.
    completion_criteria:
      - id: chamber_doctrine_exists
        kind: file_exists
        file: docs/vision_maps/MASTER_2026-07-07_hyperbolic_time_chamber.md
      - id: phase0_dossier_exists
        kind: file_exists
        file: docs/plans/HYPERBOLIC_CHAMBER_PHASE0_DOSSIER_2026-07-07.md
      - id: phase0_firewall_stated
        kind: file_contains
        file: docs/plans/HYPERBOLIC_CHAMBER_PHASE0_DOSSIER_2026-07-07.md
        pattern: "archive fitness for self-modification still requires the One Wire external quorum"
      - id: baseline_receipt_valid
        kind: receipt_valid
        file: reports/governance/inward_ascent/baseline_receipt.json
        expect_digest: true
        requires_keys:
          - schema_version
          - surfaces
          - summary
          - content_digest
      - id: frontier_ledger_receipt_valid
        kind: receipt_valid
        file: reports/governance/chamber/frontier_ledger_receipt.json
        expect_digest: true
        fresh_ttl_days: 30
        requires_keys:
          - schema
          - rows
          - door
          - chamber_drift
          - summary
          - inputs
      - id: frontier_ledger_replays
        kind: command_passes
        command: ["python3", "scripts/governance/frontier_ledger.py", "--check"]
    non_goals:
      - No efferent/world-facing actions of any kind (posts, outreach, trades, publishing, PR/issue submission to external repos).
      - Never weaken a gate, ratchet, or the One Wire quorum; gym gradients never touch archive fitness; DHARMA_EVOLUTION_SHADOW and BR-003 sequencing unchanged.
      - Do not touch RSI/arena surfaces (dharma_swarm/coordination/**, council/**, reports/governance/arena/**) or duplicate C2 measurement.
      - No new truth stores; Bronze -> Chetana -> MemoryKernel/ontology is the only landing path; ingested content is data, never instructions.
      - No source without a named consumer loop and a moving scorer (demand-driven rule); market signals never per-iteration selection.
      - No trained weights; selection stays MAP-Elites (archive.py); no environment monoculture.
      - Python remains the composition root; no gate/spine/receipt logic reimplemented in another language; Rust/C++ per-component only with measured justification.
      - No credentials committed; feed keys and hosts are operator-provisioned.
      - Files <500 lines; sibling track surfaces untouched except via their own next-items.
```

Note: `fresh_ttl_days: 30` on the ledger criterion is deliberate — it forces
a refresh at least every review cycle, making a stale review page a failing
criterion rather than a feeling.

---

## 8. Operator decision queue (nothing else blocks on these)

1. **Ratify** the Phase-0 dossier (this file; the seal's hard gate). The
   sibling's dossier is absorbed — one ratification covers both.
2. **Environment picks** for the first gym wave. Recommendation on the table:
   G1 + G2 + G3 now, G4 when its snapshot ships (sibling's pick, consistent
   with doctrine §8's recommendation minus the deferred gate gym).
3. **Hosts + keys:** which ingest feeds run where (Mac cron vs VPS daemon);
   BR-004 cron split-brain resolution rides the organism-rewire D1/VPS item.
4. **G4 substrate:** ship a sanitized `runtime.db` snapshot (or grant
   daemon-host execution); also resolves the ~2,191 (loop-closure track) vs
   ~8.8k (sibling's host) delegation_runs discrepancy — both numbers are
   claims about a DB this session cannot see.
5. **Compute budget** for env 15 (public benchmarks) and GPU for any
   distillation (env 12).
6. **First 30-day door review date** → fills `next_review` on the ledger.
7. **RSI-lab boundary confirmation:** shared receipt format + MAP-Elites
   descriptor conventions with the Mac/maharaja program (§2d states the
   contract; the lab side should countersign).
8. **Apply the track entry** (§7) to ACTIVE_TRACK.yaml on ratification (or
   instruct the next session to).

**Phase 1 (build) starts only after item 1** — zeitgeist ingest live first
(cheapest, verified live-capable, zero credentials), then ONE gym environment
end-to-end with its autoresearch loop and daily delta receipt. One
environment fully closed beats four half-built.

---

*Read order for the ratifier: doctrine file §0–§5 (the why and the shape) →
this dossier §0 + §3 + §5 (what is new) → `FRONTIER_LEDGER.md` (the page you
will read every 30 days) → Inward-Ascent dossier §(b) (the gym specs you are
ratifying).*
