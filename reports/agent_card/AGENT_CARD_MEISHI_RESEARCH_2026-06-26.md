# Agent Card Meishi Research

Generated: 2026-06-26
Mission ID: agent-card-meishi-rolodex-2026-06-26

## Local Finding

The current live Agent Card layer is useful but not normalized enough to be the
sole identity authority:

- 33 live card files exist under `~/.dharma/a2a/cards`.
- They currently use 5 different top-level shapes.
- The dominant shape is the older base A2A card, while newer cards include
  A2A 1.0 fields such as `skills`, `security_schemes`, `signatures`,
  `supported_interfaces`, and `extensions`.
- Some cards carry rich registration metadata; others are simple interop cards.
- At least one live card uses a forbidden typo alias (`opencalw`), while
  Semantic Commons correctly records that alias as forbidden.

Conclusion: Agent Card should become the unified product surface, but it must
be a joined projection over existing authority lanes.

## External Standards And Patterns

### A2A Agent Card

Source: https://a2a-protocol.org/latest/specification/

Important points:

- A2A servers must make an Agent Card available.
- The card describes identity, capabilities, skills, and interaction
  requirements.
- Discovery can happen through a well-known URI, curated registries/catalogs,
  or direct configuration.
- The spec includes public cards and an authenticated Get Extended Agent Card
  operation for richer details.
- The spec supports Agent Card signing with JWS and JSON Canonicalization
  Scheme.

Implication for Dharma:

- Public card: safe discovery and routing.
- Extended card: authenticated rich card.
- Operator card: dashboard projection that can show even more local proof.

### NATS Subjects And JetStream KV

Sources:

- https://docs.nats.io/nats-concepts/subjects
- https://docs.nats.io/nats-concepts/jetstream/key-value-store

Important points:

- NATS subjects are named communication channels.
- Dot-separated subject hierarchies are the normal semantic namespace pattern.
- NATS provides location transparency through subject-based routing.
- JetStream KV provides persistent key/value buckets with put/get/delete/keys
  style operations.

Implication for Dharma:

- Agent Card should publish update events on semantic subjects.
- JetStream KV is a good fit for current card snapshots when NATS is live.
- File projection remains the offline truth until NATS is proven fresh.

### W3C DID And Verifiable Credentials

Sources:

- https://www.w3.org/TR/did-core/
- https://www.w3.org/TR/vc-data-model-2.0/

Important points:

- DID Core defines identifiers that can be controlled by the entity and used to
  prove control with cryptographic proofs.
- DID documents can include verification methods and service endpoints.
- Verifiable Credentials use issuer, subject, validity, and proof fields to
  express tamper-evident claims.

Implication for Dharma:

- The current identity invariant digest is already close to a local credential
  primitive.
- A future card credential can wrap agent identity, authority floor, passport,
  and registration claims in a VC-like envelope.
- Sensitive details should be progressively disclosed: public card first,
  authenticated extended card second.

### vCard And jCard

Sources:

- https://www.rfc-editor.org/rfc/rfc6350
- https://www.rfc-editor.org/rfc/rfc7095

Important points:

- vCard is the mature contact-card standard for representing and exchanging
  information about entities.
- It includes identification, communication, organizational, explanatory,
  security, calendar, and extended properties.
- jCard serializes vCard in JSON.

Implication for Dharma:

- Agent Card can export a "business card" profile without inventing every
  contact-card convention from scratch.
- Agent-specific fields remain Dharma extensions, but the handoff/export
  concept should feel familiar and portable.

### JSON Schema And Canonical JSON

Sources:

- https://json-schema.org/draft/2020-12/json-schema-core
- https://www.rfc-editor.org/rfc/rfc8785
- https://www.rfc-editor.org/rfc/rfc7515

Important points:

- JSON Schema provides vocabularies and meta-schemas for validation.
- A2A card signing calls for JSON Canonicalization Scheme before JWS signing.
- JWS is the standard envelope for signed JSON-style payloads.

Implication for Dharma:

- Agent Card packets need a schema version and validator.
- Public/extended/operator cards need deterministic digest computation.
- Signature support should be designed now even if cryptographic enforcement
  lands in a later phase.

## Design Synthesis

The frontier pattern is not "one huge JSON blob." It is:

1. a small public discovery card;
2. an authenticated extended card;
3. a local operator card that joins all evidence;
4. portable credential/export envelopes;
5. event and key/value projections for live substrate distribution.

Dharma already has most raw materials. The missing layer is the projection
index, validator, export contract, and dashboard experience.

## Recommended Agent Card Layers

Public:

- id, agent_uid, display_name, role, provider, model family, public endpoint,
  A2A interfaces, public skills, safe tags, public status, public card digest.

Extended:

- registration, identity invariant digest, authority floor, autonomy policy,
  workspace policy, NATS subjects, mailbox, richer skills, tool surfaces,
  team/squad/department, Semantic Commons route, latest non-sensitive receipts.

Operator:

- local paths, LivingDock status, passport, D-score, task history, traces,
  costs, provider availability, raw findings, forbidden alias warnings,
  quarantine status, handoff readiness, comparison metrics.

Export:

- public A2A JSON;
- extended JSON;
- markdown handoff;
- jCard/vCard-compatible contact data;
- future VC/DID credential envelope.

## Build Recommendation

Start read-only:

- create `AgentCardIndex` that joins current live and repo surfaces;
- create `agent_card_check.py` to fail on identity/card inconsistency;
- produce `reports/agent_card/index.json` and `.md`;
- then wire API and dashboard consumers.

This gives immediate operator value without increasing authority risk.

