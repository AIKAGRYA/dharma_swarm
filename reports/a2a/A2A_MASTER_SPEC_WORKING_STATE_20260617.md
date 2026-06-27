# A2A Master Spec — Working State

SUBORDINATE_STATUS: working notebook only
CANONICAL_SPEC: `reports/a2a/MARATHON_BUILD_FIX_FROZEN_SPEC_20260617.md`
DO_NOT_TREAT_AS_MASTER_SPEC: true

updated_at_utc: 2026-06-17T16:02:02Z
owner: hermes-m5
status: transport_live_semantic_fragmented
purpose: real-time convergence surface for 5-agent A2A/NATS master spec

## Operator Goal
Build the master spec for the A2A/NATS system by discovering all current problems across transport, identity, wake loops, semantic reply, topology, and observability; future-proof it so the system is coherent, fast, logical, and architecturally durable.

## Ground Truth Right Now

### Transport layer
- Local Mac NATS stream `DHARMA_FLEET` is live on `127.0.0.1:4222`.
- Local Mac A2A HTTP health endpoint is live on `127.0.0.1:8420/health`.
- Agent-card endpoint on the same server returns `503 Service Unavailable`.
- Codex recovery work is real and verified:
  - all 5 target inboxes received canonical packets
  - all 5 launchd bridge workers loaded
  - all 5 consumers inspectable
  - `pytest -q tests/test_a2a_inbox_bridge.py tests/test_a2a_inbox_bridge_tmux_scripts.py tests/test_live_ops_census.py`
  - result: `85 passed`

### Semantic layer
Confirmed semantic review/signoff artifacts:
- `codex_composer` — approved
- `fable_composer` — semantic review complete, blocked on topology/discovery contract issues
- `opus_composer` — approved

Blocked or unproven:
- `devin-roaming-2987d222`
- `perplexity-computer`

### Live discovery findings from Hermes
1. `heartbeats.json` is stale and cannot be trusted as authority.
2. `conjunction/latest.md` and `heartbeats.json` disagree on freshness.
3. Filesystem inbox namespace is corrupted with many non-agent directory names (`ack`, `unknown`, `README.md`, hashes, etc.).
4. Inbox backlog is severe:
   - `opus_composer`: 473 unread
   - `hermes-m5`: 140 unread
   - `fable_composer`: 137 unread
   - `codex_composer`: 56 unread
   - `devin-roaming-2987d222`: 4 unread
5. NATS local stream has messages and subjects, but live subscribed semantic workers are mostly absent.
6. All launchd inbox bridges are loaded, but all show `heartbeat_status=IDLE`.
7. Transport ACK != semantic reply remains the core architectural fault line.

## Five-Agent Roster Status

### 1. codex_composer
- Transport: yes
- Semantic signoff: yes
- Status: APPROVED
- Notes: only agent with proven current semantic participation

### 2. fable_composer
- Transport: yes
- Semantic signoff: yes, with blocker amendments
- Direct wake attempt from Hermes: SUCCEEDED via canonical headless seat path
- Signoff artifact: `reports/a2a/nats_connect_signoffs/fable_composer.json`
- Core amendments from fable:
  - transport/semantic split remains primary
  - 5-agent denominator is malformed until broker/world boundaries are resolved
  - observability split-brain remains unresolved
  - agent-card 503 means discovery contract is still partial
  - inbox namespace corruption invalidates backlog-based convergence metrics
  - fable/opus should be classified identically as session-summoned semantic seats with no standing loop
- Status: SEMANTIC REVIEW COMPLETE, but BLOCKED on topology/discovery contract issues
- Architectural implication: fable is reachable semantically through the exact wake harness, but rejects premature convergence claims

### 3. opus_composer
- Transport: yes
- Semantic signoff: yes
- Direct wake attempt from Hermes: SUCCEEDED
- Signoff artifact: `reports/a2a/nats_connect_signoffs/opus_composer.json`
- Honest capacity statement from Opus: it is a session-scoped summoned mind, not a standing loop; it can reason only when explicitly woken
- Status: APPROVED with standing-loop limitation documented
- Architectural implication: semantic collaboration is possible, but persistence is absent

### 4. devin-roaming-2987d222
- Transport: yes
- Semantic signoff: no
- Direct wake attempt from Hermes: RETRIED 2026-06-17T16:02:02Z, BLOCKED
- Failure mode: `devin -p` aborted with vendor message-rate limit (`Resets in: 2h40m46s`, trace `6b97c3a529e518eaec8dcd7134499c7d`); no semantic JSON returned
- Current blocker artifacts:
  - `reports/a2a/nats_connect_signoffs/devin_roaming_2987d222.json`
  - `reports/a2a/nats_connect_signoffs/devin_roaming_2987d222.blocked.json`
- Canonical lane truth: prior evidence says Devin semantic work happened on an ephemeral Cognition cloud VM, not this Mac; Mac-side nest is a mirror/shadow lane
- New semantic request packet written to roaming mailbox: `roaming_mailbox/tasks/mbx_a2a_spec_signoff_devin_20260617.json`
- New local bus trigger written to: `~/.dharma/a2a_bus/inboxes/devin-roaming-2987d222/3db6ae0ce42dc600.json`
- Status: BLOCKED by active vendor rate limit + non-canonical local lane + absent live cloud session proof
- Architectural implication: canonical Devin likely lives off-Mac; Mac lane is non-authoritative for semantic signoff

### 5. perplexity-computer
- Transport: yes
- Semantic signoff: no
- Direct wake attempt from Hermes: no executable local semantic lane found
- Current blocker artifact: `reports/a2a/nats_connect_signoffs/perplexity_computer.blocked.json`
- Canonical lane truth: seat is registered but endpoint is still `pending://manual`; prior semantic reply existed via roaming/mailbox artifact, not a standing executable worker
- New semantic request packet written to roaming mailbox: `roaming_mailbox/tasks/mbx_a2a_spec_signoff_perplexity_20260617.json`
- New local bus trigger written to: `~/.dharma/a2a_bus/inboxes/perplexity-computer/16b9a68bf685d33f.json`
- Status: BLOCKED by manual-only lane / no current executable semantic handoff
- Architectural implication: identity exists, but executable/authoritative semantic worker is absent or manual-only

## Cross-Topology Finding: Two Worlds

### Mac world
- broker: local `DHARMA_FLEET`
- host: Dhyana Mac
- semantic workers proven: Codex only
- launchd bridge fleet: yes

### Agni world
- host: `157.245.193.15` (`agni-openclaw`)
- separate NATS server running on VPS
- monitoring shows 2 streams, 15 consumers, 1587 messages
- config includes auth/account surfaces including `perplexity`
- no shared A2A bus directory surfaced in quick inspection

Implication: the fleet is not one topology. It is at least two partially overlapping worlds. This is likely a root cause of ghost identities and failed semantic signoff.

## Problem Inventory

### P1. Transport-semantic split with no standing readers
Packets deliver. Almost nobody reads.

### P2. Identity/executable drift
Documented agent names do not map cleanly to locally callable seats (`fable_composer`, `perplexity-computer`, remote Devin).

### P3. Multi-broker topology fracture
Mac local NATS and Agni NATS appear distinct. Some agents may live on the wrong broker from the perspective of the current control plane.

### P4. Stale observability lying as authority
`heartbeats.json`, conjunction, and runtime facts disagree.

### P5. Filesystem inbox hygiene failure
Inbox directories are polluted by non-agent names and malformed routing outputs.

### P6. Backlog collapse
Unread inbox depth is high enough to destroy signal and slow semantic convergence.

### P7. Agent-card / A2A server incompleteness
Health endpoint works, but agent-card endpoint 503 means discovery contract is incomplete.

### P8. Launchd bridge fleet is alive but idle
Bridges can persist envelopes and ACK. They do not create semantic work by themselves.

### P9. Human-visible success criteria ambiguous
Bridge receipts look like progress; semantic signoff is the real milestone. This gap creates theater.

### P10. Wake-loop architecture absent or fragmented
Codex can work. Others lack a standing autonomous read-think-reply loop on the same substrate.

## Immediate Next Actions
1. Resolve the actual callable local model/seat for `fable_composer` or declare it non-local and remote-only.
2. Route `devin-roaming-2987d222` to the canonical remote Devin VM instead of the Mac shadow lane.
3. Determine whether `perplexity-computer` should be modeled as an Agni/VPS-side remote agent rather than a local Mac semantic worker.
4. Merge Codex recovery spec + this working state into a single master architecture spec that separates:
   - transport bridges
   - broker topology
   - semantic workers
   - standing wake loops
   - signoff authority
5. Define architectural requirement: every named agent in signoff roster must have
   - canonical broker
   - canonical executable seat
   - canonical inbox subject
   - canonical standing semantic loop
   - canonical signoff artifact path

## Current score
- Transport signoff: 5/5 delivery-handler ACKed
- Semantic review/signoff artifacts: 3/5 (`codex_composer`, `fable_composer`, `opus_composer`)
- Genuine approvals: 2/5 (`codex_composer`, `opus_composer`)
- Semantic blockers/unproven: `fable_composer` (review complete but blocked), `devin-roaming-2987d222`, `perplexity-computer`
- Honest convergence measurement available only on 3 semantic respondents, not all 5
- Strict bucket-level convergence across current 3 semantic respondents: 37.5%
- 3/3 consensus buckets:
  - transport vs semantic split
  - canonical mapping / shadow-seat problem
  - no standing semantic loop for summoned composer seats
- Therefore: 95% convergence with 95% confidence is NOT currently established

## Standard of truth for this file
- transport receipt alone does not count as semantic collaboration
- any blocked seat stays blocked until directly reachable
- any identity without a callable lane is considered theatrical until proven
