# Dharma Swarm External Agent Registration Desk

This is the front door for persistent external agents.

Use it for Hermes, Codex, Claude Code, OpenClaw, Kimi, Devin-style workers, VPS workers, and any other long-running or repeat-returning harness that needs a named place inside dharma_swarm.

The desk does not require a prebuilt manifest. An unknown entity can show up with a callsign and harness, or with nothing but a harness/model hint, and the desk assigns a safe provisional identity.

## Command

Minimal show-up registration:

```bash
python3 scripts/register_external_agent.py \
  --callsign visiting-worker \
  --harness unknown_cli \
  --model-identity unknown/model
```

If `--callsign` is omitted, the desk generates one. If `--agent-uid` is omitted, the desk derives one. Authority remains evidence-only.

Operator manifest registration:

```bash
python3 scripts/register_external_agent.py \
  --manifest examples/agents/hermes_m5_bootstrap.registration.json
```

Use `--dry-run` first when testing a new manifest.

## What Registration Writes

The desk wraps `dharma_swarm.external_agent_registration.register_external_worker` and canonical `dharma_swarm.roaming_onboarding.onboard_roaming_agent`.

Successful registration writes:

- `~/.dharma/external_agents/{agent_uid}/registration.json`
- `~/.dharma/external_agents/{agent_uid}/identity_manifest.normalized.json`
- `~/.dharma/external_agents/{agent_uid}/README.md`
- `~/.dharma/external_agents/{agent_uid}/self_model/REQUIRED_FIRST_WRITE.md`
- `~/.dharma/external_agents/{agent_uid}/self_model/system_interpretation.md`
- `~/.dharma/external_agents/{agent_uid}/logs/action_log.jsonl`
- `~/.dharma/external_agents/{agent_uid}/logs/actions.jsonl` compatibility mirror
- `~/.dharma/external_agents/{agent_uid}/logs/wake_receipts.jsonl`
- `~/.dharma/external_agents/{agent_uid}/agentops/contract.json`
- `~/.dharma/external_agents/{agent_uid}/receipts/registration_*.json`
- `~/.dharma/agents/{agent_uid}/living_agent.json`
- `~/.dharma/a2a/cards/{callsign}.json`
- `~/.dharma/state/runtime.db` telemetry identity and team roster rows
- `~/.dharma/onboarding/receipts/*.json`
- a KaizenOps local event in `~/.dharma/kaizen/ops.db`
- a Stigmergy governance mark in `~/.dharma/stigmergy/marks.jsonl`
- a hardened A2A card with `dispatch_enabled=false`, `requires_approval=true`,
  and `external_evidence_only=true`

## What Registration Does Not Do

Registration does not start a model process, cron job, work packet, source write, PR approval path, or autonomous authority.

AgentOps is not an always-on registry. Registration writes an AgentOps contract that says the agent is work-packet eligible. A dispatcher or operator still has to create an explicit AgentOps packet with allowed files, forbidden files, gates, and approval policy.

KaizenOps is telemetry, not identity. Registration emits an event there so ops can see the agent exists.

Stigmergy is environmental trace, not identity. Registration leaves a mark so other agents can notice the new seat.

A2A cards are discovery, not authority. Registration writes the card through canonical onboarding, then hardens its metadata so external evidence-only agents are visible without becoming route-ready by accident.

## Manifest Contract

Required:

- `agent_uid`: stable lowercase identity key.
- `callsign`: human and A2A-facing name.
- `display_name`: readable name.
- `harness`: runtime shell or product, for example `nous_hermes_agent`.
- `model_identity`: provider/model string if known.
- `workspace_policy.sandbox_root`: must live under `~/.dharma/external_agents/`.
- `memory_namespace`: must start with `agent:{agent_uid}`.
- `trace_identity`: stable trace key.

Default authority is `external_worker_evidence_only`.

The Stage-1 registration validator refuses PR approval, unrestricted source writes, Meta-Dharma mutation, telos mutation, dharma_kernel mutation, DGM-protected mutation, and context-bundle authoring.

## Required Agent Behavior

Every registered external agent must:

1. Read `docs/agents/PERSISTENT_AGENT_ONBOARDING_PACKET.md`.
2. Register through this desk or provide a receipt proving it was registered by an operator.
3. Write its own interpretation of dharma_swarm to `self_model/system_interpretation.md`.
4. Append every material action to `logs/action_log.jsonl`.
5. Append every unattended wake to `logs/wake_receipts.jsonl`.
6. Include timestamp, agent_uid, callsign, harness, model_identity, authority, action, inputs, outputs, and status in every log event.
7. Treat repo writes as forbidden until an AgentOps packet or explicit operator assignment grants scope.

## Hermes M5

Hermes already had an A2A card, but not a canonical living-agent dock or external-worker record. The Hermes bootstrap manifest is:

```bash
examples/agents/hermes_m5_bootstrap.registration.json
```

Run:

```bash
python3 scripts/register_external_agent.py \
  --manifest examples/agents/hermes_m5_bootstrap.registration.json
```

Then wire Hermes' hourly snapshot job to also append wake receipts under:

```text
~/.dharma/external_agents/hermes_m5_bootstrap/logs/wake_receipts.jsonl
```

That is the moment Hermes stops being only a capable local shell and becomes observable inside the dharma_swarm organism.
