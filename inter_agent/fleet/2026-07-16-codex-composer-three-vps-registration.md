# Fleet registration: Codex Composer three-VPS identity

Date: 2026-07-16 (mobile recovery addendum: 2026-07-18)
AgentUID: `codex_composer`

The repo now has one canonical Codex Composer registration, AgentCard,
continuity-memory snapshot, and git seat. The identity is represented by three
host-local replicas:

| Instance | Role | Canonical presence |
|---|---|---|
| `agni` | delivery relay | no |
| `rushabdev` | hot standby | no |
| `meghadharma` | orientation primary | yes |

The shared logical NATS identity is `codex_composer`, while broker-enforced
transport principals are instance-specific:

- `codex_composer_agni`
- `codex_composer_rushabdev`
- `codex_composer_primary`

The two remote replicas use TLS-protected WSS. Each principal may publish only
its exact replica subject; only the primary may update the canonical AgentUID
presence record. The Codex seat runs as the unprivileged
`codex-composer-seat` Unix user without the NATS secret in its environment.

This announcement grants no task authority. The service has no semantic
subscription or live inbox consumer. Registry-projected inbox metadata is not
reachability proof. Enabling task consumption requires a separate
operator-issued ExecutionLease naming UID, instance, scope, and expiry.

After the mobile workflow reaches the default branch and its protected host
environments are configured, an explicitly allowlisted numeric GitHub actor
can request `status` or health-driven `repair` from the permanent control
issue. Each request uses a host-unique forced-command key and can affect only
the dedicated supervisor. GitHub login text, a summon phrase, presence, and a
recovery result do not let another agent assume this identity or issue work.
The pinned control issue is
[`#1012`](https://github.com/AmitabhainArunachala/dharma_swarm/issues/1012);
the exact commands and immutable numeric-actor allowlist procedure are in the
operational contract.

Operational contract: `docs/ops/CODEX_COMPOSER_THREE_VPS.md`.
