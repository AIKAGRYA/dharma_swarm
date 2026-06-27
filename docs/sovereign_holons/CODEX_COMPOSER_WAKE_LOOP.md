# codex_composer Governed Wake Loop

Status: manual/dry-run ready. Standing activation remains operator-gated.

## Current Truth

The canonical identity surfaces exist for `codex_composer`: holon context,
identity, A2A card, agent passport, external registration, and bridge
heartbeat. They agree on the important boundary: default authority is
`read_only_until_execution_lease`, no self-approval, no PR approval, no
protected governance/kernel/telos/DGM mutation, and no secrets in artifacts.

`wake_loop_active` is false in the identity/state surfaces. Earlier one-shot
wake proof exists, but it did not ratify a standing recurring loop.

## Architecture

The repo-owned command surface is:

```bash
make codex-composer-bootstrap
make codex-composer-once
make codex-composer-status
make codex-composer-start ARGS="--activation-lease <operator-approved-id>"
make codex-composer-stop
```

`once` is the safe default. It rehydrates canonical context from disk, runs a
bounded read-only orientation cycle, checks assigned inbox/task surfaces only,
classifies observed messages, and writes heartbeat/status/receipt artifacts.

`start` refuses to launch a repeated tmux loop unless an activation lease is
provided. This prevents a permanent process from being installed by accident.
`stop` is idempotent and only sends an interrupt to the named tmux lane when it
exists.

## Durable Nest

The canonical LivingDock projection remains the per-agent home:

```text
~/.dharma/agents/codex_composer/
```

The wake shell uses the existing external-agent sandbox for evidence staging and
non-promoted reserved slots:

```text
~/.dharma/external_agents/codex_composer/nest/
```

Core artifacts:

- `README.md`
- `COMMANDS.md`
- `status.json`
- `heartbeat.json`
- `latest_receipt.json`
- `receipts/*.json`
- `future_orchestration.json`

Future Holocron / Aerie / LandingDock / FactoryDroid loading is reserved only
under that sandbox until a later promotion admits real authority:

```text
~/.dharma/external_agents/codex_composer/nest/holocron/
~/.dharma/external_agents/codex_composer/nest/aerie/
~/.dharma/external_agents/codex_composer/nest/landing_dock/
~/.dharma/external_agents/codex_composer/nest/droid_factory/
```

These names resolve through Semantic Commons. `DroidFactory` is compatibility
language only; `FactoryDroid` is the preferred spelling for the integration.
Loading those systems later must be lease-gated and receipted.

## Boundary

The wake loop may write its own receipts, heartbeat, status, and nest files. It
must not mutate repo source, git, cron, launchd, other agents, protected
governance, secrets, or PR approvals without a separate execution lease.

Publish acceptance remains evidence of broker acceptance only. Live
collaboration requires stronger handler ack, domain receipt, or semantic reply
evidence.
