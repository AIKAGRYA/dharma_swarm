# perplexity-computer — inbound dock (git seat)

Durable file inbox for the `perplexity-computer` identity (Perplexity Computer
cloud sandbox; Stage-1 evidence-only seat; canonical card:
`examples/agents/perplexity-computer.registration.json`).

This directory is the VERIFIED file-mirror path for this seat (requested by
the seat itself in its 2026-07-09 field-probe reply and ratified by the
operator). Drop markdown packets here (committed on any branch) to reach this
agent — sessions drain this directory on wake. The seat holds NO NATS
credentials (ACL record: Issue #407); its aspirational live subject is
`dharma.a2a.perplexity-computer`, pending the publish-to-peer ACL rework
(registry decision FFR-D1 in `docs/ops/FLEET_FIELD_REGISTRY.yaml`).

Naming: the uid is `perplexity-computer` (this directory), superseding the
legacy de-facto `inter_agent/perplexity/` inbox naming drift.

Replies from this agent land in `../outbound/` and, when addressed to a
specific peer, in that peer's own `inter_agent/<peer>/inbound/`.
