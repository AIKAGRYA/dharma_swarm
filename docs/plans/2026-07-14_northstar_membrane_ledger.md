# North Star ↔ Membrane Ledger — 2026-07-14

Session ledger: what was produced 07-13→07-14, where it lives, what was verified. Written so nothing here depends on a chat transcript surviving.

## Artifacts and custody

| Artifact | Location | Custody |
|---|---|---|
| DharmaGraph North Star AMPLIFIED (14 lenses → 3 judges → synthesis; 10-move power core; D1–D6) | `~/handoffs/2026-07-13_DHARMAGRAPH_NORTHSTAR_AMPLIFIED.md` + `dharma_swarm/docs/plans/` (committed this session) | pushed to origin |
| Raw brainstorm corpus (81 moves, 14 lens returns, 3 judge verdicts, 408KB jsonl) | `~/handoffs/2026-07-13_northstar_brainstorm_corpus.jsonl` | LOCAL ONLY |
| Master assessment (codex, 13 files, frozen c14b950, validator 0/0, 12/12 probes) | `dharma_swarm/reports/audits/dharma_antithesis_master_assessment_2026-07-13/` (was untracked; committed this session) | pushed to origin |
| Memory entries | `~/.claude/projects/-Users-dhyana/memory/dharmagraph-northstar-amplified-2026-07-13.md` | LOCAL ONLY |

## Verified this session (against builder receipt JSON, not prose)

The operator-relayed membrane synthesis ("proof plane between action system and self-improvement system") was checked at receipt level — 3/3 load-bearing numbers CONFIRMED:

1. **LG14–18 = 33.00 of the 52.00** — raw points 2 each, weights 4/9/2/8/10 → weighted 66/200. 63% of the parity score sits exactly on the surfaces with reproduced correctness failures (lost update F-02, fork alias F-03, poison journal F-04).
2. **13 application scenarios, all `neutral_engine_involved: false`** (raw_evidence/applications; +4 in APP facets = 17 total).
3. **248 surface probes = 208 `dharma_public_surface_missing` + 40 `related_public_surfaces_present_behavior_unproven`.**

Two corrections to that synthesis:
- Its caution #3 is a MISREAD: DHARMA_CODEBASE_AUDIT.md:319 ("7 narrow Swarm tests, five defects those tests miss") is exact — the five swarm-side probes are stigmergy, failed-prerequisite, SignalBus, provider-URL, provider-diversity. No internal inconsistency.
- "Not another active track" is half wrong: assessment §7 requires exactly ONE owning track for replay-lab surfaces; cross-cutting adoption is the acceptance criterion, not the ownership model (estate failure mode = unowned work stranding, cf. one-door unifier).

Adopted from that synthesis (fold into membrane RFC):
- The category-error framing: all 12 counterexamples = one illicit conversion, *weaker receipt read as stronger claim*.
- **EPI-PROP-MISMATCH refinement**: `Claim<Satisfies<P>, Reproduced, Principal<K>, Scope<S>>` + non-deserializable `Authorize<K,P,Promote<C>,S>`; promotion only when P == PromotionObligation(C). Closes the real hole where a reproduced ParityScore(52) could discharge ProductionReady. Authorize-as-capability = the Weismann vault from pure type theory — third convergent lane (UCL 07-05, Sealed Act 07-13, this 07-14).
- Modalities are not a confidence ladder; a perfectly reproduced bad oracle remains bad.

## Merged execution order (North Star × assessment roadmap)

Day 0–7: `make onboard` fix (P0, 0.5–1d; Makefile:592 fails GNU Make 3.81) + rotate argv-exposed credentials + WebSocket auth → commit/sign/anchor genesis (31→52 lineage + ledger + this session's artifacts) → judge trust-root (~2d, F-07) → F-11 shadow-fitness isolation → pre-registered bounty trial (metric (a) merge+payment unfakeable now; metric (b) needs F-11) → RFC-001/002/003 ladder → attested launcher (precondition for Epoch One's chain-only falsifier) → engine-swap rite + paid verdicts.

North Star self-kill clause: anchored within 7 days of 2026-07-13 or the tenure thesis is publicly confessed dead.

## Operator decisions pending (D1–D6)

In the North Star §VI: D1 ratify category sentence + image; D2 Hour Zero key ceremony; D3 genesis content = 31→52 lineage with both self-deflations; D4 bounty trial pre-registration (25 attempts/60 days); D5 contested calls (standards sequencing / honeycomb deferral / promotion ordering); D6 witness-mortality succession protocol. Pointer added to `~/.dharma/darshan/DECISIONS_PENDING.md`.

## Still at loss-risk after this session

- Auto-memory dir (`~/.claude/projects/-Users-dhyana/memory/`) — no off-host copy.
- `~/handoffs/` as a whole (incl. the 408KB corpus) — no off-host copy.
- The 1GB meghadharma organism — zero off-host backup (standing).
