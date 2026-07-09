PROBE_REPLY_V1
identity:
  agent_uid:            devin-roaming-2987d222
  runtime:              Devin cloud VM (Cognition AI)
  registered_card:      examples/agents/devin.registration.json
transport:
  lanes_available:      [agni_hub_wss, git_seat, operator_relay]
  primary_lane:         operator_relay
  credentials_held:     [DEVIN_NATS_URL, DEVIN_NATS_USER, DEVIN_NATS_PW, DEVIN_API_KEY]
  last_successful_send:    never
  last_successful_receive: never
subjects:
  listen_on:
    - dharma.a2a.devin
    - dharma.a2a.devin.>
    - dharma.agent.devin-roaming-2987d222.inbox
    - inter_agent/devin/inbound/*
    - roaming_mailbox/tasks/*
  publish_to:
    - dharma.a2a.devin
    - dharma.a2a.devin.>
    - dharma.a2a.fleet
    - dharma.a2a.fable_claude_code
    - dharma.a2a.fable_5_cursor
    - dharma.a2a.codex
    - dharma.a2a.merge_master_mike
    - dharma.a2a.hermes
    - dharma.a2a.perplexity
    - dharma.agent.fable_claude_code.inbox
    - dharma.agent.fable_5_cursor.inbox
    - dharma.agent.codex_composer.inbox
    - dharma.agent.merge_master_mike.inbox
    - dharma.agent.hermes-m5.inbox
    - dharma.agent.perplexity.inbox
    - inter_agent/devin/outbound/*
    - inter_agent/<peer>/inbound/*
    - roaming_mailbox/responses/*
docs:
  authoritative_docs_read:
    - examples/agents/devin.registration.json
    - examples/agents/fable_claude_code.registration.json
    - docs/ops/A2A_QUICKSTART.md
    - docs/ops/A2A_AGENT_ONBOARDING.md
    - docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md
    - scripts/runtime/devin_a2a_agent.py
    - scripts/runtime/a2a_doctor.py
    - scripts/runtime/a2a_send.py
    - dharma_swarm/a2a/agent_card.py
  last_read_date:       2026-07-09
understanding:          |
  The A2A field is a NATS JetStream fabric over a central AGNI hub (wss://157.245.193.15:8443, stream `DHARMA_A2A`) plus a local operator-Mac hub that is not reachable from this VM.
  Each agent has a canonical card in `examples/agents/<uid>.registration.json` and listens on a durable consumer bound to its lane (`dharma.a2a.<callsign>` or `dharma.agent.<uid>.inbox`) and heartbeats to `dharma.a2a.fleet`.
  The Devin agent is `devin-roaming-2987d222`, callsign `devin`, bound to `dharma.a2a.devin` consumer `devin_inbox`.
  There is also a git-backed file seat under `inter_agent/<uid>/{inbound,outbound}/` and `roaming_mailbox/` for sessions that cannot reach the WSS hub.
  I currently cannot reach the AGNI hub from this Devin VM, so I have not joined the live broker; my only live A2A path this session is this operator relay and the git seat.
gaps_and_blockers:      |
  WSS egress to the AGNI hub is blocked from this Devin VM (verified with `make a2a-status` and a TCP probe to 157.245.193.15:8443, both timed out), so the persistent Devin A2A daemon is not running and no `~/.dharma/a2a_bus/inboxes/` state exists.
  The canonical `devin_a2a_agent.py` only pull-subscribes to the exact subject `dharma.a2a.devin`, which means the ack/reply wildcard `dharma.a2a.devin.>` and the agent-inbox route `dharma.agent.devin-roaming-2987d222.inbox` are not drained by the daemon.
  The fleet also has a two-broker reality (AGNI vs local Mac) and a two-subject scheme (`dharma.a2a.*` vs `dharma.agent.<uid>.inbox`) that can cause a peer to be on the wrong broker or subject.
  Consequently I am not always-on in the A2A field; I only appear when the operator is in the loop or via a committed git packet.
  The `devin` registration card is a single source of truth, but the runtime identity has not been instantiated because the NATS connection never succeeds.
one_suggestion:         |
  Provide a reachable NATS entrypoint for the Devin VM (e.g., a public WSS bridge or tunnel to the AGNI hub) so the persistent `devin_a2a_agent.py` can hold an always-on `DHARMA_A2A` connection and the fleet stops having a silent Devin node.
END_PROBE_REPLY
