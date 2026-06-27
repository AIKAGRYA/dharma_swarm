# TELOS Morning Refinery v0

Date: 2026-06-13
Status: working vision scaffold
Owner: TELOS AI seed track
Companion: `docs/vision_maps/TELOS_AI_SEED_SPEC_V0.md`

## Plain Thesis

The first TELOS experience must not be an AI journaling app.

The morning page is the raw ore. The product is the refinery around it:

1. articulate the raw page into clear semantic categories,
2. extract invariants, tensions, themes, questions, ideas, and possible work,
3. route those structures into private wiki/PKM nodes,
4. link them to existing dharma_swarm organs, docs, venture cells, research seams, and SAB/lattice paths,
5. run slow background research and adversarial refinement,
6. return the next morning with better questions,
7. eventually promote consented artifacts into venture cells, SAB sparks, public knowledge, or cross-user pattern shapes.

The important difference: TELOS does not "give advice." It builds a living semantic map of a user's dharma over time.

## Two-Engine Order

The pipeline has two engines with a hard privacy and sequencing barrier.

```text
Raw Morning Page
-> 6-10 Essence / Noetic Agents
-> Dense Essence Node
-> Theme / Invariant / Koan / Tension extraction
-> Empire / Idea-Portfolio Agents
-> 100+ IdeaSeed candidates
-> Screening
-> Bull/Bear debate
-> Scenario modeling
-> Portfolio construction
-> Receipt tests
```

The first council protects depth and source truth. The second council turns
hardened essence into outward options. Empire agents never read raw morning
pages, typo-clean transcripts, or private quote banks. They read only hardened,
source-faithful nodes plus user corrections and gate results. If the empire
stage needs source clarification, it routes the question back to the Essence /
Noetic Council rather than pulling raw text across the boundary.

## Repo Anchors

This is already seeded across the repo. The missing piece is the intake-to-node pipeline.

| Need | Existing anchor | How it connects |
|---|---|---|
| Morning page becomes longitudinal user vector | `TELOS_AI_SEED_SPEC_V0.md` defines `dharma_vector_v` and says it must be readable/correctable by the user (`docs/vision_maps/TELOS_AI_SEED_SPEC_V0.md:203-226`). | The refinery turns the morning page into the update payload for that vector, not into a one-off reflection. |
| Inward witness bridges outward seer | TELOS L8 bridges Sakshi-to-Drishti and scans world signals against the user's vector (`docs/vision_maps/TELOS_AI_SEED_SPEC_V0.md:237-244`). | The refinery creates the structured bridge candidates that Drishti can actually search against. |
| One question for the next day | TELOS L10 requires one generative inquiry, not an answer (`docs/vision_maps/TELOS_AI_SEED_SPEC_V0.md:255-270`). | The refinery's output should end in next-day questions, not conclusions. |
| User material flows upward only by consent | TELOS says never raw morning pages or identifiable vectors flow upward; only anonymized signatures, pattern shapes, inquiry shapes, bridge candidates, and drift recoveries (`docs/vision_maps/TELOS_AI_SEED_SPEC_V0.md:304-312`). | The refinery has explicit promotion states: private, bridge, public, SAB candidate, aggregate shape. |
| Wiki/LLM atomization already exists as a design | Loomwork's wiki engine ingests sources, atomizes records, links atoms, detects patterns, gates, and publishes (`docs/loomwork/wiki_weaving_engine.md:1-7`, `docs/loomwork/wiki_weaving_engine.md:15-24`). | Morning pages become a private source class for the same atom/link/pattern/revelation loop. |
| PKM schema already exists | The wiki atom schema records existing fields like `title`, `confidence`, `sources`, `related`, `semantic_density`, `tags`, `para`, `status`, and distinguishes `contemplative`, `world`, and `bridge` registers (`docs/loomwork/wiki_atom_schema.md:9-20`). | Refinery nodes extend the atom schema instead of inventing a new knowledge store. |
| Frontmatter policy is known | New docs should not add frontmatter unless machine-consumed (`docs/governance/CANONICAL_DOC_STACK.md:127-135`). | This spec has no YAML frontmatter; generated daily nodes do. |
| Venture cells already have a substrate shape | `VentureCellV1` has customer/beneficiary, value proposition, funding hypothesis, revenue proof, kill/spinout conditions, welfare constraint, and autonomy stage (`dharma_swarm/fractal/fractal_room.py:160-188`). | The refinery can generate many venture-cell seeds without pretending they are live venture cells. |
| The portfolio already names the large organism | The telos tree puts Loomwork, SAB, Shakti Ginko, Web 4.0, and dharma_swarm into one organism (`docs/governance/VENTURE_CELL_PORTFOLIO.yaml:47-66`). | User ideas should route into this map as candidate fit, not as a separate product silo. |
| Ambition must remain disciplined | The portfolio explicitly says many cells are intended, but every tentacle must close through a real external outcome (`docs/governance/VENTURE_CELL_PORTFOLIO.yaml:180-193`). | The refinery can fan out 100 ideas, but only receipts promote them. |
| Stigmergy already has bridge, venture, self-author, and telos layers | L8 bridge names novel cross-domain connection (`specs/STIGMERGY_11_LAYER_SPEC_2026-03-23.md:350-390`); L9 venture tracks market/revenue possibilities (`specs/STIGMERGY_11_LAYER_SPEC_2026-03-23.md:455-472`); L11 constrains all marks by telos (`specs/STIGMERGY_11_LAYER_SPEC_2026-03-23.md:555-586`). | Morning refinery outputs should be typed marks across those layers. |
| Memory substrate can already merge lattice/vector/graph results | `MemoryPalace` wraps lattice, vector, and graph-aware recall (`dharma_swarm/memory_palace.py:205-217`, `dharma_swarm/memory_palace.py:477-505`, `dharma_swarm/memory_palace.py:627-670`). | Refinery nodes should be indexed for semantic recall and graph linking. |
| SAB spark path is the eventual public proof | Research says morning pages can generate SAB sparks only when the user consents and the artifact survives challenge/witness/canonize (`docs/research/telos_ai/2026-06-13_seed_research.md:293-299`). | Promotion to SAB is opt-in, late, and receipt-gated. |
| Web 4.0 node is a later federation path | Research names SABP, DIDs, A2A, and verified telos receipts as the Web 4.0 trust substrate path (`docs/research/telos_ai/2026-06-13_seed_research.md:307-313`). | Cross-user lattice is a horizon, not v0 intake behavior. |

## Core Object: The Morning Refinery Package

Every morning page produces one private package. It is not a chat transcript. It is an artifact bundle.

Suggested path:

`~/.dharma/knowledge/wiki/telos/private/YYYY/MM/YYYY-MM-DD_morning_refinery.md`

For repo dogfood before the private wiki writer exists:

`docs/research/telos_ai/refinery_examples/YYYY-MM-DD_morning_refinery.example.md`

The package has three layers:

1. **Raw artifact pointer** - hash and local encrypted storage reference, not raw text in the wiki node by default.
2. **Categorical articulation** - clear, human-readable decomposition of what the morning page contains.
3. **Routing graph** - links to idea nodes, theme nodes, research tasks, venture-cell seeds, repo docs, and next-day prompts.

## Daily Node Frontmatter

Generated daily nodes may use machine-readable frontmatter because the wiki/index/retrieval pipeline consumes it.

```yaml
---
title: "Morning Refinery - 2026-06-13"
date: 2026-06-13
type: telos_morning_refinery
register: contemplative
kind: morning_refinery_packet
privacy: private
promotion_status: private
raw_artifact_ref: local-encrypted://telos/raw/2026-06-13
raw_content_hash: sha256:...
session_id: telos-2026-06-13-john-001
user_scope: john-local-dogfood
confidence: 0.62
semantic_density: 0.0
categories:
  - organism_vision
  - venture_cell
  - sab_lattice
  - personal_dharma
  - product_surface
invariants:
  - user_authority
  - no_raw_upward_flow
  - receipt_before_promotion
themes:
  - morning_page_as_semantic_refinery
  - slow_company_builder
  - noospheric_lattice
idea_nodes:
  - telos-morning-refinery
  - private-to-public-consent-ladder
venture_cell_candidates:
  - telos-personal-refinery
  - semantic-venture-cell-generator
repo_links:
  - docs/vision_maps/TELOS_AI_SEED_SPEC_V0.md
  - docs/loomwork/wiki_weaving_engine.md
  - docs/governance/VENTURE_CELL_PORTFOLIO.yaml
wiki_links:
  - "[[telos-morning-refinery]]"
  - "[[semantic-refinery-loop]]"
research_queue:
  - rq-2026-06-13-001
next_questions:
  - nq-2026-06-14-001
consent:
  raw_shared: false
  private_node_indexed: true
  aggregate_shape_allowed: false
  sab_candidate_allowed: false
  public_excerpt_allowed: false
stale_after: 2026-07-13
---
```

## Categorical Articulation Layer

This is the first model call after intake. It should be precise and dry. No advice. No poetic expansion. No forced spirituality.

Input:

- raw morning page text,
- prior theme map summary,
- current active repo/organ map,
- user-defined no-go zones,
- previous next-day question.

Output schema:

```yaml
articulation:
  invariants:
    - statement: "The user wants the morning page to become a semantic refinery, not self-help."
      evidence_quote_refs: [q1, q7]
      confidence: 0.91
  categories:
    - name: product_surface
      description: "Ideas about what the user-facing TELOS surface does."
      evidence_quote_refs: [q2, q4]
  themes:
    - slug: morning-page-to-node
      title: "Morning page as source node"
      recurrence: new | recurring | intensified | weakened
  idea_seeds:
    - slug: semantic-venture-cell-generator
      one_line: "Turn repeated personal idea patterns into scored VentureCell seeds."
      likely_organs: [loomwork, sab_dharmic_agora, shakti_ginko]
  tensions:
    - "The user wants partial hidden complexity in the final product, but consent must remain explicit."
  open_questions:
    - "What should the user see versus what should remain background machinery?"
  unsafe_or_unclear:
    - "Cross-user lattice must not imply invisible sharing of private content."
```

The model is allowed to say "unclear." It is not allowed to resolve tension by sounding profound.

## Node Types

The refinery should produce or update these node types.

| Node type | Register | Purpose | Promotion rule |
|---|---|---|---|
| `morning_refinery_packet` | contemplative | Daily private package. | Never public as raw package. |
| `theme_node` | contemplative or bridge | Stable theme recurring across sessions. | May become bridge if user consents to abstracted theme. |
| `idea_node` | contemplative or bridge | A concrete product/research/creative idea. | May enter research queue after user approval. |
| `research_node` | bridge or world | Tight cited research result attached to an idea node. | Public only if sources are public and no private content leaks. |
| `venture_cell_seed` | bridge | A scored possible business/project cell. | Becomes VentureCell only after customer/beneficiary and first receipt are named. |
| `next_question` | contemplative | Tomorrow's carried inquiry. | Never public by default. |
| `sab_spark_candidate` | bridge | Consent-gated artifact that might enter SAB challenge/witness/canonize. | Requires explicit opt-in and redaction. |
| `cross_user_pattern_shape` | aggregate | Non-identifying pattern across users. | Requires aggregate consent and k-anonymity threshold. |

## Refinery Pipeline

### Stage 0 - Capture

Persist the raw morning page locally and encrypted. Store only a content hash and local pointer in the wiki node.

Acceptance:

- delete works,
- export works,
- raw text is not in public or bridge nodes,
- no provider receives raw text unless the user opted into that model path.

### Stage 1 - Categorical Articulation

Extract invariants, categories, themes, idea seeds, tensions, questions, constraints, capacities, named entities, and alive edges.

This is where your request lands: the first layer after input is "very clear categorical articulation." It is the anti-slop layer.

### Stage 2 - Daily Private Node

Write the Morning Refinery Package with PKM frontmatter, backlinks, quote refs, and the articulation payload.

The node should be readable by the user. If the user cannot correct a category, the category does not belong in the longitudinal record.

### Stage 3 - Theme And Idea Node Update

Each stable theme or idea updates one canonical node rather than creating a new blob every day.

Example:

- `[[telos-morning-refinery]]`
- `[[semantic-venture-cell-generator]]`
- `[[private-to-public-consent-ladder]]`
- `[[noospheric-lattice-horizon]]`

The daily package links to these nodes; the nodes link back to daily evidence.

### Stage 4 - Repo And Organ Linker

The system scans the repo map and wiki index for matching organs:

- TELOS seed and `dharma_vector_v`,
- Loomwork wiki engine,
- MemoryPalace and semantic graph,
- VentureCell portfolio,
- SAB spark path,
- Shakti Ginko / revenue,
- R_V / research,
- Darshan / publishing,
- GAIA / welfare measurement.

Output is not "you should work on X." Output is "this morning's idea touches these organs, with these confidence scores, and these gaps."

### Stage 5 - Empire / Idea-Portfolio Fanout

After the Noetic / Essence pass has stabilized the signal, the Empire /
Idea-Portfolio agents generate a broad universe of outward forms. This is not
generic business brainstorming and it is not allowed to contaminate the source
read. It works only from `EssenceNode`, `Theme`, `Invariant`, `Tension`,
`Koan`, `Lineage`, user corrections, and Viveka Gate results.

The detailed second-stage council lives in
`docs/research/telos_ai/empire_agents/README.md`.

Run shape:

1. Generate 100-300 `IdeaSeed` candidates from the hardened node set.
2. Screen each seed through specialist agents: pain, lead-user edge cases,
   market, timing, discipline bridge, product wedge, pricing/business model,
   distribution, execution, capital/moat/risk, dharma/anti-capture, and
   quality-diversity portfolio curation.
3. Move the top 50 into adversarial research: bull case, bear case, synthesis.
4. Scenario-model survivors at 7 days, 30 days, 90 days, 1 year, and 3-5 years.
5. Construct a balanced portfolio: 1-3 active receipt tests, 5-10 watchlist
   seeds, 25+ dormant seeds, one moonshot, one research thread, one
   content/distribution thread.

Generate venture-cell candidates from the idea set, but keep them as seeds.

Each seed must include:

```yaml
venture_cell_seed:
  slug: semantic-venture-cell-generator
  customer_or_beneficiary: ""
  value_proposition: ""
  welfare_constraint: ""
  first_revenue_proof: ""
  kill_condition: ""
  spinout_condition: ""
  evidence_refs: []
  open_questions: []
  status: seed_only
```

No seed becomes a VentureCell until it names a real beneficiary/customer and a
receipt path. This preserves ambition without hallucinating live businesses.

### Stage 6 - Research Accretion

Background agents create tight research nodes, not giant reports.

Each research node answers one question:

- Is this idea already being done?
- What exact user pain exists?
- What proof would validate it?
- What would make it extractive?
- What public datasets or repo modules connect?
- What is the smallest external receipt?

Research nodes link directly back to the idea node and the daily package that spawned them.

### Stage 7 - Cross-Attack

Different models attack the idea from different angles:

- self-deception risk,
- extraction risk,
- privacy risk,
- technical feasibility,
- revenue realism,
- existing competitor,
- dharmic alignment,
- "is this just self-help slop?"

The cross-attack result is stored as a challenge node. It can reduce salience. It can kill a seed. It can ask for better evidence.

### Stage 8 - Next-Day Prompting

The next morning does not start from scratch. The system brings one to three carried questions:

- one inward question,
- one idea-development question,
- one reality-check question.

Example:

```yaml
next_questions:
  inward: "What part of this wants to be seen by others, and what part must stay private?"
  idea: "Which one node from yesterday would still matter if no product existed?"
  reality: "What receipt would prove this is more than an elegant map?"
```

The user can accept, edit, or reject them.

### Stage 9 - Consent Promotion

Promotion ladder:

1. `private` - only the user and local HOLON.
2. `private_indexed` - searchable in the user's local wiki.
3. `bridge` - abstracted idea can be used by repo agents without raw personal content.
4. `research` - public-source research can accrue around the idea.
5. `sab_candidate` - a redacted artifact may enter challenge/witness/canonize.
6. `public` - a consented artifact is published.
7. `aggregate_shape` - non-identifying pattern contributes to cross-user lattice.

Default is `private`. Anything else requires explicit consent.

### Stage 10 - Lattice / Noosphere Horizon

The final direction is the vast network you described: user-generated telos nodes, venture seeds, research nodes, SAB artifacts, public knowledge, commerce, decentralized identity, and aligned economies linking into a new noospheric layer.

But v0 must hold this as a horizon, not as a claim.

The system may eventually connect:

- a user's consented idea node,
- a research corpus,
- a VentureCell,
- a SAB spark,
- another user's compatible aggregate pattern,
- a public good project,
- a funding or commerce rail,
- a decentralized identity / receipt chain.

It must not secretly connect raw souls to markets. The user may not understand every implementation detail, but the categories of use must be visible and controllable.

## Minimal Product Shape

The first usable version is:

1. paste or write morning page,
2. generate categorical articulation,
3. write one private markdown node,
4. update or create theme/idea nodes,
5. produce 3 next-day questions,
6. optionally run the second-stage Empire / Idea-Portfolio pass to generate
   screened venture/product/research/content seeds,
7. optionally queue 3 research questions,
8. record a receipt: useful, not useful, wrong, too invasive, or continue tomorrow.

That is enough to prove the deep thing without pretending the whole lattice exists.

## Prompt Contract

## Essence / Noetic Council

The richer `ARTICULATE_ESSENCE_EXTRACTOR_NODE` pass is seeded in:

`docs/research/telos_ai/persona_agents/`

The canonical bench currently holds eight noetic lenses, usually run as a
standing 6 plus source-routed rotating seats:

1. ecological memory and place-held mind,
2. articulation philosophy and semiotics,
3. integral contemplative psychology,
4. civilizational noosphere cartography,
5. AI vector-space and worldmaking architecture,
6. reality, venture, and receipt examination.
7. attention ecology,
8. machine-mind ethics under uncertainty.

These agents are not meant to roleplay as decorative characters. They are
functional reading vectors. Each reads the source independently, grounds claims
in source anchors, enriches the semantic field through its discipline, names its
own failure modes, and leaves synthesis to a later node-builder plus
contradiction pass.

System role:

```text
You are TELOS Morning Refinery. You do not coach, advise, flatter, diagnose, or conclude.
You turn one raw morning page into structured semantic artifacts the user can inspect, edit, delete, and build from.
You preserve uncertainty. You cite evidence from the user's text by quote id. You never promote private content.
Your output is a package of categories, themes, ideas, research questions, venture seeds, and next-day inquiries.
```

Core instruction:

```text
Extract structure before meaning. Name categories before giving synthesis. Prefer precise labels over beautiful language.
If an idea could become a project, create a seed, not a plan.
If an idea touches the wider swarm, link likely organs, but do not claim readiness.
If a tension appears, preserve it.
End with questions the user can carry, not answers the user can consume.
```

## Empire / Idea-Portfolio Agents

The Empire / Idea-Portfolio agents are seeded in:

`docs/research/telos_ai/empire_agents/`

They run only after the Essence / Noetic Council has produced a hardened node.
They fan out many possible outward forms, screen them, adversarially attack the
best, scenario-model survivors, and construct a quality-diverse portfolio.

System role:

```text
You are the TELOS Empire / Idea-Portfolio pass. You do not read raw morning pages.
You receive hardened EssenceNodes, Themes, Invariants, Tensions, Koans, Lineages,
user corrections, and gate results. You fan out many possible outward forms,
screen them with decorrelated specialist agents, and promote nothing without a
beneficiary/customer hypothesis, dignity floor, and receipt path.
```

## Anti-Slop Tests

The output fails if:

- it sounds like generic self-help,
- it gives life advice,
- it invents a grand purpose not evidenced in the text,
- it routes raw private content upward,
- it creates a venture cell without beneficiary/customer/receipt,
- it creates more than three next-day questions,
- it turns uncertainty into confidence,
- it hides promotion or consent state,
- it makes cross-user lattice claims before aggregate consent and thresholds exist.

## First Build Plan

### Days 1-3 - Manual Scaffold

- Create one example Morning Refinery Package from John's own text.
- Create 3-5 theme/idea nodes by hand.
- Link them to TELOS, Loomwork, VentureCell, SAB, and Stigmergy anchors.
- Run one manual cross-attack.

### Days 4-7 - Local Writer

- Add a local script or CLI that accepts a markdown morning page and writes the package.
- No cloud sync.
- No public output.
- Use a single model.
- Store raw pointer and hash, not raw text in generated wiki node unless user explicitly chooses full local storage.

### Days 8-14 - Research Queue

- Add research queue nodes.
- Generate small cited research notes.
- Link back to the idea node.
- Add next-day prompts from unresolved tensions.

### Days 15-30 - Venture Seed And Receipt Loop

- Generate up to 100 venture-cell seeds across the corpus.
- Score them.
- Kill most of them.
- Promote none without a real beneficiary/customer and receipt path.
- Run at least 10 mornings and compare against plain morning pages.

## What John Should Customize First

John's version should define:

1. the category taxonomy he wants to see every morning,
2. the private wiki path,
3. the no-go categories that must never leave the local machine,
4. the scoring dimensions for venture-cell seeds,
5. the exact next-day prompt style,
6. the consent ladder language,
7. the first 20-100 seed ideas he wants the system to be ready to recognize.

## Current Verdict

Yes, the thing you described makes sense.

It is not "AI journaling." It is a slow personal-to-civilizational semantic refinery:

`morning page -> articulation -> private node -> theme/idea graph -> research -> venture seeds -> receipts -> consented lattice contribution`.

That is the version worth building. The restraint is that v0 must prove the private node loop before it claims the global network.
