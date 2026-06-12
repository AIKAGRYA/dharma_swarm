# Build Guide — Sovereign Agent Holons

**Status:** DESIGN IN PROGRESS — pending (a) operator approval of the first-brick design and (b) the
widened research (Task `wa692029u`). **No implementation until the design section is approved**
(brainstorming hard-gate). This doc captures the frontier-informed direction so the build, when
greenlit, starts from ground truth.

---

## The organ model (target)

A sovereign holon = the existing 5 organs **wired together** + the missing **harness organs** the
2026 frontier says are the real differentiators (see `00_RESEARCH_DOSSIER.md`).

| # | Organ | Exists? | Source of truth |
|---|---|---|---|
| 1 | Evolving registry **self** | ✅ data only | `agent_registry.py` (`AgentRegistry`) |
| 2 | Autonomous wake-loop **body** | ✅ but registry-disconnected | `persistent_agent.py` (`PersistentAgent`) |
| 3 | Reasoning **brain** | ✅ | `autonomous_agent.py` (`AutonomousAgent`) |
| 4 | Registration manifest (**banks** + summon) | ⚠️ 2 agents | `examples/agents/*.registration.json` |
| 5 | NATS **mailbox** (cell-in-organism) | ✅ | `~/.dharma/a2a_bus/inboxes/` |
| 6 | **Record→runtime bridge** | ❌ MISS | *to build — the first brick* |
| 7 | Human **talk** surface | ❌ MISS (chat endpoint is cosmetic) | *to build* |
| 8 | **Verification loop** organ (separate Evaluator) | ❌ doctrine-only | obey detonation rule; gauntlet skeleton |
| 9 | **Context-bridging** harness (compaction + notes) | ⚠️ partial | MemoryKernel; wake loop |
| 10 | **Reliability** instrumentation (`pass^k`/GDS/meltdown) | ❌ MISS | replace empty `fitness_history` (τ-bench pass^k) |
| 11 | **Sleep-time compute** (idle memory reorganization) | ⚠️ timer only | `AgentCronScheduler` exists; lacks the reorg content (Letta) |
| 12 | **Pilot→prod triad** (observability + HITL + cost discipline) | ❌ MISS | the actual demo→production gap (only ~5% reach prod) |

> **Run-2 reinforcement (2026-06-08):** harness variance is **7.8× model variance** (arXiv 2605.23950) —
> organs 6/7 are empirically the biggest lever, not a "commodity shell." Anthropic's Managed Agents docs
> *productize the holon-as-cell* (context-isolated persistent worker threads) — strong validation of the
> direction. **Adversarial caution:** Cognition's "don't build multi-agents" warns multi-agent
> context-sharing *reduces* coherence — so **build the one great sovereign holon before the fleet.**

---

## The first brick — the record→runtime bridge (highest leverage on the whole frontier)

**One sentence:** a function that turns a *registered agent record* into a *running, governed,
model-backed agent you can talk to* — and a thin `talk` surface around it that leaves an inspectable
receipt.

### Shape (to be finalized in design)
```
load_agent(name) -> PersistentAgent
  # reads ginko/agents/<name>/identity.json + prompt_variants/active.txt + the
  #   registration.json (authority/autonomy_policy = the banks)
  # resolves model/provider via runtime_provider (free-first; default Ollama Cloud GLM-5)
  # constructs a PersistentAgent configured from THAT record (not hardcoded, not global)

talk <name>
  # boots load_agent(name), runs an interactive AutonomousAgent loop bound to the agent's banks
  # every turn: gate-check (real, fail-closed) -> act -> witness-log -> receipt
  # "done" = verifier/receipt written, not "the model said bye"
```

### Non-negotiables (from the dossier + the audits)
- **Route to a free live model by default** (Ollama Cloud GLM-5 / DeepSeek / NVIDIA NIM), never
  default to `claude_code` for a local sovereign agent (it crashes if the binary is absent).
- **Sovereign within the banks:** the agent's `autonomy_policy` (can/can't mutate telos/kernel/source,
  approval requirements) is loaded from its manifest and *actually enforced* at the talk boundary —
  not the paraphrase-evadable `REVIEW→applied` path. Start with a small fail-closed gate
  (ALLOW→act / BLOCK→reject / REVIEW→hold), explicitly better than the audited-broken one.
- **A verification loop is part of the organ from day one** — a separate Evaluator pass, because
  single-agent self-critique is unreliable (Epsilla/Anthropic). Reuse the obey detonation rule's
  spirit: the receipt is the proof, not the model's say-so.
- **Use existing classes only.** No new registry, daemon, memory store, or truth store. This is a
  bridge + a surface over `AgentRegistry` + `PersistentAgent` + `AutonomousAgent` + `runtime_provider`.

### Acceptance (the "I saw it work" bar, from the proposal)
Boot one governed agent locally with a free model → it loads its identity + memory → Dhyana talks to
it directly → it learns one lesson → it leaves one receipt that can be opened and inspected.

---

## Build sequence (draft — for the eventual implementation plan)

1. **`load_agent(name) -> PersistentAgent`** in/near `agent_registry.py` or a new thin
   `agent_loader.py` — the bridge. (TDD: a test that registers an agent, loads it, asserts the
   returned object carries the record's model/prompt/banks.)
2. **`talk` CLI/REPL** (e.g., `dgc agent talk <name>` — extend the existing `dgc` surface, do not mint
   a new entrypoint) that drives the loaded agent interactively, free-model by default.
3. **Fail-closed gate at the talk boundary** loading `autonomy_policy` from the manifest (the honest
   minimal gate, not the broken telos path).
4. **Receipt + witness** on every turn; an `open-receipt` affordance.
5. **A separate Evaluator pass** (verification organ) before a turn's action is considered done.
6. **First holon:** decide KARYA (register it fresh — richest soul, 1/5 organs) vs. merge_master_mike
   (4½/5 organs, narrow) vs. Mike-first-then-KARYA. *Pending operator decision; the bridge is the same
   regardless.*

---

## Open design questions (resolve in brainstorm before coding)

- Which agent is the **first** complete holon? (KARYA / merge_master_mike / Mike-then-KARYA.)
- Where does the bridge live — extend `agent_registry.py`, or a new `agent_loader.py`? (Prefer extend.)
- How much of memory is in-repo vs. a repo-managed store? (Earlier fork — leaning: definition in-repo,
  memory in a repo-managed store; revisit against the dossier's "naive memory hurts reliability"
  warning.)
- What is the *minimal honest* enforceable gate at the talk boundary (vs. the broken telos path)?
- Does the verification organ run inline (per turn) or as a separate Evaluator agent (decorrelated)?

---

## Governance flag (carried from README)

This is **off the declared active track** ("Runtime Truth Reconciliation"). A `talk` surface reads and
interacts over existing owners (likely fine), but opening this lane is an explicit operator choice.
Bind the implementation lane per `dharma_swarm/CLAUDE.md` rules (owner, branch/worktree, allowed
surfaces, verification command, receipt path) before broad edits.

---

## Critic pass (2026-06-08) — design risks to RESOLVE before any code

An adversarial design critic (sonnet, read-only) attacked this guide against the real repo. Nine
risks, with repo evidence. **These re-order the plan.**

| # | Risk | Evidence | Severity |
|---|---|---|---|
| 1 | `model_router` is **not** optional in practice — every real `PersistentAgent` gets a live router | `orchestrate_live.py:1609`; `persistent_agent.py:158` | HIGH |
| 2 | No clean `dict → PersistentAgent` path; `load_agent` returns a dict; enum coercion (`role`/`provider_type`) is the MM-02/03 bug class; identity.json and registration.json live in separate trees | `agent_registry.py:329`; `INTERFACE_MISMATCH_MAP.md` | HIGH |
| 3 | **`autonomy_policy` is documented as deliberately NOT enforced at runtime** — "without depending on runtime enforcement code reading the same fields back" | `external_agent_registration.py:136-141` | **CRITICAL** |
| 4 | KARYA-as-first = 8-10 authoring artifacts + unanswered questions (no ginko self, no manifest, persona doesn't map to the 2-field schema, worker-spawning has no mechanism); mike = ~2 | `~/.claude/agents/karya-*.md`; no `ginko/agents/karya/` | MED-HIGH |
| 5 | `talk` surface risks active-track non-goals if it touches orchestrate_live/swarm/agent_runner or mints a new receipt store | `CLAUDE.md` non-goals | MED |
| 6 | Existing `_check_gate` is **fail-OPEN** (returns `None` on exception → wake continues) — reusing it as "fail-closed" is a false claim | `persistent_agent.py:425-443` | MED-HIGH |
| 7 | Free-model default needs the explicit `preferred_runtime_provider_configs()` call; the default `resolve_runtime_provider_config()` is most-powerful-first → silently routes to Claude → crashes if binary absent | `runtime_provider.py:88-100` | MED |
| 8 | **Verification organ underdefined — strongest stall risk.** A same-model "did that work?" call is theater identical to the cosmetic chat endpoint | `witness.py` (closest analog); acceptance criterion | HIGH |
| 9 | 44/46 ginko agents have no registration.json — bridge needs an explicit missing-manifest policy (default-deny) | `examples/agents/` (2 files) | MED |

### Binding corrections (these override the draft above)

- **First holon = merge_master_mike, not KARYA.** Both critics + the substrate agree. Mike has a
  complete `registration.json` + real `AutonomyPolicy` + narrow understood authority. KARYA becomes the
  *second* holon once the bridge is proven. (Resolves build-sequence step 6.)
- **Descope the gate.** Do NOT claim to "enforce autonomy_policy better than telos" as a first brick —
  that is the unsolved PDP/PEP problem (`external_agent_registration.py:136-141`). First brick = a
  literal **default-deny** check on a single field (e.g. `requires_approval` / a missing-manifest →
  deny), called a *skeleton*, not a PEP. Honest acceptance: "we read one field and block," not "we
  enforce policy."
- **Fail-closed must be built in the talk layer**, not by reusing fail-open `_check_gate` — or patch
  `_check_gate` to raise (one line + test + track coordination).
- **Verification organ must assert a re-readable artifact**, not a model self-report. Acceptance
  upgrade: the receipt must contain a lesson written to a named file that a *separate process* can open
  and read; the verifier asserts that artifact exists. Name the verifier signature + pass-condition in
  the design before coding. This is the single check that keeps the build from repeating the cosmetic
  endpoint.
- **Route via `preferred_runtime_provider_configs()` explicitly**; add a new INTERFACE_MISMATCH_MAP
  entry for the free-first-vs-default-chain trap.
- **Reconcile the model-tier tension (from the dossier critic):** for the *first proof* consider a
  strong model so the demo isn't bottlenecked by GLM-5's ceiling; make "free-model default" a
  deliberate, separately-justified choice, not an assumed one.
- **Add prompt-injection defense to scope** — a holon that ingests external context without it is a
  security hole (absent from the research's 16 capabilities).
- **Write the 8-10 line `load_agent` skeleton first** (file reads + enum coercions + constructor call)
  to surface the missing-field decisions as code, before the implementation plan.
