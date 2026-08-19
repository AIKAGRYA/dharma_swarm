---
title: "Karpathy LLM Wiki (canonical gist)"
confidence: 0.95
sources:
  - https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
  - https://gist.githubusercontent.com/karpathy/442a6bf555914893e9891c11519de94f/raw/ac46de1ad27f92b28ac95459c782c07f6b8c964a/llm-wiki.md
stale_after: "2027-04-15"
related:
  - karpathy-wiki-pattern
  - karpathy-loop
  - obsidian-web-clipper
  - qmd-search
  - microsoft-markitdown
status: canonical
para: resource
domain: computational
---

# Karpathy LLM Wiki (canonical gist)

This page records the upstream idea in Andrej Karpathy's April 2026
`llm-wiki.md` gist. It is deliberately separate from the local conformance
report, [[karpathy-wiki-pattern]], so implementation claims cannot drift into
claims about what Karpathy specified.

## Source status

- Primary source: <https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f>
- Audited pinned revision:
  `ac46de1ad27f92b28ac95459c782c07f6b8c964a`
- Pinned raw SHA-256:
  `dc3efe98ae62f23dd08acad13aba2e95287beb20b6bec2f4af0423557fe37401`

## The three-layer shape

1. **Raw sources are immutable.** Papers, conversations, images, notes, and
   other inputs remain the evidence layer.
2. **The wiki is mutable.** The LLM maintains summaries, entities, concepts,
   syntheses, cross-references, and current claims.
3. **The schema co-evolves.** Human and LLM refine the instructions that govern
   how the wiki is structured, ingested, queried, and maintained.

The human supplies source material, asks questions, and directs exploration;
the LLM performs summarization, filing, cross-referencing, and bookkeeping.
Karpathy's shorthand is: “Obsidian is the IDE; the LLM is the programmer; the
wiki is the codebase.”

## Three operations

### Ingest integrates

A new source is read against the existing wiki. The agent creates or updates
the relevant summary, entity and concept pages, then refreshes the index,
cross-references, contradictions, and log. One source touching 10–15 pages is
an example of integrative breadth, not a quota. Ingestion can happen one source
at a time for closer supervision or in batches once the workflow is trusted.

This produces compounding state: knowledge is synthesized into the wiki and
kept current instead of re-derived from raw chunks for every question.

### Query synthesizes with citations

The agent searches the maintained wiki and answers from relevant pages with
citations. A useful answer can be filed back as a page, allowing exploration to
compound. The gist specifies that behavior; any local review or promotion gate
is an implementation policy, not part of the upstream claim.

### Lint maintains

Periodic lint looks for contradictions, superseded or stale claims, orphan
pages, missing pages and cross-references, and evidence gaps that need new
research.

## Index, log, and scale

- `index.md` is a content-oriented catalog with a one-line summary for every
  page. It is read first at moderate scale—roughly 100 sources and hundreds of
  pages in the example.
- `log.md` is an append-only chronological operation record. A stable prefix
  such as `## [2026-04-02] ingest | Article Title` makes recent activity
  inspectable with ordinary text tools.
- As the corpus grows, the gist explicitly recommends proper local search.
  Retrieval over the compiled wiki is compatible with the pattern; repeatedly
  synthesizing directly from unintegrated raw material is the failure mode.

## Workflow and optional tools

Obsidian supplies browsing, graph navigation, and editing in the example.
Obsidian Web Clipper captures web material; qmd supplies local hybrid search;
Marp, Dataview, image tools, frontmatter, and Git add presentation, views,
metadata, and history. These are modular examples rather than requirements.

Suggested use cases include personal goals and journals, long-running research,
a companion wiki for a book, team conversations and transcripts, competitive
analysis, due diligence, travel planning, and course notes.

## Why maintenance can compound

The bottleneck in a human-maintained wiki is recurring bookkeeping: keeping
summaries, contradictions, and cross-references consistent as the collection
grows. An LLM can update many related files in one pass without tiring of that
work. Karpathy relates the design in spirit to Vannevar Bush's Memex—personal
knowledge linked by associative trails—but adds a tireless maintainer.

## Attribution boundary

The pinned source does not say “RAG is dead,” “knowledge should be compiled,
not retrieved,” or “the wiki is the product, chat is the interface.” It also
does not prescribe hand-written backlinks, a fixed page ceiling, an Ollama-only
implementation, `dgc kb` commands, a weekly cron, or wholesale page overwrites.

The local implementation, its safeguards, and its current gaps live in
[[karpathy-wiki-pattern]].

## Backlinks
