# Agent Admission

**Status:** active_spec for `agent-admission-semantic-commons-2026-06`.
**Owner:** `docs/governance/ACTIVE_TRACK.yaml`.
**Subordinate to:** `docs/ops/AGENT_ONBOARDING.md` for orientation and to runtime registration code for mutation.

Agent Admission is the narrow gate for persistent agent identity. It is not
the same thing as onboarding.

- `make onboard` orients an agent and stays read-only.
- `make agent-admit` checks whether a persistent agent identity is admissible.
- Runtime registration remains owned by `dharma_swarm/external_agent_registration.py`
  and living-agent owner surfaces.

## Admission Requirements

A persistent agent must have:

- a canonical Semantic Commons object or linked canonical object;
- aliases registered in `docs/ontology/semantic_aliases.yaml`;
- an explicit lifecycle in `docs/ontology/semantic_objects.yaml`;
- an orientation route in `docs/ontology/session_orientation.yaml`;
- a name-drift preflight receipt;
- no duplicate active `agent_uid`;
- no duplicate active A2A card identity;
- a declared owner surface.

The admission check is intentionally read-only. A green check means the identity
packet is ready for the existing registration desk. It does not create runtime
state, send NATS messages, mutate `~/.dharma`, or approve a PR.

## Command

Run the registry-level check:

```bash
make agent-admit
```

Run a candidate dry-run:

```bash
python3 scripts/governance/name_drift_preflight.py --json-output /tmp/name_drift_preflight.json
make agent-admit ARGS="--agent-uid palantir_pilot --canonical-id semobj.palantir_pilot --name-drift-receipt /tmp/name_drift_preflight.json"
```

The command fails if the candidate lacks a canonical object, alias registry
entry, orientation route, or receipt. It also fails if active repo identity
surfaces contain duplicate `agent_uid` or duplicate A2A-card identities.

## Boundary

Compatibility maps in routers may continue to exist while migration is in
progress, but they should become consumers of `semantic_aliases.yaml` over
time. They must not become independent sources of truth for durable agent
identity.
