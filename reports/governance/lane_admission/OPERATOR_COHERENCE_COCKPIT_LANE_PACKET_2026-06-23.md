# Lane Admission Packet — Operator Coherence Cockpit — 2026-06-23

## Status

`CANDIDATE_HIGH_PRIORITY`, not canonical yet.

The Operator Coherence Cockpit is implemented in the dirty local checkout and verified narrowly, but it is not present in the clean reconciliation worktree or canonical `origin/main` as of this packet.

## Location

- Checkout: `/Users/dhyana/dharma_swarm`
- Branch: `telos-ai-seed-v0-from-sandbox`
- HEAD observed: `cd610be3ccef`
- Canonical `origin/main` observed: `839fd25f43c76375f49e45012fe8f20a324aa74c`

## Candidate surfaces

Modified:

- `api/main.py`
- `dashboard/src/app/dashboard/cockpit/page.tsx`

Added/untracked:

- `api/routers/operator_coherence.py`
- `dharma_swarm/operator_core/operator_coherence_cockpit.py`
- `scripts/runtime/operator_coherence_cockpit.py`
- `dashboard/src/lib/operatorCoherence.ts`
- `dashboard/src/hooks/useOperatorCoherence.ts`
- `dashboard/src/components/operator-coherence/`
- `tests/test_operator_coherence_cockpit.py`
- `reports/governance/operator_coherence_cockpit.json`
- `reports/governance/operator_coherence_cockpit.md`

## Verification run by this continuation agent

From `/Users/dhyana/dharma_swarm`:

```text
python3 -m json.tool reports/governance/operator_coherence_cockpit.json
uv run python -m compileall -q api/routers/operator_coherence.py dharma_swarm/operator_core/operator_coherence_cockpit.py scripts/runtime/operator_coherence_cockpit.py
uv run pytest -q tests/test_operator_coherence_cockpit.py
```

Result:

```text
1 passed in 0.54s
```

## Why this lane matters

The operator regularly runs 4–10 agents across multiple windows, branches, worktrees, and providers. Therefore, a “clean workspace” cannot mean no parallel work. It must mean:

- all work is visible,
- all work is classified,
- all valuable work is preserved,
- all promotion decisions are evidence-backed,
- no candidate lane is silently treated as canonical truth.

The cockpit is the natural read-model candidate for this operating style.

## Admission recommendation

Promote this lane before building Forge/DGM, but do so through a review PR or isolated preservation branch — not by raw merging the dirty checkout.

Recommended path:

1. Preserve current dirty checkout/off-machine before branch surgery.
2. Extract cockpit files into a dedicated branch, e.g. `governance/operator-coherence-cockpit-20260623`.
3. Re-run the full claimed verification suite in that branch.
4. Add links from cockpit output to:
   - production-readiness packet,
   - portfolio truth registry,
   - preservation receipt,
   - active-track evidence,
   - lane/admission packets.
5. Decide whether cockpit becomes:
   - an extension of `runtime-truth-reconciliation-2026-06`,
   - a successor control-tower track,
   - or a prerequisite for `orchestration-arena-v1`.

## Open concerns

- GitHub auth/PR state unavailable in several probes, so remote CI truth is uncertain.
- Cockpit currently lives in a dirty multi-lane checkout; extraction is required before canonical admission.
- Its reported full verification included `npm run build`, but this continuation only re-ran narrow Python/JSON/unit verification.
- The cockpit should not become a new authority store; it must remain a read-only projection over owners.

## DGM impact

This is a direct prerequisite for safe Dharma Forge operation. Forge should not ingest raw git chaos. It should ingest cockpit-visible cards and lane/admission packets.
