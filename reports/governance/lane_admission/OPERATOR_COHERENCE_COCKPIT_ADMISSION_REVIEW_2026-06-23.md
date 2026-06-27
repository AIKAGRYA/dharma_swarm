# Operator Coherence Cockpit Admission Review — 2026-06-23

## Verdict

`KEEP_CANDIDATE_NEEDS_EXTRACTION` with recommendation to extract as a dedicated, reviewable branch:

```text
governance/operator-coherence-cockpit-20260623
```

The cockpit is high-value and should become the control-tower read model for multi-agent lane admission, production-readiness review, and future Forge/DGM arena ingestion. It is **not canonical yet** because it currently lives in the dirty candidate checkout:

```text
/Users/dhyana/dharma_swarm
branch: telos-ai-seed-v0-from-sandbox
status: CANDIDATE_HIGH_PRIORITY_NOT_CANONICAL
```

Do **not** raw-merge that checkout. Do **not** union its local active-track state into canonical governance.

## Authority baseline

Canonical authority remains:

```text
origin/main
839fd25f43c76375f49e45012fe8f20a324aa74c
[codex] governance: refresh active track and fitness properties [impact-checked] (#647)
```

Canonical portfolio at that ref:

- active tracks: `7`
- `track_policy.max_active`: `10`
- admitting a new orchestration/arena track would be `8/10`, allowed by cap.

Dirty candidate checkout portfolio is different:

- `/Users/dhyana/dharma_swarm` currently projects local dirty state (`11 active / max 11` in local cockpit runs)
- this is not canonical `origin/main` truth.

## Core thesis folded into plan

John routinely runs 4–10 agents across providers, windows, branches, worktrees, and local/remote contexts. Therefore, “clean workspace” means:

- no invisible work;
- no unclassified work;
- no unpreserved valuable work;
- no unowned work;
- no unreceipted claims;
- no candidate lane silently treated as canonical truth.

The build seam is now:

```text
Operator Coherence Cockpit
→ Agent Lane Admission Packet
→ Production Readiness / Candidate Promotion
→ Orchestration Arena v1
→ Forge/DGM shadow loop
```

Forge/DGM must consume cockpit-visible cards and lane/admission packets, not raw git chaos.

## Candidate cockpit surfaces

Modified in dirty checkout:

- `api/main.py`
- `dashboard/src/app/dashboard/cockpit/page.tsx`

Added/untracked in dirty checkout:

- `api/routers/operator_coherence.py`
- `dharma_swarm/operator_core/operator_coherence_cockpit.py`
- `scripts/runtime/operator_coherence_cockpit.py`
- `dashboard/src/lib/operatorCoherence.ts`
- `dashboard/src/hooks/useOperatorCoherence.ts`
- `dashboard/src/components/operator-coherence/`
- `tests/test_operator_coherence_cockpit.py`
- `reports/governance/operator_coherence_cockpit.json`
- `reports/governance/operator_coherence_cockpit.md`

Additional current V2 planning/design files created in the dirty candidate checkout and therefore also candidate-only:

- `docs/design/COCKPIT_V2_GRAFANA_LONG_RUNNING_GOAL.md`
- `docs/design/COCKPIT_V2_DESKTOP_SOURCE_MANIFEST.md`
- `docs/design/cockpit_v2_desktop_source_manifest.json`
- `reports/governance/cockpit_v2_grafana_execution_receipt.md`
- `dashboard/src/components/operator-coherence/v2/` (work-in-progress; do not treat as extraction-ready until verified)

## Verification already reported by Fugu

Fugu re-ran the claimed cockpit verification in the dirty checkout and reported PASS:

```bash
uv run python -m compileall -q \
  api/routers/operator_coherence.py \
  dharma_swarm/operator_core/operator_coherence_cockpit.py \
  scripts/runtime/operator_coherence_cockpit.py

uv run pytest -q tests/test_operator_coherence_cockpit.py

uv run python scripts/runtime/operator_coherence_cockpit.py \
  --output reports/governance/operator_coherence_cockpit.json \
  --markdown reports/governance/operator_coherence_cockpit.md

python3 -m json.tool reports/governance/operator_coherence_cockpit.json

cd dashboard && npm run lint -- \
  src/lib/operatorCoherence.ts \
  src/components/operator-coherence/CoherenceSections.tsx

cd dashboard && npm run build
```

Result: `PASS`.

Latest reported projection from that run:

- readiness score: `40.8`
- cards: `185`

This verification proves the candidate works locally. It does **not** make it canonical.

## Production-readiness verdicts to surface in cockpit

The cockpit must not render checker-SHIPPABLE as production-closed. It must display the stricter production verdicts:

| Track | Production verdict | Cockpit rendering rule |
|---|---|---|
| `runtime-truth-reconciliation-2026-06` | `CLOSE_READY_WITH_FOLLOWUP` | Candidate closure only after dependency-honest operator rendering and fresh runtime DB receipt snapshot. |
| `runtime-truth-nats-2026-06` | `KEEP_ACTIVE_PROD_HARDENING` | Keep active until live NATS/JetStream ack proof and owned-surface reconciliation exist. |
| `truth-graph-platform-2026-06` | `KEEP_ACTIVE_PROD_HARDENING` | Keep active until fresh NATS/presence proof and dependency-honest `make orient` exist. |
| `composer-holon-spine-longrun-2026-06` | `SPLIT_BEFORE_CLOSE` | Split Build A readiness from standing composer / Holon L4 production proof before closure. |
| `provider-routing-consolidation-2026-06` | `CLOSE_READY_WITH_FOLLOWUP` | Candidate closure only after live-provider canary / egress proof is recorded or explicitly environment-gated. |

## Dependency-honesty correction

Do **not** re-render managed active-track include blocks to “fix” `render_active_track_includes.py --check`.

Settled finding:

- system `python3` without PyYAML: FAIL due fallback parser whitespace-only diff;
- repo `.venv/bin/python`: PASS.

Conclusion: this is not stale governance content. It is a dependency-honesty problem.

Follow-up: governance entrypoints should use the repo venv or fail loud with remediation. Treat this as an engineering follow-up, not a docs drift fix.

## Updated implementation plan

### Phase 1 — Authority and extraction

1. Treat the current cockpit as `CANDIDATE_HIGH_PRIORITY_NOT_CANONICAL`.
2. Preserve the dirty checkout/off-machine before any branch surgery if needed.
3. Create a clean extraction worktree from canonical `origin/main` at `839fd25...`.
4. Create branch `governance/operator-coherence-cockpit-20260623` from that canonical baseline.
5. Copy only the known cockpit surfaces into that branch; do not copy unrelated dirty checkout state.
6. Re-run the full verification suite in the extracted branch.
7. Produce an admission review packet from the extracted branch results.

### Phase 2 — Cockpit as control tower

The cockpit must distinguish these truth layers visibly in UI/report language:

- canonical `origin/main` truth;
- dirty local candidate truth;
- open PR truth;
- worktree truth;
- branch/stash preservation truth;
- live ops / runtime receipt truth;
- production-readiness truth;
- candidate lane truth.

Add cockpit cards/links for:

- production readiness results;
- lane admission packets;
- preservation receipt;
- portfolio truth registry;
- active-track evidence;
- PR/CI uncertainty;
- dirty work radar.

### Phase 3 — Agent Lane Admission Packet

Adopt `docs/governance/schemas/agent_lane_admission_packet.schema.json` as the draft schema.

Promotion path:

```text
parallel work lane
→ cockpit-visible card
→ preserved/off-machine if valuable
→ lane packet
→ production-readiness/admission review
→ ACTIVE_TRACK.yaml admission, fold into existing track, or archive
```

### Phase 4 — Track lifecycle

Do not close tracks only because checker says SHIPPABLE.

Candidate closures:

- `provider-routing-consolidation-2026-06` only with follow-up for live-provider canary / egress.
- `runtime-truth-reconciliation-2026-06` only after dependency honesty and fresh runtime DB receipt.

Keep active:

- `runtime-truth-nats-2026-06`
- `truth-graph-platform-2026-06`

Split before close:

- `composer-holon-spine-longrun-2026-06`

### Phase 5 — DGM / Forge path

Do not build Forge yet as a broad autonomous mutation engine.

First Forge/DGM track should be narrow and falsifiable:

```text
orchestration-arena-v1
```

or:

```text
dgm-fitness-arena-2026-06
```

Definition:

- zero learned weights at first;
- frozen task battery;
- orchestration genome schema;
- receipt capture;
- Council/verifier hook;
- real score: `VerifiedCapabilityDelta × Trust / (cost × latency × fragility)`;
- decorrelated correctness / marginal contribution measured;
- no autonomous mutation until arena receipts are reliable.

## Exact branch/extraction strategy

Recommended commands **after operator approval**:

```bash
# 1. Fetch canonical baseline.
git -C /Users/dhyana/dharma_swarm fetch origin main

# 2. Create isolated extraction worktree from canonical origin/main.
git -C /Users/dhyana/dharma_swarm worktree add \
  /Users/dhyana/worktrees/dharma_swarm_operator_coherence_cockpit_20260623 \
  -b governance/operator-coherence-cockpit-20260623 \
  839fd25f43c76375f49e45012fe8f20a324aa74c

# 3. Copy only the candidate cockpit surfaces from dirty checkout.
rsync -a --relative \
  api/main.py \
  api/routers/operator_coherence.py \
  dharma_swarm/operator_core/operator_coherence_cockpit.py \
  scripts/runtime/operator_coherence_cockpit.py \
  dashboard/src/app/dashboard/cockpit/page.tsx \
  dashboard/src/lib/operatorCoherence.ts \
  dashboard/src/hooks/useOperatorCoherence.ts \
  dashboard/src/components/operator-coherence/ \
  tests/test_operator_coherence_cockpit.py \
  reports/governance/operator_coherence_cockpit.json \
  reports/governance/operator_coherence_cockpit.md \
  /Users/dhyana/worktrees/dharma_swarm_operator_coherence_cockpit_20260623/

# 4. Copy plan/admission docs if approved as part of same PR.
rsync -a --relative \
  docs/governance/schemas/agent_lane_admission_packet.schema.json \
  reports/governance/lane_admission/OPERATOR_COHERENCE_COCKPIT_ADMISSION_REVIEW_2026-06-23.md \
  reports/governance/lane_admission/OPERATOR_COHERENCE_COCKPIT_ADMISSION_REVIEW_2026-06-23.json \
  /Users/dhyana/worktrees/dharma_swarm_operator_coherence_cockpit_20260623/
```

Alternative if `rsync --relative` is unavailable: use `tar` with explicit file list or `git diff -- <paths> > cockpit.patch` plus manual review. Avoid broad `cp -R .`.

## Should cockpit be successor track or runtime-truth extension?

Recommendation: **successor/control-tower track**, not merely a runtime-truth extension.

Rationale:

- It consumes runtime truth but also spans git, branches, worktrees, stashes, PR/CI, lane admission, production-readiness, preservation, design sources, and Forge/DGM admission.
- Runtime truth remains one input owner. The cockpit is the cross-domain read model / control tower.
- Do not open or edit `ACTIVE_TRACK.yaml` yet. If admitted, recommended track identity is:

```text
operator-coherence-control-tower-2026-06
```

Possible `serves`: `substrate-nativeness`.

Initial owned surfaces:

- `api/routers/operator_coherence.py`
- `dharma_swarm/operator_core/operator_coherence_cockpit.py`
- `scripts/runtime/operator_coherence_cockpit.py`
- `dashboard/src/app/dashboard/cockpit/page.tsx`
- `dashboard/src/components/operator-coherence/**`
- `dashboard/src/lib/operatorCoherence.ts`
- `dashboard/src/hooks/useOperatorCoherence.ts`
- `docs/governance/schemas/agent_lane_admission_packet.schema.json`
- `reports/governance/lane_admission/**`

## Files touched by this fold-in

- `reports/governance/lane_admission/OPERATOR_COHERENCE_COCKPIT_ADMISSION_REVIEW_2026-06-23.md`
- `reports/governance/lane_admission/OPERATOR_COHERENCE_COCKPIT_ADMISSION_REVIEW_2026-06-23.json`
- `docs/governance/schemas/agent_lane_admission_packet.schema.json`
- `docs/design/COCKPIT_V2_GRAFANA_LONG_RUNNING_GOAL.md`
- `reports/governance/cockpit_v2_grafana_execution_receipt.md`

No branch extraction, active-track edit, cleanup, PR operation, reset, stash, or destructive command was performed by this fold-in.

## Verification commands for extraction branch

Run from the extracted branch/worktree:

```bash
uv run python -m compileall -q \
  api/routers/operator_coherence.py \
  dharma_swarm/operator_core/operator_coherence_cockpit.py \
  scripts/runtime/operator_coherence_cockpit.py

uv run pytest -q tests/test_operator_coherence_cockpit.py

uv run python scripts/runtime/operator_coherence_cockpit.py \
  --output reports/governance/operator_coherence_cockpit.json \
  --markdown reports/governance/operator_coherence_cockpit.md

python3 -m json.tool reports/governance/operator_coherence_cockpit.json

cd dashboard && npm run lint -- \
  src/lib/operatorCoherence.ts \
  src/components/operator-coherence/CoherenceSections.tsx

cd dashboard && npm run build
```

Additional governance checks before PR:

```bash
make onboard
python3 scripts/governance/check_track_status.py
.venv/bin/python scripts/governance/render_active_track_includes.py --check
```

Do not use system `python3` render-check failure as docs drift evidence unless PyYAML dependency status is also reported.

## Risks / blockers

- Dirty checkout is not canonical; local 11/11 active-track projection differs from canonical 7/10.
- GitHub auth unavailable in several probes; PR/CI truth may remain partial.
- tmux/liveness probes can be stale or unavailable; cockpit must show uncertainty explicitly.
- NATS local proof currently fails in production-readiness packet; do not claim live transport production readiness.
- V2 Grafana UI work under `dashboard/src/components/operator-coherence/v2/` is in-progress and should not be extracted until verified separately.
- Off-machine preservation / GitHub auth / Agni copy may be required before destructive cleanup.

## Operator approval required before proceeding

Explicit approval required for:

- creating extraction worktree/branch;
- copying candidate cockpit files into a clean branch;
- pushing branch or opening PR;
- editing `ACTIVE_TRACK.yaml` to admit a successor track;
- any PR merge/close;
- any destructive cleanup: reset, clean, stash drop, branch deletion, worktree prune;
- any raw union of dirty local active tracks into canonical governance;
- any Forge/DGM autonomous mutation beyond a frozen receipt arena.
