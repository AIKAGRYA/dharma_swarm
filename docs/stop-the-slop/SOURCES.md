# Sources — landscape survey (topic & angle seed, not a copy bank)

A scan of ~40 prompt banks / code-quality resources, surveyed for **topics and
angles** to widen the roadmap. **Sourcing ethics (non-negotiable, it's the brand):**

- **Open/permissive repos (MIT/Apache):** reference for *ideas, patterns, topic
  coverage*; if any wording is reused, attribute. We still rewrite to the Pramāṇa
  discipline (route-to-truth, return-clean, lineage, run-on-real-repo).
- **Paid / gated products (Vaylo, the €9.99 packs, marketplaces):** **topic signal
  only.** We do not lift their prompt text. Their existence tells us the market and
  the categories; nothing more.
- **Research papers:** cite as evidence/lineage.

## A. Open-source collections & awesome-lists (idea/pattern reference)

**Cursor / rules:**
- [PatrickJS/awesome-cursorrules](https://github.com/PatrickJS/awesome-cursorrules) — the canonical .cursorrules hub (framework-specific rules)
- [tugkanboz/awesome-cursorrules](https://github.com/tugkanboz/awesome-cursorrules) · [JhonMA82/awesome-clinerules](https://github.com/JhonMA82/awesome-clinerules) · [ivangrynenko/cursorrules](https://github.com/ivangrynenko/cursorrules) · [usrrname/cursorrules](https://github.com/usrrname/cursorrules) · [survivorforge/cursor-rules](https://github.com/survivorforge/cursor-rules)
- [tonynguyennvt/cursor-rules-awesome](https://github.com/tonynguyennvt/cursor-rules-awesome) — **72 topics incl. OWASP Top 10, SRE, 9 compliance frameworks (SOC2/ISO27001/HIPAA/PCI-DSS/GDPR)** → *compliance angle*

**Refactoring / review:**
- [craftvscruft/chatgpt-refactoring-prompts](https://github.com/craftvscruft/chatgpt-refactoring-prompts) — Ray Myers; letter-grades + code-smell lists → *grading angle*
- [baz-scm/awesome-reviewers](https://github.com/baz-scm/awesome-reviewers) — review prompts **mined from real OSS review feedback** → *review-pattern-mining angle*
- [PickleBoxer/dev-chatgpt-prompts](https://github.com/PickleBoxer/dev-chatgpt-prompts) · [ai-driven-dev/prompts](https://github.com/ai-driven-dev/prompts) · [continuedev/prompt-file-examples](https://github.com/continuedev/prompt-file-examples)

**Claude Code / agents:**
- [VoltAgent/awesome-claude-code-subagents](https://github.com/VoltAgent/awesome-claude-code-subagents) (100+) · [wshobson/agents](https://github.com/wshobson/agents) (48) · [rahulvrane/awesome-claude-agents](https://github.com/rahulvrane/awesome-claude-agents) · [supatest-ai/awesome-claude-code-sub-agents](https://github.com/supatest-ai/awesome-claude-code-sub-agents) · [milisp/awesome-chatgpt-claude-agents](https://github.com/milisp/awesome-chatgpt-claude-agents) · [JakesterMt/agent-prompts](https://github.com/JakesterMt/agent-prompts) · [jqueryscript/awesome-claude-code](https://github.com/jqueryscript/awesome-claude-code) · [lst97/claude-code-sub-agents](https://github.com/lst97/claude-code-sub-agents)
- [Piebald-AI/claude-code-system-prompts](https://github.com/Piebald-AI/claude-code-system-prompts) · [WesleyMaik/system-prompts-and-models-of-ai-tools](https://github.com/WesleyMaik/system-prompts-and-models-of-ai-tools) — leaked system prompts (structure reference)

**Security / architecture:**
- [doneyli/ai-agent-security-audit](https://github.com/doneyli/ai-agent-security-audit) — **5-phase AI-agent security audit (found 18 vulns)** → *agent-security angle (relevant to dharma_swarm itself)*
- [Alexanderdunlop/ai-architecture-prompts](https://github.com/Alexanderdunlop/ai-architecture-prompts) — **Eskil Steenberg's replaceable/modular interfaces** → *interface-replaceability angle*
- [ottosulin/awesome-ai-security](https://github.com/ottosulin/awesome-ai-security) · [piyushrajyadav/awesome-ai-dev-prompts](https://github.com/piyushrajyadav/awesome-ai-dev-prompts) · [eltociear/awesome-AI-driven-development](https://github.com/eltociear/awesome-AI-driven-development)

**Prompt-engineering meta:**
- [promptslab/awesome-prompt-engineering](https://github.com/promptslab/awesome-prompt-engineering) · [snwfdhmp/awesome-gpt-prompt-engineering](https://github.com/snwfdhmp/awesome-gpt-prompt-engineering)

**The slop category itself (direct competitors/validation):**
- [flamehaven01/ai-slop-detector](https://github.com/flamehaven01/ai-slop-detector) — "detects empty functions, fake docs, inflated comments" → *we already cover several; the meta-prompt is our flagship*

## B. Paid / gated / marketplaces — TOPIC SIGNAL ONLY (do not copy)

- **Vaylo Studios** (vaylostudios.com) — the kit that started this; gated (403)
- **"100 AI Prompts for Developers — Ship Code 10x Faster"** (€9.99) — uses a "CRTSE" framework (Context-Role-Task-Steps-Examples); structure signal only
- **[PromptBase](https://promptbase.com)** (largest marketplace) · **PromptHero** (search) · **[prompts.chat](https://prompts.chat)** (community)
- **[josecasanova.com — AI Code Slop Reviewer](https://www.josecasanova.com/prompts/ai-code-slop-reviewer)** · **[Larridin — AI Slop Index](https://larridin.com)** (5 signals: duplication ratio, 30/90-day revert rate, complexity-adjusted analysis, architectural coherence, test-behavior coverage) → *the flagship's signal set*

## C. Research (lineage / evidence)

- [arXiv 2601.16839](https://arxiv.org/pdf/2601.16839) — empirical AI-generated build-code quality
- [arXiv 2508.14727](https://arxiv.org/pdf/2508.14727) — quality & security of AI-generated code (**364 smells; Wildcard Usage #1 @ 97; dead code 34–42%**)
- [arXiv 2412.13801](https://arxiv.org/pdf/2412.13801) — PEFT for code-smell detection

**Added in v0.1 (new-dimension lineage):**
- **Tufano et al. (2025), Propensity Smelly Score (PSC)** — probabilistic, model-comparable smell propensity; AI code skews to god-classes/method bloat → grade structural smells as a distribution, expect the AI signature
- **Spracklen et al. (2025), package hallucination / "slopsquatting"** — 5–30% of LLM-suggested installs name non-existent packages; attackers pre-register them → `phantom-deps-audit` (a phantom import is a supply-chain attack surface, not a typo)
- **D'Ambros, Lanza, Robbes (2009), logical/change coupling** — git co-change predicts defects better than static coupling → `change-coupling-hotspots`
- **DeMillo, Lipton & Sayward (1978), mutation testing** — coverage proves a line ran, not that a test would catch a bug; the oracle gap = mutation-score deficit → measurable "test theater"
- **Campbell / SonarSource (2017), Cognitive Complexity** — nesting/breaks, not raw branch count, track comprehension → flat-dispatch vs nested-spaghetti distinction
- **Dhuliawala et al. (2023), Chain-of-Verification** — draft→verify-against-tool cuts hallucination → the "confirm with <tool>" step is the verification pass, not decoration

## What the survey added to the roadmap (new angles)

The topics are commodity; the survey's value is a few **angles we didn't have** — now
queued in `ROADMAP.md`:

1. **`ai-slop-index`** (flagship) — the meta-prompt: score AI-slop via *measurable*
   signals (duplication, complexity inflation, test-mirrors-implementation,
   architectural coherence, dead code, wildcard imports). The brand's keystone.
2. **`ai-agent-security-audit`** — prompt-injection / tool-permission / agent attack
   surface (directly relevant to dharma_swarm).
3. **`interface-replaceability-audit`** — Eskil Steenberg / Parnas: can an
   implementation be swapped without ripple?
4. **`wildcard-import-audit`** — the #1 measured AI smell.
5. **`test-mirrors-implementation`** — tests that assert structure, not behavior.
6. **`duplication-ratio-scan`** · **`complexity-inflation-scan`** — two core slop signals.
7. **`legacy-modernization-plan`** — risk areas + cleanup priorities + context pack.
8. **`compliance-pii-readiness`** — PII handling, retention, audit-log presence.
9. **`llm-call-hygiene`** — for codebases that *call* LLMs (token budget, injection,
   retries) — meta, and dharma_swarm-relevant.
