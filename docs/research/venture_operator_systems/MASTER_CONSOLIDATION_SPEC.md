# Dharma Swarm Operator OS Consolidation Spec

Date: 2026-06-02
Status: architecture packet with first native brick implemented
Scope: VentureCell Operator OS, Darshan first brick, Go evidence organ, Chetana/wiki substrate

## Executive Decision

Build the Dharma Swarm VentureCell Operator OS as a governed company-operating shell, not as a clone of Polsia or Cofounder.

The correct fusion is:

- Polsia ambition: one operator can wake up to meaningful company progress, not a pile of chats.
- Cofounder shell: company profile, departments, agents, task board, Canvas, Library, review states, Plan/Execute, integrations, publishing.
- Karpathy-style wiki: all durable papers, docs, repos, decisions, receipts, source packs, evals, and critiques become agent-native context.
- Dharma Swarm substrate: VentureCells, Chetana, ontology, TaskBoard, DecisionLog, A2A lifecycle, governed work admission, Go receipts, claim/source ledgers, attention gates, kill conditions.

The wedge is trust. DS should make the "AI runs the company" loop evidence-bound, memory-native, inspectable, reversible, and progressively autonomous.

## Current Receipts

External receipts:

- Cofounder docs: https://docs.cofounder.co/
- Cofounder Canvas: https://docs.cofounder.co/workspace/canvas
- Cofounder Library: https://docs.cofounder.co/workspace/library
- Cofounder agents: https://docs.cofounder.co/agents/overview
- Cofounder integrations/MCP: https://docs.cofounder.co/integrations/mcp-toolkits
- Cofounder publishing: https://docs.cofounder.co/publishing/overview
- Polsia live surface: https://polsia.com/live
- Polsia GitHub org: https://github.com/PolsiaAI
- Public Polsia funding reports were checked during this packet. Treat the "$30M" signal as market validation until backed by primary investor/company receipts.
- Anthropic effective agents: https://www.anthropic.com/engineering/building-effective-agents
- MCP docs: https://modelcontextprotocol.io/docs/getting-started/intro

Local receipts:

- Darshan governance names `external_readers_who_read_and_replied` as the metric outranking internal gates: `docs/governance/VENTURE_CELL_DARSHAN.md`.
- Darshan bundles already include `source_pack.json`, `claim_ledger.json`, `attention_ledger.json`, `gate_decisions.json`, `decision_delta.json`, and `polsia_handoff.json`: `dharma_swarm/venture_cell/darshan/bundle.py`.
- Darshan materialization already links Chetana, ontology, TaskBoard, and DecisionLog: `dharma_swarm/venture_cell/darshan/substrate.py`.
- Go receipt SDK already emits deterministic `go_evidence_receipt.v0` receipts and explicitly does not decide: `tools/go_sdk/receipt/receipt.go`.
- Python Go bridge already loads accepted Go receipts and keeps Python/DS governance as the decision layer: `dharma_swarm/operator_core/go_evidence_bridge.py`.
- Control surface already projects Go receipt rows and world-radar receipt summaries: `dharma_swarm/operator_core/control_surface_go.py`.
- Chetana currently has a wiki/memory substrate, but the current query for `Polsia Cofounder VentureCell Operator OS Karpathy wiki MemoryKernel` returned zero hits across wiki, catalytic, gitnexus, memory, and contextplus.

## What To Build

Build a DS-native Operator OS with these primitives:

| Primitive | Meaning | Existing DS owner |
|---|---|---|
| VentureCell profile | company/cell identity, telos, buyer, metric, autonomy stage, kill/spinout conditions | `docs/governance/VENTURE_CELL_DARSHAN.md`, future portfolio schema |
| Department roster | UX projection over agents, roles, allowed tools, and authority tiers | A2A registry, TaskBoard, governed work admission |
| Canvas | visual projection over tasks, receipts, claims, source packs, gates, and blockers | TaskBoard, A2A lifecycle, Darshan bundle |
| Plan/Execute gate | inspectable plan before risky action; receipts after execution | `governed_work_admission.py`, A2A lifecycle |
| Library | artifact, source, receipt, prompt, spec, and decision browser | Chetana/wiki, Darshan bundles, DecisionLog |
| Attention tray | human approvals, blocked gates, missing evidence, high-risk external actions | control surface, governed admission |
| External operator observatory | Cofounder/Polsia sessions logged as evidence, not authority | Darshan `operator_log.py` and schemas |
| Go evidence organ | deterministic external-world receipts | Go SDK and Python bridges |
| MemoryKernel | fast retrieval across papers, repos, docs, receipts, source packs, decisions, evals | Chetana graph unifier plus MCP clients |

## First Brick

The first implementation brick is now:

Darshan external-reader/contact gate requires an accepted Go evidence receipt before a Darshan artifact can advance to DONE.

Implementation receipt:

- schema: `ExternalReaderEvent`, `GoEvidenceReceiptRef`, and `DecisionDelta.external_reader_events`;
- validator: `dharma_swarm/venture_cell/darshan/external_reader_gate.py`;
- advancement: `validate_bundle_for_done()`;
- cockpit row: `darshan.external_reader_go_receipts`;
- memory hook: Chetana staged `receipt` atoms for accepted events;
- tests: `tests/test_darshan_external_reader_gate.py`.

This is the smallest brick that forces the whole architecture to line up:

- product shell: an artifact task cannot be called done without a reader event;
- Polsia ambition: company progress must touch the real world;
- Cofounder UX: work state becomes visible and reviewable;
- Go organ: external evidence is deterministic and hash-bound;
- Dharma governance: Python validates the receipt and makes the gate decision;
- Chetana: the event becomes memory, not just status narration.

## What Not To Build

Do not build:

- a greenfield Polsia clone;
- a greenfield Cofounder clone;
- autonomous outreach or publishing without human approval;
- Go-side policy or dispatch;
- a new memory graph that bypasses Chetana;
- a dashboard that treats declarations as observed truth;
- revenue/share or growth automations before contact and consent gates exist;
- "company activity stream" theatrics without receipts.

## Autonomy Ladder

Level 0: read-only research and planning.

Level 1: reviewed edits and draft artifacts.

Level 2: sandboxed execution with tests and local receipts.

Level 3: gated internal state transition with DecisionLog and control-surface row.

Level 4: gated external action such as outreach, publishing, deployment, or spend.

Level 5: narrow automation after repeated receipt-backed success and explicit policy.

Darshan Season 0 stays at Level 1 for external action. Agents may draft and route. A human approves any publish/outreach. The Go receipt proves the external event happened; it does not authorize the event.

## Eight Week Direction

Week 1: Darshan-Go external-reader gate packet and tests.

Week 2: control-surface row for Darshan contact gate and missing receipt state.

Week 3: Chetana ingest path for external-reader events and operator sessions.

Week 4: TaskBoard/A2A projection for VentureCell departments and attention queue.

Week 5: Cofounder-style Canvas projection over current DS truth owners.

Week 6: Polsia-style daily company cycle view with receipts, budgets, and blocked actions.

Week 7: progressive autonomy policy and eval suite.

Week 8: VentureCell creation/profile flow and multi-cell portfolio view.

## Open Risks

- Polsia's market/funding signal is strong, but public technical evidence remains thin.
- Chetana has the right components but not reliable recall for this mission yet.
- The repo worktree is very dirty; first implementation should be a narrow branch/worktree.
- Existing control surface projects Go receipt infrastructure but not Darshan-specific contact-gate truth.
- Darshan bundle validation currently validates draft structure, not advancement readiness.
