# NATS SUBSTRATE MASTER SPEC

## Authority

This file owns the internal live-transport decision for Dharma Swarm.
It is doctrine and operating contract, not live state. Live state is still
rendered by `make onboard`; current build intent is still owned by
`docs/governance/ACTIVE_TRACK.yaml`; declared repo surfaces are still owned by
`ACTIVE_SURFACE_MANIFEST.yaml`.

If any agent, doc, or PR claims that A2A is "live", "ready", or "reachable",
that claim must be backed by this contract or it is false.

Manifest state: NATS is a declared integration surface in
`ACTIVE_SURFACE_MANIFEST.yaml`, but it is not live until a JetStream health
probe and ack-bearing hot-contact receipt exist. A declared surface is not a
liveness proof.

## Decision

NATS JetStream is the canonical internal fleet transport for live agent
messaging.

The system split is:

- NATS JetStream: internal fleet nervous system.
- A2A HTTP / Agent Cards: external and cross-vendor edge.
- Temporal: durable workflow execution, not message transport.
- OpenTelemetry: trace envelope, not delivery.
- Filesystem and SQLite buses: compatibility mirrors and audit trails during
  migration, not live-contact authority.

## Layer Boundaries

NATS owns delivery, durable consumers, replay, acknowledgements, and internal
fanout.

A2A HTTP owns interop with independent agents and vendors. It must not be used
as the internal hot path for local fleet messaging.

Temporal owns long-running workflow state. It must not be used as the fleet
event bus.

Filesystem paths under `~/.dharma/a2a_bus/` may remain as mirror surfaces for
receipts, verifier rows, historical compatibility, and human inspection. They
must not be represented as proof of live agent reachability.

## External A2A Boundary

External A2A HTTP and Agent Cards enter Dharma Swarm only through a gateway.
Agent cards are discovery metadata, not reachability proof.

External agents do not publish directly to internal fleet subjects. The gateway
verifies the external identity, mints or resolves the stable internal
`agent_uid`, wraps the request in the NATS envelope, and publishes to the
canonical internal subject.

Internal subjects may use `dharma.a2a.*` for migrated task lifecycle events,
but those subjects are internal NATS subjects. They are not Google A2A wire
compatibility by themselves.

## Subject Contract

The first NATS substrate implementation must define these subjects before
implementation spreads:

- `dharma.fleet.heartbeat`
- `dharma.agent.<agent_uid>.inbox`
- `dharma.agent.<agent_uid>.outbox`
- `dharma.a2a.task.claim`
- `dharma.a2a.task.close`
- `dharma.a2a.receipt`
- `dharma.operator.hot_contact`
- `dharma.substrate.health`

Agents subscribe through durable consumers named from stable agent UIDs. Human
display names, model names, and temporary worktree names are not durable
consumer identifiers.

## JetStream Stream Topology

The implementation owns streams, not ad hoc subscribers. Stream definitions are
part of the contract.

| Stream | Subjects | Retention | Storage | Max age | Duplicate window | Discard |
|---|---|---|---|---|---|---|
| `DS_FLEET` | `dharma.fleet.*`, `dharma.substrate.health` | limits | file | 7 days | 10 minutes | old |
| `DS_AGENT_INBOX` | `dharma.agent.*.inbox`, `dharma.agent.*.outbox` | limits | file | 14 days | 10 minutes | old |
| `DS_TASKS` | `dharma.a2a.task.*` | workqueue where possible, limits otherwise | file | 30 days | 10 minutes | old |
| `DS_RECEIPTS` | `dharma.a2a.receipt` | limits | file | 90 days | 10 minutes | old |
| `DS_OPERATOR` | `dharma.operator.*` | limits | file | 14 days | 10 minutes | old |
| `DS_DLQ` | `dharma.dlq.*` | limits | file | 90 days | 10 minutes | old |

All publishes use the `Nats-Msg-Id` header set to the envelope `message_id`.
The first local deployment may use one replica; clustered deployment raises the
replica count without changing subjects or envelope fields.

## Durable Consumer Contract

Consumer names are stable slugs derived from `agent_uid`. They must contain
only printable slug characters and must not contain `.`, `*`, `>`, slash,
whitespace, or path separators.

| Consumer family | Stream | Filter subject | Delivery | Ack policy | Ack wait | Max deliver | Replay |
|---|---|---|---|---|---|---|---|
| Agent inbox | `DS_AGENT_INBOX` | `dharma.agent.<agent_uid>.inbox` | pull durable | explicit | 30s | 5 | instant |
| Agent outbox mirror | `DS_AGENT_INBOX` | `dharma.agent.<agent_uid>.outbox` | pull durable | explicit | 30s | 5 | instant |
| Task claimant | `DS_TASKS` | `dharma.a2a.task.claim` | pull durable queue group | explicit | 60s | 3 | instant |
| Task closer | `DS_TASKS` | `dharma.a2a.task.close` | pull durable queue group | explicit | 60s | 3 | instant |
| Receipt projector | `DS_RECEIPTS` | `dharma.a2a.receipt` | pull durable | explicit | 30s | 5 | instant |
| Operator hot contact | `DS_OPERATOR` | `dharma.operator.hot_contact` | pull durable | explicit | 15s | 2 | instant |
| Audit mirror | all streams | configured per stream | pull durable | explicit | 120s | 10 | instant |

New consumers use `DeliverNew` at registration unless they are explicitly
audit/indexer consumers. Existing durable consumers resume from their durable
state. Audit/indexer consumers may use `DeliverAll`; command and hot-contact
consumers must not replay old commands as fresh work.

## Envelope Contract

Every NATS message uses a typed envelope. Minimum fields:

- `schema`: version string, initially `dharma.nats.envelope.v1`.
- `message_id`: stable unique id.
- `trace_id`: OpenTelemetry-compatible trace id. Generate one if absent.
- `span_id`: OpenTelemetry-compatible span id. Generate one if absent.
- `parent_span_id`: parent span id when this message continues an existing span.
- `correlation_id`: stable id tying a request, replies, receipts, and mirrors.
- `causation_id`: prior `message_id` that caused this message, when present.
- `subject`: published subject.
- `from_agent`: stable sender uid.
- `to_agent`: stable target uid or `fleet`.
- `kind`: heartbeat, command, task, receipt, verifier_row, health, or event.
- `created_at`: UTC ISO timestamp.
- `requires_ack`: boolean.
- `payload`: object.

Raw strings are not fleet messages. If a CLI accepts a string, the CLI wraps it
in this envelope before publish.

## Trace And Causality

Trace fields are mandatory for commands, task lifecycle events, receipts, and
verifier rows. Gateways map `trace_id`, `span_id`, and `parent_span_id` to
OpenTelemetry `traceparent`/`tracestate` headers when crossing process or HTTP
boundaries.

Receipts must carry the original `trace_id`, `correlation_id`, and triggering
`message_id`. A reply without causality fields is mirror evidence only.

## Delivery And Ack Contract

For hot contact, success means a broker-owned acknowledgement or a durable
consumer-visible delivery receipt. Writing a file is not success.

With NATS reachable:

- publish to the canonical subject;
- require ack for operator commands and task lifecycle events;
- surface the ack id, subject, and elapsed time.

With NATS unreachable:

- fail fast with `NATS_UNAVAILABLE`;
- print the exact check that failed;
- do not crawl `~/.dharma/a2a_bus/` looking for a substitute success signal.

## Ack Tiers

The system must name which ack tier it has proven:

- `PUBLISH_ACCEPTED`: JetStream accepted the publish and returned stream
  sequence metadata.
- `DELIVERED_TO_CONSUMER`: a durable consumer saw the message.
- `HANDLER_ACKED`: the target handler acknowledged completion of the message
  handling step.
- `DOMAIN_RECEIPTED`: a typed Dharma receipt exists for the intended domain
  effect.

Operator hot contact requires `HANDLER_ACKED` or `DOMAIN_RECEIPTED` within the
configured timeout. `PUBLISH_ACCEPTED` alone is not live human-usable contact.

## Replay And Poison Message Policy

Commands and hot-contact messages must be idempotent and must not replay as new
commands after agent restart. Durable resume is allowed; accidental command
re-execution is not.

When `MaxDeliver` is exhausted, the handler publishes a typed failure envelope
to `dharma.dlq.<stream>.<consumer>` and emits an operator-visible blocker. DLQ
messages are retained for audit and human replay. The failed original message
must not be silently treated as handled.

## Hot Contact Protocol

`dgc a2a send <agent_uid> <message>` publishes an `operator_command` envelope to
`dharma.agent.<agent_uid>.inbox`. `dharma.operator.hot_contact` is an operator
receipt/coordination subject, not the target inbox.

The CLI prints:

- `message_id`;
- target `agent_uid`;
- stream and sequence for `PUBLISH_ACCEPTED`;
- ack tier reached;
- elapsed milliseconds;
- blocker code when the timeout expires.

Without NATS ack proof the command exits non-zero and prints `NATS_UNAVAILABLE`
or `NATS_ACK_UNVERIFIED`.

## JetStream KV And Object Store

JetStream KV may own ephemeral fleet presence, last heartbeat, lease pointers,
registry snapshots, and hot-contact pending state. KV compare-and-set is the
only allowed lease mutation primitive once migrated.

JetStream Object Store may own large transcripts, artifacts, and blobs. NATS
messages carry object references and hashes, not large payloads.

## Compatibility Mirrors

During migration, existing filesystem and SQLite surfaces may mirror NATS
events for audit compatibility:

- `~/.dharma/a2a_bus/receipts/`
- `~/.dharma/a2a_bus/verifier.jsonl`
- `~/.dharma/a2a_bus/conjunction/`
- `~/.dharma/a2a_bus/tasks/queue.jsonl`
- `~/.dharma/a2a_bus/inboxes/`
- existing `MessageBus` SQLite records when needed by older views

Mirrors are append-only evidence copies. They do not own delivery, liveness,
ordering, backpressure, or retry semantics.

## Anti-Slop Rules

Agents must not:

- add a new file-poll inbox or queue and call it live A2A;
- add a new `queue.jsonl` authority path for task dispatch;
- add a second internal broker, registry, or delivery abstraction without
  updating this spec first;
- claim Perplexity, Codex, Opus, Hermes, Warp, Devin, or any other agent is
  reachable because a card or folder exists;
- silently fall back from NATS to filesystem for hot contact.

Allowed exceptions:

- tests may use temp filesystem fixtures;
- legacy compatibility code may read existing mirrors while explicitly naming
  them as mirrors;
- governance reports may mention old filesystem paths as broken or historical
  evidence.

## Onboarding And Enforcement

`make onboard` must render the NATS substrate status every session. It must
show:

- this spec path;
- whether TCP port 4222 is listening locally;
- whether filesystem A2A mirrors exist;
- that filesystem mirrors are not live-transport proof.

`make nats-substrate-contract` must verify the wiring of this contract.
`make governance-all` must include that check.

## Supersession

Older Go/event-fabric plans that described NATS as optional or file spool as
the default remain valid only for evidence ingress, historical compatibility,
or mirror experiments. They are superseded for live-contact authority by this
spec.

## Acceptance Criteria

The first NATS substrate implementation is complete only when:

- this spec exists and is referenced from onboarding and governance docs;
- `make onboard` prints the NATS substrate section without requiring NATS;
- `make nats-substrate-contract` passes;
- tests prove the checker fails when this contract is disconnected;
- no new filesystem inbox is introduced as the hot-contact fix.
