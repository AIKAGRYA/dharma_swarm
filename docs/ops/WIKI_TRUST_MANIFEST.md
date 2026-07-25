# Wiki Trust Manifest (PR-08, audit WS-D.1/2)

**Rule-2 role declaration:** `~/.dharma/knowledge/wiki/MANIFEST.jsonl` (+ detached
`MANIFEST.jsonl.sig`) is the **canonical trust projection** over the wiki tree —
committed, signed, versioned. It owns exactly one fact per file: *(path, sha256,
tier, reasons)* at adjudication time. It is not a store of wiki content and not a
second registry; every consumer below is a read-side filter over it.

## Contract

- A wiki file is **trusted** iff it appears in a signature-verified manifest with
  `tier ∈ {gold, trusted}`. Contested tiers (`needs_review`, `quarantine`,
  `archive_only`) are **excluded pending operator decision D-3**.
- **Fail-closed:** missing manifest, missing/invalid signature, tampered bytes,
  malformed or duplicate rows, or an unavailable dharma kernel (placeholder
  signature) ⇒ **empty trusted set** plus one logged warning. There is no
  permissive fallback and no bypass flag.
- Manifest location: `DHARMA_WIKI_MANIFEST` env override, else `MANIFEST.jsonl`
  in the directory being read, else in its parent (so `concepts/` resolves to
  the wiki root). Entry paths are posix, relative to the manifest's parent.
- Signature: `chetana.provenance.compute_axiom_signature(manifest_bytes,
  kernel_signature)` — the existing kernel-bound scheme, no new crypto. It is
  **tamper-evidence and kernel-binding, not operator authentication**; the
  authoritative copy is the git-versioned one (OP-3).

## Consumers (all four READ seams)

| Seam | Behavior |
|---|---|
| `dharma_swarm/wiki_vector_ingest.py` | non-trusted files never reach the vector door; content drift since signing (sha256 mismatch) also refuses ingest; receipt carries `manifest_excluded_files` |
| `scripts/wiki_vector_live_gate.py::_concept_files` | only trusted files are gate-counted (membership+tier; content drift intentionally stays visible so the gate's own digest comparison reports `missing_or_stale` instead of silently shrinking the set) |
| `memory_kernel/adapters/read_only.py::KnowledgeWikiAdapter` | manifest filter runs **before** the `max_files` truncation — untrusted alphabetically-early scratch files can no longer crowd out trusted pages; drifted content is refused |
| `dharma_swarm/chetana/staging.py::list_trusted` | the trusted projection is disk ∩ manifest; `apply_manifest=False` exists only for audit tooling (drift reports) |

`chetana verify` therefore audits exactly what production consumers can see;
its `--mode production` empty-scan fail-closed rule (PR-07) prevents a missing
manifest from reading as a green corpus.

## Operational notes

- **Deploy order matters:** until OP-3 lands a regenerated, operator-adjudicated,
  signed manifest at `~/.dharma/knowledge/wiki/MANIFEST.jsonl`, every seam
  yields an empty wiki set and the daily wiki gate goes honestly red. That is
  the intended fail-closed posture, not a bug.
- **Freshly approved atoms are not auto-trusted.** `chetana approve` writes the
  atom into `concepts/` but manifest membership requires a manifest
  regeneration + signing (OP-3 tooling / `chetana.manifest.write_manifest`).
  Trust additions are a manifest commit, by design.
- Regenerator: `~/handoffs/wiki_gold_layer_audit_2026-07-09/scan_wiki.py`
  (per-file sha256/tier/reasons; 2026-07-09 manifest is stale — regenerate
  before signing, then adjudicate D-3 tiers).

## Hermes writer inventory (why trust binds at READ)

Writer-side control of the wiki tree is **documented, not claimed**. These
`~/.hermes/scripts/*` write into `~/.dharma/knowledge/wiki` outside every
chetana gate (verified 2026-07-26 by scanning for write calls among scripts
referencing the tree):

- `wiki_circulator_connect.py`
- `wiki_connect_orphans.py`
- `wiki_distill.py`
- `wiki_orphan_finder.py`
- `sync_wiki_staging_atoms.py`
- `find_orphans.py`
- `file_collaboration_scorecard_judgment.py`
- `hermes_state_and_queue_tick.py`

(plus read-only orphan/stale analyzers). Because these writers exist, a
promote-time-only gate is theater: the manifest is enforced at every read
seam, and sha256 binding means a hermes mutation of a gold page un-trusts it
until the next adjudicated manifest regeneration. Bringing the writers under
governance (or retiring them) is separate ops work — nothing in this PR claims
writer control.
