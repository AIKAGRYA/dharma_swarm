# Karpathy LLM Wiki — primary-source audit

Observed: 2026-08-15T01:20:00+09:00

Primary source: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f

Pinned raw revision: https://gist.githubusercontent.com/karpathy/442a6bf555914893e9891c11519de94f/raw/ac46de1ad27f92b28ac95459c782c07f6b8c964a/llm-wiki.md

Pinned raw SHA-256: `dc3efe98ae62f23dd08acad13aba2e95287beb20b6bec2f4af0423557fe37401`

Related first-party posts:

- https://x.com/karpathy/status/2039805659525644595
- https://x.com/karpathy/status/2040470801506541998

## Audited contract

- **K1 — Three layers.** The architecture consists of immutable raw sources, a mutable agent-maintained wiki, and a co-evolved schema that governs structure and workflows.
- **K2 — Integrative ingest.** A new source is read and integrated into the existing wiki: relevant summaries, entity pages, concept pages, index, cross-references, contradictions, and log are updated. The stated 10–15 pages is an example, not a quota.
- **K3 — Compounding state.** The wiki is kept current rather than recomputed from raw material for every query.
- **K4 — Query with citations.** Answers are synthesized from wiki pages with citations; valuable answers may be filed back into the wiki.
- **K5 — Periodic lint.** Lint checks contradictions, superseded or stale claims, orphans, missing pages and cross-references, and data gaps.
- **K6 — Index and log.** `index.md` catalogs every page with a one-line summary; `log.md` is an append-only chronological operation record.
- **K7 — Scale-aware search.** Index-first navigation is offered for moderate scale, while proper local search is explicitly recommended as the wiki grows.
- **K8 — Tool agnostic.** Obsidian, qmd, frontmatter, images, slide tools, exact directory layout, and implementation details are optional and modular.

## Attribution boundary

The pinned source does not contain “RAG is dead,” “knowledge should be compiled, not retrieved,” or “the wiki is the product, chat is the interface.” Those formulations must not be attributed to Karpathy. The source contrasts a maintained wiki with repeatedly re-deriving synthesis from raw chunks; it does not prohibit retrieval over the compiled wiki.

The source does not prescribe hand-written backlinks, a fixed 100-page ceiling, a weekly cron, an Ollama-only implementation, `dgc kb` commands, a specific Python package, or wholesale page overwrites.

## Local acceptance fixture

A resolved claim in an authoritative register must propagate to every dependent current article through a reviewable multi-page plan. Generated backlinks must be a derived projection and must not count as authored evidence. A loop that scans zero eligible input beyond its freshness SLA must not report healthy.
