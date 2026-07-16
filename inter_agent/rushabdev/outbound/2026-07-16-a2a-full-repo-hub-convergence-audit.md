# A2A Full-Repository and Hub-Convergence Audit

**Date:** 2026-07-16  
**Verdict:** **HOLD live migration; converge the architecture and repository contract first.**

## 1. Audit scope

The audit used a clean worktree at current `origin/main`:

- Repository: `AmitabhainArunachala/dharma_swarm`
- Audited commit: `954e6f47cf362c07654939b365ebdb2c901f8ab5`
- Clean audit worktree: `/tmp/dharma_swarm_a2a_audit_954e6f47`

Dirty/deployed trees were preserved, not reset or overwritten:

- `/home/openclaw/dharma_swarm`: commit `d3e084c6`, **111 commits behind**, untracked local work
- `/opt/dharma-dashboard`: commit `a370d3cd`, **36 commits behind**, unresolved `Makefile` conflict
- `/opt/dharma-a2a-gateway`: commit `f057416c`, **134 commits behind**, locally modified mailbox gateway
- Meghadharma Command Node: deployed from open draft PR #947 commit `f73ee7b2`

A clean worktree was necessary because pulling any of the deployed trees would risk destroying uncommitted or conflicted work.

## 2. Repository inventory

Current main contains substantial A2A implementation—not a greenfield shell:

| Surface | Files | Approximate lines |
|---|---:|---:|
| `dharma_swarm/a2a/` core | 17 | 5,451 |
| A2A/NATS-related tests | 112 | 24,419 |
| Runtime/governance scripts | 29 | 7,594 |
| A2A/NATS docs and contracts | 52 | 11,761 |
| Agent registration manifests | 13 | 1,064 |
| Other matching tracked surfaces | 168 | 2,088 |
| **Total matching tracked surface** | **391** | **42,377** |

There are **65 mainline commits** touching the principal A2A/NATS surfaces since 2026-05-01.

### Implemented owners on main

- `a2a_server.py`: A2A task lifecycle and server
- `agent_card.py`: AgentCard schema, aliases, registry
- `agent_directory.py`: agent discovery projection
- `agent_presence.py`: current presence roster/filesystem projection
- `delivery_topology.py`: crash-safe delivery state transitions
- `mailbox_gateway.py`: authenticated HTTPS send/drain edge
- `nats_transport.py` + support: canonical typed NATS task transport, idempotency, ACK/NACK, DLQ
- `node_gateway.py`: HTTP A2A task/control gateway
- `node_registry.py`: remote node registry and health projection
- `registry_hydrator.py`: card-to-node hydration
- `spine_adapter.py`: task dispatch through runtime spine
- `task_receipt.py`: structured receipt validation/quarantine
- `scripts/runtime/a2a_*`: operator send, inbox bridge, reply capture, domain receipt worker, gateway server
- `scripts/runtime/devin_a2a_agent.py`: persistent AGNI-connected agent pattern
- `scripts/governance/*nats*` / `*a2a*`: contract, evidence and onboarding checks

### Additional implementation conflicts found by independent review

- The main-repository `NodeGateway` is now mounted and initialized, contrary to older architecture prose. However, it submits into the local spine/`A2AServer`; it does **not** yet wrap external tasks into `A2ANatsTransport`, so the external-edge-to-canonical-NATS contract remains incomplete.
- Two incompatible validators use the same schema identifier, `dharma_a2a_task_receipt.v1`: `dharma_swarm/a2a/task_receipt.py` expects claim/evidence/verdict fields, while `operator_core/a2a_task_lifecycle.py` expects receipt/task/agent IDs, terminal status, summary, hash, evaluation and return address. One schema name currently denotes two wire shapes.
- `A2ANatsTransport.connect()` accepts an endpoint but does not load the authenticated/TLS/CA connection settings required by the AGNI field. Compatibility tools use separate NATS configuration helpers. The canonical transport therefore lacks the production connection factory it needs.
- There are three competing subject families: stable AgentUID inboxes, live callsign compatibility subjects, and canonical task subjects. There is also an inconsistent `dharma.a2a.reply.<packet_id>` constant while real compatibility sends use `<target-subject>.reply.<packet_id>`.
- Identity is spread across manifests, CardRegistry, NodeRegistry, static presence and contact registries, aliases, the fleet field registry, onboarding receipts, telemetry, living-agent docks and git seats. Only the runtime-registration part of onboarding is transactional; the rest is still manual.
- The alias `hermes -> hermes-m5` conflicts with the field registry's distinction between AGNI `hermes` and operator-Mac `hermes-m5`.

### Authority hierarchy in the repository

1. `docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md` owns the **target internal transport contract**.
2. `docs/ops/FLEET_FIELD_REGISTRY.yaml` owns the **observed live routing field**.
3. `docs/architecture/A2A_ALWAYS_ON_SPINE_MASTER_PLAN.md` owns the integration/build order.
4. `scripts/runtime/a2a_topology.py` explicitly separates live compatibility topology from target topology.
5. `docs/architecture/A2A_COORDINATION_SUBSTRATE.md` is **dormant/superseded** and must not become a parallel implementation.

## 3. What “AGNI” currently means

The repository is unambiguous:

- **AGNI hub/VPS:** `157.245.193.15`
- Live endpoint: NATS `:4222`, WSS `:8443`
- Live stream: `DHARMA_A2A`
- Hub-resident semantic identity: currently `hermes`, described as **AGNI Hermes**

Meghadharma is represented separately in the repository as a Codex/operator seat. The repository does **not** yet know about:

- Meghadharma’s new NATS server at `100.103.106.70`
- `meghadharma-hermes`
- the new `FLEET_STATE` KV bucket
- the `FLEET_ARTIFACTS` object store
- the deployed Command Node on `178.128.87.170`

Therefore the old AGNI broker cannot honestly be called “legacy” yet. It remains the repo-declared and live-field authority until a governed migration changes that declaration.

There is also an operator-language collision: newer operational notes sometimes use AGNI for Meghadharma. This must be resolved by separating:

- **logical hub identity** (`agni-hub` or equivalent),
- **physical host** (`157.245.193.15` or `meghadharma-cloud`), and
- **agent identity** (`agni-hermes`, `meghadharma-hermes`, etc.).

## 4. Live topology observed

### AGNI / `157.245.193.15`

- Reachable NATS `4222`, WSS `8443`, HTTPS `443`
- `DHARMA_A2A`: 1,618 retained messages at probe time
- Sequence range: `8119062`–`8120679`
- 42 durable consumers
- One replica
- Explicit legacy subjects, including Rushabdev and fleet subjects
- SSH unavailable from this operator node
- This is still the broker named by the canonical fleet registry and agent cards

### Meghadharma / `100.103.106.70` over Tailscale

- Tailscale-connected to openclaw23, Mac and iPhone
- NATS 2.10.9 active
- `DHARMA_A2A`: 4,177 messages, 2 consumers, one replica
- `KV_FLEET_STATE`: 27 live records at probe time
- `OBJ_FLEET_ARTIFACTS`: 2 records
- Active Meghadharma semantic bridge and fleet-status projector
- Active Command Node backend/frontend from open PR #947
- NATS stream captures broad `dharma.a2a.>` and `dharma.agent.>` subjects
- Two configured principals still have unrestricted publish/subscribe grants
- NATS listens on all interfaces; monitoring also listens beyond loopback
- Local Command Node state backups run every ~15 minutes, but they are on the same host and **do not contain JetStream state**
- Litestream container is restart-looping (18,207 restarts at probe time)
- `dharma-swarm` container is unhealthy
- JetStream has no replica or proven off-host restore

### openclaw23 / `167.172.95.184`

- Public Command Node: `command.167-172-95-184.nip.io`
- Public mailbox gateway: `a2a.167-172-95-184.nip.io`
- Gateway currently connects to AGNI `157.245.193.15`, not Meghadharma
- Active Rushabdev semantic bridge and collaboration loop also use AGNI
- Standalone Command Node deployment contains only built artifacts; its rebuildable source is not present in that deployment directory
- Main dashboard/API services run from stale/conflicted checkouts

### Operator surfaces

There are currently at least three overlapping control-plane implementations:

1. Main-repository `NodeGateway` + dashboard/API surfaces.
2. Standalone Command Node at `167.172.95.184`.
3. PR #947 A2A operator node deployed at Meghadharma.

One operator URL may survive, but only after its source is canonicalized and it becomes a projection over the chosen bus—not a fourth authority.

## 5. Repository target versus live topology

The repository target is **multiple streams on one NATS/JetStream authority**, not multiple brokers:

- `DS_FLEET`
- `DS_AGENT_INBOX`
- `DS_TASKS`
- `DS_RECEIPTS`
- `DS_OPERATOR`
- `DS_DLQ`

The live compatibility stream is `DHARMA_A2A`.

Important incompatibility: Meghadharma’s current broad `DHARMA_A2A` subjects overlap the target streams:

- `dharma.a2a.>` overlaps target `dharma.a2a.task.>`
- `dharma.agent.>` overlaps target `dharma.agent.*.inbox`

JetStream does not allow overlapping subjects across ordinary streams. We must choose one of these before migration:

1. retain a single broad stream and formally supersede the `DS_*` contract; or
2. retain the repository’s richer `DS_*` topology and narrow/retire the broad compatibility stream during migration.

For robustness, distinct retention, replay and consumer policies, option 2 is the stronger fit for “one node, many layers.”

PR #947 adds another unresolved topology:

- default presence stream: `DS_PRESENCE`
- subject: `dharma.agent.*.presence`
- live deployment overrides it to current `DHARMA_A2A`

`DS_PRESENCE` is not in the master spec. Presence should be folded into `DS_FLEET` or explicitly ratified as another stream before PR #947 is landed.

## 6. Open and unmerged A2A work

### PR #947 — durable A2A presence and operator node

- 53 files, roughly 14,004 additions
- Deployed on Meghadharma at commit `f73ee7b2`
- **OPEN, DRAFT, CONFLICTING/DIRTY**
- Previous CI had one ACTIVE_TRACK governance failure
- Adds persistent presence, phone-first operator UI and crash-safe STORED-only send receipts
- Python-focused audit: **82 passed**
- Node operator suite: **108/109 passed locally**; the one failure is root-execution-specific because a test expects a root-owned sticky custom ancestor to be rejected while the implementation explicitly permits root-owned sticky ancestry. Prior non-root CI reported all 109 passing.
- It cannot be treated as canonical production code until rebased, reconciled and merged.

### PR #949 — governance ownership for #947

- OPEN, DRAFT, mergeable but blocked
- Must precede #947 according to the PR’s own ordering contract

### PR #904 — remote holon fast path

- OPEN, DRAFT
- Adds SSH/preflight/identity activation controls, not a replacement A2A transport
- Explicitly holds deployment because live NATS evidence is stale and the probed VPSs are not activation-ready

### PR #973 — fleet model-pool unification

- OPEN, DRAFT, design-only
- Confirms three-node drift and reports broken Meghadharma Litestream/off-host continuity
- Does not establish transport authority

### Closed, unmerged but relevant

- PR #868: full A2A fleet/control-plane audit; useful evidence, not canonical because it closed unmerged
- PR #892: Synadia/CAR leaf-node proposal; closed after stream-overlap/governance findings and must not be treated as active architecture

## 7. Verification results

### Current `origin/main`

- Fleet registry check: **PASS** — 7 probed agents, secret policy holds
- Broad A2A-related test selection: **939 passed** across 62 test files
- Agent onboarding drift check found:
  - roster without card: `codex_composer`, `hermes-m5`
  - card without roster: `merge_master_mike`, `qwen_code`, `sis_steward`
  - no local runtime receipt identities in the clean checkout
- NATS substrate contract: **FAIL**
  - onboarding does not render the canonical NATS spec path
  - live NATS evidence is approximately 14 days stale
- Live NATS production-evidence check: **FAIL — stale evidence**

The code surface is substantial and well-tested, but repository governance correctly refuses a production-ready claim.

## 8. Recommended converged architecture

“Single node, many layers” should mean one **primary writable hub node**, not one shared identity or one irreversible failure domain.

```text
Stable logical hub name: AGNI-HUB
                 │
        Tailscale private underlay
                 │
      ONE NATS/JetStream server authority
                 │
 ┌───────────────┼────────────────────┐
 │               │                    │
DS_* streams   JetStream KV       Object Store
 │               │                    │
 ├─ identity/ACL/keys/signatures      │
 ├─ HTTPS mailbox edge                │
 ├─ WSS edge                          │
 ├─ semantic bridges                  │
 ├─ presence/status projectors        │
 └─ Command Node/operator API ── phone/Telegram
```

Every runtime remains a separate authenticated identity:

- `agni-hermes`
- `meghadharma-hermes`
- `rushabdev`
- Cursor
- Claude Code
- Perplexity
- Devin
- other registered agents

Recommended naming decision:

- Preserve **AGNI** as the logical hub identity if desired.
- Call `157.245.193.15` `agni-legacy` during migration.
- If Meghadharma wins the host decision, promote it to the physical home of `agni-hub` after state migration.
- Never infer an agent UID from the machine name or Tailscale IP.

Evidence currently favors Meghadharma as the future physical home because it is controllable, on Tailscale and already has KV/Object Store. It is **not ready yet** because security, stream topology, repo authority and off-host durability remain open.

## 9. Required cutover gates

1. Ratify one architecture decision in the repository: logical hub ID, physical host, stable service name, stream topology, identity grammar and rollback owner.
2. Ratify the `DS_*` target and a two-stage migration: first relocate the authority while preserving the compatibility `DHARMA_A2A` contract; only after the new authority is stable, narrow the compatibility stream and create the non-overlapping `DS_*` streams. Do not combine broker relocation, stream renaming, identity repair and consumer recreation into one cutover.
3. Add/ratify the presence subject in `DS_FLEET`; do not silently create `DS_PRESENCE`.
4. Regain administrative access to the current AGNI host and export:
   - stream configuration,
   - retained messages or snapshot,
   - all 42 consumer configurations and active-state classification,
   - authentication/ACL configuration,
   - final sequence watermark.
5. Replace wildcard principals with per-agent credentials and least-privilege ACLs; rotate historically exposed credentials.
6. Restrict NATS/monitoring to Tailscale or loopback as appropriate; expose HTTPS/WSS edges rather than raw broker access to sandboxes.
7. Build a bounded, idempotent compatibility bridge with hop markers and loop prevention. Do not make two ledgers permanent writable authorities.
8. Rebase and reconcile PRs #949/#947; extract useful operator/presence work rather than maintaining an unmerged production fork.
9. Put the surviving Command Node source and deployment definition on main; retire standalone build-only deployments.
10. Collapse the duplicate `dharma_a2a_task_receipt.v1` definitions into one unambiguous schema contract and add compatibility translation for historical receipts.
11. Move the authenticated/TLS NATS connection factory into the canonical A2A transport before making it the production send path.
12. Migrate one identity at a time with all four proof tiers:
    - publish accepted,
    - delivered to consumer,
    - handler acknowledged,
    - semantic/domain receipt.
13. Take off-host JetStream/KV/Object snapshots and complete a restore drill before claiming durability.
14. Only after every canonical identity is proven on the new hub: freeze old writes, record final watermark, drain, archive and retire `157.245.193.15` as a broker.

## 10. Independent three-way review

Three read-only auditors independently examined architecture/history, code/tests and live-topology convergence. Their shared conclusions match this report:

- AGNI `157.245.193.15` remains the merged live-field authority.
- No merged Meghadharma/Tailscale one-bus migration exists.
- Meghadharma is the stronger future physical anchor, but is not production-ready.
- `DHARMA_A2A` is live compatibility topology; `DS_*` remains target topology.
- The repository correctly fails closed on stale live evidence.
- One logical authority with AGNI preserved as a leaf/compute/DR role is the correct convergence model.

The implementation auditor separately ran 48 focused files: **533 passed** with approximately **81% branch-aware coverage** over `dharma_swarm/a2a`. Combined with the broader 62-file run above (**939 passed**), this supports code-substrate maturity but not live production readiness.

## Final verdict

The desired architecture is coherent: **one primary hub node with many internal layers and many independently authenticated agents**.

The immediate proposal is not ready for execution because it omits the repository-declared AGNI authority, conflicts with the repository stream contract, depends on unmerged operator code, and lacks off-host JetStream durability.

**No live traffic, broker configuration or credential was changed during this audit.**
