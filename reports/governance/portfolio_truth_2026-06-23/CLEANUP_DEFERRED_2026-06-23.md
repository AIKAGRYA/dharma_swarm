# Cleanup Deferred — Preservation-First Policy (2026-06-23)

## Status

This is a deferral ledger, not a cleanup plan. The system has useful messy work. The right move is classification, preservation, and promotion proposals before any archive-after-preserve action.

## No-touch zones

Do not mutate these during reconciliation:

- `.dharma/lancedb` — 243G storage object.
- `.dharma/vectors.db` — ~49G storage object.
- `.dharma/conversation_log` — 31G corpus/storage object.
- `.dharma/preservation/dgm_reconciliation_20260622` — local preservation packet.
- Existing stashes and preservation refs.
- Dirty candidate checkout until extraction strategy is approved.
- `ACTIVE_TRACK.yaml` for raw union of local candidate truth.

## Deferred ref/worktree/stash categories

| Category | Count / examples | Deferred action |
|---|---:|---|
| Stale duplicate branches | 62 | Archive-after-preserve after off-machine preservation + operator approval. |
| Already-on-main branches | 21 | Keep as historical refs unless operator asks for ref hygiene; archive-after-preserve after off-machine preservation + operator approval. |
| Orphaned upstream-gone branches | 38 | Inspect high-signal items first; low-signal items only archive-after-preserve after off-machine preservation + operator approval. |
| Stashes | 70 | Index and classify; no stash operation during this phase. |
| Dirty worktrees | `telos`, CashClaw, NATS preflight, Helm, organ seat | Preserve first, then extract narrow slices. |
| Empty sibling dirs | 3 observed | Treat as wrappers; value likely lives in stashes/PRs; archive-after-preserve after off-machine preservation + operator approval if confirmed empty. |

## Storage policy required

The `.dharma` root is 344G but volume capacity is not an immediate emergency. Do not run storage compaction as part of project reconciliation.

Required storage policy outputs:

1. Storage inventory receipt using metadata only.
2. Off-machine copy policy for lancedb/vectors/conversation logs.
3. Retention labels: hot, warm, cold, preserved, unknown.
4. Operator approval gate before any archive-after-preserve treatment.
5. Cockpit cards for storage risk age, size, and preservation status.

## Dirty/Stash uncertainty

Dirty+Stash Miner final output was not available. Current partial clusters:

- Cockpit/backplane: `api/routers/operator_coherence.py`, `dashboard/src/components/operator-coherence/`, `dashboard/src/lib/operatorCoherence.ts`, cockpit reports/artifacts.
- Runtime truth: runtime closeout, burn-in, clean epoch, task backlog firebreak, runtime context tests.
- A2A/NATS: A2A cloud contact, inbox bridge fleet launchd scripts, A2A reports.
- Holon L4: Holon service/supervisor/model-probe files and tests.
- Research-depth: Palantir, Telos persona/council docs, research ingest scripts.
- Governance: lane admission, active-track evidence, portfolio truth reports.
- Stash clusters: telos/cockpit, command-plane UI, persistent-agents research, Chetana grand memory, inquiry-chain, LF5/runtime truth.

## What not to let DGM learn from

- Dirty `ACTIVE_TRACK.yaml` as if it were canonical.
- Stale receipts that claim liveness without fresh proof.
- Local-only branches without preservation or admission packets.
- Broad dirty checkouts as a single fitness example.
- Storage objects treated as disposable logs.
- STOP_BUILD-cleared assumptions without a receipt.
