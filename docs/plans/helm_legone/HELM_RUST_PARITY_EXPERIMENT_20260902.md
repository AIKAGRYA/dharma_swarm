# Slice H — Rust kernel parity experiment (design only; no Rust is built here)

status: DESIGN_WITH_MEASURED_BASELINES
locus: codex/helm-legtwo-20260902 · Johns-MacBook-Pro · leg-two P6

## Question the experiment answers
Would a Rust terminal kernel measurably improve the Helm seat where it is
actually slow, at parity of behavior — or is the Bun oracle already fast enough
that a rewrite buys risk without felt gain?

## Measured Bun-oracle baselines (P4 receipt, 2026-09-02, offline, M5)
Source: `~/.dharma/campaigns/helm-legtwo-20260902/receipts/P4_report.json`
(authority MEASURED_LOCAL_ONLY, provider turns OFFLINE_STUB — first baseline,
state FAIL against first-guess limits; that failure is signal, not noise).

| metric | value | reading |
|---|---|---|
| boot p95 | 382 ms | warm launcher → live bridge; already fast |
| intent parse p95 | 364 ms | local language → reducer; fast |
| provider turn p95 (stub) | 575 ms | bridge round trip floor, no provider |
| render p95 | 4446 ms | **bimodal: cockpit unfold ≈4s; zen return 148 ms** |
| soak 24 journeys | 1 failure | one 15s stall — reproduce before blaming GC |
| rss peak growth | 31.5 MB | modest |
| rollback | stop✓ start✓ replay probe INVALID | post-restart sessions pane rendered empty projection — verify by hand before treating as regression |

## Implication for H
The hot spot is NOT the terminal kernel's input path (parse 364 ms is UI-frame
work, not language cost) — it is the **cockpit unfold render** (~4 s) and
whatever produced the soak stall. Both live in the Ink render/layout layer.
A Rust kernel only pays off if the unfold cost is kernel-bound, not
layout-algorithm-bound. Therefore:

## Protocol
1. **Attribute the 4 s unfold** first (Bun-side): instrument render spans
   (layout vs write vs bridge-refresh) across 20 unfolds. If ≥70% is layout
   algorithm, a Rust kernel is the wrong lever — optimize the layout, close H
   as NO_PROMOTION for the rewrite.
2. Only if kernel-bound: build a throwaway Rust PTY echo+diff probe (≤1 day,
   not a product) rendering the same cockpit frame set; measure unfold p95 on
   identical frames.
3. **Oracle diff**: replay a recorded journey (P4's soak script) against both;
   frames must byte-match after ANSI normalization — parity before speed talk.
4. Promotion gates (all required): unfold p95 improvement ≥3× on the probe,
   zero oracle diffs, and a maintainability judgment by the operator. Anything
   less → the Bun oracle stays, receipts retained.

## Kill criteria
Layout-bound attribution (step 1) · oracle diff that cannot be normalized away ·
probe exceeding one day of effort. A killed H is a healthy outcome; the seat's
felt speed comes from step-1 optimization either way.
