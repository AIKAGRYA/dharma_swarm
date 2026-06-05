# Andon Status — Audit Verification

**Pulled:** 2026-06-01T06:28Z by perplexity-computer
**State:** RECONCILIATION DRAFTED — awaiting operator close decision
**Blocks:** Layer-2 Revision 3 (field-bridge types) on PR #414

## Page sent

| Channel | Target | Status |
|---|---|---|
| NATS `dharma.a2a.fleet` | all listeners | published seq=189 (durable) |
| NATS `dharma.a2a.perplexity` | claude | published seq=190 (durable) |
| `inter_agent/*/inbound/` | 6 agents | dropped |
| PR #414 comment | operator John | posted |

## Slice tracker

| Slice | Topic | Verdicts received | Cross-checked |
|---|---|---|---|
| A | Identity schemes (10+ IDs claim) | **perplexity** → `partially_confirmed` | pending peer |
| B | Envelope schemas (7 envelopes claim) | **perplexity** → `partially_confirmed` | pending peer |
| C | Authority & execution (4 sub-claims) | **perplexity** → C1 overstated · C2 confirmed · C3 partially_confirmed · C4 wrong | pending peer |
| D | Workflow state ownership | — | — |
| E | A2A external/internal collision | — | — |
| F | What Codex MISSED (PhD reviewer eye) | folded into A/B/C side-notes (7 findings) | pending peer |

Verdicts at `andon/verdicts/<agent>-<slice-letter>.md`.
Reconciliation at `andon/reconciliation.md`.

## Headline pattern (from reconciliation)

Codex is directionally correct on fragmentation, evidentially sloppy. Three falsifiable claims about untracked or non-existent code (`correlation_key`, "spec envelope", `nats_a2a_bridge.py`). One sharp real bug (C2: `execute_action` does not honor `ActionDef.modifies`). One overstated framing (C1: one canonical authority stack misread as 5–7). Real fragmentation worse than claimed in places (claim_id 4-way, NATS 3+ wire formats, missed 8th envelope).

## Close criteria

1. [x] Every slice A–C has ≥1 verdict file (D, E still open)
2. [ ] At least one slice has 2 independent verdicts (cross-check) — none yet
3. [x] perplexity-computer wrote `andon/reconciliation.md`
4. [ ] Operator John reviews + closes

## Operator decision needed

- **Option (i):** close andon now, ship narrow Revision 3 (`executionIdentity`, `runEnvelope`, `humanReview`; defer `workflowRun`; kill `authority`; file C2 binding bug separately).
- **Option (ii):** keep andon open another tick for slices D + E and peer cross-checks before finalizing.

See `reconciliation.md` for the full case.
