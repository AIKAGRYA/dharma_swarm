# Learned Auditable Orchestrator — Build Spec (TRACK PROPOSAL)

**Status:** PROPOSAL — not yet admitted to the active portfolio.
**Serves spine objective:** `substrate-nativeness`.
**Author:** Claude remote (Lane B). **Drafted:** 2026-06-22.

> **Governance note (read first).** The portfolio is mid-reconciliation and already
> over the WIP cap (13 candidate tracks vs `max_active: 10`). This track is a
> **proposal**, deliberately NOT wired into `ACTIVE_TRACK.yaml` yet. Admit it only
> after the reconciliation frees a slot (close/fold a stale or local-only track).
> The declaration block below is ready to paste when that happens.

---

## Why

Sakana shipped **Fugu** (2026-06-22): orchestration-as-a-model — a learned coordinator
that selects the best model per sub-task, delegates, verifies, and synthesizes behind one
API. It is the productized form of the **Transcendence Principle already written into our
`CLAUDE.md`** (diverse competent agents + decorrelated errors + quality aggregation).

We already own most of the organs Fugu needed to invent. What we lack is the *learned
coordinator* that ties them. This track builds that coordinator — and makes it **better
than Fugu on the two axes where Sakana is structurally weak**: verification rigor and
auditability. Fugu's routing is proprietary/opaque ("users cannot see which models are
selected") and its numbers are self-reported. Ours will be **receipted and
moat-verified** — every routing decision provable.

## Research basis (the two recipes we fuse)

**TRINITY** (arXiv 2512.04695, ICLR 2026) — the *cheap, evolved, reactive* router:
- Coordinator = small SLM (Qwen3-0.6B class) + a lightweight head after the final hidden
  layer emitting **`L` model-logits (pick 1 of L agents) + 3 role-logits**
  (Thinker / Executor / Verifier). No generation for routing — one forward pass.
- Head adapted via SVF (singular-value fine-tuning, Transformer²), optimized by
  **separable CMA-ES**: sample perturbed parameter vectors → fitness → fitness-weighted
  recombine into next parent. Beats RL/imitation/random under tight budget + high dim.
- Multi-turn **accept-driven loop**: Executor solves → Verifier ACCEPT/reject → Thinker
  plans if stuck, until ACCEPT or max turns.

**Conductor** (arXiv 2512.04388, ICLR 2026) — the *rich, RL-trained, generative* planner:
- Base = Qwen2.5-7B, fine-tuned with **GRPO**. Writes a workflow as a sequence of steps,
  each = **(natural-language instruction, assigned agent, access-list of what that agent
  can see)** — designing both topology and per-worker prompt.
- Reward = **correctness + cost penalty**. Trained with **randomized agent pools** → adapts
  to arbitrary open/closed workers. **Recursive** (self-as-worker). Emergent: problem
  decomposition + independent attempts + final debate rounds.

The two are complementary: TRINITY = near-free per-turn role routing; Conductor = rich
upfront planned topology. Fugu ships both layered.

## Substrate mapping — what we already have

| Fugu/paper component | We already own |
|---|---|
| Evolved coordinator (sep-CMA-ES) | `DarwinEngine` (`evolution.py`) — evolutionary, diversity-preserving |
| Topology execution (fan-out/in/pipeline/debate) | `orchestrator.py` topology primitives |
| Verifier role / debate | `world_radar/frontier_council.py` — decorrelated cross-falsification moat |
| Reward (correctness + cost) | `ginko_brier.py` (Brier) + `telos_gates.py` + `cost_efficiency` vital sign |
| Randomized diverse pool | multi-provider pool + `diversity_archive.py` (MAP-Elites, measured) |
| Recursion (self-as-worker) | `cascade.py` LoopEngine `F(S)=S` |
| **Audit (Fugu has none)** | `spine` **EvidenceReceipt** — per-dispatch proof |

## The build — staged, lowest-risk first

### Stage 0 — Auditable + moat-verified wrapper (NO training; weeks)
Wrap the **existing** power-first router with two things already built:
- Emit a **`RoutingReceipt`** (read-only projection of `spine.EvidenceReceipt`) for every
  selection: which provider, why (precedence trace), cost, verdict. No new authority.
- Gate any multi-candidate answer through the **Frontier Council moat** as the aggregator
  → one corroborated verdict + receipt.

**Result: already beats Fugu on auditability + verification rigor, with zero learned model.**

*Owned new surfaces:* `dharma_swarm/coordination/routing_receipt.py`,
`dharma_swarm/coordination/verified_aggregator.py`,
`scripts/governance/check_routing_receipt.py`,
`tests/test_routing_receipt.py`, `tests/test_verified_aggregator.py`.
*Acceptance:* every routing decision in a fixture run carries a `RoutingReceipt`;
multi-candidate fixtures resolve through the moat to one verdict; hermetic replay check
green; `dispatch_authority` stays False; no edits to `provider_policy.py` (consult only).

### Stage 1 — TRINITY layer: an evolved CoordinationHead (DarwinEngine IS the optimizer)
A small hidden-state head emitting `(provider_logits[L], role_logits[3])` per turn, with
the Thinker/Executor/Verifier accept-loop. **Evolve it with `DarwinEngine`** (we have the
evolutionary substrate TRINITY needed CMA-ES for), fitness = **Brier-scored task success**
on a frozen offline eval set, decorrelation preserved via `diversity_archive`. The Verifier
role is the **Frontier Council moat** (stronger than a single Verifier role).

*Owned new surfaces:* `dharma_swarm/coordination/coordination_head.py`,
`dharma_swarm/coordination/accept_loop.py`,
`dharma_swarm/coordination/evolve_coordinator.py` (DarwinEngine harness),
`scripts/governance/check_coordinator_replay.py`,
`tests/test_coordination_head.py`, `tests/test_accept_loop.py`.
*Acceptance:* head is a pure deterministic function of (context embedding, weights);
offline eval harness runs on a **fixture pool with no live provider calls**; evolved head
beats the hand-tuned precedence baseline on the frozen eval (Brier); accept-loop terminates
on moat-ACCEPT; every turn receipted.

### Stage 2 — Conductor layer: generative topology planner (DEFERRED; research lane)
A planner that writes `(instruction, agent, access-list)` steps for `orchestrator.py` to
execute, trained with **GRPO + pool randomization**, reward = telos-gated Brier + receipted
external-acted outcomes; recursion via LoopEngine. **Out of initial scope** — needs a rollout
harness + compute. Hold behind Stage 0/1 proof and a flag. De-risk training stability with
Graph-GRPO (arXiv 2603.02701).

## Differentiators (why this is *higher quality than Sakana*, not equal)
1. **Verification:** decorrelated cross-falsification moat > a single Verifier role.
2. **Auditability:** per-decision EvidenceReceipt > Fugu's opaque routing.
3. **Measured decorrelation:** `diversity_archive` Krogh-Vedelsby term > unpublished pool diversity.
4. **Honest eval:** receipted, third-party-verifiable benchmark loop > self-reported numbers
   (recall Fable 5 still beats Fugu Ultra 80.3 vs 73.7 on SWE-Bench Pro).

## Non-goals
- Do NOT own or modify `provider_policy.py`, `model_hierarchy.py`, or `orchestrator.py`
  routing wiring — **consult/reuse only** (avoids overlap with provider-routing-consolidation
  and runtime-truth-spine-adoption).
- Do NOT change the `EvidenceReceipt` schema; project over it.
- Do NOT make live provider calls in CI or unit tests (fixture pool only).
- Do NOT flip dispatch authority or touch archive fitness.
- Do NOT copy Sakana internals; implement the shared principle on our substrate, citing
  Krogh-Vedelsby / Zhang 2024 / Abreu 2025 as the theory.

## Track declaration block (paste into ACTIVE_TRACK.yaml when a slot frees)
```yaml
- id: learned-auditable-orchestrator-2026-06
  name: Learned Auditable Orchestrator — receipted, moat-verified model coordination
  status: ACTIVE
  opened_at: "2026-06-22"
  verified_at: "2026-06-22"
  ttl_days: 21
  owner: "@AmitabhainArunachala"
  serves: substrate-nativeness
  complements:
    - provider-routing-consolidation-2026-06
    - runtime-truth-spine-adoption-2026-06
    - seeing-organ-2026-06
  owned_surfaces:
    - dharma_swarm/coordination/**
    - scripts/governance/check_routing_receipt.py
    - scripts/governance/check_coordinator_replay.py
    - tests/test_routing_receipt.py
    - tests/test_verified_aggregator.py
    - tests/test_coordination_head.py
    - tests/test_accept_loop.py
    - docs/architecture/LEARNED_AUDITABLE_ORCHESTRATOR_SPEC.md
  moves_vital_signs: [quality_gates, tool_coverage, cost_efficiency]
```

## Sources
TRINITY arXiv 2512.04695 · Conductor arXiv 2512.04388 (OpenReview U23A2BUKYt) ·
Sakana Fugu (sakana.ai/fugu) · Graph-GRPO arXiv 2603.02701 · AgentConductor arXiv 2602.17100 ·
Krogh-Vedelsby 1995 · Zhang et al. NeurIPS 2024 · Abreu et al. 2025 (cited in CLAUDE.md).
