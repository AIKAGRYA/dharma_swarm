# ADR-007: Retire AutoProposer Direct Darwin Submission — Route All Proposals Through BoardStore Cards

> **Date:** 2026-05-20
> **Status:** PROPOSED
> **Decision:** Retire `AutoProposer.submit_to_darwin` (and any equivalent direct-submission path) by **end of Phase 3**. From that point, every Darwin/evolution submission must originate as a `proposal` card created through `BoardStore.create_card` and gated by the facade's ARJUNA threshold + override flow. AutoProposer becomes a **pure noticer** (observation + card creation, no execution side-effect).
> **Companions:** [`SWARM_BOARDSTORE_SPEC.md`](../SWARM_BOARDSTORE_SPEC.md#16-open-questions-and-explicit-non-goals) (Open Q5 — this ADR resolves it), [`BUSINESS_INTELLIGENCE_NOTICERS.md`](../BUSINESS_INTELLIGENCE_NOTICERS.md#11-open-questions) (Q7 — this ADR resolves it), [`SHAKTI_GINKO_ORGAN.md`](../SHAKTI_GINKO_ORGAN.md), [`auto_proposer.py:136+`](../../../dharma_swarm/auto_proposer.py#L136)

---

## Context

Codex's BoardStore facade spec (`SWARM_BOARDSTORE_SPEC.md §4.7, §16 Q5`) explicitly leaves one substrate question open for v1:

> *"Should AutoProposer continue direct Darwin submission? Decision for v1 BoardStore: existing code can remain, but noticer-mode AutoProposer integration cannot access direct submit through the board. A later ADR should decide whether AutoProposer direct submission is retired or gated behind cards."*

Mirrored in our noticer spec as Open Q7 (`BUSINESS_INTELLIGENCE_NOTICERS.md §11`).

The unresolved-state problem: AutoProposer currently has two output channels — `submit_to_darwin` (direct, bypassing the substrate) and proposal-record observations (notice-only). The new Business Intelligence noticer roster (MarketScan / Viability / Opportunity / Ideation / Quality / Treasury) is **explicitly notice-only by contract** — they submit proposal cards through BoardStore.create_card and the facade enforces ARJUNA ≥ 0.35 + operator override semantics. If AutoProposer's direct path remains, we have **two divergent submission semantics** in one organ: the legacy path with no ARJUNA gate and no audit trail, and the new card path with both.

This is the exact pattern the ARJUNA Directive warns against: *every build must measurably advance Jagat Kalyan, not be meta-tooling*. Two parallel submission paths is meta-tooling — it forces every downstream consumer (Guardian, Sakshi, operator surfaces, Phase 3 noticer roster) to handle two cases forever.

The operator vision (`SHAKTI_GINKO_ORGAN.md §1`) is **multi-agent trust through one substrate** — Cursor, Codex, Claude Code, Devin, Warp all coordinating through BoardStore cards. A direct-submit backdoor breaks that trust model: an agent could bypass the gate.

## Options Considered

### A: Keep AutoProposer's direct submission indefinitely (status quo)

- **Pro:** Zero migration cost. Existing tests pass. Backward compatibility for any consumer wired to direct submission.
- **Con:** Permanent two-path submission semantics. Every new noticer must document "we don't do what AutoProposer does." Audit trail incomplete (direct submissions don't get card receipts). Operator override flow has a backdoor. ARJUNA threshold can be bypassed by any caller of `auto_proposer.submit_to_darwin`. Multi-agent trust model breaks: an agent could route around the substrate.

### B: Gate direct submission behind a feature flag, leave on by default

- **Pro:** Keeps backward compat, introduces a deprecation lever.
- **Con:** Feature flags that default to legacy behavior tend to ossify (cf. every "we'll flip the default later" in software history). The two-path semantics remain visible to every downstream consumer.

### C: Retire direct submission, route all submissions through `proposal` cards (CHOSEN)

- **Pro:** Single submission path. ARJUNA threshold uniformly enforced at the facade. Operator override has no backdoor. Full audit trail (every Darwin submission has a card receipt + `arjuna_override` event when applicable). Multi-agent trust model holds: every agent — including AutoProposer — must go through the same gate. Aligns AutoProposer with the rest of the BI noticer roster (notice-only). Matches Codex's substrate framing in `SWARM_BOARDSTORE_SPEC.md §4.7` directly.
- **Con:** Migration touches `auto_proposer.py:136+` and any caller of `submit_to_darwin`. Phase 3 noticer-roster PR cannot land until AutoProposer is converted. Submission latency increases by one card-create hop (negligible — millisecond range).

### D: Move direct submission to a privileged internal API, restrict by ACL

- **Pro:** Preserves the path for governance-internal callers (Guardian auto-fix, emergency operator interventions).
- **Con:** Privileged APIs become *de facto* parallel substrates. Every new use case argues for inclusion in the privileged list. Same two-path drift problem with extra access-control complexity. If the operator needs an emergency path, the override flow on `BoardStore.create_card` already provides it.

## Decision

**Option C — retire AutoProposer's direct Darwin submission.** All Darwin/evolution submissions go through `BoardStore.create_card(card_type="proposal", target="darwin", ...)`. AutoProposer becomes structurally identical to the other BI noticers: observe → score → submit card → facade gates.

This resolves `SWARM_BOARDSTORE_SPEC.md §16 Q5` and `BUSINESS_INTELLIGENCE_NOTICERS.md §11 Q7` as the same decision, expressed once.

### Concrete shape after the change

```
[before]                              [after]
AutoProposer                          AutoProposer (noticer)
  ├── observe()                         ├── observe()
  ├── score()                           ├── score()
  ├── record_proposal()                 ├── record_proposal()         ← unchanged
  └── submit_to_darwin()  ◄ removed     └── BoardStore.create_card(   ← new
       │                                       card_type="proposal",
       └── DarwinEngine                        target="darwin",
                                                ...
                                            )
                                              │
                                              ├── ARJUNA gate (≥0.35)
                                              ├── override flow
                                              ├── card receipt
                                              └── DarwinEngine consumes
                                                  via card subscription
```

### Migration plan (Phase 3)

1. **Add card-based submission** to AutoProposer. New method: `AutoProposer.submit_card(proposal, score, intended_target="darwin")` → wraps `BoardStore.create_card`. Lands behind a `use_card_submission` config flag, default **off** for the first PR (additive change, zero behavior delta).
2. **Add a Darwin-side card subscription**: a small adapter in DarwinEngine that pulls `card_type="proposal" target="darwin" state="accepted"` cards and feeds them into the existing submission pipeline. Behavioral parity with direct submission.
3. **Flip the flag default to on** in a follow-up PR. Existing callers of `submit_to_darwin` start using the card path. Card receipts now exist for every submission.
4. **Deprecate `submit_to_darwin`**: log a warning when called, behavior unchanged.
5. **Remove `submit_to_darwin`** in the PR after deprecation lands. AutoProposer's interface becomes notice-only.
6. **Audit Guardian + welfare aggregator + treasury noticer** to confirm none rely on direct-submission semantics.

### Backout

If a Phase 3 step regresses, revert the flag flip (step 3). Direct submission resumes. The card-based pathway remains additive and dormant until re-enabled.

## Consequences

### Positive

- **One submission path** across the entire substrate. Every Darwin submission has a card receipt, an ARJUNA score, and (if overridden) an `arjuna_override` event with named-target reason.
- **Multi-agent trust holds**: Cursor, Codex, Claude Code, Devin, Warp, AutoProposer all submit through the same gate. No agent can route around the substrate.
- **Phase 3 noticer-roster PR is unblocked**. BUSINESS_INTELLIGENCE_NOTICERS spec can ship without a "what about AutoProposer" footnote.
- **Audit completeness**: Sakshi sees every proposal as a card event. Welfare aggregator can score every submission. Guardian can flag patterns across all submissions uniformly.
- **Future organs inherit the pattern** (a community organ, a learning organ) without re-litigating the submission path.

### Negative / Costs

- Phase 3 migration touches `auto_proposer.py:136+` and tests in `tests/test_auto_proposer*.py`.
- DarwinEngine needs a small card-subscription adapter (estimated <100 LOC + tests).
- One PR cycle of deprecation warnings before final removal.
- Submission latency increases by ~1ms (negligible).

### Neutral

- AutoProposer's role becomes structurally identical to MarketScan / Viability / Opportunity / Ideation / Quality / Treasury noticers. This is the point.

## Open Questions Resolved by This ADR

- `SWARM_BOARDSTORE_SPEC.md §16 Q5` — **resolved**: retire direct submission.
- `BUSINESS_INTELLIGENCE_NOTICERS.md §11 Q7` — **resolved**: same decision.

## Open Questions Created by This ADR

- **Q-ADR007-1:** Should Guardian auto-fix submissions also be routed through cards? *(Recommended: yes, but separate ADR after Phase 3.)*
- **Q-ADR007-2:** What's the right `card_subscription` API for DarwinEngine — pull-based polling, push-based event subscription, or both? *(Recommended: push-based via the existing `task_board.subscribe` mechanism, fallback poll for resilience.)*
- **Q-ADR007-3:** Do existing AutoProposer historical proposal records get back-filled as cards? *(Recommended: no. Historical proposals stay as proposal records; only new submissions go through cards. Migration is forward-only.)*

## References

- `SWARM_BOARDSTORE_SPEC.md §4.7` — AutoProposer + recursive_discovery contract
- `SWARM_BOARDSTORE_SPEC.md §16 Q5` — the open question this ADR resolves
- `BUSINESS_INTELLIGENCE_NOTICERS.md §11 Q7` — the matching open question in our spec
- `SHAKTI_GINKO_ORGAN.md §1` — multi-agent trust through one substrate (the principle)
- `dharma_swarm/auto_proposer.py:136+` — current AutoProposer implementation
- `ADR-006-shakti-ginko-organ.md` — the umbrella organ this AutoProposer serves

---

**Author:** John Shrader (operator) + Computer (Perplexity)
**Required for:** Phase 3 (noticer-roster implementation PR)
**Blocks:** Nothing currently shipped. Recommended landing order: this ADR → AutoProposer card-path additive PR → flag-flip PR → deprecation PR → removal PR.
