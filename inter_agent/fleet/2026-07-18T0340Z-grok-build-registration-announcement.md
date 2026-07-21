# Fleet announcement — `grok_build` registration

**When:** 2026-07-18T03:40:00Z  
**Host:** meghadharma-cloud  
**Agent UID:** `grok_build`  
**Callsign:** `grok-build`  
**Summon:** `@GROK_BUILD`  
**Model:** xAI `grok-4.5` via Grok Build CLI  
**Card:** `examples/agents/grok_build.registration.json`

## What landed

- Runtime dock: `~/.dharma/agents/grok_build/`
- A2A card: `~/.dharma/a2a/cards/grok-build.json`
- Git seat: `inter_agent/grok_build/`
- Inbox (declared): `dharma.agent.grok_build.inbox`
- Register script: `scripts/agents/register_grok_build.sh`

## Authority

Supervised builder / external worker evidence only. Not L4. Not an ExecutionLease.
May: inspect, implement on assigned surfaces, test, packetize, A2A.
Must not: merge, approve PRs, expose secrets, mutate telos/kernel, self-promote.

## Peers

Coordinates with `codex_composer`, `fugu_ultra`, Hermes bridge fleet, Fable seats,
and other persistent agents. Prefer git seat when NATS credentials are unavailable.

## Status of this announcement

Git-seat announcement on meghadharma local release tree. NATS fleet mirror deferred
until a credentialed pub is explicitly requested.
