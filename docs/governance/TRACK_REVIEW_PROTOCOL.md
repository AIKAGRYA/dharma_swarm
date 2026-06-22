# Track Review Protocol — Opus 4.8+ panel

**Operator policy (2026-06-22): track completion reviews are conducted by
high-capability auditors only — Opus 4.8 or higher.** Lower-tier models
(Sonnet, Haiku, pre-4.8 Opus) may be recorded for transparency but **do not
count** toward an attesting quorum. This is a deliberate trade of model-family
decorrelation for reviewer capability; decorrelation now comes from
**independent runs / stances** of floor-meeting auditors.

## Why this exists

The deterministic completion gate (`scripts/governance/check_track_status.py`)
grades by `file_exists` / `file_contains`. Presence ≠ working: a track flips
"SHIPPABLE" when a file contains a string. The review panel is the quality
backstop that catches gamed/proxy/false-green criteria — and a backstop is only
as good as its reviewers, hence the capability floor.

## The mechanism (enforced in code)

`scripts/governance/track_health_grade.py` projects two owners — the file-grade
evidence and the panel sign-offs — and **enforces the floor**:

- `ACCEPTED_GRADER_FAMILIES = {"claude-opus"}` and `MIN_OPUS_VERSION = (4, 8)`
- `meets_capability_floor(model_family, model)` parses the opus version from the
  model id and requires `>= 4.8`; a receipt naming only the family is trusted as
  the current opus. Raise the bar by editing those two constants; approve a
  specific frontier model via `GRADER_ALLOWLIST`.
- A sign-off below the floor is **recorded** (`below_floor`) but never weighted.
- **Quorum = 3 independent floor-meeting reviewers.** Axes aggregated by median;
  attested-SHIPPABLE requires median `wired >= 3 AND proven >= 3` AND a reviewer
  majority verdict of SHIPPABLE. Dissent is reported, not hidden.

So even if a future run uses a weaker model, the grader will refuse to count it —
the policy cannot be bypassed by accident.

## How to run a review

1. **Commission 3 independent Opus 4.8+ reviewers** (separate agent runs; the
   decorrelation is the independence). Each examines all active tracks
   **criterion by criterion** against the actual code/tests and returns, per
   track: the 5-axis grade (`wired/proven/live/world_class/balanced`, 0–4) +
   `verdict`, plus the audit (`audit_opinion` CLEAN/QUALIFIED/ADVERSE/DISCLAIMER,
   `completion_claim_holds`, and any PROXY/GAMED/FALSE `flagged_criteria`).
   The canonical reviewer brief lives in this repo's review history; reuse it
   verbatim so runs stay comparable.
2. **Write each run as receipts:**
   - sign-off → `reports/governance/track_signoffs/<run>.signoff.json`
     (`schema: dharma_track_signoff.v1`, with `model_family` and `model`)
   - audit → `reports/governance/track_audits/<run>.audit.json`
     (`schema: dharma_track_audit.v1`)
   Name runs distinctly (e.g. `opus-run-A/B/C`) — they are independent runs of
   the same tier, not different models.
3. **Aggregate:** `make track-health` (runs `check_track_status.py` then
   `track_health_grade.py`). `ENFORCE=1` fails on an OVERSTATED track.
4. **Consolidate** the audit into a dated `track_audits/TRACK_COMPLETION_AUDIT_<date>.md`
   with the opinion matrix and the union of material findings.

## Quick reference

```bash
make track-health            # presence grade + opus-only quorum grade (advisory)
make track-health ENFORCE=1  # fail if a file-green track is not quorum-attested
```

A track may be closed on the file-grade only when the Opus 4.8+ panel **attests**
it (quorum met, claim holds). A file-green track with no attesting quorum is
PROVISIONAL; a file-green track the panel withholds is OVERSTATED.

## The governance toolchain (4 read-models, one feed)

All are stdlib-only, read-only projections under `scripts/governance/`. None
owns truth; each projects from an existing owner.

| Command | Tool | What it answers | Output |
|---|---|---|---|
| `check_track_status.py` | presence gate | do the declared criteria pass? (now incl. `file_not_contains`) | `active_track_evidence.json` |
| `make track-health` | `track_health_grade.py` | does the Opus-4.8 quorum *attest* the claim? | `track_health.{json,md}` |
| `make criterion-lint` | `criterion_lint.py` | would each criterion, if it passed, actually prove the capability? (gameability) | `criterion_lint.{json,md}` |
| `make track-coherence` | `track_coherence.py` | **one fused per-track + per-umbrella view** of all of the above + spine coverage | `track_coherence.{json,md}` |

For a coherence cockpit, consume **`reports/governance/track_coherence.json`** —
it carries each track's `coherence_state` (CLOSE_READY / OVERSTATED / STALE /
IN_PROGRESS), the umbrella rollup, and the uncovered spine objectives, so the
cockpit doesn't re-join the four upstream feeds. `make track-coherence` refreshes
the whole chain. `criterion-lint` also runs (advisory) inside `make governance-all`.
