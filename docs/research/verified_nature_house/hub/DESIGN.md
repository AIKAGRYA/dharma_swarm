# The Seam — front-end design (world-class spec)

**Status:** DESIGN · SEED. The blueprint for turning the hub from documents into a
*living instrument*: a public surface that makes the whole nature-verification
industry **alive and visible**, lets us **publish articles and graphics**, draws out
the **"what if these points connected"** vision, and shows the **math that proves it**.
$0 · seed · not deployed; everything here inherits the publish gate in `site/README.md`.

> **The design brief, in one line.** A verification brand has exactly one job its UI
> must do: *model verification honesty in its own pixels.* Every number sourced,
> dated, and shown with its uncertainty; every claim separable from our reading of it;
> the seed-status never hidden. The credibility **is** the product. A beautiful site
> that fakes precision would refute the entire thesis. So: world-class, and ruthlessly
> honest, are the same requirement here — not a trade-off.

---

## 1. The core image — the empty center

One visual idea carries the whole brand: **the seam is a hole.** Every primary view
renders the ~105 actors as a constellation orbiting an **empty center** — the
connective verification layer no one occupies. "Everyone is in the field. No one is in
the seam" becomes literal in pixels. The center is where the Weave (§4) lights up, where
the Proof (§5) resolves, where the offer lives. The negative space is the logo, the
hero, the argument, and the product, all at once. Get this one image right and the rest
follows.

---

## 2. The five surfaces

### THE ATLAS — the industry made alive *(the centerpiece; the "grade-A Grafana")*

A living, explorable map of the field, in two coupled layers:

- **The Constellation.** Force-directed graph: nodes = actors (sized by influence /
  volume / capital), colored by the six clusters (AI-energy · carbon-removal & integrity
  · nature-tech/MRV · restoration & justice · standards & finance · thinkers & AI-ethics).
  Edges = real relationships (funds, rates, supplies, cites, **contradicts**). The field
  visibly orbits the empty center. Click a node → its card (what it does, its blind-spot
  "seam," sources, live metrics). Filter by cluster, by "who-contradicts-whom," by
  "who's-frozen."
- **The Telemetry rail (the Grafana feel).** The vitals that make the field *alive* —
  refreshed on a published cadence, never fake-real-time:
  - **AI's body:** datacenter electricity trend (≈415 TWh 2024 → ≈945 TWh 2030),
    per-query energy as a **band** (the ~10×/~65× contestation, drawn as a band, never a
    point), projected AI MtCO₂.
  - **The trust collapse:** the integrity premium (durable removals priced multiples over
    avoidance), CCP-labeled share (~4% of issuance), the "phantom credit" findings
    (contested-in-magnitude / robust-in-direction), voluntary biodiversity market (~$8M)
    against the ~$700B/yr nature-finance gap.
  - **The disagreement meter:** rater divergence on the *same* projects (one high, two
    low) — the field's incoherence, live.
  - **The frozen-capital gauge:** committed vs delivered (e.g. $1.5B committed,
    ≈0 delivered) — money parked at the verification gate.
  - **THE killer panel — the Seam Index.** The field's own three-condition score:
    *diverse competence* (high) × *error decorrelation* (near zero) × *aggregation*
    (zero) → **collective lift ≈ 0.** One gauge that says: a hundred geniuses, no smarter
    than the best single one. It ties straight to the Proof (§5).

  *Grade-A honesty = every panel carries source, timestamp, and an uncertainty band; a
  "rebuttable" badge on hover; refresh cadence shown ("as of …"). No tick is invented.*

### THE WEAVE — the "what if these connect" engine *(the signature interaction)*

The thing that turns a directory into a vision. Select **2** nodes — or **10**, or
**20** — and watch what emerges when their work is woven *through the empty center.*

- **Interaction:** pick nodes on the Atlas → press **Weave** → threads animate from each
  selected node through the seam, and a synthesis panel resolves: *"Canopy MRV (Pachama)
  + eDNA (NatureMetrics) + community custody (ICCA) + decorrelated aggregation → the
  biodiversity verification that survives the soft factors none of them can see alone."*
  Plus a generated diagram and the math lift (§5) for that specific weave.
- **Curated presets (the article engine):**
  - **The 2-point spark** — energy bottleneck (Jensen's "power-limited industry") + the
    restoration loop → AI's footprint *funds* the repair, verifiably.
  - **The 10-point weave** — a cross-cluster synthesis.
  - **The 20-point vision** — the whole seam woven; the company's thesis in one canvas.
- **Honesty:** curated weaves are backed by the dossier's real analysis. An "weave
  anything" free mode is allowed but **clearly labeled generated/draft**, never shown as
  established fact. (The brand cannot launder a guess as a finding.)

### THE PROOF — the math, made visible *("the math that proves it")*

The decorrelation theorem, interactive — Condorcet (1785), Krogh–Vedelsby (1995),
Breiman (2001): **E_ensemble = E_mean − E_diversity.** The diversity term literally
*subtracts* from error.

- **Three sliders:** number of judges · their individual competence · their error
  correlation. Watch ensemble accuracy climb as errors decorrelate — and **flatline (no
  lift) when errors are correlated.**
- **"Load the real field" button:** sets high competence + high correlation + zero
  aggregation → **lift ≈ 0**, exactly today's field. The abstract theorem becomes
  viscerally, undeniably true, and wired to the Seam Index gauge in the Atlas. This is
  the intellectual climax of the whole site.

### THE ESSAYS — the writing *(The Weave Series)*

Editorial long-form, NYT/Pudding-grade. The repeatable format **is** the Weave: *pick N
points → show the weave → show the proof of lift.*
- **The Weave Series:** "Two points" (energy ↔ restoration), "Ten points," "Twenty
  points (the whole seam)"; plus the standing essays (the metering problem; the free
  second-opinion worked example; reciprocity & sovereignty).
- **Scrollytelling:** the Constellation animates as you scroll the argument; live
  telemetry and Weave/Proof widgets embed *inline* in the prose.
- **Authoring:** write Markdown/MDX, drop in `<Atlas>`, `<Weave ids=…>`, `<Metric src=…>`,
  `<Proof>` components. The hub `.md` stays the canonical source.

### THE HUNDRED + THE OFFER — directory & invitation

The full sourced map (with the **name-redaction toggle** from `build.py --redact` exposed
as a UI switch), and the standing offer: *a free, decorrelated second opinion on one
public claim, with our own footprint printed on the output.* Earned, not decreed.

---

## 3. The design system

- **Mood:** "living system meets scientific instrument." Calm, credible, alive. **Not**
  eco-cliché (no leaf-stock, no green gradients); **not** cold-tech. A refined,
  data-journalism register that earns trust on sight.
- **Palette:** ink (`#1a1f1c`), warm paper (`#fbfcfb`), one living accent (a deep
  leaf-green `#2f6f4e`), a single alert ochre for "contested/rebuttable." Restraint is
  the brand.
- **Type:** an editorial serif for long-form (Spectral / Tiempos register) + a precise
  grotesk for data & UI (Inter / Söhne register). Numbers in a tabular face so bands
  align.
- **Motion:** meaningful and physics-based — the constellation *breathes*; threads
  *weave*; figures count up *with their uncertainty band drawn*, never to false
  precision. Motion that explains, never decorates.
- **Honesty UI primitives (the differentiator):** a `<Sourced>` number (hover → source +
  date + band), a `rebuttable` badge, an `[IND]/[VEN]` provenance chip on every external
  figure, a persistent **"$0 · seed · not a product · independent analysis"** footer, and
  the redaction toggle. *The UI itself models verification.*

---

## 4. "Made alive" without faking it — the data architecture

Grade-A telemetry where the data is honestly *slow* (industry metrics move monthly, not
per-second). So: **static-generated + scheduled refresh,** not fake live ticks.
- **`data/` layer:** each metric a small sourced record — `value`, `as_of`, `p05/p95` or
  range, `source_url`, `[IND]/[VEN]`, `method`. Versioned in git; diffable; auditable.
- **Refresh pipeline:** a scheduled job re-pulls the public sources, opens a PR with the
  diff (so every number change is reviewed, never silently drifting — same discipline as
  the dossier). "Live" means *freshly sourced and dated*, not *streaming*.
- **Optional real Grafana:** for the few genuinely time-series panels (e.g. grid carbon
  intensity via a public API), embed actual Grafana/Observable; for the rest, the custom
  honesty-first panels above. Either way, cadence is always shown.

---

## 5. The graphics / share system *("make graphics, attract people")*

Every node, weave, metric, and proof exports a **beautiful, on-brand, shareable card**
(social OG images + print-ready) from one template engine — so a single weave or a single
"Seam Index = ~0" gauge becomes a graphic that travels. Auto-generated, consistent,
sourced (the card carries the figure's date + provenance, so even the shareable is
honest). This is how the ideas leave the building.

---

## 6. Tech stack & information architecture

- **Stack:** Next.js + React + TypeScript; MDX for essays; Observable Plot / visx / D3
  for custom viz; sigma.js / deck.gl for the constellation; satori/`@vercel/og` for the
  share cards; static-first hosting (Vercel / Netlify / Pages). No external fonts/CDNs in
  the hermetic build path; analytics privacy-respecting.
- **Pages:** `/` (hero — the empty-center constellation + the one-line diagnosis) ·
  `/atlas` (the living field) · `/weave` (the what-if engine) · `/proof` (the theorem) ·
  `/essays` + `/essays/[slug]` · `/the-hundred` (directory + redaction toggle) · `/about`
  (what this is, the fences, the offer).

---

## 7. Phasing (honest, buildable)

- **Phase 0 — the credible MVP (upgrade today's scaffold).** Design system + the hero
  constellation (static positions) + ONE telemetry panel (the Seam Index) + the flagship
  essay rendered in the system. Already looks world-class; ships behind the gate.
- **Phase 1 — the Weave.** Curated presets (2 / 10 / 20) first; the interaction + diagram;
  the share-card export.
- **Phase 2 — the living Atlas + the Proof.** The full sourced `data/` layer + refresh
  pipeline; the interactive theorem wired to the Seam Index.
- **Phase 3 — author tooling + "weave anything."** MDX component authoring; the labeled
  generative weave mode; the full graphics engine.

---

## 8. The fences (non-negotiable — credibility is the product)

- Every published figure: **sourced + dated + uncertainty band**; `[IND]/[VEN]` provenance;
  "rebuttable" where contested. No fake precision, ever.
- The **name-redaction toggle** ships in the UI; the named-person fairness pass must be
  current before deploy.
- Persistent **"$0 · seed · not a product · no endorsements"**; named actors unaffiliated.
- The generative "weave anything" mode is **always labeled draft**; a generated synthesis
  is never rendered as an established finding.
- Deployment stays behind the operator coherence gate + the publish checklist
  (`site/README.md`). The scaffold builds the instrument; the operator decides when it
  faces the world.

*The whole design reduces to one move: build the most beautiful possible instrument that
could not lie about what it knows — because for a verification brand, that instrument is
the argument.*
