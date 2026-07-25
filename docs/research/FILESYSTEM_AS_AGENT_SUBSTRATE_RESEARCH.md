# Filesystem-as-Agent-Substrate — Research Dossier (the "Four Powers")

**Status:** Research dossier (Phase 0 — no build code). **Date:** 2026-06-24.
**Branch:** `claude/file-system-org-gjt-g819q0`.
**Theme:** Treating the filesystem (directories, markdown, paths) not as dumb storage
but as the substrate an agent *thinks in and through* — as orchestration, as context
boundary, as knowledge graph, as memory.

This file is the "single location" for the four sources the operator asked to
consolidate. It exists because the previously-prototyped "file system organization
program" on this branch was never committed — the branch is an empty pointer to
`main` — so the work is reconstructed here from primary sources, then mapped onto
the swarm's existing surfaces with a concrete implementation proposal.

> Doctrine line this dossier respects (same as the reconciliation/truth-graph lanes):
> **Read models project truth from owners; they do not become authority.** A
> filesystem-native layer must *project* from and *converge on* the existing owners
> (MemoryKernel, the spine, the orchestrator), not mint a new truth store.

---

## The four powers at a glance

| # | Power | Source | One-line essence | Layer it owns |
|---|-------|--------|------------------|---------------|
| 1 | **LSFS** — LLM-based Semantic File System | arXiv 2410.11843 (ICLR 2025), Shi/Mei/Zhang et al. | Semantic syscalls + vector index over files; manage files by natural-language prompt | **Query / retrieval** |
| 2 | **LlamaFS** — self-organizing file system | `iyaja/llama-fs` (2024) | A daemon that watches a dir and auto-renames/reorganizes by content; smart incremental cache | **Self-organization / write** |
| 3 | **ICM / MWP** — Interpretable Context Methodology, Model Workspace Protocol | arXiv 2603.16021 (Mar 2026), Jake Van Clief | Numbered folders = pipeline stages; `CONTEXT.md` = per-stage contract; folders = token firewalls | **Orchestration / context-scoping** |
| 4 | **OKF** — Open Knowledge Format | Google Cloud, v0.1 (2026-06-12) | A directory of markdown concept-files with YAML `type`; links form a graph; `index.md`/`log.md` reserved | **Portable knowledge interchange** |

The through-line: **the directory tree becomes the program.** Sequencing is folder
numbering; scoping is folder hierarchy; state is files on disk; knowledge is a
markdown graph; coordination is one folder's output being the next folder's input.

---

## Power 1 — LSFS: LLM-based Semantic File System

**Source:** *From Commands to Prompts: LLM-based Semantic File System for AIOS*,
arXiv [2410.11843](https://arxiv.org/abs/2410.11843), ICLR 2025. Authors: Zeru Shi,
Kai Mei, Mingyu Jin, Yongye Su, Chaoji Zuo, Wenyue Hua, Wujiang Xu, Yujie Ren,
Zirui Liu, Mengnan Du, Dong Deng, Yongfeng Zhang.

**Problem.** Traditional filesystems force precise commands and exact paths/names.
Existing LLM-file work is app-level and agent-specific; there is no general semantic
substrate other agents can reuse.

**Design.** LSFS is *an additional layer on top of the traditional filesystem* that
builds a **semantic index** (embedding vectors in a vector DB) over file contents.
Two tiers of **semantic syscalls**:

- **Atomic syscalls:** `create_or_get_file()`, `add_()`, `overwrite()`, `del_()`,
  `keywords_retrieve()`, `semantic_retrieve()`.
- **Composite syscalls:** `lock_file()`, `group_semantic()`, `integrated_retrieve()`,
  `file_join()`.
- **Higher-level APIs** on top: Retrieve-Summary, Change-Summary, Rollback, Link
  (summarization, version restore, secure sharing).

**NL → parameters.** An **LSFS Parser** uses an LLM to extract parameters from the
user prompt, emits them comma-separated, and a regex maps them straight into syscall
arguments.

**Supervisor.** A background module periodically scans directories, detects disk
changes, and syncs them into the LSFS via syscalls (with process locking + status
change reports) — keeping the semantic index live.

**Results.** Parser ~90% accuracy overall (Change-Summary/Link up to 100%; Rollback/
Retrieve-Summary ~85%). Semantic retrieval *beats LLM-only as file counts grow*
(avoids context-length blowups). 100% link-generation success for sharing.

**What it gives the swarm:** the *read/query* discipline — never dump a whole corpus
into context; retrieve semantically and bounded.

---

## Power 2 — LlamaFS: self-organizing file system

**Source:** `iyaja/llama-fs` ([GitHub](https://github.com/iyaja/llama-fs)), 2024
(hackathon project, not an arXiv paper).

**Two modes.**
- **Batch:** point it at a messy directory → it returns a *proposed* reorganized tree
  with interpretable names, for human approval before anything is moved.
- **Watch (daemon):** monitors a directory, intercepts FS operations, and *learns
  naming patterns from your edits* — e.g. once you make a `tax/` folder and move docs
  in, it continues the pattern for new files.

**Mechanism.** Uses Llama 3 to summarize file content and infer folder hierarchy +
names, applying well-known conventions (e.g. time). **Smart caching** selectively
rewrites only the sections of the index touched by the *minimum necessary filesystem
diff* → sub-500ms ops in watch mode.

**Multimodal.** Images via **Moondream**, audio via **Whisper**.
**Privacy.** "Incognito mode" routes through local **Ollama** instead of cloud.

**What it gives the swarm:** the *self-organization* discipline — propose-then-apply,
learn-from-edits, incremental re-index, human-in-the-loop before mutation.

---

## Power 3 — ICM / MWP: Folder Structure as Agentic Architecture (Van Clief)

**Source:** *Interpretable Context Methodology: Folder Structure as Agentic
Architecture*, arXiv [2603.16021](https://arxiv.org/abs/2603.16021) (Mar 2026),
Jake Van Clief. Reference impl: `RinDig/Interpreted-Context-Methdology`.

**Thesis.** *"If the prompts and context for each stage of a workflow already exist
as files in a well-organized folder hierarchy, you do not need multiple agents or a
coordination framework."* The filesystem **is** the orchestrator.

**Numbered folders = stages.**
```
workspace/
  stages/
    01-research/
    02-script/
    03-production/
```
Sequential by numeric order; one folder's `output/` is the next folder's input.

**`CONTEXT.md` = stage contract** with three mandatory parts:
- **Inputs table:** `| Source | File/Location | Section/Scope | Why |` — explicit,
  *section-level* loading (not whole files).
- **Process:** numbered steps the agent executes.
- **Outputs table:** artifacts produced, location, format. *"Every output is an edit
  surface"* — a human can edit any stage's output before proceeding.

**Five-layer context hierarchy** (load in order, stop when satisfied):

| Layer | File | Purpose | Scope |
|-------|------|---------|-------|
| 0 | `CLAUDE.md` | System orientation | ~800 tok, always |
| 1 | `CONTEXT.md` (workspace) | Task routing | ~300 tok |
| 2 | Stage `CONTEXT.md` | Stage instructions | ~200–500 tok |
| 3 | Reference material | Conventions/voice/design — *internalized as constraints* | configured once, stable |
| 4 | Working artifacts | Prior outputs, user input — *processed as input* | changes per run |

The L3/L4 distinction is load-bearing: L3 is "write *like this*"; L4 is "transform
*this*."

**Folders as token firewalls.** The agent only accesses files listed in its stage's
Inputs table — never the whole workspace. Per-stage context stays ~2k–8k tokens
(where models perform best) vs 30k–50k monolithic blobs where models lose the thread.
Structure: `references/` (L3), `output/` (L4), `_config/` (workspace constants),
`shared/`, `skills/`.

**LLM vs deterministic split.** The LLM does creative work inside the Process; local
scripts do file I/O, folder sequencing, variable substitution, checkpoint pause/
resume. *The agent never manages pipeline state — the numbered folders do.*

**Emergent property:** observable-by-default. Every intermediate is a plain file, so
debugging = reading the markdown; no logging infra needed. And portable: a workspace
is a folder — copy/zip/git/sync it anywhere.

**What it gives the swarm:** the *orchestration + context-scoping* discipline — make
the pipeline and its token boundaries legible as on-disk structure.

---

## Power 4 — OKF: Open Knowledge Format (Google)

**Source:** Google Cloud, **Open Knowledge Format v0.1**, published **2026-06-12**.
Spec: `GoogleCloudPlatform/knowledge-catalog/okf/SPEC.md`. This is the recent (June
2026) Google work on the same theme — the closest cousin to Van Clief's ICM.

**Bundle = directory tree of markdown files.** Directory structure is independent of
domain. Distributable as a git repo, tarball, or subdir. **Each file is one concept;
its path is its identifier.**

**Frontmatter.** Each file opens with a YAML block. **The single required field is
`type`** — "a short string identifying the kind of concept" (e.g. `BigQuery Table`,
`API Endpoint`, `Metric`). Types are **not** centrally registered; consumers **must
tolerate unknown types gracefully.** Recommended optional: `title`, `description`,
`resource` (canonical URI), `tags` (list), `timestamp` (ISO 8601).

**Two reserved filenames** (at any directory level):
- **`index.md`** — progressive-disclosure listing of the directory (no frontmatter;
  sections with relative links + descriptions).
- **`log.md`** — change history, ISO-8601 date headings newest-first, prose entries
  marked `**Update**` / `**Creation**`.

**Links form a graph.** Concepts cross-reference via ordinary markdown links —
absolute (bundle-relative, `/tables/customers.md`) or relative (`./other.md`). Links
assert *untyped* relationships; the *kind* is conveyed by surrounding prose, not the
link. Consumers must tolerate broken links → directory is a **graph, not a flat list.**

**Producer/consumer separation (enforced).** Producers author/generate bundles;
consumers read/traverse. A consumer **MUST NOT reject** a bundle for missing optional
fields, unknown `type` values, or broken links. Versioned `<major>.<minor>`;
`okf_version: "0.1"` declared in root `index.md`.

**What it gives the swarm:** the *interchange* discipline — a portable, vendor-neutral
on-disk format to **export/import** the knowledge graph other agents (and other
orgs) can consume without bespoke adapters.

---

## The convergent thesis

All four say the same thing from four sides:

- **LSFS:** *read* the filesystem semantically (don't grep, retrieve).
- **LlamaFS:** *organize* the filesystem by meaning (propose, learn, apply).
- **ICM/MWP:** *orchestrate* through the filesystem (folders = stages + token walls).
- **OKF:** *interchange* the filesystem as a knowledge graph (markdown + `type` + links).

Put together they describe a **filesystem-native agent substrate**: directories are
boundaries, markdown is the universal interface, paths are identifiers, and the tree
is simultaneously the program, the memory, and the knowledge graph.

---

## How this serves the organism (the non-myopic tie — read before building)

This dossier sits one inch from a named anti-pattern. `foundations/THE_ORGANISM.md`
warns: *"Inward motion with no telos and no contact (recursion-for-its-own-sake,
narration outrunning build, **papers about our own architecture**) is still the
anti-pattern."* A "research dossier about a filesystem-context-substrate" **is** a
paper about our own architecture unless it compounds into capability that reaches the
world. So the tie below is not decoration — it is the licence for this work to exist.

**1 — It is a Tier-1 substrate power, not a feature.** `NORTH_STAR.md` §4 names a
three-tier metabolism; Tier 1 is *"Substrate guides… the most powerful, evolving
toolset we can manage — fuels, organizes, and guides everything else. Top tier
because it is the organizer, not the point."* Filesystem-as-substrate is exactly an
**organizer**: the tree through which every organ reads and writes. It serves the
`substrate-nativeness` spine objective directly, and only that.

**2 — It realizes self-organs the vision already declares.** `THE_ORGANISM.md` genome
③ lists, verbatim, the organs this work *is*:
- **self-onboarding** ("fresh agent coherent on first token — the cure for 'every new
  instance is confused'") → ICM's `CLAUDE.md → CONTEXT.md` layered load is
  self-onboarding rendered as on-disk structure.
- **self-ontology-maintenance** ("one shared world-model all organs read/write") →
  OKF is that world-model made portable: a markdown graph any organ (or external
  human/agent) can consume.
- **self-memory-curation** (chetana decay/revive) → LlamaFS's propose-then-apply
  organizer is curation with a gate.

**3 — It is categorical systems theory made physical (the deepest tie).** Genome ①
names *"categorical systems theory — objects+morphisms so parts compose with provable
interfaces… self-rewire without losing coherence."* ICM's `CONTEXT.md` Inputs/Outputs
tables **are morphism declarations** — typed interfaces between stages. OKF's required
`type` field + links **are objects + morphisms**. A filesystem-native substrate gives
the organism *compositional interfaces it can read, audit, and rewrite without losing
coherence.* This is the abstract pillar grounded in something you can `ls`.

**4 — It is the portable face of the truth graph (sibling track tie).** The
`truth-graph-platform-2026-06` track is building *"a single truth graph that every
agent reads."* OKF is the **portable serialization** of that graph — and an ingest
path for external bundles. This track *complements* truth-graph-platform (it does not
duplicate it): truth-graph owns the in-repo projection; this owns the on-disk
interchange format and the per-stage contract reader.

**5 — It feeds Arjuna, which is what licenses it.** The outward hook (the cure for the
anti-pattern) is OKF interchange: a vendor-neutral, portable knowledge format makes
the swarm's knowledge **leave the house** — readable by external humans and other
agent systems. That is `NORTH_STAR.md` §6 (noosphere propagation, "an organized,
lawful, global way") and §8 trust-gate item 1 (*"a pointed audit agent reports… deep
understanding of how everything flows"* — a legible filesystem substrate makes that
flow auditable by default, per ICM's "observable-by-default" property).

**The doctrine line this track inherits** (from reconciliation + truth-graph):
*Read models project truth from owners; they do not become authority.* Every slice
below projects from / converges on existing owners (MemoryKernel, the spine, the
orchestrator). None mints a new truth store.

---

## Mapping onto dharma_swarm's existing substrate

The strongest finding of this research: **dharma_swarm has already independently grown
most of this.** A filesystem-native layer is mostly *naming, formalizing, and wiring
together* what exists — not new machinery. Concrete owners (verified by code survey):

### Already-present analogues

| Power's idea | Already in the swarm | File / API |
|---|---|---|
| ICM five-layer context hierarchy | `ContextCompiler.compile_bundle()` allocates a **token budget across 13 weighted sections** (governance 9%, operator-intent 10%, task-state 10%, memory-kernel 12%, …) | `dharma_swarm/context_compiler.py`; `ContextBundleRecord` in `runtime_state.py` |
| ICM Layer-0 `CLAUDE.md` orientation | Literally `CLAUDE.md` + `make onboard` (`agent_onboard.py`) | repo root; `scripts/governance/agent_onboard.py` |
| ICM tiered freshness load | `context_agent.py` already loads **11 tiers** of context by freshness | `dharma_swarm/context_agent.py` |
| OKF markdown-concept + YAML `type` | Agent roles are **already markdown files with YAML frontmatter** (`name`, `model`, `provider`, `tags`, `keywords`, `context_weights`) | `dharma_swarm/skills/*.skill.md` |
| OKF/LSFS semantic graph + retrieval | **MemoryKernel** front door + surface registry + read-only adapters; vector + temporal-graph surfaces; `semantic_retrieve`-style query | `holon/memory_kernel/__init__.py`; `memory_kernel/surface_specs_core.py`, `adapters/read_only.py` |
| ICM token firewall / bounded context | `MemoryContextBudget` (`max_admitted_atoms`, `max_total_chars`, per-atom truncation, fail-closed admission) | `memory_kernel/context_admission.py` |
| ICM numbered-stage pipeline | `Orchestrator` `TopologyType.PIPELINE` + **`Task.depends_on` DAG** enforced by TaskBoard; `skill_composer.CompositionPlan` topological waves | `orchestrator.py`, `task_board.py`, `models.py`, `skill_composer.py` |
| ICM "output is next stage's input" handoff | **Typed `Artifact` + `Handoff`** with lineage chains | `handoff.py` (`HandoffProtocol.create_handoff`, `handoff_chain`, `build_context_from_handoffs`) |
| OKF `log.md` change history | Append-only JSONL receipt/witness logs; `EvidenceReceipt` per dispatch | `spine/receipt.py`, `~/.dharma/witness/` |
| LlamaFS supervisor/watch | `context_agent` freshness scanner; existing daemons | `context_agent.py` |
| Canonical dispatch + receipt | `spine.invoke_agent()` → one `EvidenceReceipt` | `spine/invoke.py`, `spine/receipt.py` |

### The gaps (what is genuinely missing)

1. **No per-directory `CONTEXT.md` stage contract.** The swarm has a global
   `CLAUDE.md` and per-role `*.skill.md`, but no *per-stage* contract declaring
   `inputs / process / outputs` that an orchestrator reads to drive a pipeline.
2. **No on-disk workspace → swarm pipeline loader.** Pipelines are expressed in code
   (topology flags, `depends_on`), not as a legible numbered-folder workspace a human
   can read/edit/zip.
3. **No OKF export/import.** The MemoryKernel graph cannot yet be projected to a
   portable OKF bundle (or ingested from one).
4. **No self-organizing propose-then-apply pass** (LlamaFS-style) over repo docs or
   `~/.dharma/` notes.

---

## Implementation proposal (for discussion — not yet built)

**Shape:** a new track, *Filesystem-Native Context Substrate*, serving the
`substrate-nativeness` spine objective. It **converges on existing owners** and mints
no new truth store. Read-models project; the spine stays the dispatch path.

Four slices, ordered by leverage-to-risk (each independently shippable):

### Slice A — `CONTEXT.md` stage-contract reader (ICM/MWP) — *highest leverage*
A read-only parser `stage_contracts.py` that reads a numbered-folder workspace
(`stages/01-*/CONTEXT.md`) and emits the existing data structures:
- Inputs/Process/Outputs tables → `Task` objects with `Task.depends_on` edges and
  `Task.metadata["stage_contract_sha256"]`.
- Hand the tasks to the **existing** `Orchestrator` (PIPELINE) + `TaskBoard` DAG; each
  stage dispatches through **`spine.invoke_agent()`** → one `EvidenceReceipt`.
- Stage `output/` → `HandoffProtocol` artifact → next stage's input.
- Bounded context per stage via the Inputs table → `MemoryContextBudget`.
No new orchestrator, no new receipt type. ~1 module + parser + tests.

### Slice B — OKF projector (export/import) — *highest interchange value*
- **Export:** project a MemoryKernel surface (or `skills/`) to an OKF bundle — one
  markdown file per concept, YAML `type` required, `index.md` + `log.md` generated,
  cross-links from existing edges. Pure read-model; reuses the surface registry.
- **Import:** ingest an OKF bundle as a read-only MemoryKernel surface
  (`home.okf_imported`) via a new adapter — *tolerant consumer* per spec (never reject
  on unknown `type`/broken link).
- This makes the swarm's knowledge portable and lets it consume Google-OKF bundles.

### Slice C — Semantic query surface (LSFS) — *converges, doesn't add*
Formalize a small, bounded LSFS-style query API over the **existing** vector/graph
surfaces through the MemoryKernel front door (`semantic_retrieve`, `group_semantic`,
`integrated_retrieve` as thin facades). No new vector DB; wrap what exists. NL→params
parsing optional and gated.

### Slice D — Self-organizing propose-then-apply (LlamaFS) — *last, most caution*
A **batch, dry-run-first** pass that proposes a reorg/renaming of a target dir
(repo `docs/` or `~/.dharma/` notes) and writes a *proposal*, never mutating until
operator approval (mirrors LlamaFS batch + the swarm's telos-gate ethos). Watch-mode
deferred. Writes go through `MemoryWritePolicy` (ALLOW/WARN/DENY), never raw.

### Non-goals (hard boundaries)
- Do **not** create a new daemon, database, vector store, event log, or truth store.
- Do **not** mint a second receipt type; project over `EvidenceReceipt`.
- Do **not** mutate files without a dry-run proposal + operator approval (Slice D).
- Do **not** broadly refactor `orchestrator.py`, `agent_runner.py`, or `swarm.py`;
  plug in at `dispatch_next()` / TaskBoard, honoring spine-adoption's surfaces.
- Do **not** touch `operator_core/**` or `runtime_state.py` ownership boundaries.

### Recommended first build
**Slice A** (the ICM `CONTEXT.md` reader). It is the highest-leverage, lowest-risk
slice: it is pure read + reuse of the orchestrator/TaskBoard/spine/handoff that
already exist, it makes the swarm's pipelines legible-and-portable on disk, and it
directly serves substrate-nativeness (more dispatch flowing through `invoke_agent`).

---

## Sources

- LSFS — *From Commands to Prompts: LLM-based Semantic File System for AIOS*,
  arXiv 2410.11843 (ICLR 2025): https://arxiv.org/abs/2410.11843
- LlamaFS — `iyaja/llama-fs`: https://github.com/iyaja/llama-fs
- ICM / MWP — *Interpretable Context Methodology: Folder Structure as Agentic
  Architecture*, Jake Van Clief, arXiv 2603.16021: https://arxiv.org/abs/2603.16021
  (reference impl: https://github.com/RinDig/Interpreted-Context-Methdology)
- OKF — Google Cloud, Open Knowledge Format v0.1 (2026-06-12), spec:
  https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md ;
  blog: https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing

> **Provenance note:** the four powers above were reconstructed from primary sources
> on 2026-06-24 after confirming the prior on-branch prototype was never committed.
> The swarm-surface mappings were verified against the live codebase (context_compiler,
> memory_kernel, orchestrator, spine, handoff) on the same date.
