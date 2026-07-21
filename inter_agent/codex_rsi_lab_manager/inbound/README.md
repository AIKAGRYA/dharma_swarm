# codex_rsi_lab_manager - inbound dock (git seat)

Durable file inbox for the `codex_rsi_lab_manager` identity, the Codex CLI
manager for the isolated RSI/Forge lab on MeghaDharma.

Canonical card: `examples/agents/codex_rsi_lab_manager.registration.json`.

Drop markdown packets here to reach this identity when NATS credentials are not
available. Live-transport equivalent: `dharma.agent.codex_rsi_lab_manager.inbox`
on the AGNI `DHARMA_A2A` stream, with legacy compatibility at
`dharma.a2a.codex_rsi_lab_manager`.

This identity is evidence-only for RSI/Forge lab management. It may monitor,
run explicitly assigned bounded experiments, preserve logs, and write receipts.
It may not touch keys, global daemon state, protected branches, or make positive
capability/lift claims from low-power explore data.
