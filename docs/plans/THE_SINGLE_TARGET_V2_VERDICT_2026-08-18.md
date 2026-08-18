# THE SINGLE TARGET v2 — verdict (2026-08-18)

**Document role:** `report` (dated research output). No runtime, merge, or
governance authority. Subordinate to
`docs/governance/CANONICAL_DOC_STACK.md`. This is the deliverable demanded
by the v2 tournament prompt on PR #1383 (not in this checkout). The
repository at HEAD is the fact base; the operator dossier in that prompt §3
is a self-report under test.
**Status:** UNRATIFIED recommendation. Does not admit a work packet.
**Checkout:** `main @ 8cc04b71987b`. **Run date:** 2026-08-18.
**Elevated thesis entered as S6:**
`docs/plans/THE_WITNESS_ENGINE_ELEVATED_2026-08-18.md`.

Commands actually run (orientation, §4.0): `make onboard` (READY, authority
none); `python3 scripts/repo_xray.py` (1081 Python modules, 982 test files —
cite the command, not prose memory); `python3 scripts/governance/check_track_status.py`;
`python3 scripts/governance/cybernetics_codex_audit.py --json`;
`python3 scripts/governance/trust_gate_status.py`
(wrote `reports/governance/trust_gate_status.json` this run);
`git log --oneline -20`;
`git show origin/generated/status:reports/governance/active_track_evidence.md`.
Pytest is **not installed** in this cloud checkout; several track criteria
are UNVERIFIED here for that reason, which is not evidence of regression.

---

## E1 — Load-bearing map

Full organ table and CUT/REPURPOSE calls:
`docs/plans/THE_WITNESS_ENGINE_ELEVATED_2026-08-18.md` §C.
Compressed census used for C1/C7 scoring:

| Organ | Status | Evidence |
|---|---|---|
| DarwinEngine + safety | HARNESS_PROVEN; live mutation fail-closed | `dharma_swarm/evolution_safety.py:5-13`; first-fire script is plumbing "do not light" (`scripts/first_fire_plumbing.py:1-8`); HEAD `#1379` |
| MAP-Elites `archive.py` | HARNESS_PROVEN; +fitness BLOCKED | `archive.py:52-78`; One Wire guard tests exist |
| Ginko ledger | HARNESS_PROVEN; filesystem JSONL, not a public git branch | `ginko_brier.py:11-31` |
| Forge SWE-bench | HARNESS_PROVEN; lift −0.10 | `trust_gate_status.json:22-32`; `forge_v1/harness.py` |
| Chamber gym | HARNESS_PROVEN | `dharma_swarm/chamber/gym_git_history.py` |
| Arena | HARNESS_PROVEN; inadmissible as capability | `trust_gate_status.json:26` |
| Go / world-radar | DORMANT | `tools/*_go/`, `dharma_swarm/world_radar/` |
| Memory kernel | HARNESS_PROVEN (front door) | `dharma_swarm/memory_kernel/__init__.py:1-6` |
| Stigmergy / catalytic / cascade | HARNESS_PROVEN | modules exist; not CLOSED_LIVE |
| StrangeLoop | constructed if Organism boots | `organism.py:164-170` — dossier "off-by-default flag" **not found** at this HEAD |
| DharmaGraph | not in production dispatch | `dharma_swarm/graph/types.py:5` |
| Spine | HARNESS_PROVEN | `dharma_swarm/spine/__init__.py` |
| GAIA | HARNESS_PROVEN code; cell ENVISIONED | `gaia_verification.py:1-8`; portfolio yaml:139-141 |
| TCB packages | HARNESS_PROVEN | `packages/telos-kernel/`, `packages/titanium-verify/` |
| Living-agent kernel | HARNESS_PROVEN, no provider dispatch | `living_agent_kernel.py:1-7` |
| Mission control | HARNESS_PROVEN | `dharma_swarm/mission_control*.py` |
| A2A receipts | HARNESS_PROVEN | `a2a/task_receipt.py:18-19` |
| Revenue / audit kit | HARNESS_PROVEN kit; $0 cash | `audit_kit.py`; `first_cash_receipt_status.md:3` |
| Capital lab | INCUBATING paper | portfolio yaml:108-112 |
| Darshan | ACTIVE_SEASON_0 | portfolio yaml:73-77 |
| Trust gate overall | **closed** (not open) | `trust_gate_status.json:6` `gate_open: false` |
| Portfolio YAML vs ACTIVE_TRACK | **drift** | yaml still names `goodworks-dgm` ACTIVE_BUILD_TRACK; `ACTIVE_TRACK.yaml` at HEAD has ten other tracks, no goodworks |

Disagreement with dossier §3.1 is in E3.

---

## E2 — Loop census

Source: `reports/loop_closure/cybernetics_codex/latest_audit.json`
(observed_at 2026-07-24; audit file **stale vs 21-day TTL** — the
cybernetics criterion `cybernetics_codex_latest_audit_valid` fails freshness
on generated/status). Standing claim in `CYBERNETIC_LOOP_MAP.md`:
CLOSED_LIVE 0/13; HARNESS_PROVEN 11; BLOCKED 2.

| # | Loop | Verdict | Waiting for |
|---|---|---|---|
| 1–11 | task, heartbeat, Darwin, memory, zeitgeist, witness, flywheel, recognition, conductors, context, replication | HARNESS_PROVEN not CLOSED_LIVE | each loop's live owner-surface criterion (see `latest_audit.json` `live_owner_surface_criterion`) |
| 12 | Self-Improvement | BLOCKED | One Wire N≥5, M≥3, explicit archive-fitness authority |
| 13 | Free Evolution Grind | BLOCKED | same |

**One Wire arithmetic at this checkout:**
`latest_audit.json:617-628` — guardian receipt **missing**, confirmed=0,
domains=0, eligible=false, fitness_authority_granted=false.
**One Wire arithmetic in the loop map (stale relative to this audit):**
N=3/5, M=1/3 (`CYBERNETIC_LOOP_MAP.md:59`), matching the 2026-07-01 guard
receipt (`2026-07-01_loop12_13_one_wire_archive_fitness_guard.json:9-16`)
and the 2026-07-05 revenue-wedge note (cycle-004, all receipts in
`external_code_contribution`).

Documented fill paths (RECEIPT(`first_cash_receipt_status.md`:20-28)):
domain 2 = first cash paid work; domain 3 = GAIA/ecological pilot intake
**or** externally-reviewed research artifact. Domain diversity, not raw
count, is the binding constraint.

---

## E3 — Drift list

| Claim | Dossier / vision | Repo at HEAD | Trust |
|---|---|---|---|
| First live self-modification fire "today" | §3.2 REPORTED | HEAD is first-fire **plumbing**, "do not light" (`scripts/first_fire_plumbing.py:1-8`; commit `8cc04b71`) | **Repo.** Fire itself not reached at this checkout. |
| Merge queue serving five real merges today | §3.2 | Not re-counted here; Merge Master code exists | REPORTED |
| Forecast ledger 26 model forecasts, public append-only branch | §3.1 | Ginko is `~/.dharma/ginko/predictions.jsonl`; public derived branch is `generated/status` (governance evidence, not a forecast ledger) | **Repo.** "Public forecast branch" not at HEAD. |
| Swarm lift −0.10 | §3.1 | Confirmed by trust-gate projection | Both agree |
| Revenue $0 | §3.1 | Confirmed | Both agree |
| One Wire N=3/5 M=1/3 | §3 / loop map | Live audit: guardian missing, N=0 M=0 | **This audit** for liveness; loop map for last known guardian-era state. Do not cite N=3 as currently sensed. |
| ~12,000 archive entries, zero external authority | §4 C4 | Not re-counted (`repo_xray` does not print this). Treat as REPORTED until `archive.py` JSONL is counted in `~/.dharma/` | REPORTED |
| Risk budget $1k/$100/$50/$500 | §3.4 | Not packaged as one canon doc | REPORTED operator ratification |
| Darwin proven live | §3.1 | Fail-closed; plumbing only | **Repo** |
| GoodWorks DGM is the coding seam | portfolio yaml:120-123; NORTH_STAR table | `ACTIVE_TRACK.yaml` has no goodworks track | **ACTIVE_TRACK.yaml** |
| IETF drafts don't provide behavioral trust | NORTH_STAR §10 | ATTP `draft-sharif-attp-01` defines five-dimension behavioural scoring | **Live IETF text** |
| StrangeLoop off-by-default flag | v2 prompt §4.2 hazard | `Organism.__init__` constructs it in a try/except (`organism.py:164-170`) | **Repo** |
| `$500–$1,500` vs `$5k–$25k` offer | v2 prompt notes v1 drift | Offer doc is $5k–$25k | **Offer doc** |
| VENTURE_CELL_PORTFOLIO `generated: 2026-05-30` | — | 80+ days stale vs HEAD | YAML is an index, not live build intent |

---

## E4 — Frontier brief

See elevated thesis §D for the eight-fact table. Tournament-facing
compression:

| Fact | Changes which C-score |
|---|---|
| Kalshi LLM agents −16% to −30.8% (`arXiv:2604.07355`) | **Kills S1 C6** at $1k bankroll; S1 C5 as "edge of AI trading" |
| ERC-8004 off-chain scoring hole | **Empowers S6/S2 C5/C6** (named buyer-shaped API) |
| ERC-8126 static 0–100 security score | Caps S6: do not claim "the" agent risk score; occupy promise-keeping |
| ATTP behavioural transport | Stale NORTH_STAR §10; S6 must *feed* ATTP, not ignore it |
| `arXiv:2608.09055` repeated-game inference IC | Narrows S6's "vacant slot" to world-behavior, not GPU-integrity |
| AIUC-1 quarterly adversarial tests | Empowers S2/S6 C6 (assurance buyers exist) |
| Sylvera $50k–$250k/year | **Kills biosphere-as-spearhead C6** for a solo 90-day dollar |
| DGM + Mendel papers both resolve | Empowers C4 language; does not unlock Loops 12/13 |

---

## P. Premise audit

The verbatim ask is right about *outwardness* and wrong about three
couplings. "Uses every component" is a sunk-cost trap: DharmaGraph is
explicitly not on the production dispatch path, and stuffing it into a
mission so C1 looks high would degrade the product. "One thing" is the
right *shape* if it means one spearhead with a sequenced second domain of
the same engine — a portfolio of equal missions is what the organism
already has, and it has $0. "RSI-like mechanism to make money" conflates
the selection signal with the income stream; the repo already forbade that
conflation (`ORGANISM_REWIRE_DOCTRINE` §4: P&L is never per-iteration
fitness). The 90-day dollar does **not** have to wait for live capital
(S1's trap) but it **does** collide with NORTH_STAR §8 if "pushing
outside" is read as a capability claim. A paid sealed-receipt sprint is
not a claim that the swarm beats single agents. Treating it as one would
make C6 impossible until C2 greens, which the trust-gate file says has
not happened. I answer as asked: one externally-pointed mission, not
evolution-as-mission, not Darshan.

---

## A. The mission, one sentence

**Sell adversarial verification of agent behavior — sealed receipts and a
published-misses calibration record that a buyer, an AIUC-1 auditor, or
an ERC-8004/ATTP rail can consume — and run that same witness on
ecological claims only after the first paid receipt exists.**

---

## B. The loop, mechanically

Money → (funding only) compute → more gym volume.
Signal → Brier + planted-failure outcomes → selection in MAP-Elites.
Selection → better probes/verifiers → better product → more money.

| Arrow | Artifact that proves it fired | Today | Must build |
|---|---|---|---|
| Client pays | RevenueSpine row + bank evidence; One Wire domain `paid_governance_engagement` | $0 (`first_cash_receipt_status.md:3`) | Packet 1 + operator outreach |
| Payment must not select | Doctrine + a code guard that archive fitness ignores invoice amount | Doctrine exists; product-specific guard does not | One test: fitness write with dollar field present still uses Brier only |
| Signal | Ginko JSONL miss/hit; gym episode receipt; A2A task_receipt verdict | Ginko + A2A + gym exist | Agent-promise taskpack (packet 3) |
| Selection | `archive.py` add_entry with One Wire authority | **Blocked** (N/M below quorum or guardian missing) | Ordinary operation must mint domain-diverse receipts (packets 1 and 4) before Loops 12/13 move |
| Capability | Next sprint uses a verifier lineage with better held-out Brier | Not yet a product loop | Packets 2–3 |
| More money | Second engagement or a monitoring subscription | None | Channel (operator) |

If One Wire never fills, C4's "verifiable RSI" stays metaphor: lineages
can still be compared on Ginko/gym numbers, but **archive fitness cannot
move** (`archive.py` OneWireFitnessAuthorityError). That does not kill
the *income* loop; it kills the claim that Loops 12/13 are live. The
mission is still scored on whether ordinary sales mint the quorum.

---

## C. The tournament

Scores 0–5. C1/C7 cite paths. C5/C6 cite dated externals. REPORTED-only
justifications flagged. Campaign X-Ray (28/100, HELD) is precedent for
any service shape.

| | C1 code | C2 uplift | C3 telos | C4 RSI | C5 edge | C6 income | C7 dots | **Sum** |
|---|---|---|---|---|---|---|---|---|
| **S6 Witness (winner)** | 4 | 4 | 5 | 4 | 4 | 3 | 4 | **28** |
| S2 Verified-agent-work (kit-as-sold-today) | 3 | 3 | 4 | 2 | 3 | 4 | 2 | **21** |
| S3 Evals lab | 3 | 4 | 4 | 3 | 4 | 2 | 3 | **23** |
| S7 Agent-Promise Benchmark (novel) | 3 | 5 | 4 | 4 | 5 | 1 | 3 | **25** |
| S5 Forecast desk | 3 | 2 | 3 | 2 | 2 | 1 | 4 | **17** |
| S4 Agent factory | 4 | 3 | 2 | 2 | 2 | 2 | 3 | **18** |
| S1 Capital Lab | 3 | 3 | 3 | 2 | 1 | 1 | 2 | **15** |

**Justifications (winner S6), one line each:**

- **C1 4** VERIFIED: serving path = audit_kit + spine receipts + telos gates
  + Ginko + A2A + archive + forge/gym. DharmaGraph/StrangeLoop not counted
  (not serving-path). Not 5: Darwin live-mutation and world-radar are not
  load-bearing in cycle 1.
- **C2 4** VERIFIED: gym win-rate and forge lift are named non-M metrics;
  signal rides archive + Ginko. Transfer is real only after packet 3.
- **C3 5** VERIFIED: ONE LAW is the product (external receipts); generator/
  evaluator split; published misses (Ginko SATYA). Jagat Kalyan is literal
  once biosphere is sequenced, not decorative.
- **C4 4** VERIFIED: Mendel/DGM loop specified in elevated §B; One Wire
  domains named; P&L not the selection signal. Not 5: Loops 12/13 remain
  BLOCKED until receipts exist — C4 is a *path*, not a live loop.
- **C5 4** EXTERNAL: ERC-8004 wants off-chain aggregators (2026-08-18);
  ATTP needs a TA feed; 8126/EigenAI occupy adjacent niches. Future-proof
  because cheaper models increase demand for independent verification.
  Not 5: well-funded AIUC-1 auditors can ship a "good enough" heuristic.
- **C6 3** VERIFIED offer $5k–$25k + ASSUMPTION conversion. Channel is the
  operator; X-Ray already failed this. Not 4 until one outreach is sent.
- **C7 4** VERIFIED: packet 4 + Go/world-radar (organism-rewire) + GAIA
  ENVISIONED cell + loomwork DESIGN_ONLY get a reason to exist. Packet 1
  does not wake them — sequencing does.

**Seeds, steelman then kill:**

- **S1 Capital Lab.** Best form: money loop *is* the world-grader; honesty
  stack (DSR/PBO) is the wedge vs agentic-fund mirage (`arXiv:2510.07920`
  cited in capital-lab architecture). Kill: (i) doctrine forbids daily P&L
  as selection so the "maximal C4" claim as stated is a violation;
  (ii) Prediction Arena Kalshi −16 to −30.8% (EXTERNAL `arXiv:2604.07355`);
  (iii) Ginko's own bar is ≥500 resolved forecasts at Brier < 0.125 before
  live capital (`ginko_brier.py:7-9`) — that is not a 90-day dollar at
  this HEAD; (iv) $1k bankroll is noise. Nests inside S6 as a forecasting
  cell. Do not resurrect as spearhead without a public Ginko track record.
- **S2 kit-as-today.** Best form: fastest dollar, fixture-proven,
  $5k–$25k, AIUC-1-shaped. Kill as *the whole mission*: C4 is "client paid
  → ??? breeds"; C1 uses ~the kit, not the organism; X-Ray channel failure.
  **S6 is S2 with a spine** — kit is packet 1, not the telos.
- **S3 Evals lab.** Best form: C5 (better models → more eval demand);
  gym generalizes to private benchmarks. Kill as spearhead: crowded
  (LMArena, Scale, LiveBench, AIUC-1 testers); this repo's arena is
  inadmissible as a capability claim. Absorbed as S6 packet 3 (internal
  gym) + S7 (public benchmark).
- **S4 workforce factory.** Best form: C1 maximal, mission-control is real.
  Kill: trust gate C2 RED; selling swarm labor before beating single
  agents fails SATYA; solo non-coder cannot service verticals.
- **S5 forecast desk.** Best form: C7 maximal (wakes Go/radar). Kill:
  §3.5 sequence (no selling forecasts before a public record) plus weak
  C4. Sensing organs wake under S6 packet 4, not as a content business.

**Novel S7 — Public Agent-Promise Benchmark.** An open, held-out set of
"did this agent do what it claimed" tasks with planted failures, published
misses, equal-budget rules copied from the forge. C5/C2 maximal (the
field does not have a SWE-bench-for-promises). C6 weak (benchmarks don't
pay; they make S6 purchasable). If S6's channel fails, S7 is the honest
fallback that still fills an `externally_reviewed_methodology` One Wire
domain. Not the winner because the operator asked for income, not another
leaderboard — but it is the right *storefront* for S6 and should be
packet 2–3, not a second mission.

**Strongest argument against S6 (better than its opponents):**
It is still a service sold by one non-coding human into a market whose
own gauntlet already HELD the consulting shape, while well-capitalized
assurance firms (Schellman / AIUC-1) and protocol teams (ERC-8004
aggregators, ATTP TAs) can ship "trust scores" without Jagat Kalyan.
The philosophy can lose to a worse product with a sales team.

**Why it loses anyway:** the kill-condition is dated and external (no
signed engagement in 90 days). If that fires, stop. If it does not fire,
ordinary operation mints the only receipts that lawfully turn Loops 12/13
on — which no other seed does without either violating no-daily-P&L (S1)
or waiting for a track record that does not exist (S5). Highest ROI for
the whole system is the mission that both pays and unblocks the RSI gate.

---

## D. The 90-day falsifiable test

**By 2026-11-16** (90 days from this run):

1. `reports/revenue_wedge/first_cash_receipt_status.md` shows recorded
   revenue **≠ $0**, with a named counterparty and a RevenueSpine receipt
   an outsider can read.
2. A sealed audit-kit receipt for that engagement exists (JSON, same
   schema as `tests/fixtures/revenue_wedge_target_repo/`).
3. One Wire guardian, re-sensed, shows domain count ≥ 2 including
   `paid_governance_engagement` **or** a dated note that the cash receipt
   was emitted but the guardian was not updated (that note is a process
   miss, not a pass).

**Kill the mission if** (any one):

- No signed engagement by day 90 (channel failed; X-Ray repeated).
- The deliverable is a PDF without a sealed kit receipt (consulting drift).
- Marketing claims the swarm beats single agents while
  `trust_gate_status.py` C2 is still RED (SATYA fail).
- Archive fitness is moved without a guardian N≥5/M≥3 flag (doctrine fail).

Outsiders check the markdown status file, the receipt JSON, and the
guardian JSON — they do not have to trust the swarm.

---

## E. First three build packets

(Full five-packet spine: elevated thesis §F. Tournament asks for three.)

1. **First sealed external verification (cash or signed unpaid pilot if
   cash is refused, but cash is the pass).** Surfaces:
   `scripts/revenue_wedge/audit_kit.py`,
   `docs/offers/agentic-code-governance-sprint.md`,
   `dharma_swarm/revenue/`, `reports/revenue_wedge/`. Not a hot path. Not
   owned by the ten `ACTIVE_TRACK.yaml` globs — do not touch
   `dharma_swarm/chamber/**` or `dharma_swarm/coordination/**` here.
   Independent value: kit + one counterparty row.
2. **Published-misses verifier ledger** using Ginko's JSONL grammar for
   agent-promise items. Surface: `dharma_swarm/ginko_brier.py` — coordinate
   with incubating Shakti Ginko; do not mix trading predictions into
   witness rows without a namespace. Independent value: public honesty
   even if no second sale.
3. **Planted-failure agent-behavior gym** on `dharma_swarm/forge_v1/`
   (unowned glob) **or**, if git-history tasks are required, a packet
   admitted by `hyperbolic-time-chamber-2026-07` before editing
   `dharma_swarm/chamber/**`. Do not cite `coordination/arena/` as a
   public capability. Independent value: eval asset.

---

## F. The operator's hands

The operator does not write code. Exhaustive physical list:

1. Say yes or no to this spearhead (this document is not authority).
2. Ratify the existing $5k–$25k offer as what may be sent, or write a
   lower first-sprint price; agents must not invent prices.
3. Name 10 real humans/firms and send the offer (email or equivalent).
   If this line is refused, C6 is dead — do not ask agents to "find a
   channel."
4. Sign the engagement and receive the wire; no agent holds the account.
5. Merge the packet PRs that install kit output and RevenueSpine rows.
6. Pick one ecological/GAIA counterparty **after** the first receipt (or
   explicitly defer packet 4).
7. Do **not** send live capital to Kalshi as part of this mission.
8. Do **not** sign chain custody / staking for packet 5 in the first 90
   days.
9. If trust-gate C2 staying RED should block *all* external sales, say so
   in one word now — that choice kills the 90-day dollar on purpose.

---

## G. Evidence ledger

| Claim | Class | Path / URL | Shows |
|---|---|---|---|
| Onboard READY, no edit authority | VERIFIED | `make onboard` this run | Session status only |
| Module inventory | VERIFIED | `python3 scripts/repo_xray.py` | 1081 py modules, 982 tests |
| CLOSED_LIVE 0/13, loops 12/13 BLOCKED | VERIFIED | `CYBERNETIC_LOOP_MAP.md:82-94`; `latest_audit.json:446-594` | RSI gated |
| Guardian missing at this audit | VERIFIED | `latest_audit.json:617-628` | N=0/M=0 observed 2026-07-24 |
| Last known N=3/M=1 | RECEIPT | `2026-07-01_loop12_13_one_wire_archive_fitness_guard.json:9-16`; `first_cash_receipt_status.md:22` | Historical guardian-era |
| Revenue $0 | RECEIPT | `first_cash_receipt_status.md:3` | No cash |
| Offer $5k–$25k | VERIFIED | `docs/offers/agentic-code-governance-sprint.md:3-5` | Price |
| X-Ray HELD 28/100 | VERIFIED | `VENTURE_CELL_PORTFOLIO.yaml:91-98` | Consulting precedent |
| Trust gate closed; C2 RED −0.10 | RECEIPT | `reports/governance/trust_gate_status.json:6,22-32` | Honesty stack |
| Live mutation fail-closed | VERIFIED | `evolution_safety.py:5-13` | Darwin not live |
| First-fire is plumbing | VERIFIED | `scripts/first_fire_plumbing.py:1-8`; git `8cc04b71` | Dossier fire unreached |
| DharmaGraph not in dispatch | VERIFIED | `graph/types.py:5` | C1 trap |
| Ginko JSONL + Brier bar | VERIFIED | `ginko_brier.py:1-12,29-31` | Calibration organ |
| One Wire code guard | VERIFIED | `archive.py:52-78`; `tests/test_one_wire_archive_fitness_guard.py` | C4 teeth |
| No-daily-P&L | VERIFIED | `ORGANISM_REWIRE_DOCTRINE_2026-07-02.md:36-37` | C4 doctrine |
| goodworks YAML vs ACTIVE_TRACK | VERIFIED | portfolio yaml:120-123 vs `docs/governance/ACTIVE_TRACK.yaml` | Drift |
| EigenAI paper | EXTERNAL | https://arxiv.org/abs/2602.00182 (2026-08-18) | Crypto inference ≠ behavior |
| Repeated-game inference IC | EXTERNAL | https://arxiv.org/html/2608.09055 (2026-08-18) | Slot narrowed |
| ERC-8004 | EXTERNAL | https://eips.ethereum.org/EIPS/eip-8004 (2026-08-18) | Off-chain aggregator hole |
| ERC-8126 | EXTERNAL | https://eips.ethereum.org/EIPS/eip-8126 (2026-08-18) | Static security score |
| ATTP behavioural dimensions | EXTERNAL | https://datatracker.ietf.org/doc/draft-sharif-attp/ (2026-08-18) | Transport, not witness |
| AIUC-1 | EXTERNAL | https://www.aiuc-1.com/ (2026-08-18) | Paying assurance |
| Kalshi LLM losses | EXTERNAL | https://arxiv.org/abs/2604.07355 (2026-08-18) | S1 kill |
| Sylvera pricing | EXTERNAL | climate-decode.com VCM 2026 rater article (2026-08-18) | Biosphere C6 kill |
| DGM / Mendel | EXTERNAL | https://arxiv.org/abs/2505.22954 ; https://arxiv.org/html/2608.07645 (2026-08-18) | RSI vocabulary |
| Risk budget quartet | REPORTED | dossier §3.4 | Not one canon doc |
| Dossier "fire today" / "26 forecasts on a public branch" | REPORTED | prompt §3.2 | Unreached at HEAD |
| Conversion of 10 outreaches → 1 sale | ASSUMPTION | — | C6 not a fact |
| Chain settlement legal for US solo | ASSUMPTION | — | Packet 5 quarantined |

**Drift list:** see E3. Rule applied: repo (and live web for §5) outranks
dossier; newer-than-HEAD operator events stay REPORTED.

---

*Verdict of a repo-aware run of THE SINGLE TARGET v2, 2026-08-18.
Winner: S6 The Witness (spearheaded). Not a build grant.*
