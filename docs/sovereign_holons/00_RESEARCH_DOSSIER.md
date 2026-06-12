# Research Dossier — World-Class Super-Autonomous Agents in 2026, and What We're Missing

**Compiled:** 2026-06-08 · **Method:** `deep-research` harness (fan-out web search → fetch → verify →
synthesize), two passes, fused with a read-only internal-wiring panel over the dharma_swarm repo and
three verified safety/self-improvement audits from the prior week.

> **Verification caveat (read this):** Run 1's automated adversarial-verification phase hit a harness
> bug — the verifier sub-agents failed to emit structured output and every claim defaulted to
> "killed (0-0, 3 abstain)." That is a *harness failure, not a refutation.* The underlying claims are
> well-sourced (primary Anthropic engineering + arXiv + framework docs) and the major ones are
> corroborated from first-principles knowledge. Treat them as **well-sourced but not independently
> cross-examined.** Run 2 (widened, ≥40 sources) is appended when it lands.

---

## THE HEADLINE (the "so what")

Across nearly every 2026 source, one thesis dominates: **the harness is the product, not the model.**

- Same model + better harness = **+18 points** on long-horizon tasks (arXiv 2605.10912).
- One coding agent moved **rank 30 → top 5 on harness redesign alone** (awesome-harness-engineering).
- Practitioner consensus (Reddit synthesis): agent quality is a *harness/workflow* problem, not a
  weights problem.

This is an uncomfortable **inversion for dharma_swarm**: we invested most in *governance*, and the
frontier says governance/heavy-control is secondary to harness quality (and naive memory + heavy
control can actively *hurt* reliability). Meanwhile the "commodity shell" — runnable agent +
verification loop + context engineering — is the actual differentiator, and per our own audit is the
verified-weakest part. **The good news: the thing the operator wants to build next (a sovereign holon
you can talk to) is the single highest-leverage missing piece.**

---

## (A) Frontier landscape by source-type (run 1)

- **Primary engineering (Anthropic ×4):** `effective-harnesses-for-long-running-agents`,
  `effective-context-engineering-for-ai-agents`, `managed-agents`, async-agents w/ Cognition Labs.
  Canonical playbook: external filesystem artifacts bridge context windows; compaction +
  note-taking; brain/hands/session decoupling; mandatory E2E verification.
- **Academic (arXiv, primary):** Darwin Gödel Machine (2505.22954); long-horizon reliability
  (2603.29231) — the deepest paper; native-runtime long-horizon bench (2605.10912).
- **Frameworks:** LangGraph durable-execution docs; a counter-source (diagrid) arguing
  "checkpoints ≠ durable execution"; LangGraph-vs-CrewAI-vs-OpenAI-SDK comparison.
- **Practitioner ground-truth:** Reddit-thread synthesis (late Apr–May 2026) — cost & reliability
  dominate; harness over weights.
- **Harness-engineering canon:** `awesome-harness-engineering` (GitHub) — names the discipline + ~11
  categories.

### Source table (run 1)

| URL | Quality | Claims |
|---|---|---|
| arxiv.org/abs/2505.22954 (Darwin Gödel Machine) | primary | 5 |
| anthropic.com/engineering/effective-harnesses-for-long-running-agents | primary | 5 |
| anthropic.com/engineering/effective-context-engineering-for-ai-agents | primary | 5 |
| anthropic.com/engineering/managed-agents | primary | 5 |
| anthropic.com/webinars/mastering-async-agents-cognition-labs | secondary | 3 |
| epsilla.com/blogs/anthropic-harness-engineering-multi-agent-gan-architecture | secondary | 5 |
| github.com/ai-boost/awesome-harness-engineering | secondary | 5 |
| docs.langchain.com/oss/python/langgraph/durable-execution | primary | 4 |
| particula.tech/blog/langgraph-vs-crewai-vs-openai-agents-sdk-2026 | blog | 5 |
| arxiv.org/pdf/2603.29231 (long-horizon reliability) | primary | 5 |
| arxiv.org/html/2605.10912v1 (harness>model, native runtime) | primary | 5 |
| nxcode.io/.../what-is-harness-engineering-complete-guide-2026 | blog | 5 |
| andriifurmanets.com/.../ai-agents-2026-practical-architecture-tools-memory-evals-guardrails | blog | 5 |
| kili-technology.com/blog/ai-benchmarks-guide-...-2026 | blog | 5 |
| dev.to/.../ai-agents-on-reddit-late-april-to-early-may-2026 | secondary | 5 |
| *(fetch-failed, harness bug)* letta.com/blog/letta-v1-agent; niteagent.com; diagrid.io checkpoints; inovabeing.com reliability; arxiv 2507.21046 / 2603.07670 / 2509.18970 / 2601.01743 | unreliable | 0 |

**24 sources fetched, ~16 with real claims, ~8 fetch-failed. Short of the 40 bar — run 2 widens.**

---

## (B) The ~11 capabilities that define world-class autonomy (run 1)

1. **Harness engineering** as a discipline (the meta-capability).
2. **External persistent-artifact memory** to cross context windows (feature-list JSON + progress +
   git history) — Anthropic effective-harnesses.
3. **Verification loops / E2E testing** — "done = verifier green," not "AI says done." Canonical
   failure mode = marking complete without testing; mitigation = browser-automation E2E.
4. **Generator/Evaluator separation (GAN-style)** — single-agent self-critique is unreliable; models
   over-rate their own output; externalize evaluation to a separate agent (Epsilla on Anthropic).
5. **Context engineering** — compaction + structured note-taking outside the window (Claude plays
   Pokémon across thousands of steps).
6. **Brain/hands/session decoupling** — uniform `execute(name,input)→str` tool interface; sandboxes
   as disposable "cattle"; state in a session object outside context, queryable via `getEvents()`
   (Anthropic managed-agents).
7. **Durable execution** — checkpoint + fault-tolerant resume (LangGraph), and the harder "real
   durable execution," not just checkpoints (diagrid critique).
8. **Reliability ≠ capability instrumentation** — measure long-horizon success/meltdown, not pass@1
   (arXiv 2603.29231).
9. **Self-improvement** — archive-based open-ended evolution with empirical validation (DGM:
   SWE-bench 20→50%, Polyglot 14→30%).
10. **Tool/action-space + skills/MCP design.**
11. **Permissions/authorization + human-in-the-loop.**

**Two hard research warnings:**
- **Naive episodic memory *universally hurt* long-horizon reliability** across all 10 models tested —
  negative/neutral Graceful Degradation Score (arXiv 2603.29231).
- **The "MOP paradox":** *more capable* models melt down *more* (up to 19%) by over-reaching; even the
  best agent (Opus 4.7) reaches only **62.2%** on long-horizon native-runtime tasks (2605.10912).

---

## (C) Gap analysis — HAVE / PARTIAL / MISS (adversarial, with receipts)

| Capability | Status | Honest reality + receipt |
|---|---|---|
| Governance / safety | **PARTIAL → THEATER** | Looks world-class; verified paraphrase-evadable, `REVIEW→applied`, no live self-mod gate. Frontier says governance is secondary anyway. `project_hostile_safety_audit_2026_06_05`; `telos_gates.py:270-339`; `evolution.py:1768`; `ontology.py:385,944` |
| Self-improvement (DarwinEngine) | **MISS (unwired)** | 0/11,095 archive lineage, 99% empty diffs; `--continuous` never calls a proposer. We have DGM's *skeleton*, not its loop. `project_dgm_loop_unwired_2026_06_07`; `benchmarks/gauntlet.py:237` |
| **Runnable shell + human talk surface** | **MISS** | `chat_with_agent` runs the *global* model with a cosmetic persona string; never loads the agent's own model/prompt; no record→runtime bridge. Real build, not glue. `api/routers/agents.py:404-496,419-470`; `agent_registry.py:329-350` |
| Verification loop as a runtime organ | **MISS (doctrine-only)** | Exists as the obey detonation rule + skills, not wired into the agent runtime. The gauntlet is its unwired skeleton. |
| Context engineering / durable execution | **PARTIAL** | MemoryKernel + witness logs exist; no verified long-horizon compaction/resume harness in the wake loop. |
| Generator/Evaluator separation | **PARTIAL** | The Transcendence Principle *is* this doctrinally; not wired into a single agent's run. |
| Brain/hands/session decoupling | **PARTIAL** | `docker_sandbox.py` exists; agents not architected as brain/hands/session. |
| Reliability instrumentation | **MISS** | `fitness_history` measures the wrong thing (and is 99% empty); no GDS/meltdown metric. |
| Persistent self / identity | **HAVE (data) / MISS (runtime)** | `AgentRegistry` stores rich evolving selves; nothing loads them into a running agent. |
| Model routing | **PARTIAL** | Canonical free-first door exists (`runtime_provider.py:93,158,434`); Ollama Cloud / DeepSeek / NVIDIA NIM **LIVE & free**; but presets default to `claude_code` → crash if binary missing, no free fallback there (`autonomous_agent.py` PRESET_AGENTS; `cli_wake` 1554-1611). |

---

## (D) Top things we're missing, ranked by leverage

1. **The runnable shell + human talk surface** (record→runtime bridge). Highest leverage; frontier's
   #1 lever; literally the holon. → *harness engineering.*
2. **A wired verification loop as an agent organ** (separate Evaluator, E2E, verifier-green=done). →
   *GAN Generator/Evaluator.*
3. **Reliability (not capability) instrumentation.** → *arXiv 2603.29231 GDS/meltdown.*
4. **Context-bridging harness in the wake loop** (compaction + external note artifacts). →
   *Anthropic context-engineering.*
5. **Brain/hands/session decoupling** with a uniform tool interface. → *managed-agents.*
6. **An honest self-improvement loop** (real lineage + non-empty diffs + empirical gate). → *DGM.*
7. **Re-examine memory & governance against reliability evidence** — our two biggest investments may
   be *net-negative* on long-horizon reliability. → *arXiv 2603.29231.*
8. **Decorrelated free-model routing as the default** for local sovereign agents (Ollama Cloud, not
   claude_code).

---

## Internal-wiring panel (read-only, 2026-06-08) — the receipts behind (C)

Three decorrelated Explore agents (opus/sonnet/haiku), each prompted to **refute** "the substrate is
wired," not confirm:

- **chat surface + registry round-trip → UNWIRED/STUB.** `chat_with_agent` (`api/routers/agents.py`)
  resolves `agent_id` to a metadata dict (`load_agent`, agents.py:226), builds a cosmetic system
  prompt (441-449), and calls the generic `_agentic_stream` (470) with the *operator's* global
  `settings` (432) — the agent's stored `model`/`provider`/active prompt are never used to configure
  the call. `AgentRegistry` has **no** method returning an `AutonomousAgent`/`PersistentAgent`; no
  `load_agent(name) -> runnable` exists anywhere. **"Talk to a registered agent" is a real build.**
- **PersistentAgent → REAL but registry-disconnected.** Composes `AutonomousAgent`; instantiated only
  in `orchestrate_live.py:1457-1460,1615-1616` from hardcoded config, never from a registry record.
- **Model routing → PARTIAL.** Canonical door (`runtime_provider.resolve_runtime_provider_config` /
  `create_runtime_provider`) + free-first ordering exist and work; `dkeys`: Ollama Cloud, DeepSeek,
  NVIDIA NIM **live & free**. But default presets route to `claude_code` and crash if the `claude`
  binary is absent (no free fallback on that path) — the likely root of the prior opus_composer
  "Credit balance too low." **First holon should route to Ollama Cloud (GLM-5): free, live,
  decorrelated.** (3rd agent partially rate-limited; `PersistentAgent` runtime confirmed real via the
  chat-agent's cross-read.)

---

## Run 2 — widened pass (completed 2026-06-08, Task `wa692029u`)

28 additional sources (78 claims). Combined with run 1 = **~52 distinct sources / ~150 claims**, past
the 40 bar. Same harness verification bug (claims defaulted to "killed") — same caveat applies. New,
materially important findings below.

### New source table (run 2, claim-bearing)

| URL | Quality | Theme |
|---|---|---|
| arxiv.org/html/2605.23950 | primary | **Factorial harness study: harness variance 18.48pp² vs model 2.37pp² = 7.8×**; 6 ranking reversals; Terminal-Bench 2 69.7→77.0 scaffold-only |
| arxiv.org/pdf/2406.12045 (τ-bench) | primary | **pass^k reliability metric**; GPT-4o <50% on τ-bench, pass^8 <25% retail — reliability collapses under repeated trials |
| letta.com/blog/sleep-time-compute | primary | **Sleep-time compute**: async memory reorganization; dual-agent split (primary handles user, sleep-time agent reorganizes memory); "raw context → learned context" |
| letta.com/blog/memory-blocks | blog | Structured editable memory blocks as the agent's self |
| github.com/getzep/graphiti | primary | **Bi-temporal memory graph**: validity windows, point-in-time queries, incremental real-time, hybrid retrieval (embeddings+BM25+graph) |
| platform.claude.com/docs/en/managed-agents/multi-agent | primary | **Orchestrator-worker; each worker a context-isolated persistent session thread with own history/model/prompt/tools/MCP/skills** — Anthropic productizing the holon-as-cell |
| latent.space/p/factory | secondary | Production agents need integrated enterprise context (Slack/Notion/Linear/Jira/Datadog/Sentry/GitHub) — "throw code at it" = toy; verification = automated tests not human review; limiting factor = models lack long-horizon post-training; droids are "loosely goal-oriented," bounded-autonomous |
| uvik.net/blog/agentic-ai-frameworks | secondary | Same Opus 4: 64.9% (HAL) vs 57.6% (HF) on GAIA, ~30pt bare-vs-scaffold; durable execution a production primitive; **only ~5% of 300+ agent builds reach production** — failure = no observability + no HITL + no cost discipline, not the framework |
| github.com/ComposioHQ/agent-orchestrator | secondary | Parallel agents each in own git worktree/branch; verification/self-correction loop (agents auto-fix CI failures + review comments) |
| cognition.ai/blog/dont-build-multi-agents | (fetch-failed, title-known) | **Counter-thesis: single-threaded coherence often beats multi-agent**; shared context across agents causes incoherence |
| philschmid.de/agents-pass-at-k-pass-power-k; simmering.dev/blog/agent-benchmarks; kili (GAIA 7pt swing); morphllm; addyosmani code-agent-orchestra; digitalapplied 5 patterns | blog/secondary | reliability metrics, harness-is-product corroboration, orchestration patterns |

### New capabilities surfaced (extend section B)

12. **Sleep-time compute** — agents reorganize memory/context during idle time (a *separate* sleep-time
    agent), turning raw context into reusable learned context (Letta).
13. **Bi-temporal memory** — facts carry validity windows; query "what was true at time T," not just
    now (Graphiti). A principled answer to the "naive memory hurts" warning: structure + recency, not
    a flat episodic dump.
14. **Context-isolated persistent worker threads** — orchestrator-worker where each worker keeps its
    own model/prompt/tools/history across turns (Anthropic Managed Agents) — *this is the holon-as-cell
    pattern, validated by Anthropic.*
15. **Production-grounding + the pilot→prod triad** — integrated context sources + observability +
    human-in-the-loop + cost discipline. Only ~5% reach production; the gap is operational, not model.
16. **Worktree-isolated parallel agents with CI self-correction** (Composio) — and the **counter-thesis**
    that *multi-agent can hurt coherence* (Cognition "don't build multi-agents").

### How run 2 sharpens the gap analysis

- **Harness dominance is now quantified: 7.8× model variance** (2605.23950). The headline isn't soft —
  it's the single largest measured lever. Our weakest organ (the runnable shell) is empirically the
  biggest one.
- **Reliability metric to adopt: `pass^k`** (τ-bench). Concrete, droppable into our (currently empty,
  wrong-target) `fitness_history`. Measures the thing that actually matters for autonomy.
- **Sleep-time compute maps directly onto our `AgentCronScheduler`** — we already have the per-agent
  mini-cron *timer*; we lack the memory-reorganization *content* it should run. Cheap, high-value.
- **Anthropic Managed Agents validates the holon-as-cell** — context-isolated persistent worker threads
  are exactly what we're building; we have the mailbox, not the isolated persistent session.
- **The pilot→prod triad (observability + HITL + cost) is a MISS** and is *the* thing separating real
  agents from demos — more than any single capability.
- **Adversarial caution (Cognition):** dharma_swarm bet heavily on a multi-agent organism. The frontier
  has a serious counter-current that multi-agent context-sharing *reduces* coherence. Our stigmergy /
  decorrelation is a different (better) flavor, but the warning stands: a single coherent sovereign
  holon may beat a noisy swarm for many tasks. Build the *one* great holon before the fleet.

### "moltbook" — UNRESOLVED

Neither run resolved "moltbook" to a real, citable agent resource. Likely a misspelling. Candidates to
confirm with the operator: **"Moltbook"** (no match), possibly **"MoltBook"/"Moltbook"** misheard for
something else, or a private/Discord resource not web-indexed. **Flagged for operator clarification.**

---

## Critic pass (2026-06-08) — research blind spots & load-bearing corrections

An adversarial completeness critic (opus, read-only) was run against this dossier. Findings that
change how the dossier should be *used*:

1. **Provenance bias — the corpus is ~70% Anthropic-ecosystem.** The vendors sampled (Anthropic,
   Letta, Factory, Composio) all *sell* the harness/memory layer; "harness > model" is their house
   view. Missing entirely: Google DeepMind, OpenAI, and — ironically — **DeepSeek/Zhipu/Moonshot**
   agent research, i.e. the lab behind the GLM-5 we recommend routing to. Soften "across nearly every
   source" → "across the Anthropic-harness ecosystem sampled."
2. **"Practitioner ground-truth" is overstated** — it is one secondary dev.to *summary* of Reddit, not
   primary Reddit/HN/X/Discord threads. Downgrade the claim.
3. **Missing capabilities (add before any build):** **prompt-injection / tool-output-poisoning defense**
   (build-blocking for a holon that ingests external context — absent from all ~16); **cost/cache
   economics** (prompt caching is the biggest 2026 cost/latency lever — never pulled); **structured-
   output / tool-call reliability**; **agentic RL post-training** (where the *model* dominates). Scope
   line needed: this dossier covers *coding/knowledge-work text agents*, NOT computer-use/voice/embodied.
4. **"7.8× harness variance" is over-generalized** from one coding-benchmark factorial study within a
   *near-frontier model band*. Swap in a weaker free model and model variance returns. It **cannot** be
   used to justify routing to GLM-5 while claiming the harness compensates — that's the exact regime
   where the number evaporates.
5. **"Harness > model" raises the FLOOR within a model's envelope; the model sets the CEILING** (MOP
   paradox; Opus 4.7 caps at 62.2%; post-training as limiter). A great harness on GLM-5 still inherits
   GLM-5's long-horizon ceiling. This directly tensions the "free-model by default" recommendation —
   reconcile explicitly.
6. **Category-error caution:** the "governance is net-negative on reliability" finding is measured on
   *coding task-completion* benchmarks. dharma_swarm's governance optimizes a *different* objective
   (identity coherence, value-alignment). The honest, narrower claim is **"governance should not sit in
   the task-execution hot path"** (a wiring claim) — NOT "governance is theater." Do not gut governance
   on out-of-domain evidence.
7. **This dossier exempts itself from its own Generator/Evaluator principle.** Its verification phase
   failed; by its own capability #4, an un-cross-examined synthesis is a *generator draft*. Every
   headline number (7.8×, +18pp, 62.2%, ~5%-reach-prod, DGM 20→50%) is **verifier-pending** and
   several are single-source/self-reported (DGM grades its own method; ~5% is an uncited vendor stat).
8. **Dated framing:** "GAN Generator/Evaluator" → it's *LLM-as-judge / critic separation* (no
   adversarial training). DGM is 2025-generation; the 2026 successor direction is agentic-RL /
   verifier-guided self-improvement.

**Net:** the dossier's *direction* (build the runnable shell + wired verification + context-bridging)
holds. Three corrections are binding before a build commit: **(a) don't gut governance on coding
evidence; (b) don't read "harness>model" as license to default to a weak free model; (c) add
prompt-injection defense to scope.**
