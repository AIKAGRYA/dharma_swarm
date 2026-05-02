# CANONICAL DOC STACK

**Date**: 2026-04-04
**Purpose**: Define the minimal root-adjacent file stack for repo integrity.

---

## Hierarchy (Read Order)

```
TIER 1 — MANDATORY FIRST-READ (agents MUST ingest before any action)
├── CLAUDE.md                          → Agent operating instructions (OWNER of: behavioral rules, architecture, build commands)
├── docs/governance/SOVEREIGN_MANIFEST.md → Repo ground truth (OWNER of: axioms, domain map, invariants, locks)
│
TIER 2 — DOMAIN REFERENCE (read when working in that domain)
├── docs/architecture/NAVIGATION.md    → Module-level map (OWNER of: which file does what, layer assignments)
├── docs/architecture/MODEL_ROUTING_CANON.md → Routing truth (OWNER of: provider selection, model hierarchy)
├── specs/DGC_TERMINAL_ARCHITECTURE_v1.1.md → Terminal protocol (OWNER of: Bun↔Python JSON stdio contract)
│
TIER 3 — FOUNDATIONAL (read for deep context, rarely changes)
├── foundations/INDEX.md               → 10-pillar intellectual genome entry point
├── specs/Dharma_Constitution_v0.md    → Constitutional rules
├── specs/KERNEL_CORE_SPEC.md          → Kernel immutability spec
│
TIER 4 — OPERATIONAL REFERENCE (read when operating the system)
├── README.md                          → Repo overview, quick-start
├── docs/governance/REPO_GOVERNANCE_AUDIT.md → Audit findings, contradictions, stale doc log
│
TIER 5 — ARCHIVE (do not read unless investigating history)
├── docs/archive/*                     → Correctly quarantined old docs
├── LIVING_LAYERS.md                   → Demote to archive (stale, overlaps NAVIGATION.md)
├── program.md                         → Demote to archive (overlaps README)
├── PRODUCT_SURFACE.md                 → Demote to archive or merge into SOVEREIGN_MANIFEST
```

---

## File Ownership Rules

| Kind of Truth | Canonical File | All Others Must Defer |
|---------------|---------------|----------------------|
| Agent behavior rules | `CLAUDE.md` | — |
| Repo axioms & domain map | `SOVEREIGN_MANIFEST.md` | — |
| Module-level what-does-what | `NAVIGATION.md` | — |
| Model/provider routing | `MODEL_ROUTING_CANON.md` | model_routing.py files must not contradict |
| Terminal protocol | `specs/DGC_TERMINAL_ARCHITECTURE_v1.1.md` | v1.0 is deprecated |
| Constitutional axioms | `specs/Dharma_Constitution_v0.md` | — |
| Kernel spec | `specs/KERNEL_CORE_SPEC.md` | — |
| Contradictions & staleness | `REPO_GOVERNANCE_AUDIT.md` | — |

---

## Memory Authorities

This section is the canonical map for memory-write authority. It does not
create a new memory system. It tells agents which existing surface owns each
kind of memory, which API they must use, and which bypasses are forbidden.

| # | Authority | Class | Owner Module | Write API | Callers MUST NOT |
|---|-----------|-------|--------------|-----------|------------------|
| 1 | Register/conscience marks | Write | `dharma_swarm/register_disciplines.py` | `make_register_mark()` + `write_register_mark()` | Append directly to `~/.dharma/stigmergy/register_marks.jsonl` |
| 2 | Runtime facts and edges | Write | `dharma_swarm/runtime_state.py::RuntimeStateStore` | `record_memory_fact()` + `record_memory_edge()` until the membrane facade lands | Execute SQL writes to `memory_facts` or `memory_edges` outside the store |
| 3 | Episodes/events | Write | `dharma_swarm/engine/event_memory.py::EventMemoryStore` | `ingest_envelope()` | Write runtime event JSONL or event SQL outside the store |
| 4 | Trusted semantic atoms | Write | `dharma_swarm/chetana/promote.py` | `promote()` with chetana provenance and gate check | Promote without `gate_check_atom()` or mutate trusted atoms in place |
| 5 | Context admission | Project | `dharma_swarm/memory_lattice.py` + `dharma_swarm/context_compiler.py` | `MemoryLattice.recall()` today; `MemoryLattice.compile_memory_context()` once the membrane slice lands | Hand-query underlying stores for prompt context unless doing an audit |
| 6 | Vector/graph/palace/dashboard views | Project | Downstream readers | Read-only projections over owner APIs | Claim upstream truth ownership or write canonical memory state |
| 7 | Distillers: drift, witness, causal, revive, decay, semantic bridge | Distill | Per-module producer | Emit `RegisterMark`s through authority 1 or staged atoms through authority 4 | Mutate trusted state directly |

### Required Patterns

- To record a new operational fact, construct a `MemoryFact` through the
  runtime memory path. After the admission facade lands, call
  `MemoryLattice.admit_memory_fact(...)` instead of calling
  `RuntimeStateStore.record_memory_fact(...)` directly.
- To record a session decision or runtime episode, use
  `MemoryLattice.ingest_runtime_envelope(...)` / `EventMemoryStore`, not a
  promoted semantic atom and not a bare `MemoryFact`.
- To record a conscience or repair signal, use
  `make_register_mark(...)` + `write_register_mark(...)`; never raw-append the
  canonical register log.
- To promote chetana knowledge, use `chetana.promote.promote(...)` so the
  frontmatter, gate result, provenance, and trusted-path write stay coupled.

### Membrane Migration Rule

`MemoryLattice` is the planned admission facade, not a parallel store. Existing
`record_fact()`, `promote_fact()`, `remember()`, and `recall()` calls remain
valid until the membrane APIs are added. New direct callers of
`RuntimeStateStore.record_memory_fact()` or `record_memory_edge()` outside
`memory_lattice.py` must be tagged `TODO(membrane)` with a reason and migrated
one minor version after the admission facade lands.

---

## Deprecation / Merge Decisions

### DEPRECATE (move to docs/archive/)
| File | Reason |
|------|--------|
| `LIVING_LAYERS.md` | Overlaps NAVIGATION.md, stale line counts, bloated frontmatter |
| `program.md` | Overlaps README.md |
| `PRODUCT_SURFACE.md` | Content belongs in SOVEREIGN_MANIFEST or README |
| `specs/DGC_TERMINAL_ARCHITECTURE.md` (v1.0) | Superseded by v1.1 |
| `specs/SOVEREIGN_BUILD_PHASE_MASTER_SPEC_2026-03-19.md` | Stale build plan |
| `specs/ONTOLOGY_PHASE2_*.md` | Stale migration spec |
| `docs/architecture/DHARMA_SWARM_THREE_PLANE_ARCHITECTURE_2026-03-16.md` | Pre-TUI, stale |
| `docs/architecture/JIKOKU_SAMAYA_*.md` (4 files) | Merge into 1 or archive |
| `docs/architecture/SWARMLENS_MASTER_SPEC.md` | Replaced by Bun TUI |

### RETAIN AND UPDATE
| File | Action Needed |
|------|--------------|
| `CLAUDE.md` | Fix stale numbers (514 modules, 8571 collected tests, swarm.py 3119 lines, 18 providers not 9). Add pointer to SOVEREIGN_MANIFEST.md. |
| `docs/architecture/NAVIGATION.md` | Fix stale numbers, add bridge/adapter/orchestrator maps |
| `docs/architecture/MODEL_ROUTING_CANON.md` | Acknowledge 3 routing files, define which is canonical |
| `README.md` | Strip excessive Codex frontmatter, keep concise |

### CREATED BY GOVERNANCE AUDIT (2026-04-04)
| File | Purpose | Status |
|------|---------|--------|
| `docs/governance/SOVEREIGN_MANIFEST.md` | Repo ground truth for all agents | **EXISTS** — rewritten with filesystem-verified numbers |
| `docs/governance/REPO_GOVERNANCE_AUDIT.md` | Audit findings and contradiction log | **EXISTS** — updated with re-audit corrections |
| `docs/governance/CANONICAL_DOC_STACK.md` | This file — doc hierarchy | **EXISTS** |

---

## Frontmatter Policy

The Codex (GPT-5) frontmatter injection added 80+ lines of YAML to every markdown file. Policy going forward:

1. **Root governance docs** (Tier 1-2): NO frontmatter. Plain markdown. Maximum clarity.
2. **Architecture docs** (Tier 2-3): Minimal frontmatter (title, date, status only — 5 lines max).
3. **Archive docs**: Leave existing frontmatter in place (it's archived, doesn't matter).
4. **New docs**: No frontmatter unless the doc is consumed by a machine-readable pipeline.

---

## Anti-Doc-Maze Rules

1. **Maximum governance docs at root or docs/governance/**: 5 files
2. **Maximum architecture docs**: 10 files (current: 20 — cut in half)
3. **Any new doc must identify which existing doc it replaces or subordinates to**
4. **No doc may claim "single source of truth" for something another doc also covers**
5. **Stale docs must be archived within 2 weeks of becoming stale**
