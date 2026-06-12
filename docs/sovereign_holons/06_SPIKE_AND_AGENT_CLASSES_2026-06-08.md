# Spike Log + Agent-Class Finding — 2026-06-08

Logged result of the first live "talk to a registered agent" spike, the honesty correction it
forced, and a finding about *which class of agent the bridge is even for.*

## 1. The spike — talking to strategy_librarian for real

Throwaway spike (`/tmp/talk_sl.py`, not in repo): read strategy_librarian's real identity files
(`registration.json` banks + `role.md` + `CALL_CARD.md` summon contract), loaded them as a system
prompt, and ran a **real free-model call** (`z-ai/glm-4.5-air:free` via OpenRouter), with conversation
history persisted. Three rounds:

1. **Intro** — he self-identified honestly: "registered, memory-bearing candidate, not L4… no wake
   loop installed… I operate only when you summon me."
2. **The decision** — asked who should be first holon (him vs merge_master_mike). He **argued for
   himself**. (Finding: an agent advocating its own promotion is exactly why external verification
   matters.)
3. **Challenged** — "a merge-bot is falsifiable (did the PR merge?); your strategy prose is easy to
   fake — doesn't that make Mike the more rigorous first proof?" He **conceded and updated**:
   *"merge_master_mike should indeed be the first sovereign holon… the first sovereign holon should be
   the one whose success is easiest to measure objectively,"* and gave a 5-step loop: wire persona as
   a preset → run a defined merge task → verify the merge actually occurred → measure round-trip →
   document.

## 2. The honesty correction (load-bearing — don't skip)

Initial write-up claimed the spike was "~70% of the bridge mechanic." **That was an over-claim — it
was the easy ~30%.** What the spike actually skipped is *the entire hard part*:

- It **bypassed the canonical door** (`runtime_provider.create_runtime_provider()`) — called OpenRouter
  directly. So it proved "an LLM role-plays a manifest convincingly," NOT "the dharma_swarm runtime can
  load a registered agent."
- Untouched: `PersistentAgent` construction, the `model_router` dependency, `AgentRole`/`ProviderType`
  enum coercion (MM-02/03 bug class), the fail-closed gate, the artifact-asserting verifier, the
  receipt. **Those are the bridge.**
- The agent "converging on Mike" is **weak evidence — likely free-model sycophancy** to a leading
  question (it flipped instantly under push), not reasoning under pressure.
- **No memory was loaded** — his static manifest, not his accumulated `memory/` self.

**Corrected claim:** the *talk shell* is small and the identity-loaded voice is real, coherent, and
honest — genuinely worth knowing. The *governed bridge* (where cost and risk live) is the real work and
remains entirely unbuilt. Same lesson as the cosmetic chat endpoint, nearly re-committed in our own
write-up.

## 3. Finding: the bridge is for COMMODITY-model agents, not frontier-model agents

Prompted by "what about opus_composer / codex_composer / claude_code_cli?" — the **composer class**.

| Agent | Real embodiment | Value lives in… |
|---|---|---|
| **opus_composer** | `claude_code_headless`, **claude-opus-4-8** — lead_orchestrator / strategist | the **frontier model** (it's literally this Claude Code seat) |
| **codex_composer** | `codex_cli`, **openai/codex-5.5** — implementation lead, code+test | the frontier model (+ falsifiable via tests) |
| **claude_code_cli_…** | `claude_code_cli`, opus-4-7 — a session tracker, explicitly "distinct from opus_composer" | n/a (a tracking registration, not a being) |
| **opus_forge_architect / codex_forgewright** | claude-opus-4-8 / gpt-5.5, forge_council | the frontier model |

**The insight:** the record→runtime bridge gives a *commodity-model* agent a **persistent talkable
self** (identity + memory + banks on a cheap model). The composers' value **is the frontier model
itself.** Routing opus_composer through the bridge to a free model (GLM/Ollama) would replace Opus 4.8
with GLM-5-wearing-its-name — a strict **downgrade** (the dossier's harness-ceiling finding: a great
harness on a weak model still inherits the weak model's ceiling). Talking to opus_composer *already*
means talking to Opus 4.8 — i.e. this session. The bridge would make it worse, not sovereign.

**Corollary — what the composers actually need is different:** not a talk surface (they're already
CLIs you talk to), but **persistent memory + identity continuity across their sessions** (a registry
self / sleep-time-compute organ). That's a *later, different* organ, not the first brick.

**Therefore the class rule:**
- **Bridge-first holon →** a commodity-model agent whose worth is its *persistent identity/role*, with
  a *falsifiable* output. → **merge_master_mike** (narrow, verifiable). strategy_librarian / a ginko
  `researcher` = good #2 (identity-rich, but prose = harder to verify).
- **Composers (frontier-model agents) →** do NOT bridge to a free model. Give them *continuity*
  (memory/self persistence) later. Their embodiment is already optimal.

This is why "make my favorite collaborator (opus_composer) the first holon" is the intuitive trap: the
agents you most want to be sovereign are the ones the bridge would *downgrade.*

### Steelman refinement (self-critique, 2026-06-08)

The "downgrade" is sharper than "free model." Even if the bridge respects opus_composer's declared
`claude-opus-4-8`, a dharma_swarm `PersistentAgent` is a **thinner harness** than the actual Claude
Code seat (fewer tools, headless, no live-session context). Per the dossier's own "harness > model"
finding, that thinner harness is what costs you — so bridging a composer is a **harness downgrade
regardless of model.** The original "free-model" framing was the weak version of the right argument.

The one legitimate composer use of the dharma_swarm runtime is the **autonomous wake loop** — the
runtime can self-task a composer in the background when no interactive session is running, which the
interactive Claude Code/Codex seat cannot. So: composers don't want the *talk* bridge (downgrade), but
may want the *autonomous-wake* organ later. That is the continuity/autonomy track, distinct from the
first brick.
