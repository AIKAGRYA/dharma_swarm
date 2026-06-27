# A2A Roll Call Triple Confirmation - 2026-06-17

updated_at_utc: 2026-06-17T12:50:40Z
owner: codex_composer
status: partial_rollcall_minimum_5_present_if_perplexity_human_relay_counts

## Purpose

Before writing more spec text, establish who is actually online, present, and in role call across the current split topology.

This file distinguishes:

- transport presence: inbox/consumer/bridge can accept packets;
- semantic presence: an agent actually read/reasoned/signed or produced a current working artifact;
- relay presence: a current agent output was provided by the operator but is not yet visible through the shared bus.

## Triple Confirmation Sources

1. Mac-local bridge/process plane:
   - `bash scripts/status_a2a_inbox_bridge_fleet_launchd.sh`
   - local launchd bridge fleet loaded for all five target lanes plus Hermes
   - fresh bridge heartbeats at ~2026-06-17T12:49Z

2. Mac-local NATS plane:
   - `nats consumer ls DHARMA_FLEET`
   - all repaired local consumers inspectable
   - Ack Pending `0`
   - Unprocessed `0`

3. Agni remote plane:
   - `nats --context agni-wss consumer ls DHARMA_A2A`
   - `nats --context agni-wss stream subjects DHARMA_A2A`
   - `nats --context agni-wss stream get DHARMA_A2A 8108503`
   - `nats --context agni-wss stream get DHARMA_A2A 8108506`

4. Semantic artifact plane:
   - `reports/a2a/A2A_MASTER_SPEC_WORKING_STATE_20260617.md`
   - `reports/a2a/nats_connect_signoffs/codex_composer.json`
   - `reports/a2a/nats_connect_signoffs/opus_composer.json`
   - agni `DHARMA_A2A#8108503` Devin semantic signoff
   - operator-pasted current Perplexity output

## Roll Call Table

| Agent | Transport Presence | Semantic Presence | Remote/Agni Presence | Verdict |
| --- | --- | --- | --- | --- |
| `codex_composer` | local bridge and local consumer live | approved in `codex_composer.json`; current Codex lane active | no agni-specific Codex consumer observed | ONLINE / PRESENT |
| `hermes-m5` | local bridge and local consumer live | current working-state artifact authored by Hermes; operator pasted Hermes current report | no dedicated agni Hermes activity observed in this pass | ONLINE / PRESENT |
| `opus_composer` | local bridge and local consumer live | approved in `opus_composer.json` at 2026-06-17T12:36Z | no agni-specific Opus consumer observed | ONLINE / PRESENT when summoned; not standing |
| `devin-roaming-2987d222` | local bridge exists, but local lane is shadow only | agni semantic signoff verified at `DHARMA_A2A#8108503` | `devin_inbox` active; recent delivery; waiting pulls observed | ONLINE / PRESENT on canonical remote Devin |
| `perplexity-computer` | local bridge and consumer live; Mac Perplexity Helper process observed | current output pasted by operator; no bus-visible semantic signoff | agni `perplexity_inbox` exists but is miswired to `dharma.a2a.claude`; no deliveries | PRESENT BY HUMAN RELAY ONLY; BUS ROLECALL NOT PROVEN |
| `fable_composer` | local bridge and local consumer live | blocked; direct wake failed; no semantic signoff | agni `fable_composer_inbox` exists but no delivery | TRANSPORT-ONLY / BLOCKED |

## Minimum-5 Status

Strict machine-verifiable semantic role call:

- Count: 4
- Agents: `codex_composer`, `hermes-m5`, `opus_composer`, `devin-roaming-2987d222`
- Missing for 5: `perplexity-computer` bus-visible semantic reply, or `fable_composer` semantic wake/signoff.

Operational role call including current operator-relayed Perplexity output:

- Count: 5
- Agents: `codex_composer`, `hermes-m5`, `opus_composer`, `devin-roaming-2987d222`, `perplexity-computer`
- Caveat: Perplexity is not yet confirmed through agni/local NATS as a semantic consumer. It is current by human relay only.

Transport-only reachable lanes:

- Count: 6 local bridge lanes
- Agents: `hermes-m5`, `codex_composer`, `fable_composer`, `opus_composer`, `devin-roaming-2987d222`, `perplexity-computer`
- Caveat: transport-only does not count as semantic role call.

## Key Verified Facts

Mac-local bridge:

```text
hermes-m5                  launchd=loaded nats_consumer=inspectable heartbeat=fresh
codex_composer             launchd=loaded nats_consumer=inspectable heartbeat=fresh
fable_composer             launchd=loaded nats_consumer=inspectable heartbeat=fresh
opus_composer              launchd=loaded nats_consumer=inspectable heartbeat=fresh
devin-roaming-2987d222     launchd=loaded nats_consumer=inspectable heartbeat=fresh
perplexity-computer        launchd=loaded nats_consumer=inspectable heartbeat=fresh
```

Mac-local NATS:

```text
codex_composer_inbox          Ack Pending=0 Unprocessed=0
fable_composer_inbox          Ack Pending=0 Unprocessed=0
opus_composer_inbox           Ack Pending=0 Unprocessed=0
devin_roaming_2987d222_inbox  Ack Pending=0 Unprocessed=0
perplexity_computer_inbox     Ack Pending=0 Unprocessed=0
hermes_inbox                  Ack Pending=0 Unprocessed=0
```

Agni:

```text
stream: DHARMA_A2A
subjects:
  dharma.a2a.devin             count=6
  dharma.a2a.merge_master_mike count=6
  dharma.a2a.fleet             count=1628
```

Devin canonical remote signoff:

```text
DHARMA_A2A#8108503 subject=dharma.a2a.fleet type=SEMANTIC_SIGNOFF verdict=APPROVED
from=devin-roaming-2987d222
from_detail=canonical-remote-devin, not Mac shadow registration
```

Devin amendment:

```text
DHARMA_A2A#8108506 subject=dharma.a2a.fleet type=SPEC_AMENDMENT
amendment_id=AMD-001-remote-bridge-gap
```

## Blockers Before Claiming Clean 5/5

1. Perplexity must produce a bus-visible semantic role-call/signoff, not only a human-relayed report.
2. Agni `perplexity_inbox` is miswired:

```text
perplexity_inbox filter_subject=dharma.a2a.claude
claude_inbox     filter_subject=dharma.a2a.perplexity
```

3. Fable must be mapped to a real executable seat or removed from the always-on semantic roster.
4. Local and agni planes must share canonical subjects or bridge between them.
5. Remote agents must not need Mac filesystem access to participate.

## Proceed / No-Proceed Call

Proceed with spec architecture work only under this truthful condition:

```text
We have 5 present agents if Perplexity's current human-relayed output counts.
We do NOT yet have 5 machine-verifiable bus-visible semantic agents.
```

Recommended next action:

- Use the five-present roster for discussion: Codex, Hermes, Opus, Devin, Perplexity.
- Do not claim final 5/5 ratification until Perplexity is visible on agni/local NATS or produces a durable signoff artifact.
- Treat Fable as blocked until executable mapping is repaired.

