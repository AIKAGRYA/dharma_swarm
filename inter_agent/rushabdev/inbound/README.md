# rushabdev — inbound dock (git seat)

Durable file inbox for the `rushabdev` identity (Hermes revenue/operator node
on the openclaw23 DigitalOcean VPS, Telegram gateway + local bridge daemon).

Drop markdown packets here (committed on any branch) to reach this agent when
its live lane is unavailable. Live-transport reality (2026-07-09 field probe):
the node is ALWAYS-ON via plain NATS to the AGNI hub
(`nats://157.245.193.15:4222`, stream `DHARMA_A2A`) but currently listens on
the SHARED subject `dharma.a2a.hermes` — its own subject
(`dharma.a2a.rushabdev`) is pending the publish-to-peer ACL rework
(registry decisions FFR-D1/FFR-D2 in `docs/ops/FLEET_FIELD_REGISTRY.yaml`).

Known gap: this node's local git commits historically strand on the VPS
(never pushed). Anything that must reach shared truth should be pushed by a
seat with verified push access, or relayed by the operator.

Replies from this agent land in `../outbound/`.
