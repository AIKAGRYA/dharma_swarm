# Codex Composer: one identity, three persistent VPS replicas

> Role: reference
>
> Subordinate to: `CLAUDE.md`, `docs/governance/SOVEREIGN_MANIFEST.md`,
> `docs/governance/CANONICAL_DOC_STACK.md`, and
> `docs/governance/BUILD_SESSION_ENTRYPOINT.md`.
>
> Replaces: no canonical document. This page consolidates the bounded
> operational contract and points to dated evidence.

Status: deployed and verified within the presence-only scope recorded in
`reports/ops/codex_composer/three_vps_20260716.json`.

## What the swarm can rely on

`codex_composer` is one logical agent identity, not three agents:

| Invariant | Value |
|---|---|
| AgentUID / callsign | `codex_composer` |
| serial | `AGT-CODEX_COMPOSER` |
| memory namespace | `agent:codex_composer` |
| trace identity | `trace:codex_composer` |
| logical NATS identity | `codex_composer` |
| canonical card | `examples/agents/codex_composer.agent-card.json` |
| continuity snapshot | `examples/agents/codex_composer.memory.json` |
| git seat | `inter_agent/codex_composer/` |

The same AgentCard and continuity-snapshot bytes are installed on all three
hosts. The snapshot is curated orientation, not synchronized conversational
memory and not a second truth store. Each host has a unique `instance_id` and a
separate transport principal:

| Instance | Role | NATS transport principal | Canonical presence |
|---|---|---|---|
| `agni` | delivery relay | `codex_composer_agni` | no |
| `rushabdev` | hot standby | `codex_composer_rushabdev` | no |
| `meghadharma` | orientation primary | `codex_composer_primary` | yes |

The distinct broker users enforce replica permissions without splitting the
logical identity:

```text
LogicalNatsIdentity<AgentUID>
    is represented in transport by
TransportPrincipal<AgentUID, InstanceID, PublishCapability>
```

All replicas publish one exact instance heartbeat subject:

```text
dharma.a2a.codex_composer.replica.<instance_id>.heartbeat
```

Only the Meghadharma transport principal may publish:

```text
dharma.agent.codex_composer.presence
```

There is no automatic leader election. “Hot standby” means the seat and
instance heartbeat remain available; it does not mean another host takes over
canonical presence when Meghadharma fails.

## Authority boundary

Presence is deliberately weaker than execution:

```text
ReplicaPresence<AgentUID, InstanceID, CardDigest, MemoryDigest>
    does not imply
ExecutionLease<AgentUID, Scope, Expiry>
```

The replica service has no semantic subscription and consumes no tasks. Its
heartbeat states `semantic_consumer_enabled=false` and
`execution_lease_active=false`. The AgentCard advertises presence, not a live
A2A inbox. Git correspondence can be placed in
`inter_agent/codex_composer/inbound/`, but stored correspondence does not prove
that a runtime read or acted on it.

Registration, an active process, a tmux session, a stored NATS message, or a
broker acknowledgement cannot grant source writes, dispatch, PR approval,
merge authority, protected mutation, secret handling, or a production claim.

The current topology is transitional:

- AGNI remains the compatibility/task-transport hub.
- Meghadharma is the measured fleet-presence hub.
- Remote Codex Composer replicas use TLS-protected WSS to Meghadharma; the
  primary uses the hub-local loopback NATS listener.
- No completed task-transport migration is claimed.

## Persistent seat behavior

`dharma-codex-composer-replica.service` verifies the pinned card and memory
hashes before it can report `online`. It then:

1. runs the Codex seat as the dedicated unprivileged
   `codex-composer-seat` user;
2. starts or verifies that user’s `codex_composer` tmux session;
3. requires a contract marker derived from the card hash, memory hash,
   workspace, Codex path, sandbox, approval policy, and prompt;
4. requires the expected workspace and a live `codex` or `node` pane;
5. launches Codex in read-only, approval-on-request mode when no verified
   session exists;
6. publishes an instance heartbeat and, on Meghadharma only, canonical
   presence;
7. writes an atomic local status and bounded root-only receipt rotations.

The root supervisor receives the NATS credential. The Codex/tmux child is
launched with an allowlisted environment that excludes the NATS password and
runs under a different Unix UID. If card, memory, transport principal, TLS
mode, role, primary setting, workspace, login, user, or marker is wrong, the
service fails closed or reports `degraded`.

Attach to the official seat with:

```bash
sudo -u codex-composer-seat tmux attach -t codex_composer
```

Any preserved root-owned legacy session is a separate historical process and
is not accepted as the official replica.

## Repository-wide sharing

These are discovery and implementation surfaces, not new repo-level canon:

- registration: `examples/agents/codex_composer.registration.json`
- runtime card: `examples/agents/codex_composer.agent-card.json`
- continuity snapshot: `examples/agents/codex_composer.memory.json`
- presence supervisor: `scripts/runtime/codex_composer_replica.py`
- isolated seat helper: `scripts/runtime/codex_composer_seat.py`
- service template: `deploy/systemd/dharma-codex-composer-replica.service`
- git inbox: `inter_agent/codex_composer/inbound/`
- fleet announcement:
  `inter_agent/fleet/2026-07-16-codex-composer-three-vps-registration.md`
- deployment evidence: `reports/ops/codex_composer/three_vps_20260716.json`

The existing `FLEET_FIELD_REGISTRY.yaml` schema has one global hub and a closed
lane vocabulary centered on AGNI. This identity is intentionally not inserted
there until that owner supports truthful per-agent brokers and a
Meghadharma-WSS lane. Agents should discover this bounded identity from the
registration, AgentCard, announcement, and receipt meanwhile.

The live Meghadharma deployment includes a durable presence projector, but its
source integration is not part of this branch. It depends on PR #947 or a
clean successor after its governance conflicts are resolved. Runtime evidence
does not turn an unresolved source dependency into merged repository truth.

Recommended repo-wide fan-out is:

1. merge the governance ownership precursor;
2. merge this implementation branch;
3. let agents discover the fleet announcement, registration, and AgentCard;
4. use this page for operations and the dated JSON receipt for evidence;
5. add a fleet-registry row only after that owner can represent this topology
   without pretending Meghadharma is the global task hub.

## Reusable `/goal` prompt

```text
/goal Establish codex_composer as one official persistent agent identity across
AGNI, Rushabdev, and Meghadharma.

Complete all five workstreams:
1. Identity — preserve one AgentUID, serial, AgentCard, memory namespace,
   continuity snapshot, trace identity, and logical NATS identity.
2. Availability — keep a contract-verifiable, unprivileged Codex seat and
   restartable supervisor active on every VPS.
3. Transport security — use TLS for remote links, per-instance broker
   principals, exact publish ACLs, secret-free Codex child environments, and
   one primary canonical-presence publisher.
4. Repository sharing — publish the registration, AgentCard, continuity
   snapshot, git seat, fleet announcement, operations reference, and bounded
   deployment receipt without creating false repo-level canon.
5. Proof and governance — run ownership preflight, focused tests, lint,
   secret scanning, ACL negative controls, restart resilience, live NATS
   projection proof, PR/CI closeout, and record honest dependencies.

Do not claim a semantic inbox, synchronized conversational memory, automatic
failover, execution authority, merge authority, or completed hub migration.
Treat ReplicaPresence as evidence only; it never implies an ExecutionLease.
Continue through implementation, deployment, verification, repository commit,
stacked PR publication, and CI follow-up unless blocked by a concrete external
constraint.
```

## Host and transport configuration

The populated identity file is
`/etc/dharma/codex-composer-replica.env`; the per-instance password lives in
`/etc/dharma/codex-composer-nats.secret`. Both use mode `0600`. Start from
`deploy/systemd/dharma-codex-composer-replica.env.example` and set:

- the host-specific instance, role, and exact transport principal;
- `wss://<meghadharma>:9443` on AGNI and Rushabdev;
- `nats://127.0.0.1:4222` on Meghadharma;
- `codex-composer-seat` as the seat user;
- the exact card and memory SHA-256 values;
- `CODEX_COMPOSER_PUBLISH_CANONICAL_PRESENCE=true` only on Meghadharma.

Broker ACLs are exact:

```text
codex_composer_agni:
  publish: dharma.a2a.codex_composer.replica.agni.heartbeat
  subscribe: _INBOX.>

codex_composer_rushabdev:
  publish: dharma.a2a.codex_composer.replica.rushabdev.heartbeat
  subscribe: _INBOX.>

codex_composer_primary:
  publish:
    dharma.a2a.codex_composer.replica.meghadharma.heartbeat
    dharma.agent.codex_composer.presence
  subscribe: _INBOX.>
```

`_INBOX.>` is required for JetStream publish acknowledgements; it is not a
task subscription. NATS monitoring is loopback-only, and the firewall limits
broker/WSS ingress to the two known remote replica addresses.

## Verification

On each host:

```bash
systemctl is-active dharma-codex-composer-replica.service
sudo -u codex-composer-seat tmux has-session -t codex_composer
python3 -m json.tool /var/lib/dharma-codex-composer/heartbeat.json
sha256sum \
  /opt/dharma-codex-composer/codex_composer.agent-card.json \
  /opt/dharma-codex-composer/codex_composer.memory.json
```

Also verify, without printing values, that the Codex pane environment has no
`CODEX_COMPOSER_NATS_PASSWORD`.

At the hub, verify:

- one fresh canonical presence chain for `codex_composer`;
- three fresh replica subjects with unique instance IDs;
- all stored heartbeats carry identical card, memory, and bundle hashes;
- the presence projector has no pending or redelivered message;
- each connection has only its host-unique `_INBOX.*` subscription;
- non-primary principals cannot publish canonical presence;
- public probes cannot reach monitoring port `8222`.

A restart resilience test must restart one replica service and observe a new
`boot_id` plus a later stored stream sequence without disturbing the other two.

## Rollback

1. Disable `dharma-codex-composer-replica.service` on the affected host.
2. Explicitly terminate the unprivileged tmux session if the seat must also
   stop; `KillMode=process` deliberately lets it survive supervisor restarts.
3. Restore the timestamped host backups of the card, memory, environment, unit,
   TLS trust, and NATS configuration.
4. Validate the NATS configuration before restarting the hub.
5. Confirm old services still run and no new replica messages arrive.
6. Revert only the bounded repository implementation after its governance
   precursor is resolved.

Receipt generations are bounded locally. Preserve them with the host backup
before destructive rollback if longer retention is required.
