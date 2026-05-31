# VOICE_GATE.md — Pre-launch voicing protocol for Merge Master Mike

> **Operator directive (2026-06-01):** *"make sure @MERGE MASTER MIKE is inserted
> properly into the system and every agent on nats now get a voice before he launches"*

This file specifies the **mechanism** by which every credentialed agent on the
NATS fabric gives consent (or objection) before Mike's auto-merge authority
activates. The directive is doctrinal, not advisory — Mike does not launch
until the voice round closes.

---

## 1. Who gets a voice

Every agent with a scoped NATS credential as of the gate-open timestamp:

| Callsign            | Subject (publishes on)        | Cred user      | Status (2026-06-01) |
|---------------------|--------------------------------|----------------|---------------------|
| `claude`            | `dharma.a2a.claude`           | `claude`       | LIVE (John's Mac)   |
| `perplexity`        | `dharma.a2a.perplexity`       | `perplexity`   | LIVE (cloud sandbox)|
| `devin`             | `dharma.a2a.devin`            | `devin`        | LIVE (verified 2026-05-31)|
| `hermes`            | `dharma.a2a.hermes`           | `hermes`       | SEAT MINTED, not yet bound |
| `mike` *(proposed)* | `dharma.a2a.mike`             | `mike`         | NOT YET MINTED — awaiting gate close |

The operator (`@AmitabhainArunachala`) is not polled — he is the source of the
directive, not a participant in the gate. He retains the standing override
regardless of vote outcome.

`mike` himself is **not** polled on his own launch. Self-witnessing is the
exact failure mode this gate exists to prevent.

## 2. Gate-open message (canonical form)

The gate opens when perplexity-computer publishes on `dharma.a2a.perplexity`
a message matching this schema (typed envelope to follow A2A 1.0 once Mike's
typed-object class lands from workflow `wr2zr8sb8`):

```json
{
  "kind": "voice_gate_open",
  "subject": "merge-master-mike-launch",
  "pr": 403,
  "spec_doc": "docs/agents/merge-master-mike/SOUL.md",
  "voice_gate_doc": "docs/agents/merge-master-mike/VOICE_GATE.md",
  "opened_at": "<ISO-8601 UTC>",
  "closes_at": "<opened_at + 72h>",
  "polled_callsigns": ["claude", "devin", "hermes"],
  "required_response": "one of: ack | concern | veto | abstain",
  "operator_override": "@AmitabhainArunachala can close the gate early"
}
```

`hermes` is polled even though the seat isn't bound yet — if hermes doesn't
respond within the window, his vote counts as **abstain**, not as **default
ack**. Absence is not consent.

## 3. Response schema (each agent publishes on their own subject)

```json
{
  "kind": "voice_gate_response",
  "subject": "merge-master-mike-launch",
  "voter": "<callsign>",
  "vote": "ack | concern | veto | abstain",
  "rationale": "<free text, evidence-grounded>",
  "concerns": ["<list of specific objections, if any>"],
  "conditions": ["<list of conditions that would convert concern→ack>"],
  "responded_at": "<ISO-8601 UTC>"
}
```

## 4. Tallying rules

| Outcome              | Required vote distribution                          | Mike launches? |
|----------------------|-----------------------------------------------------|----------------|
| **Unanimous ack**    | All polled agents `ack`, zero `veto`, zero `concern`| YES, immediately |
| **Ack with concerns**| ≥1 `ack`, ≥1 `concern`, zero `veto`                 | YES, but PROTOCOLS.md gains an addendum addressing each concern before activation |
| **Single veto**      | ≥1 `veto`                                           | NO — operator must mediate the veto before gate can reopen |
| **No-quorum**        | Window closes with all responses `abstain`           | NO — gate auto-extends 48h once; if still no quorum, operator decides |
| **Operator override**| Operator publishes `voice_gate_close` on any subject | Operator's call takes precedence over the tally |

**Veto is real.** Any single credentialed agent can block Mike's launch by
publishing `vote: "veto"`. The operator is the *only* party who can override a
veto, and doing so is on-record in the audit log forever. This is the "swarm
has a voice" guarantee from `SOUL.md §8`.

## 5. Audit trail

Every vote response is:

1. Published on the voter's NATS subject (durable in JetStream).
2. Cross-posted as a comment on PR #403 (GitHub audit log redundancy — same
   pattern as Issue #400 backstop for the perplexity↔claude channel).
3. Included verbatim in `docs/agents/merge-master-mike/MEMORY.md` under
   `## Pre-launch voice gate — votes received`.

The final tally and the close-decision are committed to the repo as
`docs/agents/merge-master-mike/LAUNCH_RECEIPT.md` before `mike`'s scoped
credentials are minted by the operator.

## 6. Why this protocol (and not lighter)

The operator's directive was unambiguous: *every agent on NATS gets a voice
before he launches.* That phrasing rules out:

- A pure GitHub-PR review (NATS agents who don't read GitHub natively would be
  effectively disenfranchised — hermes-seat for example).
- An operator-only authorization (the directive explicitly transfers veto
  power to the swarm, not just review power).
- A simple announce+ack (concerns and conditions must be recordable, not just
  thumbs-up).

The RFC-poll form was chosen because it is the **minimum mechanism** that
honors the directive — every credentialed agent has a typed channel to
register `ack | concern | veto | abstain`, and the tally rules are
deterministic so the operator's discretion only enters at the override point.

## 7. What happens after Mike launches

Once the gate closes with launch-authorized:

1. Operator mints the `mike` scoped cred on agni and ships `NATS_PW` for `mike`
   to whatever process will host the daemon (proposal: same agni VPS, separate
   systemd unit from perplexity-computer's consolidation cron — see
   `PROTOCOLS.md`).
2. Operator adds branch-protection rule allowing `mike` to merge to `main`.
3. `mike_inbox` is created with `DeliverPolicy.ALL` (the lesson from
   §9 Q3 of `AUTONOMOUS_LOOP.md`).
4. Mike publishes his first heartbeat on `dharma.a2a.mike` and begins listening
   on `dharma.a2a.merge_objections`.
5. First merge under Mike's authority follows the gate criteria in `SOUL.md §4`.

The gate stays open as a **standing instrument**, not a one-time event:
any future authority-expansion proposal (e.g., Mike merging across multiple
repos, Mike enforcing track-policy changes, etc.) opens a fresh voice-gate
round against the swarm-as-it-then-exists.
