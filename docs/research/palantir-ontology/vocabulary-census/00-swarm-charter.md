# Layer 2 Vocabulary Inhabitation Swarm — Charter

**Operator directive (verbatim):**
> "I just want layer 2 automated more until we get more consensus. I want agents to think this through, map things, look deeper at the code base, how it relates to the large meta docs and vision docs, see what is most active in these last few months and start to just have more intimate working understanding before presenting me with the names and paragraphs underneath explaining the logic in a narrative-like form."
>
> "90 days is ok unless it is a powerful meta doc or vision doc or something that maybe by mistake got archived... yes per option B [Palantir-canonical camelCase]. I want intelligent lively back and forth on this."

## Posture
- **Inhabit first, name second.** No agent proposes a name in Pass 1. Pass 1 is felt-sense building.
- **Palantir-canonical default** (plain camelCase, no dots, no `.v<N>`), per Option B grounding in `auto-grounded/2026-06-01-1200-oms-hardening-pr409.md`. Flag any case where the convention betrays the meaning.
- **Intelligent lively back-and-forth.** Agents argue in writing in workspace files. Disagreement is signal, not noise. Convergence must be earned, not assumed.
- **PhD-grade, 5th-grade reality.** Be the adult. Challenge Devin's 21 names. Challenge my morning trio. Challenge each other.
- **90-day activity window for "what's alive"** — but pull in any older meta/vision/doctrine doc that earns its place. Specifically inspect:
  - `docs/archive/PALANTIR_ONTOLOGY_GAP_ANALYSIS.md`
  - `docs/archive/VISION_COMPLETE_CIRCUIT.md`
  - `docs/archive/UNASSAILABLE_SYSTEM_BLUEPRINT.md`
  - `docs/archive/DHARMA_SWARM_1000X_MASTERPLAN_2026-03-16.md`
  - `docs/_archive/2026-04/FOUNDATIONS_TO_CODE_MAP.md`
  - any other archived doc the corpus-reader judges as load-bearing

## Layer 2 = Vocabulary
The set of typed objects the system speaks in. Devin mechanically picked 21. The question is not "is 21 the right number" but: **what does this system actually have to say about itself, and what are the right nouns to say it in?**

## Pass structure

### Pass 1 (parallel, ~90min) — Inhabit
Four agents work in parallel, save findings to workspace files. NO naming yet.

- **1a — Vision/Doctrine corpus reader.** Reads `docs/governance/`, `docs/doctrine/`, `docs/vision_maps/`, `docs/loomwork/vision/`, `docs/dse/`, plus the flagged archives. Builds concept map: what does the *system itself* claim to be about? What recurring nouns appear in vision language? What is the metaphysics? Output: `passes/1a-vision-concept-map.md`.

- **1b — Code-walker.** Walks `dharma_swarm/`, `api/`, key tests. Maps actual classes, NATS subjects, agent_cards, message envelopes, state machines. What objects does the code already model? What does the code call them? Output: `passes/1b-code-reality-map.md`.

- **1c — Activity archaeologist.** Reads last 90 days of git log, PRs, issues, NATS subjects-in-use, MERGE_LEDGER, DAILY_OPERATING_BRIEF, ACTIVE_TRACK.yaml. What concepts are *alive* — getting touched, debated, evolving? What is dormant? Where is the energy? Output: `passes/1c-aliveness-map.md`.

- **1d — Prior-art critic.** Re-reads Devin's 21 (PR #409 `ontology/typed_objects_registry.py`), my morning trio (PR #410), the cron grounding (PR #413), PALANTIR_ONTOLOGY_GAP_ANALYSIS archive, and the Palantir community guide. Where did Devin's 21 come from? Which are load-bearing vs. cargo-cult? Output: `passes/1d-prior-art-critique.md`.

### Pass 2 (~60min) — Lively back-and-forth
One synthesis agent reads all four Pass 1 files, then writes a **debate doc** (`passes/2-debate.md`) that:
- Surfaces where the four maps agree (consensus zones)
- Surfaces where vision-language and code-reality diverge (tension zones)
- Surfaces where one concept has 3 names across the corpus
- Surfaces where one name does too much work (overloaded)
- Surfaces where Devin's 21 are well-grounded vs. where they appear to be made up
- Frames the open questions that Pass 3 must resolve

### Pass 3 (~90min) — Narrative vocabulary
Final synthesis agent produces `docs/research/palantir-ontology/vocabulary-census/PROPOSED_VOCABULARY.md`:
- For each proposed type: **camelCase name + 1-2 paragraph narrative** of what it *is in the life of this system*, why this name, what code/docs/traffic it binds, what it deliberately excludes, where it touches dharma/telos/shakti/witness/loomwork themes.
- A second section: **open tensions** — things the swarm could not resolve, framed as discernment questions for John.
- A third section: **what we removed from Devin's 21 and why**, **what we added and why**.

## Output
- All four Pass 1 files, the Pass 2 debate, the Pass 3 PROPOSED_VOCABULARY.md land in a single PR on branch `perplexity-grounding/<ts>-vocabulary-census`.
- PR body summarizes the journey and points John to PROPOSED_VOCABULARY.md as the read-like-a-story entry point.
- Stage-1, evidence-only. John merges or sends back for another round.

## Constraints
- `api_credentials=["github"]` on all gh/git
- Never use scrape/crawl
- Never define agents, never amend doctrine
- This is John's voice on Layer 2. Earn the names.
