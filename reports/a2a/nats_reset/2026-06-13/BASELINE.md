# A2A/NATS Reset Baseline

Date: 2026-06-13 JST
Worktree: `/Users/dhyana/dharma_swarm_a2a_active`
Branch: `codex/a2a-active-track-20260613`
Base: `origin/main` at `9c76b2106`

This is a read-only baseline before any drain/reset action.

## AGNI `DHARMA_A2A`

- Endpoint context: `agni-wss`
- Stream subjects: `dharma.a2a.>`
- Retention: `limits`
- Storage: `file`
- Discard: `old`
- Messages: `8,106,912`
- Bytes: `1,427,133,017`
- First seq: `1`
- Last seq: `8,106,912`
- Subject count: `22`
- Consumer count: `11`
- `max_msgs`: unlimited (`-1`)
- `max_bytes`: unlimited (`-1`)
- `max_age`: unlimited (`0`)
- `max_msgs_per_subject`: unlimited (`-1`)

Top retained subjects:

| Subject | Count |
|---|---:|
| `dharma.a2a.fleet` | 4,053,354 |
| `dharma.a2a.devin` | 4,053,353 |
| `dharma.a2a.perplexity` | 91 |
| `dharma.a2a.claude` | 45 |
| `dharma.a2a.merge_master_mike` | 31 |

Largest consumer backlogs:

| Consumer | Unprocessed | Last Delivery |
|---|---:|---|
| `claude_from_devin` | 4,053,238 | never |
| `merge_master_mike_fleet` | 4,053,346 | never |
| `devin_inbox` | 10 | never |
| `fable_5_cursor_inbox` | 1 | 22h56m57s |

Reading: AGNI is not production-clean. It has unbounded retention and two
runaway subjects accounting for essentially the whole stream.

## Local `DHARMA_FLEET`

- Stream subjects: `dharma.>`
- Retention: `limits`
- Storage: `file`
- Discard: `old`
- Messages: `64`
- Bytes: `114,076`
- Subject count: `20`
- Consumer count: `1`
- `max_msgs`: `5,000`
- `max_age`: `7d`
- `max_msgs_per_subject`: `50`

Reading: local broker state is bounded and small. The production issue is not
NATS as a technology; it is topology split and AGNI retention/backlog hygiene.

## Baseline Verdict

Status: `NOT_PRODUCTION_READY`

Reasons:

- AGNI stream retention is unbounded.
- AGNI contains 8.1M retained messages.
- Two stale consumers hold multi-million unprocessed backlogs.
- File inboxes and NATS routing are not yet one governed route.
- A production readiness quorum has not been collected.
