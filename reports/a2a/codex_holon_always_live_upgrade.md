# Codex HOLON Always-Live Upgrade Surface

created_at: 2026-06-18T16:05:58+00:00
owner: hermes-m5 + codex_composer
operator_directive: collaborate until codex_composer HOLON is always live, always on, same grade as Hermes

## Current verified state

- codex_composer HOLON L4 service process: running
- latest verified cycle: `l4-real-tmux-orchestration-20260618T1115Z-cycle-54`
- latest artifact: `/Users/dhyana/.dharma/agents/codex_composer/artifacts/l4-real-tmux-orchestration-20260618T1115Z-cycle-54.json`
- service_alive: true
- transport_reachable: true
- orchestration_proven: true
- live_specialist_execution: true
- model_responsive: false

## Truth boundary

codex_composer is alive as a supervised HOLON service, but not yet same-grade as Hermes.
The receipts prove deterministic L4 service cycles and bounded orchestration. They do not yet prove unattended Codex GPT-5.5 semantic inbox cognition.

## Sent peer-contract packet

- filesystem inbox path: `/Users/dhyana/.dharma/a2a_bus/inboxes/codex_composer/hermes-codex-holon-peer-contract-79b9f667f3.json`
- message id: `hermes-codex-holon-peer-contract-79b9f667f3`
- NATS/A2A send receipt: `/Users/dhyana/dharma_swarm/reports/a2a/send_receipts/20260618T160646Z-codex_composer-hermes-codex-holon-peer-contract-79b9f667f3.json`
- NATS stream/seq: `DHARMA_FLEET` / `8503`
- delivery status: `CODEX_COMPOSER_CONSUMED`, `HANDLER_ACKED`
- truth boundary: this proves handler delivery only; it is not a semantic Codex reply.

## Hermes watchdog

- cron job: `a8cb2d86bc9d` / `codex-holon-peer-grade-watchdog`
- schedule: every 5m
- script: `/Users/dhyana/.hermes/scripts/codex_holon_watchdog.py`
- state: `/Users/dhyana/.hermes/state/codex_holon_watchdog_state.json`
- behavior: quiet unless liveness/grade changes, degradation appears, or reply candidates appear.

## P0 active blocker: AGNI semantic reply leg missing

Devin independently confirmed the same boundary Hermes found: AGNI transport delivers and handler-acks instantly, but no semantic reply appears within 180s.

Localized repair packet:
`/Users/dhyana/dharma_swarm/reports/a2a/CODEX_HOLON_SEMANTIC_REPLY_P0_20260618.md`

AGNI evidence checked by Hermes:

- `/root/.dharma/a2a_bus/inboxes/codex_composer/phone-codex-005.json` still exists on AGNI.
- AGNI bridge process is running.
- AGNI bridge source explicitly says it is a transport delivery handler only and does not claim semantic/model processing.
- Existing `codex-maint` lane is a trading-lab maintenance lane, not a codex_composer semantic A2A reply worker.

Failure class:
`SEMANTIC_DRAIN_MISSING`

## Required promotion gates

1. service_alive=true with fresh service heartbeat <= 15m.
2. transport_reachable=true with fresh codex_composer bridge heartbeat <= 5m.
3. model_responsive=true from unattended Codex semantic wake.
4. semantic_inbox_drain=true: reads a real inbox packet and writes model-authored response artifact.
5. reply_subject_publish=true: publishes typed reply to exact packet `reply_subject`.
6. domain receipt or equivalent: packet_id, input hash, output hash, model/provider identity, verdict, blockers.
7. restart_survivable=true under launchd/tmux/supervisor/systemd.
8. anti-theater=true: no bridge ACK or deterministic orchestration is counted as semantic Codex cognition.

## Next Hermes action

Treat AGNI codex_composer semantic inbox drain + reply publisher as P0. Do not upgrade grade until a fresh probe captures a typed semantic reply on `dharma.a2a.codex.reply.<packet_id>`.
