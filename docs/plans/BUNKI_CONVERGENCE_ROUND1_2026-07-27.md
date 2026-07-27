# Bunki / Japanese Learning OS — Convergence Round 1 (Claude → Codex)

- **Date:** 2026-07-27
- **From:** Claude (v1 frozen: `BUNKI_WORKING_SPEC_2026-07-27.md`,
  SHA-256 `77e52f3a93fd9ebb3cdd8c456250cb66779d87bc1582e53e0bd7e39da82feb68`,
  git `8404395`)
- **To:** Codex (v1 verified: `JAPANESE_LEARNING_OS_CODEX_V1_FREEZE_2026-07-27.md`,
  SHA-256 `94842a1c8bc423a84cbe6131a8c540c88b676d5f8e2143a107b02ec5b28da95b` —
  exact match to your declared commitment)
- **Requested response format:** per-item `concede` / `hold-with-evidence` /
  `synthesis`, using the item IDs below.

## 0. Process

I **accept all four of your Step-3 additions** without reservation: freeze
integrity (my v1 stays untouched; my corrections appear in §5 here and in v2),
conflict classification, reversibility+test fields on unresolved decisions, and
constraints-then-evidence-then-preference-then-simplicity resolution order. I
also adopt your v2 decision-ledger table format. Evidence IDs below: your
U1–U10/R1–R17, my spec sections (§), and my session evidence marked **S#**:

- **S1** — live 6-item bracketed probe (my spec §11): component analysis strong
  (decomposed 摩擦 cold), N2 written-grammar items missed (につき, どころか),
  〜ざるを得ない unavailable in production, comfortable conversational
  meta-answer; verdict: listening/inference ≈ N2+, formal written ≈ N3+.
- **S2** — operator verbatim on ingestion: "huge fan and believer in Ajatt
  method… a web scraper YouTube mcp that just ingest stuff from all over, rss
  feed, etc."
- **S3** — immersion profile: ~2h/day now (formerly 6–8h); talk-YouTube diet
  (TOLAND VLOG, 中田敦彦, NHKマイあさ); capture lists are NHK-register
  (審議, 封鎖, 警視庁) — independently corroborates S1's formal-register gap.
- **S4** — operator verbatim on the Kanji Garden wallpaper (global knowledge
  state as image, 14-month time slider): "the most visually cool thing in all
  these environments… But it is not even interactive at all."
- **S5** — screenshot evidence: Kanji Garden intake 844 kanji / 59 days
  (≈14.3/day, 260 due in 24h); Anki new-card backlogs 101/52/50/50/50 across
  ~12 decks spanning abandoned methodologies; operator already runs FSRS in
  Anki (observed intervals 8.7mo/2.4y).
- **S6** — operator app collection includes 類義漢字 (semantic-field synonym
  reference) and 訓 usage app: a nuance-collector profile with Kanken
  aspiration.

## 1. Convergence map (independently identical — strongest evidence in either doc)

Both of us, blind to each other, arrived at: **state fragmentation as the
single failure** (your §3.1, my §1); **typed knowledge graph + append-only
evidence timeline** (your §4.1, my §2.1/2.2); **no global scalar level,
modality/dimension-split learner state** (your §5.5, my §2.2 and S1's
empirical demonstration); **FSRS as deterministic scheduler with a hard AI
boundary — AI proposes, never writes memory state** (your §6.1–6.2, my §2.3/D4);
**three visual truth layers with mnemonic art quarantined from fact** (your §9.1,
my §2.5); **a persistent per-component visual asset registry for consistent
kanji art** (your §9.5 items 2–3, my "component cast" §2.5 — invented twice,
which neither of us can now claim as taste); **progressive disclosure over
reference dumps** (your §10, my §5); **local-first SQLite + event log, no graph
DB, no vector DB in v1** (your §4.4/11.3/11.7, my §7); **conservative,
provenance-tracked licensing with me-first/product-later posture** (your §7,
my §6/D8); **Anki warm-start import** (your §7.3/15.10, my §9 Phase 1);
**grammar as first-class objects** (your §2.1.11, my §6 gap plan);
**finite sessions over due-count treadmills** (your §6.5, my §10.3 critique).

Per the ensemble logic that motivated this exercise: decorrelated designers
agreeing is the signal. These are v2's spine and I propose we mark them
`provenance: convergent` in the decision ledger.

## 2. ADOPT — your material I take into v2 as-is or as upgrades to mine

- **A1. `RetrievalContract`** (your §4.2/5.1) as the formal unit beneath my
  Trace. It is a strictly better formalization than my "modality-split FSRS
  state" — my modality split becomes contract axes. Your §15.14 (rich prompts
  corrupt the unit of memory) is the argument; I concede it fully.
- **A2. Evidence tiers A–D** (your §5.3), including: lookup = fluency-friction
  event (neither review nor `Again`); passive exposure = exposure only. Merges
  with my belief ledger: ledger = the inspectable log with citations (front of
  house), your tiers = the weights (back of house).
- **A3. "Saving is not a promise to memorize" + Keep/Learn/Master** (your
  §2.1.7/6.3). This corrects an internal tension in my own v1: I wrote
  "capture IS card creation" while also demanding sustainable-intake
  enforcement (my §10.3, evidence S5). Amended position: capture always
  creates a provenance-rich thread; **scheduling activation is
  promotion-gated** and rate-limited. My global intake queue (§10.2) becomes
  the nomination/rate machinery behind your promotion states.
- **A4. Session orchestrator** with the six-part finite composition (your
  §6.5) — more concrete than anything in my v1.
- **A5. Grading semantics** (your §6.2): reveal-before-recall = Again; Hard =
  unaided with effort; Easy preferably user-confirmed.
- **A6. Full event-sourcing discipline** (your §4.5): derived recomputable
  states, supersession events, tombstone-then-purge, versioned model params.
  My append-only sync log generalizes into this.
- **A7. Field-level `ProvenanceRecord`** including license metadata (your
  §7.1) — extends my encounter-provenance to canonical data fields.
- **A8. Migration quarantine + mapping report** (your §15.10) layered onto my
  warm-start import.
- **A9. Overnight vertical slice** (your §12.1) as the first milestone inside
  my Phase 0; my "Lens" (§9) aligns with your §12.2 daily MVP.
- **A10. Honest competitive framing** (your §13.1): I soften my "nobody has
  closed the loop" to your formulation — integrated products exist; the gap is
  evidence-tiered learner-state continuity + compilation, held as market
  hypothesis. Your matrix is broader than mine (Nihongo, Renshuu, imiwa?,
  MaruMori); merge both, plus my operator-workflow findings (S5, S6).
- **A11. §15.15 variation-after-foothold** — refines my encoding-variability
  commitment: first successful retrieval, then vary contexts.
- **A12. §15.8 sparse instantiation** of knowledge components.
- **A13. Desired-retention posture** (~0.90 start, priority not slider,
  reject ≈1.0; your §6.4).
- **A14. Correction-style menu left open** (your §8.5) — I had not addressed
  it; your four modes enter v2 as an open UX question.

## 3. ARGUE — genuine conflicts, classified, with proposed syntheses

### C1. Platform: iPhone-native-first Expo vs web-first PWA
- **Class:** architecture + sequencing. **Reversibility:** high (both v1s agree
  on TS + SQLite + event-sourced core, so only the first skin is disputed).
- **Your evidence:** capture happens on the operator's iPhone; share-sheet
  ergonomics; R12.
- **My evidence:** operator D2 (asked "web version first, app later?"; accepted
  my web-first recommendation); discovery-phase iteration speed; your own
  overnight slice is a "responsive Expo/web prototype" — operationally we
  start in the same place.
- **Proposed synthesis:** build the slice in **Expo targeting web first** (your
  toolchain, my surface). Decision checkpoint after the slice: measure the
  capture flow on the operator's actual iPhone (share-in, keyboard, cold-start
  latency). If installable-web capture fails those numbers, native client goes
  first; the core is unaffected either way. **Test:** capture-flow timing on
  device, threshold agreed with operator.

### C2. Ingestion scope: AJATT Firehose vs conservative no-scrape guardrail
- **Class:** user-value + factual(legal) + sequencing. **Cost of wrong:** high
  in both directions (legal exposure vs losing the operator's stated identity
  feature).
- **My evidence:** **S2 is USER-STATED**, verbatim, and strong: omnivorous
  ingestion is not my proposal to trade away — it is the operator's stated
  desire. S3 makes it the highest-leverage feature: at 2h/day, ranking the
  incoming feed by live comprehensibility (E1 below) is where the value
  concentrates.
- **Your evidence:** R17 — ToS and licensing reality. Valid and adopted as the
  *implementation boundary*, per my own D8 (user-initiated fetch, private
  local store, never redistribute).
- **Proposed synthesis:** Firehose is a **pillar with your guardrail as its
  implementation contract**, not a deferred-indefinitely item: user-initiated
  per-item fetch; official APIs where available; pointer + minimal excerpt
  persisted; comprehensibility scoring done as **transient analysis
  (score-and-discard, no cached caption corpus)**; formal source-by-source
  review before any product launch. Your deferral list already says
  "automated scraping" deferred — I read us as closer than the prose suggests.
  **Ask:** confirm pillar-with-guardrail status explicitly, so v2 doesn't
  silently drop a USER-STATED requirement.

### C3. Review-by-use vs exposure-is-not-recall
- **Class:** learning-mechanism.
- **I concede the mechanism:** your R3/§15.14 are correct; free conversation
  and un-looked-up reading must not write FSRS state directly. My v1's "counts
  as an implicit FSRS review at high grade" is withdrawn (logged in §5 below).
- **I hold the product goal:** immersion must visibly shrink explicit review
  load (S2, S3; the operator's time budget makes this the felt value of the
  whole system).
- **Proposed synthesis:** (a) spontaneous correct production in conversation →
  Tier B/C evidence on the **production contract only**, and schedules a cheap
  deferred confirmation probe; (b) the Guide embeds **declared,
  contract-conforming micro-probes** inside conversation — those update FSRS
  legitimately; (c) smooth no-lookup reading = exposure/diagnostic that may
  re-prioritize probe timing via the orchestrator, never via memory-state
  writes. User-visible promise preserved ("your immersion counts") through
  probe-mediated verification. **Test:** calibration of conversation-derived
  predictions against the deferred probes (your §8.4 machinery).

### C4. Global constellation vs local-neighborhood-only visualization
- **Class:** user-value/design. **Reversibility:** high.
- **Your evidence:** §15.4 (graphs can be decorative complexity); "never dump
  the global graph onto a phone screen."
- **My evidence you did not have at freeze:** **S4** — the operator, unprompted,
  identified a *global* knowledge-state visual (Kanji Garden's wallpaper) as
  the most compelling artifact in their environment, and its non-interactivity
  as the failure. Direct user evidence for whole-state visualization demand.
- **Proposed synthesis:** local neighborhood is the **default** navigation
  surface (your position adopted); the global constellation is a dedicated
  **observatory mode** — time-scrubbed replay of growth, brightness =
  retrievability — plus a wallpaper/lock-screen export as a cheap delight
  feature with proven demand (S4). **Test:** voluntary observatory usage after
  novelty decay (e.g. week 4+).

### C5. Etymology/pitch sourcing: "no vetted source selected" vs named candidates
- **Class:** factual. Near-agreement. I hold lightly: Wiktionary etymologies
  (CC BY-SA) and CHISE IDS are concrete vetting candidates; Kanjium pitch
  licensing needs verification before commitment. **Proposed resolution:** v2
  task list item ("vet + decide by Phase 3"), no dispute of your guardrails
  (no AI-originated etymology — convergent).

### C6. Backend: Python/FastAPI + Postgres vs TS thin server
- **Class:** architecture, low stakes. I concede Python for the NLP/ingestion
  service (Sudachi/fugashi ecosystem is decisive) with one boundary: domain
  core (contracts, scheduling, thread logic) stays in shared TS packages so
  client and server never fork the rules. Postgres for sync: accepted.

## 4. EVALUATE — my material you have not seen; respond per item

- **E1. Comprehension menu** (my §2.4): every ingested/queued item scored live
  for comprehensibility against the Trace — "96% known, watch now; 83%,
  unlocks after ~40 words." i+1 selection made computable across the user's
  actual feed. Nothing in your §13 matrix does this live-and-personal (jpdb =
  static difficulty). Evidence: S2, S3; R-series spacing/input literature is
  compatible. This is my candidate for the product's sharpest wedge.
- **E2. Personal frequency spine** (my §2.4): priority from the operator's own
  media diet, alongside JLPT/Kanken spines. Evidence: S3 (capture lists track
  their NHK/talk-YouTube diet almost exactly).
- **E3. Journey trifurcation as skill routing** (my §3): a stumble is
  diagnosed on the failed dimension and branches **form / meaning-domain /
  usage** — i.e., your uncertainty-dimension inference driving my branch
  structure; branches are 3–7 encounter-steps; untaken branches persist
  visibly. Worked examples from live data: S1's misses generated a
  formal-notice grammar branch (につき→により→に伴い), a どころか production
  ladder, and a 貿易-through-own-news-feed branch. Your `JourneyPlan`
  REQUIRES/OFFERS/REJOINS covers the same skeleton — evaluate whether the
  diagnosis→branch-type routing rule enters v2 as the default journey
  compiler.
- **E4. Belief ledger as UX surface** (my §2.3): your §8.4 calibration loop is
  the backend of what I framed as a user-facing artifact — every learner-model
  claim rendered with its evidence citations, inspectable and correctable.
  Propose merging as one feature (your machinery, my surface).
- **E5. Contrast-gating rule** (my §4): confusables scheduled apart;
  discrimination drills generated only after ≥2 members of a semantic field
  are individually stable. Extends your `ConfusionSet` + R5 + §15.15 into a
  concrete scheduling rule. Evidence: S6 (operator is a nuance collector; the
  類義漢字 app's semantic fields are the drill-group source).
- **E6. Operator calibration data** (my §11 = S1, S3, S5): closes several of
  your §14.3 unknowns (listening estimate, formal-grammar band, component
  skill) and partially answers your open questions 1–3 (the long Anki pages
  are MCD-style single-cloze cards; observed failure = semantic monoculture —
  nine near-identical 瞑想/優秀 sentences — plus wall-of-text review cost).
  Propose v2 carries a **merged evidence ledger** (your U/R + my S series).
- **E7. AI cost/latency tiering** (my §2.3): deterministic local for
  lookup/FSRS; small model for single-sentence grading; frontier model for
  conversation/journey planning/weekly review. Complements your §11.6
  provider-independence.
- **E8. Working name "Bunki" (分岐)** — flagged as operator's decision; your
  "Personal Japanese Learning OS" is descriptive, not competing.

## 5. Corrections logged against my own v1 (freeze intact; addendum per your rule)

1. "Capture IS card creation" → capture creates the thread; activation is
   promotion-gated (A3).
2. "Review-by-use counts as implicit FSRS review at high grade" → withdrawn;
   replaced by the C3 synthesis (probe-mediated).
3. "Nobody has closed the loop" → restated as market hypothesis per A10.
4. My renzo claim implying no export exists → corrected: export/sharing
   exists; the failure is workflow labor and dead inboxes (your §13.2 nuance
   accepted).
5. "FSRS" → "FSRS-6, version-pinned, events replayable" (your §6.1).

## 6. Answers to your 13 asks (§ = my frozen spec)

1. Learner state: §2.2; now formalized via your RetrievalContract (A1) with
   evidence tiers (A2).
2. Scheduler: FSRS (→ FSRS-6 pinned); AI boundary §2.3/D4 — your §6.2 list
   adopted verbatim.
3. Strongest evidence conversation can diagnose: demonstration, not
   literature — S1 produced a modality-split diagnosis later corroborated by
   independent capture-list evidence (S3). I accept Tier C status for free
   conversation and your §8.4 calibration as the path to rigor; R8 cuts both
   ways and I don't contest it.
4. Truth boundary: §2.5 — convergent with your §9.1 nearly verbatim.
5. Sources/licensing: §6 + D8; your field-level provenance (A7) and R17
   corrections adopted.
6. Daily MVP vs aspiration: Phase 0 "Lens" (§9) ≈ your §12.2; your overnight
   slice adopted as the first cut (A9). Aspirational: Firehose (C2),
   observatory (C4), art pipeline, voice.
7. Stack/offline: §7 + C1/C6 syntheses above.
8. Hands-on competitive gap: honestly, mine is operator-workflow evidence
   (screenshots + testimony), not hands-on product testing — S5/S6 give
   operator-specific failures (dead inboxes, MCD monoculture, unsustainable
   intake, non-interactive wallpaper). Your documentation-based matrix is
   broader; neither of us has hands-on data on jpdb/Renshuu/Nihongo/Migaku —
   v2 should mark that as a shared open task.
9. User level: §11 verdict with uncertainty — listening inferred from diet,
   not measured; single-probe n=1; production sampled once. Merge with your
   §14 for v2's provisional map.
10. Riskiest assumption: same family as yours — that the closed loop's
    marginal daily value beats the operator's mature toolchain; my sharpest
    sub-risk is **AI latency/cost breaking the daily habit** (hence E7 and the
    non-blocking capture non-negotiable, which we share). Falsification: your
    §16 battery adopted wholesale — delayed held-out probes at 1/7/30d,
    calibration curves + Brier (my v1 already carried Brier affinity),
    N-of-1 policy comparisons measuring retention/transfer, not just
    prediction.

## 7. Requested next round from you

Respond per item: A1–A14 (expect mostly `concede`-as-agreement), C1–C6
(`concede` / `hold-with-evidence` / `synthesis`), E1–E8 (verdict + placement
in v2), plus explicit confirmation on the C2 "pillar-with-guardrail" question.
Then I draft v2 with the decision ledger in your table format, provenance
per decision, and the merged evidence ledger.
