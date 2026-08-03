# INDEX — Historical Design Read Order

> **Authority notice (2026-08-03):** Start at the canonical subject doorway,
> [`../SARATHI.md`](../SARATHI.md), for current terms, runtime-family boundaries,
> and evidence routes. This index preserves the June design sequence; its
> present-tense implementation claims are historical. The July estate map is a
> dated deep reference only.

**Created:** 2026-06-08 · **Purpose:** The shortest path through the sovereign-holon initiative for someone arriving cold.

Use this file when tracing the original research and design lane.

> **Looking for where a June artifact lived?** → [MAP.md](MAP.md).
> **Tracing the original build proposal?** → §"Original build sequence" below, then [05_RECONCILED_PLAN.md](05_RECONCILED_PLAN.md).

---

## The one-paragraph version

dharma_swarm has 46 registered agents on disk, a real wake-loop body (`PersistentAgent`), a real reasoning brain (`AutonomousAgent`), and a real NATS mailbox — but **no function turns a registered record into a runnable agent**. The dashboard chat at `api/routers/agents.py:404` runs the operator's global model with a cosmetic persona string. The fix is the **record→runtime bridge** ([02_FIRST_BRICK_SPEC.md](02_FIRST_BRICK_SPEC.md)) built in this order: **Mike-first** (governed runtime-bridge proof) → **Perplexity-second** (rich soul/seed shape proof), both using one `AgentSeedResolver` reading one `agent.seed.yaml` contract ([04_FRONTIER_DOSSIER.md](04_FRONTIER_DOSSIER.md), [05_RECONCILED_PLAN.md](05_RECONCILED_PLAN.md)). Three hygiene patterns ([03_REGISTER_AS_HYGIENE.md](03_REGISTER_AS_HYGIENE.md)) make sure the work survives any agent turnover.

## Read order

1. **[README.md](README.md)** — the verified state of the substrate (5 organs, what's real, what's a gap).
2. **[05_RECONCILED_PLAN.md](05_RECONCILED_PLAN.md)** — the operator-decided sequencing (Mike first, then Perplexity) and the 6-step build plan.
3. **[02_FIRST_BRICK_SPEC.md](02_FIRST_BRICK_SPEC.md)** — the executable spec for the first brick, with `file:line` evidence for every claim.
4. **[04_FRONTIER_DOSSIER.md](04_FRONTIER_DOSSIER.md)** — the long-term `agent.seed.yaml` contract the bridge must produce / consume.
5. **[07_SOTA_HARNESS_OVERBUILD.md](07_SOTA_HARNESS_OVERBUILD.md)** — the bleeding-edge overbuild spec for the runnable shell + verification + context-bridging harness (the three areas the frontier and our dossiers say actually move the needle). Model-agnostic, MemoryKernel-powered, artifact + pass^k + sleep-time first-class.
6. **[00_RESEARCH_DOSSIER.md](00_RESEARCH_DOSSIER.md)** — only when you want the receipts: 52-source research, gap analysis, the two ironies.
6. **[01_BUILD_GUIDE.md](01_BUILD_GUIDE.md)** — the original organ-model walk-through. Subsumed by 02+05 but kept for the architecture diagram.
7. **[03_REGISTER_AS_HYGIENE.md](03_REGISTER_AS_HYGIENE.md)** — only when you (or another agent) are about to commit anything in this lane: three patterns to add to `dharma_swarm_pr_review_control`.

## Original build sequence at a glance

| # | What | Where it's specified |
|---|---|---|
| 1 | `AgentSeedResolver` (read-only) | [05_RECONCILED_PLAN.md §1](05_RECONCILED_PLAN.md) |
| 2 | `agent.seed.yaml` for `merge_master_mike` | [05_RECONCILED_PLAN.md §2](05_RECONCILED_PLAN.md), shape from [04](04_FRONTIER_DOSSIER.md) |
| 3 | `dgc agent talk <uid> --projection` | [05_RECONCILED_PLAN.md §3](05_RECONCILED_PLAN.md) |
| 4 | Artifact verifier (external-process re-readable) | [05_RECONCILED_PLAN.md §4](05_RECONCILED_PLAN.md), see [02 acceptance #4](02_FIRST_BRICK_SPEC.md) |
| 5 | Real runtime mode (seed → resolver → policy → `PersistentAgent`) | [05_RECONCILED_PLAN.md §5](05_RECONCILED_PLAN.md), [02 acceptance #1–6](02_FIRST_BRICK_SPEC.md) |
| 6 | Dashboard honesty (relabel or re-route `/api/agents/{id}/chat`) | [05_RECONCILED_PLAN.md §6](05_RECONCILED_PLAN.md) |

Then build perplexity-computer's `agent.seed.yaml` against the now-proven contract, using the existing nest at `docs/agents/perplexity-computer/`.

## Non-negotiables (carried from every dossier and critic pass)

- No new daemon, registry, memory store, or truth store. Bridge + surface over existing owners.
- No full policy-engine claim — first gate is a literal default-deny skeleton on one field.
- Fail-**closed** in the talk layer. Do not reuse fail-open `_check_gate`.
- Verification must assert a re-readable artifact (separate process can open it). No same-model self-grading.
- Route via `preferred_runtime_provider_configs()` explicitly. Default chain routes to Claude → crashes if absent.
- Prompt-injection defense in scope (moltbook is the cautionary tale — see [README addendum](README.md#addendum-2026-06-08--new-research-findings-folded-in)).
