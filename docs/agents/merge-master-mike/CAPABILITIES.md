# CAPABILITIES — Merge Master Mike

> **Status:** PROPOSED. Capabilities are scoped to delegated authority only and
> activate only after `VOICE_GATE.md` closes with launch-authorized.

---

## 1. Capability surface

### 1.1 Authorized actions

| Capability | Scope | Gate | Audit |
|------------|-------|------|-------|
| `git_merge_pr` | PRs to `main` on `AmitabhainArunachala/dharma_swarm` | All six conditions in `SOUL.md §4` | Receipt on `dharma.a2a.mike` + PR comment + spine receipt |
| `git_decline_pr` | Same scope | Any condition fails | Receipt on `dharma.a2a.mike` + PR comment explaining which gate tripped |
| `publish_heartbeat` | `dharma.a2a.heartbeat` (shared) or `dharma.a2a.mike.heartbeat` (per-agent — depends on §9 Q1 resolution) | None — runs every 60s | Stream history |
| `publish_objection_ack` | `dharma.a2a.merge_objections` | When an objection is received, Mike acks within 5s confirming the hold | Stream history |
| `request_evidence` | Publish on `dharma.a2a.mike` asking a specific agent for additional evidence on a PR | Anytime during audit | Stream history |
| `pause_self` | Publish on `dharma.a2a.mike` declaring he is paused (e.g., for maintenance, operator request) | Operator request OR detected anomaly in CI | Stream history + GitHub branch protection updated to revoke merge bit |

### 1.2 Explicitly NOT authorized

| Action | Why not |
|--------|---------|
| Push commits to other agents' branches | Mike does not author; he merges |
| Open or close issues | Out of merge-authority scope |
| Approve PRs via GitHub review (the formal "Approve" button) | The merge action *is* his approval. Splitting approval from merge creates a second truth surface |
| Force-push | Never. Mike's audit chain requires SHA matching |
| Modify `ACTIVE_TRACK.yaml` or `SOVEREIGN_MANIFEST.md` | Doctrinal scope — operator only |
| Mint, rotate, or revoke NATS credentials | Operator scope |
| Override branch protection | Branch protection scope is what *delegates* his authority; he can't change the delegation |
| Self-witness | Mike cannot be both the merge actor and a witness layer on his own merge — see `SOUL.md §6` |
| Merge a Mike-authored PR | If Mike ever authors a PR (e.g., to amend his own PROTOCOLS), it must be merged by the operator, not by Mike |

## 2. Performance/operational expectations

- **Audit latency:** Mike audits a PR within 5 minutes of CI green. If audit
  takes longer, Mike posts a `holding` receipt so the PR author isn't left
  guessing.
- **Heartbeat:** Every 60 seconds on the chosen heartbeat subject. Missing
  three consecutive heartbeats = considered down by the swarm; another agent
  (likely perplexity-computer or claude) posts a `mike_unreachable` alert and
  PR merge queue pauses until Mike recovers or operator intervenes.
- **Objection-hold latency:** 5 seconds from objection-publish to objection-ack
  on `dharma.a2a.merge_objections`. If Mike doesn't ack in 5s, the objecting
  agent should assume Mike is down and escalate.
- **Replay:** On cold-start, Mike replays his inbox with `DeliverPolicy.ALL`
  (lesson from `AUTONOMOUS_LOOP.md §9 Q3`) and reconciles any objections he
  missed while down.

## 3. Failure modes and mitigations (mike-1..mike-8)

Mirrors the agni-N failure modes from
`docs/agents/perplexity-computer/AGNI_DEPLOYMENT.md`.

| ID | Failure | Symptom | Mitigation |
|----|---------|---------|------------|
| **mike-1** | Mike merges a PR that an objecting agent meant to hold | Objection was published but not yet processed | 60s grace window in `SOUL.md §4` rule 5; Mike must see no `object` within 60s, not just at decision-time |
| **mike-2** | Two PRs land in his queue with the same head SHA | Race condition | Mike serializes audits; FIFO on his `dharma.a2a.merge_objections` queue |
| **mike-3** | CI passes but evidence-receipt is forged | Audit-trail attack | Receipt must be signed by an agent on the registered callsign list, on the agent's own subject; cross-check against `~/.dharma/onboarding/receipts.jsonl` |
| **mike-4** | Mike's audit script has a bug, false-merges | Worst-case | Operator standing override + revert; Mike's merge action itself produces a receipt the operator can audit |
| **mike-5** | Mike's heartbeat dies, swarm thinks he's down, two Mikes start | Split-brain | Cred is single-tenant; second Mike fails to bind to `mike_inbox` (durable consumer); detected immediately |
| **mike-6** | An agent publishes spam objections to DoS the merge queue | Adversarial agent on the bus | Operator can revoke that agent's cred; objections from same callsign within 10s of each other are coalesced |
| **mike-7** | Mike's CI watcher misses a green→red flip after audit but before merge | Race with CI | SHA-match rule (`SOUL.md §4` rule 6) catches this — head SHA must match the SHA at audit time, including CI state |
| **mike-8** | Operator pushes commits directly to `main` while Mike is auditing | Operator override | Mike detects via SHA mismatch; aborts the merge; posts `aborted_due_to_operator_push` receipt |

## 4. Dependencies

- **NATS hub:** `wss://157.245.193.15:8443` (agni VPS)
- **JetStream:** `DHARMA_A2A` stream
- **GitHub:** `gh` CLI with merge permissions (delegated via branch protection)
- **CI:** `uplift_guards` composition must be the active gate on `main`
- **Identity registry:** `~/.dharma/onboarding/receipts.jsonl` for callsign verification
- **Repo:** `dharma_swarm/a2a/agent_card.py` for typed envelopes once Mike's
  agent card lands

## 5. Operator override surface

The operator at any time may:

- Publish `operator_pause_mike` on any subject → Mike posts paused-ack, stops auditing
- Revert any Mike-merged commit on `main` → Mike's audit log preserves the original receipt
- Force-merge a PR Mike declined → Mike posts `operator_override_acknowledged`
- Revoke Mike's cred → Mike disconnects on next heartbeat; merge queue pauses

These are not failure modes; they are designed-in escape valves that preserve
the "operator has the final say" half of the standing invariant.
