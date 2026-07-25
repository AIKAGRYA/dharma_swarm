# Palantir Pilot Long-Run Goal - 2026-06-14

Status: longrun goal handoff spec
Intended runner: `ds-goal` with explicit audited-checkout pin
Mission id: `palantir-pilot-public-source-mastery-2026-06-14`
Agent: `palantir_pilot`

## Operator Intent

Create a persistent agent holon that becomes Dharma Swarm's master specialist in
Palantir from end to end: Foundry, AIP, Ontology, Apollo, Gotham, OSDK, public
course paths, governance/process patterns, and implications for the swarm. The
holon should be queryable by the operator and other agents, keep growing, and
offer Palantir-side contributions back into Dharma Swarm.

## Safety Boundary

This is public-source only. Do not bypass access controls, login, paywalls,
robots.txt, enrollment flows, rate limits, or private tenant boundaries. Do not
copy Learn/course bodies, course pages, videos, transcripts, labs, quizzes, gated,
or private material, and do not commit deep-card prose to git. Store URLs, metadata,
timestamps, original summaries, concept maps, short excerpts, and — for robots-allowed
public docs pages — full parsed prose as local-only deep-cards (under ~/.dharma,
internal RAG only, no redistribution).

`learn.palantir.com/page/course-catalog` is important but currently treated as
link/manual-review only because autonomous fetch observed a 403 robots response
on 2026-06-14.

## Phases

1. Source compliance and map:
   - verify `www.palantir.com/robots.txt`;
   - index `www.palantir.com/sitemap.xml` and `www.palantir.com/docs/sitemap.xml`;
   - record Learn as manual-review/link-only unless allowed access is confirmed.

2. Workspace construction:
   - refresh `~/.dharma/knowledge/wiki/research/palantir-pilot.md`;
   - write source index JSON/MD under `~/.dharma/knowledge/wiki/raw/palantir-pilot/`
     and `~/.dharma/knowledge/wiki/research/palantir-pilot/`;
   - write bounded public-doc source cards under
     `~/.dharma/knowledge/wiki/research/palantir-pilot/source-cards/`;
   - fold prior repo research from `docs/research/palantir-ontology/`.

3. Mastery maps:
   - Foundry platform map;
   - Ontology object/action modeling map;
   - AIP workflow and governance map;
   - Apollo operations map;
   - Gotham public docs map;
   - OSDK/API developer map;
   - course-path map from public/manual-review evidence.

4. Query surface:
   - document how operators and agents should query Palantir Pilot;
   - provide citation-grounded answer examples;
   - record unanswered questions and source gaps.

5. Swarm contribution:
   - extract Palantir-grade process patterns relevant to Dharma Swarm;
   - propose only source-grounded improvements;
   - separate observation from inference.

## Verifiers

- `python3 scripts/runtime/ds_goal_longrun_preflight.py --repo-pin /Users/dhyana/dharma_swarm --json`
- `python3 scripts/governance/palantir_pilot_audit.py --json`
- `python3 scripts/governance/register_palantir_pilot.py --dry-run`
- `python3 scripts/research/palantir_public_source_index.py --dry-run`
- `python3 scripts/research/palantir_public_source_cards.py --topic aip --dry-run --limit 2 --json`
- `python3 scripts/research/palantir_source_card_quality.py --dry-run --json`
- `python3 scripts/research/palantir_pilot_query.py ontology --json --limit 3`
- `python3 scripts/research/palantir_pilot_query.py ontology --answer --json --limit 3`
- `python3 scripts/research/palantir_pilot_query.py ontology --json --limit 3 --index-workspace --record-db`
- `python3 scripts/research/palantir_pilot_orientation.py --json`
- `python3 scripts/research/palantir_pilot_curriculum.py --json`
- `pytest -q tests/test_palantir_pilot.py`
- `DHARMA_SWARM_REPO=/Users/dhyana/dharma_swarm /Users/dhyana/.dharma/bin/ds-goal status --mission-id palantir-pilot-public-source-mastery-2026-06-14 --json --board-cards`

## Done Criteria

- Palantir Pilot has repo-side seed docs and Stage-1 live registration receipt.
- Allowed public source index exists in the Dharma wiki filesystem.
- Bounded source cards exist for key public docs anchors without full page body
  mirroring.
- Learn/course catalog boundary is explicit.
- Query and contribution protocols are documented.
- Runtime/ds-goal receipt exists for this mission.
- No full copyrighted page/course mirroring is introduced.
