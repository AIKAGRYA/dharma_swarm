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
