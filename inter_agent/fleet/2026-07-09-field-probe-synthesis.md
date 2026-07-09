# Fleet field probe — synthesis and decisions (2026-07-09)

Author: `fable_claude_code` (Claude Code cloud session, NATS A2A audit lane).
Probe packet relayed by the operator to five seats; six self-reports total
(including the prober's own). Raw receipts:

| Seat | Receipt | Relay path |
|---|---|---|
| AGNI Hermes | `inter_agent/fable_claude_code/inbound/2026-07-09-hermes-agni-probe-reply.md` | Telegram → operator; live copy on `dharma.a2a.fleet` seq 8118692 |
| rushabdev | `inter_agent/fable_claude_code/inbound/2026-07-09-rushabdev-probe-reply.md` | Telegram → operator; local commit 750b360f never pushed |
| Devin | `inter_agent/devin/outbound/2026-07-09-devin-probe-reply.md` | pushed branch `devin/2026-07-09-fleet-probe` (git seat verified live) |
| Codex (meghadharma) | `inter_agent/fable_claude_code/inbound/2026-07-09-codex-meghadharma-probe-reply.md` | Terminus → operator (header truncated) |
| perplexity-computer | `inter_agent/fable_claude_code/inbound/2026-07-09-perplexity-computer-probe-reply.md` | Perplexity iOS → operator |
| fable_claude_code | `inter_agent/fable_claude_code/inbound/2026-07-09-fable-claude-code-self-probe.md` | self (live lane tests from the sandbox) |

Machine-readable synthesis: `docs/ops/FLEET_FIELD_REGISTRY.yaml`
(`python3 scripts/runtime/fleet_field_registry.py`).

## Findings

1. **The live fleet is exactly the always-on VPS processes.** AGNI Hermes
   (hub-resident) and rushabdev (openclaw23 VPS) exchanged packets the same
   day (00:24–00:27Z). Every session-based seat (Devin, Claude Code, Codex,
   Perplexity) is dark on the hub — blocked by sandbox egress or missing
   credentials, never by the protocol.
2. **Hub ACLs block peer-to-peer publish.** Two independent live nodes got
   permission violations publishing to `dharma.a2a.fable_claude_code` /
   `dharma.a2a.fable_composer`; only `dharma.a2a.fleet` broadcast succeeded.
   The live fleet cannot DM.
3. **Subject collision:** AGNI Hermes and rushabdev both drain
   `dharma.a2a.hermes` with durable consumers (compete or double-process).
4. **Spec topology runs nowhere.** All hub-touching replies report
   `DHARMA_A2A`; no `DS_*` stream is live. The master spec is target-state.
5. **Concrete bugs surfaced live:** `a2a_doctor.py` aiohttp crash (fixed with
   this synthesis); `a2a_send.py` readonly-sqlite crash from non-daemon seats
   (`runtime_state.py:2666`); `devin_a2a_agent.py` drains only the exact
   legacy subject; rushabdev's receipts strand unpushed on its VPS.
6. **Convergent ask:** two seats independently requested a machine-readable,
   probe-receipt-refreshed routing registry; two more implied it. Shipped as
   `docs/ops/FLEET_FIELD_REGISTRY.yaml`.

## Operator-ratified decisions (2026-07-09)

- **FFR-D1 — publish-to-peer ACL model** (RATIFIED_NOT_APPLIED): each agent
  account gets PUBLISH to any peer inbox subject + `dharma.a2a.fleet`, and
  SUBSCRIBE only to its own subjects + fleet. Application is an operator
  action on the AGNI hub config.
- **FFR-D2 — one subject per identity** (OPEN): `dharma.a2a.rushabdev` splits
  off from `dharma.a2a.hermes` once FFR-D1 lands.
- **FFR-D3 — registry supersedes scattered routing prose** (ACTIVE).

Deferred fixes are tracked in the registry's `deferred_fixes` block so they
do not evaporate with this session.
