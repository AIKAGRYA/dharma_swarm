# Bunki (分岐) — Working Product Spec v1 (brainstorm-phase draft)

- **Date:** 2026-07-27
- **Status:** DRAFT v1 — closing artifact of brainstorm phase, session 1.
  Awaiting merge with a second AI collaborator's independent spec → convergence into v2.
- **Operator:** user #1 and design partner (see §11 calibration snapshot).
- **Working name:** Bunki (分岐, "branch point" — a railway term; gifts the visual
  language of a branching metro map). Alternates parked: Kodama 木霊, Ayumi 歩み.

---

## 1. Thesis

Every existing Japanese-learning tool treats the language as a **list** (word
lists, kanji levels, card decks). Japanese is natively a **graph**: sentences
contain words, words contain kanji, kanji contain components; grammar patterns
link sentences; everything links back through the learner's memory of it.

Nobody has closed the loop **conversation ↔ learner model ↔ SRS ↔ content
graph**. Anki+Yomitan is power with zero cohesion; jpdb.io has frequency data
but no AI or conversation; WaniKani is a beautiful kanji silo; Bunpro a grammar
silo; ChatGPT converses but has no memory state or scheduler. **The product is
the closed loop.**

Positioning: dictionary + kanji dictionary + SRS + sentence mining + AI tutor
rolled into one recursive, multi-dimensional learning journey — fast,
scientifically grounded, beautiful, AI-native.

## 2. Architecture — four pillars + a visual layer

### 2.1 The Atlas — content graph (reference layer)
Typed graph. **Nodes:** kanji, components, words, grammar patterns, sentences,
audio, pitch-accent shapes. **Edges:** `contains` (sentence→word→kanji→component),
`contrasts-with` (lookalike kanji 末/未, near-synonyms 解決/解消),
`collocates-with`, `derives-from`, and `component-of(role=semantic|phonetic|corrupted)`.
Component **roles** are first-class: most kanji are phono-semantic and knowing
which part carries sound vs meaning is one of the highest-leverage facts in
kanji study (e.g. 演 = 氵 semantic "water/flowing" + 寅 phonetic イン→エン;
never make the learner memorize the tiger).

### 2.2 The Trace — learner state (overlay on Atlas)
Per node: FSRS memory state (stability, difficulty, retrievability) **split by
modality** — reading recognition ≠ meaning recall ≠ production ≠ listening.
Plus **provenance** (which video/conversation/article the item was met in) and
error history. Provenance makes cards emotional instead of orphaned facts.
A single JLPT number is the wrong abstraction (operator's own probe proved it:
listening ~N2+, formal written grammar ~N3 — §11).

### 2.3 The Guide — AI layer
Conversational tutor that (a) converses at calibrated i+1 by consulting the
Trace before each reply, (b) diagnoses from errors/hesitations, (c) plans
branching journeys, (d) drafts cards from real encounters.

**Hard rules:**
- **AI proposes, deterministic systems dispose.** Scheduling is FSRS math, not vibes.
- **Belief ledger:** every AI judgment about the learner cites evidence
  ("used 〜ざるを得ない correctly on 7/20; confused 滞る twice") — inspectable,
  never "I sense you're intermediate." (Citation-or-silence, applied to tutoring.)
- Cost tiers: cheap/local for tokenization, lookups, FSRS; small model for
  single-sentence grading; frontier model for conversation, diagnosis, journey
  planning, weekly tutor reviews.

### 2.4 The Firehose — omnivorous AJATT ingestion
User-initiated pipelines: YouTube transcripts (ships first — operator's diet is
talk-heavy YouTube), RSS, web clipper (readability-extracted), subtitle files,
ebooks, pasted anything; later podcast audio via Whisper. Everything tokenized
(Sudachi/MeCab) and diffed against the Trace. Unlocks:

- **The comprehension menu:** every ingested item scored live for
  comprehensibility ("this video is 96% known — perfect i+1, watch now; this
  article is 83% — unlocks after ~40 more words, here they are"). A daily
  immersion queue ranked scientifically. Nobody does this live across arbitrary
  sources against a real memory model.
- **Personal frequency list:** word priority computed from the learner's own
  media diet, not a national corpus. AJATT's core insight made computable.

Licensing stance: ingestion is user-initiated fetch into the user's own local
store (the Yomitan "tool, not content distributor" model) — clean for a future
product.

### 2.5 Visual layer — three strata with an honesty split
AI art and factual reference must never blur:

1. **Stroke order — deterministic, not AI.** KanjiVG ordered vector strokes →
   animations, tracing, stroke-by-stroke scrubbing.
2. **Etymology — factual and cited.** Real 字源 with semantic/phonetic role
   tagging (sources: CHISE IDS, Wiktionary, curated). Always labeled history.
3. **Mnemonic art — AI, proudly invented.** Style bible (sumi-e ink + one
   vermilion accent) and a **persistent visual cast**: every component gets a
   fixed visual identity (麻 is always *that* hemp motif, 糸 always *that*
   thread), and each kanji's artwork is composed from its components'
   established characters (reference-conditioned generation / style LoRA).
   Recognizing the cast IS recognizing the kanji — dual-coding as a system,
   not a gimmick. Generated once, cached, versioned, regenerable with the
   user's own mnemonic story. Labeled "memory image," never history.

## 3. Journey engine — branching as skill routing

A **journey** is a small DAG generated by the Guide from a **seed** (failed
review, conversation stumble, mined sentence). Diagnosis picks which dimension
failed and offers branches — bifurcation/trifurcation is not a gimmick, it's
routing across different memory systems:

- **Form branch** (misread): component story, kanji family, lookalike contrasts.
- **Meaning/domain branch** (concept-space gap): 5-sentence micro-ramp from the
  learner's own ingested corpus, then a short Guide chat in that domain.
- **Usage branch** (knew it, couldn't deploy): suffix/collocation patterns,
  then a production drill.

Branches are 3–7 encounter-steps, each generating cards. Untaken branches stay
visible on the map as dimmed rails — revisitable. Worked example from the
operator's live probe (首相 hesitation → 首 family / politics micro-immersion /
〜相 suffix + collocations) and from probe misses (formal-notice grammar branch
につき→により→に伴い; どころか drill ladder; 貿易 vocab through own news feed).

## 4. Learning science commitments

- **FSRS** scheduler (open-source, outperforms SM-2; per-user parameter fitting
  once review history accumulates). One true scheduler; no vibes.
- **Retrieval practice** with graded ladders: recognition → cued recall → free production.
- **Encoding variability:** same word re-met across multiple real contexts
  beats one frozen card; the Firehose supplies this naturally.
- **Interference management:** the graph knows confusables (末/未, 解決/解消) —
  schedule them apart; explicit contrast drills only after each is individually
  stable.
- **Review-by-use (signature mechanic):** correct use in conversation, or
  reading past a word in context without lookup, logs as an implicit FSRS
  review (conversation use = strong signal; no-lookup reading = weak signal —
  start conservative). Immersion shrinks the review queue; cards become the
  backstop, not the grind.
- **i+1 comprehensible input** enforced computationally (95–98% target), not by feel.
- **Dual coding** via the component-cast visual system (§2.5).

## 5. Kanji page spec (anti-overload contract)

Five zones earn pixels; everything else is one "unfold" tap away, present but
silent — progressive disclosure driven by the Trace, not a settings page:

1. Readings (on/kun) tagged by real-world frequency of each reading; rare
   readings collapsed.
2. Components with roles (semantic vs phonetic).
3. Position on progression spines: JLPT band, Kanken level, news-frequency
   rank, personal-corpus rank.
4. Compounds ranked by frequency — learner's own corpus first, then general.
5. Stroke order + visual layer (KanjiVG animation, cited etymology, mnemonic art).

Dictionary indices (SKIP, Henshall, NJECD, Gakken, New Nelson, KALD, Daikanwa/
Morohashi) are **join keys, not curriculum**: kept in the database (KANJIDIC2
interop), never rendered on the kanji page.

**Progression spines (selectable per goal):** JLPT · Kanken · personal
frequency. Operator's aspiration is upper Kanken — note 準1/1 require
handwriting, so a stroke-input canvas enters the long-term roadmap.

## 6. Data plan (open, product-safe)

| Layer | Source | License |
|---|---|---|
| Words | JMdict | CC BY-SA |
| Kanji | KANJIDIC2 | CC BY-SA |
| Components | KRADFILE / CHISE IDS | open |
| Sentences | Tatoeba | CC BY |
| Pitch accent | Kanjium | open |
| Stroke order | KanjiVG | CC BY-SA |
| Frequency | BCCWJ lists + personal corpus | open / user's own |
| Tokenization | Sudachi or MeCab+UniDic (fugashi) | Apache/BSD |

**Honest gap:** grammar patterns have no great open dataset (Bunpro/DoJG
proprietary). Plan: curate the pattern *taxonomy* ourselves (few hundred
patterns); the Guide generates explanations on demand anchored to it.

## 7. Platform & stack decisions

- **Web-first PWA now, mobile app later** — enabled by keeping everything that
  matters in platform-agnostic TypeScript packages: `atlas` (graph + ingest),
  `trace` (FSRS — use open-source ts-fsrs), `journey` (DAG engine), `guide`
  (LLM orchestration). Web UI is a skin; a later Expo/Capacitor app reuses the core.
- **Local-first SQLite** (wa-sqlite/OPFS in browser) + **append-only event log
  for sync** — the one thing that's painful to retrofit, so designed in from day one.
- Thin server: ingestion workers (YouTube/RSS/Whisper), sync, LLM proxy.
- Do NOT start in React Native for a hypothetical future app; design-discovery
  iteration speed wins. PWA is installable for phone reviews meanwhile.

## 8. Design language

Typography-first: real Japanese type (Shippori Mincho for reading surfaces,
clean sans for UI), first-class furigana (ruby), optional vertical text.
Reading surfaces render clean; only Trace-unknown/fragile words carry a quiet
mark (personal frontier, never global-level rainbow underlining — §10.4).
Ink-and-paper palette, one vermilion accent, generous *ma*. Centerpiece: the
**constellation/metro map** where node brightness IS FSRS retrievability — due
items literally dim; the map growing and glowing is the reward. The map is a
live, tappable navigation surface (node → kanji page / journey seed), with a
**time scrubber** to replay growth history — inspired by Kanji Garden's
wallpaper export (§10.3), which proved the emotional pull of
whole-knowledge-at-a-glance while being a dead poster. No confetti,
no XP; honest metrics (retention rate, comprehension %). Bar for reference
screens: a kanji page should feel like a museum card, not a spreadsheet row.

## 9. Build phasing

- **Phase 0 — The Lens** (~2–3 wks): Atlas in SQLite; paste/URL reader with
  tap-to-lookup; mine → FSRS reviews; Trace v0 with provenance. Replaces the
  Yomitan+Anki loop; daily-usable immediately.
- **Phase 1 — The Guide:** AI tutor with belief ledger; mining from
  conversation; review-by-use; calibration onboarding (probe of §11 style);
  **Anki warm-start import** — ingest collection + review logs, map cards to
  Atlas nodes, inherit FSRS states (operator already runs FSRS in Anki, so
  years of memory history transfer instead of cold-starting the Trace).
- **Phase 2 — The Firehose:** YouTube/RSS/clipper pipelines; personal frequency
  list; comprehension menu.
- **Phase 3 — The Map:** journey DAG engine; constellation view; contrast
  drills; pitch training; per-user FSRS fitting.

## 10. Competitive metabolism (running log)

| Tool | Keep | Reject |
|---|---|---|
| Anki+Yomitan+Migaku | power, openness | zero cohesion, no learner model, manual card labor |
| jpdb.io | frequency-aware decks | no AI, no conversation, dated UI, static difficulty |
| WaniKani | kanji polish, mnemonics discipline | fixed order, silo, no mining |
| Bunpro | grammar taxonomy | silo |
| Satori Reader | graded reading UX | closed content |
| LingQ | word-status model over content | crude model, no SRS depth |
| ChatGPT tutoring | conversation | no memory state, no scheduler, no structure |

### 10.1 "Japanese" (renzo) — reviewed 2026-07-27 from operator screenshots
- **Keep:** five-tab IA (Search/Text/Reference/Lists/Study ≈ our modes —
  validates the IA; missing piece is *circulation* between tabs); Kanji Kentei
  as first-class taxonomy; offline/fast/comprehensive local-first feel;
  conjugation tables as unfoldable reference.
- **Diagnoses:**
  1. **Vocabulary graveyard** — operator's monthly lists (e.g. 七月: 演習,
     対価, 封鎖, 審議, 飢える, 左折, 秘訣, とんちんかん, 警視庁) capture
     without metabolism: no context, no provenance, no scheduler; export-to-Anki
     is manual labor that never happens. In Bunki, **capture IS card creation**
     (auto provenance + context sentence from own corpus + FSRS state); a
     monthly list auto-becomes a journey seed. Note the list is NHK-register —
     corroborates the probe's formal-register gap across independent sources
     (belief ledger cross-validation).
  2. **Data without pedagogy** — its 演 page shows components 氵 ("No
     Translations") and 寅 as zodiac trivia while withholding the one fact that
     matters (phono-semantic structure). Role tagging (§2.1) is the antidote.
  3. **Reference-index noise** — SKIP/Henshall/NJECD/Gakken/New Nelson/KALD/
     Daikanwa rendered at full weight; see §5 contract: join keys, not curriculum.
- **Sensibility lesson:** it's a database rendered as table views — no
  hierarchy between headword and index number, no story. §8 is the antidote.

### 10.2 Anki (operator's live setup) — reviewed 2026-07-27 from screenshots
- **Meta-finding:** the deck list is an archaeology of methodology reboots
  (RTK 13, Lazy Kanji + Mod, All in One Kanji, Kanji Radical, Japanese MCD
  Pro, yearly "2024 NIHONGO" / "2025 漢字検定"). Each reboot orphaned the
  previous deck's scheduling history → principle: **one Trace, many views** —
  methods/drill styles are filters over one permanent memory state; a
  methodology change must never lose memory history again.
- Cross-deck prioritization is impossible in Anki; new-card backlogs
  (101/52/50/50/50) hide the true queue → Bunki uses a **single global intake
  queue**, priority = personal frequency × goal spine, rate-limited by
  FSRS-projected workload × real time budget.
- **MCD cards:** right philosophy (one cloze target, rich ambient context),
  weak execution — generated text is a semantic monoculture (nine
  near-identical 瞑想と学習/優秀 sentences), violating encoding variability,
  and wall-of-text reviews cost minutes → the Guide generates *varied*
  micro-contexts across domains, one retrieval target per card; long-form
  multi-highlight text becomes a reading exercise, not an SRS unit.
- **Keep:** operator already runs FSRS in Anki (玉 card intervals 8.7mo/2.4y)
  → warm-start import (§9 Phase 1). Personal-domain decks (Ashtanga special,
  NIHON DHARMA) validate personal domains as first-class spines/tags.

### 10.3 Kanji Garden — reviewed 2026-07-27 from screenshots
- **Keep:** the emotional register — organic growth metaphor ("watered"
  reviews, garden visuals), the anti-sterile counterexample to §10.1; the
  **Forgot?** button as an honesty affordance; the trouble queue
  (就/首/宮/張/盛) as a natural journey-seed feed.
- **Wallpaper generator = the constellation map's ancestor.** By the
  operator's own account, the most visually compelling artifact in their
  entire environment: full kanji inventory colored by knowledge state, ~14
  months of history on a time scrubber, exportable PNG/video. Yet it is
  static, non-interactive, arbitrarily laid out, crudely colored, and leaves
  the app as a file. Bunki's centerpiece is that artifact **alive** (§8):
  tappable nodes, graph-neighborhood layout, live retrievability brightness,
  history scrubber retained.
- **Reject:** multiple-choice recognition as the primary retrieval act (low
  desirable difficulty; inflates grades fed to the scheduler — MC belongs
  early in a drill ladder, never at the top); kanji-only silo with private
  state; unsustainable intake (844 unlocked in 59 days ≈ 14.3/day; 260 due in
  24h) — third tool showing the same over-collection signature, so the
  scheduler must **enforce** sustainable intake, not merely permit binges.

### 10.4 Todaii Japanese — reviewed 2026-07-27 from screenshots
- **Keep:** fresh dated news with synced audio + speed/skip controls (read-
  while-listen suits the operator's listening-forward profile); furigana
  toggle; difficulty awareness; the instinct to embed AI chat inside the
  reading surface.
- **Reject 1 — highlights the language, not the learner:** near-every content
  word underlined in global-JLPT rainbow colors — when everything is
  highlighted nothing is. Bunki inverts: clean text, quiet marks only on
  Trace-unknown/fragile words (personal frontier, not global level).
- **Reject 2 — AI as bolt-on:** "Tomo Chat" explains but remembers, updates,
  and schedules nothing. Same placement in Bunki is the Guide: reads through
  the Trace, logs asked-about words as provenance-carrying encounters, seeds
  journeys, counts un-looked-up reading as weak implicit review.

### 10.5 Synonyms (類義漢字) + Usage (訓) reference pair — reviewed 2026-07-27
- Semantic-field kanji grouping (e.g. "arrange": 並比列陳羅揃整理, per-kanji
  nuance + compounds) is the `contrasts-with` edge set rendered as a static
  book — strongest external validation of the Atlas contrast dimension.
- **Metabolize:** groups become **usage-boundary drill generators**, gated by
  the interference rule (drill discrimination only after ≥2 members are
  individually stable); Guide explains nuance anchored to the group; semantic
  fields add a meaning-neighborhood layout dimension to the constellation.
- Failure mode to avoid: pure reference silo — no learner state, no drills,
  no personal examples. Operator profile note: the collection (synonyms,
  usage 使い分け, Kanken aspiration) marks a **nuance collector** — an
  advanced-learner appetite mainstream apps don't serve; contrast edges +
  boundary drills serve it natively.

### 10.6 Further apps — operator will supply next batches; append here.

**Cross-tool meta-finding (2026-07-27):** at least five systems currently hold
unreconciled shards of the operator's learner state (renzo lists, ~12 Anki
decks, Kanji Garden, Todaii, implicit knowledge in the YouTube diet).
Fragmentation of *state* — five contradictory estimates of "do I know 玉?" —
is the disease Bunki's single Trace cures; every reviewed tool confirms it
from a different angle.

## 11. Operator calibration snapshot (belief ledger seed, 2026-07-27)

Six-item probe, bracketed N3→N1:

| Dimension | Evidence | Band |
|---|---|---|
| Component analysis | decomposed 摩擦 cold (麻 hemp, 扌 hand, 察 via 警察) without knowing the word | strong, N2+ |
| Kanji association | unknown 滞る → reached 滞在 (correct graph edge) | strong |
| Contextual inference | correct meaning guess for 滞る from context | strong (AJATT profile) |
| Written vocab | 摩擦 read not known (N1-band, fine); 貿易 unread (N3-band, NHK-frequent — high-value gap) | solid N3, patchy above |
| Formal grammar | missed につき (chose に対して) and どころか (chose のみならず) — both N2 | N3 ceiling currently |
| Production | comfortable conversational meta-answer in Japanese; 〜ざるを得ない unavailable | fluent-conversational, formal patterns missing |
| Listening | untested; 2h/day fast native talk content implies | likely N2+ |

**Verdict:** listening/inference ≈ N2+; written grammar/formal vocab ≈ N3+.
Modality-split Trace validated on user #1.

**Immersion profile:** ~2h/day now (formerly 6–8h) — optimize for making
limited immersion count double. Rotation: TOLAND VLOG, 中田敦彦のYouTube大学,
ダイゴロー, NHKマイあさ (the formal-register counterweight — exactly where
につき-style grammar lives). Aspiration: upper Kanken.

## 12. Decision log

| # | Decision | Choice |
|---|---|---|
| D1 | Audience | Operator first, product later (architecture product-ready: clean licensing, optional accounts) |
| D2 | Platform | Web-first PWA; agnostic TS core + event-log sync so mobile comes later cheaply |
| D3 | Content sources | All of: own content, AI conversations, open corpora, omnivorous web/YouTube/RSS ingestion (AJATT) |
| D4 | Scheduler | FSRS, deterministic; AI never schedules |
| D5 | Assessment | Evidence-cited belief ledger; modality-split levels |
| D6 | Visual layer | Three strata with honesty split (deterministic strokes / cited etymology / labeled AI mnemonic art with persistent component cast) |
| D7 | Kanji page | Five zones; dictionary indices under the hood only |
| D8 | Ingestion legality | User-initiated fetch, user-local store, never redistribute |

## 13. Open questions (for v2 convergence and beyond)

1. Final name (Bunki is working title).
2. Remaining app reviews to metabolize (Todaii + next batches, incl. which
   screens the operator uses daily vs avoids).
3. Grammar-pattern taxonomy: build order and seed list.
4. Mnemonic-art pipeline specifics: generation model, LoRA vs
   reference-conditioning, cast-sheet bootstrap for ~214 components.
5. Repo/venue for the build: new track in this repo's portfolio vs fresh repo
   built with swarm assistance (governance decision at build-phase entry).
6. Monetization posture (deferred until product phase).
7. Pitch accent & listening drills placement in phasing.
8. Handwriting canvas (Kanken 準1/1) — long-term slot.

## 14. v2 convergence protocol (with second AI collaborator)

The operator ran the same brainstorm with another AI and wants a shared
understanding before build. Protocol:

1. Operator pastes the other AI's spec/notes into the session.
2. Claude produces a **structured diff**: agreements (adopt), conflicts (argue
   with evidence, recommend), novel ideas from either side (evaluate against
   §1 thesis and §4 science commitments).
3. Disagreements resolve by: learning-science evidence > operator preference >
   simplicity. No idea survives on fluency alone (citation-or-silence).
4. Output: `BUNKI_SPEC_V2` superseding this file, marking provenance of each
   major decision (Claude / other AI / synthesis / operator).
