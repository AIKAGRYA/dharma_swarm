# Canonicalization Runbook — Operator Coherence Cockpit Backplane — 2026-06-23

This is the decision-complete runbook for flipping the cockpit backplane from candidate to canonical. Do not run the mutating steps until the operator explicitly approves and off-machine preservation / GitHub auth is available.

## Preconditions

- `gh auth status` succeeds OR operator provides another approved PR path.
- Off-machine preservation exists for `/Users/dhyana/dharma_swarm` and relevant local branches/stashes.
- Operator approves cockpit as the control-tower candidate.
- Operator approves successor track framing: recommended `operator-coherence-control-tower-2026-06`.
- No raw merge of the dirty checkout.

## Phase 1 — Land or review the grading branch

Purpose: canonicalize the track feeds and hardened criteria.

Branch:

```text
origin/claude/tracks-consolidation-grading-nb67lq
```

Expected content:

```text
reports/governance/track_coherence.json
reports/governance/track_coherence.md
reports/governance/track_health.json
reports/governance/track_health.md
reports/governance/track_audits/*
reports/governance/track_signoffs/*
scripts/governance/track_coherence.py
scripts/governance/track_health_grade.py
scripts/governance/check_track_status.py  # file_not_contains + hardened criteria support
docs/governance/TRACK_REVIEW_PROTOCOL.md
Makefile                                  # track-health / track-coherence / governance-all wiring
tests/test_track_coherence.py
tests/test_track_health_grade.py
tests/test_check_track_status.py
```

Verification after landing/review:

```bash
make track-health
make track-coherence
python3 -m json.tool reports/governance/track_coherence.json
python3 -m json.tool reports/governance/track_health.json
```

Acceptance:

- `track_coherence.json` exists on `origin/main`.
- `portfolio.objective_coverage` and `portfolio.overstated` are visible.
- reviewer floor / Opus-family quorum remains enforced.
- old vs new criterion ids are source-labeled or migrated; no UI hardcoding.

## Phase 2 — Extract cockpit into dedicated branch

Recommended branch:

```text
governance/operator-coherence-cockpit-20260623
```

Source checkout:

```text
/Users/dhyana/dharma_swarm  # dirty candidate source only
```

Copy ONLY these surfaces from dirty checkout into a clean branch from current `origin/main`:

```text
api/main.py
api/routers/operator_coherence.py
dharma_swarm/operator_core/operator_coherence_cockpit.py
scripts/runtime/operator_coherence_cockpit.py
dashboard/src/app/dashboard/cockpit/page.tsx
dashboard/src/lib/operatorCoherence.ts
dashboard/src/hooks/useOperatorCoherence.ts
dashboard/src/components/operator-coherence/
tests/test_operator_coherence_cockpit.py
reports/governance/operator_coherence_cockpit.json
reports/governance/operator_coherence_cockpit.md
reports/governance/lane_admission/
reports/governance/prod_readiness/
```

Do NOT copy unrelated Telos/A2A/Holon dirty files.

## Phase 3 — Patch cockpit backplane consumption after grading branch lands

Once `track_coherence.json` is on main, cockpit generator should prefer:

1. `reports/governance/track_coherence.json`
2. `reports/governance/track_health.json`
3. `reports/governance/track_audits/*.audit.json`
4. `reports/governance/active_track_evidence.json`

Required display semantics:

- Top banner: uncovered objectives / objective coverage defect.
- Track rows: `coherence_state` dominant over file shippability.
- Distinct columns: `presence` vs `claim_holds`.
- Loud state: `OVERSTATED` when `file_shippable=true` but `claim_holds=false` / portfolio overstated.
- Umbrella rollups: Runtime Truth Spine, Cybernetic Closure & Routing, Sovereign Holons.
- All non-main feeds badged by canonicality if branch-only.

## Phase 4 — Verification on the extraction branch

Run:

```bash
uv run python -m compileall -q \
  api/routers/operator_coherence.py \
  dharma_swarm/operator_core/operator_coherence_cockpit.py \
  scripts/runtime/operator_coherence_cockpit.py

uv run pytest -q tests/test_operator_coherence_cockpit.py tests/test_track_coherence.py tests/test_track_health_grade.py

uv run python scripts/runtime/operator_coherence_cockpit.py \
  --output reports/governance/operator_coherence_cockpit.json \
  --markdown reports/governance/operator_coherence_cockpit.md

python3 -m json.tool reports/governance/operator_coherence_cockpit.json

cd dashboard && npm run lint -- \
  src/lib/operatorCoherence.ts \
  src/components/operator-coherence/CoherenceSections.tsx

cd dashboard && npm run build
```

Acceptance:

- cockpit generator runs from clean branch.
- `operator_coherence_cockpit.json.track_portfolio` reflects canonical main state, not dirty 11/max11 state.
- UI shows source errors as uncertainty, not pass/fail.
- UI renders backplane-provided canonicality/proof/prod-readiness labels, not derived labels.

## Phase 5 — PR / closeout

Open PR only after verification passes. PR description should link:

```text
reports/governance/lane_admission/INDEX_2026-06-23.md
reports/governance/lane_admission/OBJECTIVE_REQUIREMENTS_TRACE_2026-06-23.md
reports/governance/lane_admission/REQUIREMENTS_EDGE_CASE_AUDIT_2026-06-23.md
reports/governance/lane_admission/TRACK_COHERENCE_UNIFIED_FEED_CONTRACT_2026-06-23.md
reports/governance/prod_readiness/PROD_READINESS_FINAL_CLOSEOUT_2026-06-23.md
```

Do not mark the long-running goal complete until:

- grading feeds are on `origin/main`,
- cockpit extraction PR is merged,
- cockpit generator re-run from a clean canonical worktree,
- generated cockpit JSON proves canonical 7/max10 state or the then-current canonical equivalent,
- all verification commands above pass.
