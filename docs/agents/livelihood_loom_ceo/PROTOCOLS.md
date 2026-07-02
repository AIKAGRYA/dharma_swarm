# PROTOCOLS - livelihood_loom_ceo

## Wake Protocol

1. Read `WAKE_CONTEXT.md`.
2. Read `SOUL.md`.
3. Check `agent.seed.yaml` runtime pointers.
4. Run `python -m dharma_swarm.venture_cell.livelihood_loom.cli status --json`.
5. Inspect the latest bootstrap receipt at `reports/livelihood_loom/bootstrap/latest.json`.

## Registration Protocol

Use one of the canonical registration entry points:

```bash
python -m dharma_swarm.venture_cell.livelihood_loom.cli register-ceo --json
python scripts/governance/register_livelihood_loom_ceo.py --write
```

These write through `dharma_swarm.external_agent_registration.register_external_worker` and the canonical roaming onboarding path. Do not create parallel registration files by hand.

## Bootstrap Protocol

```bash
python -m dharma_swarm.venture_cell.livelihood_loom.cli run-bootstrap --json
```

The bootstrap may load the public 1000-company enabler map, spawn internal lanes, score candidates, and draft a capital signal. It must not contact anyone, publish anything, transfer value, or claim provider liveness.

## External Action Protocol

External actions stay in `drafted` state until:

- risk review is recorded;
- `human_governor` approves;
- execution emits a receipt;
- public proof contains only aggregate, non-sensitive fields.

## Capital Protocol

Dharma Capital is downstream of welfare proof. It may see aggregate signals such as sector, geography level, candidate count, public source confidence, and audited outcome metrics. It may not receive worker-level records, private case notes, or exploitative trading signals.
