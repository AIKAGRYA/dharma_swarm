# 03 — Holon System Code Map and Hermes-Organ Comparison

> **Historical lane map:** This describes the pre-merge collapse plan, including
> surfaces subsequently deleted or rebuilt. Use
> [`../architecture/HOLON_RUNTIME_FULL_ESTATE_MAP.md`](../architecture/HOLON_RUNTIME_FULL_ESTATE_MAP.md)
> for the current body synthesis and dated readiness witness.

## Core distinction

```text
holon_system = identity + provider routing + persistent wake kernel + governed runtime +
               orchestration + A2A transport + semantic responders + gateway +
               observability + packaging/CLI + proof gates

Sarathi = apex occupant/wrapper of holon_system
```

## Verified bodies in the estate

| Body | Size/status | Decision in this lane |
|---|---|---|
| `dharma_swarm/holon_*.py` + `scripts/holon_*.py` | Canonical runtime body, four layers: identity, liveness, work-authority, completion-proof. | Reuse. |
| `holon/` fork package | Standalone fork redefining `load_holon` and `holon_wake_cycle`; only two known importers. | Delete in Phase B after migration. |
| `dharma_swarm/holon_system/` dead scaffold on magpie | Dead scaffold from dirty branch, zero external importers. | Do not port; rebuild fresh facades in Phase C. |
| Legacy stack (`persistent_agent.py`, `autonomous_agent.py`, `agent_registry.py`, `agent_runner.py`, `swarm.py`) | Live/load-bearing substrate. | Do not retire or refactor in this lane. |

## Hermes-like organs

| Organ | Dharma status | Current gap |
|---|---|---|
| Identity / registry | Exists | Scattered across registry, runtime identities, A2A cards. |
| Provider routing | Exists | Needs safe `@frontier`/wake-time routing boundaries before broad use. |
| Persistent wake kernel | Exists | LivingAgentKernel and holon runtime are not yet product-shaped under one facade. |
| Governed runtime | Exists | Reversibility gate now ported; collapse guard still must go green. |
| Orchestration | Exists | Reuse existing orchestrator/swarm; no second spine. |
| A2A transport | Exists | Runtime state can drift; not fixed here. |
| Semantic responders | Partial | Codex/Fable/Sarathi wake shells exist as profile pattern; proof varies by seat. |
| Gateway | Missing/partial | Sarathi gateway package and runtime wrapper are Phase C. |
| Observability | Partial | Receipts/checks exist; product-shaped scoreboard/gates still needed. |
| Packaging/CLI | Partial | `dgc` exists; holon-system facade CLI is future work. |
| Proof gates | Now explicit | `sprawl_guard.py` is the collapse done gate. |

See also the committed architecture maps:

- `docs/architecture/AGENT_HOLON_CODE_MAP.md`
- `docs/architecture/HOLON_RUNTIME_FULL_ESTATE_MAP.md`
