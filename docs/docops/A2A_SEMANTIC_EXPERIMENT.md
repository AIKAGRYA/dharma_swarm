# A2A Semantic Compression Experiment

**Status:** experiment only
**Authority:** none
**Boundary:** may not control runtime behavior, gates, witnesses, or ontology
schema.

## Position

Agents in a shared ecosystem can develop compact coordination codes. Dharma
Swarm should study that, but it should not hide operational intent inside an
opaque machine language. The safe version is a witnessed compression layer
that always expands back to human-readable English and cites source files.

## Rules

1. Every compact symbol must have a human legend.
2. Every compact message must round-trip to plain English.
3. Every expansion must cite the source docs, code files, or witness records it
   summarizes.
4. The compact language is advisory. It cannot replace `AGENTS.md`,
   `CLAUDE.md`, governance docs, tests, gates, witness logs, or ADRs.
5. Experiments must report compression ratio, ambiguity rate, reconstruction
   failures, and human correction notes.
6. Successful patterns graduate through an ADR or active spec before they
   become load-bearing.

## Suggested Record Shape

```json
{
  "symbol": "DOCOPS.PATH_GUARD",
  "plain_english": "Verify that managed documentation references existing repo paths.",
  "source_refs": [
    "docs/docops/DOCOPS_INTEGRITY.md",
    "scripts/docops/check_docops_integrity.py"
  ],
  "compression_ratio": 0.34,
  "round_trip_passed": true,
  "human_review": "clear"
}
```

## Fit With DocOps

DocOps treats these compact messages as generated or experimental artifacts,
not trusted governance documents. A future checker can validate the required legend,
round-trip expansion, citations, and metrics before any A2A semantic artifact
is accepted.
