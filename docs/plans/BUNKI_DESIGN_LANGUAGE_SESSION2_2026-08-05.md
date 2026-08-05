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
2. ~~Kodansha kanji app screenshots~~ RESOLVED round 2 → §7.3 capability bar.
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

### 7.3 Reference analysis — Kodansha Kanji Learner's Dictionary app, round 2 (2026-08-05)

Reference 2 (open item 2 → RESOLVED). Screens: 川 entry (full anatomy +
grade-explanation popup), 局 entry, radical-44 family index. This is the
kanji-page capability/design bar:

1. **Hero glyph** — huge vermilion calligraphic character dominates; the
   page is a specimen case. Entry number + SKIP quietly beneath.
2. **Core meaning as 1–3 emphatic red words** (▶RIVER; ▶BUREAU ▶LIMITED
   PART), readings directly under. No prose before the point.
3. **Join keys in one compact bordered table** (radical/number, Jōyō grade,
   SKIP, frequency, Ⓚ, Unicode) — AND tappable: tapping a cell yields a
   plain-language explanation ("part of the Education Kanji list, taught
   in grade 1"). Metadata as doors, never inline noise. Solves spec §5's
   "join keys, not curriculum" with an interaction, not just placement.
4. **Compounds grouped by sense** with sense markers (❶❷, ⓐⓑ), each
   compound tagged to its sense (小川=ⓐ, 江戸川=ⓑ; 薬局 under ❶, post
   office under ❷); reading in warm color, tight gloss. The compound list
   teaches the sense structure — the cure for v12's flat UNSEEN-badge wall.
5. **Cross-references as doors even in print:** homophones ⇒entry-number
   (かわ 河 ⇒0298), →Ⓢ/→Ⓤ appendix arrows, SPECIAL READINGS section.
   Kodansha wanted §4's recursion; paper couldn't deliver it; Bunki can.
6. **Radical family index** (radical 44 → 尻 尾 尽 局 尿 届 屈 居 屋 屑
   展…): one component opens its whole kanji family, each row = glyph +
   representative reading + one-word gloss, each row a door. Same anatomy
   the particle pages need for their "connects to N kanji" lists.

**Meta-observation:** both reference apps (renzo, Kodansha) are white
ground + black ink + exactly ONE deep red doing all semantic work. The
operator's daily visual diet already is the ink-and-vermilion language;
the Nihonga theme system (§2) extends it with more pigments. v12's
cream-and-gold is the outlier. Triple confirmation of the palette
direction.

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

### 8.1 Drift v1 field test → v2 direction (2026-08-05, operator on-device)

Operator ran prototype v1 on iPhone. Verdict: "a good start, I like where
it is going" — the tap-depth + swipe grammar survives contact. Three
corrections drive v2:

1. **Palette absent.** v1 shipped only a pale 北斎 and a night toggle. v2
   must carry the actual §2 theme set (北斎 / 墨 / 岩絵具 / 緑青 / 夜) with
   the real pigment hexes, cycling in-app.
2. **Tendrils point off-screen.** When connections ripple out, sibling
   words are often outside the viewport, so lines shoot into the void.
   Law: **connections pull the relatives to you** — on dive, siblings swim
   in from the edges and take orbit around the focus; a tendril may never
   terminate off-screen.
3. **"Flat and clinical."** Words on a static ground is not suminagashi.
   Operator's ask, verbatim in spirit: *fractally zoom in and out of this
   theme* and get "way way more powerful on graphics, effects, feeling,
   immersive quality."

**v2 concept — the fractal dive.** The drift is a surface; every element
is a depth. Tap a word: it unfolds. Tap again: DIVE — the word slides to
center and becomes the sun of its own local universe; its component kanji
detach as orbiting glyphs; sibling words swim in and orbit; brush-stroke
tendrils connect them; everything else recedes (smaller, blurred, dimmed —
atmospheric perspective, not a modal). Tap an orbiting kanji: dive again —
now the KANJI is the sun and every word containing it takes orbit. Word →
kanji → word → kanji, indefinitely: the dictionary as a fractal. Tap open
water to surface one level. Swipes keep their meaning at every depth
(right = bloom into pigment mist; left = sink as heavy ink), and the §8
honesty contract is unchanged.

**Atmosphere requirements (anti-flat):** living suminagashi ground — ink
marbling in the active theme's pigments, slowly advected, disturbed by
touch ripples; words live in parallax depth bands (near = large/sharp,
far = small/soft); tendrils are tapered brush strokes, not hairlines;
grading dissolves are particle pigment, not CSS fades. Trance boundary
still binds: no flash, no score, continuous motion only.

### 8.2 Drift v2 field test → v3 direction (2026-08-05, operator on-device)

v2 verdict: "getting better… I like the 5 themes option… the moving drift
sense and the inter-click ability." Then the ask: level up ~2000x — depth,
nuance, layered texture ("words on old parchment paper"), Hokusai-grade
nihonga contrast, MORE connections and exploratory layers (particles as
doors; kanji branching into other kanji), more gamified — with the hard
ceiling restated: never noisy, cluttered, chaotic. Named vibe:
"ancient Japan meets anime meets outer space meets obsidian graph meets
additive AI study app."

**v3 organizing idea — the surface is ancient paper; depth is outer
space.** At rest you drift over layered parchment (pre-rendered per theme:
tonal mottling, laid fibers, foxing age-spots on light sheets, edge
vignette) with Hokusai contrast: concentrated pigment masses in the lower
field + an undulating wave band, over the mist blobs. Every dive deepens a
veil and *gold-leaf / star flecks emerge through it* — by depth 3 the sheet
has dissolved into cosmos (in 夜 the stars are always out). Surfacing all
the way home draws the visited chain (e.g. 報告 › を › 報 › 土) as a brief
gold constellation that fades — the journey acknowledged, never scored.

**Graph completed — four node kinds, four door types:**
- word → its kanji (inner ring), its particles (circled hiragana stamps,
  accent-colored tendrils — 助詞 as first-class doors, per §4), sibling
  words (outer ring);
- kanji → words that contain it (outer), sibling kanji built from the same
  parts (mid), its own components (inner, e.g. 報 → 土/又);
- component → every kanji built with it (kanji→kanji branching: 習慣 › 習 › 羽);
- particle → every word that travels with it (交渉 › を).
Tendril color encodes door type: pigment-1 words, pigment-2 kanji,
accent particles. At the surface an obsidian-graph whisper: shared-kanji
words within ~200px link with faint node-dot lines while they drift.

**Quiet gamification (allowed set):** 深さ N (deepest dive) joins the
拾った/済み tray; journey constellation on surfacing; permanent ink stains
along the bottom for gathered words (stigmergic trail, §5). Still no
scores, streaks, confetti, or interruptions.

**Craft details locked in v3:** per-word ±1.5° tilt (hand-laid type on the
sheet); ink-bleed text edge; red hanko seal 分 as the brand mark; light
well behind the dive center (the diving eye brings its own lantern);
elliptical orbit rings separated **vertically** when phone width caps the
x-radius (a tendril still may never point off-screen); free-drifting words
carry a gentle mutual repulsion so the surface never piles up.

**Prototype status:** v3 live at the same artifact URL; verified on
simulated iPhone — full recursion chains (報告 › 報 › 土, 習慣 › 習 › 羽,
交渉 › を), pool returns to exactly 22 on surfacing, zero off-screen
orbiters at every level, both swipe grades intact at all depths. JS gotcha
recorded: CJK *radical-block* characters (⻌ etc.) are not valid unquoted
object keys — quote all kanji/kana map keys.

### 8.3 Drift v3.1 field test → v4 directives (2026-08-05, operator on-device)

Six operator directives, verbatim in spirit:

1. **Swipe legibility failure.** Operator had to ASK whether left/right
   differ — the grammar exists (right = know it, left = don't) but the two
   feel identical. v4 law: the word itself must act out the judgment —
   right = blooms up-and-away in pigment; left = turns 朱, falls the full
   height into the ink pool at the bottom. No ambiguity at a glance.
2. **Orbit speed.** Second-tap orbiters "a bit too fast" — all ring speeds
   cut ~3.5x; drift must stay patient at every depth.
3. **RADICALS, explicitly.** Particles are nice but the operator's real
   ask: break kanji down into radicals and keep forking/diverging from
   there. The component ring becomes the RADICAL ring — boxed
   radical-dictionary styling, named, present for every kanji that can
   decompose, and each radical remains a door to every kanji built on it.
4. **Paper still not felt.** "Doesn't have a patient paper feel or any
   real sense of texture." v4 ground gains 簀の目 laid screen-lines +
   chain lines (handmade washi), per-grain dot noise, heavier fiber
   strands, stronger deckle vignette — texture must survive a phone
   screenshot.
5. **Pigment-colored words.** Kanji must not be only-black or only-white:
   per-theme word palettes drawn from nihonga practice — tonal sumi scale
   (濃→淡) in 墨; mineral pigments on warm ground in 岩絵具; 紺紙金泥
   (gold/gofun ink on indigo-dark paper) in 夜; aerial perspective =
   distant words take the palest tones. Study source: the great nihonga
   colorists' restraint — few pigments, layered, never noisy.
6. **Stroke order.** A toggle (placement TBD by operator) that shows each
   kanji handwritten on note paper with proper stroke order and very
   light numbering — v4 embeds real KanjiVG stroke data for the pool's
   kanji + radicals, drawn stroke-by-stroke on a genkouyoushi-style cell.

**v4 shipped (same artifact URL), all six directives implemented:**
swipe judgments act out their meaning (right = pigment bloom up-and-away;
left = word turns 朱, falls the full screen height into the ink pool);
orbit speeds ÷3.5; the component ring is now the RADICAL ring — boxed
radical-dictionary chips (土/羊/⻌ around 達), each a door onward, COMP
map extended (交/成/変); washi ground gains 簀の目 laid lines + chain
lines + per-grain speckle + kozo strands + deeper vignette; per-theme
nihonga word palettes with aerial perspective (北斎 indigo family; 墨
tonal sumi scale 濃→淡; 岩絵具 rust/ochre/malachite; 緑青 greens +
gunjō; 夜 = 紺紙金泥 gofun-white/gold-ink/pale-ultramarine on iron
dark); 筆順 button on every kanji/radical card animates real KanjiVG
strokes (114 characters embedded, ~85KB) on a note-paper cell with
light numbering. Verified on simulated iPhone: 摩擦 › 摩 › 麻 chain,
both swipe grades, stroke animation, clean surfacing to a 22-word pool.
Toggle placement for stroke order = card-level 筆順 button for now;
operator to decide the final home.

**v4.1 — radicals as planets (operator: "radicals are not able to be
seen as their own planet or zoomed in on or separated from the kanji").**
Root cause found on-device: the radical ring orbited so close to the
enlarged center kanji that the chips sat UNDER it — invisible and
un-tappable (the planet swallowed their touches). Fixed: radical ring
pushed out to the clear inner orbit; radicals detach one by one (staggered
fade-out-of-the-glyph); chips render above the planet (a moon transiting);
tendril only draws once a radical is actually visible. And when a radical
takes the center it sheds its chip box entirely — it becomes a bare, large
planet with its own universe (kanji built from it + words carrying it +
its own components), box restored on surfacing. Verified chain:
記憶 › 記 › 言 — 言 centered huge with 記/語 orbiting, 口 detached, 言葉/
方言 in word orbit. Interaction law added to §8.2's list: **an orbit ring
must never sit inside the center body's own bounding box.**

### 8.4 Radical expansion — the Kodansha index inside the Drift
(2026-08-05, operator screenshots: KKLC "Kanji with radical 44/163")

Operator confirms the radical-planet moment ("I do see it now") and names
the missing half: from a radical you must be able to EXPAND to the
complete family — Kodansha shows a full list of every kanji using that
radical (尸 → 尻尼尽尾局尿届屈居屋屑展…), reading + core meaning per
row. "I don't know how you'll do it spatially on the drift but that's
what I meant."

Spatial answer (v4.2): two layers of expansion —
1. **Orbit = a taste.** The radical planet's rings carry a sample of its
   family (pool kanji first, then common jōyō members), every one a door.
2. **Card = the full index.** Tapping the radical planet itself opens the
   Kodansha-style list: 「◯の漢字 · N字」, scrollable rows of glyph +
   reading + core meaning covering the ENTIRE jōyō family — and every row
   is itself a door that dives that kanji as a new planet.

Data: real radkfile radical→kanji index + kanjidic2 readings/meanings
(EDRDG licences), filtered to jōyō, embedded — so decomposition and
family expansion work across the whole jōyō space, not just the 52-word
demo pool. Out-of-pool kanji dive onward via kradfile components; word
orbits and 筆順 sheets stay pool-scoped for now.

### 8.5 v4.2 field test → v5 directives (2026-08-05, operator)

"Getting better. Let's keep going." Seven directives:

1. **Radical index completeness.** The family list must carry the Kangxi
   radical NUMBER (Kodansha: "Kanji with radical 163"), merge variant
   forms under one number (忄/心/⺗ = 61; 氵/水 = 85; ⻌ = 162; ⻏ = 163;
   ⻖ = 170), and list the whole family (drop the ≥3-member threshold).
2. **Both readings.** Every kanji row and kanji card shows ON (katakana)
   and kun (hiragana), not one collapsed reading.
3. **Stroke order must be visible without hunting.** Operator still
   "doesn't see anywhere that shows stroke order written out" — the 筆順
   sheet now renders automatically inside every kanji/radical card,
   animating on open; the button becomes replay.
4. **Swipes must mean something and add up.** Judgments persist
   (localStorage in the prototype): lifetime counts survive reload;
   known words return to the drift faded and settled; unknown words
   return enlarged and haloed (exposure-evidence visuals only — the
   §8 honesty contract still bars direct memory-state writes).
5. **The whole dictionary floats.** 52 demo words → thousands of
   JLPT-tagged words (N5–N1) drifting through the field.
6. **Level slider.** Thin, faint vertical scale on the LEFT edge;
   strengthens under the finger; stops N5→N1 blended with school-grade
   and 漢検 labels (N3 ≈ 小5-6 ≈ 漢検6-5級 etc.). Sliding re-seeds the
   drift — a tide change — so the field speaks that register. Top stop
   自 (custom): in the real app the level is estimated continuously from
   AI conversation/assessment, SRS progression, mock-test results, and
   other deterministic factors; the prototype shows the stop + intent.
7. **More dimensions.** Pinch-out over a word/kanji = dive into it;
   pinch-in anywhere = surface — zoom joins the tap grammar. More
   connections: faint second-degree links between orbiters that share
   components.

### 8.6 v5 field test → v6 directives (2026-08-05, operator voice note)

1. **Consistency law: every element opens, everywhere.** Operator noticed
   not all words expand into their kanji, and radicals aren't clickable
   everywhere. Root cause: v5's dictionary words only got kanji rings
   when their kanji happened to be in the 52-word seed gloss table (K) —
   the ring filter must accept ANY CJK ideograph, with glosses from the
   full jōyō table. Law: word → kanji → radical → kanji → word, with no
   dead ends, across all 6,687 words.
2. **Fluid dynamics — "super super super important."** The drift plane
   becomes a real fluid: drag a finger and everything moves against it —
   currents, wakes, weaving. Research done: browser bleeding edge is
   WebGPU MLS-MPM (matsuoka-601 WebGPU-Ocean / WaterBall, ~100k–300k
   particles real-time); the foundational interactive technique is Jos
   Stam's stable fluids (real-time Navier-Stokes, GDC 2003) that powers
   the canonical WebGL fluid demos. v6 implements a true Stam solver on
   a coarse CPU grid (damping → pressure projection for vortices →
   semi-Lagrangian advection) — same physics, phone-safe, CSP-safe —
   coupling free words (strong), orbiters (subtle), ink blobs (medium),
   plus visible "flow motes" riding the currents. WebGPU MLS-MPM is the
   named real-app tier.
3. **Hofstadterian strange loop.** Depth is unbounded (500 layers if you
   like); when a dive chain revisits a label already in the journey
   (言葉 › 言 › 語 › 言 …), the breadcrumb earns an ∞ mark and a gold
   ripple — the Escher moment acknowledged, never interrupted.

### 8.7 v6 field test → v7 directive: the vault-field (2026-08-05)

Operator scores the work so far 50/100 and names the gap: "an interactive
obsidian vault type of field — navigate in and out, rotate, see whole
clusters, zoom in and out of galaxies, see grouping and connection and
depth, all in a 5D interactive environment." Standing order: self-iterate
— engage, take notes, rewrite, polish, verify, repeat until convinced.

**v7 architecture — from pond to universe:**
- **World space + camera.** Words live on a world plane ~3.2 viewports
  square; a camera (pan / continuous pinch-zoom / two-finger rotate,
  positions rotate but glyphs stay upright) navigates it. One-finger drag
  on open water pans AND stirs the fluid — swimming through the field.
- **Galaxies.** The most word-productive kanji become hubs, laid out on a
  phyllotaxis spiral; every word anchors near its hubs (multi-hub words
  sit between them as bridges); hub kanji render as large faint suns.
- **The whole dictionary, always.** All 6,687 words exist in-world:
  the ~64 most relevant nearby (unknown > fragile > level-match) are
  full DOM words; the rest draw as canvas points with word→hub edge
  lines — the Obsidian graph made of ink.
- **Zoom-through-to-dive.** Pinching past max zoom over a word pushes
  THROUGH it into its dive universe — continuous zoom and the fractal
  dive become one gesture. Level slider re-weights brightness/priority
  instead of respawning.

### 8.12 v10 shipped — the verified Obsidian lock (2026-08-05)

Five-agent verification panel ran against the build before publish:
- Mechanics 5/6 → pin-dim defect found (pins lacked hlDom) → FIXED.
- Grammar regression 8/8 (unfold/dive/no-self-orbit/sibling-floor-5/
  cards+strokes/surfacing/swipes/pinch-travel), zero pageerrors.
- Chain navigation 5/5 (word→word→word, word→kanji with radical pins
  耳・又 from 取, tap preserves lock, dive+surface clean, camera pulled
  edge-word 280px to center) → insight: canvas members untouchable →
  FIXED (touch materializes them into real words).
- Chaos: ~600 gestures + 3 seeded fuzz runs + storage poison + 200°
  twists: zero crashes/dups/desyncs/orphans; ONE real defect — fps
  collapse at min zoom (7.8fps, software rendering) → FIXED via dot
  batching+thinning, cached hub-glyph sprites, and half-resolution
  linework at far zoom (relative cliff halved; SwiftShader floor now
  ~23fps at extreme zoom-out vs 30-61 baseline variance; GPU devices
  expected 60). Tap-bloom now decays after 12s idle (panel note).
- Consistency floor 16/17 → root cause of the one failure (壷): all-
  fallback members drew arms past the viewport → FIXED with a viewport
  containment force in the lock simulation; 壷 now 12/12 observable
  including the previously-lost 限定. Slider narrowed (38→26px) so it
  cannot swallow word presses.

The semantic tier is LIVE in the lock: SEM pilot (27 words + 5 new N1
lexicon entries) feeds shells first — verified 過酷 assembles 16 members
(苛酷・酷使・酷暑 family / 厳しい・劣悪・熾烈 synonyms / 試練・逆境・
極限 themes / 過酷な労働・環境・運命 collocations as gold ghosts) with
typed edge colors; mechanical channels top up everything else to the
floor. `window.__lockWord(word)` added as the search-to-lock API seam.

### 8.11 The semantic tier — LLM as the relation engine (2026-08-05)

Operator asked me for 過酷's top-20 constellation, then asked why. The
answer became the directive: the relationality the Drift keeps missing
(厳しい as register-adjacent synonym, 試練/逆境 as host themes, 過労死 as
collocational endpoint) lives in the LANGUAGE MODEL, not in character
data — kanji-overlap can never surface 試練 for 過酷 (zero shared ink).
Operator: integrate this as the edge, research + brainstorm included.

**Research grounding (2025 frontier):** CEFR-Annotated WordNet
(arXiv:2510.18466) — LLM-annotated proficiency-graded semantic network,
110k word instances — and DIY-MKG (arXiv:2507.01872) — LLM-built personal
knowledge-graph language learning. Bunki's thesis (LLM-authored,
level-aware semantic web rendered as a living nihonga universe) sits
exactly on this line, ahead of both on embodiment.

**Pipeline (real app):** one batch LLM pass over the full lexicon →
per word: typed relations [synonym | kanji-family | collocation | theme |
register-twin | contrast] each with shell rank + one-line use-note,
merged with JMdict senses + Tatoeba sentences + embeddings (UMAP of
embedding space becomes the GALAXY LAYOUT — semantic geography where
near-in-meaning IS near-in-space, replacing hash placement).

**Methodology brainstorm (mine, as instructed — each maps to a §8 organ):**
1. Semantic-gradient bridges: LLM precomputes shortest meaning-paths
   between any two words (寒い→涼しい→冷たい→冷酷→過酷); the Drift can
   draw a walkable path across galaxies — the "two words decorrelated"
   navigation.
2. i+1 tide (自 mode): field composition targeting ~95% known /
   5% frontier vocabulary from SRS state — comprehensible-input dosing as
   a TIDE, not a lesson.
3. Elaborative whisper: each lock carries one LLM-written line of WHY
   these belong together (JP+EN) — elaborative encoding at the moment of
   curiosity.
4. Generation-effect probes: bloom members reveal reading first, gloss on
   demand — retrieval attempt before answer, feeding the honesty
   contract's probe queue.
5. Register twins as a visible axis (話す/しゃべる/語る) — formality as
   geometry.
6. Story threads: micro-narratives binding 8–10 due words into one
   coherent paragraph — the sentence layer (§8.8) born from the SRS deck.
7. Error-driven mnemonics: repeated left-swipes trigger an LLM keyword
   mnemonic + component story on that word's card.
8. Contrastive discrimination: near-synonym forks as micro-choices
   (過酷/残酷/冷酷 — which fits 労働?) — desirable difficulty.

**Pilot (this prototype, hand-authored by me):** SEM table for ~27
flagship words (+5 missing N1 entries added to the lexicon: 過酷 試練
逆境 熾烈 劣悪) with typed, ordered relations incl. out-of-lexicon GHOST
satellites (rendered gold, labeled, force-simulated — the semantic web
visibly exceeding the dictionary). Lock consumes SEM first, mechanical
channels top up to the ≥12 floor. Typed edge colors: synonym=pigment-1,
family=pigment-2, collocation=accent, theme/ghost=gold.

### 8.10 v10 — the Obsidian lock (2026-08-05, operator escalation;
self-authored contract at operator request)

Operator: still not Obsidian; too drawn out; fix in one shot with
subagents. Contract (self-authored prompt, verbatim):

- Gesture grammar: tap = furigana+gloss · double-tap = planet dive ·
  LONG-PRESS (~430ms) = constellation lock: the viewed universe
  reorganizes around the pressed word — all relations pulled into view in
  shells (1: strong = shares 2+ kanji, plus its own kanji glyphs and
  radicals; 2: family = shares a kanji; 3: loose = radical-kin +
  same-register), camera glides to center it, arrangement STAYS after
  release. Long-press any member (word or kanji) re-orients around it —
  chainable. Tap water releases.
- CONSISTENCY FLOOR: every word, no exceptions, yields >=12 members via
  cascading channels (shared-kanji -> radical-kin -> same-register).
  Dive satellites get a >=4 sibling floor through the same cascade.
- Verification: parallel subagent panel (long-press mechanics; chain
  navigation; 30-word consistency sample; tap/dive grammar regression;
  perf/idle/slider regression; adversarial free-play) before publish.
- Honest scope: true synonyms/conceptual similarity need JMdict senses /
  embeddings (real-app data tier, §8.8); prototype "loose" = radical-kin
  and register neighbors, labeled as such here.

### 8.9 v9 — tap-bloom + the self-satellite diagnosis (2026-08-05)

Operator re-stated §8.8 with force: (a) the HOME field must carry obvious
relationality — "a light tap on one word will bring up at least ten"
connected words/compounds, Obsidian-vault local-graph semantics (research
confirmed: hover a node → its connections highlight, rest dims; local
graph assembles connected notes at chosen depth); (b) duplicates STILL
present — "almost every word" orbits its own copy.

**Duplicate diagnosis (empirical, 8 scripted dives):** word-node dedupe
from v8 was correct — the real duplicate was SEMANTIC: single-kanji words
(謎, 生, 崖 — abundant since the v5 dictionary) spawned their own kanji
as a satellite glyph: 謎 orbiting 謎. The word-dive was designed when all
pool words had 2+ kanji. Fix: a single-kanji word IS its kanji — its
inner ring is now its RADICALS (謎 → 言口米), never itself. Law: **no
node may ever orbit its own name.**

**Tap-bloom shipped (same artifact URL):** a light tap on any word (first
tap, surface level) now assembles up to 14 shared-kanji relatives around
it in a loose ring — they physically swim in from wherever they drift,
get bright dots + canvas labels + direct ink edges to the tapped word —
while every other dot, edge, mesh line, and DOM word dims to ~40%.
Tap water: the family swims home (eased return, wander resumes). Second
tap still dives; grading the focus clears the bloom. Verified: light tap
on 取り上げる assembled 取り出す/取り付け/見上げる/立ち上がる/お手上げ/
引き上げる/取引/上位/上手 with depth untouched; dive of 謎 shows
radicals 言口米, zero self-glyphs.

### 8.8 v8 — the web of life (2026-08-05, operator voice note, redrafted
as directive at operator request)

**Redrafted operator prompt:** (1) Zooming IN must NEVER auto-open a
word — kill the reflex; only deliberate taps open. (2) A center word must
never orbit a copy of itself. (3) Left alone, the universe keeps moving —
every word in frame drifts perpetually. (4) Constellationality must exist
AT REST: families, shared-kanji relatives, compounds visible as webbing in
the field itself; the level slider must VISIBLY change the register of the
sky; the destination is sentence-depth — words + particles conjoining into
real example sentences/paragraphs 3–4 levels down — the whole field
navigable like the language model's own vector space rendered as a
Japanese universe.

**v8 shipped (same artifact URL):** zoom-through-dive REMOVED entirely
(zoom is pure travel; taps open — verified: 3 consecutive aggressive
zoom-ins leave depth empty); duplicate-satellite bug fixed (dive sibling
scan excludes the center word and dedupes — verified 1 visible copy);
perpetual drift (per-word wander velocities integrated each frame, no
trig, + a gentle ambient fluid impulse every 3.6s — verified 26px of
motion in 2.2s of pure idle at 62fps); constellation mesh at rest
(shared-non-hub-kanji chains, up to 9,000 precomputed edges, batched
single-stroke, viewport-culled) + level register made LOUD (match dots
bigger/brighter, off-register dots near-invisible, tide responds in
300ms — N1 slide visibly fills the sky with 目論見/賑わす/素っ気無い).

**Data-tier roadmap for full §8.8(4)** (real app, not prototype-fakeable):
JMdict sense groups → synonym families; Tanaka/Tatoeba corpus → example
sentences and the particle-conjoining sentence layer; frequency-ranked
compound lists per kanji. The prototype now shows the SHAPE of the web;
these corpora give it flesh.

**v7.1 — exploration must never collapse (operator: "the fluid was NOT
WORKING… a word we touch pops up as the center and collapses the
depth").** Root cause: zoom-through-to-dive triggered on ABSOLUTE zoom —
a pinch-out starting with fingers close multiplies zoom 2–3x in one
gesture and blasted past the threshold, force-diving the nearest word on
nearly every exploratory pinch. Law: navigation gestures may never cost
the traveler their altitude. Fix: dive-through now requires the pinch to
BEGIN already pressed close (start z >= 2.0) and push past the raised
ceiling (2.55; max zoom 2.6), with a tighter 110px target radius; the
camera stays at close range after the dive instead of resetting. Verified:
the previously-collapsing gesture now purely zooms; a deliberate second
press dives (文房具); taps remain the primary way to open a word.

**v7 shipped (same artifact URL) — iterated to 60fps.** World plane 3.2
viewports square; 42 kanji-hub suns on a phyllotaxis spiral; every one of
the 6,687 words anchored near its hubs (multi-hub words bridge between);
camera pans (one finger on water — which also stirs the fluid), pinch
zooms continuously about the midpoint (0.34–2.35×), twist rotates
(positions rotate, glyphs stay upright); pinching past 2.25× over a word
zooms THROUGH into its dive universe; hub suns are tappable doors; ~64
highest-priority words (unknown > fragile > level-match) are DOM, the
rest render as ink dots + word→hub edges — the Obsidian vault as
constellation map. Self-iteration log: r1 camera edge-clamp + sun/edge
tuning; r2 gesture telemetry (probe error, camera correct); r3 fps 26 at
galaxy zoom → dots as rects (40) → edge batching (42) → sprite-cached
blobs + stain patina layer (40) → PROFILED per-subsystem: drawWorld was
the entire cost — per-call cos/sin + object allocation in the 6.7k-word
hot loop; hoisted transform + precomputed hub screens → **61fps stirred
at full galaxy zoom**. Stains now accumulate on a permanent patina canvas
(deeper stigmergy, cheaper frames).

**v6 shipped (same artifact URL).** (1) Universal expandability: the
kanji-ring filter now accepts any CJK ideograph with jōyō glosses —
verified on dictionary word 磁気 (N1): 2 kanji glyphs, 磁 → 3 radicals;
no dead ends. (2) The water is real: Stam stable-fluids on a 26×44 CPU
grid — inject (finger drag + tap bursts), damp, 6-iteration pressure
projection (true vortices), semi-Lagrangian advection — coupling free
words (strong), orbiters (subtle), pigment blobs (medium), plus 44 flow
motes that draw the currents as living streaks. Measured 60fps on the
simulated phone after vigorous stirring. (3) Strange loop: a dive chain
that revisits a label earns ∞ in the breadcrumb + a gold ripple; depth
unbounded. Real-app tier named: WebGPU MLS-MPM (matsuoka-601
WebGPU-Ocean/WaterBall class) for full-particle suminagashi. All seven §8.5
directives: (1) radical cards carry Kangxi numbers (部首 61 etc.),
variant forms merged under their number (忄=心=⺗→61; 阝 shows 163·170),
threshold dropped to 2 → 592 families; (2) ON (katakana) + kun readings
on every family row and kanji card; (3) 筆順 sheet auto-writes itself the
moment any kanji/radical card opens — button is now replay (もう一度);
(4) swipes persist via localStorage: lifetime 拾った/済み survive
reload, right-swipe redeems an unknown mark, unknown words return
fragile+haloed, twice-known words return settled at 55% presence;
(5) the dictionary drifts: 6,687 JLPT-tagged words (open-anki-jlpt-decks,
N5:553 N4:535 N3:1836 N2:1489 N1:2274) unified with the seed pool;
(6) level slider on the left edge — faint until touched, stops
自/N1/N2/N3/N4/N5 with school-grade + 漢検 blend labels, commit triggers
a tide change (field re-seeds ~70% target level); 自 stop states the
adaptive intent; (7) pinch-out over a body dives it, pinch-in surfaces,
and orbiters sharing a kanji now link with second-degree whisper lines.
Verified: N1 tide brings 採掘/判決/崖; dictionary word 判決 dives to 決
with auto-strokes + ケツ/き.める; pinch-in surfaced; store JSON survives
reload. Honest scope: particles remain seed-pool only; 筆順 covers the
114 embedded characters; Kanken values are label-blends, not per-word
data.

**v4.2 shipped (same artifact URL).** Source pivot: edrdg.org is
proxy-blocked, so the family index is built from KanjiVG's own
`kvg:element` component annotations (same dataset as our stroke order —
self-consistent) over all 2,136 jōyō kanji, + kanji.json
readings/meanings: 457 radical families (言 70字, 氵 122字, 尸 43字
matching the operator's Kodansha screenshot, 阝 46字 merged from the
⻏/⻖ variant forms). Verified chain: 感情 › 情 › 忄 → card 「この部首の
漢字 · 31字」 scrollable rows (忙 ボウ Busy / 快 カイ Cheerful …) → tap
恨 → out-of-pool kanji becomes a depth-4 planet with its own radicals
(忄心艮) detached. Fix ridden along: tapping the card's own paper now
closes it (before, an open card silently swallowed water-taps). File is
~300KB all-in (stroke + family data embedded). Radical orbit shows an
8-body family sample; the card holds the complete index.

**v3.1 — the dive is a true magnification (operator-picked).** Offered two
zoom grammars: re-orbit (the old layer steps back small, looking down
through water) vs. literal magnification (a forward dolly — the layer you
leave GROWS ×2, blurs, and rushes past the screen edges as you pass
through it; a zoom shock-ripple disturbs the ink; surfacing reverses the
dolly, the old layer flying back in from beyond the frame while the
abandoned universe falls away beneath). Operator chose magnification.
Interaction law learned on-device: anything receded, dying, or graded must
become **tap-transparent** (pointer-events none) the moment it fades —
scaled-up ghosts otherwise swallow water-taps invisibly.
