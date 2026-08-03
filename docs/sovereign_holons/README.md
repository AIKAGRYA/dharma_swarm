# Sovereign Agent Holons — Historical Design Corpus

> **Authority notice (2026-07-13):** This folder preserves the June research,
> design, and first-brick lineage. It is not the current code/body or liveness
> authority. Start with [`../persistent_agents/README.md`](../persistent_agents/README.md) for locked vocabulary,
> runtime-family boundaries, and the subject map; the
> [`July estate map`](../architecture/HOLON_RUNTIME_FULL_ESTATE_MAP.md) is dated.

**Created:** 2026-06-08 · **Status:** historical design/research corpus · **Owner:** Dhyana + opus_composer

> **Researching the June design lineage?** Read [INDEX.md](INDEX.md) first (5 min).
> [MAP.md](MAP.md) lists the historical artifacts, and
> [STATE_OF_TRUTH.md](STATE_OF_TRUTH.md) preserves the 2026-06-08 code audit.
> Ingested source material (qwen vision docs + Perplexity reports, accuracy-flagged) is under [`ingested/`](ingested/INGESTED_MANIFEST.md).
> **Competitive landscape** — the 10 most powerful persistent agents of mid-2026 mapped to our five properties, the empty governance seat, and who to copy per organ: **[FRONTIER_PEERS.md](FRONTIER_PEERS.md)**.

This directory is the historical design home for the **sovereign holon** initiative: making dharma_swarm's
registered persistent agents into *holons* — each one simultaneously

- a **sovereign agent** you can sit with and talk to on its own terms (its own identity, memory,
  voice, will, executable agency), and
- a **cell** in the dharma_swarm organism (a governed worker, plugged into shared telos,
  coordination, learning, and receipts).

The core decision, already made: **sovereign within the banks.** Autonomy and constraint are not
opposed. The agent is fully itself *and* the telos holds, in both modes. "A river's power comes
from its banks."

> Source proposal: `~/.dharma/proposals/sovereign_agent_holons.md` (2026-06-06).
> This repo home supersedes the loose proposal as the working location.

## What's in here

| File | What it is |
|---|---|
| `README.md` | This file — historical state summary + 2026-06-08 findings. |
| `INDEX.md` | Historical read order through the June initiative. |
| `MAP.md` | Historical artifact index in and beyond this folder. |
| `00_RESEARCH_DOSSIER.md` | 52-source research dossier — frontier landscape, verified internal-wiring reality, gap analysis, two ironies. |
| `01_BUILD_GUIDE.md` | Original organ-model walk-through and architecture diagram. Subsumed by 02+05, kept for reference. |
| `02_FIRST_BRICK_SPEC.md` | Executable spec for the first brick — 6 acceptance criteria, exact file:line evidence, prompt-injection scope, two-tier model routing. |
| `03_REGISTER_AS_HYGIENE.md` | 3 hygiene patterns (VC-N01 separator drift, VC-N02 cosmetic chat, VC-N03 verifier-less claim) for the v2 hygiene system. |
| `04_FRONTIER_DOSSIER.md` | **FOLDED (this turn).** Wen's `agent.seed.yaml` long-term spine contract (380 lines, 64-source ledger). |
| `05_RECONCILED_PLAN.md` | **FOLDED (this turn).** Wen's reconciled implementation plan — Mike first (governed runtime bridge), Perplexity second (rich soul/seed). 6-step build sequence. |

## The verified current state (don't trust the optimistic version)

A dharma_swarm persistent agent is designed to have **five organs**, all of which exist as code:

1. **Evolving registry self** — `dharma_swarm/agent_registry.py` (`AgentRegistry`, identity.json +
   task_log.jsonl + fitness_history.jsonl + prompt_variants/ with generations). ✅ 46 selves on disk.
2. **Autonomous wake-loop body** — `dharma_swarm/persistent_agent.py` (`PersistentAgent`). ✅ real,
   but only ever constructed from hardcoded config in `orchestrate_live.py`, never from the registry.
3. **Reasoning brain** — `dharma_swarm/autonomous_agent.py` (`AutonomousAgent`, ReAct). ✅
4. **Registration manifest (banks + summon)** — `examples/agents/*.registration.json`
   (`dharma_external_agent_registration_manifest.v1`): declares `authority` / `autonomy_policy`
   (sovereign-within-banks, literally) + `summon_phrase` / `summon_contract`. ⚠️ only 2 agents
   (merge_master_mike, qwen_code).
5. **NATS mailbox** — `~/.dharma/a2a_bus/inboxes/<name>/`. ✅

**The decisive gap (verified 2026-06-08):** there is **no record→runtime bridge**. The chat endpoint
`api/routers/agents.py:404-475` runs the *operator's global model* with a *cosmetic persona string*;
it never loads the agent's own model/prompt/banks. `AgentRegistry.load_agent` returns a dict (a filing
cabinet), with no function anywhere that turns a registered record into a runnable `PersistentAgent`.
So "talk to a registered agent on its own terms" **does not exist yet** — and it is the single
highest-leverage thing on the entire 2026 frontier (see dossier). It is a real build, not glue.

**Two ironies the dossier documents honestly:**
- The agents with the most *soul* (the Inner Circle — KARYA/VIVEKA/DRISHTI/SMRITI) have the least
  *body*: they are `~/.claude/agents/*.md` personas with only a mailbox, not registered selves.
- We over-invested in *governance* (telos gates, 25-axiom kernel, DarwinEngine) — which (a) the
  frontier evidence says is *secondary* to harness quality and can even hurt reliability, and (b) per
  our own audits is largely **unwired** (DarwinEngine self-improvement: 0% lineage; telos gate:
  paraphrase-evadable, REVIEW→applied). Meanwhile the "commodity shell" we under-built **is** the
  differentiator.

## Relationship to existing substrate (this is an EXTENSION, not a parallel build)

This initiative wires together code that already exists. It must NOT create a new agent system, a new
registry, a new daemon, or a new memory store. It composes: `AgentRegistry` (self) + `PersistentAgent`
(body) + `AutonomousAgent` (brain) + the registration manifest (banks/summon) + `runtime_provider`
(the one canonical model door) + a small new **record→runtime bridge** + a human **talk** surface with
a **verification loop** baked in.

## Governance note (honest)

The repo's declared active track is "Runtime Truth Reconciliation," whose non-goals forbid new
daemons/stores. A `talk` surface is read-and-interact over existing owners (likely fine), but it is
**off the declared active track** — opening this lane is an explicit operator choice, recorded here.

---

## Addendum (2026-06-08) — new research findings folded in

Augmenting the dossier with what surfaced this turn. Full URLs preserved for future verification.

- **moltbook RESOLVED.** [moltbook.com](https://www.moltbook.com) is an AI-agent social network running the OpenClaw framework; 770k+ AI agents by late January 2026. Independent analyses warn it is a textbook **lethal-trifecta** environment: untrusted input, capable agents, and outbound action. See [Forbes 2026-01-30](https://www.forbes.com/sites/amirhusain/2026/01/30/an-agent-revolt-moltbook-is-not-a-good-idea/), [Vectra AI 2026-02-03](https://www.vectra.ai/blog/moltbook-and-the-illusion-of-harmless-ai-agent-communities), [ComplexDiscovery](https://complexdiscovery.com/moltbook-and-the-rise-of-ai-agent-networks-an-enterprise-governance-wake-up-call/), [Sophos 2026-05-11](https://www.sophos.com/en-us/blog/inside-the-lethal-trifecta-blast-radius-reduction-in-ai-agent-deployments). **Implication for us:** the first brick must include explicit prompt-injection scope and a refusal-to-act on contents pulled in from any A2A bus or external feed. Captured in 02_FIRST_BRICK_SPEC.md and as hygiene pattern VC-N03.

- **Fireworks GLM 5.1 + Opus 4.7 advisor pattern.** [Open-source agents with frontier advisors](https://fireworks.ai/blog/open-source-agents-frontier-advisors): 18/100 at $368 (open-source agent loop with a frontier model only as advisor on hard turns) beats Opus-only 14/100 at $954 on the same benchmark. **Implication:** the two-tier model-routing policy in 02_FIRST_BRICK_SPEC.md (cheap-default + escalate-on-uncertainty) is not a compromise; it is the current-best operating point.

- **Google Antigravity 2.0 + Managed Agents API (I/O 2026).** Productizes holon-as-cell at $0.08/session-hour on Gemini 3.5 Flash, scoring 76.2% on Terminal-Bench 2.1. **Implication:** the abstractions we are building have a commercial validator; we are not making up the shape.

- **Agentic Self-Learning (ASL), ICLR 2026.** [arxiv.org/pdf/2510.14253v1.pdf](https://www.arxiv.org/pdf/2510.14253v1.pdf). The GRM (generative reward model) co-evolves with the policy. Upgrade beyond DGM. **Implication:** the verification organ in 02_FIRST_BRICK_SPEC.md (and hygiene VC-N03) is on the ASL track, not the same-model-self-grading track.

- **NVIDIA Dynamo `--strip-anthropic-preamble`.** [Streaming tokens and tools, multi-turn agentic harness support](https://developer.nvidia.com/blog/streaming-tokens-and-tools-multi-turn-agentic-harness-support-in-nvidia-dynamo/). 5× TTFT reduction (168ms → 912ms → 169ms) via KV-cache reuse when the preamble is stable. **Implication:** identity separator drift (VC-N01) is not stylistic; every separator swap busts cache and 5×'es latency for that turn.

- **Anthropic prompt caching.** 90% cost reduction on cache hits, with 5-min and 1-hour cache options. **Implication:** same as above — stable name prefixes matter for the holon runtime's economics, not just its tidiness.

- **Cognition "don't build multi-agents" — confirmed.** [cognition.ai/blog](https://cognition.ai/blog/dont-build-multi-agents). Walden Yan's follow-up: write single-threaded; additional agents should add *intelligence* (different signal), not *actions* (more of the same). **Implication:** the dharma_swarm holon is single-threaded inside the cell; any second agent must be a different *model* serving as advisor (Opus → GLM) or a different *role* (verifier), not a second worker thread.

- **τ-bench pass^k metric.** [Sierra blog](https://sierra.ai/blog/benchmarking-ai-agents), [github.com/sierra-research/tau-bench](https://github.com/sierra-research/tau-bench). The right reliability metric is not pass@k but pass^k (probability of *every* run succeeding). **Implication:** the verification loop's acceptance criterion is "k consecutive successes on the same task," not "1 success out of k tries." Folded into 02_FIRST_BRICK_SPEC.md acceptance criterion #6.
