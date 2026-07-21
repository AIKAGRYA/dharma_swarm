# TELOS Canon Reconciliation — 2026-07-21

**Status:** decision memo — BLOCKED-ON-OPERATOR-DECISION. Merging this document changes no track
state; it records the divergence and stages the candidate.
**Author:** Fable 5 builder lane G, 2026-07-21 (JST).
**Companion:** `docs/governance/proposed_tracks/telos-ai-morning-refinery-2026-07.yaml` (the honest
re-admission candidate) · operator send kit at `~/handoffs/2026-07-21_telos_first_receipt_kit/`.

## The divergence, verified on disk 2026-07-21

| | Local checkout (`~/dharma_swarm`, branch `fix/tool-call-xml-dialect-parser`) | Canon (`origin/main` @ 88458e06f) |
|---|---|---|
| telos track | `telos-ai-morning-refinery-2026-06` ACTIVE in ACTIVE_TRACK.yaml; 6/7 criteria green; failing ONLY `first_external_receipt_exists` | **Absent.** Removed at the 2026-07-07 reconcile; recorded as a PROPOSED-HOLD comment (~line 1504): "CANT-MAKE-REAL. RECOMMEND: design-hold (or close)" — all telos_ai owned surfaces absent from main; only real gate = the external receipt |
| `reports/telos_ai/*` | 4 files present (schema, operator packet, sanitized candidate, prototype receipt; all 2026-06-30) | **Absent** (`git ls-tree origin/main reports/telos_ai/` empty) |
| Revenue-objective lane | telos track | `darshan-publication-2026-07` (operator DECREE, GOLDEN SEAL 2026-07-12) |
| Receipt checker | `check_external_acted_receipt` (10 required fields, 14 forbidden markers, fail-closed) | Same checker present on canon — the gate machinery survives; only the track that used it is gone |

**Consequence:** a perfect first external acted receipt currently has no canon gate to satisfy. It
would go green only on a non-canon branch. The 21-days-unsent sanitized artifact
(`reports/telos_ai/SANITIZED_EXTERNAL_OUTPUT_CANDIDATE_2026-06-30.md`, local only) is consent-ready
external evidence with nowhere canonical to land.

## Option (a) — port the telos track to canon, honestly re-scoped

The staged candidate (`proposed_tracks/telos-ai-morning-refinery-2026-07.yaml`, this PR) accepts the
2026-07-07 hold verdict instead of arguing with it:

- **Drops all six lint-style criteria** the verdict rejected (file_exists / file_contains / the
  markdown-lint "test" that exercised zero product code). Nothing green-theater is ported.
- **One completion criterion only**: `first_external_receipt_exists`, kind `external_acted_receipt`,
  on `reports/telos_ai/FIRST_EXTERNAL_ACTED_RECEIPT.md` — the fail-closed checker already on canon.
- **Prerequisites**: the three 2026-06-30 evidence artifacts land on main via a small port PR (they
  are honest evidence-and-consent documents, not product claims).
- **Product scope stays on design-hold** exactly as the verdict recommends. The claim boundary is one
  sentence: one external human acted on one consented sanitized output, receipted.
- The full proposed ACTIVE_TRACK.yaml entry text is the body of the staged YAML file (id, serves,
  owned_surfaces `reports/telos_ai/**`, claim_boundary, prerequisites, the single criterion,
  non-goals, blocker items). Promotion into ACTIVE_TRACK.yaml is G3: operator-only.

## Option (b) — fold the external-acted gate into darshan-publication-2026-07

Add a second completion criterion to darshan (kind `external_acted_receipt`; receipt under
`reports/darshan/` or a surface grant for `reports/telos_ai/`).

- **Pros:** one revenue lane; no track-count growth; the decree lane gains an external-human-acted
  proof class alongside its publication receipt.
- **Cons:** claim-boundary pollution. Darshan's criteria prove "the publication organ exists and its
  output is receipted"; a TELOS Morning Refinery review receipt proves a different product's privacy
  boundary. The falsifiers are independent — darshan can ship Issue One with zero TELOS action, and
  TELOS can get its receipt with zero articles — so one track would carry two unrelated ways to fail.
  Darshan's own non-goal ("this decree does not lift the outreach lease for anything but the
  Darshan-owned site") means the TELOS send needs its own lease decision under (b) anyway: no lease
  economy is gained, only a blurred boundary.

## Recommendation

**Option (a), narrow re-scope.** Canon's own hold note already named the honest future gate — "the
external receipt" — and (a) implements exactly that and nothing more. (b) is workable but makes the
decree lane carry a second falsifier for a different product; boundary hygiene has been the estate's
hardest-won lesson.

Either way, the send itself is one operator lease decision that serves two threads at once (TELOS
receipt + SAB first-independent-operator contact) — kit with generic and named-recipient email
variants, verbatim artifact copy, and a fail-closed receipt skeleton is staged at
`~/handoffs/2026-07-21_telos_first_receipt_kit/`.

## Operator decisions needed

1. **A-vs-B** (default recommendation: A).
2. **Lift the outreach hold** (standing since 2026-05-27) for the ONE send in the kit.
3. If A: approve the small port PR landing `reports/telos_ai/*` on main, then (optionally, later)
   promote the proposed track by moving its entry into ACTIVE_TRACK.yaml with a fresh verified_at.

Nothing in this PR performs any of the three.
