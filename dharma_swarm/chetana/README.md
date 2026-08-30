# chetana — Grand Memory System for dharma_swarm

**chetana** (Sanskrit: चेतना, "consciousness, awareness, sentience") is the
connective tissue layer that turns Dhyana's five distributed knowledge
substrates into one operational PKM.

## What it does

```
RAW SOURCES          CHETANA              TRUSTED SUBSTRATES
-----------          -------              ------------------
session JSONL    ─►  ingest    ─►  staging/  (untrusted draft)
webclip                │                  │
PDFs/audio (MarkItDown)│                  │  promote (gate check)
voice memos            │                  │      │
                       │                  ▼      ▼
                       │             wiki/ trusted atoms
                       │                  │
                       ▼                  ▼
                    decay scan ──► quarantine/  (past stale_after)
                    gap scan ──►  gap_queue.jsonl  (under-covered topics + open questions)
                    palace ──►   memory_palace.canvas (10 pillar rooms, JSON Canvas)
                    query  ──►   unified hits across memory + gitnexus + contextplus + catalytic
```

Capture and compilation are deliberately separate. `ingest` creates a staged
derivative atom; immutable raw-source custody is not implemented yet. `compile`
consumes a reviewed `chetana.integration.v2` plan and revises only the canonical
pages explicitly named by that plan when all source hashes, target hashes,
per-operation evidence bindings, claim IDs, and exact replacement counts still
match. It is dry-run-only unless `--apply` is given.
Plan sources declared as agent inference, runtime observation, operator input,
or primary source cannot directly rewrite canonical pages. A write must bind to
an audited source or canonical ledger below an operator-configured authority
root. Every claim ID must occur as an exact token in a unique locator inside the
hashed evidence; ledgers/registers and audited-source sections have additional
structural checks. These are bounded filesystem capabilities and syntactic proof
obligations, not semantic entailment or cryptographic attestations. Apply
requires and records a reviewer name; authenticating that reviewer remains
outside this prototype.

Every promote pass runs through `dharma_swarm.telos_gates.TelosGatekeeper`
(11 gates) and is signed against `dharma_swarm.dharma_kernel.KernelGuard`'s
SHA-256. Atom provenance is structurally enforced: source, processing chain,
gate decision, axiom signature, review status, stale_after.

## The 5 layers

| Layer | What | Where it lives | chetana's role |
|-------|------|----------------|----------------|
| L0 atoms | Frontmattered markdown | `~/.dharma/knowledge/wiki/`, `~/.claude/cabinet/`, `foundations/` | `chetana ingest` writes staged drafts; `chetana promote` writes trusted |
| L1 graph | Bidirectional typed links | memory MCP, gitnexus, contextplus, catalytic_graph.json | `chetana query` is the unified surface |
| L2 PARA view | Projects/Areas/Resources/Archives projections | computed, not stored | `chetana palace --para` renders |
| L3 memory palace | 10 Pillars rooms + 25 Axioms loci | JSON Canvas spec | `chetana palace` renders to `memory_palace.canvas` |
| L4 governance overlay | TelosGatekeeper + KernelGuard + provenance | `dharma_swarm/telos_gates.py`, `dharma_swarm/dharma_kernel.py` | every promote routes through gate_check_atom() |

## Philosophy: stale → revive, not exile

When an atom passes `stale_after`, the **default** chetana response is REVIVE,
not quarantine. Stale is the trigger for re-integration, not termination:

  - scan the corpus for atoms captured *after* this one with overlapping tags/related
  - find new backlinks (atoms now pointing at this one)
  - check whether the original body's open questions have been answered elsewhere
  - propose a patch (new `related:` links, refreshed `confidence`, extended `stale_after`)
  - on apply, append a `revival_chain` entry to the atom's provenance
    (audit trail of every revival event with prior signature, neighbors added,
    questions resolved, reviewer)

Quarantine is reserved for atoms that are genuinely contradicted by evidence,
no longer relevant, or have failed multiple revival passes. It is opt-in
(`chetana decay --quarantine`), not the default.

This is the active-inference / Friston layer made concrete: the wiki adapts
to what the world has learned since the atom was last verified, instead of
freezing claims at their original confidence.

## CLI

```bash
python -m dharma_swarm.chetana.cli ingest --kind session ~/.claude/projects/.../<id>.jsonl
python -m dharma_swarm.chetana.cli promote ~/.dharma/knowledge/staging/2026-04-27/<atom_id>.md

# Stale atoms — default = surface only; suggest revive
python -m dharma_swarm.chetana.cli decay
# Re-integrate every due atom
python -m dharma_swarm.chetana.cli revive --all
# Apply (write the refreshed atom + revival_chain entry)
python -m dharma_swarm.chetana.cli revive --all --apply
# Last resort: actually quarantine atoms that resist revival
python -m dharma_swarm.chetana.cli decay --quarantine

python -m dharma_swarm.chetana.cli gap-scan --queue ~/.dharma/campaign_chetana/gap_queue.jsonl
python -m dharma_swarm.chetana.cli palace
python -m dharma_swarm.chetana.cli query "strange loop"
python -m dharma_swarm.chetana.cli status

# Integrative ingest: inspect a multi-page patch, then apply the same plan
python -m dharma_swarm.chetana.cli compile plan.json --show-diff
python -m dharma_swarm.chetana.cli compile plan.json \
  --canonical-ledger-root /trusted/ledgers --apply --reviewer NAME

# Backlinks are a computed projection, not authored semantic evidence
python -m dharma_swarm.chetana.cli backlinks
python -m dharma_swarm.chetana.cli backlinks --apply
# Reconcile a reviewed batch while retaining a full-corpus hash guard
python -m dharma_swarm.chetana.cli backlinks --page concepts/example.md --apply
```

## MCP server

```bash
# In .mcp.json:
"chetana": {
    "command": "python",
    "args": ["-m", "dharma_swarm.chetana.mcp_server"]
}
```

Requires `pip install mcp` for the JSON-RPC server. Tools:
`chetana_ingest`, `chetana_promote`, `chetana_query`, `chetana_gap_scan`,
`chetana_decay_check`, `chetana_palace_state`.

## Testing

```bash
python -m pytest dharma_swarm/chetana/tests -q
```

## Status (2026-04-27)

- **v0.1.0 — initial Python package**: ingest, promote, decay, gap-scan, palace, query, governance, provenance, staging, MCP server skeleton, CLI.
- **Permissive fallback**: when the parent dharma_swarm package is not pip-install-e'd, `gate_check_atom` runs in a permissive mode that warns and writes everything as `staged` for human review. Real governance kicks in once `pip install -e .` is run.
- **Council finding honored**: chetana does NOT add semantic-evaluation gates. The underlying telos gates use substring matching today; a separate Phase 6b campaign is responsible for upgrading them. chetana benefits without changes when that lands.
- **Decay layer is the differentiator**: every existing wiki / cabinet / foundations atom carries `stale_after:` metadata that is currently inert. `chetana decay` is the active-inference job that turns the wiki from accretive into living.

## Roadmap (post-v0.1)

- v0.2 — wire memory MCP + contextplus through `chetana_query` via an MCP client (currently surface notes the limitation).
- v0.3 — `chetana publish` for Quarto / arXiv / blog output formats.
- v0.4 — full structured-predicate kernel enforcement (depends on Phase 6a).
- v0.5 — semantic gate matching (depends on Phase 6b).
