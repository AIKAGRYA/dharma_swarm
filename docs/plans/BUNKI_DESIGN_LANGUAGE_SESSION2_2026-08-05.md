# Bunki — Design Language, Session 2 (2026-08-05)

- **Status:** DRAFT — operator voice-note capture, session 2 of design language.
  Supersedes spec §8 ("Design language") of `BUNKI_WORKING_SPEC_2026-07-27.md`
  where they conflict. An earlier, deeper design session was lost to an
  unrecorded instance; this file exists so that cannot happen again.
- **Source:** operator voice note, transcribed and structured same-day.
- **Context:** Bunki v12 is merged and green on Bunki-app main; operator
  verdict on its current look: "neither here nor there." A full interactive
  design critique of v12 (26-screen Playwright tour vs spec) was delivered
  2026-08-05 in-session; its findings are compatible with, and subordinate
  to, this direction.

## 1. North-star feel

Two worlds deliberately held together:

- **Ground — Nihonga (日本画).** The material world of traditional Japanese
  painting: mineral pigments (岩絵具 iwa-enogu — ground azurite, malachite,
  cinnabar, ochre) on washi; earthy, deep, matte, granular. Hokusai is one
  doorway among many, not the whole style.
- **Energy — Akira × Studio Ghibli.** Ghibli's warmth and hand-made organic
  life; Akira's kinetic precision and night intensity. Ancient pigment
  carrying future voltage — not a museum piece.

## 2. Palette system — toggleable Nihonga themes

Operator instruction: research the actual Nihonga palette and offer a broad
selection of traditional colors to toggle through inside the app.

Pigment identities (sources: Nakagawa Gofun Enogu, Pigment Tokyo; digital hex
equivalents from the 伝統色 databases — NIPPON COLORS (nipponcolors.com, 250
colors with hex/RGB/CMYK) and the standard traditional-colors references):

- 群青 gunjō — azurite deep blue
- 緑青 rokushō — malachite green
- 朱 shu — cinnabar vermilion
- 弁柄 bengara — iron-oxide red-brown
- 黄土 ōdo — yellow ochre
- 胡粉 gofun — crushed-shell white
- 墨 sumi — ink
- ベロ藍 bero-ai — Prussian blue (Hokusai's signature)

Theme grammar: **one washi ground + ink + two pigments + one accent.**
Initial proposed set (hex values indicative, to be finalized against
NIPPON COLORS):

| Theme | Ground | Ink | Pigments | Accent |
|---|---|---|---|---|
| 北斎 Hokusai | 生成り cream #FBFAF5 | 藍墨 | ベロ藍/瑠璃 #1E50A2 · 藍 #165E83 | 朱 #EB6101 |
| 墨 Sumi | white washi | 墨 #595857 | grays only | 朱 (single flame) |
| 岩絵具 Earth | 鳥の子 warm paper | 焦茶 | 黄土 #C39143 · 弁柄 #8F2E14 | 緑青 #47885E |
| 緑青 Forest (Ghibli) | pale moss paper | 千歳緑 | 緑青 #47885E · 群青 #4C6CB3 | 山吹 #F8B500 |
| 夜 Night (Akira) | 鉄黒 #281A14 | 胡粉 text #FFFFFC | 群青 depths #113285 | 猩々緋 #E2041B |

Implementation note: v12 already has an appearance panel with mood toggles
(Paper/Warm/Mist/Night) — replace those generic moods with these pigment
themes; same mechanism, real identities.

## 3. Foundation bar (non-negotiable baseline)

Core dictionary + kanji dictionary + SRS must be **equal to or above** the
reference apps in capability and polish — "triple-A-plus quality, locked in,
as the baseline core" — before/above everything else:

- Reference 1: the Japanese dictionary app the operator named (voice
  transcription unclear — sounded like "ring key"; operator will supply
  screenshots; match the name then).
- Reference 2: the Kodansha kanji app.

Dictionary baseline includes: word lookup, example sentences, practices.

## 4. The structural law — every element is a door

No terminal surfaces. Every click-through opens a dictionary surface:

- word → its kanji → each kanji's component kanji → back out through
  compounds → words → dictionary entries;
- sentence → **particles as first-class clickable objects** → a full
  particle page (Japanese explanation + English explanation + history —
  reference: the specialist who makes dedicated per-particle PDF pages) →
  the particle's connected kanji (e.g. "this particle connects with 48
  kanji", all tappable) → each kanji's page → its compound words → each
  word's dictionary entry.

The dictionary is not a tab; it is the connective tissue the whole app is
made of. This deepens the Atlas (spec §2.1); **particles-as-deep-destinations
is new** — underweighted in every earlier spec.

## 5. Stigmergic tracking

Intuitive free wandering (clicking through by curiosity, following what one
knows or doesn't) leaves trails; trails influence the system.

- **Visual half:** every visit deposits pigment — frequently walked paths
  accumulate paint, a patina on the graph (stigmergy rendered in the Nihonga
  material itself: worn paths on washi). Search/discovery can also surface
  heavily-walked paths earlier.
- **Mechanical half (honesty-preserving):** trail density counts as
  exposure-tier evidence per the convergence evidence-tier rules
  (`BUNKI_CONVERGENCE_ROUND1_2026-07-27.md` A2/C3) — it nominates items for
  the SRS intake queue, raises priority, and schedules confirmation probes;
  it never writes FSRS memory state directly (wandering ≠ recall).
- Lineage note: this is the operator's dharma_swarm StigmergyStore concept
  crossing into Bunki.

## 6. Open items

1. ~~Confirm reference dictionary app name~~ RESOLVED: it is "Japanese" by
   renzo (five-tab Search/Text/Reference/Lists/Study — same app as spec
   §10.1; "ring key" was a voice-transcription artifact). Screenshot rounds
   2–3 still incoming.
2. Kodansha kanji app screenshots — incoming; extract the capability bar.
3. Particle-page reference source (the per-particle PDF specialist) — obtain
   name/examples from operator.
4. Theme toggle scope: global vs per-surface (reading surface may want its
   own theme independent of chrome).
5. Reconcile with the v12 critique's "where to start" list (copy pass,
   de-spreadsheeting, empty states) — those repairs should land *in* this
   language, not before it.

## 7. Reference analysis — "Japanese" (renzo), round 1 screenshots (2026-08-05)

Operator's main daily app. Two surfaces captured; rounds 2–3 incoming.

### 7.1 Opening screen — the silence lesson

White void + search bar + words drifting at varied sizes/gray depths
(事業 弁解 好き 風呂 一致 節約 気難しい 全力 / 続き 浮かぶ 大嫌い 過ぎる
銀行 増える). No onboarding, no greeting, no system voice, no noise.

- **Bar:** Bunki's front door must be this quiet. (Direct inverse of v12's
  Today screen: greeting + philosophy copy + six empty dashboards.)
- **But renzo's words are dead** — random, non-interactive. Operator
  directions: interactive · connected to SRS entries · emergence patterns
  (shapes, rain, "5D interactive universe graph") · or three deepening
  recursive layers of the theme.
- **Proposed synthesis (one idea, not four):** the floating words are the
  SURFACE of the learner's knowledge graph. They are the learner's own
  words — fragile/due items drift nearest and largest, rendered in the
  active Nihonga theme's pigments, patina-weighted by stigmergic trails
  (§5). Every word is a door (§4). The "three deepening versions" become
  zoom strata: (1) ambient drift → (2) pinch: constellation neighborhood →
  (3) pinch: full observatory (the Kanji Garden wallpaper made alive, per
  convergence C4). Rain/shapes are weathers of this one surface. Opening
  screen = ambient SRS = universe graph = living wallpaper: one centerpiece.

### 7.2 Search — the four doors of entry (baseline requirements)

Entry-mode bar observed: keyboard · handwriting · radical picker · SKIP.

1. **Typed** — one field eating kanji/kana/romaji/English, no mode switch.
2. **Handwritten** — draw the kanji you can see but not read; live
   recognition with a candidate strip (operator drew 持; candidates
   持 焚 挺 括 挿 封 村…). Doubles as Kanken writing practice — connects
   to v12's existing trace canvas.
3. **Radical/component picker** — assemble from visible parts, grouped by
   stroke count ("I can see what it's made of").
4. **SKIP code** — shape-based lookup for power users.

Interaction details to preserve: results update incrementally WHILE
drawing; kana readings shown in the single red accent (one color doing
semantic work — readings pop, nothing else is colored); candidate strip
above the canvas; instant, offline-fast.

## 8. The Drift — 墨流し Suminagashi mode (concept v0.1, 2026-08-05)

Second voice note refined §7.1's floating-words direction. Operator's own
framing: not sure of the exact shape, but the qualities are — movement; many
options at once; the mind going very deep and very fast through layers of
the whole dictionary (words, kanji, concepts) in a graphic, visual,
interactive way; intuitive and moving; showing the interconnections. NOT
pinch-zoom — tap-depth. A rapid swipe as instant self-judgment. "Gamified
is not the right word" — fluid, HYPNOTIC. Explicitly its own layer within
the app, distinct from the rock-solid A+++ dictionary/kanji/SRS bones.

**Name:** 墨流し (suminagashi — the traditional art of floating ink on
water, touch-responsive and trance-inducing). The floating words are ink on
the surface; touches disturb and redirect the flow. Direct continuation of
the Nihonga material world (§1–2).

### Interaction grammar v0.1

- **Drift:** the learner's own words (from the Trace) float in the active
  pigment theme; weather variants (slow drift, rain, spiral).
- **One tap:** word unfolds in place — reading + meaning bloom around it;
  flow never breaks.
- **Double tap:** connections ripple out as ink tendrils — component kanji,
  sibling compounds, attached particles, near-synonyms; every rippled node
  is itself tappable (fast deep travel through the dictionary without
  opening a "page"). This is §4's every-element-is-a-door at speed.
- **Triple tap / hold:** commit — open the full solid entry (hand-off to
  the bones).
- **Swipe right / left:** "I've got it" / "I don't." Instant, wordless, no
  confirmation UI, next word flows in.
- **Partial-knowledge move:** on an unfolded word, swiping a LAYER (one
  kanji within it, or the reading, or the meaning) grades that depth
  independently — "know the word, not its second kanji." Maps directly to
  the modality/contract-split memory model (spec §2.2, convergence A1).

### Honesty contract (non-negotiable)

Swipes are self-assessment, not retrieval proof. Per convergence A2/C3:
right-swipe = "claims known" → logs exposure/self-report evidence and
quietly schedules a real retrieval probe; left-swipe = nomination into the
SRS intake queue with raised priority. The Drift feeds the scheduler but
can never write FSRS memory state directly — and no popup ever interrupts
the flow to say so.

### Boundaries

- Own layer/mode; the dictionary, kanji pages, and review sessions remain
  conventional, sturdy, and fast (§3 foundation bar).
- Motion must serve trance, not spectacle: continuous, low-contrast,
  interruption-free; no scores, streaks, or confetti (spec §8 honest-metrics
  stance carries over).
