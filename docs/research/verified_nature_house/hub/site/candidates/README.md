# Design candidates — decorrelated, then judged

This is the project's own thesis applied to its own front end: don't pick one design,
**generate several decorrelated candidates, judge them against fixed criteria, and
aggregate the best.** Each candidate is a *different structural/aesthetic bet*, built
self-contained so they can be compared side by side (and so no single author's blind
spot decides the look). One among many — not the design, *a* design.

## The candidates

| | Bet | Status |
|---|---|---|
| **A** | *The living instrument* — the empty-center constellation as the hero; the field made alive; honesty primitives baked into the UI. | **built (Phase 0)** — `./A/` |
| B | *Editorial-first* — data-journalism / scrollytelling lead; the argument as the spine, viz in service of prose. | open |
| C | *The terminal / instrument* — a dense, precise "Bloomberg-for-nature-verification" register; maximal information density. | open |
| … | other decorrelated bets welcome. | — |

## Judging criteria (fixed, so the contest is fair)

Score each candidate 0–5 on each; the winner may be a *graft* (best hero from one, best
essay reader from another) — aggregation, not just selection.

1. **Credible on sight** — does it earn trust in 3 seconds without a word read?
2. **The UI models honesty** — are sourced/dated/uncertainty-banded numbers and the
   seed-status *native to the design*, not bolted on? (Non-negotiable: a verification
   brand whose UI fakes precision fails automatically.)
3. **The one diagnosis lands** — "diverse competence, correlated errors, no aggregation"
   felt, not just stated.
4. **The empty-center "aha"** — is the seam-as-a-hole a genuine visual idea or decoration?
5. **Distinctive, not eco-cliché** — no leaf-stock, no green gradients; its own register.
6. **Performant + hermetic + accessible** — no external CDNs/fonts in the build path;
   `prefers-reduced-motion` honored; keyboard/contrast sane; loads fast.

## Rules (so candidates stay decorrelated and honest)

- Self-contained under its own folder; **no external network calls / CDNs / fonts.**
- Carries the binding fences: `noindex`, the DRAFT/NOT-PUBLISHED banner, the
  `$0 · seed · independent analysis` footer, sourced figures.
- A candidate is a **scaffold**, not a deployment. The publish gate (`../README.md`)
  still governs.
