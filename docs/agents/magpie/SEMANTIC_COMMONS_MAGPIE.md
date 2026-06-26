# Semantic Commons registration — THE MAGPIE (STAGED PROPOSAL)

**Status:** proposal · not merged · mirrors the ARTHA_CREAM / RAY D. ALPHA staged-proposal pattern.
**Target files:** `dharma_swarm/docs/ontology/{semantic_objects.yaml, semantic_aliases.yaml}`
**Merge gate:** operator + independent evaluator. The live SSOT had unrelated in-flight edits when this was
staged — do not hand-merge while dirty. Reuses an existing orientation route (no new route invented).

---

## Block 1 — append to `docs/ontology/semantic_objects.yaml`

```yaml
  - id: semobj.magpie
    canonical_name: Magpie
    api_name: dharma.agent.Magpie
    lifecycle: seed
    owner_surface: docs/agents/magpie/agent.seed.yaml
    authority_level: active_spec
    source_path: docs/agents/magpie/agent.seed.yaml
    object_kind: rnd_intake_organ_holon
    public_ontology: true
    aliases:
      - Magpie
      - THE MAGPIE
      - the-magpie
      - magpie
    forbidden_aliases:
      - MAGPIE            # bare all-caps token collides with unrelated acronyms — keep qualified
      - corvid            # squad noun, not an identity (shared with KARASU/TOMBI/YATAGARASU)
      - the thief         # role noun, ambiguous
    supersedes: []
    superseded_by: []
    orientation_route: route.semantic_commons_campaign
```

## Block 2 — append to `docs/ontology/semantic_aliases.yaml`
(every spelling resolves to exactly one object, or name-drift-preflight fails)

```yaml
  - {alias: Magpie,      canonical_id: semobj.magpie, status: active, kind: display}
  - {alias: THE MAGPIE,  canonical_id: semobj.magpie, status: active, kind: display}
  - {alias: the-magpie,  canonical_id: semobj.magpie, status: active, kind: slug}
  - {alias: magpie,      canonical_id: semobj.magpie, status: active, kind: token}
```

## Merge procedure (operator-run, by the rules)

```bash
cd ~/dharma_swarm
# 1. (when ontology SSOT is clean) paste Block 1 + Block 2 into the two files
python3 scripts/governance/name_drift_preflight.py --json-output /tmp/magpie_name_drift.json
python3 scripts/governance/name_drift_preflight.py --strict-semantic-commons      # must be green
make agent-admit ARGS="--agent-uid magpie --canonical-id semobj.magpie \
  --orientation-route route.semantic_commons_campaign \
  --name-drift-receipt /tmp/magpie_name_drift.json"
#    exit 0 = admissible. Then an INDEPENDENT evaluator (not the author) signs off.
```

## The pipeline steps are NOT registered as agents

CAPTURE / STRIP / ROAST / GAP-CHECK / ADAPT / BUILD / A-B / RECORD are **bounded delegated jobs within THE
MAGPIE's one lane**, not standing agents. Per ADR-009's granularity law (one holon ≈ one durable lane), they do
NOT each get a persistent-agent seat or a Semantic Commons object — that would be fragmentation. Only THE MAGPIE,
the R&D-intake organ for the whole lane, is registered.

## The downstream organs are NOT his subordinates

ARTHA_CREAM, tool_metabolism, and find-skills are **consumers** of the Magpie's findings, not parts of his holon.
He hands them proposals; they adopt behind their own gates. Registering the Magpie does not change their ontology.

## Venture cell — not applicable

THE MAGPIE is an R&D organ, not a revenue cell. He is NOT added to `VENTURE_CELL_PORTFOLIO.yaml`. The
revenue-relevant techniques he surfaces flow to ARTHA_CREAM, which is the lane subject to the venture One Law.
