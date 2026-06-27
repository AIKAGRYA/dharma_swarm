# Operator Decisions — 2026-06-23 DGM Reconciliation

## Immediate decisions requested

| Decision | Recommendation | Why it matters | Approval needed? |
|---|---|---|---|
| Confirm off-machine preservation | Yes, before ref hygiene or archive-after-preserve work | Local preservation exists, off-machine safety is uncertain | Yes |
| Extract cockpit | Yes, to `governance/operator-coherence-cockpit-20260623` | Cockpit is high-value but dirty-local | Yes |
| Admit Arena v1 track | Yes, `orchestration-arena-v1-2026-06` | Arena/Council substrate is on-main but invisible to active-track governance | Yes |
| Triage #675 | Yes, high priority | Provider discoverability can remove a false no-provider blocker | Yes before promotion |
| Triage #674 | Yes, high priority | Closure gate improves production-grade review rigor | Yes before merge |
| Open revenue lane | Yes, narrow and receipt-gated | Repairs revenue objective coverage gap | Yes |
| Open research-depth lane | Yes, verified-claim-gated | Repairs research-depth objective coverage gap | Yes |
| Storage policy | Yes, metadata-only first | `.dharma` is 344G and includes hot storage objects | Yes |
| STOP_BUILD handling | Add cockpit/Arena blocker card | Prevent DGM from learning from unresolved regression state | Yes to clear |

## Recommended yes/no packet

### A. Cockpit extraction

Approve:

```text
Create/reuse a clean extraction branch named governance/operator-coherence-cockpit-20260623.
Extract only cockpit/backplane/UI files from dirty checkout.
Run compile/test/dashboard build verification.
Produce admission packet.
No broad merge from telos-ai-seed-v0-from-sandbox.
```

### B. Arena governance admission

Approve:

```text
Draft ACTIVE_TRACK admission proposal for orchestration-arena-v1-2026-06 anchored to origin/main 4137e83c.
No autonomous mutation.
Zero learned weights at first.
Frozen task battery and Council/verifier receipts required.
```

### C. Revenue coverage repair

Approve:

```text
Open a narrow revenue-external-human-receipt lane.
Candidate input: CashClaw + on-main revenue spine.
Admission proof must be an external-human action or cash receipt.
Current $0 proof is not sufficient for production-grade success.
```

### D. Research-depth coverage repair

Approve:

```text
Open a research-depth-verified-sensemaking lane.
Candidate inputs: Chetana MarkItDown, Palantir pilot, persistent-agent and Moltbook branches.
Admission proof must be verified claims, not just ingestion.
```

### E. Preservation and storage

Approve:

```text
Confirm off-machine copy for preservation packet and high-value overlays.
Create metadata-only storage policy for .dharma storage objects.
No storage-object mutation during reconciliation.
```

## Decisions to defer

- Ref hygiene for already-on-main and stale duplicate branches.
- Any archive-after-preserve action for stashes.
- Any archive-after-preserve action for empty sibling dirs.
- Any attempt to make dirty local `ACTIVE_TRACK.yaml` canonical.
- Any Forge/DGM autonomous mutation track beyond Arena v1 measurement.

## Current top 10 action queue for John

1. Say yes/no to cockpit extraction branch.
2. Confirm whether GitHub auth should now be used for read-only PR checks and later operator-approved pushes.
3. Confirm off-machine preservation target: GitHub refs, Agni, external disk, or another vault.
4. Decide whether #675 should be reviewed before cockpit extraction or after it.
5. Decide whether #674 closure gate should become part of cockpit/backplane acceptance.
6. Approve Arena v1 governance admission draft.
7. Choose the first revenue proof target.
8. Choose the first research-depth corpus.
9. Decide whether Helm/terminal UX is a later lane or out-of-scope for this cockpit sprint.
10. Decide how STOP_BUILD gets cleared: test suite, targeted regression replay, or explicit safety receipt.
