# External Campaign Preregistration — v1 (instrument + protocol)

**Doc role:** plan / instrument template. **Authority: none** — every grant named
here belongs to the operator. Subordinate to `docs/vision_maps/NORTH_STAR.md`,
`docs/doctrine/OPERATIONAL_DOCTRINE.md`, and the M−1/M3 sequence of the Dharma
Blueprint (constitution candidate v1.0, dual-architect consensus 2026-08-30).

**Why this exists:** the Foundry's receipt schema already carries a
`pre_registration` link (`dharma_swarm/foundry/receipts.py:34-97`) and 39
receipt files on meghadharma carry `externally_confirmed: false` with no
preregistration behind them. This is the document that must exist, frozen and
externally timestamped, BEFORE the next campaign runs — so its result, positive
or negative, is publishable evidence rather than an evidence-shaped artifact.
Discipline adapted from the converged fire spec in
`docs/plans/FIRST_FIRE_DECISION_DOSSIER_2026-08-18.md` §4b (one-shot fuse,
planted-red-then-green, non-empty-evidence receipts, OpenTimestamps anchoring).

---

## 1. Identity (filled in at freeze time; immutable after timestamping)

| Field | Value | Rule |
|---|---|---|
| campaign_id | `ext-YYYYMMDD-<slug>` | one id, one run |
| pinned_release | `<commit sha>` | the single M−1-adjudicated release; every process in the campaign runs from it; receipts embed it |
| target | `<repo/benchmark + version/commit>` | external; the organism cannot edit it; fixed baseline recorded below |
| baseline | `<metric name = value, measured on <date>, command>` | reproduced ≥2 times before freeze; variance recorded |
| executor | `<name + containment contract path>` | the narrowest executor whose contract admits this target (RUDRA v0 admits only trusted first-party repair — it is NOT eligible for third-party targets) |
| acceptance authority | `<external mechanism>` | one of: upstream merge; independent benchmark reproduction by a party outside the dyad; accepted deliverable with counterparty sign-off |
| operator grant | `<dated, single-use>` | per capital-lease pattern: scope, ceiling, expiry, revocation; no re-run without a new grant |

## 2. Frozen criteria (written before the run; the run cannot amend them)

- **Success (`verified_improvement`):** `<metric>` improves by ≥ `<margin>` over
  baseline on the held-out set, reproduced by the acceptance authority. The
  margin and sample size are chosen for statistical power BEFORE the run and
  recorded here with the power calculation.
- **Failure (`measured_negative`):** the cohort completes and no candidate
  clears the margin. This outcome is published with the same prominence as
  success (SATYA: all results published, including misses —
  `dharma_swarm/ginko_brier.py` doctrine).
- **`inconclusive_low_power` / `blocked_with_evidence`:** reuse the forge_lab
  closeout vocabulary verbatim (`dharma_swarm/forge_lab/run_receipts.py:15`).
- **Cost ceiling:** `<USD / tokens / wall-clock>`, enforced by a mechanical
  bound outside any model's judgment (Keel loop invariant).
- **Kill date:** `<date>` — the campaign ends on this date regardless of state.

## 3. Role separation (no self-grading, by construction)

| Role | Owner | May not |
|---|---|---|
| Search | RSI Lab (forge_lab, shadow authority) | grade, confirm, promote |
| Execute | named executor, inside its containment contract | select candidates, score itself |
| Confirm | Foundry blind evaluation, `docker` isolation with captured isolation proof | see candidate provenance labels |
| Publish | Witness (calibration book, wins and misses) | alter any state it reports on |
| Promote | Operator only, via dated grant | be automated |

## 4. Evidence requirements per receipt (closing the gaps found 2026-08-30)

Every candidate receipt MUST bind, or the receipt is invalid:
1. `pinned_release` hash and the exact command line.
2. **Provider reality:** request/response digests (SHA-256 of raw provider
   payloads) and the cost line per call — model *labels* alone are not
   provider proof.
3. **Isolation proof:** container image digest + `docker inspect` network
   config captured at run time — `"isolation_level": "docker_nonet"` as a
   string claim is insufficient.
4. Non-empty artifact hash AND outcome state — an empty diff or skipped
   evaluation can never serialize as a pass (First Fire dossier §4b:
   `evolution.py:2379-2380` precedent).

## 5. Controls (run before the cohort; campaign invalid without them)

- **Planted red:** a known-bad candidate (deliberately broken patch) must be
  REJECTED by the Foundry's evaluation, and its rejection receipt archived.
- **Planted trivial-green:** a no-op candidate must score exactly baseline —
  catching any evaluator that rewards submission itself.
- **Held-out split:** confirmation workloads never seen by the search phase
  (`dharma_swarm/foundry/` held-out discipline).

## 6. Learning closure (declared before the run)

Named consumer of the outcome: `<which file/policy/distribution changes>`.
The campaign is not closed when receipts are written; it is closed when the
outcome demonstrably alters the next search distribution, routing choice, or
budget (`docs/vision_maps/2026-05-07_operating_company_kernel.md:66`). Storing
the result is not learning.

## 7. Timestamping and publication

- This document, once filled, is committed and its SHA-256 anchored via
  OpenTimestamps BEFORE the first candidate runs (git timestamps alone are
  self-asserted — First Fire dossier §1.P2).
- The outcome report (any state) is published through the Witness with the
  same anchoring, within `<N>` days of the kill date.

## 8. Admission consequences (fixed at the second convergence)

- Positive + externally accepted → the Evolution organ becomes admissible to
  canon as proven (ring-three receipt attached).
- Negative but honest → the canon substrate proceeds; Evolution remains an
  absent port; experiments continue in dharma-lab only.
- Any criteria amendment after timestamping, any second run without a new
  grant, or any receipt failing §4 → the campaign is void and is recorded as
  void.
