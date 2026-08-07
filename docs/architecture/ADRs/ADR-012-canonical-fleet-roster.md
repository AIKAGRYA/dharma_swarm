# ADR-012: Canonical Fleet Roster

> **Date:** 2026-08-07
> **Status:** PROPOSED (awaiting operator ratification)
> **Decision:** Establish one canonical fleet roster as the single owner of agent identity, subject routes, model, host/node, capabilities, authority tier, and liveness/contact metadata. Competing projections remain subordinate adapters and must not independently define routing or authority.

---

## Context

The repository currently has several roster and identity projections:

- `docs/ops/FLEET_FIELD_REGISTRY.yaml` — field-probed routing and connectivity registry;
- `dharma_swarm/a2a/contact_registry.py` — built-in contacts;
- `dharma_swarm/agent_directory.py` — merged directory projection;
- Agent Cards and runtime identity/presence projections;
- `ACTIVE_SURFACE_MANIFEST.yaml` — declared surface ownership, not a complete live roster.

The survey found no single roster owning all identity, subject, model, host, capability, and verified liveness dimensions. This is a direct scaling hazard for a 50-agent system.

The field registry documents concrete seams:

- **FFR-D2 Hermes/rushabdev collision:** `docs/ops/FLEET_FIELD_REGISTRY.yaml:84-122` records AGNI Hermes with UID `hermes` while rushabdev also listens on `dharma.a2a.hermes`; the registry identifies the collision and leaves FFR-D2 OPEN.
- **Devin compatibility-subject-only drain:** `docs/ops/FLEET_FIELD_REGISTRY.yaml:124-141` records stable UID `devin-roaming-2987d222` while the compatibility route is `dharma.a2a.devin`; the compatibility process does not drain the UID inbox plus reply/ACK routes.
- **Perplexity naming drift:** `docs/ops/FLEET_FIELD_REGISTRY.yaml:179-195` resolves `perplexity` versus `perplexity-computer` in favor of UID `perplexity-computer`.
- **Competing in-code names:** `contact_registry.py:110-152` includes names such as `claude-code` and `hermes-m5` that do not line up one-for-one with field-registry names such as `fable_claude_code` and `hermes`.

## Decision

Create and ratify one canonical fleet roster. Its records own:

| Field family | Required contents |
|---|---|
| identity | stable UID, callsign, registration/card identity |
| routing | UID inbox, compatibility route, reply/ACK routes, broker/node |
| execution | model, provider/harness, host/VPS |
| capability | declared capabilities and capability-gated claim eligibility |
| authority | `command` / `worker` tier and delegation limits |
| liveness | transport contact, heartbeat projection, last verified send/receive |
| lifecycle | registered, probed, live, blocked, retired, collision state |

All other registries become projections or adapters. They may provide evidence into the canonical roster, but they may not silently mint a competing subject, UID, or authority assignment.

The canonical roster must generate subject routes through `scripts/runtime/a2a_topology.py` and must distinguish:

- live transport contact;
- recent heartbeat/last-seen projection;
- registered but unprobed;
- operator-relay-only;
- blocked or colliding identity.

## Consequences

### Positive

- One subject derivation for direct probes and operator routing.
- FFR-D2, Devin route coverage, and Perplexity naming drift become explicit reconciliation work.
- Authority and capability decisions can scale beyond ten agents without relying on callsign convention.
- Presence truth levels remain visible rather than merged into one misleading green dot.

### Negative

- Existing registries need migration and reconciliation.
- A roster owner and change process must be chosen.
- Agent Card signature enforcement remains necessary; a canonical record alone does not authenticate a publisher.

### Neutral

- `FLEET_FIELD_REGISTRY.yaml` remains valuable field evidence during migration.
- This ADR does not decide whether the live hub topology is `DHARMA_A2A` or `DS_*`.

## Enforcement

Milestone M0 in `docs/architecture/FLEET_COMMAND_OPERATOR_SURFACE.md` is the first enforcement bar:

1. resolve FFR-D2's Hermes/rushabdev collision;
2. make Devin drain UID inbox plus reply/ACK routes;
3. close `perplexity-computer` naming drift;
4. probe every agent using subjects derived solely from the canonical roster.

Until M0 is complete, the Fleet Command client must display roster status as reconciled, colliding, unprobed, or relay-only rather than treating every declared identity as live.

## Options considered

| Option | Verdict |
|---|---|
| Keep `FLEET_FIELD_REGISTRY.yaml`, contact registry, Agent Cards, and presence lists independently authoritative | ✗ preserves subject collisions and identity drift |
| Let the phone client maintain its own dispatch catalog | ✗ creates a third routing authority and repeats the original Fleet Hub error |
| **One canonical roster with subordinate evidence/projection surfaces (CHOSEN)** | ✓ makes identity single-valued while preserving existing field evidence |

## Related decisions

- `docs/architecture/FLEET_COMMAND_OPERATOR_SURFACE.md`
- `docs/architecture/ADRs/ADR-011-operator-actions-through-taskboard.md`
- `docs/ops/FLEET_FIELD_REGISTRY.yaml`
- `scripts/runtime/a2a_topology.py`
- `dharma_swarm/a2a/agent_presence.py`

## Status history

- **2026-08-07** — PROPOSED on the Fleet Command operator-surface branch; operator ratification by merge remains pending.
