# MERGE AUTHORITY DELEGATION — Stage-2 Doctrine Amendment

> **Status:** PROPOSED in PR #403. Activates only after `VOICE_GATE.md` closes
> with launch-authorized.
> **Authored:** 2026-06-01 by perplexity-computer, on operator directive.
> **Scope:** Authorizes a delegated git-merge authority to a new agent
> (`merge-master-mike`) while preserving operator sovereignty and swarm voice.

---

## 1. What this amends

This amendment **does not modify** `SOVEREIGN_MANIFEST.md` directly. It is a
**delegation instrument** that the operator (`@AmitabhainArunachala`) authorizes
under his standing sovereignty. The sovereign manifest remains the architectural
source of truth; this delegation is an operational specialization of the
operator's merge authority.

The amendment specifically:

- Authorizes one named agent (`merge-master-mike`, callsign `mike`) to perform
  git merges to `main` on `AmitabhainArunachala/dharma_swarm` under the
  six-gate decision tree in `docs/agents/merge-master-mike/PROTOCOLS.md §2`.
- Establishes the swarm's standing veto via `dharma.a2a.merge_objections`.
- Preserves operator's absolute override.
- Codifies the multi-track policy floor reference in `SOVEREIGN_MANIFEST.md` L13
  by adding a `concurrent_tracks` schema slot to `ACTIVE_TRACK.yaml`.

## 2. Doctrinal posture (the four invariants)

> **I1.** The operator is sovereign. Delegation does not transfer sovereignty.
> **I2.** The swarm has a voice. Any credentialed agent can hold a merge.
> **I3.** Mike does not self-witness. He occupies the task-owner layer; the
> other four witness layers must be present and verifiable.
> **I4.** No parallel truth surface. Mike uses the same correlation_spine and
> uplift_guards composition every other agent uses.

These four invariants are non-negotiable. Any future amendment that weakens
any one of them requires a fresh voice-gate round per `VOICE_GATE.md §7`.

## 3. What delegation does NOT include

To prevent doctrinal drift via scope creep (a common mode in any delegation
regime), the following are explicitly out of scope:

- **Doctrine amendment.** Only the operator may amend `SOVEREIGN_MANIFEST.md`,
  `ACTIVE_TRACK.yaml`, or any file under `docs/governance/`. Mike has read-only
  access to these surfaces.
- **Track lifecycle.** Mike cannot open, close, or modify tracks. He can only
  audit whether a PR is *on* a track.
- **Credential management.** Mike cannot mint, rotate, or revoke any NATS cred,
  including his own.
- **Branch protection rules.** The very mechanism that delegates Mike's
  authority is operator-controlled. Mike cannot modify the delegation.
- **Operator-only PRs.** Any PR labelled `operator-only` is invisible to Mike's
  merge action regardless of other gates passing.
- **Cross-repo authority.** This delegation applies only to
  `AmitabhainArunachala/dharma_swarm`. Any other repo requires a fresh
  amendment.

## 4. Standing override mechanisms

Operator may at any time:

1. **Pause Mike:** publish `kind: "operator_override", action: "pause_mike"`
   on any subject. Mike pauses within 5s.
2. **Revoke a merge:** revert the merge commit on `main`. The merge receipt
   remains in `MEMORY.md` as historical record.
3. **Force-merge:** merge a PR Mike declined. Operator's force-merge produces
   an `operator_override_merge_receipt` that Mike acknowledges.
4. **Revoke cred:** revoke the `mike` NATS user. Mike disconnects on next
   heartbeat. Merge queue pauses pending operator decision.
5. **Close voice gate:** publish `kind: "operator_override",
   action: "close_voice_gate"` at any time during a voice-gate round. Operator
   override is logged and supersedes the tally.

These are not Mike-failure paths. They are the operator's standing instruments.

## 5. Schema extension to ACTIVE_TRACK.yaml

This amendment adds a new top-level key to `ACTIVE_TRACK.yaml`:

```yaml
# ---------------------------------------------------------------------------
# Track policy (added by MERGE_AUTHORITY_DELEGATION.md, 2026-06-01)
# ---------------------------------------------------------------------------
track_policy:
  schema_version: 1
  min_active: 1
  max_active: 10
  rationale: |
    SOVEREIGN_MANIFEST.md L13 (2026-05-31 doctrine amendment) authorized the
    operator to run between min_active and max_active concurrent tracks. This
    block is the machine-readable expression of that policy. The default
    floor of 1 holds whenever the operator has not explicitly opened a second.

concurrent_tracks: []
  # Each entry must have: id, name, status (ACTIVE | SHIPPABLE), owner,
  # opened_at, verified_at, ttl_days, surfaces, prerequisites,
  # completion_criteria. Surfaces must not overlap the active_track.surfaces.
```

The `merge-master-mike-launch-2026-06` track (if the operator chooses to open
it as a concurrent track rather than wait for the spine track to ship) would
be the first entry in `concurrent_tracks`:

```yaml
concurrent_tracks:
  - id: merge-master-mike-launch-2026-06
    name: Merge Master Mike — delegated merge-authority launch
    status: PROPOSED
    opened_at: "2026-06-01"
    verified_at: "2026-06-01"
    ttl_days: 7
    owner: "@AmitabhainArunachala"
    description: |
      Insert Mike (callsign mike) as the fifth NATS agent and final
      delegated merge authority. Pre-launch voice gate per
      docs/agents/merge-master-mike/VOICE_GATE.md must close with
      launch-authorized before scoped cred is minted.
    surfaces:
      - docs/agents/merge-master-mike/**
      - docs/governance/MERGE_AUTHORITY_DELEGATION.md
    prerequisites:
      - id: identity_nest_complete
        kind: file_exists
        file: docs/agents/merge-master-mike/SOUL.md
      - id: voice_gate_doc_exists
        kind: file_exists
        file: docs/agents/merge-master-mike/VOICE_GATE.md
    completion_criteria:
      - id: launch_receipt_exists
        kind: file_exists
        file: docs/agents/merge-master-mike/LAUNCH_RECEIPT.md
      - id: mike_cred_minted
        kind: external_witness
        receipt: "operator publishes mike_cred_minted on NATS"
      - id: first_merge_receipt
        kind: external_witness
        receipt: "first merge_receipt on dharma.a2a.mike"
```

If the operator prefers serial opening, the PROPOSED status holds until the
Runtime Truth Spine track ships, then this becomes the next ACTIVE.

## 6. Acceptance criteria for THIS amendment

This amendment becomes live when:

- [ ] Operator approves (merges PR #403).
- [ ] `VOICE_GATE.md` voice-gate round closes with launch-authorized.
- [ ] `LAUNCH_RECEIPT.md` is committed with the tally.
- [ ] `mike` scoped cred is minted on the agni hub.
- [ ] Branch-protection rule on `main` allows merge from `mike` user.
- [ ] `mike_inbox` durable consumer exists with `DeliverPolicy.ALL`.
- [ ] `dharma.a2a.merge_objections` topic exists; every credentialed agent
      has publish permission on it.

## 7. Reversibility

This delegation is fully reversible. The operator may at any time:

- Revoke Mike's cred → delegation effectively void.
- Add an `operator-only` label to all PRs → Mike's authority effectively void.
- Remove the branch-protection rule → Mike's merge attempts return permission-denied.
- Publish a doctrine-amendment PR closing this delegation → amendment closed,
  Mike's identity nest moves to `docs/agents/_archived/merge-master-mike/`.

There is no path by which delegation becomes irreversible. This is by design.

## 8. Cross-references

- `docs/agents/merge-master-mike/SOUL.md` — what Mike is
- `docs/agents/merge-master-mike/CAPABILITIES.md` — exact authority scope
- `docs/agents/merge-master-mike/PROTOCOLS.md` — decision tree and receipts
- `docs/agents/merge-master-mike/VOICE_GATE.md` — pre-launch voicing protocol
- `docs/agents/merge-master-mike/RECOGNITION_STANCE.md` — witness model
- `docs/agents/merge-master-mike/WAKE_CONTEXT.md` — cold-start checklist
- `docs/governance/SOVEREIGN_MANIFEST.md` L13 — multi-track policy
  (the source clause this amendment specializes)
