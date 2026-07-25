# Cockpit Consolidation — Finalization & Verification — 2026-06-23

Role: finalizer. This record confirms builds/imports work, verifies the consolidation spec
against the LIVE grading-branch feeds (not prose), corrects field names to real ones, and
checks doctrine adherence. No canonical or destructive mutation performed.

## 1. Build / import verification (PASS)

Run from `/Users/dhyana/dharma_swarm` (cockpit lives in dirty checkout; origin/main has only page.tsx):

```
uv run python -m compileall -q api/routers/operator_coherence.py \
  dharma_swarm/operator_core/operator_coherence_cockpit.py \
  scripts/runtime/operator_coherence_cockpit.py        -> COMPILE_OK
uv run pytest -q tests/test_operator_coherence_cockpit.py -> 1 passed
uv run python scripts/runtime/operator_coherence_cockpit.py --output ... --markdown ... -> exit 0
python3 -m json.tool <generated>                        -> COCKPIT_JSON_VALID
```

(Prior full run also verified dashboard `npm run lint` + `npm run build` PASS.)

## 2. Feeds verified against real bytes (not prose)

Pulled via `git cat-file --batch` from `origin/claude/tracks-consolidation-grading-nb67lq`
(HEAD `ef7565a99`, 7 ahead / 0 behind `origin/main` `839fd25f4`):

| Feed | bytes | canonicality |
|---|---|---|
| `active_track_evidence.json` | 31592 | CANONICAL_ORIGIN_MAIN (also on main) |
| `track_health.json` | 5249 | OPEN_PR_REMOTE (branch only) |
| `track_audits/opus-run-A.audit.json` | 5629 | OPEN_PR_REMOTE (branch only) |
| `track_audits/opus-run-B.audit.json` | 5759 | OPEN_PR_REMOTE (branch only) |
| `track_audits/opus-run-C.audit.json` | 6650 | OPEN_PR_REMOTE (branch only) |

Confirmed canonicality correction stands: only `active_track_evidence.json` is on `origin/main`.

## 3. Ground truth CONFIRMED from track_health.json `portfolio` block (verbatim)

```
track_mean: 46.4
objective_coverage: 0.33
coverage_cap: 84.9
portfolio_score: 46.4
portfolio_grade: F
attested_shippable: [provider-routing-consolidation-2026-06, runtime-truth-reconciliation-2026-06]
overstated: [truth-graph-platform-2026-06]
```

This corroborates the handoff exactly: coverage 0.33, attested-shippable pair, truth-graph OVERSTATED.

## 4. CORRECTION to signal-design field names (use real schema, not invented names)

The earlier spec proposed `{presence_grade, quorum_attestation, claim_holds, coverage_contribution, staleness_ttl, blockers}`.
The LIVE per-track schema in `track_health.json.tracks[]` is:

```
id, serves, file_grade, file_shippable, signoff_count, families, below_floor,
quorum_met, median_axes{wired,proven,live,world_class,balanced}, score, grade,
consensus_verdict, dissent, attested_shippable, notes
```

Authoritative mapping the cockpit MUST use (real field -> cockpit signal):

| Cockpit signal | Real source field |
|---|---|
| presence_grade | `file_grade` + `file_shippable` (and `active_track_evidence.json` presence) |
| quorum_attestation | `quorum_met` + `signoff_count` + `families` |
| claim_holds | `consensus_verdict` vs `file_shippable` (OVERSTATED when file green but verdict not SHIPPABLE) |
| coverage_contribution | `serves` (+ portfolio `objective_coverage`) |
| reviewer_floor_ok | `below_floor` empty + `families ⊆ accepted_grader_families` |
| quality | `score`, `grade`, `median_axes` |

OVERSTATED detection (verified): a track is OVERSTATED when `file_shippable==true` AND it is in
portfolio `overstated[]` (truth-graph). Per-track there is no `overstated` boolean — the portfolio
block is the authority. The cockpit must read OVERSTATED from `portfolio.overstated`, not a per-track field.

## 5. Reviewer floor verified

`track_health.json.rubric.accepted_grader_families == ["claude-opus"]`; 8 `claude-opus` refs; `min_signoffs: 3`.
Per-track `below_floor` lists sign-offs that fail the floor. Cockpit projects `quorum_attestation`
only when `quorum_met==true` and `below_floor==[]`. Consistent with operator-locked Opus-4.8+ policy.

## 6. Axis-count vs file-count is NOT a contradiction (refinement)

`track_health` reports `file_grade` (e.g. reconciliation 11/11) AND a separate quality `score/grade`
(e.g. 66.2 / D). These are different axes, not conflicting counts. The genuine source-labeled
divergence to surface remains: canonical `check_track_status` criterion set vs the grading branch's
hardened/renamed criterion set. Cockpit must label which criterion set any X/Y count came from.

## 7. Doctrine adherence (PASS)

- Projects from owners; the three feeds are owner-generated read-only artifacts. No new truth store.
- Coheres with the 5-file live-status family; does not fork a parallel family.
- Forge/Arena gating preserved: only CANONICAL_ORIGIN_MAIN feeds fitness; branch feeds are candidate.

## 8. No mutation confirmed

origin/main unchanged (`839fd25f4`); ACTIVE_TRACK.yaml untouched by me; only new read-only
governance artifacts written into the reconciliation worktree.

## Verdict

Consolidation spec is VERIFIED and now decision-complete: feeds exist with real content, ground
truth matches the live portfolio block, signal field names corrected to the real schema, build/import
green. Canonicalization remains operator-gated on landing the grading branch and extracting the cockpit.
