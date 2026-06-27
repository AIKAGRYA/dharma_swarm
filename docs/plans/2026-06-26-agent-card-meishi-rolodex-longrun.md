# Agent Card Meishi Rolodex Long-Run

Status: active mission packet
Mission ID: agent-card-meishi-rolodex-2026-06-26
Created: 2026-06-26
Owner surface: Agent Card projection layer, dashboard agents surface, A2A discovery, Semantic Commons consumers
Boundary: additive projection only; do not collapse Semantic Commons, registration, identity invariant, LivingDock, passport, A2A, NATS, or receipt owners.

## Progress Log

2026-06-26:

- Slice 0 landed a read-only Agent Card index builder, governance checker,
  FastAPI routes, report outputs, and backend tests.
- Slice 1 landed `/dashboard/agent-cards`, compact meishi cards, an expandable
  detail panel, dashboard types/API helpers/hooks, filtering/sorting helpers,
  nav wiring, and dashboard helper tests.
- Slice 2 landed portable export packets: public JSON, extended JSON, operator
  JSON, Markdown handoff brief, jCard, vCard/VCF, raw export API routes, and
  dashboard copy/download controls.
- Receipts:
  - `reports/agent_card/AGENT_CARD_MEISHI_SLICE0_RECEIPT_2026-06-26.md`
  - `reports/agent_card/AGENT_CARD_MEISHI_SLICE1_DASHBOARD_RECEIPT_2026-06-26.md`
  - `reports/agent_card/AGENT_CARD_MEISHI_SLICE2_EXPORTS_RECEIPT_2026-06-26.md`

## Objective

Build Agent Card into the swarm's world-class portable digital meishi: a clean,
dynamic, expandable, handoffable rolodex and "LinkedIn for agents" surface that
shows who every agent is, what it can do, how to contact it, what authority it
has, what proof backs that authority, how it relates to teams and ontology
objects, and what operational evidence exists.

The word "Agent Card" becomes the product surface. Underneath it remains a
joined projection over the existing truth lanes.

## Non-Negotiable Invariant

Agent Card must not become a second source of truth.

It must read from and point back to:

- Semantic Commons for durable names, aliases, forbidden aliases, and routes.
- External registration for agent_uid, callsign, harness, model identity,
  department, squad, team, authority, autonomy policy, workspace policy, memory
  namespace, and trace identity.
- Identity invariant for stable digest and serial.
- A2A card for public discovery, skills, protocol interfaces, and endpoints.
- NATS for live addressability and event routing.
- LivingDock and authority passport for workspace, home, and authority proof.
- Runtime receipts, traces, task history, and D-score for operational evidence.

## Product Shape

Agent Card has three presentation tiers:

1. Public Card
   - Safe A2A-compatible discovery card.
   - Suitable for `.well-known/agent-card.json`, registries, and handoff links.
   - No secrets, no sensitive local paths unless explicitly safe.

2. Extended Card
   - Authenticated card with richer skills, tools, authority, provenance,
     team membership, ontology links, NATS subjects, receipts, and handoff
     context.
   - Mirrors A2A extended card semantics.

3. Operator Card
   - Dashboard-native card with collapsible layers, comparison lanes, health,
     proof, recent work, memory status, receipts, D-score, and action buttons.
   - This is the "LinkedIn for agents" experience.

## Core Data Model

The projected card should include:

- identity:
  - agent_uid, serial, callsign, display_name, canonical_object_id, aliases,
    forbidden-alias findings, provider, model_identity, harness.
- org:
  - department, squad_id, team_id, role, operating title, council role,
    coordination peers, owner surface.
- authority:
  - authority floor, policy ceiling, autonomy policy, workspace policy,
    allowed/gated/forbidden capabilities, passport path, identity digest.
- discovery:
  - A2A endpoint, supported interfaces, skills, capabilities, security schemes,
    public/extended card URLs, NATS inbox subject, mailbox.
- ontology:
  - Semantic Commons object, route, source path, lifecycle, object/action/link
    relationships, Palantir-style object map.
- operations:
  - status, last seen, heartbeat freshness, recent tasks, current task,
    success rate, fitness, cost, provider route state, recent traces.
- proof:
  - identity invariant validation, card digest, registration digest, latest
    receipts, D-score, admission status, lint findings.
- handoff:
  - machine JSON, markdown brief, jCard/vCard-compatible contact export,
    A2A card export, QR/link target, "how to summon", "how to safely hand off".

## Research Grounding

The design follows current external protocol directions:

- A2A requires Agent Cards for discovery and says cards describe identity,
  capabilities, skills, and interaction requirements.
- A2A supports public cards plus authenticated extended cards.
- A2A defines card signing using JWS and JSON canonicalization.
- NATS subject hierarchies provide semantic namespaces and location-transparent
  routing; JetStream KV is a good fit for a current card index.
- W3C DID and Verifiable Credentials provide portable, proof-based identity
  and credential exchange primitives.
- vCard/jCard provide the battle-tested business-card/contact-card export
  metaphor.
- JSON Schema gives the validation layer for stable card packets and future
  schema evolution.

Detailed notes live in:

- `reports/agent_card/AGENT_CARD_MEISHI_RESEARCH_2026-06-26.md`

## Architecture

Implement a read-only projection service first:

```text
Semantic Commons
External registration
Identity invariant
A2A card registry
LivingDock / passport
NATS status / inbox
Runtime receipts / traces / D-score
        |
        v
AgentCardIndex builder
        |
        +--> public card JSON
        +--> authenticated extended card JSON
        +--> operator dashboard payload
        +--> markdown handoff
        +--> jCard/vCard-compatible export
        +--> NATS KV / event projection
```

## Proposed Repo Surfaces

- `dharma_swarm/a2a/agent_card_index.py`
- `dharma_swarm/a2a/agent_card_schema.py`
- `scripts/governance/agent_card_check.py`
- `api/routers/agent_cards.py`
- `dashboard/src/app/dashboard/agent-cards/page.tsx`
- `dashboard/src/app/dashboard/agent-cards/[id]/page.tsx`
- `dashboard/src/components/agent-cards/*`
- `tests/test_agent_card_index.py`
- `tests/test_agent_card_check.py`
- `tests/test_agent_card_api.py`

Existing `/dashboard/agents` can consume the new card projection gradually. Do
not delete the existing agent workspace.

## NATS Projection

Use semantic subjects:

- `dharma.agent_card.<agent_uid>.public`
- `dharma.agent_card.<agent_uid>.extended`
- `dharma.agent_card.<agent_uid>.status`
- `dharma.agent_card.<agent_uid>.handoff`
- `dharma.agent_card.index.updated`

Use JetStream KV when live NATS is available:

- bucket: `AGENT_CARDS`
- keys:
  - `public.<agent_uid>`
  - `extended.<agent_uid>`
  - `status.<agent_uid>`
  - `digest.<agent_uid>`

The file projection remains canonical for local/offline operation until the
NATS substrate is proven fresh.

## Dashboard Experience

The dashboard should feel like a dense operational rolodex, not a marketing
page.

Views:

- card grid: filter by team, role, authority, status, model, capability,
  verification state, handoff readiness.
- comparison table: stable columns for identity, authority, model, endpoint,
  health, receipts, D-score, cost, tasks, trust grade.
- card detail:
  - identity header with meishi-style compact card.
  - collapsible layers: Identity, Authority, Discovery, Capabilities, Ontology,
    Operations, Proof, Handoff, Raw.
  - graph panel: teams, peers, NATS route, A2A route, ontology object links.
  - export buttons: JSON, markdown, public A2A, jCard/vCard.

## Verification Gates

Phase 1 must pass:

- `make semantic-commons-check`
- `pytest -q tests/test_agent_admission.py tests/test_a2a_spec_conformance.py`
- new live-card linter over `~/.dharma/a2a/cards/*.json`

The linter must prove:

- all live cards parse without metadata type errors;
- every admitted card has `metadata.agent_uid`;
- live card names resolve through Semantic Commons or are explicitly quarantined;
- forbidden aliases such as `opencalw` cannot silently appear as healthy cards;
- duplicate `agent_uid` across live cards fails;
- identity invariant digests validate when present;
- public and extended card projections preserve A2A compatibility.

## Acceptance Targets

V0 acceptance:

- All 33 current live cards are indexed.
- Codex Composer renders as a complete rich card with identity, registration,
  invariant, A2A, passport, LivingDock, latest receipt, and handoff lanes.
- Live card inconsistencies are reported, not hidden.
- Public/extended/operator payload split exists.
- Dashboard can render a card list and one detail card from the new index.

V1 acceptance:

- NATS projection writes current public/status card packets when NATS is live.
- A2A extended card endpoint is wired with authentication boundary.
- jCard/vCard-compatible and markdown handoff exports exist.
- Card signing/digest verification is implemented with canonical JSON.

V2 acceptance:

- DID/VC-style credential wrapper exists for authority and identity claims.
- Agents can exchange card handoffs through A2A/NATS without losing provenance.
- Dashboard comparison can answer: "Who is this agent, can I trust it, what can
  it do, how do I contact it, and what evidence proves that?"

## First Build Slice

Build a read-only `AgentCardIndex` and checker.

Inputs:

- `~/.dharma/a2a/cards/*.json`
- `~/.dharma/external_agents/*/registration.json`
- `~/.dharma/external_agents/*/identity_invariant.json`
- `~/.dharma/external_agents/*/authority/passport.json`
- `~/.dharma/agents/*/{identity,living_agent}.json`
- `docs/ontology/{semantic_objects,semantic_aliases,session_orientation}.yaml`

Outputs:

- `reports/agent_card/index.json`
- `reports/agent_card/index.md`
- `reports/agent_card/findings.json`

This first slice is deliberately read-only and can land safely in the current
dirty worktree without collapsing any existing lane.
