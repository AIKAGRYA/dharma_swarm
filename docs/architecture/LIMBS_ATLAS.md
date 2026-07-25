# Limbs Atlas — MEGAFILE Slot 4

**Status:** SEEDED (2026-07-01 inaugural content; graduates the Slot-4 stub
reserved in [`docs/MEGAFILE_INDEX.md`](../MEGAFILE_INDEX.md)).
**Audience:** Engineer, Agent.
**Read for:** the module map, the dependency graph, "what calls what," and —
via the lenses below — which limb implements which named capability.

This file is a thin **index** for Slot 4, not a re-authored map. The substrate it
points to remains the primary reference; this file exists so the pieces are
discoverable from one place (MEGAFILE_INDEX recursion rule 2).

## Substrate (the real maps)

- [`NAVIGATION.md`](NAVIGATION.md) — the static module map (770+ modules, 12
  layers). May lag code; regenerate with `make xray`.
- [`HOLON_RUNTIME_FULL_ESTATE_MAP.md`](HOLON_RUNTIME_FULL_ESTATE_MAP.md) — the
  current holon-specific body synthesis across repo implementation,
  `~/.dharma` runtime evidence, the parallel `~/.hermes` ecosystem, recent work,
  and a dated readiness witness.
- [`../../ACTIVE_SURFACE_MANIFEST.yaml`](../../ACTIVE_SURFACE_MANIFEST.yaml) —
  machine-readable authority for which surfaces are active / projection / adapter
  / research / frozen.
- `CLAUDE.md` → *Key Abstractions* — the 9 highest-order abstractions (tip of the
  iceberg).
- `make xray` — live static inventory (ephemeral).
- GitNexus `.gitnexus/` — symbol + relationship index (MCP-accessible).

## Lenses (capability views over the limbs)

- [`AGENTIC_PATTERNS_ATLAS.md`](AGENTIC_PATTERNS_ATLAS.md) — the 21 named
  agentic design patterns (Gulli) mapped to the modules that implement them, with
  STRONG / PARTIAL / OUT-OF-SCOPE verdicts. Answers "does the substrate already do
  pattern X, and how well?"

Add new capability lenses here as they are authored; do not fork the module map.
