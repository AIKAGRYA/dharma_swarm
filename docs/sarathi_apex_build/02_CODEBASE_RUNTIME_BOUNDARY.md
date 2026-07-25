# 02 — Codebase / Runtime Boundary Verdict

> **Dated lane detail:** The boundary principle remains valid, but counts and
> the dated surface witness defer to
> [`../architecture/HOLON_RUNTIME_FULL_ESTATE_MAP.md`](../architecture/HOLON_RUNTIME_FULL_ESTATE_MAP.md);
> current operating state remains owned by onboarding and Live Ops.

## Verdict

Keep the boundary. Do **not** merge repo and runtime homes.

| Home | Verdict | Role |
|---|---|---|
| `dharma_swarm/` | Source of truth for code | Python modules, tests, schemas, docs, proof gates, CLIs. |
| `~/.dharma/` | Mutable runtime state | Identities, inboxes, heartbeats, ledgers, wake receipts, local runtime wrappers. |
| `~/.hermes/` | Side ecosystem | NousResearch Hermes Agent product checkout/runtime; `hermes-m5` is a field-ops peer, not dharma holon lineage. |

## Five identity homes currently in play

1. `~/.dharma/agents`
2. `~/.dharma/ginko/agents`
3. `docs/agents`
4. `~/.dharma/a2a/cards`
5. `~/.dharma/external_agents`

Known drift includes hyphen/underscore aliases, stale identities, and provider
enum mismatch (`fugu_ultra` / `sakana`). This lane records the drift and points
to the agent-admission semantic-commons track as owner of remediation; it does
not normalize runtime state.

## Boundary rule

- Runtime wrappers under `~/.dharma` must stay thin and import repo-owned code.
- Runtime heartbeats/inboxes/receipts are mutable evidence and must not be
  committed as source.
- Source-like code for Sarathi belongs under `dharma_swarm/holon_system/sarathi/`
  once Phase C unlocks.
- A file in `~/.dharma/agents/sarathi` can be a prompt, identity, or wrapper; it
  cannot be the canonical implementation of Sarathi.

## Anti-overclaim rule

`identity.json`, `SOUL.md`, `BOOT.md`, compass counts, or an A2A card prove that
a named seat exists. They do not prove that a breathing holon is running. Alive
requires wake receipts and the proof gates in `06_PROOF_GATES.md`.
