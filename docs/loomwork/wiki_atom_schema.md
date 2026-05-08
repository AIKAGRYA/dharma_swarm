# World-Facing Wiki Atom Schema — Extension Spec

**Created:** 2026-05-07 (Arjuna mode)
**Status:** Drop-in implementation spec. Extends, does not replace, the existing Karpathy-style atom format at `~/.dharma/knowledge/wiki/`.
**Constraint:** all existing 249 atoms must keep parsing without modification. New fields default to safe values when absent.

---

## 0. What already exists (verified, not invented)

- **Wiki root:** `~/.dharma/knowledge/wiki/`
- **Subdirs (kinds):** `concepts/`, `connections/`, `mocs/`, `voices/`, `qa/`
- **CLI:** `/Users/dhyana/bin/wiki` (list / show / search / fzf / related / backlinks / graph / random / stats / index / log / edit / path / open)
- **Regen:** `/Users/dhyana/.dharma/scripts/regen_wiki_index.py` — walks via `wiki_lib.iter_atoms()`, builds index.md with sections: MOCs, Concepts by Tag, Concepts by PARA, High-Density (top 20), Low-Density (bottom 20 — enrichment queue), Orphans, Recently Captured.
- **Existing required-ish frontmatter:** `title`, `confidence` (0.0–1.0), `sources` (list), `stale_after` (date), `related` (list of slugs), `semantic_density` (0.0–1.0).
- **Existing optional:** `tags`, `para`, `status`, `claude_voice`, `domain`, `mocs`, `evolution_seeds`, `crosses_domain`, `dataview_queries`, `energy`, `captured`.
- **Wikilink syntax in body:** `[[slug]]`.
- **Slug = filename minus .md.**

The world-facing schema **extends this** by adding (a) a new `kind` field, (b) new directory subtypes, (c) a `register` field separating `contemplative` (private) from `world` (public-eligible), (d) provenance/safety fields required for any `register: world` atom.

---

## 1. The `register` axis (existing atoms unaffected)

Add one optional top-level field to every atom:

```yaml
register: contemplative  # default if absent — preserves all 249 existing atoms as-is
# OR
register: world          # required for public-render eligibility
# OR
register: bridge         # spans both — viewable in both render layers
```

`iter_atoms()` gains a filter argument; index regen runs twice (private index, public index).

---

## 2. New `kind` field (in addition to directory placement)

Existing atoms have implicit kind from their directory. New atoms declare it explicitly:

```yaml
kind: event | entity | pattern | connection | dot | revelation | actor | dataset | claim | question | concept | moc
```

Backwards-compat: if `kind` absent, infer from parent directory (concept / connection / moc / voice / qa).

**New directories under `~/.dharma/knowledge/wiki/`:**
- `events/` — discrete real-world incidents
- `entities/` — orgs, vessels, facilities, beneficial owners
- `patterns/` — recurring structures
- `dots/` — provisional pattern hypotheses (low confidence)
- `revelations/` — high-confidence cross-source insights
- `actors/` — named human roles
- `datasets/` — pointers to ingested sources
- `claims/` — empirical assertions
- `questions/` — open investigative threads

`mocs/` and `concepts/` keep current semantics; `connections/` is **shared** between contemplative and world registers.

---

## 3. World-facing atom subtypes — full YAML specs

### 3.1 `event`

```yaml
---
title: "Methane plume — Permian Basin operator-X — 2026-04-30"
register: world
kind: event
confidence: 0.82                       # detection confidence
sources:
  - https://carbonmapper.org/api/plumes/abc123
  - dataset:carbon-mapper-tanager1     # internal slug → datasets/
captured: 2026-05-01T08:14:00Z         # when ingested
event_at: 2026-04-30T17:32:00Z         # when the real-world thing happened
event_type: methane_plume              # taxonomy: see §6
location:
  geo: { lat: 31.7619, lon: -103.4150, precision_m: 50 }
  jurisdiction: [US-TX, county:Reeves]
involves_entities: [permian-operator-x, well-pad-7732]
involves_actors: []
related: [methane-super-emitter-pattern, edf-methanesat-watch]
provenance: documentary                # proxy | behavioral | geometric | documentary
stale_after: 2027-05-01
republishable: true                    # default false; explicit opt-in
exposes_vulnerable_persons: false
requires_lawyer_review: false
public: true                           # only if all gates §4 pass
public_at: 2026-05-01T08:30:00Z        # set by gate engine, not by hand
license: CC-BY-4.0                     # of the source data, not the atom
ingested_by: methane_engine_v0.1
semantic_density: 0.0                  # computed by wiki_density_pulse.py
tags: [methane, climate, accountability]
---
```

**Required for `kind: event`:** title, register, kind, confidence, sources, captured, event_at, event_type, location, provenance, stale_after, republishable, exposes_vulnerable_persons.
**Optional:** involves_entities, involves_actors, requires_lawyer_review, license, ingested_by, related, tags.

### 3.2 `entity`

```yaml
---
title: "Permian Operator X (Beneficial Owner: Y Capital Partners)"
register: world
kind: entity
confidence: 0.88
sources:
  - https://www.opencorporates.com/companies/us_tx/...
  - dataset:opencorporates-us
  - dataset:sec-edgar
captured: 2026-05-01T09:02:00Z
entity_type: corporate                  # corporate | vessel | facility | trust | govt | ngo | media
identifiers:                            # all known IDs across registries
  - { kind: ein, value: 12-3456789, source: sec-edgar }
  - { kind: lei, value: 5493001KJTIIGC8Y1R12, source: gleif }
  - { kind: imo, value: null }          # for vessels
beneficial_owners: [y-capital-partners, john-q-doe-1962]
parent_entity: y-capital-partners
jurisdiction: [US-DE, US-TX]
operates_in: [US-TX, US-NM]
involved_in_events: []                  # auto-populated by index regen
involved_in_patterns: [recurrent-methane-emitter]
related: [...]
provenance: documentary
stale_after: 2027-05-01
republishable: true
exposes_vulnerable_persons: false
requires_lawyer_review: true            # naming an entity is a libel surface
public: false                           # default false until lawyer_review = passed
public_at: null
license: ODbL-1.0
semantic_density: 0.0
tags: [oil-gas, permian, beneficial-ownership]
---
```

### 3.3 `pattern`

```yaml
---
title: "Recurrent methane emitter — same operator detected ≥3× / 12mo"
register: world
kind: pattern
confidence: 0.74
sources: [dataset:carbon-mapper-tanager1, dataset:methanesat-l3]
pattern_type: recurrence                # recurrence | network | flow | anomaly | absence
instances: [event:plume-2026-01-12-...,
            event:plume-2026-03-04-...,
            event:plume-2026-04-30-...]
pattern_definition: "Same entity, ≥3 plume detections within 12 months, ≥1 t/h emission, no SEC-reported repair"
threshold: { count: 3, window_days: 365, min_emission_t_per_h: 1.0 }
involves_entities: [permian-operator-x]
related: [methane-super-emitter-engine-target]
provenance: documentary
stale_after: 2027-05-01
republishable: true
exposes_vulnerable_persons: false
public: true
public_at: 2026-05-01T10:00:00Z
semantic_density: 0.0
tags: [methane, recurrence, accountability]
---
```

### 3.4 `connection` (extension of existing connection atoms)

```yaml
---
title: "Plume-2026-04-30 ↔ Permian Operator X"
register: world
kind: connection
connection_type: same-actor-as          # see §5 connection vocabulary
from: event:plume-permian-2026-04-30
to: entity:permian-operator-x
confidence: 0.81
evidence:
  - "Plume centroid within 200m of operator-X well-pad-7732 (verified via state oil-gas registry)"
  - "Wind-direction analysis: emission origin ≤ 50m from pad infrastructure"
sources: [dataset:tx-rrc-pad-registry, dataset:carbon-mapper-tanager1]
captured: 2026-05-01T09:30:00Z
provenance: documentary
stale_after: 2027-05-01
republishable: true
exposes_vulnerable_persons: false
public: true
semantic_density: 0.0
tags: [attribution]
---
```

### 3.5 `dot` (provisional, low-confidence hypothesis)

```yaml
---
title: "DOT: Three Y-Capital portfolios all show methane recurrence in same week"
register: world
kind: dot
confidence: 0.42                        # < 0.6 = stays as dot
sources: [pattern:recurrent-methane-emitter, entity:y-capital-portfolio-list]
captured: 2026-05-07T11:00:00Z
hypothesis: "Y-Capital Partners may have systemic OPEX-cut directive triggering deferred maintenance across portfolio"
involves_entities: [y-capital-partners, permian-operator-x, ...]
candidate_evidence_needed:
  - "Internal Y-Capital portfolio-management directives (FOIA / leak / litigation)"
  - "Maintenance-spend cuts in 10-K filings 2024-2026"
  - "Worker-witness statements re: deferred repair orders"
promote_to_revelation_when:
  - corroborating_sources_count: 3
  - confidence_floor: 0.75
  - human_review: passed
related: [methane-super-emitter-engine-target]
provenance: documentary
stale_after: 2026-08-07                 # short — dots decay faster
republishable: false                    # never publish a dot
exposes_vulnerable_persons: false
requires_lawyer_review: true
public: false
semantic_density: 0.0
tags: [hypothesis, private-investigation, methane]
---
```

### 3.6 `revelation` (high-confidence cross-source insight)

```yaml
---
title: "Y-Capital portfolio shows systemic methane recurrence — pattern across 7 operators"
register: world
kind: revelation
confidence: 0.86
sources: [dot:y-capital-three-portfolios, ..., 12 corroborating atoms]
captured: 2026-06-14T09:00:00Z
promoted_from: dot:y-capital-three-portfolios
promotion_rationale: "Three independent corroborating sources crossed 0.75 confidence threshold; lawyer review passed; dataset-attribution audit clean"
key_finding: "Y-Capital's 7 portfolio operators jointly account for 18% of recurrent emitters in TX/NM in 2024-2026, vs 2% expected by portfolio share"
involves_entities: [y-capital-partners, ...]
involves_patterns: [recurrent-methane-emitter]
related: [methane-super-emitter-engine-target, edf-methanesat-watch]
journalist_legible_summary: "Private equity firm Y-Capital Partners' oil-gas portfolio shows methane-recurrence rates 9× the industry baseline."
provenance: documentary
stale_after: 2027-06-14
republishable: true
exposes_vulnerable_persons: false
requires_lawyer_review: true
lawyer_review_status: passed             # passed | pending | failed
lawyer_review_at: 2026-06-13T14:00:00Z
public: true
public_at: 2026-06-14T09:00:00Z
license: CC-BY-4.0
featured: true                           # appears on front page
semantic_density: 0.0
tags: [methane, private-equity, accountability, revelation]
---
```

### 3.7 `actor`

```yaml
---
title: "John Q. Doe (b. 1962) — Y-Capital Managing Partner"
register: world
kind: actor
confidence: 0.79
sources: [dataset:opencorporates-us, dataset:sec-edgar, dataset:linkedin-public]
captured: 2026-05-01T09:15:00Z
actor_type: corporate-officer            # corporate-officer | govt-official | journalist | ngo-staff | activist | defender | refugee | witness
roles:
  - { entity: y-capital-partners, role: managing-partner, since: 2014, source: sec-edgar }
identifiers:
  - { kind: linkedin, value: john-q-doe-1962, source: linkedin-public }
public_figure: true                      # CRITICAL — gates safety
related: [y-capital-partners]
provenance: documentary
stale_after: 2027-05-01
republishable: true                      # only because public_figure: true
exposes_vulnerable_persons: false        # public_figure overrides
requires_lawyer_review: true
public: false                            # default false until lawyer review
semantic_density: 0.0
tags: [private-equity, named-actor]
---
```

**Refugee / defender / witness actors:** `public_figure: false`, `republishable: false`, `exposes_vulnerable_persons: true`. **Never** rendered publicly. Stored encrypted-at-rest if implementation supports.

### 3.8 `dataset`

```yaml
---
title: "Carbon Mapper Tanager-1 plume catalog"
register: world
kind: dataset
confidence: 1.0                          # datasets are descriptive, not claims
sources: [https://carbonmapper.org/data]
captured: 2026-05-01T07:00:00Z
dataset_url: https://carbonmapper.org/api/plumes
dataset_format: GeoJSON-streaming
update_cadence: daily
license: CC-BY-4.0
coverage: { regions: [global], time_start: 2024-08-01 }
ingestion_method: cron+http              # how dharma_swarm pulls it
ingestion_path: ~/.dharma/ingest/carbon_mapper/
ingestion_schema: ~/.dharma/ingest/carbon_mapper/schema.json
disinformation_risk: low                 # low | medium | high
related: [methane-super-emitter-engine-target]
provenance: documentary
stale_after: 2027-05-01
public: true
semantic_density: 0.0
tags: [dataset, methane, satellite]
---
```

### 3.9 `claim`

```yaml
---
title: "CLAIM: Y-Capital portfolio methane-recurrence rate is 9× industry baseline"
register: world
kind: claim
confidence: 0.86
sources: [revelation:y-capital-systemic-methane, dataset:carbon-mapper-tanager1, dataset:edgar-10k-filings]
captured: 2026-06-14T09:30:00Z
claim_text: "Y-Capital's 7 portfolio operators jointly account for 18% of recurrent emitters in TX/NM in 2024-2026, vs 2% expected by portfolio share."
claim_type: empirical-comparative        # empirical-comparative | causal | descriptive | predictive | normative
methodology: |
  Numerator: count of recurrent-methane-emitter pattern instances 2024-2026 attributed to operators with verified Y-Capital ownership stake.
  Denominator-A: total recurrent-methane-emitter instances same period and region (n=152).
  Denominator-B: expected share = sum(Y-Capital portfolio operator-output) / total regional output (= 2%).
  Test: chi-squared one-tailed, p < 0.001.
falsifiable_by:
  - "Demonstration that ≥3 of the 7 attributed operators have non-Y-Capital majority ownership"
  - "Demonstration that recurrent-emitter classification has systematic bias toward Y-Capital portfolio"
provenance: documentary
stale_after: 2027-06-14
republishable: true
exposes_vulnerable_persons: false
requires_lawyer_review: true
lawyer_review_status: passed
public: true
semantic_density: 0.0
tags: [empirical-claim, methane, private-equity]
---
```

### 3.10 `question`

```yaml
---
title: "Q: Why does Y-Capital's portfolio show 9× recurrence vs control?"
register: world
kind: question
confidence: 0.0                          # questions don't claim
sources: [revelation:y-capital-systemic-methane]
captured: 2026-06-14T10:00:00Z
candidate_explanations:
  - "Systemic OPEX-cut directive (testable via internal docs)"
  - "Selection bias — Y-Capital acquires distressed assets with deferred maintenance (testable via acquisition records)"
  - "Operator-level rather than portfolio-level effect (testable by null-model)"
investigative_threads:
  - "FOIA TX-RRC inspection records for 7 operators 2020-2026"
  - "Pull 10-K MD&A sections for maintenance-spend trends"
  - "Cross-reference with Walk Free / IJM forced-labor flags in supply chain"
related: [revelation:y-capital-systemic-methane, dot:y-capital-three-portfolios]
provenance: documentary
stale_after: 2026-12-14
public: true                             # questions are public; only answers are gated
semantic_density: 0.0
tags: [open-question, methane, private-equity]
---
```

---

## 4. Telos gates for world-facing atoms (publication firewall)

Before any atom flips `public: true`, **all gates must pass.** Implemented as `~/.dharma/scripts/wiki_publication_gate.py`, called by index regen.

| Gate | Rule | Atom-types it fires on |
|---|---|---|
| `vulnerable_person_gate` | Block if `exposes_vulnerable_persons: true` AND `public_figure` not in actor frontmatter | actor, event, claim, revelation |
| `libel_gate` | Block if names a specific living person/entity AND `requires_lawyer_review` AND `lawyer_review_status != passed` | entity, actor, claim, revelation |
| `citation_retrievability_gate` | Block if any `sources:` entry is unreachable (HTTP 4xx/5xx, missing dataset slug) | all `register: world` |
| `disinformation_gate` | Block if any source dataset has `disinformation_risk: high` AND no corroborating independent source | event, claim, revelation |
| `pramana_gate` | Require explicit `provenance:` field in {proxy, behavioral, geometric, documentary} — block if absent | all `register: world` |
| `confidence_floor_gate` | Block `revelation` with `confidence < 0.75`; block `claim` with `confidence < 0.7` | claim, revelation |
| `staleness_gate` | Refuse to render an atom whose `stale_after` < today (mark `stale: true`, exclude from public render) | all |

Implementation: each gate is a function in `wiki_publication_gate.py`. Returns `(passed: bool, reason: str)`. The aggregate gate logs every failure to `~/.dharma/knowledge/wiki/_gate_log/<date>.jsonl`. Atoms that fail any gate are kept in repo with `public: false` and a `_blocked_by:` field listing failures.

---

## 5. Cross-pollination graph schema

### 5.1 Connection vocabulary (all valid `connection_type:` values)

`cites`, `contradicts`, `corroborates`, `same-actor-as`, `same-jurisdiction-as`, `temporal-precedes`, `spatial-overlaps`, `pattern-instance-of`, `funded-by`, `regulated-by`, `supplies`, `competes-with`, `succeeds`, `prior-art-for`.

### 5.2 Auto-link triggers (run on atom-create or atom-update)

Implementation: `~/.dharma/scripts/wiki_auto_link.py`, queued via post-write hook.

| Trigger | Heuristic | Output |
|---|---|---|
| identifier match | New atom shares any `identifiers[].value` with an existing atom | propose `same-actor-as` connection |
| spatial overlap | New `event.location.geo` within 500m of existing event | propose `spatial-overlaps` |
| temporal precedence | Two events on same entity within 90 days | propose `temporal-precedes` |
| jurisdiction match | Same state/country and same `event_type` | propose `same-jurisdiction-as` |
| beneficial-ownership chain | New `entity.beneficial_owners` overlap with existing entity's parent chain | propose `same-actor-as` (with depth) |
| named-entity NER | Body of new atom mentions [[wikilink]] candidates not in `related:` | propose `cites` |
| pattern membership | New event matches existing pattern's `threshold:` rule | propose `pattern-instance-of`, increment pattern's `instances:` |

Proposed connections land in `~/.dharma/knowledge/wiki/_pending_connections/` for human/agent review before promotion to `connections/`.

### 5.3 The "dot connection" engine — when does a connection become a finding?

A `dot` is created when:
- ≥2 existing atoms share a non-trivial property (entity, geography, temporal proximity)
- AND no existing `pattern` or `revelation` already covers the link
- AND human inspection or single-LLM call would not surface it (novelty heuristic: the two atoms have ≤1 prior shared backlink)

A `dot` promotes to `revelation` when:
1. `confidence ≥ 0.75`
2. ≥3 corroborating sources from independent datasets (e.g., satellite + corporate registry + court filing)
3. `lawyer_review_status: passed` (if names entities/actors)
4. All telos gates §4 pass

A `revelation` becomes `featured: true` (front-page) when:
- `journalist_legible_summary` is ≤200 words
- ≥1 partner org tagged in `related:` (NGO, journalist, regulator)
- Human approval (Dhyana or designee) marked in `_featured_approvals/<slug>.txt`

---

## 6. Event-type taxonomy (controlled vocabulary)

Initial domains. Extend by adding to `~/.dharma/knowledge/wiki/_taxonomy/event_types.yaml`.

```yaml
environmental:
  - methane_plume
  - deforestation_alert
  - mining_alert
  - oil_spill
  - air_quality_excursion
  - water_contamination
  - wildlife_trafficking_intercept
  - illegal_logging
maritime:
  - dark_vessel_detection
  - ais_disabling_event
  - port_arrival
  - illegal_fishing_signal
financial:
  - sec_filing
  - sanctions_listing
  - shell_company_registration
  - beneficial_owner_change
  - ipo_filing
legal:
  - lawsuit_filed
  - settlement_announced
  - regulatory_action
  - foia_response
  - whistleblower_disclosure
labor:
  - forced_labor_signal
  - factory_audit_failure
  - displaced_worker_intake
  - skill_match_completed
political:
  - election_anomaly
  - gerrymandering_finding
  - lobbying_disclosure
  - regulatory_capture_signal
health:
  - outbreak_signal
  - pharmacovigilance_alert
  - rare_disease_aggregation
```

---

## 7. Public render layer

**Choice:** **Quartz v4** (https://quartz.jzhao.xyz). It already understands Obsidian-style `[[wikilinks]]`, YAML frontmatter, tag pages, graph view. Native fit for this corpus. Static-site, deploys to Cloudflare Pages or GitHub Pages. Free.

**Pipeline:**

```
~/.dharma/knowledge/wiki/                  # source-of-truth
        │
        ├─ regen_wiki_index.py             # private index (all atoms)
        │
        ├─ wiki_publication_gate.py        # marks public flags
        │
        ├─ wiki_world_export.py  ── NEW   # copies register: world | bridge with public: true
        │                                   into ~/.dharma/sites/dharma-eyes/content/
        │
        └─ Quartz build  (npx quartz build --serve | --bake)
                ├─ public-index.html       # MOCs + featured revelations + recent dots
                ├─ /events/, /entities/, /patterns/, /revelations/  (per-kind sections)
                ├─ /tags/<tag>/             (tag pages)
                ├─ /graph                   (interactive graph view, Obsidian-style)
                ├─ /feed.xml                (RSS — new revelations only)
                └─ /api/atoms.json          (machine-readable export, JSON-LD recommended)
```

**Public site name:** to be chosen by Dhyana. Suggestion neutral candidates: `dharma-eyes`, `lattice`, `the-loom`, `cross-weave`, `seeings`, `the-watch`. The internal name `dharma_swarm` does NOT appear externally per ARJUNA.md.

**Deploy target:** Cloudflare Pages (free tier; 500 builds/mo; instant rollback). DNS later.

**RSS:** auto-generated from new `revelation:` atoms with `featured: true`. One revelation = one feed item. `<dc:source>` = `journalist_legible_summary`.

**Graph view:** Quartz's built-in graph. Filter UI: by tag, by event_type, by jurisdiction, by date range. Featured revelations appear bold.

---

## 8. Migration path — the existing 249 inward atoms

**Step 1 (one-time, automated).** A migration script `~/.dharma/scripts/wiki_register_migrate.py`:
- Walks all atoms.
- For each atom with no `register:` field, infers register from tags + path:
  - tags include any of {bridge, claude-voice, contemplative, akram, altitude} → `register: contemplative`
  - tags include any of {infra, governance, computational, agent-pattern} AND no contemplative tags → `register: bridge`
  - explicit override list (e.g., `bridge-hypothesis`) → `register: bridge`
  - default fallback → `register: contemplative`
- Writes the field in-place via atomic-tmp pattern.
- Outputs a manifest at `~/.dharma/knowledge/wiki/_migration/2026-05-07-register.csv` (slug, old-state, new-register, rationale).

**Step 2.** Update `wiki_lib.iter_atoms()` to accept `register=` filter; default to all.

**Step 3.** `regen_wiki_index.py` runs twice: once for `register in {contemplative, bridge}` → `index.md` (private), once for `register in {world, bridge}` → `index_public.md`.

**Step 4.** Move no files. The `concepts/` dir continues to host both contemplative and bridge atoms; new `events/`, `entities/`, etc. directories host world atoms. The `register:` field, not the path, governs visibility.

**Step 5.** Add a `_private/` subdirectory only for actor atoms with `exposes_vulnerable_persons: true`. These live encrypted-at-rest if the implementation reaches that maturity.

**Step 6.** Existing `wiki` CLI is unchanged. Add new commands:
- `wiki public list` — list all `register: world | bridge` atoms with `public: true`
- `wiki gate-status <slug>` — show which telos gates pass/fail for a draft atom
- `wiki promote <dot-slug>` — invoke promote-dot-to-revelation logic
- `wiki ingest <dataset-slug>` — kick off ingestion run for a registered dataset

---

## 9. Out of scope for this spec (named so it isn't lost)

- Encrypted-at-rest storage for vulnerable-actor atoms (implementation note: age-encryption is the simplest path).
- Multi-tenant access control if external orgs ever directly write into the wiki.
- Redaction-on-export for atoms shared partially with partners (different problem from public/private split).
- Scraper inventory itself — that's a separate strategy doc; this spec only defines how scraped atoms are *shaped*.

---

*Drop-in implementation reference: every YAML key above maps to a Python dataclass field in a new `~/.dharma/scripts/wiki_world.py` module. Existing atoms keep parsing because all new fields are optional with safe defaults. Index regen is split into private/public passes via the `register:` filter. Public render is Quartz v4. Telos gates are pure functions composable into the existing pipeline. Migration is one script, idempotent, ~30 minutes wall-clock for 249 atoms.*
