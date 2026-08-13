# THE METABOLIZATION — 30-Day Consolidation Charter (2026-08-09)

**Role:** plan/charter, operator-ratifiable. Drafted from the operator conversation of
2026-08-09 following the two-day operator debrief
(`reports/operator_debrief_2026-08-09/OPERATOR_DEBRIEF.md`,
`reports/operator_debrief_2026-08-09/day2/DAY2_ADDENDUM.md`).
**Authority:** subordinate to `docs/governance/SOVEREIGN_MANIFEST.md` §Telos Hierarchy and
`docs/vision_maps/NORTH_STAR.md`. This file owns no runtime state; portfolio changes in §6
are PROPOSED, not executed — `docs/governance/ACTIVE_TRACK.yaml` remains the owner of
declared intent until the operator ratifies.
**Rule:** if this file disagrees with a receipt or the code, trust the receipt/code.

---

## 1. Declaration and authority

For 30 days (2026-08-09 → 2026-09-08) the organism builds **no new wings**. Every session
serves one program: metabolize what exists into one honest, running body. This is not a
retreat from the vision; it is the vision's own mandate applied to ourselves:

- **The ONE LAW:** "no cell spawns, grows, or claims status except by closing a strange
  loop on a real, gated, verifiable, diversity-preserving outcome"
  (`docs/vision_maps/NORTH_STAR.md:57-59`).
- **The needle:** "only the self-evolution that compounds into capability counts …
  narration outrunning build … is still the anti-pattern"
  (`foundations/THE_ORGANISM.md:16`).
- **The measured gap:** across two operator days, **1 of 12** delegated tasks round-tripped
  through the swarm board (day 1: 1/4, `OPERATOR_DEBRIEF.md:135-136`; day 2: 0/8,
  `day2/DAY2_ADDENDUM.md:21-23`). The one success was excellent (5/5, "would ship",
  `OPERATOR_DEBRIEF.md:130`). The body works when it works; it mostly does not work.

**Done-definition (all three, mechanically checkable on day 30):**

1. **Task round-trip ≥95% honest completion.** A task submitted via
   `POST /api/commands/task` either completes with real output or fails with a truthful
   failure state — never `completed/success=true` on a permission stall
   (`OPERATOR_DEBRIEF.md:60-66`, F5) and never discarded by a state race
   (`day2/DAY2_ADDENDUM.md:27-31`, F15).
2. **Canonical knowledge metabolized to git as text.** Per the canon-metabolism rule:
   "nothing is canonical until it is metabolized to main"
   (`docs/vision_maps/NORTH_STAR.md:175-187`, §9). §4 below gives it a home.
3. **Every agent hydrated with identity on first token.** NORTH_STAR trust-gate criterion 5
   ("memory-kernel first-token orientation", `docs/vision_maps/NORTH_STAR.md:164-168`);
   THE_ORGANISM names self-onboarding as an organ — "fresh agent coherent on first token —
   the cure for 'every new instance is confused'" (`foundations/THE_ORGANISM.md:49`).
   Today's receipt of failure: after 16+ agent runs, the mandated externalization
   directory `~/.dharma/shared/` was empty (`day2/DAY2_ADDENDUM.md:42-44`, F20).

**Friction ledger baseline:** F1-F14 (`OPERATOR_DEBRIEF.md:37-102`) and F15-F20
(`day2/DAY2_ADDENDUM.md:25-44`). The Metabolization is scored against this ledger; a
friction item is closed only by a receipt (test, command output), never by prose.

---

## 2. Workstream A — Spine honesty

**Packet:** `metabolization-WP-SPINE1-honest-lifecycle` (this PR's companion work).
Required because these paths match `HOT_PATH_PATTERNS`
(`scripts/runtime/pr_merge_control.py:95-110` lists `dharma_swarm/orchestrator.py`,
`dharma_swarm/swarm.py`). Surface note: `orchestrator.py`/`swarm.py` are owned by
`dharmagraph-engine-2026-07` (`docs/governance/ACTIVE_TRACK.yaml:940`) and `swarm.py` also
by `organism-rewire-2026-07` (`ACTIVE_TRACK.yaml:788`); §6 proposes reassigning lifecycle
surfaces to the Metabolization program — until ratified, WS-A executes as organism-rewire
work (the track already owns `dharma_swarm/organism.py` and runtime wiring).

Items, each pinned to a measured failure:

1. **Late-completion acceptance.** The board rejected finished work with
   "Invalid transition: pending -> completed" after the timeout+reconciler requeued the
   task — real Claude Code output observed live, then thrown away
   (`day2/DAY2_ADDENDUM.md:27-31`, F15; reconciler orphan sweep F16 at :32-34). Fix: a
   completion arriving for a requeued task is accepted (idempotent, receipt kept), never
   discarded.
2. **Operator-first dispatch.** Dispatch picked self-spawned "latent insight" tasks over
   four submitted operator tasks (`OPERATOR_DEBRIEF.md:70-74`, F6). Fix: user-submitted
   tasks strictly outrank self-spawned work (debrief fix #5, `OPERATOR_DEBRIEF.md:177-178`).
3. **Timeout 300→1800.** Default is `task_timeout_seconds: 300.0`
   (`dharma_swarm/config.py:28-31`; enforcement string at
   `dharma_swarm/orchestrator.py:2948`). The one successful task took ~4 min; every day-2
   task exceeded the ceiling (`day2/DAY2_ADDENDUM.md:23`). Raise default to 1800 s and
   surface it at submit time (debrief fix #6).
4. **Provider deadpool.** The cheap-first chain
   (`dharma_swarm/runtime_provider.py:122-140`) walked a dead Ollama 14 times at 3-11 ms
   per "call" while tasks sat `running` (`OPERATOR_DEBRIEF.md:54-59`, F4). Fix: instant
   reachability probe at dispatch; providers failing it enter a deadpool and are skipped
   (debrief fix #2).
5. **Evolve-daemon brain fix.** The daemon hardwires OpenRouter —
   `provider = swarm._router.get_provider(ProviderType.OPENROUTER)`
   (`dharma_swarm/terminal_commands/evolution.py:134-135`) — so 50 shadow cycles produced
   ~99 failed calls and 0 proposals while a working claude_code lane sat in the same
   process (`day2/DAY2_ADDENDUM.md:37-40`, F18/F19). Fix: route through the provider
   chain; also make the source scan checkout-relative, not `$HOME`-relative (F18).
6. **Boot-seed fixes.** Every boot logs real failures: `ConceptGraph` import error from
   `graph_nexus` and stigmergy `string_too_long` seeding failure
   (`OPERATOR_DEBRIEF.md:85-87`, F10). Fix both; a clean boot logs zero component errors.
7. **Onboard fullness counts.** `make onboard` (Makefile:771-772 →
   `scripts/governance/agent_onboard.py`) prints READY while zero execution steps below it
   can run (`OPERATOR_DEBRIEF.md:30-36`). Add alive/dead organ counts (the debrief §3
   dead-list: DarwinEngine, kernel, HUM, NATS, Go ingestors —
   `OPERATOR_DEBRIEF.md:117-124`) so READY is scoped honestly.

Also in scope, same packet family: honest failure states on the board (F5's
permission-stall reported as success), permission profile for the ClaudeCodeProvider
subprocess lane (debrief fixes #3-4, `OPERATOR_DEBRIEF.md:171-176`), and metering the
claude_code lane so "what did today cost" has an answer (F7, `OPERATOR_DEBRIEF.md:75-78`).

---

## 3. Workstream B — Memory metabolization

**The three-class state doctrine** (proposed as standing rule):

| Class | Where it lives | Rule |
|---|---|---|
| Runtime receipts | `~/.dharma/` only | Already a hard rule: "Runtime receipts never enter git" (`CLAUDE.md` §Hard rules); owners listed in `CLAUDE.md` §State directory |
| Canonical knowledge | **TEXT in git**, under `docs/wiki/` (new directory, permitted — sourced docs belong in `docs/`, per the no-new-root-files rule) | Nothing is canon until merged to main (`NORTH_STAR.md:175-187`) |
| Derived indexes | rebuilt on demand, never committed | e.g. graph projections, embeddings; the module that builds them is the truth |

Items:

1. **Chetana promote gate ends in a commit.** Today `chetana promote` gates and lands an
   atom in a PENDING root under `~/.dharma/knowledge/`
   (`dharma_swarm/chetana/cli.py:72-86`, staging path named at `cli.py:5`) — class-1
   custody for class-2 content. The Metabolization closes the loop: a promoted atom's
   terminal state is a text file under `docs/wiki/` in a PR, so the ingest→stage→gate→
   promote pattern NORTH_STAR §9 names as "the metabolizer" actually reaches main.
   (NORTH_STAR.md:184-187 still describes chetana as stranded on an extraction branch;
   `dharma_swarm/chetana/` is on main in this checkout — the note is stale, which is
   itself the split-brain failure §9 warns about.)
2. **Litestream / always-on-host replication.** The stranded vehicle is **PR #1082**
   ("Backup Triad Runbook", draft since 2026-07-21, `ci-stranded-rebase-skipped` label —
   the label the backlog review calls "silent graveyard duty",
   `reports/operator_debrief_2026-08-09/pr_backlog_review.md:44-46`). Its verified facts:
   the VPS litestream replica writes to the SAME disk as the data, and the Mac's 479 MB
   `runtime.db` has no replication (PR #1082 body). Revive the runbook, land it, and
   execute leg 1 (off-host bucket) once the operator provisions credentials (§8). The
   compose service already exists: `docker-compose.yml:139-146`
   (`litestream/litestream:0.3.13`, config at `scripts/ops/litestream.yml`, procedure in
   `docs/ops/RUNBOOK.md` §3e per `docker-compose.yml:138`).

---

## 4. Workstream C — One body

Per the ratified doctrine: "VPS shift is NOW-class, not later: compose `swarm` service +
NATS + litestream state replication on an always-on host; Mac demotes to dev seat/mirror
… Operator provisions host + secrets" (`docs/plans/ORGANISM_REWIRE_DOCTRINE_2026-07-02.md:20`).

**What exists:** `docker-compose.yml` ships `web` (:59), `swarm` (:78, read-only source
mount at :87), `cron` (:120), `litestream` (:139). **Honest gap:** no NATS service is in
the compose file (grep receipt: zero `nats` matches outside the litestream comment block);
onboard reports "127.0.0.1:4222: not listening" on a fresh checkout
(`OPERATOR_DEBRIEF.md:121-122`). WS-C adds the NATS service or documents the external
substrate host — one or the other, in the compose file, not in prose.

**Runbook summary (target state):** one always-on host runs `docker compose up` for
web+swarm+cron+nats+litestream; the swarm service runs the persistent tick loop the
operator had to fake with manual `POST /api/commands/dispatch` calls
(`OPERATOR_DEBRIEF.md:25-36`; the real daemon is `dgc orchestrate-live`,
`dharma_swarm/terminal_commands/lifecycle.py:83`).

**Operator provisioning checklist** (only John can do these — repeated in §8):
host + SSH; object-store bucket + the two `LITESTREAM_*` credential names (PR #1082);
provider API keys for at least one always-reachable brain (F4's root cause is a keyless,
Ollama-less machine); `DHARMA_API_ALLOW_LOCAL_NOAUTH` decision for the loopback lane
(`api/main.py:396`).

**Phone-reachable board.** The debrief's harness verdict: "the spine to invest in is
board-in/board-out, because that's the only loop that closed today"
(`OPERATOR_DEBRIEF.md:146-161`). WS-C exposes `POST /api/commands/task` +
`GET /api/commands/tasks` (with honest failure states from WS-A) through the deployed
`web` service so the operator can submit and watch from a phone. The TUI and dashboard
remain skins; the board is the organ.

---

## 5. Workstream D — One organ, one number, one paper

The three external-contact deliverables. Everything else waits.

1. **One organ: SIS to first external countersignature.** The SIS corpus
   (`docs/research/verified_nature_house/`, 14 documents) carries its own fence: "No
   outward motion before the gate. No public site, no outreach to external
   [parties] … Internal artifacts never mint value; only externally-countersigned"
   artifacts do (`docs/research/verified_nature_house/12_SIS_FOUNDING_CHARTER.md:132-137`;
   "$0 lifetime external revenue" at `12_SIS_FOUNDING_CHARTER.md:5`). The day-2 plan is
   already grounded in the corpus's own build order
   (`day2/sis_development_plan.md`). Deliverable: ONE externally countersigned artifact —
   the corpus's own definition of the first real help
   (`12_SIS_FOUNDING_CHARTER.md:161`) — by day 30. Darshan serves as SIS's voice (§6).
2. **One number: weekly Forge SWE-bench ritual.** The runbook exists and is complete:
   `docs/RUNPOD_SWEBENCH_RUNBOOK.md` (CPU pod spec :9-15, keys as "the only real gate
   besides the box" :22-27). Blocked on `RUNPOD_API_KEY` (absent, per
   `day2/DAY2_ADDENDUM.md:19`). The bar is named in canon: "the swarm scores higher than
   single models on coding benchmarks … The published bar: Sakana/UBC's Darwin Gödel
   Machine self-improved 20%→50% on SWE-bench" (`docs/vision_maps/NORTH_STAR.md:155-160`;
   DGM figures at :157-160). Ritual: one scored run per week, numbers published to
   `reports/` — a real number, even a bad one, replaces the current state (never
   measured; `dgc evolve trend` → "No fitness data yet", `OPERATOR_DEBRIEF.md:118`).
3. **One paper: R_V paper completion, dated.** The lab lives on the operator's machine —
   `~/mech-interp-latent-lab-phase1/` is mapped as "R_V metric research — ACTIVE, 70-80%
   paper-ready" with paper materials and LaTeX enumerated
   (`dharma_swarm/ecosystem_map.py:27-31`), which is why `dgc health` reports 77/79
   MISSING everywhere else (`OPERATOR_DEBRIEF.md:79-81`, F8). The R_V program is
   NORTH_STAR §2's falsifiable-awareness claim (`NORTH_STAR.md:22-28`) and the doctrine's
   research node 6 (`ORGANISM_REWIRE_DOCTRINE_2026-07-02.md:40`). Deliverable: submitted
   draft by **2026-09-08**, with the lab repo granted to a session (§8) so the swarm can
   carry figures/reproduction, not just the operator.

---

## 6. Portfolio surgery — PROPOSED final states (ratification-ready, NOT executed)

Current declared intent: 10 ACTIVE tracks (`docs/governance/ACTIVE_TRACK.yaml`; line refs
below are each track's `- id:` line). **Coordination note:** open PRs **#1213/#1214**
already carry the helm and arena closures ("both say CLOSED_NOT_PROD; if you agree the
tracks are done, these should merge promptly",
`reports/operator_debrief_2026-08-09/pr_backlog_review.md:25`). Per the coordination rule
(`CLAUDE.md` §Hard rules, BR-id PRs: check open PRs citing the same id and coordinate),
this charter does NOT re-execute those closures — it endorses merging the existing PRs.

| Track (ACTIVE_TRACK.yaml line) | Proposed state | Rationale |
|---|---|---|
| `loop-closure-2026-06` (:135) | **KEEP-ACTIVE**, consolidated under Metabolization | Loop honesty IS the program |
| `orchestration-arena-v1-2026-06` (:458) | **CLOSE via PR #1214** (already open) | Endorse merge; no new PR |
| `merge-master-mike-d4-2026-06` (:617) | **KEEP as infrastructure** | The gate (`scripts/runtime/pr_merge_control.py`) is load-bearing for every other row |
| `organism-rewire-2026-07` (:788) | **KEEP-ACTIVE**, consolidated; WS-A/WS-C execute here | Owns the runtime surfaces WS-A repairs |
| `dharmagraph-engine-2026-07` (:940) | **FREEZE at invoked scope**; parity gauntlet becomes a fence, not a roadmap | Verdict: "58.00/100 … NOT_FINISHED. Closeout blocked: true" (`reports/governance/dharmagraph_parity/PARITY_MATRIX.md:1-3`). What the organism invokes today is kept green; the remaining ~29 gap cards stop generating work |
| `helm-worldclass-terminal-2026-06` (:1319) | **CLOSE via PR #1213** (already open) | Endorse merge; no new PR |
| `sovereign-safety-tcb-2026-07` (:1390) | **KEEP-ACTIVE**, consolidated | Fail-closed gates are the ≥95% honesty mechanism |
| `hyperbolic-time-chamber-2026-07` (:1590) | **DORMANT** | Eulogy below |
| `repository-titanium-hardening-2026-07` (:1758) | **KEEP-ACTIVE**, consolidated | CI truth (`docs/governance/CI_TRUTH_CONTRACT.json`) is how day-30 claims get verified |
| `darshan-publication-2026-07` (:1968) | **KEEP, re-aimed: serves the SIS voice** | Darshan's desks (`docs/plans/DARSHAN_CHARTER_2026-07-12.md`) narrate the countersignature hunt of §5.1 — one voice, one organ, per the ONE LAW |

**Eulogies (salvage with every kill):**

- **Helm** (`terminal/**`). Helm proved the operator deserves a world-class surface, and
  the debrief proved the surface must be the board, not the terminal: the TUI "booted but
  bridge-dependent and not the thing I reached for" (`OPERATOR_DEBRIEF.md:146-148`).
  Salvage: the Ink rendering layer stays in-tree as the future skin for the board
  (`OPERATOR_DEBRIEF.md:158-159`: "the TUI is the right skin for this if its bridge
  lands"). PR #1213 carries the closure; nothing is deleted.
- **Arena** (`dharma_swarm/coordination/**`, `dharma_swarm/council/**`). The arena built
  the frozen-eval discipline the doctrine now mandates for every autoresearch node
  (`ORGANISM_REWIRE_DOCTRINE_2026-07-02.md:36-40` — "arena/orchestration genome — already
  built, node one"). Salvage: its hermetic-fitness pattern and truth report
  (`scripts/governance/arena_truth_report.py`) become the template for the weekly Forge
  ritual of §5.2. PR #1214 carries the closure.
- **Hyperbolic Time Chamber.** The chamber asked the right question — can the organism
  train against ingested history — before the organism could reliably execute a single
  300-second task (`day2/DAY2_ADDENDUM.md:21-23`). Salvage: the gym battery and Frontier
  Ledger designs (`docs/plans/HYPERBOLIC_CHAMBER_ELEVATION_SPEC_2026-07-07.md`,
  `scripts/governance/frontier_ledger.py`, tests under `tests/test_chamber_*.py`) stay
  intact and dormant; the chamber reopens when WS-A's round-trip number holds ≥95% for a
  week — the chamber needs a body that metabolizes before it can exercise one.
- **DharmaGraph (freeze, not death).** 58/100 against LangGraph is an honest number from
  an uncharmable gauntlet — exactly the kind of instrument this repo exists to build.
  Salvage: the gauntlet (`scripts/governance/dharmagraph_parity_gauntlet.py`) survives as
  a regression fence over the invoked scope; the rubric stops being a to-do list.

---

## 7. Trust-gate scoreboard

The five criteria the operator must SEE before pushing outside
(`docs/vision_maps/NORTH_STAR.md:144-168`, §8), scored honestly today:

| # | Criterion (NORTH_STAR line) | Today (2026-08-09, receipt) | 30-day target |
|---|---|---|---|
| 1 | Clean repo, high-quality code, audited flow (:150-154) | **FAIL** — fresh checkout cannot `pip install -e .` (F1), API needs manual dep install (F2); 33 open PRs, 12 drafts, 8 stranded (`pr_backlog_review.md:4,44`) | Bootstrap green on a fresh machine; open-PR count <15 with zero stranded |
| 2 | Swarm beats single models on coding benchmarks (:155-160) | **UNMEASURED** — no Forge run has ever produced a number (`dgc evolve trend` → "No fitness data yet", `OPERATOR_DEBRIEF.md:118`) | ≥4 weekly scored SWE-bench runs published; swarm-vs-best-single delta stated, whatever its sign |
| 3 | Full venture-cell build, end to end, competitive (:161-162) | **FAIL** — SIS at $0 lifetime external revenue (`12_SIS_FOUNDING_CHARTER.md:5`); Darshan Issue One is an outline (`darshan_issue_one_outline.md`) | One externally countersigned SIS artifact (§5.1) |
| 4 | All seeded parts wired and functioning (:163) | **FAIL** — dead list on a fresh checkout: DarwinEngine, dharma kernel, HUM, NATS, Go ingestors, ConceptGraph, cost ledger (`OPERATOR_DEBRIEF.md:117-124`) | Onboard fullness counts (§2.7) show ≥80% of the dead list alive or explicitly DORMANT-by-ratification |
| 5 | Agents that know operator/system/telos on first token (:164-168) | **FAIL** — `~/.dharma/shared/` empty after 16+ runs (F20); no first-token hydration exists | Every dispatched agent receives identity hydration; verified by a WS-A lifecycle test |

Task round-trip (the done-definition's own number, feeding rows 1 and 4): **1/12 ≈ 8%**
today → **≥95%** at day 30.

---

## 8. Operator decision list — what only John can do

1. **Merge #1213 / #1214** (helm, arena closures) — they "gate portfolio WIP accounting"
   (`pr_backlog_review.md:25`).
2. **Provision the VPS** (host + SSH) and its **secrets**: the two `LITESTREAM_*`
   credential names + bucket (PR #1082's checklist), provider API keys for one
   always-reachable brain, loopback-auth decision (`api/main.py:396`). Per doctrine,
   "Operator provisions host + secrets" (`ORGANISM_REWIRE_DOCTRINE_2026-07-02.md:20`).
3. **Name the SAB repo/host** — it is not in dharma_swarm and only John knows where it is
   (`day2/DAY2_ADDENDUM.md:51`, blocking item 6).
4. **Grant `RUNPOD_API_KEY` + the mech-interp lab repo** to a session
   (`day2/DAY2_ADDENDUM.md:52-53`, blocking item 8) — unblocks §5.2 and §5.3.
5. **Ratify §6 portfolio surgery** — until ratified, `docs/governance/ACTIVE_TRACK.yaml`
   stands unchanged and this charter binds nothing.

---

*Drafted 2026-08-09. Every claim above carries a `file:line` or a named receipt; anything
found uncited is a defect in this document — file it against the charter, not against the
program.*
