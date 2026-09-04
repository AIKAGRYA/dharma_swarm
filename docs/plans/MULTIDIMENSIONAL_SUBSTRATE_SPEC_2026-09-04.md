---
role: working_plan
date: 2026-09-04
status: DRAFT — operator-ordered ("supersede and sublimate every dimension of agentic harness and A2A infra in the 2026 zeitgeist"); no runtime, merge, or governance authority until admitted as work packets in docs/governance/ACTIVE_TRACK.yaml
subordinates_to: docs/plans/THE_BLUEPRINT_2026-08-29.md (anatomy); docs/research/web5_planetary_commons_2026-07-11/field_agentic-protocols.md (protocol field report); docs/governance/CANONICAL_DOC_STACK.md
world:
  commit: b59b8ef (branch tip) · host: Claude Code cloud sandbox · branch: claude/dharma-swarm-fusion-review-voer57
---

# THE MULTIDIMENSIONAL SUBSTRATE — one identity, one door, one ledger, every harness an adapter

**Thesis in one line.** Hermes, OpenClaw, Claude Code, Codex, Devin, and the
next harness that ships on Monday are *seats*. NATS, A2A-over-HTTP, MCP, the
HTTPS mailbox gateway, Telegram, and the next transport are *doors*. The
substrate that outlives all of them is three things this repo already
partially owns: a single agent identity that every door binds to, a single
action path that every consequence passes through, and a single receipt
ledger that every claim is checked against. "Supersede and sublimate" means:
never rebuild what a harness or protocol does well; absorb it as an adapter
behind those three invariants. That is also exactly what the 2026 field says
the market lacks (see §2, "the whitespace").

Glossary: **harness** = the shell around a model that gives it tools,
memory, and a schedule (Hermes, Claude Code). **A2A** = the Linux Foundation
Agent2Agent protocol for agents talking over HTTP, distinct from this repo's
NATS "a2a" subjects. **MCP** = the tool-connection protocol. **receipt** = a
signed, non-backdateable record that an action happened.

## 1. Where the 2026 zeitgeist actually landed (dated, sourced)

The repo's own July field report is the authoritative survey
(`docs/research/web5_planetary_commons_2026-07-11/field_agentic-protocols.md`);
this section only adds what moved since, from sources fetched 2026-09-04.

| Dimension | 2026 state | What it settles for us |
|---|---|---|
| Agent-to-agent | A2A under the Linux Foundation; v1.0 shipped 2026-04-09 with signed Agent Cards; v1.0.1 (May 2026) added an **extension mechanism** for new data, RPC methods, and state machines; 150+ orgs, in Azure Foundry and Bedrock AgentCore | Our Dharma-specific claims (receipts, authority tier, gate results) ride as an A2A **extension**, not a fork. `dharma_swarm/a2a/agent_card.py:1-16` already implements the 1.0 card with `extensions[]` |
| Tools | MCP under the Agentic AI Foundation (Dec 2025); 2025-11-25 spec added async **tasks**, elicitation, server-side loops, extensions; 2026 roadmap: `.well-known` discovery, enterprise audit trails, DPoP, workload identity; stateless core in the next release | Mission Control is already an MCP server (`dharma_swarm/mission_control_mcp.py`). MCP tasks are the right shape for long-running owner operations |
| Skills | Agent Skills open standard (agentskills.io, Dec 2025) adopted by ~40 products incl. Codex, Copilot, Cursor, Gemini CLI; Hermes loads `SKILL.md` from `~/.hermes/skills/` | One skill format for every seat. `.agents/skills/dharma-fleet-mailbox/` (this branch) is already in that format |
| Harness shape | Consensus five layers: execution runtime · context system · capability surface · governance layer · protocol adapters; guardrails in the runtime, not the prompt; cache-first context; small stable tool set; subagents only for isolation (Modern Agent Harness Blueprint 2026; Osmani; Microsoft Agent Framework 1.0 GA 2026-04-02 with hosted agents, CodeAct, OpenTelemetry) | We do not build a harness. We specify the four things a seat must expose to be admitted (§3) and let each harness keep its own five layers |
| Durable execution | Temporal Agent Harness: event-sourced history, turns that resume across crashes and days, a hard seam between "model decides" and "capability executes" | Our seam is the one door (`telos_gates.py` + spine receipts). Our event history is the three books (`THE_BLUEPRINT_2026-08-29.md` Part III) |
| Identity | IETF drafts: Agent Identity Protocol (key pair per agent, every action signed), Agent Identity Framework (identity · authorization · attestation · evidence · trust as five separated layers), AI-agent auth/authz; WEBBOTAUTH WG for signed requests; ERC-8004 on-chain registries **empirically 3–15% valid, 60–90% sybil reviewers** (arXiv 2606.26028) | Identity must be ours, local, and single-valued (Blueprint: "identity is the actual bug"); we adopt the five-layer separation as vocabulary and sign every outbound action with the seat's key. Trust registries without witnessed evidence fail, which is the Witness thesis stated by someone else's data |
| Receipts | IETF SCITT published as RFC 9943 (June 2026): COSE-signed statements, transparency log, offline-verifiable receipts; academic "Governance Gaps" paper: MCP/A2A/ACP cannot express identity, delegation, accountability, receipts, or revocation | The receipt envelope is standardized; the semantics are the whitespace. Our ledger becomes a SCITT profile, and the gap paper is our positioning statement |
| Payments | x402 under the Linux Foundation (Apr 2026); AP2 v0.2 at FIDO with Verifiable Intent; card-network agent protocols | rushabdev already runs x402 (`fleet-hub/src/roster.json`, `docs/ops/FLEET_FIELD_REGISTRY.yaml:103-122`). Payment receipts join the treasury book, never a fourth ledger |
| Discovery | AGNTCY Agent Directory (OASF schema, content-addressed), MIT NANDA registry quilt, W3C agent-protocol and agent-identity CGs | Publish our signed Agent Cards to one external directory as a mirror; the roster stays the authority |

**The whitespace, restated:** every protocol above answers "can this agent
connect, prove a key, and move money." None answers "under whose authority,
against which gate, with what receipt, reversible by whom." That is the
Witness product (`docs/plans/THE_WITNESS_ENGINE_2026-08-18.md`), and it is
the only layer here worth building from scratch.

## 2. What the repo already holds, dimension by dimension (measured)

| Dimension | Exists (cite) | Honest state |
|---|---|---|
| Identity roster | `dharma_swarm/a2a/contact_registry.py`, `agent_presence.py:15-25`, `fleet-hub/src/roster.json`, `agent_card.py` | Five competing rosters (ADR-012); none signs actions |
| Transport: NATS | `dharma_swarm/a2a/nats_transport.py`, hub on AGNI, stream `DHARMA_A2A` | Live, one host, broadcast-only until FFR-D1 (`docs/ops/AGNI_FLEET_FUSION_ONE_SITTING_2026-09-04.md` Door 1) |
| Transport: HTTPS gateway | `dharma_swarm/a2a/mailbox_gateway.py` | Merged, tested, undeployed (Door 2) |
| Transport: A2A protocol over HTTP | `dharma_swarm/a2a/a2a_server.py`, `/.well-known/agent-card.json` public route (`api/main.py:336-347`) | Card served; Tier-2 transport bindings not implemented (`node_gateway.py:20`) |
| Tools: MCP | `mission_control_mcp.py` (read-only by default, mutation needs injected authorizer), `chetana/mcp_server.py` | Real; not advertised in any card |
| Skills | `dharma_swarm/skills/*.skill.md` (swarm roles), `.agents/skills/*/SKILL.md` (external seats), `.warp/skills` | Four formats (`CLAUDE.md` "Skills & agent-instruction registries"); only `.agents/skills` matches the open standard |
| Memory | twelve-plus stores; read-only unifier `memory_kernel/facade.py:1-5`; chetana RED | No single write path (`docs/plans/FLEET_FUSION_REVIEW_2026-09-04.md` §2) |
| Durable execution | `RuntimeStateStore`, `TaskBoard`, Mission Control leases/attempts/receipts (`mission_control_contract.py:133-142`) | Real and typed; no compare-and-swap version for commands (`fleet-hub/HANDOFF.md:31-37`) |
| Gates (the seam) | `telos_gates.py` (11 gates), `dharma_kernel.py` (25 axioms) | Run in-process; charmable by text (audit §6); not yet an importable TCB |
| Receipts | `dharma_swarm/spine/` EvidenceReceipt; `a2a/task_receipt.py`; `packages/telos-kernel` Merkle log | Several receipt types; no SCITT profile; not externally timestamped |
| Operator instruments | Helm terminal, web cockpit, Fleet Hub phone (ADR-013) | Fleet Hub owner adapter built this branch (fleet-hub#17) |
| Payments | x402 on rushabdev | Off-repo; no treasury book entry |

## 3. The admission contract — what makes any harness a seat

A harness is admitted to the fleet when it can do four things through the
substrate, regardless of what it is internally. This is the whole
"supersede and sublimate" mechanism: we do not care whether the seat is
Hermes, Claude Code, or a cron job.

1. **Bind identity.** One `agent_uid`, one signing key, one token per door.
   The mailbox gateway already enforces token → uid (`mailbox_gateway.py:8-11`).
   Extend the same binding to NATS users (FFR-D1 ACL) and to the A2A card's
   JWS signature so the three doors agree on who is speaking.
2. **Prove liveness honestly.** `whoami` over the gateway or a signed
   heartbeat on `dharma.fleet.heartbeat`, labeled by Fleet Hub as
   `identity_bound` only when the door binds identity to transport
   (`fleet-hub/src/hub/presence.py:13-15`). Reported claims stay reported.
3. **Act only through the door.** Any consequence outside the seat's own
   sandbox (publish, file write on shared state, spend, merge) goes through
   `invoke → gates → receipt`. Seats that cannot call the door directly get
   the door as an MCP server; seats that cannot speak MCP get it as an HTTPS
   endpoint. Same code path, three faces.
4. **Write back.** Every completed unit appends to the brain (the one write
   path §4.2) and emits a receipt into the event book. No receipt, no credit,
   per the spine doctrine (`docs/architecture/SPINE_ADOPTION_NARRATIVE.md`).

Everything a harness does *inside* itself (its memory tiers, compaction,
sub-agents, skills loop) is its own business and is the reason to adopt it
rather than rebuild it.

## 4. Build order — each phase is a packet, each packet ends in a receipt

Phase order follows the harness-blueprint rule "single durable agent first,
protocol adapters last" and the Blueprint's "constitution runs at action time."

### 4.0 Open the doors (operator, this week)
`docs/ops/AGNI_FLEET_FUSION_ONE_SITTING_2026-09-04.md`. Nothing below is
measurable until seats can DM and the gateway is up.

### 4.1 One identity (M0 of the Blueprint, ~1 packet)
Collapse the five rosters into one signed roster object owned by
`dharma_swarm/a2a/contact_registry.py`; every other list becomes a projection
(`fleet-hub/src/roster.json` generated, not hand-edited). Add an Ed25519 key
per seat; the gateway signs outbound envelopes with the seat's key so
receivers can verify without trusting the broker. Acceptance: Fleet Hub
Roster shows at least one seat as `identity_bound` from real traffic.

### 4.2 One write path for memory (~1 packet)
Make `memory_kernel/facade.py` writable through exactly one function that
every seat's write-back calls, backed by markdown in git as system of record
and the existing stores as indexes (the gbrain rule). Chetana's Stop hook is
the first caller. Acceptance: a session on any seat leaves a receipt-bearing
atom that the next session on a different seat can retrieve by query.

### 4.3 The door as three faces (~1 packet)
Expose `invoke → gates → receipt` as (a) the Python call it is today, (b) an
MCP server tool `dharma_invoke` alongside Mission Control, (c) an HTTPS
endpoint on the mailbox gateway. Same gate battery, same receipt schema.
Acceptance: a Hermes seat performs one gated action via the gateway and the
receipt lands in the event book with the seat's signature.

### 4.4 Receipts as a SCITT profile (~1 packet, the product)
Define the Causal Action Receipt as a COSE-signed statement (RFC 9943) with
the Dharma semantics: authority chain, gate verdicts, expected vs observed
outcome, reversal handle. Run one transparency log; externally timestamp it.
Acceptance: an outside verifier with no repo access validates one receipt
offline.

### 4.5 A2A extension and directory mirror (~1 packet)
Register a Dharma A2A extension URI carrying the receipt reference and
authority tier; publish signed cards to one external directory (AGNTCY ADS
or NANDA) as a mirror. Acceptance: an external A2A client discovers a Dharma
seat and receives a receipt-bearing reply.

### 4.6 Commands on the phone (~1 packet, gated on 4.3)
Add an atomic expected-version transition to TaskBoard so Fleet Hub can
enable steer/assign/claim with idempotency and receipts
(`fleet-hub/HANDOFF.md:31-37`). This is the last piece of "direct it all
from one page."

## 5. Kernel extraction (yes-sheet item 5) — assessment, not yet a commit

The operator said yes to moving `dharma_kernel.py` and `telos_gates.py`
into `packages/telos-kernel/`. Measured today:

- `telos_gates.py` (890 lines) imports `anekanta_gate`, `models`,
  `telos_payload_classifier`, `telos_reroute`, and lazily `telos_receipts`
  and `organism` (`telos_gates.py:24-41,827-841`).
- `dharma_kernel.py` (427 lines) imports `aiofiles` and `models._utc_now`
  (`dharma_kernel.py:20-23`); `aiofiles` is outside the kernel's import
  allow-list (`packages/telos-kernel/README.md`, "Import allow-list").
- Both files are `HOT_PATH_PATTERNS` entries; touching them makes the PR
  CRITICAL under `scripts/runtime/pr_merge_control.py:1058-1062` and
  requires the packet ceremony plus human approval.

So it is not a file move; it is a five-module untangle plus an async-IO
rewrite of the kernel's persistence, under the strictest merge tier. It is
the right first commit of the new repo, and it must be its own packet, not a
rider on the fleet PR. Proposed packet name:
`kernel-extraction-m0-2026-09`; scope: the two files, their five direct
dependencies, and a `dharma_swarm` shim that re-exports from the package so
the 89 importers (`grep -rn "from dharma_swarm.telos_gates import"` count on
this branch) need no change.

## 6. What "fully alive" will mean, measurably

Alive is not a feeling; it is these five meters reading non-zero on the
Helm, each fed by a receipt:

1. Seats heard, identity-bound, in the last 10 minutes (Roster).
2. Peer messages delivered seat-to-seat in the last hour (bus).
3. Gated actions receipted in the last day, by seat (event book).
4. Memory atoms written back in the last day, by seat (brain).
5. External receipts confirmed this week (calibration book; the ring-three
   receipt that unblocks the new repo).

When all five are non-zero on the same day, the organism is alive by its own
definition, and the phone page is directing it. Until then, every "alive"
claim is a rumor by the repo's own convention.
