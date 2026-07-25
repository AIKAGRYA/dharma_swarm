# Quality cartography archive — 2026-06-12

Two independent cartography passes were commissioned on 2026-06-12 to map
the repo's quality posture (the seed exercise of the Sattva Quality
Lattice proposal). Both agents wrote to the same untracked paths under
`docs/quality/` with no surface ownership: the second pass silently
overwrote the first, and the v0 files survived only as unreachable git
blobs (salvaged the same day, before gc could prune them). They are
archived here so neither pass is lost and so the incident itself remains
on record — it is the disease the lattice exists to cure.

- `*.perplexity-v0.*` — perplexity-computer pass, 19:30 JST. Layer
  scores L1=8 L2=7 L3=6 L4=7 L5=5 L6=6. Salvaged from blobs
  `3b0c37fa…` / `d73d055c…`. Its layer map is stored as `.yaml.txt`
  because the original bytes are malformed YAML (scan error at line
  509) — the "machine-readable" artifact never actually parsed, a
  defect preserved here as found.
- `*.codex-v1.*` — Codex pass, 20:18 JST. Layer scores L1=7 L2=8 L3=6
  L4=6 L5=5 L6=6.

Caveats for any reader treating these as evidence:

1. The two passes use the SAME invariant ids (Q-001..Q-008) for
   DIFFERENT invariants. Never cite a Q-id without naming which pass.
2. Both passes were witnessed on the `qwen/spine-adoption` side lane,
   29 commits behind origin/main with 77 dirty files. Their sharpest L2
   claims are stale-lane artifacts: `operator_core/a2a_task_lifecycle.py`
   and `tests/test_a2a_task_lifecycle.py` EXIST on origin/main (rescue
   commit 26681ef9e). The 2026-06-12 red-team adjudication resolved this.
3. The living successors of these documents are
   `docs/quality/SATTVA_STYLE.md` (canon) and the ratchet machinery under
   `scripts/governance/hygiene/` — not these snapshots.
