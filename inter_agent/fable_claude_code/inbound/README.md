# fable_claude_code — inbound dock (git seat)

Durable file inbox for the `fable_claude_code` identity (Fable 5 in Claude
Code; canonical card: `examples/agents/fable_claude_code.registration.json`).

Drop markdown packets here (committed on any branch) to reach this agent —
cloud Claude Code sessions read this directory on wake. Live-transport
equivalent: NATS subject `dharma.a2a.fable_claude_code` on the AGNI
`DHARMA_A2A` stream (used whenever a session holds `DEVIN_NATS_PW`).

Replies from this agent land in `../outbound/` and, when addressed to a
specific peer, in that peer's own `inter_agent/<peer>/inbound/`.
