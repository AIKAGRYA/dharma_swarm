# Context Packet System Metabolized Handoff

Date: 2026-07-02
Branch: `agent/magpie-seed`
Mode: audit-discoverable handoff, no runtime authority
Search tags: `CONTEXT_PACKET_CLOSEOUT`, `AGENT_OFFBOARD_RECEIPT`, `OFFBOARD_V0_0_0_1`

## Essence

This lane turned the context packet library from generic onboarding prose into
organ-specific agent work contracts.

Each packet now tells a future agent:

- which highest-vision docs shape the work;
- which current-reality anchors must be checked before claims;
- which dense docs/code/reports form the organ anatomy;
- which work lanes, blockers, gates, and TODOs matter now;
- which evidence can be cited and which sources are only projections;
- which future-agent review questions must be answered;
- what handoff receipt shape to leave.

## Durable Surfaces

- `docs/context_engineering/README.md`
- `docs/context_engineering/PACKET_SCHEMA.md`
- `docs/context_engineering/CONTEXT_PACKET_INDEX.json`
- `docs/context_engineering/packets/*.md`
- `scripts/governance/context_packet_router.py`
- `tests/test_context_packet_router.py`
- `docs/ops/AGENT_OFFBOARDING.md`
- `scripts/governance/agent_offboard.py`
- `tests/test_agent_offboard.py`
- `Makefile` target: `make offboard`

## Multi-Agent Council

The context-packet upgrade requested five parallel lanes. All five responded.

- Volta: packet content and organ-anchor audit
- Popper: schema, router, and test upgrade design
- Ramanujan: bleeding-edge context-engineering critique
- Codex Composer: governance handoff and council requirement
- Lovelace: future-agent workflow and plain-language use pattern

Consensus:

- Add explicit `Vision Anchors`, `Current Reality Anchors`, `Dense Docs`,
  `Work-Lane Anchors`, `Evidence Boundary`, and `Future-Agent Review Hooks` to
  every packet.
- Make `CONTEXT_PACKET_INDEX.json` the machine-readable v1.1 source of anchor
  metadata.
- Keep packet Markdown as the human work contract.
- Teach the router to validate and expose anchors without parsing Markdown.
- Require future packet evolution to request a multi-agent/model council when
  practical; if not possible, record a skip/failure receipt.

Runtime note:

- The first full-history subagent spawn attempt failed because full-history
  forks inherit role/model. The fallback was to spawn non-forked agents with
  explicit repo/task context. This still produced five responding lanes.

## Offboard V0.0.0.1

`make offboard` was added as the lifecycle complement to `make onboard`.

- `make onboard`: start with current operating reality.
- `make offboard`: finish with a handoff receipt for the next agent/auditor.

Default receipts:

- `~/.dharma/ops/offboard_receipt.json`
- `~/.dharma/ops/offboard_receipt.md`

Optional durable repo receipts:

- `reports/handoffs/offboard/*.json`
- `reports/handoffs/offboard/*.md`

Use `--repo-receipt` only for substantial handoffs that should be visible from a
clone. Do not create a repo receipt for tiny edits.

## How A New Audit Agent Finds This

Start with:

```bash
make onboard
python3 scripts/governance/context_packet_router.py --id ctx.command-plane-governance --show-anchors
rg -n "CONTEXT_PACKET_CLOSEOUT|AGENT_OFFBOARD_RECEIPT|OFFBOARD_V0_0_0_1" docs reports scripts tests Makefile
```

For packet use:

```bash
python3 scripts/governance/context_packet_router.py "provider fallback" --path dharma_swarm/runtime_provider.py --json --hydrate
python3 scripts/governance/context_packet_router.py --id ctx.model-provider-routing --print-packet
```

For closeout:

```bash
make offboard ARGS='--task "..." --packet-id ctx.command-plane-governance --verification "..." --next-step "..."'
```

## Required Future Rule

Future context-packet evolution should use a multi-agent/model council when
practical, with at least five lanes requested. If fewer than five lanes respond,
or no council is run, record the reason as a first-class handoff receipt.

Every packet must preserve or refresh:

- `vision_anchors`
- `current_reality_anchors`
- `dense_docs`
- `work_lane_anchors`
- `evidence_boundary`
- `future_agent_review_hooks`
- common handoff fields: `claims_with_citations`, `claims_not_made`,
  `next_packet`, `residual_risk`, `next_step`

## Verification To Re-run

```bash
python3 -m json.tool docs/context_engineering/CONTEXT_PACKET_INDEX.json /tmp/context_packet_index_check.json
pytest tests/test_context_packet_router.py tests/test_agent_offboard.py
python3 -m py_compile scripts/governance/context_packet_router.py scripts/governance/agent_offboard.py
git diff --check -- docs/context_engineering docs/ops/AGENT_ONBOARDING.md docs/ops/AGENT_OFFBOARDING.md scripts/governance/context_packet_router.py scripts/governance/agent_offboard.py tests/test_context_packet_router.py tests/test_agent_offboard.py Makefile reports/handoffs/CONTEXT_PACKET_SYSTEM_METABOLIZED_2026-07-02.md
```

Also run a narrow secret scan over the same touched surfaces before commit or PR
handoff.
