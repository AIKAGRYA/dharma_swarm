# Semantic Commons registration — ARTHA_CREAM (STAGED PROPOSAL)

**Status:** proposal · not merged · mirrors the RAY D. ALPHA staged-proposal pattern.
**Target files:** `dharma_swarm/docs/ontology/{semantic_objects.yaml, semantic_aliases.yaml}`
**Merge gate:** operator + independent evaluator. The live SSOT had unrelated in-flight edits (395 dirty files)
when this was staged — do not hand-merge while dirty. Reuses existing `route.semantic_commons_campaign` (no new route).

---

## Block 1 — append to `docs/ontology/semantic_objects.yaml`

```yaml
  - id: semobj.artha_cream
    canonical_name: ArthaCream
    api_name: dharma.agent.ArthaCream
    lifecycle: seed
    owner_surface: docs/agents/artha_cream/agent.seed.yaml
    authority_level: active_spec
    source_path: docs/agents/artha_cream/agent.seed.yaml
    object_kind: revenue_command_holon
    public_ontology: true
    aliases:
      - ArthaCream
      - ARTHA_CREAM
      - ARTHA CREAM
      - artha-cream
      - artha_cream
      - Cash Rules Everything Around Me
    forbidden_aliases:
      - CREAM            # bare ambiguous token (Wu-Tang / generic) — must stay qualified
      - ARTHA            # bare ambiguous token — collides with the revenue concept
      - the Don          # role noun, not an identity — ambiguous
    supersedes: []
    superseded_by: []
    orientation_route: route.semantic_commons_campaign
```

## Block 2 — append to `docs/ontology/semantic_aliases.yaml`
(every spelling resolves to exactly one object, or name-drift-preflight fails)

```yaml
  - {alias: ArthaCream,                        canonical_id: semobj.artha_cream, status: active, kind: display}
  - {alias: ARTHA_CREAM,                       canonical_id: semobj.artha_cream, status: active, kind: token}
  - {alias: ARTHA CREAM,                       canonical_id: semobj.artha_cream, status: active, kind: display}
  - {alias: artha-cream,                       canonical_id: semobj.artha_cream, status: active, kind: slug}
  - {alias: artha_cream,                       canonical_id: semobj.artha_cream, status: active, kind: token}
  - {alias: Cash Rules Everything Around Me,   canonical_id: semobj.artha_cream, status: active, kind: display}
```

## Merge procedure (operator-run, by the rules)

```bash
cd ~/dharma_swarm
# 1. (when ontology SSOT is clean) paste Block 1 + Block 2 into the two files
python3 scripts/governance/name_drift_preflight.py --json-output /tmp/artha_cream_name_drift.json
python3 scripts/governance/name_drift_preflight.py --strict-semantic-commons      # must be green
make agent-admit ARGS="--agent-uid artha_cream --canonical-id semobj.artha_cream \
  --orientation-route route.semantic_commons_campaign \
  --name-drift-receipt /tmp/artha_cream_name_drift.json"
#    exit 0 = admissible. Then an INDEPENDENT evaluator (not the author) signs off.
```

## The crew are NOT registered as agents

THE PROFESSOR, THE STALL, and CASHCLAW are **delegated campaign sub-specialists of ARTHA_CREAM**, tracked as
crew cards under `~/.dharma/artha/crew/`. Per ADR-009's granularity law (one holon ≈ one durable lane), they do
NOT each get a persistent-agent seat or a Semantic Commons object — that would be fragmentation. Only ARTHA_CREAM,
the command holon for the whole revenue lane, is registered.

## Venture cell — deferred to the One Law

ARTHA_CREAM as a revenue **cell** may at most be added to `VENTURE_CELL_PORTFOLIO.yaml` at `status: ENVISIONED`,
and may NOT be marked `ACTIVE_SEASON_0` until the crew lands a real cleared receipt — the One Law: "No cell
spawns, grows, or claims status except by closing a strange loop on a real, gated, verifiable, diversity-
preserving outcome." Registration deferred until there is cash to justify it.
