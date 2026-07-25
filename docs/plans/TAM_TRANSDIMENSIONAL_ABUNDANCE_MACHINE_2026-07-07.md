# TAM — Transdimensional Abundance Machine (2026-07-07)

**Track:** `company-builder-parity-2026-07` (serves `revenue-external-humans-served`)
**Instrument:** `scripts/governance/tam_ledger.py` (+ data owner `scripts/governance/tam_axes.py`)
**Surface:** `reports/governance/tam/` — `tam_receipt.json` (digest-stamped), `COMPANY_BUILDER_PARITY.md` (the board), `tam_history.jsonl` (velocity chain)
**Replay:** `python3 scripts/governance/tam_ledger.py --check` (byte-for-byte or non-zero exit)

## The machine's name and telos

**TAM = Transdimensional Abundance Machine** (operator-resolved 2026-07-07):
the organ that measures abundance across every dimension the organism serves
against the strongest external company-builders. The soul lives in the name;
the clarity lives in the number — its single headline output is deliberately
plain: the **Company-Builder Parity %**.

## The metric, plainly

> **Company-Builder Parity %** — 0% = far below the Polsia/Cofounder
> capability baseline; 100% = at parity on everything they do; >100% = we
> exceed on axes they cannot match.

Per-capability scoring: **Behind = 0 · At parity = 1 · Ahead = 1.5**, over
the denominator of all comparable + unmeasured rows. Lane rules (pure
function `parity_bucket`, ordering is load-bearing):

1. Competitor cell uncited or UNKNOWN → **Unmeasured** (never a guess).
2. Our cell without a repo owner → **Unmeasured**.
3. Competitor ABSENT (cited clean negative) → **No competitor equivalent**
   (excluded from the denominator; watched as the exceed-vector lane).
4. Ours RUNS + cited structural exceed-vector → **Ahead**.
5. Ours RUNS → **At parity**. Anything less → **Behind**.

### Anti-gaming (the adversary check, encoded as tests)

Question asked before committing: *can parity_pct be made to look higher than
honest?* Vectors found and closed:

- **Mark Unmeasured rows as Ahead** — impossible: uncited competitor cells
  bucket to UNMEASURED before AHEAD is ever considered (rule ordering), and
  UNMEASURED scores 0 **while staying in the denominator**, so not measuring
  always drags the number down (`test_unmeasured_rows_stay_in_denominator_and_cannot_inflate`).
- **Narrate an exceed-vector on a dormant organ** — `validate_row` raises
  ValueError unless ours is RUNS *and* the exceed citation exists
  (`test_ahead_must_be_earned_not_narrated`).
- **Shrink the denominator by declaring competitor ABSENT** — ABSENT requires
  a cited clean negative or `validate_row` raises
  (`test_uncited_competitor_absent_cannot_shrink_denominator`).
- **Hand-edit the receipt/board** — digest seal + `--check` pure-render
  comparison catch both (`test_write_then_check_roundtrip_and_tamper_detection`,
  `test_markdown_is_a_pure_render`).

## First honest render (2026-07-07)

**parity_pct = 35.0 [RED]** · Behind 6 · At parity 2 · Ahead 1 ·
No-equivalent 2 · Unmeasured 1. Sparse and mostly Behind — that IS the
day-one truth. Velocity is unmeasured until a second render populates
`tam_history.jsonl` (the chain is digest-linked; the governance checker
verifies it with `expect_chain`).

## Axis list and sourcing

Competitor snapshot: 2026-06-10 world triangulation
(`reports/anatomy_altitude_2026-06-10/lane_F_world.md`); every competitor
cell carries a URL + verification label (`vendor-claim` /
`third-party-report` / `source-pending` / `unverifiable`) per the
NORTH_STAR §5 source-pending rule. Refreshing these facts is track
next-item 2, never silently assumed current.

| Axis | Ours (owner) | Competitor (source) | Lane |
|---|---|---|---|
| Org-shaped orchestration | WIRED_BUT_DORMANT — orchestrator + spine (lane_F:21) | Cofounder CLAIMED (cofounder.co) | Behind |
| HITL approval | RUNS — telos_gates + gate PEP (lane_F:22) | Cofounder CLAIMED (cofounder.co) | At parity |
| Typed witnessed gates | RUNS — GateRegistry + witness (lane_F:28) | Cofounder CLAIMED (cofounder.co) | **Ahead** (exceed cite lane_F:28) |
| Customer-facing execution | ABSENT (lane_F:25 clean negative) | Cofounder CLAIMED (cofounder.co) | Behind |
| GTM milestone scaffold | ABSENT (lane_F:26) | Cofounder CLAIMED (cofounder.co) | Behind |
| Extensibility (MCP/skills) | RUNS — SkillRegistry + registries | Cofounder CLAIMED (cofounder.co) | At parity |
| Pricing + billing | ABSENT (lane_F:42) | Polsia SHIPPED ($49/mo + 20%, polsia.com) | Behind |
| Distribution / ARR | ABSENT — $0 (lane_F:199; portfolio revenue_usd 0) | Polsia CLAIMED ~$10M ARR, **source-pending** (ain.ua, aiweekly, zilla.so) | Behind |
| E2E company operation | ASPIRATION — portfolio live-read | Polsia CLAIMED 9 agents E2E (polsia.com) | Behind |
| **Honest (receipted) ARR** ⭐ | WIRED_BUT_DORMANT — EvidenceReceipt, $0 to date (lane_F:28,44) | Polsia+Cofounder ABSENT — 4.4x claims gap (zilla.so, third-party) | No equivalent |
| Governed self-evolution | WIRED_BUT_DORMANT — genome table "overclaim risk" | Polsia+Cofounder ABSENT (public surfaces, lane_F) | No equivalent |
| Competitor internals | RUNS (repo-inspectable) | UNKNOWN — SPECULATIVE (lane_F:18,204), no citation | Unmeasured |

**The headline differentiator is `honest_arr`**: Polsia's documented 4.4×
claimed-vs-actual ARR gap (claimed $3M+ vs $689K run-rate,
zilla.so/blog/polsia-review) is the load-bearing wedge — incumbents cannot
publish receipted revenue without exposing the gap; our receipt spine can,
the moment real dollars flow through it. Honestly graded WIRED_BUT_DORMANT
($0 receipted revenue to date), so it sits in the exceed-vector watch lane,
not in Ahead.

## Naming resolution (collision map)

- **TAM (this machine)** = Transdimensional Abundance Machine — instrument
  name only; headline stays "Company-Builder Parity %".
- **TAM = Total Addressable Market** (`foundations/FIVE_FOURTEEN_A.md:49`) —
  untouched, not overloaded.
- **`reports/tam/`** — Darshan-owned; untouched. This machine writes only
  `reports/governance/tam/`.

## Reuse map (no new primitives)

- `stable_digest` / `utc_now` — `dharma_swarm/memory_kernel/write_receipts.py`
  (same seal convention `check_track_status.check_receipt_valid` recomputes).
- `verdict_for` (GREEN≥0.8 / AMBER≥0.4 / RED) and `parse_cell_statuses`
  (portfolio live-read) — imported from `scripts/governance/trust_gate_status.py`.
- Surface contract (receipt + pure-render markdown + `--check` replay,
  volatile-keys convention) — cloned from `scripts/governance/arena_truth_report.py`.
- History chain rows follow the `check_track_status` chain convention
  (digest over all fields except `digest`; `prev_digest` links; empty genesis).

**Deviation from the build prompt, flagged honestly (updated at merge):**
the prompt named `scripts/governance/frontier_ledger.py`,
`dharma_swarm/chamber/ledger_rows.py` / `ledger_history.py`, and the
`hyperbolic-time-chamber-2026-07` track as the instrument/modules to clone.
At build time none of these existed on the main this branch was cut from —
**they landed on main mid-session via PR #830** (merged after this branch's
base commit `d0a2c5d`). TAM was therefore built as a sibling of the shipped
instrument implementing the identical contract, `arena_truth_report.py`,
with the row/comparator and history-chain semantics implemented against the
same house conventions the chamber ledger uses (`stable_digest` seal,
`check_track_status` chain format). Reconciled at merge: the track now
`complements` both `organism-rewire-2026-07` (whose next-item 8 demanded
this spine objective be served next) and `hyperbolic-time-chamber-2026-07`;
a consolidation audit onto the chamber ledger helpers is track next-item 3.
The operator's forged master prompt (which PR #830 committed at this file's
path) is preserved verbatim at `docs/plans/TAM_MASTER_PROMPT_2026-07-07.md`.

**Competitor-fact correction in flight (2026-07-07):** the deep
blueprint/genealogy research pass adversarially REFUTED the zilla.so "4.4×
claimed-vs-actual ARR gap" framing this dossier and `tam_axes.py` cite: the
$689K run-rate (Mixergy, recorded ~Feb 2026) predates the $3M+ claims by
2–3 weeks of independently documented hypergrowth (True Ventures 2026-03-23
"tripled to $3M ARR"; agent-wars 2026-03-14 "$3.5M"), the contemporaneous
gap was ~1.45× at most, and zilla.so is an anonymous SEO-style review blog,
not third-party reporting. The structural honest-ARR thesis (no incumbent
publishes third-party-verifiable revenue) stands, but the 4.4×-gap wedge
must not be repeated as fact. Axis rows `honest_arr` and `distribution_arr`
get corrected from the verified dossier in track next-item 2.

## Operator decision queue

1. **Track home** — keep standalone `company-builder-parity-2026-07` (as
   landed) or fold into another lane; one-line YAML move either way.
2. **WIP** — the portfolio now has 6 ACTIVE tracks (warn threshold 5, max
   10). Checker warns; ratify the sixth or close/merge one.
3. **Axis set + weights** — ratify the day-one 12 axes and the
   Behind 0 / At 1 / Ahead 1.5 scoring (in particular whether Ahead's 1.5
   premium is wanted in the headline).
4. **Refresh cadence** — competitor facts are a 2026-06-10 snapshot;
   `fresh_ttl_days: 30` on the receipt forces a monthly re-render. Approve
   the afferent research refresh (track next-item 2).
5. **Dashboard wiring** — optional `KanbanLane[]` producer feeding
   `CoherenceKanban.tsx` (next-item 3); until then the `.md` table IS the board.
