# MEMORY - Palantir Pilot

## 2026-06-14 - Seed State

- `www.palantir.com/robots.txt` was observed to allow public crawling and list
  both the main sitemap and docs sitemap.
- `www.palantir.com/docs/sitemap.xml` was observed reachable and includes public
  docs surfaces for Foundry, AIP, Apollo, Gotham, Defense OSDK, API reference,
  release notes, and localized Foundry docs.
- `learn.palantir.com` returned a 403 robots/autonomous fetch response through
  the fetch path. Treat Learn as link/manual-review only until an allowed access
  path is confirmed.
- Dharma Swarm already has prior Palantir ontology research under
  `docs/research/palantir-ontology/`. This holon inherits that corpus.

## 2026-06-16 - Deep Corpus Layer (operator directive: "scrape it deep")

- The original card schema stored only headings + one 280-char excerpt. That was
  a self-imposed conservative choice, not a legal limit. Under operator direction
  the boundary was re-scoped to deep public-doc ingestion within legal bounds.
- New layer: `deep-cards/` under the wiki research dir. 5,586 cards, ~9.06M chars
  of full parsed public-doc prose across the `www.palantir.com` sitemap
  (Foundry, Apollo, Gotham, Defense OSDK, AIP, API ref, plus newsroom/site).
  Ingester: `scripts/research/palantir_deep_ingest.py` (reuses the existing
  fetch/parse path; only stops discarding the body).
- Boundary unchanged in spirit, sharpened in letter: full text of PUBLIC
  `www.palantir.com` pages (robots `Allow: /`), for INTERNAL RAG only, NOT
  redistributed. `learn.palantir.com` (403), gated, and private-tenant material
  remain excluded.
- Retrieval was tuned so the depth is actually used: the answer-builder now reads
  a deep card's `## Content` section (`_extract_note_answer_claim`) and the claim
  cap rose 520 -> 1400. `build_answer_packet` now returns multi-thousand-char
  source-grounded answers instead of a first-sentence stub. 29/29 unit tests green.
- Two-tier storage: the thin v1 `source-cards/` carry the metadata-only boundary;
  `deep-cards/` carry full parsed prose of robots-allowed public docs pages,
  local-only under `~/.dharma` (never committed to git, internal RAG only, no
  redistribution). The boundary strings across the policy surfaces, packets, and
  seed were reconciled to own this deep-card layer while still forbidding
  Learn/course/gated/private full-text.
