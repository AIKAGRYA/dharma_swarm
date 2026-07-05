# Karpathy LLM Wiki System Integration Plan

Status: implementation seed
Priority: HIGH
Created: 2026-07-05 JST
Scope: dharma_swarm, `~/.dharma/knowledge/wiki`, Memory Common, Chetana,
agent onboarding, repo-local decision memory, and cross-agent receipts.

## Mission

Make the Karpathy LLM Wiki pattern a required operating substrate for the whole
system: agents should read from it before serious work, write back durable
observations through governed promotion, metabolize stale or contradictory
material, and leave receipts that future agents can actually use.

The target is not "more notes." The target is a living, source-linked,
agent-readable wiki/brain layer that compounds across sessions and agents.

## Research Sweep

This sweep was done on 2026-07-05 JST against current web, arXiv, and GitHub
results. Treat fast-moving GitHub repos as design signals until inspected and
vetted before code import.

1. Karpathy original gist: the core pattern is still raw sources, maintained
   markdown wiki, and agent schema/instructions. The wiki should support ingest,
   query, lint, `index.md`, `log.md`, local search, graph view, images, git, and
   LLM maintenance. Source:
   https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
2. Trip2G LLM Wiki: the strongest concrete iteration is MCP-accessible wiki
   navigation, instruction pages exposed as methods, `_mcp_initialize.md`,
   index-first traversal, search/RAG-assisted section retrieval, and
   federation. Source: https://trip2g.com/en/user/llm_wiki
3. Equational Applications `expo-llm-wiki`: adds production-style retrieval
   mechanics: immutable versus mutable facts, facts/tasks/events, maintenance
   jobs, semantic plus keyword fallback, hybrid weighting, tier weights, ranker
   fallback policies, auto-librarian thresholds, and auto-heal thresholds.
   Source:
   https://raw.githubusercontent.com/equationalapplications/expo-llm-wiki/main/packages/core/README.md
4. Google Open Knowledge Format: useful interchange target. It keeps the format
   intentionally small: markdown files with YAML frontmatter, no central
   registry, no required tooling. Source:
   https://raw.githubusercontent.com/GoogleCloudPlatform/knowledge-catalog/main/okf/SPEC.md
5. ProjectBrain / BRAIN.md: a repo-local, git-native decision memory layer:
   `BRAIN.md`, pages, `compiled_truth`, append-only `timeline`, link lint, and
   atomic update-truth. It complements `README` and `AGENTS.md` by preserving
   rationale and decisions, not raw note dumps. Source: https://projectbrain.md/
6. MindMux: reinforces local-first project brain, markdown memory on disk,
   compiled truth/timeline, and model-agnostic task handoff. Source:
   https://mindmux.ai/
7. Code Wiki fork of the Karpathy gist: adapts the method to codebases with
   `repos.json`, `last_sha`, `ingest_scope`, structure fingerprints, git-diff
   refresh, and pages for domains/modules/files/runbooks. Source:
   https://gist.github.com/MihirModi1421/94b5c2299bf743c346590e322d709046
8. Infini Memory, arXiv 2606.10677: use topic-structured memory documents,
   short-term buffers, periodic consolidation, and iterative retrieval rather
   than one-shot vector lookup. Source: https://arxiv.org/abs/2606.10677
9. Vector RAG vs LLM-Compiled Wiki, arXiv 2605.18490: compiled wiki is stronger
   for connecting findings and citation checking; RAG is cheaper and stronger
   for single-fact retrieval. The system should use both, routed by task type.
   Source: https://arxiv.org/abs/2605.18490
10. Memory as Metabolism, arXiv 2604.12034: memory needs recurring operations:
    TRIAGE, DECAY, CONTEXTUALIZE, CONSOLIDATE, and AUDIT. It also needs
    anti-entrenchment behavior so minority hypotheses and contradictions are
    retained rather than overwritten. Source: https://arxiv.org/abs/2604.12034
11. Memori, arXiv 2603.19935: structured triples plus summaries can preserve
    long-term memory with much lower token cost. This maps cleanly to Chetana
    atoms, NAGA triples, and Memory Common retrieval packs. Source:
    https://arxiv.org/abs/2603.19935
12. Mesh Memory Protocol, arXiv 2604.19540: cross-agent memory should use
    field-level acceptance, source-trace lineage, role evaluation, and explicit
    remix operations. Source: https://arxiv.org/abs/2604.19540
13. GroupMemBench, arXiv 2605.14498: group memory is harder than individual
    memory. Speaker-grounded belief tracking, audience adaptation, and group
    dynamics matter; simple BM25 remains competitive. Source:
    https://arxiv.org/abs/2605.14498
14. GitHub ecosystem scan on 2026-07-05 JST: active implementations now include
    desktop apps, Codex/Claude/Gemini/OpenCode agent plugins, local Ollama
    variants, wiki compiler repos, and BRAIN.md tooling. The most important
    lesson is not any single repo; it is that the pattern is becoming an
    interoperable agent convention.

## Current Dharma Fit Score

Score for "firing exactly like the current Karpathy LLM Wiki methodology":
68/100.

Subscores:

- Retrieval projection health: 100/100. The latest local live gate passed with
  260/260 concepts indexed, 260/260 retrieved, and p95 latency under the gate.
- Wiki existence and volume: 90/100. The wiki exists and is large: local counts
  showed 11,892 markdown files under `~/.dharma/knowledge/wiki` and 260 trusted
  concept files.
- Governed write path: 78/100. Chetana promotion, gate checks, wiki log append,
  cross-update, and vector auto-ingest exist, but not every agent workflow is
  forced through the path.
- Agent utilization: 55/100. `make onboard` mentions wiki and memory, and
  Memory Common exists, but the advertised `wiki show/search` command is not
  installed in PATH on this machine. Agents can use `dgc memory common`, but the
  richer read/write/metabolism receipt is not a hard session contract.
- Metabolism and freshness: 52/100. `dgc memory metabolize` and a cron handler
  exist, but current logs indicate old wiki maintenance state and stale cron
  evidence. The system has the organ; it is not yet guaranteed to pulse daily.
- Latest-method alignment: 48/100. The system does not yet have repo-local
  `BRAIN.md` compiled truth/timeline, `_mcp_initialize.md`, section-level wiki
  expansion, explicit anti-entrenchment audits, OKF export/import, group-memory
  speaker tracking, or field-level mesh acceptance as standard.

Interpretation: the retrieval engine is green; the total Karpathy-method
operating loop is only partially enforced.

## Design Laws To Adopt

1. Raw sources are immutable. Wiki synthesis is mutable only through governed
   promotion.
2. Vector memory is a projection, never authority.
3. Every nontrivial agent run begins with Memory Common plus exact owner-file
   reads when owner files are known.
4. Retrieval is mode-routed: index-first for curated concepts, section-level
   expansion for large wiki pages, keyword/BM25 for exact terms, vector for
   semantic recall, and graph traversal for relations.
5. Every durable output should either cite existing memory or leave a candidate
   writeback receipt.
6. Decision-grade truth is separate from raw evidence. Use a repo-local brain
   layer for current decisions and rationale.
7. Contradictions and dead ends are first-class memory objects, not cleanup
   trash.
8. Multi-agent memory requires lineage, source refs, role of the writer, and
   field-level acceptance.
9. Scheduled metabolism is a gateable system function: triage, decay,
   contextualize, consolidate, audit.
10. Agent instructions must name working commands only. If `wiki` CLI is absent,
    the contract must use `dgc memory ...` or install/provide a real `wiki`
    alias.

## Target Architecture

### Canonical Layers

- Raw layer: source receipts, transcripts supplied by the operator, URLs,
  artifacts, task logs, and external citations.
- Staging layer: Chetana staged atoms, Idea Spark candidates, task receipts, and
  contradiction/dead-end candidates.
- Trusted wiki layer: `~/.dharma/knowledge/wiki/concepts/*.md`, promoted only
  through Chetana or an equivalent governed path.
- Projection layer: vector DB, retrieval sidecars, semantic aliases, search
  indexes, and graph views.
- Repo brain layer: root `BRAIN.md` plus `docs/brain/` pages containing
  `compiled_truth`, `timeline`, decisions, rationale, and links back to trusted
  wiki/source receipts.
- Agent contract layer: `AGENTS.md`, onboarding, context packets, and Memory
  Common packs.

### Required New/Upgraded Artifacts

- `BRAIN.md`: repo-local entrypoint for decision-grade project memory.
- `docs/brain/index.md`: map of current compiled truths, active decisions, and
  timeline pages.
- `docs/brain/timeline.md`: append-only decision/event timeline.
- `~/.dharma/knowledge/wiki/_mcp_initialize.md`: session initialization page for
  wiki-aware agents.
- `~/.dharma/knowledge/wiki/AGENTS.md`: wiki-local instructions, retrieval
  modes, writeback rules, and lint expectations.
- `~/.dharma/knowledge/wiki/SCHEMA.md`: frontmatter, relation, source, dead-end,
  contradiction, and OKF compatibility schema.
- `reports/memory_kernel/wiki_metabolism/*.json`: daily metabolism receipts.
- `reports/memory_kernel/wiki_eval/*.json`: recurring evals for single-fact,
  synthesis, citation, contradiction, dead-end, and group-memory cases.

## Implementation Ladder

### P0: Make The Contract Honest

- Replace onboarding references to missing `wiki show/search` with working
  commands or implement `dgc wiki search/show` aliases.
- Update `tests/test_agent_onboard.py` to require the truthful command surface.
- Add a "Karpathy Wiki Contract" section to `docs/ops/MEMORY_COMMON.md`.
- Definition of done: `make onboard` names only executable local commands, and
  tests fail if it regresses.

### P1: Seed Repo-Local Brain

- Add root `BRAIN.md` pointing to `docs/brain/index.md`.
- Add `docs/brain/index.md` with `compiled_truth` and "open contradictions."
- Add `docs/brain/timeline.md` as append-only event history.
- Add a small link lint check for wiki links in `docs/brain/**`.
- Definition of done: agents have one repo-local decision memory entrypoint
  separate from raw reports and projections.

### P2: Enforce Agent Read Path

- Extend `render_agent_memory_pack()` so Memory Common packs include:
  accepted source ids, weak/empty result warning, required owner-file reads,
  dead-end query field, and writeback expectation.
- Add a preflight check that nontrivial agent closeouts include either
  `memory_sources_used` or `memory_not_used_reason`.
- Definition of done: agent closeout receipts can prove whether memory was used.

### P3: Govern Writeback Everywhere

- Standardize a writeback receipt schema:
  `task`, `source_refs`, `memory_queries`, `accepted_context`,
  `rejected_context`, `durable_observations`, `contradictions`,
  `dead_ends`, `candidate_atom_path`, `promotion_status`.
- Add a helper command that stages a durable observation into Chetana instead
  of letting agents paste into trusted wiki files.
- Definition of done: durable observations have a staged atom or a recorded
  "not durable" reason.

### P4: Add Section-Level And Hybrid Retrieval

- Add section IDs to wiki concept ingestion metadata.
- Support `dgc memory query --section-expand` or equivalent section expansion.
- Preserve keyword/BM25 fallback alongside vector retrieval; do not replace it.
- Add task-type routing: single-fact, synthesis, citation, relation, group
  memory, and contradiction.
- Definition of done: retrieval can return a page section with source digest,
  heading path, and backlink context.

### P5: Metabolism As A Scheduled Gate

- Restore/verify daily `dgc memory metabolize` scheduling.
- Split metabolism receipts into TRIAGE, DECAY, CONTEXTUALIZE, CONSOLIDATE,
  AUDIT.
- Add orphan, stale, contradiction, and dead-end queues.
- Add anti-entrenchment audit: no disputed claim is deleted or overwritten
  until a receipt records the competing evidence.
- Definition of done: a failing metabolism gate is visible in onboard/status.

### P6: OKF And Federation

- Add OKF-compatible frontmatter aliases for trusted wiki concepts.
- Add export/import smoke tests for a small OKF bundle.
- Add MCP/federated read endpoint only after the local contract is stable.
- Definition of done: the wiki can share a bounded, source-linked bundle with
  another agent without losing provenance.

### P7: Mesh Memory For Multi-Agent Work

- Add a cross-agent memory envelope with:
  writer role, source lineage, field-level acceptance, reviewer role,
  remix/source refs, audience, and confidence.
- Require semantic receipts from model councils and A2A agents to cite accepted
  fields instead of accepting whole blobs.
- Add group-memory evals for speaker-grounded beliefs and audience-specific
  summaries.
- Definition of done: council/agent memory can be merged field by field.

### P8: Continuous Evaluation

- Add a small recurring eval suite:
  single-fact lookup, synthesis across pages, citation verification,
  contradiction recovery, dead-end avoidance, group-memory recall, and token
  cost.
- Score wiki, keyword, vector, and hybrid modes separately.
- Definition of done: the system reports both projection health and methodology
  health; a 100/100 vector gate can no longer hide weak agent utilization.

## Enforcement Hooks

Add or wire these hooks incrementally:

- `make wiki-gate`: run wiki live gate plus section retrieval smoke.
- `make memory-metabolize`: run `dgc memory metabolize`.
- `make wiki-orphan-status`: render total atoms, orphan count, semantic-density
  coverage, missing source/status/PARA counts, and sample orphan slugs.
- `make wiki-orphan-upgrade`: enrich orphan atoms with stronger YAML,
  source-hardening status, cross-pollination targets, ideation seeds, and an
  inbound MOC anchor; regenerate the wiki index; re-ingest concepts; run the
  live vector gate.
- `make brain-lint`: validate `BRAIN.md`, `docs/brain/**`, and wiki links.
- `make agent-memory-contract`: validate closeout receipts for memory fields.
- `make karpathy-wiki-ci`: aggregate wiki gate, brain lint, onboarding truth,
  orphan absence, writeback schema, and metabolism smoke.

CI policy:

- PRs touching `dharma_swarm/memory*`, `dharma_swarm/wiki*`,
  `dharma_swarm/chetana/**`, `scripts/governance/agent_onboard.py`,
  `docs/ops/MEMORY_COMMON.md`, or `docs/brain/**` must run
  `make karpathy-wiki-ci`.
- PRs claiming memory improvements must include a receipt with external source
  refs, local files changed, verification command, and whether a durable wiki
  atom was staged.
- Onboarding must fail tests if it advertises a command that is not implemented
  or installed by repo setup.

Runtime policy:

- Every long-running agent lane starts with `dgc memory common "<task>"`.
- Every long-running agent lane ends with a memory closeout field.
- Chetana promotion triggers vector ingest and wiki log append.
- Daily cron runs metabolism and writes a receipt.
- Weekly audit checks stale pages, orphan pages, contradictions, dead ends, and
  group-memory drift.

Orphan rule:

- An atom with zero inbound backlinks is not culturally adopted, even if it is
  beautifully written.
- Orphan recovery is not cosmetic tagging. The recovery pass must create real
  graph edges through MOC anchors and must attach source quality, review status,
  cross-pollination targets, and ideation prompts.
- `make karpathy-wiki-ci` treats orphan count as a hard local contract. Legacy
  schema debt may remain visible, but newly isolated atoms should not silently
  accumulate.

## Agent Seed Packet

Use this packet in agent prompts, onboarding, and Memory Common output after P0
truthfulness is fixed:

```text
Before nontrivial work:
1. Run `dgc memory common "<task>"`.
2. Read exact owner files when known; retrieval is not authority.
3. Use index-first wiki navigation for curated concepts.
4. Use keyword plus vector search for broad recall.
5. Record weak hits, failed queries, contradictions, and dead ends.

After work:
1. List memory sources used, accepted, and rejected.
2. If there is a durable observation, stage it through Chetana or record why not.
3. If a decision changed, update the repo brain compiled truth and append the
   timeline entry.
4. Run the narrowest relevant memory/wiki gate.
5. Leave a receipt with source refs and verification.
```

## First Build Slice

The highest-leverage first slice is:

1. Fix onboarding truth around `wiki show/search`.
2. Add the repo brain skeleton.
3. Add memory closeout fields to agent receipts.
4. Add a `karpathy-wiki-ci` aggregate target.
5. Restore/verify scheduled `dgc memory metabolize`.

That slice converts the current state from "healthy retrieval projection" into
"agents are forced to use and improve the wiki method."

## Follow-On Commercial And RSI Deep Dive

The high-priority follow-on plan for turning this substrate into a revenue
engine and self-evolution tool lives at:

`docs/research/2026-07-05-karpathy-wiki-obsidian-mcp-rsi-money-engine.md`.

Its core decision is to sell verified evidence work first, keep Obsidian as the
operator cockpit, expose Obsidian MCP only through a Dharma/NAGA policy broker,
and feed RSI through staged experiment receipts, contradiction queues, and
dead-end ledgers.
