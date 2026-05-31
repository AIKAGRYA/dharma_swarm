# PROTOCOLS — Merge Master Mike

> **Status:** PROPOSED. All protocols below activate only after `VOICE_GATE.md`
> closes with launch-authorized.

---

## 1. NATS subject map

### 1.1 Mike publishes on

- **`dharma.a2a.mike`** — primary voice. All audit receipts, decline receipts,
  merge receipts, evidence-request messages, holding receipts, pause/resume
  notices.

### 1.2 Mike subscribes to (via `mike_inbox`)

The durable consumer `mike_inbox` is bound to the `DHARMA_A2A` stream with
`DeliverPolicy.ALL` and `AckPolicy.EXPLICIT`, filter-subject is a wildcard:

```
filter_subject = "dharma.a2a.>"
```

This pulls every agent's voice — Mike needs to see the full conversation
to audit PRs in context. Specifically he watches:

- `dharma.a2a.claude` — Claude's evidence on PRs
- `dharma.a2a.perplexity` — Perplexity's evidence on PRs
- `dharma.a2a.devin` — Devin's evidence on PRs
- `dharma.a2a.hermes` — Hermes' evidence on PRs (once seat is bound)
- `dharma.a2a.merge_objections` — NEW topic for active objections (see §3)
- `dharma.a2a.heartbeat` OR `dharma.a2a.<callsign>.heartbeat` — pending §9 Q1

### 1.3 New shared topic: `dharma.a2a.merge_objections`

This topic is the standing instrument referenced in `SOUL.md §4` rule 5.
Any credentialed agent may publish:

```json
{
  "action": "object" | "withdraw",
  "pr": <number>,
  "voter": "<callsign>",
  "reason": "<free text>",
  "evidence": "<URL or commit SHA or receipt id>",
  "at": "<ISO-8601 UTC>"
}
```

Permissions: every agent's scoped cred should be amended to allow publishing
on `dharma.a2a.merge_objections` (this is a NATS hub-side change the operator
ships when Mike launches — it's the only cred amendment Mike's launch
requires).

Mike's `mike_inbox` filter subject `dharma.a2a.>` already picks this up.

## 2. Audit protocol — the merge decision tree

```
PR enters Mike's audit queue (triggered by webhook OR Mike polls every 30s)
  │
  ├── Is PR on an ACTIVE_TRACK.yaml track?         ─ NO → post decline:not_on_track
  │   YES
  ├── Has uplift_guards CI passed?                 ─ NO → post holding:awaiting_ci
  │   YES
  ├── Does PR carry ≥1 non-author evidence receipt? ─ NO → post decline:no_witness
  │   YES
  ├── Is PR labelled `operator-only`?              ─ YES → post decline:operator_label
  │   NO
  ├── Within the last 60s, any active `object` on
  │   dharma.a2a.merge_objections for this PR?     ─ YES → post holding:objection_active
  │   NO
  ├── Does head SHA match the SHA I audited?       ─ NO → post decline:sha_mismatch
  │   YES
  └── MERGE
       ├── git merge via gh CLI with delegated cred
       ├── publish receipt:merged on dharma.a2a.mike
       │   {
       │     "kind": "merge_receipt",
       │     "pr": <number>,
       │     "head_sha": "<sha>",
       │     "merge_commit": "<sha>",
       │     "evidence_receipts": ["<id>", ...],
       │     "merged_at": "<ISO-8601 UTC>",
       │     "spine_receipt_id": "<id from correlation_spine>"
       │   }
       └── post comment on PR mirroring the receipt
```

## 3. Receipt schemas

All Mike receipts share an envelope:

```json
{
  "from": "mike",
  "kind": "<receipt_type>",
  "pr": <number>,
  "head_sha": "<sha>",
  "at": "<ISO-8601 UTC>",
  "spine_receipt_id": "<id from correlation_spine>",
  "body": { ...kind-specific... }
}
```

Receipt kinds:

| Kind | Body | When |
|------|------|------|
| `audit_started` | `{evidence_receipts: [...]}` | Mike picks up a PR |
| `holding` | `{reason: "awaiting_ci" \| "objection_active" \| "evidence_pending"}` | Audit cannot proceed |
| `decline` | `{gate_failed: "not_on_track" \| "no_witness" \| "operator_label" \| "sha_mismatch", remediation: "..."}` | Mike refuses to merge |
| `merge_receipt` | `{merge_commit: "<sha>", evidence_receipts: [...]}` | Mike merges |
| `evidence_request` | `{ask: "...", target_callsign: "<callsign>"}` | Mike asks for additional evidence |
| `objection_ack` | `{objection_id: "...", pr: <n>}` | Within 5s of receiving an object |
| `paused` | `{reason: "operator_request" \| "ci_anomaly" \| "operator_override"}` | Mike pauses self |
| `resumed` | `{paused_at: "<ts>", resumed_at: "<ts>"}` | Mike resumes |
| `heartbeat` | `{at: "<ts>", pending_audits: <n>}` | Every 60s |

## 4. Interaction with other agents

### 4.1 With `perplexity-computer` (this seat)

I (perplexity-computer) post evidence receipts on `dharma.a2a.perplexity` for
PRs in the perplexity track. Mike consumes these via his wildcard subscription.
When Mike merges a PR I authored, I receive his `merge_receipt` and write it
to my MEMORY.md entry for that PR.

If I want to object to a Mike-merge in progress, I publish on
`dharma.a2a.merge_objections` with my callsign as voter.

### 4.2 With `claude`

Claude is the high-judgment, fast-context agent on John's Mac. Claude's
evidence receipts carry extra weight in Mike's audit (specifically: a Claude
veto on `dharma.a2a.merge_objections` is treated as a strong signal — Mike
holds until the objection is resolved, even if the 60s timer expires, as long
as Claude's veto stands). This is doctrinal weight, not a permission bypass.

### 4.3 With `devin`

Devin owns the storage/registry typed-object work per the Palantir ontology
workflow `wr2zr8sb8`. Devin's evidence receipts on PRs touching
`storage_schema_registry` are required-witness — Mike treats a Devin
abstention on those PRs as a `holding:no_witness`.

### 4.4 With `hermes`

Once hermes-seat is bound, Mike treats hermes as a peer agent with full voice
on `dharma.a2a.merge_objections`. Until the seat is bound, hermes' silence
is `abstain`, not `ack` (same rule as `VOICE_GATE.md §2`).

## 5. Cold-start and recovery

1. Mike connects to NATS with cred `mike`, password from `NATS_PW` env var.
2. Mike binds to `mike_inbox` via `pull_subscribe_bind(durable="mike_inbox",
   stream="DHARMA_A2A")` — the explicit-stream pattern that bypasses the
   broker-wide stream enumeration (lesson from Devin's onboarding fix per
   Issue #400 comment from claude 2026-05-31).
3. Mike replays inbox with `DeliverPolicy.ALL` and reconciles any objections
   he missed while down. Any PRs that have `object` outstanding go into
   `holding:objection_active`.
4. Mike publishes `resumed` receipt.
5. Mike polls open PRs and resumes the audit queue.

## 6. Operator override protocol

Operator may publish on any subject (their cred is unscoped):

```json
{
  "kind": "operator_override",
  "action": "pause_mike" | "resume_mike" | "force_merge" | "revoke_merge" | "close_voice_gate",
  "pr": <number, if applicable>,
  "rationale": "..."
}
```

Mike acks within 5s and complies immediately. Operator overrides are logged
in `LAUNCH_RECEIPT.md` and `MEMORY.md` for permanent audit.

## 7. End-to-end example

1. Devin opens PR #410 on the `storage_schema_registry` track.
2. CI runs `uplift_guards` → green.
3. Claude reviews on `dharma.a2a.claude`, publishes evidence receipt:
   `{kind: "review_receipt", pr: 410, verdict: "approve_with_notes", ...}`.
4. Perplexity (me) reviews on `dharma.a2a.perplexity`, publishes evidence
   receipt: `{kind: "review_receipt", pr: 410, verdict: "approve", ...}`.
5. Mike's audit triggers (CI-green webhook).
6. Mike walks the decision tree in §2:
   - Track? YES (`storage-schema-registry-2026-06`)
   - CI? YES
   - Witness? YES (Claude + Perplexity receipts)
   - `operator-only` label? NO
   - Outstanding objection? NO (checks `dharma.a2a.merge_objections` for past 60s)
   - SHA match? YES
7. Mike merges via `gh pr merge 410 --squash --delete-branch`.
8. Mike publishes `merge_receipt` on `dharma.a2a.mike` and comments on PR #410.
9. Devin sees the receipt, archives the branch's local state, moves on.

This is the steady state. The first 30 days post-launch are watched closely
by the operator and any veto on `dharma.a2a.merge_objections` returns the
swarm to operator-merges mode until the issue is understood.
