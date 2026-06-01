# Andon Status — Audit Verification

**Pulled:** 2026-06-01T06:28Z by perplexity-computer
**State:** OPEN — line stopped, verification in flight
**Blocks:** Layer-2 Revision 3 (field-bridge types) on PR #414

## Page sent

| Channel | Target | Status |
|---|---|---|
| NATS `dharma.a2a.fleet` | all listeners | published seq=189 (JetStream durable) |
| NATS `dharma.a2a.perplexity` | claude | published seq=190 (JetStream durable) |
| `inter_agent/claude/inbound/` | claude | dropped |
| `inter_agent/devin/inbound/` | devin | dropped |
| `inter_agent/hermes/inbound/` | hermes | dropped |
| `inter_agent/mike/inbound/` | mike | dropped |
| `inter_agent/codex/inbound/` | codex | dropped |
| `inter_agent/gpt55/inbound/` | gpt55 | dropped |
| PR #414 comment | operator John | posted |

## Slice tracker

| Slice | Topic | Verdicts received | Cross-checked |
|---|---|---|---|
| A | Identity schemes (10+ IDs claim) | perplexity (in flight) | — |
| B | Envelope schemas (7 envelopes claim) | perplexity (in flight) | — |
| C | Authority & execution (4 sub-claims) | perplexity (in flight) | — |
| D | Workflow state ownership | — | — |
| E | A2A external/internal collision | — | — |
| F | What Codex MISSED (PhD reviewer eye) | — | — |

Verdicts land at `andon/verdicts/<agent>-<slice-letter>.md`.

## Close criteria

1. [ ] Every slice A–F has ≥1 verdict file
2. [ ] At least one slice has 2 independent verdicts (cross-check)
3. [ ] perplexity-computer writes `andon/reconciliation.md`
4. [ ] Operator John reviews + closes the andon

Only after close → Revision 3 vocabulary discussion resumes.
