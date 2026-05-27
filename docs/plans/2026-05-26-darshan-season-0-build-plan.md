# Darshan Season 0 Build Plan

**Date:** 2026-05-26
**Status:** Steps 1-7 implemented for the first manual artifact transaction
**Source seed:** `lodestones/seeds/darshan_publication_venture_cell.md`
**Season:** After the Feed

---

## Scout Consensus

Darshan should not start as a CMS, publication app, daily content engine, paywall, or autonomous article writer.

Darshan becomes real when one artifact completes this loop:

```text
world signal
-> public clarity artifact
-> source pack
-> claim ledger
-> attention ledger
-> Chetana ingest
-> ontology KnowledgeArtifact
-> TaskBoard follow-up
-> DecisionRecord / decision delta
-> next swarm action
```

A website without that loop is just a publication. A source pack without a public reader is inward drift. The loop is the cell.

## Confidence

Darshan is not the first VentureCell overall. Shakti Ginko and the Revenue Wedge already occupy that terrain.

Darshan is the best first **world-facing conductor cell** candidate because it forces World Radar, evidence capture, claim discipline, attention design, Chetana, ontology, BoardStore, decisions, and Polsia operations to work as one organism.

Current confidence: **90/100** that Darshan is the right first public conductor cell, conditional on proving the artifact loop manually before building scale.

## Build Order

### Phase 0: Manual Bundle Before External Operators

Create the Darshan bundle format and external-operator observation ledger before giving Cofounder, Polsia, or any adjacent service operational responsibility.

Required bundle directory:

```text
~/.dharma/artifacts/venture_cell/DARSHAN/<yyyy-mm-dd>/<slug>/
  article.md
  source_pack.json
  claim_ledger.json
  counterframes.json
  attention_ledger.json
  gate_decisions.json
  decision_delta.json
  bundle_manifest.json
  polsia_handoff.json
```

Required external-operator ledger:

```text
~/.dharma/venture_cell/DARSHAN/external_operator_observations.jsonl
~/.dharma/venture_cell/DARSHAN/polsia_observations.jsonl
```

`external_operator_observations.jsonl` is the canonical generic log. `polsia_observations.jsonl` remains as a legacy/comparative Polsia-specific log.

As of 2026-05-27, **Cofounder.co is the active collaborator** for the Darshan operating shell. Polsia remains a benchmark/observatory candidate.

External operators should be used for the operating shell, not for final seeing.

Allowed external-operator scope:

- launch calendar
- editorial ops board
- checklists
- source-pack workflow
- outreach CRM
- subscriber/admin ops
- weekly operating review
- runbook

Forbidden external-operator scope in Season 0:

- final claims
- final voice
- source-trust decisions
- public publishing
- corrections
- refusals
- sacred-name judgment
- substrate decision deltas

### Phase 1: Darshan Module Skeleton

Create a thin module group:

```text
dharma_swarm/venture_cell/darshan/
  __init__.py
  bundle.py
  chetana_adapter.py
  cli.py
  conductor.py
  decision_adapter.py
  ontology_adapter.py
  operator_log.py
  polsia_log.py
  schema.py
  substrate.py
  task_adapter.py
```

Minimal commands:

```text
python -m dharma_swarm.venture_cell.darshan.cli build-bundle
python -m dharma_swarm.venture_cell.darshan.cli validate-bundle
python -m dharma_swarm.venture_cell.darshan.cli log-polsia
python -m dharma_swarm.venture_cell.darshan.cli log-operator
python -m dharma_swarm.venture_cell.darshan.cli materialize-bundle
```

Do not build automatic article generation in this phase.

### Phase 2: First Manual Artifact Transaction

Make one manual artifact bundle for a narrow Season 0 seed.

Best first candidates:

1. The Thing They Are Competing For Is Not Just Your Attention
2. What Gets Narrowed When You Stay Informed
3. How To Read AI News Without Being Carried By It
4. The Fast World Needs Slower Eyes
5. A Claim Ledger For One Confusing AI Story

The first artifact should prove the loop, not prove the brand.

### Phase 3: Substrate Ingest

Once the bundle validates:

1. stage article and source pack into Chetana;
2. create or update an ontology `KnowledgeArtifact`;
3. emit at least one TaskBoard follow-up;
4. emit one explicit `DecisionRecord` or `decision_delta.json`;
5. write a bundle manifest with paths and hashes.

### Phase 4: External Operator Handoff

Give Cofounder or any external operator a bounded handoff packet only after the ledger exists.

First 10 external-operator tasks:

1. Build a 30-day Season 0 launch calendar for Darshan: After the Feed.
2. Create an editorial ops board with statuses from idea to published/corrected.
3. Create a repeatable checklist for one Darshan artifact bundle.
4. Create a source-pack checklist for public trust.
5. Create a claim-ledger checklist separating claims, evidence, interpretation, uncertainty.
6. Draft a corrections and refusals workflow.
7. Build a lightweight outreach list for 50 ideal first readers.
8. Design subscriber capture without engagement traps.
9. Create a weekly operating review template.
10. Produce a runbook: How to operate Darshan Season 0.

Every interaction gets logged in `external_operator_observations.jsonl`. Polsia-specific interactions may also be mirrored into `polsia_observations.jsonl` for historical comparison.

Current generic CLI:

```text
python -m dharma_swarm.venture_cell.darshan.cli log-operator
```

### Phase 5: Public Surface

Only after one artifact transaction works:

- static canonical surface plus newsletter distribution;
- no full CMS;
- no paywall;
- no infinite feed;
- no daily engine;
- public trust pages first: methodology, corrections, refusals, source packs, claim ledgers, funding/conflict page.

Decision for Season 0: use a **static/newsletter hybrid**. The static surface is canonical and holds the article, source pack, claim ledger, correction/refusal log, and funding/conflict page. Newsletter/email is distribution only; it must not become the source of truth, the archive, or the engagement loop.

First materialized artifact:

- bundle: `~/.dharma/artifacts/venture_cell/DARSHAN/2026-05-26/the-thing-they-are-competing-for-is-not-just-your-attention/`
- artifact id: `darshan-7302ff3a3a75`
- Chetana staged path: `~/.dharma/knowledge/staging/2026-05-26/63cc03c3-e0fc-4c19-a751-5cfec2017f54.md`
- ontology artifact id: `9259c2af7fd84095`
- TaskBoard task id: `c565766aba3d42c6`
- DecisionLog decision id: `e8df46000109`

## Minimum Schemas

### Claim Ledger

Fields:

- `claim_id`
- `artifact_id`
- `claim_text`
- `claim_kind`
- `scope`
- `status`
- `confidence`
- `evidence_lane`
- `evidence_refs`
- `counterclaims`
- `what_would_change_this`
- `interpretation_boundary`
- `public_wording_limit`
- `last_reviewed_at`
- `correction_parent_id`

### Source Pack

Fields:

- `source_id`
- `canonical_url`
- `final_url`
- `archive_url`
- `capture_timestamp`
- `content_hash`
- `receipt_path`
- `source_type`
- `source_independence_family`
- `license_or_reuse_status`
- `accessed_at`
- `excerpt_locations`
- `extracted_claims`
- `limitations`
- `trust_status`
- `safety_privacy_notes`
- `consent_status`

Archive receipts prove capture integrity, not factual reliability. Source trust remains separate.

### Attention Ledger

Fields:

- `starting_confusion`
- `intended_attentional_movement`
- `reading_modes_supported`
- `anti_feed_design_choices`
- `pause_or_reflection_points`
- `evidence_access_pattern`
- `expected_clarity_signal`
- `expected_calm_focus_signal`
- `manipulation_risks`
- `reader_feedback_observed`

### Decision Delta

Fields:

- `artifact_id`
- `delta_summary`
- `changed_swarm_belief`
- `changed_routing`
- `new_task_ids`
- `affected_cells`
- `followup_owner`
- `review_by`
- `evidence_refs`

## Existing Substrate To Reuse

- `docs/architecture/WORLD_ZEITGEIST.md`
- `dharma_swarm/world_radar/analysis.py`
- `dharma_swarm/world_radar/go_bridge.py`
- `dharma_swarm/world_radar/archive_to_chetana.py`
- `dharma_swarm/chetana/ingest.py`
- `dharma_swarm/dharma_corpus.py`
- `dharma_swarm/claim_graph.py`
- `dharma_swarm/citation_index.py`
- `dharma_swarm/operator_brief/insight_brief.py`
- `dharma_swarm/ontology.py`
- `dharma_swarm/task_board.py`
- `dharma_swarm/decision_ontology.py`
- `docs/architecture/VENTURE_CELL_LIFECYCLE.md`
- `docs/reports/GAIA_PUBLIC_CLAIM_EXPLORER_SPEC_2026-03-27.yaml`
- `docs/loomwork/wiki_public_surface.md`
- `docs/loomwork/wiki_weaving_engine.md`

## What Not To Build Yet

- full public site
- paywall
- autonomous writer
- automatic claim extractor
- daily public publishing engine
- deep Polsia integration
- deep Cofounder integration without exported receipts
- complex analytics
- recommender system
- mobile app
- spiritual brand surface
- substrate explainer

## 7-Day Execution Path

1. Define schemas and bundle folder format.
2. Add bundle validation and Polsia observation logging.
3. Create the first manual `After the Feed` bundle.
4. Stage the bundle into Chetana.
5. Create an ontology `KnowledgeArtifact` and one TaskBoard follow-up.
6. Emit one decision delta and one Polsia handoff packet.
7. Decide whether the first public surface is static site, newsletter, or hybrid.

## Done Definition

Darshan Season 0 has started only when:

1. one artifact bundle exists on disk;
2. its source pack and claim ledger validate;
3. the article serves a real public reader;
4. the artifact is staged or promoted into Chetana;
5. the ontology has a corresponding `KnowledgeArtifact`;
6. at least one follow-up task exists;
7. one explicit decision delta says what Dharma Swarm will do differently;
8. Polsia can receive a bounded handoff packet;
9. the name `Darshan` remains held as a vow, not a decorative brand.
