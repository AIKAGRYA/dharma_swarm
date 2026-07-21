# Darshan Issue One — Assembly Manifest

**Track**: `darshan-publication-2026-07` (GOLDEN SEAL decree 2026-07-12) · **Assembled**: 2026-07-21 late JST · **Assembler**: fable (editor/assembler pass — zero authorship)

## What this is

Issue One exists as eight full, independently-discerned essays written by the
darshan_fable seat 2026-07-12/13. Three have been live on the Darshan site
since 2026-07-13; five sat as "forthcoming" stubs while their finished bodies
waited in the seat's drafts directory. This assembly closes that gap:

- **Site side**: darshan repo PR #1 (`issue-one-20260721` → `main`) fills the
  five stubs with their full bodies. GitHub Pages deploys from `main`, so
  **merging that PR is the publication act** — it is held DRAFT for the
  operator's read.
- **Repo side (here)**: the eight assembled articles under
  `reports/darshan/issue_one/articles/`, this manifest, the honest DRAFT
  receipt, and the fail-closed seal script.

## Canonical order (per ISSUE_ONE_DIRECTION.md, operator 2026-07-13)

| # | Title | Slug | Source draft (seat) | Status |
|---|-------|------|--------------------|--------|
| 1 | The Chamber That Was Not Designed (LEAD) | 2026-07-12-the-chamber | drafts/2026-07-12_the-chamber.md | LIVE since 2026-07-13 |
| 2 | The Silenced No | 2026-07-12-the-silenced-no | drafts/2026-07-12_the_silenced_no.md | LIVE since 2026-07-13 |
| 3 | One Idea Away (The Instrument No. 1) | 2026-07-12-one-idea-away | drafts/2026-07-12_instrument-one-idea-away.md | LIVE since 2026-07-13 |
| 4 | Who Is Buying the Ground Beneath the Panic? | 2026-07-13-whose-temples | drafts/2026-07-12_china-land.md | ASSEMBLED, pending operator read |
| 5 | The Shape of a Silence | 2026-07-13-shape-of-a-silence | drafts/2026-07-12_tibet-silence.md | ASSEMBLED, pending operator read |
| 6 | The Gates Around the Minds | 2026-07-13-gates-around-the-minds | drafts/2026-07-12_gatekeeping.md | ASSEMBLED, pending operator read |
| 7 | Nobody Knows Why, and That Is the Story | 2026-07-13-nobody-knows-why | drafts/2026-07-12_iran.md | ASSEMBLED, pending operator read |
| 8 | The Age of Iron and the Machine That Has No Clock | 2026-07-13-age-of-iron | drafts/2026-07-12_kali-yuga.md | ASSEMBLED, pending operator read |

Seat paths are under `~/.dharma/agents/darshan_fable/`; each piece has a
matching independent discernment file under `discernment/` (verdicts
NEEDS_EDITS or HOLD; each draft's header records the demanded edits as
applied; the iran piece was rebuilt after its HOLD and its own header still
requests re-discernment before external circulation).

## Editorial law compliance (assembly scope)

- **Bodies byte-identical** to the seat drafts — verified programmatically
  (everything after each draft's header block; per-article sha256 in the
  receipt). No prose written, no voice touched, no claims altered.
- **Front-matter only** was authored: title/date/issue/summary/status plus
  `source_draft` and `editor_note` provenance keys.
- **Flagged copyedits** (all in front-matter, none in bodies):
  1. Piece 8 stub summary claimed "every samaya we spend" — the term does not
     appear in the body; summary corrected.
  2. Piece 5 stub summary promised the live Tibet-model probe and the Lobga
     Rangzen anchor — neither is in the body (see open directions); summary
     corrected to describe the actual text.
  3. Piece 4 ships under its draft's own title, not the stub's reframe title
     (see open directions); summary written to match the actual body.
  4. Piece 7 summary lightly adjusted to match body phrasing.

## Open operator directions (2026-07-13), NOT silently resolved

1. **Item 5 — Tibet probe**: the probe was RUN 2026-07-13 (glm-5 /
   deepseek-v3.2 / qwen3-coder; raw at
   `~/mech-interp-latent-lab-phase1/reports/tibet_model_probe_2026-07-13.md`)
   and the Lobga Rangzen anchor verified — but neither is integrated into
   "The Shape of a Silence". Integrating them is authorship and stays with
   the darshan_fable seat or the operator.
2. **Item 4 — temples reframe**: "Whose Temples, Whose Ground" (Chinese
   purchases of Japanese temples/resorts, fist-and-five-fingers, two-class
   system) was never drafted. The existing discerned farmland essay ships
   under its own honest title; the reframe title remains free for the future
   piece.
3. **Items 1–3** (Chamber depth, Silenced No new heart, One Idea Away): those
   three are already live; whether the 2026-07-13 direction is fully absorbed
   in the live versions is an operator/seat judgment, not asserted here.

## PR #965 disposition

The six ~900-word articles in closed dharma_swarm PR #965 are a separate
cursor-agent rewrite (different titles, different voice, ~1/5 the length of
the seat drafts). The operator closed that PR 2026-07-16: preserved in PR
history, revival to be freshly scoped outside One-Door. This assembly is that
fresh scoping — it uses none of PR #965's content and touches only the
track-owned surface `reports/darshan/**`.

## Receipt lifecycle (fail-closed by construction)

- `issue_one_receipt.DRAFT.json` — all six checker-required keys structured,
  `digest: null`, publication facts stated honestly (3 live/verified, 5
  pending). It deliberately does NOT live at the canonical path, so
  `darshan_issue_one_receipt_valid` stays **RED** until publication is real
  (deliberate-RED precedent: #864/#866).
- `scripts/seal_issue_one_receipt.py` — refuses to write the canonical
  receipt unless every article re-hashes to what was assembled, every URL is
  HTTP-200 with the title on the page, and the operator's read is confirmed
  in their own words. Verified 2026-07-21: it correctly REFUSES today
  (unpublished pieces 404); a simulated sealed receipt PASSES
  `scripts/governance/check_track_status.py::check_receipt_valid`
  (6 keys + digest intact) and a tampered one is REJECTED.

## The one operator session

1. Read Issue One — the five assembled pieces on darshan PR #1 (the three
   live ones are a click away).
2. Approve publication — merge darshan PR #1 (Pages deploys from `main`).
3. Convene the merge gate on this dharma_swarm PR.
4. Seal: `python3 reports/darshan/scripts/seal_issue_one_receipt.py
   --operator-read-confirmed "<your words>"` — then commit the sealed
   `issue_one_receipt.json`, and the track's second criterion goes green on
   its own machinery.
