# PROTOCOLS - Palantir Pilot

## Wake Protocol

1. Read `WAKE_CONTEXT.md`, then `SOUL.md`, then the newest entries in
   `MEMORY.md`.
2. Run `python3 scripts/governance/palantir_pilot_audit.py --json`.
3. Check the latest source index under
   `~/.dharma/knowledge/wiki/raw/palantir-pilot/`.
4. Read prior repo research under `docs/research/palantir-ontology/` before
   claiming a new finding.
5. When answering a query, cite source URLs and mark confidence.

## Source Protocol

- Public `www.palantir.com` pages and `palantir.com/docs` sitemap entries may be
  indexed as URLs and metadata.
- Two-tier storage: bounded `source-cards/` (metadata, summaries, short excerpts)
  and, for robots-allowed public `www.palantir.com` docs pages, full parsed prose
  as local-only `deep-cards/` (under `~/.dharma`, never committed to git, internal
  RAG only, no redistribution).
- Do not mirror Learn/course bodies, course text, videos, transcripts, labs,
  quizzes, gated, or private-tenant material.
- Do not bypass login, robots, paywalls, course enrollment, browser restrictions,
  or rate limits.
- `learn.palantir.com/page/course-catalog` is link/manual-review only until a
  valid autonomous access path is established.

## Mastery Protocol

For each Palantir domain, build:

- source index and date observed;
- one-page orientation map;
- key concepts and vocabulary;
- role-based workflows;
- operational gotchas and governance boundaries;
- Dharma Swarm implications;
- query-answer examples with citations.

Use `python3 scripts/research/palantir_pilot_orientation.py --json` to refresh
the first-pass orientation maps from public sitemap metadata.

Use `python3 scripts/research/palantir_pilot_curriculum.py --json` to refresh
role/domain curriculum paths from public sitemap metadata and bounded source
cards. This writes a manual Learn course-catalog intake queue, but it does not
fetch or scrape `learn.palantir.com`.

Use `python3 scripts/research/palantir_public_source_cards.py --topic aip --limit 8 --json`
or another bounded topic (`foundry-core`, `ontology`, `osdk-api`, `apollo`,
`gotham`, `course-path`) to create public-doc source cards. The selector may
also accept repeated `--family` and `--term` filters, skips existing cards by
default, and keeps `source-card-index.md` cumulative. Source cards may fetch
allowed `palantir.com/docs` pages, but they must store only titles, metadata,
headings, one short excerpt, original orientation, and citations. They must
never store full page bodies or gated Learn/course content.

Use `python3 scripts/research/palantir_source_card_quality.py --json` after
source-card expansion. The quality report is local-only: it reads existing
source-card markdown and public URL metadata, flags deprecated/thin/duplicate
cards, and writes the next review queue without fetching any new pages.

Use `python3 scripts/research/palantir_source_card_cleanup.py --dry-run --json`
before retiring legacy cards. The cleanup report is local-only and archive-only:
it plans canonical duplicate excess and deprecated/disallowed source-card moves
without fetching pages or deleting evidence. Run it without `--dry-run` only
after the plan is understood; it moves retired cards under
`source-cards-archive/`, rebuilds `source-card-index.md`, and writes a JSON
receipt.

## Query Protocol

Use `python3 scripts/research/palantir_pilot_query.py "<query>" --json` for a
local source-grounded search over Palantir Pilot's URL metadata and original wiki
notes. The query command is not a private-doc retriever and does not return page
bodies. It is the first stable operator/agent access surface until the holon has
a fuller answer synthesizer.

Use `python3 scripts/research/palantir_pilot_query.py "<query>" --answer --json`
when the operator or another agent needs a direct Palantir Pilot answer packet.
The answer packet must include confidence, source URL citations, wiki-note
citations where available, and explicit limitations. It is allowed to synthesize
only from the public-source workspace; it must say when evidence is weak or when
Learn/course material is blocked.

Use `python3 scripts/research/palantir_pilot_query.py "<query>" --json --index-workspace --record-db`
when the query should also refresh the Memory Palace database surface and record
retrieval feedback rows under consumer `palantir_pilot.query`. This stores query
text, source metadata, note snippets, and retrieval receipts only.

After refreshing source cards, run a query with `--index-workspace --record-db`
so the card markdown is indexed into `~/.dharma/db/memory_plane.db` as
`palantir_pilot_wiki`.

## Contribution Protocol

The holon contributes to Dharma Swarm by producing source-grounded patterns:
ontology design discipline, governance/checkpoint ideas, AIP workflow lessons,
developer platform comparisons, and operational runbooks. Contributions must
name their Palantir source trail and clearly separate observation from inference.
