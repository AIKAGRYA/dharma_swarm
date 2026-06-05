# Modularity & Future-Proofing Audit — Dharma Swarm v1

**Date:** 2026-05-30
**Author:** Devin (external worker, evidence-only authority)
**Branch:** `devin/2026-05-30-proof-artifact-pivot`
**Scope:** Full-power audit of repo modularity, future-proofing for increasing model capacity & multi-agent infra, identification of robust substrate vs. drift surfaces, concrete hardening PR slate.
**Operator concern (verbatim):** "I just want to ensure that we are robust, future proof, solidly modular, innovative and planning for models with increasing capacity, multiple agent infrastructure and it is not just a Python spaghetti plate."

---

## 0. Executive Summary

**The good news:** The substrate that makes this system real — the receipts protocol, evaluation kernel, manifest-driven control plane, and Go infrastructure bridge — already exists and is well-shaped. You are *not* sitting on a spaghetti plate. You are sitting on **a clean kernel surrounded by accumulated concept-debt and structural sprawl**, three pivots' worth.

**The honest news:** The structural risk is real but it's not what the polyglot proposal named. Language is not the problem. The problems are:

1. **Duplicate truth surfaces** — `EvidenceReceipt` is defined twice; the "Runtime Truth Spine" is imported by no production code; 3 different "spine" packages exist with overlapping vocabulary.
2. **Flat-top package structure** — 388 `.py` files / 210k LOC sit as siblings at `dharma_swarm/*` root, including six god-modules >2,500 LOC each.
3. **No machine-checked API contract** with the 74k-LOC TypeScript dashboard.
4. **Storage fragmentation** — 526 JSONL writes + 56 SQLite + 159 raw JSON + 119 paths under `~/.dharma/`, no schema versioning system.
5. **Concept proliferation** — 57 `Agent*` classes, 9 ontology modules, 3 "spine" packages, multiple substrate/kernel surfaces.

**The shape of this report:** This is the actual answer to "how do we plan for increasing model capacity, multi-agent infrastructure, and not become spaghetti." None of the proposed hardening requires Rust, Lean, Go expansion, or any new language. All of it is Python discipline at the boundaries.

---

## 1. What's Already Good (Protect This)

These are the surfaces that already exemplify the discipline the operator is asking for. They are the substrate. Do not touch them except to strengthen.

### 1.1 The type kernel: `dharma_swarm/models.py`

396 LOC, 29 Pydantic models, **zero internal dependencies** (only stdlib + Pydantic). Imported by 249 sites across the codebase. This is the de facto type kernel and it has the right shape: pure types, no logic, no I/O, no escape hatches.

### 1.2 The evaluation kernel: `dharma_swarm/auto_grade/`

433 LOC across 9 files, each <120 LOC. Clean separation: `engine.py` (orchestration), `models.py` (types), `rubrics.py` (config), per-metric modules (`citations`, `coverage`, `contradictions`, `efficiency`, `grounding`). This is the model of how every subsystem in this repo should be shaped.

### 1.3 The benchmarks substrate: `benchmarks/gauntlet.py`

787 LOC, 5-tier adversarial pressure architecture, structured `TaskScore` / `GauntletReport` types. The substrate that powers Layer 2 (TGSM-Eval).

### 1.4 The Go infrastructure bridge: `tools/*_go/` + `operator_core/go_*_bridge.py`

The Go layer the polyglot proposal recommends adding **already exists in the right shape**: subprocess + JSON receipts. Python invokes Go binaries via `operator_core/go_evidence_bridge.py` and `go_github_bridge.py`; Go writes receipts to disk in a documented JSON schema; Python re-reads them as typed objects. This is the textbook FFI-free polyglot boundary: no shared memory, no FFI tax, no toolchain entanglement. Clean.

### 1.5 The declared-intent manifest: `ACTIVE_SURFACE_MANIFEST.yaml`

657 lines, schema_version 2, last updated 2026-05-20. Declares: state dirs, API routers, hot-path modules, ACK/warrant paths. This is **the architectural backbone you already have** — the equivalent of an OpenAPI spec for the whole control plane. Heavily under-leveraged (see Finding H2 below).

### 1.6 The message bus: `dharma_swarm/message_bus.py`

675 LOC, SQLite-backed (via `aiosqlite`), single `MessageBus` class. The multi-agent infra primitive you need is already here. Not glamorous, but correct.

### 1.7 The Ouroboros + Receipt protocol

`results/ouroboros_experiment.json` exists. `closure_v0.EvidenceReceipt` is the proven receipt type, used in 53+ places with bit-for-bit replay semantics.

### 1.8 Hypothesis (property-based testing) seed

4 test files already use Hypothesis. The pattern is established — it just hasn't been scaled.

---

## 2. Findings: What's at Risk (Ranked by Severity)

### 🔴 H1 — Duplicate `EvidenceReceipt` definitions / spine island

**Evidence:**
- `dharma_swarm/operator_core/closure_v0.py:63` — `class EvidenceReceipt` (proven, dataclass with `work_packet_id`, `agentops_source`, `test_exit_code`, `replay_command`, frozen, validated invariants).
- `dharma_swarm/spine/receipt.py:37` — `class EvidenceReceipt` (newer, OTel-aligned, `trace_id`, `span_id`, `claim_id`, `routing_decision_id`, slots, defaults).

These two types have **disjoint fields and disjoint semantics**. The closure_v0 one is referenced 53+ times across production code. The spine one is referenced by **exactly one test (`tests/test_dispatch_dropoff_sources.py`) and one checker (`tools/spine_check.py`)** — no production import.

The `dharma_swarm.spine` package is doctrinally protected ("zero edits to `dharma_swarm/spine/**`" per Master Prompt) but is also functionally an island. This is the worst kind of architectural debt: a frozen surface that doesn't bind to runtime.

**Risk:** Any future architectural conversation must answer "which receipt do you mean?" In a year, this divergence becomes load-bearing in unintended ways. The OTel-shaped spine receipt is probably the right long-term target, but the closure_v0 one is what the system actually runs on.

**Severity:** 🔴 High. Truth-surface duplication is exactly the spaghetti pattern at root.

---

### 🔴 H2 — Manifest exists but is not machine-enforced

**Evidence:** `ACTIVE_SURFACE_MANIFEST.yaml` declares state dirs, API routers, hot paths — but reconciliation against reality is documented as "your workflow" rather than enforced by CI. There IS `tools/spine_check.py` (good!) but it only checks one surface.

**Risk:** The manifest claim that `state_dir.canonical = "~/.dharma"` is contradicted by 119 separate `~/.dharma/...` literals scattered across Python code (audited count). Some go through `daemon_config.dharma_state_dir()` (good), some don't. Same for the 28 declared API routers vs. the 28 actual files in `api/routers/` (these match today; nothing guarantees tomorrow's PR doesn't drift).

**Severity:** 🔴 High. You have the right artifact; you don't have the loop that makes it true.

---

### 🟡 H3 — Flat-top package: 388 `.py` files at `dharma_swarm/` root

**Evidence:** `ls dharma_swarm/*.py | wc -l` → 387 files (210,164 LOC) live as siblings at the package root. Subpackages exist (`memory_kernel/`, `operator_core/`, `tui/`, `revenue/`, `engine/`, `contracts/`, ...) but most of the package's mass is flat.

**God-modules at root (>2,500 LOC each):**

| Module | LOC | Notes |
|---|---|---|
| `thinkodynamic_director.py` | 5,173 | Untyped god-class candidate |
| `telos_substrate.py` | 4,512 | Concept-debt locus (see H6) |
| `evolution.py` | 3,465 | Frozen per doctrine, but huge |
| `agent_runner.py` | 3,355 | Frozen per doctrine |
| `swarm.py` | 3,227 | Imported as `SwarmManager` singleton in `api/main.py` |
| `providers.py` | 3,005 | 20 LLM provider classes in one file (see H4) |
| `orchestrator.py` | 2,755 | Frozen per doctrine |
| `terminal_bridge.py` | 2,539 | |

**Risk:** Discovery friction (where does X live?), import cycle risk grows with file count, refactoring blast radius is unbounded.

**Severity:** 🟡 Medium. Not actively breaking, but every PR that touches a god-module is more dangerous than it should be. 23 root-level files appear unreferenced by any `from dharma_swarm.X` import — candidates for archival.

---

### 🟡 H4 — `providers.py` as god-module (LLM provider layer)

**Evidence:** Single 3,005-LOC file containing **20 provider classes**: Anthropic, OpenAI, OpenRouter, NVIDIA NIM, ClaudeCode, Codex, OpenRouterFree, Ollama, Groq, Cerebras, SiliconFlow, Together, Fireworks, GoogleAI, SambaNova, Mistral, Chutes — plus `ModelRouter` and `_SubprocessProvider` base.

**What's good:** There IS an abstraction (`LLMProvider(BaseProvider)` from `base_provider.py`), and the cost tracker is integrated (`from dharma_swarm.cost_tracker import _estimate_cost`). The pattern is right.

**What's at risk:**
- Adding GPT-6 / Claude 5 / a new local-inference fork means editing a 3,005-LOC file every time.
- Provider-specific quirks (streaming shapes, tool-call schemas, structured-output gates) leak into one shared file.
- No per-provider test isolation — touching one provider can break another.

**Severity:** 🟡 Medium. The future-proofing concern operator named ("planning for models with increasing capacity") binds here directly. Each new frontier model is a god-module patch.

---

### 🟡 H5 — Storage idiom fragmentation, no schema versioning

**Evidence (counts from `dharma_swarm/`):**
- 526 JSONL operations
- 56 SQLite-backed modules
- 159 raw JSON writes
- 119 paths writing under `~/.dharma/`
- 1 pickle usage (good — pickle is poison)
- 0 YAML writes

**Specific persistence locations** (sampled from grep): `~/.dharma/state/`, `~/.dharma/ontology.db`, `~/.dharma/sessions/`, `~/.dharma/economics/`, `~/.dharma/revenue_packets/`, `~/.dharma/go_receipts/world/`, `~/.dharma/board/event_log.sqlite3`, `~/.dharma/sakshi/provenance_log.jsonl`, `~/.dharma/evolution/archive.jsonl`, `~/.dharma/flickers.jsonl`, `~/.dharma/mission.json`, `~/.dharma/meta/opportunity_board.json`, `~/.dharma/jk/truth_ledger.json`, `~/.dharma/shared/*` (free-form markdown drop zone), `~/.dharma/sub_swarms/`, plus dozens more.

**What's good:** The manifest declares `state_dir.canonical = "~/.dharma"` and `runtime_db = "~/.dharma/state/runtime.db"`. A `daemon_config.dharma_state_dir()` helper exists. Some modules route through it.

**What's at risk:**
- No declared schema for any JSONL file (you can't tell what shape `flickers.jsonl` records ought to have without reading every writer).
- No migration story when a Pydantic model field gets renamed — old records become unreadable silently.
- The 526 JSONL operations are not registered anywhere central; capacity-planning ("what fills my disk when I scale to 8000 Ouroboros samples nightly?") is unanswerable without grep.
- Schema drift between writer and reader is undetectable until a `KeyError` at runtime.

**Severity:** 🟡 Medium-high. Bites you exactly when you scale the multi-agent infra and bump the model count — the moment operator cares about.

---

### 🟡 H6 — Concept-debt: 3 spines, 9 ontologies, 57 Agent classes, multiple substrates/kernels

**Evidence (counts via find/grep):**

| Concept | Count | Examples |
|---|---|---|
| Spine surfaces | 3 | `dharma_swarm/spine/`, `dharma_swarm/revenue/spine.py`, `dharma_swarm/economic_spine.py` |
| Ontology surfaces | 9 | `ontology.py`, `decision_ontology.py`, `ontology_adapters.py`, `ontology_agents.py`, `ontology_hub.py`, `ontology_query.py`, `ontology_runtime.py`, `tui/widgets/ontology_browser.py`, `api/routers/ontology.py` |
| Classes containing "Agent" | 57 | `AgentRunner`, `AutonomousAgent`, `AgentOrchestrator`, `ContextAgent`, `BrowserAgent`, `EconomicAgent`, `GinkoAgent`, `CanonicalAgentSpec`, `AgentMemoryManager`, `AgentRegistry`, `AgentIdentity` (×2 — `agent_registry.py` AND `autonomous_agent.py`), `AgentMemoryBank`, etc. |
| Engine classes | many | `auto_grade/engine.py`, `auto_research/engine.py`, `curriculum_engine.py`, `active_inference.py`, `cascade.py`, `dynamic_correction.py`, `canonical_replay.py`, and so on |
| Substrate / kernel files | many | `dharma_kernel.py`, `telos_substrate.py`, `memory_kernel/`, plus `docs/plans/` with 6+ substrate planning documents |

This is the "multiple half-built mental models layered on each other" pattern. PR #382 is the first commitment in three pivots to *one* mental model (proof-artifact wedge). Most of these concepts predate that commitment and still live in the code.

**Risk:** New contributor (or future-you in 6 months) asking "where is the spine?" gets three answers. "What's an agent?" gets 57. "Where does the world model live?" gets 9. Each ambiguity is a small-cost spaghetti seed.

**Severity:** 🟡 Medium. Doesn't break anything today; compounds every month it's unaddressed.

---

### 🟡 H7 — No machine-checked API contract with the TypeScript dashboard

**Evidence:**
- `dashboard/` has 121 `.ts`/`.tsx` files; 42 contain hand-written `interface` or `type` definitions.
- `dashboard/src/lib/types.ts` exists — but it's hand-maintained.
- `dashboard/package.json` scripts: `dev`, `build`, `start`, `lint`, `test:visual`. **No `openapi-typescript`, no `swagger-codegen`, no `orval`, no `graphql-codegen` for the REST routes.** (There IS `api/graphql/schema.py` and `api/routers/graphql_router.py`, which could be code-genned — but no generation step is wired.)
- 28 FastAPI routers in `api/routers/`. None of them have a contract-test against the dashboard's TS types.

**Risk:** Every backend response-model change is a potential runtime error in the dashboard, caught only by the human eye or visual regression test. Schema drift here is the single most-common pattern in real-world Python/TS spaghetti.

**Severity:** 🟡 Medium-high. Especially bad as the dashboard is **74k LOC — bigger than your evaluation kernel by 15×**. The proposal-author didn't notice the dashboard; you should.

---

### 🟢 H8 — API routers reach directly into `dharma_swarm.*` (no service layer)

**Evidence:** `api/routers/chat.py` imports from `dharma_swarm.api_keys`, `dharma_swarm.certified_lanes`, `dharma_swarm.models`, `dharma_swarm.runtime_provider`. `api/routers/agents.py` imports `dharma_swarm.ontology_agents`. `api/main.py` directly instantiates `SwarmManager` from `dharma_swarm.swarm`.

**Risk:** The HTTP layer is tightly coupled to internal module shape. Changing an internal function signature ripples through routers. Not catastrophic — Pydantic models at the boundary catch most damage — but the layer-cake discipline is absent.

**Severity:** 🟢 Low. Standard FastAPI pattern at small scale; only becomes a problem if you scale to multiple HTTP frontends or external API consumers. Defer.

---

### 🟢 H9 — 23 likely-dead-code root files

**Evidence:** Of 387 top-level `.py` files, 23 appear unreferenced by any `from dharma_swarm.X` import: `agent_install.py`, `api_key_audit.py`, `coalgebra_dseintegrator_dse_integration.py`, `cron_scheduler.py`, `curriculum_engine.py`, `dharma_context_mcp.py`, `ecosystem_map.py`, `free_fleet.py`, `ginko_live_test.py`, `launchd_job_runner.py`, `model_manager.py`, `orchestrate_live.py`, `pulse.py`, `roaming_dispatch_daemon.py`, `sealed_packet_apply.py`, `startup_crew.py`, `strange_loop.py`, `swarm_health_api.py`, `terminal_bridge.py`, `topology_genome.py`, `tui_legacy.py`, `vector_store.py`, `web_search.py`.

Some may be CLI entry points referenced by `scripts/` or `Makefile` — needs per-file verification. But the population is suspicious.

**Severity:** 🟢 Low. Hygiene, not architecture.

---

## 3. The Long-Term Theory of the Codebase

The operator's concern decomposes into four sub-questions. Honest answers in this codebase's specifics:

### 3.1 "Robust" → Boundary contracts

A system is robust when its boundaries refuse bad inputs and emit typed outputs. You already have Pydantic discipline at most of these. The gap is **boundary enforcement** — schema versioning on persistence (H5), machine-checked API contract with the dashboard (H7), and deduplication of the receipt protocol (H1).

### 3.2 "Future-proof" → Substitutable backends

Future-proof means: when Anthropic ships Claude 5, you change a config; you don't refactor. When you swap SQLite for Postgres, you change one module. When you add a new ingestor, you don't touch the agent loop. This requires **explicit substitution points** — clean abstract classes with multiple concrete implementations. You have this for providers (good, but god-moduled — H4); you don't have it for persistence (H5).

### 3.3 "Solidly modular" → One source of truth per concept

A module is doing modularity work when it owns *one* concept and exposes *one* contract. Your `models.py`, `auto_grade/`, `gauntlet.py`, `message_bus.py` exemplify this. Your `evolution.py`, `thinkodynamic_director.py`, `telos_substrate.py`, `providers.py` do not. The concept-debt (H6) and god-modules (H3, H4) are the visible failure mode.

### 3.4 "Planning for models with increasing capacity, multiple agent infrastructure"

This is the future-proofing question with the highest near-term cash value. Specifically:

**For increasing model capacity (longer context, faster inference, structured-output guarantees, native tool-calling):** the provider abstraction needs to be *capability-aware* (already has `ProviderCapabilities` in `base_provider.py` — good!), and each new provider should be a separate file plugging into a registry, not an entry in a 3,005-line monolith (H4).

**For multi-agent infrastructure:** the substrate is in place (`message_bus.py`, `EvidenceReceipt`, `agent_card.py` for A2A). The risk is the 57 `Agent*` classes (H6) — there is no single Agent Protocol they all implement. Until there is, "multi-agent infra" is a generous label for "57 things that have 'Agent' in their name."

---

## 4. Hardening PR Slate (5 PRs, all Python, all decoupled from PR #382)

These are ordered by leverage-per-LOC. Each is a discrete PR. None require any new language. None touch the frozen spine surfaces (`spine/`, `orchestrator.py`, `agent_runner.py`, `runtime_state.py`) in code-changing ways. **All 5 together are ~1,500 LOC of new/refactored code, none on the critical path of PR #382.** They can run in parallel as background hardening while Layer 1/2 ships.

### PR-H1 — Receipt convergence (resolves H1, 🔴 High)

**Scope:** Document the relationship between `closure_v0.EvidenceReceipt` (production, 53+ uses) and `spine.EvidenceReceipt` (doctrine, 1 test). Decide direction (probably: spine becomes the OTel projection of closure_v0; closure_v0 stays the operational truth). Add a single-source-of-truth doc; add a CI check that no third `EvidenceReceipt` class can be defined.

**Touches:** `docs/architecture/receipt_protocol.md` (new), `tools/receipt_uniqueness_check.py` (new, ~30 LOC), `dharma_swarm/spine/receipt.py` (docstring only — no code change, doctrine respected).

**Effort:** 1 day. Doctrine-safe (no spine code changes).

---

### PR-H2 — `tools/manifest_check.py` (resolves H2, 🔴 High)

**Scope:** Promote `ACTIVE_SURFACE_MANIFEST.yaml` from declared intent to CI-enforced contract. New `tools/manifest_check.py` runs in pre-commit and CI; verifies:
- Every `api_routers` entry corresponds to an existing `api/routers/<id>.py` and is wired in `api/main.py`.
- Every declared `state_dir.*` path is reached only through `daemon_config.dharma_state_dir()` or `_state_path()` helpers (no raw `~/.dharma/...` literals).
- Schema fields in the manifest match what the code actually does.

**Touches:** `tools/manifest_check.py` (new, ~150 LOC), `.pre-commit-config.yaml` (one line), `.github/workflows/` (one line).

**Effort:** 2 days. Highest-leverage PR in this slate — turns 657 lines of documentation into 657 lines of enforced invariants.

---

### PR-H3 — Provider layer split + capability registry (resolves H4, 🟡 Medium)

**Scope:** Split `dharma_swarm/providers.py` (3,005 LOC, 20 classes) into `dharma_swarm/providers/{anthropic,openai,openrouter,nvidia_nim,claude_code,codex,openrouter_free,ollama,groq,cerebras,siliconflow,together,fireworks,googleai,sambanova,mistral,chutes}.py` plus `__init__.py` + `router.py` + `registry.py`. Each provider is its own module (60–200 LOC). `ProviderCapabilities` stays in `base_provider.py`. Add a `register_provider()` decorator so new providers are added by writing one file + one line in a registry, not editing a god-module.

**Touches:** `dharma_swarm/providers/` (new package, ~3,200 LOC across ~22 files), `dharma_swarm/providers.py` (shim re-export for backward compat). All call sites unchanged.

**Effort:** 3–4 days. **This is the actual "planning for increasing model capacity" PR.** Adding GPT-6 next year becomes a single new file.

---

### PR-H4 — Storage schema registry + migration story (resolves H5, 🟡 Medium-high)

**Scope:** Introduce `dharma_swarm/storage/` package with:
- `schema_registry.py` — every JSONL file path is registered with a Pydantic model + version number.
- `jsonl_writer.py` / `jsonl_reader.py` — wrappers that include the schema version in every record and refuse to read records they can't validate.
- `migrations/` — per-version transformers for evolving schemas.

Then migrate the highest-traffic JSONL writers (`flickers.jsonl`, `evolution/archive.jsonl`, `sakshi/provenance_log.jsonl`) to the new system. Leave low-traffic ones for later. Add CI check: no new `~/.dharma/...` literal outside the schema registry.

**Touches:** `dharma_swarm/storage/` (new, ~400 LOC), migrations of ~5 writers (~200 LOC of changes).

**Effort:** 5–7 days. **This is the "robust at scale" PR.** When you 100× the Ouroboros sample count, this is what prevents a disk-full or schema-drift incident.

---

### PR-H5 — TypeScript types generated from FastAPI (resolves H7, 🟡 Medium-high)

**Scope:** Add `openapi-typescript` to `dashboard/`. Add `npm run gen:types` script that hits FastAPI's `/openapi.json` and generates `dashboard/src/lib/api-types.generated.ts`. Replace the hand-written types in the 42 dashboard files that have them with imports from the generated file. Add CI check: `git status --porcelain dashboard/src/lib/api-types.generated.ts` must be clean after re-generating.

**Touches:** `dashboard/package.json` (add tool + script), `dashboard/src/lib/api-types.generated.ts` (new, auto), incremental migrations of 42 files (~200 LOC of TS edits over time).

**Effort:** 1 day for the wire-up + ongoing migration as you touch each dashboard surface. **This is the "no schema drift between Python and the 74k-LOC frontend" PR.**

---

## 5. What This Slate Does Not Do (Intentional)

To avoid replacing one architecture-talk pivot with another, these things are **explicitly deferred**:

1. **No spine refactor.** `dharma_swarm/spine/**` stays frozen per doctrine. PR-H1 only adds documentation and a CI check.
2. **No agent class consolidation.** The 57 `Agent*` classes (H6) need a single Agent Protocol someday, but that's a Q3 conversation after multi-agent infra has actual production traffic. Premature unification is its own spaghetti.
3. **No ontology unification.** The 9 ontology modules (H6) should probably collapse to 2–3, but the live work in PR #382 doesn't require it.
4. **No dead-code purge.** The 23 candidate files (H9) get a follow-up issue, not a PR.
5. **No router service layer.** H8 stays at 🟢 Low and is deferred indefinitely.
6. **No Rust. No Lean. No Go expansion beyond what's wired.** The polyglot proposal is independently rejected (see `polyglot_proposal_critical_review_v1.md`).

---

## 6. The Honest Reframe for the Operator's Question

> "I just want to ensure that we are robust, future proof, solidly modular, innovative and planning for models with increasing capacity, multiple agent infrastructure and it is not just a Python spaghetti plate."

You are not on a spaghetti plate. You are on **a clean kernel surrounded by three pivots of accumulated concept-debt and structural sprawl**. The kernel is real: `models.py`, `auto_grade/`, `gauntlet.py`, `message_bus.py`, `ACTIVE_SURFACE_MANIFEST.yaml`, the Go-via-receipts bridge. That's the substrate.

The work that makes the system "robust, future-proof, solidly modular, planning for increasing capacity" is **boundary discipline applied to that kernel**:

- One canonical receipt protocol (PR-H1)
- Machine-enforced manifest (PR-H2)
- Provider-per-file capability registry (PR-H3)
- Schema-versioned persistence (PR-H4)
- Codegen'd Python ↔ TypeScript contract (PR-H5)

These five PRs are ~1,500 LOC total, all Python, all decoupled from the PR #382 wedge, all addressable in 12–17 days across the next month or two as background work. They do not compete with Layer 1 / Layer 2. They make the substrate underneath Layer 1 / Layer 2 strictly stronger.

"Innovative" is not solved by structural PRs — it's solved by Ouroboros having weirdness in it, by TGSM-Eval naming a real telos-trap class no one else benchmarks. That work is *also* not what the polyglot proposal was offering.

**The structural answer to the "Python spaghetti plate" worry is not Rust. It's the slate above.** The strategic answer is: ship PR #382, harden the substrate in the background, evaluate any further architectural ambition only after Layer 2 produces inbound. Then you'll know what's actually load-bearing and what was just doctrine.

---

## 7. Receipts

**Audit method:** Direct read of `/home/user/workspace/dharma_swarm/` at branch `devin/2026-05-30-proof-artifact-pivot`. All counts from `wc -l`, `grep -rln`, `find`. Import topology computed by `grep -rh "^from dharma_swarm"`. No external information used.

**Key files referenced:**
- `dharma_swarm/models.py` (396 LOC, 29 types, 249 import sites)
- `dharma_swarm/operator_core/closure_v0.py` (the proven `EvidenceReceipt`)
- `dharma_swarm/spine/receipt.py` (the doctrine `EvidenceReceipt`)
- `dharma_swarm/providers.py` (3,005 LOC, 20 classes)
- `dharma_swarm/auto_grade/` (433 LOC across 9 files — model of subsystem shape)
- `benchmarks/gauntlet.py` (787 LOC)
- `dharma_swarm/message_bus.py` (675 LOC, SQLite-backed)
- `ACTIVE_SURFACE_MANIFEST.yaml` (657 LOC, schema_version 2)
- `tools/{evidence,github,world_signal,world_scout}_ingestor_go/` (Go bridge, clean shape)
- `dharma_swarm/operator_core/go_evidence_bridge.py`, `go_github_bridge.py` (Python↔Go boundary)
- `dashboard/` (121 TS files, 42 hand-written types, no codegen)

**Companion documents:**
- `docs/reports/polyglot_proposal_critical_review_v1.md` — why no Rust/Lean/Go-expansion
- `docs/reports/proof_artifact_slate_v1.md` — the PR #382 wedge this audit defers around
- `/home/user/workspace/polyglot_rewrite_outcomes.md` — 18-case empirical record (external)
- `/home/user/workspace/lean_aeneas_for_ai_verification_2026.md` — formal verification reality (external)

---

*Authority: external_worker_evidence_only. This document recommends 5 hardening PRs and a posture. Operator decision required to authorize any PR; none touch the frozen `dharma_swarm/spine/**` / `orchestrator.py` / `agent_runner.py` / `runtime_state.py` surfaces in code-changing ways.*
