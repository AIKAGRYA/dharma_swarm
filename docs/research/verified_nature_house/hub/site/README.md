# The Seam — website scaffold (DRAFT · NOT PUBLISHED)

A self-contained static-site scaffold for the connective hub. **It is not deployed
and must not be deployed yet.** It exists so the artifact is ready the moment the
operator's gates clear — not before.

**Status:** SEED · $0 revenue · no product · no endorsements · not affiliated with any
organization or person named in the content.

## What's here

| File | Role |
|---|---|
| `index.html` | Hand-written landing shell (hero, the one-line diagnosis, the offer, the honesty fences, nav). Committed. |
| `style.css` | Self-contained styling — no external fonts/CDNs, no outward network calls (hermetic). Committed. |
| `build.py` | Stdlib build step. Renders `../01_THE_SEAM.md` → `the-seam.html` and `../THE_HUNDRED.md` → `the-hundred.html` in the site shell. Single source of truth stays the markdown. |
| `the-seam.html`, `the-hundred.html` | **Generated** by `build.py` — git-ignored, not committed (no duplicated content in the repo). |

## Build & preview locally

```bash
cd docs/research/verified_nature_house/hub/site
python3 build.py            # generates the-seam.html + the-hundred.html (names as in source)
python3 build.py --redact   # same, but personal names dropped to affiliation level
python3 -m http.server      # open http://localhost:8000/index.html
```

`build.py` uses the `markdown` package if installed (richer output) and otherwise
falls back to a minimal stdlib renderer. Either way it makes no network calls.

## Hiding the names (the safety valve)

`--redact` drops a curated set of **personal names** (AI-industry / researcher
individuals where a person's name attaches to a critique — e.g. NVIDIA's CEO, the
sustainable-AI and water-footprint researchers, the interpretability leads) down to
**affiliation level**, while keeping the institution and the point. Thinkers and
authors cited for a **named public work** (the Dasgupta Review, Doughnut Economics,
*Braiding Sweetgrass*, "Taking AI Welfare Seriously", etc.) are intentionally **not**
redacted — the named work *is* the legitimate citation and those seams are respectful.
The source markdown stays canonical; redaction only affects the generated HTML.

**Or just keep it local.** The whole hub can stay un-pushed / local-only until the gate
clears — nothing here needs to live on a remote to be useful internally.

**Operator call (2026-06-28):** keeping the source on the current low-visibility repo
is accepted for now; a public **deployment** is not, and is still gated below.

## The publish gate (binding — do NOT deploy until ALL are true)

This site names ~105 real organizations and ~20 real individuals with a critical
"seam" reading of each. Publishing is the one irreversible outward act, behind the
operator's coherence gate (`NORTH_STAR §8`). Before any deploy:

- [ ] **Named-person fairness pass** complete — every named individual's seam line
      re-read as fair analysis, not a straw man; the sharpest org lines
      (e.g. Verra, Gold Standard) reviewed for tone.
- [ ] **Two flagged items verified or hard-hedged** — Robert Long / Eleos affiliation;
      Shrikanth's "five rules" against the primary text.
- [ ] **Contact surface + byline + venue** set by the operator.
- [ ] **Orientation register signed off** — the essay's first-person §1 held at the
      smallest, safest claim (per the inverse-to-world-facing policy in `12`/`README`).
- [ ] **Operator coherence gate** (`NORTH_STAR §8`) crossed.

`<meta name="robots" content="noindex, nofollow">` is set on every page as a
belt-and-suspenders guard against accidental indexing while in draft.

## Deploy (later, once gated)

It's plain static files — any static host works (GitHub Pages, Netlify, a plain
bucket). No build server required beyond `build.py`. The operator chooses the venue
as part of crossing the gate above.
