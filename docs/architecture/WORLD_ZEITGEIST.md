---
title: World Zeitgeist Radar
path: docs/architecture/WORLD_ZEITGEIST.md
doc_type: architecture
status: active
summary: External-world sensing path for public signals, Go scouts, Shakti opportunities, and operator briefs.
---

# World Zeitgeist Radar

Zeitgeist is external-world sensing. It is not repo health, test health, or internal emotional pressure. Those signals now live in `dharma_swarm/internal_pressure.py`.

## What It Watches

The Go scout prototype is `tools/world_scout_go`. It has six public-source families:

- `ai_frontier`: frontier lab release feeds.
- `practitioner_signal`: Hacker News and practitioner community streams.
- `agent_infra`: GitHub agent infrastructure repositories.
- `product_company`: product/company signals when found in raw observations.
- `security_regulatory`: advisories, policy, and risk signals.
- `operator_drops`: manual observations such as “SubQ appeared in my feed.”

Live fetching is gated. Cron will not fetch the web unless `DHARMA_WORLD_SCOUT_FETCH=1` or the cron job explicitly sets `fetch=true`.

## Runtime Path

1. Raw external observations enter `~/.dharma/meta/world_operator_drops.jsonl`, `world_scout_observations.jsonl`, or `world_radar_observations.jsonl`.
2. `dharma_swarm/world_radar_go_bridge.py` merges those rows and runs `tools/world_signal_ingestor_go`.
3. The ingestor writes `~/.dharma/world_feeds/world_signal_feed.jsonl`.
4. `dharma_swarm/zeitgeist.py` reads only external world feeds and writes `~/.dharma/meta/zeitgeist.jsonl`.
5. `ShaktiExecutive` reads the zeitgeist history and promotes strong rows into `opportunity_board.json` as `ecosystem_scan`.
6. The analysis layer writes `world_signal_board.json` and `world_signal_brief.md` so humans and agents can see the “so what.”

## Strategic Shape

Every normalized world signal should carry enough structure for the next move:

- First-principles questions.
- Iteration steps.
- Adjacent searches.
- Strategic moves.
- Source lineage and uncertainty.

This means “we saw SubQ” should become: verify source, map primitive breakthrough, find adjacent companies and repos, reverse engineer the workflow, draft a prototype wedge, and route the experiment to Shakti when evidence is strong enough.

## Guardrails

The scout may collect and normalize public evidence. It must not become a second control plane. Python remains responsible for telos, policy, dispatch, ontology mutation, and task creation.

Human review is still required for spending, public posting, partnerships, core architecture changes, and any action that could create external obligations.
