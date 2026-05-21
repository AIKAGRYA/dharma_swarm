# ADR-006: SHAKTI_GINKO as an Umbrella Organ Containing VentureCells

> **Date:** 2026-05-20
> **Status:** PROPOSED
> **Decision:** Treat SHAKTI_GINKO as a multi-cell **organ** of dharma_swarm — a coordinated subsystem spanning ontology, runtime, treasury, and noticers — rather than as one VentureCell or one module. The current trading work becomes the **trading-lab grouping** of cells inside the organ. Future cells (vault-mirror, agni-ops, rushabdev-spoke, revenue-wedge, ideation, etc.) live alongside it under one Treasury, one telos frame, one noticer roster, one set of operator surfaces.
> **Companions:** `docs/architecture/SHAKTI_GINKO_ORGAN.md`, `docs/architecture/VENTURE_CELL_LIFECYCLE.md`, `docs/architecture/BUSINESS_INTELLIGENCE_NOTICERS.md`

---

## Context

The repo has 18 `ginko_*` modules + 18 test files + 1201 mentions of "ginko" across `.py/.md/.yaml`. The orchestrator docstring at `dharma_swarm/ginko_orchestrator.py:3` says: *"Coordinates the Shakti Ginko VentureCell"* — singular. But the operator-local strategic vault at `~/AGNI-AUNT-HILLARY-PSMV/SHAKTI_GINKO/` describes a substantially broader scope: VISION/STRATEGY/REVENUE/PRODUCTS/OPERATIONS/METRICS/PRIMERS/TOP_10_DISCIPLINES, 4847-word master skeleton, 91 `[SWARM_TARGET]` markers, plus VPS spokes Agni and rushabdev. The operator now states explicitly: *"SHAKTI_GINKO is the bank-organ instantiating VentureCells."*

There is a definitional gap between the code's singular framing and the operator's umbrella framing. The first VentureCell was declared at `docs/governance/VENTURE_CELL_REVENUE_WEDGE.md` already, with $50k budget and $10k target — proving the multi-cell model is intended. The ontology object already supports it (`ontology.py:1470-1507` defines `VentureCell` as a first-class plural type with create/advance actions).

The operator also asks for: persistent background noticers, heterogeneous agent trust across Claude Code / Codex / Cursor / Devin / Warp / Perplexity, and *"future-proof multi-agent intelligence that works seamlessly."*

## Options Considered

### A: SHAKTI_GINKO is one VentureCell (status quo of `ginko_orchestrator.py:3`)

- **Pro:** Smallest delta from current code. The orchestrator already coordinates "the" VentureCell.
- **Con:** Contradicts the vault, the operator's stated intent, and the existence of the Revenue Wedge as a sibling cell. Forces every future cell to be either nested-under or a peer-of "the" cell, with no clear governance frame. Doesn't model Treasury, VPS spokes, or noticer roster at the right scope.

### B: SHAKTI_GINKO is a top-level module group / namespace (no organ concept)

- **Pro:** Familiar — just a Python package convention.
- **Con:** A namespace cannot own a Treasury, enforce ARJUNA gates at the boundary, run a noticer roster, or model VPS spokes. The organ concept is doing semantic work that "namespace" can't do.

### C: SHAKTI_GINKO is an **organ** containing VentureCells (CHOSEN)

- **Pro:** Matches the operator's mental model and the vault's structure. Provides a natural home for Treasury, the noticer roster, VPS spokes, and the trading-lab grouping. Each VentureCell remains first-class (ontology-typed, BoardStore row, own KPIs/budget/kill-conditions) but the organ aggregates them under one telos frame. Supports future organs (a learning organ, a community organ) without rework.
- **Con:** Introduces a new concept ("organ") above VentureCell. Requires a unified status enum and a Treasury layer (Phase 1–2 substrate work). Migration touches multiple files. Higher up-front coordination cost.

### D: SHAKTI_GINKO is a separate sibling repo

- **Pro:** Clean public/private separation.
- **Con:** Splits the substrate from the cells it serves. Treasury and noticer roster would need cross-repo coordination. Premature — there's no public artifact yet to separate.

## Decision

**Option C: organ containing VentureCells.**

Concretely, the organ shape is:

```
SHAKTI_GINKO (organ)
├── Treasury (organ-level budget + welfare aggregation)
├── Noticer roster (MarketScan, Viability, Opportunity, Ideation, Quality, Treasury)
├── Trading-lab grouping (the existing 18 ginko_* modules organized as cells)
│   ├── prediction-cell        (Brier, win-rate, paper trading)
│   ├── micro-capital-cell     ($100-500, stage 3)
│   ├── small-capital-cell     ($1K-5K, stage 4)
│   └── autonomous-cell        (stage 5, governed by spinout_conditions)
├── Revenue-wedge cell         (already declared, $50k budget)
├── Vault-mirror cell          (operator-local vault sync, ARJUNA-gated reads)
├── Agni-spoke cell            (VPS daily.toobit.sh ritual, ADR follow-up)
├── Rushabdev-spoke cell       (VPS spoke, mirrored locally at ~/rushabdev_work/)
└── Ideation cell              (host for IdeationNoticer outputs awaiting approval)
```

The trading-lab grouping is a logical group inside the organ, not a new layer. Each trading cell is a first-class VentureCell with its own KPIs/budget/kill-conditions. Cross-cell coordination happens via the noticer roster and Treasury — not via direct orchestrator calls.

No file renames in this PR. The 18 `ginko_*` Python modules stay where they are; subsequent PRs introduce deprecation shims and rename only after the substrate facade lands (`SWARM_BOARDSTORE_SPEC.md`).

## Why this shape and not another

1. **The vault already says so.** The vault is the strategic authority and it describes an organ. The code should match.
2. **The ontology already supports it.** `_VENTURE_CELL` at `ontology.py:1470` is plural by design — `create_roles`, `Advance` action, `enum_values=["incubating","active","mature","divesting","archived"]`. Plurality is encoded.
3. **The first sibling cell already exists.** `VENTURE_CELL_REVENUE_WEDGE.md` declared a non-trading cell with its own kill_conditions. Option A is already false on the ground.
4. **Treasury can't live below cells.** Budget aggregation, ARJUNA enforcement, and spinout sign-off are organ-scope concerns. They need a layer above cells.
5. **Heterogeneous agents need a single trust frame.** Claude Code, Codex, Cursor, Devin, Warp, and Perplexity will be assigned across cells. The organ owns the default-authority table (`agent_registry.py`). One organ = one trust frame.
6. **Future organs are now expressible.** If a "learning organ" or "community organ" emerges, it doesn't displace SHAKTI_GINKO — it sits beside it under dharma_swarm, with its own Treasury and noticer roster.
7. **Sublate-not-replace.** Option C keeps every existing module, test, signal bus event, and ontology object. The umbrella concept *adds* governance shape without invalidating prior work — exactly as the operator directs.
8. **ARJUNA enforcement gets the right scope.** ARJUNA Directive applies at three points (creation, advance, spinout). Those are organ-scope decision points, not cell-internal ones.

## Consequences

### Positive

- Operator now has a single name for the bank-organ that matches their mental model.
- Treasury, ARJUNA enforcement, and noticer roster have a natural home.
- Each new project (vault-mirror, agni-ops, rushabdev-spoke, etc.) slots in as a cell without bespoke architecture.
- The status enum unification (`VentureCellStatus`) becomes a clear Phase 1 task.
- Migration is staged in 4 phases (per `SHAKTI_GINKO_ORGAN.md §11`); each phase is its own PR.

### Negative

- Introduces a new concept (organ) above VentureCell. Operators must learn it. Mitigation: glossary in `SHAKTI_GINKO_ORGAN.md`, Doc B Appendix B.
- Requires the BoardStore facade to land before noticers can enforce notice-only RBAC. The two specs are coupled. Mitigation: ship spec PRs in parallel; implementation lands sequentially.
- Migration cost: ~4 PRs over multiple weeks.
- Risk of double-named concepts (organ vs ginko vs venturecell-collection) leaking into code. Mitigation: enforce naming via `.semgrep/dharma-anti-slop.yml` rule additions.

### Neutral but worth noting

- The current `ginko_orchestrator.py:3` docstring drift (*"the Shakti Ginko VentureCell"*) gets corrected to *"the Shakti Ginko organ; coordinates the trading-lab grouping of VentureCells"* in the Phase 1 PR.
- No external API changes in this PR. Public Python imports remain stable.
- Operator's daily.toobit.sh ritual on Agni continues uninterrupted; the agni-spoke cell wraps it as a first-class cell with kill_conditions in Phase 2.

## Open Questions for Operator

Routed via `SHAKTI_GINKO_ORGAN.md §13` and the PR description:

1. Confirm umbrella organ framing and trading-lab grouping.
2. Confirm vault-mirror, agni-spoke, rushabdev-spoke as cells (vs. organ-level services).
3. Confirm Phase 1 lands without file renames (rename in follow-up PR with deprecation shims).
4. Confirm default agent-authority table per heterogeneous agent.
5. Confirm noticer cadences (6 h, triggered, 1 h, 24 h, continuous).

## Related Decisions

- `docs/plans/ADR_WELFARE_TONS_REPO_STRUCTURE_2026-03-21.md` — welfare-tons is a separate public repo; dharma_swarm orchestrates work on it. Consistent with this ADR: SHAKTI_GINKO is the orchestrating organ; welfare-tons is one of the products produced by cells within it.
- (forthcoming) ADR-007 — learned ranking signals for noticers (deferred from v1 per `BUSINESS_INTELLIGENCE_NOTICERS.md §1.3`).

## Status History

- **2026-05-20** — PROPOSED on branch `spec/shakti-ginko-organ`. Companion specs co-authored.
