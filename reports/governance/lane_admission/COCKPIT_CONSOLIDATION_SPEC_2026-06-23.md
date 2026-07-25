# Cockpit Consolidation Spec — folding the track-grading handoff — 2026-06-23

This is the candidate solution for consolidating the track-grading/audit lane's feeds into the Operator Coherence Cockpit, reconciled against verified git state. It is a projection spec for the UI/backplane lanes; it writes no new truth store and mutates no canonical state.

## CRITICAL canonicality correction (verified, must lead)

The handoff says the feeds/criteria are "on origin". Verified git state says otherwise:

- Grading branch `claude/tracks-consolidation-grading-nb67lq` (HEAD `ef7565a99`) is **7 ahead / 0 behind** `origin/main` (`839fd25f4`).
- Therefore these are on the BRANCH, NOT on canonical `origin/main` yet:
  - `reports/governance/track_health.json` (+ `.md`) — branch only
  - `reports/governance/track_audits/opus-run-{A,B,C}.audit.json` + `TRACK_COMPLETION_AUDIT_2026-06-22.md` — branch only
  - renamed criterion ids in `ACTIVE_TRACK.yaml` — branch only
  - `file_not_contains` predicate in `check_track_status.py` — branch only
  - `scripts/governance/track_health_grade.py`, `tests/test_track_health_grade.py`, `docs/governance/TRACK_REVIEW_PROTOCOL.md`, `make track-health` — branch only
- Only `reports/governance/active_track_evidence.json` exists on BOTH origin/main and the branch.

Implication for the cockpit (per the canonicality taxonomy in this folder):
- `active_track_evidence.json` -> `CANONICAL_ORIGIN_MAIN`
- `track_health.json`, `track_audits/*`, the renamed criteria, the reviewer floor -> `OPEN_PR_REMOTE` / `LOCAL_ONLY_BRANCH` (candidate), NOT canonical.

The cockpit MAY project the grading feeds, but MUST badge them as branch-sourced candidate truth until the grading branch lands on origin/main. Do not present `track_health.json` attestations as canonical while they live only on a feature branch.

## Three feeds (projection contract)

| Feed | Path | canonicality (today) | Projects |
|---|---|---|---|
| presence | `reports/governance/active_track_evidence.json` | CANONICAL_ORIGIN_MAIN | deterministic presence grade per track |
| health | `reports/governance/track_health.json` | OPEN_PR_REMOTE (branch) | 5-axis quality grade + OVERSTATED flag + attestation |
| audit | `reports/governance/track_audits/opus-run-{A,B,C}.audit.json` | OPEN_PR_REMOTE (branch) | audit_opinion + completion_claim_holds + flagged criteria |

## Per-row signal design (cockpit track card extension)

Each track row carries:
```
{ presence_grade, quorum_attestation, claim_holds, coverage_contribution, staleness_ttl, blockers }
```
Loudest flag: `presence == green AND claim_holds == false` => `OVERSTATED`. Render presence-green and panel-withheld as DISTINCT states (file checks cannot catch a hand-authored receipt; the quorum is the backstop).

This maps onto the canonicality taxonomy's two-axis model: `presence_grade` ~ canonicality/static evidence; `claim_holds`/`quorum_attestation` ~ proof_state (LIVE vs STATIC vs CONTRADICTED).

## Ground truth to project (post-hardening; do not re-derive)

- 7 tracks, ALL serve `substrate-nativeness`. `revenue-external-humans-served` = 0, `research-depth` = 0. Objective coverage 0.33. **Surface this monothematic gap at the TOP of the cockpit as the single biggest coherence defect.** (Consistent with my earlier independent `make onboard`: spine coverage GAP on those two objectives.)
- Attested SHIPPABLE (Opus 4.8 panel, claim holds): `runtime-truth-reconciliation`, `provider-routing-consolidation`.
- `truth-graph-platform`: file 15/15 but panel OVERSTATED — only gap is whether the live NATS demo actually ran (receipt hand-authored). Show file-green + panel-withheld as DISTINCT. (Consistent with my prod-readiness verdict KEEP_ACTIVE_PROD_HARDENING.)
- Honestly IN_PROGRESS: `nats` 1/3, `spine-adoption` 6/9 (keystone), `loop-closure` 9/11, `composer-holon` 6/7.

NOTE on a numeric discrepancy worth surfacing, not silently resolving: the grading branch reports finer-grained criteria counts (e.g. nats 1/3, spine-adoption 6/9, composer 6/7) because it HARDENED/added criteria. Canonical origin/main `check_track_status.py` reports nats 2/2, spine-adoption 7/8, composer 6/6, loop-closure 10/11. Both are internally correct for their own criterion sets. The cockpit must label which criterion set a count came from (canonical vs hardened-branch), or it will look contradictory.

## Umbrella rollup (optional 3-row coherence view)

- A `Runtime Truth Spine` = spine-adoption (keystone) + reconciliation + nats + truth-graph
- B `Cybernetic Closure & Routing` = loop-closure + provider-routing
- C `Sovereign Holons` = composer-holon (depends_on spine-adoption)

## Criterion-id remap (repoint if the cockpit pins old ids)

Only relevant once the grading branch lands; on origin/main today the OLD ids are still authoritative.

| Old id (origin/main) | New id (grading branch) |
|---|---|
| `nats_transport_landed` | `nats_contact_module_exists` |
| `*_calls_spine` (agent_runner/orchestrator) | `*_invokes_agent` |
| `loop1_closure_receipt_exists` | `loop1_closure_verdict_closed` |
| (new) | `gate1_*_repo_checkable`, `composer_wake_repo_checkable` |
| (new predicate) | `file_not_contains` in `check_track_status.py` |

Cockpit guidance: detect criterion ids dynamically from whichever feed it reads; do NOT hardcode the old ids. If reading origin/main, expect old ids; if reading the grading branch / post-merge, expect new ids.

## Reviewer-capability floor (operator-locked)

Only Opus 4.8+ sign-offs count, enforced in `scripts/governance/track_health_grade.meets_capability_floor` (branch only today). The cockpit MUST NOT ingest a lower-tier review as authoritative; the grader already refuses it. Project `quorum_attestation` only from grader-accepted sign-offs.

## Doctrine compliance

- Cockpit projects from owners; creates no new truth store/authority.
- Cohere with the existing 5-file live-status family (LIVE_OPS_DASHBOARD.md, ACTIVE_TRACK.yaml, COHERENCE_DELTA.md, ACTIVE_SURFACE_MANIFEST.yaml, BROKEN_REGISTER.md) — do not fork a parallel truth family.
- Run `make track-health` for the live cut (only available on the grading branch today).

## Uncertainties / flags

1. The grading branch is not merged. If the cockpit hard-depends on `track_health.json` / `track_audits/*`, it will have no canonical data until that branch lands. Recommend: cockpit reads them opportunistically and badges them branch-candidate.
2. Criterion-count contradiction (canonical vs hardened) is real and must be labeled by source, not averaged or silently reconciled.
3. `make track-health` and `track_health_grade.py` are branch-only; any cockpit code path calling them must degrade gracefully on origin/main (UNAVAILABLE, not crash).
4. coverage 0.33 is consistent across both my onboard run and the handoff — safe to surface as canonical-level defect.
