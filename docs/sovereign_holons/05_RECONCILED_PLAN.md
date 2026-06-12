# Reconciled Implementation Plan — Mike first, Perplexity second

**Folded into single home:** 2026-06-08 · **Origin:** Wen's holon-agent worktree commit `946e876e9` · **Original path:** worktree root `README.md` at `/Users/dhyana/.qwen/worktrees/holon-agent/`

> Wen's worktree reconciled two research dossiers (the sovereign-holons "first brick" doc and the frontier-dossier spine doc) into one implementation plan. This file mirrors that plan into the canonical home so the build sequencing is co-located with everything else. It supersedes any earlier informal sequencing in the dossier or build guide.

**Cross-references inside this folder:**
- The bridge spec it implements: [02_FIRST_BRICK_SPEC.md](02_FIRST_BRICK_SPEC.md)
- The seed contract it adopts: [04_FRONTIER_DOSSIER.md](04_FRONTIER_DOSSIER.md)
- The hygiene patterns it protects: [03_REGISTER_AS_HYGIENE.md](03_REGISTER_AS_HYGIENE.md)
- The map of out-of-folder pointers (perplexity-computer nest, reference snapshots, registrations): [MAP.md](MAP.md)

---

# HOLON Agent — Record→Runtime Bridge

**Worktree:** `holon-agent` · **Branch:** `worktree-holon-agent` · **Created:** 2026-06-08
**Theme:** Reconcile two research dossiers into one implementation plan — build the bridge from agent record to governed runtime.

## What This Is

This worktree pulls together all the relevant work for the **sovereign agent holon** initiative — making dharma_swarm's registered persistent agents into holons you can talk to on their own terms. It is not a research artifact. It is an **implementation staging area** — a single place where both research dossiers, all key source files, and the two example agents live side-by-side so the bridge can be built.

## The Missing Thing

Both dossiers agree: dharma_swarm has pieces everywhere but no **record→runtime bridge**.

| What exists | What's missing |
|---|---|
| `AgentRegistry.load_agent()` → identity dict | No function that returns a runnable `PersistentAgent` |
| `PersistentAgent` (real wake-loop body) | Only constructed from hardcoded config in `orchestrate_live.py` |
| Dashboard chat endpoint | Cosmetic persona prompt over global model stream |
| `dgc agent wake` / `dgc agent list` | No `dgc agent talk` |
| `autonomy_policy` in registration.json | Deliberately NOT enforced at runtime |
| `_check_gate` in persistent_agent.py | Fail-open (returns None on exception → wake continues) |

## Structure

```
docs/
├── sovereign_holons/          # Build guide + research dossier (the sharper "first brick" doc)
│   ├── README.md              # Index — the organ model, verified gaps, governance note
│   ├── 01_BUILD_GUIDE.md      # The build sequence, non-negotiables, critic corrections
│   └── 00_RESEARCH_DOSSIER.md # Frontier landscape, gap analysis, 52-source research
├── frontier_dossier/          # Long-term spine architecture
│   └── FRONTIER_AGENT_DOSSIER.md  # Per-agent agent.seed.yaml contract, 64-source ledger
└── agents/
    └── perplexity-computer/   # Richest repo-native soul proof (SOUL, MEMORY, PROTOCOLS, WAKE_CONTEXT)

examples/
└── agents/
    ├── merge_master_mike.registration.json  # Complete autonomy_policy + narrow authority
    └── qwen_code.registration.json          # Second complete registration

reference/
├── agent_registry.py          # load_agent returns dict (line 329), no runnable path
├── persistent_agent.py        # Real wake-loop body, fail-open _check_gate (line 425)
├── autonomous_agent.py        # ReAct brain, hardcoded PRESET_AGENTS
├── external_agent_registration.py  # autonomy_policy documented as NOT runtime-enforced (line 140)
├── runtime_provider.py        # Canonical model door, free-first ordering
├── dgc_cli.py                 # agent wake/list/runs — no agent talk
├── api_routers_agents.py      # /agents/{id}/chat — cosmetic, line 404
├── orchestrate_live.py        # PersistentAgent construction paths (hardcoded)
├── INTERFACE_MISMATCH_MAP.md  # Known coercion/enum mismatch traps (MM-02/03)
└── CLAUDE.md.project          # Active track non-goals
```

## Reconciled Direction (operator decision captured here)

Both dossiers are directionally right. They disagree on first proof — this worktree resolves that:

| Dossier says | Reconciled decision |
|---|---|
| Sovereign holons: first holon = merge_master_mike | **Yes — first governed runtime-bridge proof** |
| Frontier dossier: first seed proof = perplexity-computer | **Yes — first rich repo-native soul/seed shape proof** |
| Long-term: per-agent `agent.seed.yaml` | **Adopted** |
| No new daemon/store/registry | **Adopted** |
| Mike-then-Perplexity | **Adopted** |

**Why Mike first:** He has external registration, autonomy_policy, living dock, A2A card, narrow authority, and a clear default-deny story — the fewest unanswered questions for a runtime enforcement proof.

**Why Perplexity second:** She has the richest repo-native nest (SOUL, MEMORY, PROTOCOLS, WAKE_CONTEXT, CAPABILITIES) — the best shape proof for the agent.seed.yaml contract. But her endpoint is `pending://manual` and her external registration record is missing from `~/.dharma/external_agents/`, so she is weaker as the first *runtime* enforcement proof.

## Implementation Plan (the bridge, in order)

### 1. AgentSeedResolver (read-only, no model calls)

A function that answers, given an `agent_uid`:

- Who is this agent?
- Where is its repo home?
- Where is its living dock? (`~/.dharma/agents/<uid>/living_agent.json`)
- Where is its external registration? (`~/.dharma/external_agents/<uid>/registration.json`)
- Where is its A2A card? (`~/.dharma/a2a/cards/<callsign>.json`)
- What authority fields exist?
- What pointers are missing?

**Acceptance:** resolves aliases, reports missing pointers explicitly, default-denies missing manifest/policy, no model calls, no writes except test fixtures.

### 2. agent.seed.yaml for merge_master_mike

Minimum Mike seed (shape from frontier dossier, content from existing registration):

```yaml
schema_version: dharma-agent-seed-v0
agent_uid: merge_master_mike
aliases: [merge-master-mike, mike, @MERGE_MASTER_MIKE]
repo_home: examples/agents

runtime_pointers:
  external_registration: ~/.dharma/external_agents/merge_master_mike/registration.json
  living_agent: ~/.dharma/agents/merge_master_mike/living_agent.json
  a2a_card: ~/.dharma/a2a/cards/merge-master-mike.json
  ginko_identity: ~/.dharma/ginko/agents/merge_master_mike/identity.json

authority:
  autonomy_level: bounded
  may_merge_when_gate_clean: true
  may_approve_prs: false
  may_write_source: false
  may_mutate_governance: false

model_routing:
  default_policy: free_first_decorrelated
  preferred_classes: [ollama_cloud, deepseek, nvidia_nim]
  fallback_classes: [paid_operator_approved]

talk:
  entrypoint: dgc agent talk merge_master_mike
  receipt_required: true
  evaluator_required: true

missing_docs: []  # honestly empty — Mike has no repo-native soul docs yet
```

### 3. dgc agent talk `<agent_uid>` --projection

Projection mode (no full PersistentAgent yet):

- Loads seed via resolver
- Prints identity + authority summary
- Refuses unknown/missing-policy agents
- Writes one conversation receipt
- Writes one lesson/artifact to a known path
- Labels itself **projection-only**

This proves the CLI → resolver → receipt seam without pretending the whole runtime body exists.

### 4. Artifact verifier (dumb, external-process friendly)

- Given a receipt path and expected artifact path
- Open the artifact from disk
- Assert it contains the session/agent marker
- Assert receipt points to it
- Fail if missing/unreadable
- **No same-model "looks good" evaluator**

### 5. Real runtime mode

Only after projection works end-to-end:

```
agent.seed.yaml → resolver → policy/model/context bundle → PersistentAgent
→ talk loop → receipt → verifier
```

**Acceptance:**
- Runtime uses seed-resolved identity, not global persona prompt
- Runtime uses explicit provider chain from `preferred_runtime_provider_configs()`
- Missing/unsafe policy blocks before action (fail-closed, not fail-open)
- Every turn writes a receipt
- Verifier can reopen the learned artifact from a separate process

### 6. Dashboard honesty

Either route `/api/agents/{id}/chat` through the same bridge, or rename/label it as projection chat. Do not leave it implying "talk to the real agent" when it is persona prompt over global stream.

## Non-Negotiables (carried from both dossiers + critic passes)

- **No new daemon, registry, memory store, or truth store.** Bridge + surface over existing owners.
- **No full policy engine claim.** First gate is a literal default-deny skeleton on one field (e.g. `requires_approval` or missing-manifest → deny), not a PEP.
- **Fail-closed in the talk layer**, not by reusing fail-open `_check_gate` (or patch `_check_gate` to raise).
- **Verification asserts a re-readable artifact**, not a model self-report. Separate process must be able to open it.
- **Route via `preferred_runtime_provider_configs()` explicitly.** Default chain routes to Claude → crashes if binary absent.
- **Free-model default is a deliberate choice, not an assumption.** The "7.8× harness variance" number does not hold at GLM-5 tier — harness raises the floor; model sets the ceiling.
- **Prompt-injection defense in scope.** A holon that ingests external context without it is a security hole.

## Two Proofs, Not One

| Proof | Agent | What it proves |
|---|---|---|
| **Governed runtime bridge** | merge_master_mike | Registration → resolver → fail-closed gate → receipt → verifier |
| **Rich repo-native soul/seed** | perplexity-computer | SOUL + MEMORY + PROTOCOLS + WAKE_CONTEXT → agent.seed.yaml shape |

Build Mike first as the bridge proof. Then build Perplexity's seed to validate the contract shape. Both use the same resolver, same seed contract, same verifier. The bridge is the same regardless.

## What's NOT in Scope

- Full policy enforcement engine (PDP/PEP unsolved — `external_agent_registration.py:136-141`)
- DarwinEngine self-improvement (0% lineage, needs measurement first)
- Fleet-scale multi-agent emergence (build one great holon before the fleet — Cognition's warning)
- New governance surfaces or truth stores
- A cosmetic "AI said it passed" verifier

---

*"The verifier must prove an artifact exists and can be opened by another process."*
*— Sovereign Holons build guide acceptance bar*
