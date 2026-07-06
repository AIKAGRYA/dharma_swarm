# 04 — Persistent-Agent Relation (the lineage ladder)

**Custody: VERIFIED 2026-07-06. Numbered front-door version of
`11_PERSISTENT_AGENT_RELATION.md` (which keeps the full file:line table).**

## The ladder

```text
PersistentAgent lineage            (older standing actor)
  -> LivingAgentKernel durability  (wake ledger, leases, proof, closeback)
    -> Holon runtime identity/governance  (load_holon + holon_wake_cycle)
      -> Holon system product package      (dharma_swarm/holon_system)
        -> Sarathi apex gateway            (the apex occupant; not yet breathing)
```

Each rung USES the rung below. Nothing here is a rewrite of the rung below.

## The rungs, with canonical code

| Rung | Canonical code | Verified anchor | Role |
|---|---|---|---|
| PersistentAgent lineage | `dharma_swarm/persistent_agent.py` (633L), `autonomous_agent.py` (1465L) | `PersistentAgent` @117, `AutonomousAgent` @384 | older standing/executing actor pattern |
| LivingAgentKernel durability | `dharma_swarm/operator_core/living_agent_kernel.py` (2921L) | `LivingAgentKernel` | durable wake ledger + leases + proof ledger + closeback |
| Holon runtime identity/governance | `holon_bridge.py` (`load_holon`), `holon_runtime.py` (`holon_wake_cycle`) | `load_holon` @106, `holon_wake_cycle` @53 | identity→runnable + govern-then-animate cycle |
| Holon system package | `dharma_swarm/holon_system/` | facade re-exports (this pass) | product-shaped navigation layer over all organs |
| Sarathi apex gateway | `dharma_swarm/holon_system/sarathi/` | `IMPLEMENTED = False` | apex chief-of-staff; specified, gated, not built |

## The load-bearing sentence

> Sarathi is not just a PersistentAgent. Sarathi is the apex holon that USES
> persistent-agent lineage + living-agent kernel + holon runtime + existing
> orchestration + A2A transport + deterministic reversibility gating, then ADDS
> operator-facing continuity — not a parallel rewrite.

## Why this matters for confusion control

The word "holon"/"agent" was collapsing five real strata into one. This ladder
is the de-collapse. When someone says "just make Sarathi a persistent agent,"
the answer is: a PersistentAgent has no reversibility gate, no gateway loop, no
operator brief, no whole-fleet map. Those are the apex additions, and they are
gated (see `06_PROOF_GATES.md`).

## Authority is an envelope, not a rank

The apex is MORE gated, not more powerful: reversible-safe autonomous floor,
irreversible-operator-only ceiling, enforced in code by
`operator_core/reversibility_gate.py` — not prose. See `05_SARATHI_APEX_MAP.md`.
