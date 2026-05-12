# World Zeitgeist Radar

Zeitgeist is the external-world sensing organ. It watches public signals about
AI products, model releases, papers, companies, funding, practitioner chatter,
open-source repos, agent infrastructure, security advisories, and adjacent
market movement. It is not repo health, witness pressure, gate pressure, or
internal runtime maintenance.

Internal pressure is handled separately by `InternalPressureScanner`.

## Runtime Path

```text
public sources / operator drops
-> world_scout_go
-> ~/.dharma/meta/world_radar_observations.jsonl
-> world_signal_ingestor_go
-> ~/.dharma/world_feeds/world_radar_go.jsonl
-> ZeitgeistScanner
-> ~/.dharma/meta/zeitgeist.jsonl
-> ShaktiExecutive ecosystem_scan
-> ~/.dharma/meta/opportunity_board.json
-> frontier task refill / dispatcher
```

## Operator Inputs

Use `~/.dharma/meta/world_operator_drops.jsonl` for discoveries from IG, X,
LinkedIn, private chats, or any source that should not be scraped directly.
Each row should include at least `title`; include `source_url`, `description`,
`published_at`, and `keywords` when available.

## Live Fetch Gate

Live public-source fetching is off by default. Enable a canary with:

```bash
DHARMA_WORLD_SCOUT_FETCH=1
```

The cron handler is `world_scout`. With the flag off, it reports
`WAITING_EXTERNAL` rather than pretending the scout is live.

## Outputs

- `~/.dharma/meta/world_scout_health.json` records source reachability, item
  count, fetch status, latency, and errors.
- `~/.dharma/meta/world_signal_board.json` is the machine-readable ranked
  signal board with movements, uncertainty, recommended moves, and opportunity
  IDs when available.
- `~/.dharma/meta/world_signal_brief.md` is the morning-readable brief for the
  next orchestrator.
- `~/.dharma/meta/world_source_weights.json` records source weighting learned
  from completed ecosystem-scan opportunities.

## Guardrails

World scouts observe and normalize. Go does not decide strategy, dispatch
agents, write ontology state, spend money, post publicly, or mutate code.
Python/Shakti interprets signals and proposes governed next moves. Human review
remains required for public communication, spending, partnerships, and core
architecture changes.
