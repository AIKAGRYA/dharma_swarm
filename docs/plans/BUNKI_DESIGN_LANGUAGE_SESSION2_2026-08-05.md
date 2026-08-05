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

1. Confirm reference dictionary app name ("ring key" transcription) —
   screenshots incoming from operator.
2. Kodansha kanji app screenshots — incoming; extract the capability bar.
3. Particle-page reference source (the per-particle PDF specialist) — obtain
   name/examples from operator.
4. Theme toggle scope: global vs per-surface (reading surface may want its
   own theme independent of chrome).
5. Reconcile with the v12 critique's "where to start" list (copy pass,
   de-spreadsheeting, empty states) — those repairs should land *in* this
   language, not before it.
