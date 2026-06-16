# Semantic Commons

**Status:** active_spec for `agent-admission-semantic-commons-2026-06`.
**Owner:** `docs/governance/ACTIVE_TRACK.yaml`.
**Subordinate to:** `docs/governance/CANONICAL_DOC_STACK.md`, `docs/architecture/ADRs/ADR-008-ontology-api-name-grammar.md`, and runtime/code owners for mutation.

Semantic Commons is the governed identity and alias layer for durable names in
`dharma_swarm`. It answers one question before agents build, admit, retrieve,
or project context: which canonical object is this name pointing at?

It is not a new database, OMS clone, or runtime authority. The files under
`docs/ontology/` are active-spec inputs to governance checks. Runtime modules,
registrations, receipts, and owner files remain authoritative for mutation and
live state.

## Files

- `semantic_objects.yaml` is the canonical object registry.
- `semantic_aliases.yaml` is the central alias registry.
- `session_orientation.yaml` is the layered orientation route registry.
- `pkm_projection.yaml` defines the generated Obsidian/PKM projection policy.
- `retrieval_scope.yaml` defines structure-first retrieval scoping.
- `SEMANTIC_COMMONS.md` explains the contract and human review rules.

## Object Contract

Every object record must include:

- `id`: stable canonical object ID.
- `canonical_name`: public display name.
- `api_name`: ADR-008 style public ontology name.
- `lifecycle`: one of the lifecycle states below.
- `owner_surface`: file or surface that owns the object.
- `authority_level`: how much authority the owner surface carries.
- `source_path`: current source path for the object definition.
- `aliases`: intentional name variants.
- `forbidden_aliases`: known-bad names that must not be introduced.
- `supersedes`: older canonical IDs this object replaces.
- `superseded_by`: newer canonical IDs that replace this object.

Public ontology `api_name` values follow ADR-008:

- stable unversioned name;
- `dharma.<domain>.<PascalCaseType>`;
- no `.v<N>` suffix;
- version belongs in metadata, not in the name.

## Lifecycle States

- `seed`: proposed or early record, not relied on as a contract.
- `working`: accepted for current implementation work.
- `preferred`: recommended target when aliases compete.
- `canonical`: stable contract; breaking changes require replacement.
- `deprecated`: retained for compatibility only.
- `forbidden`: known-bad name or object record; must not be used in new work.

## Alias Rules

Aliases are first-class registry entries. An alias may be a display string,
path slug, API token, command spelling, or compatibility spelling, but it must
resolve to exactly one active canonical object.

Required checks:

- duplicate canonical IDs fail;
- one active alias resolving to multiple active objects fails;
- hyphen and underscore variants used in active surfaces must be registered;
- forbidden aliases fail on active surfaces;
- obvious typo-distance collisions, such as `openclaw` / `opencalw`, fail;
- bare ambiguous acronyms, such as `ICM`, are forbidden unless a later record
  disambiguates them with an explicit owner and route.

## Session Orientation

`SessionOrientation` is a real object in the registry, not a loose concept.
It solves context-loading cost on top of identity resolution.

Agents must load context by layer:

- L0 Bootstrap: where am I, what must I never touch, what is the front door.
- L1 Routing / MOC: which docs, code, and tests own this task.
- L2 Active Track Packet: current intent, scope, missing artifacts, and gates.
- L3 Reference / Deep Context: authoritative references after route selection.
- L4 Corpus / Search: fuzzy recall, archaeology, vector search, wiki, reports.

L4 is never first. Search and broad recall happen only after L0-L2 establish
scope and authority.

## Admission Boundary

Agent admission consumes this registry. A persistent agent is not admitted
unless it has:

- a canonical object entry or an explicit linked object;
- a central alias entry for its `agent_uid` and known display variants;
- an orientation route assignment;
- a fresh name-drift preflight receipt;
- no duplicate active `agent_uid` or A2A card identity;
- an explicit lifecycle state.

`make onboard` remains orientation. `make agent-admit` is the narrow admission
check path.

## PKM Projection

Obsidian and wiki notes are cockpit views. They do not own Semantic Commons
truth. Generated projection notes must carry:

- `projection_of`;
- `generated: true`;
- `canon: false`;
- `canonical_object_id`;
- `source_path`;
- `aliases`;
- `lifecycle`;
- `owner`;
- `orientation_route`.

The generated vault root is
`/Users/dhyana/.dharma/knowledge/wiki/semantic-commons`. MCP access for this
projection starts read-only and path-scoped. Command execution stays disabled.

Run:

```bash
make semantic-commons-project
```

## Retrieval Scoping

Retrieval starts with the SessionOrientation route, not fuzzy search. The order
is:

1. L0/L1 orientation route.
2. Exact object ID, path, alias, or `api_name`.
3. BM25 or FTS inside the selected scope.
4. Vector search.
5. Graph expansion.
6. RRF or measured fusion.

Results must expose why they were selected: canonical target, authority,
lifecycle, source path, projection/canon status, retrieval lane, timestamp or
freshness marker, and selection reason.
