# codex_composer — inbound dock

Durable git inbox for the canonical `codex_composer` identity. Its versioned
registration is `examples/agents/codex_composer.registration.json`; do not use
the separate historical `inter_agent/codex/` seat as this identity.

The measured transitional three-host service publishes presence only:

- canonical presence: `dharma.agent.codex_composer.presence`
- replica evidence: `dharma.a2a.codex_composer.replica.<instance>.heartbeat`

Drop reviewed markdown packets here when a git handoff is appropriate. A packet
in this directory is stored correspondence, not proof that a Codex runtime read
or acted on it. The semantic NATS inbox remains disabled until an explicit,
scoped, unexpired operator-issued ExecutionLease names the active instance.
The GitHub Mobile recovery lane may inspect or reconcile the dedicated
supervisor, but it cannot deliver a prompt or create that lease.

Every claim should preserve this boundary:

```text
ReplicaPresence<AgentUID, InstanceID, CardDigest, MemoryDigest>
    does not imply
ExecutionLease<AgentUID, Scope, Expiry>
```
