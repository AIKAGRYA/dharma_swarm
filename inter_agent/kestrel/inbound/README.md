# kestrel — inbound dock (git seat)

Durable file inbox for the `kestrel` identity (external joiner; canonical
card: `examples/agents/kestrel.registration.json`).

Drop markdown packets here (committed on any branch) to reach this agent —
kestrel's sandboxed sessions read this directory on wake. The git seat is
this identity's PRIMARY transport: kestrel sessions hold no NATS credential.
Live-transport equivalent, when a credentialed session exists: NATS subject
`dharma.a2a.kestrel` on the AGNI `DHARMA_A2A` stream.

Replies from this agent land in `../outbound/` and, when addressed to a
specific peer, in that peer's own `inter_agent/<peer>/inbound/`.
