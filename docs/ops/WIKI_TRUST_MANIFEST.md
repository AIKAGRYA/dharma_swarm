# Wiki Trust Manifest (PR-08, audit WS-D.1/2)

**Rule-2 role declaration:** `~/.dharma/knowledge/wiki/MANIFEST.jsonl` (+ detached
`MANIFEST.jsonl.sig`, or the OP-3 export `MANIFEST.sig.json`) is the
**canonical trust projection** over the wiki tree —
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
  the wiki root). A single-FILE input (promote auto-ingest passes the approved
  file) resolves via the file's tree. Entry paths are posix, relative to the
  manifest's parent.
- **Env-override trap, made diagnosable:** pointing `DHARMA_WIKI_MANIFEST` at a
  manifest copy outside the wiki tree (e.g. the git-versioned copy) keeps the
  manifest valid while every lookup resolves untrusted, because entry paths are
  relative to the manifest's parent. Still fail-closed, but the loader now logs
  one `does not govern requested tree` warning so the silent-empty state is
  visible. The env override must point at a manifest that lives at the wiki
  root it governs.
- Signature: `chetana.provenance.compute_axiom_signature(manifest_bytes,
  kernel_signature)` — the existing kernel-bound scheme, no new crypto. Two
  detached-signature formats are accepted: canonical `MANIFEST.jsonl.sig`
  (key `signature`, written by `sign_manifest`) and the OP-3 export
  `MANIFEST.sig.json` (key `axiom_signature`) — the already-produced
  2026-07-25 deliverable deploys without re-signing (verified against the real
  pair: 11,945 rows load valid).
- **Forgeability, stated plainly:** the kernel signature is world-readable
  (`governance.current_kernel_signature()` is a plain file read), so ANY local
  writer — including the 8 hermes writers below, the named adversary class —
  can regenerate a poisoned manifest and recompute a passing signature. The
  runtime signature is **tamper-evidence against accidental corruption and
  kernel-binding only, not operator authentication and not an integrity
  boundary against local hostile writers**. Authority lives in the
  git-versioned copy (OP-3); detecting a self-signed on-disk swap requires
  comparing against that committed copy (e.g. a pinned `manifest_sha256`),
  which is deliberately out of scope here and belongs to the daily gate lane
  (PR-13).

## Consumers (all four READ seams)

| Seam | Behavior |
|---|---|
| `dharma_swarm/wiki_vector_ingest.py` | non-trusted files never reach the vector door; content drift since signing (sha256 mismatch) also refuses ingest; manifest filter runs **before** the `max_files` cut (same contract as the adapter seam); receipt carries `manifest_excluded_files`; single-file promote auto-ingest resolves the manifest via the file's tree |
| `scripts/wiki_vector_live_gate.py::_concept_files` | only trusted files are gate-counted (membership+tier; content drift intentionally stays visible so the gate's own digest comparison reports `missing_or_stale` instead of silently shrinking the set) |
| `memory_kernel/adapters/read_only.py::KnowledgeWikiAdapter` | manifest filter runs **before** the `max_files` truncation — untrusted alphabetically-early scratch files can no longer crowd out trusted pages; drifted content is refused |
| `dharma_swarm/chetana/staging.py::list_trusted` | the trusted projection is disk ∩ manifest; `apply_manifest=False` exists only for audit tooling (drift reports) |

`chetana verify` therefore audits exactly what production consumers can see;
its `--mode production` empty-scan fail-closed rule (PR-07) prevents a missing
manifest from reading as a green corpus. Compat mode (CLI and MCP) also fails
closed when the manifest projection is empty while the trusted dir is
non-empty (`empty-manifest-projection`) — a live corpus with a missing/invalid
manifest can no longer exit green after scanning zero atoms.

The live gate's `--min-concepts` default (`DEFAULT_MIN_CONCEPTS`) is calibrated
to the manifest-FILTERED set: 204 gold+trusted top-level `concepts/*.md` rows
in the 2026-07-25 manifest (the pre-manifest 257 counted the unfiltered dir
and would keep the gate permanently red). Retune it with every manifest
revision.

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
