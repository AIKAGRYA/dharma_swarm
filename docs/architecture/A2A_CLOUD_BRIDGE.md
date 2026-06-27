# A2A Cloud-Agent Bridge

Status: active-track design doc for `a2a-cloud-agent-bridge-2026-06`.

The bridge admits cloud-resident agents into the same A2A/NATS substrate used by
local agents. It is a transport adapter, not a new task format, receipt owner,
or public ingress service.

## Contract

- Cloud agents register as `kind: cloud_agent` in `dharma_swarm/a2a/contact_registry.py`.
- A cloud packet uses `schema_version: dharma.a2a.cloud_contact.v1`.
- The adapter maps the packet into an existing `A2ATask`.
- `A2ANatsTransport` publishes the task and owns JetStream publish receipts.
- The denominator verifier counts cloud agents separately from local launchd/tmux agents.
- Liveness is not implied by registration. It requires the same transport receipt class as local agents.

## Threat Model

- No public HTTP ingress is opened by this track.
- No external account, spend, or hosted endpoint is touched.
- Future webhook ingress must require per-agent authentication before it can call the local adapter.
- Unsigned or unregistered cloud agents must not enter the A2A task path.
- The bridge must never create a second receipt store or bypass `RuntimeStateStore`.

## Current Population

- `codex_composer`: local agent.
- `claude-code`: local agent.
- `hermes-m5`: local agent.
- `perplexity-computer`: cloud agent.

## Verification

The local round-trip test proves:

- a cloud-agent packet becomes an `A2ATask`;
- the task is published through the existing NATS transport;
- the consumer path can dispatch the task without operator copy/paste transport;
- runtime receipts include both `nats_publish` and `nats_consume`.
