# MAP — Historical Sovereign-Holon Artifact Index

> **Authority notice (2026-08-03):** This is a June artifact index, not a current
> source-of-truth map. Start at the canonical subject doorway,
> [`../SARATHI.md`](../SARATHI.md), for current terminology, family boundaries,
> and evidence routes. The July estate map remains a dated deep reference only.
> Current implementation comes from code/tests; live state comes from onboarding.

**Created:** 2026-06-08 · **Purpose:** Preserve the original initiative's artifact trail.

This file records where the original design artifacts lived. Its paths and
status claims may be stale; current code, tests, and `../SARATHI.md` win.

> **Historical maintenance contract:** The original lane required updates here.
> New subject-level work updates the named canonical owner, not this corpus.

---

## In-folder artifacts (historical corpus)

Path: `docs/sovereign_holons/`

| File | Lines | Author | Role |
|---|---|---|---|
| [README.md](README.md) | ~100 | opus_composer + Dhyana | Index & verified-state summary; addendum of new 2026-06-08 findings |
| [INDEX.md](INDEX.md) | — | this turn | Master tracker — what to read in what order |
| [MAP.md](MAP.md) | — | this turn | This file — full artifact directory |
| [00_RESEARCH_DOSSIER.md](00_RESEARCH_DOSSIER.md) | 267 | opus_composer | Frontier landscape, gap analysis, 52-source research |
| [01_BUILD_GUIDE.md](01_BUILD_GUIDE.md) | 157 | opus_composer | Organ model, gaps, build sequence, open Qs |
| [02_FIRST_BRICK_SPEC.md](02_FIRST_BRICK_SPEC.md) | 241 | this thread | Executable bridge spec, 6 acceptance criteria, file:line evidence |
| [03_REGISTER_AS_HYGIENE.md](03_REGISTER_AS_HYGIENE.md) | 213 | this thread | VC-N01/N02/N03 hygiene patterns to make this initiative survive turnover |
| [04_FRONTIER_DOSSIER.md](04_FRONTIER_DOSSIER.md) | 388 | Wen (holon-agent worktree) | Per-agent `agent.seed.yaml` spine contract, 64-source ledger |
| [05_RECONCILED_PLAN.md](05_RECONCILED_PLAN.md) | 208 | Wen (holon-agent worktree) | Mike-first / Perplexity-second build sequence; 6-step implementation plan |

---

## Cross-folder pointers (canonical content lives elsewhere; this is the trail)

Do **not** copy these into `docs/sovereign_holons/`. They have legitimate homes elsewhere. This map is the trail back to them.

### The richest soul nest — Perplexity-Computer

Canonical location: `docs/agents/perplexity-computer/`

| File | Lines | Role |
|---|---|---|
| `SOUL.md` | 331 | Identity, axioms, lineage |
| `MEMORY.md` | 328 | What state survives wake cycles |
| `PROTOCOLS.md` | 347 | A2A / NATS / coordination contracts |
| `WAKE_CONTEXT.md` | 141 | Boot bundle for the persistent loop |
| `CAPABILITIES.md` | 135 | What this holon can actually do |
| `AUTONOMOUS_LOOP.md` | 450 | Wake / decide / act / sleep cycle spec |
| `HOFSTADTERIAN_LINEAGE.md` | 288 | Strange-loop self-reference design |
| `RECOGNITION_STANCE.md` | 344 | How it recognizes other agents |
| `AGNI_DEPLOYMENT.md` | 376 | Production deploy on the agni VPS |
| `samples/` | — | Sample artifacts (receipts, lessons) |

**Why it's the soul proof:** Perplexity-Computer is the richest, most complete repo-native nest. It's the shape proof for `agent.seed.yaml` (see [04_FRONTIER_DOSSIER.md](04_FRONTIER_DOSSIER.md)).

### The runtime-bridge proof — Mike + Qwen registrations

Canonical location: `examples/agents/`

| File | Role |
|---|---|
| `merge_master_mike.registration.json` | First runtime-bridge proof — complete `autonomy_policy`, narrow `authority`, summon contract |
| `qwen_code.registration.json` | Second registration showing the contract holds across agent types |

### Pinned code snapshots — the bridge's substrate

Canonical location: `reference/` (in Wen's holon-agent worktree; also present on `main` after merge)

| File | Lines | Why pinned |
|---|---|---|
| `agent_registry.py` | 980 | `load_agent` returns dict (line 329) — no runnable path |
| `persistent_agent.py` | 537 | Wake-loop body; **fail-open `_check_gate` (line 425)** |
| `autonomous_agent.py` | 1621 | ReAct brain; hardcoded PRESET_AGENTS |
| `external_agent_registration.py` | 510 | `autonomy_policy` documented as NOT runtime-enforced (line 140) |
| `runtime_provider.py` | 697 | Canonical model door; free-first ordering |
| `dgc_cli.py` | 2212 | `agent wake`/`list`/`runs` — no `agent talk` yet |
| `api_routers_agents.py` | 599 | `/agents/{id}/chat` cosmetic route at line 404 |
| `orchestrate_live.py` | 2257 | Hardcoded `PersistentAgent` construction paths |
| `INTERFACE_MISMATCH_MAP.md` | 165 | MM-02/03 coercion traps the bridge must avoid |
| `CLAUDE.md.project` | 267 | Active-track non-goals (what the bridge MUST NOT do) |

### Live registry / NATS state (not in repo, but referenced by the bridge)

| Path on operator's machine | Role |
|---|---|
| `~/.dharma/ginko/agents/` | 46 registered selves (identity.json, prompt_variants/, task_log.jsonl, fitness_history.jsonl) |
| `~/.dharma/a2a_bus/inboxes/<name>/` | NATS mailbox per agent |
| `~/.dharma/external_agents/<uid>/registration.json` | Runtime registration (Mike: present; Perplexity: missing) |
| `~/.dharma/agents/<uid>/living_agent.json` | Living dock |
| `~/.dharma/a2a/cards/<callsign>.json` | A2A card |
| `~/.dharma/proposals/sovereign_agent_holons.md` | Original proposal (2026-06-06) — superseded by this folder |

### Hygiene system home

Canonical location: `/Users/dhyana/dharma_swarm_pr_review_control/scripts/governance/hygiene/`

| Item | Status | Reference |
|---|---|---|
| Pattern `VC-N01` — Identity Separator Drift | proposed | [03_REGISTER_AS_HYGIENE.md](03_REGISTER_AS_HYGIENE.md) |
| Pattern `VC-N02` — Cosmetic Chat Endpoint | proposed | [03_REGISTER_AS_HYGIENE.md](03_REGISTER_AS_HYGIENE.md) |
| Pattern `VC-N03` — Verifier-Less Outcome Claim | proposed | [03_REGISTER_AS_HYGIENE.md](03_REGISTER_AS_HYGIENE.md) |

### Wen's holon-agent worktree (staging branch, not on main)

Branch: `worktree-holon-agent` · Path: `/Users/dhyana/.qwen/worktrees/holon-agent/` · Commit: `946e876e9`

| Artifact in worktree | Status in the historical corpus |
|---|---|
| `README.md` (reconciled plan) | Folded → `05_RECONCILED_PLAN.md` |
| `docs/frontier_dossier/FRONTIER_AGENT_DOSSIER.md` | Folded → `04_FRONTIER_DOSSIER.md` |
| `docs/sovereign_holons/{README,00,01}.md` | Already on `main` — same files |
| `reference/*.py` | Pointer-only (canonical lives in worktree until merge) |
| `examples/agents/qwen_code.registration.json` | Pointer-only (canonical lives in `examples/agents/`) |
| Root-level stub MDs (`MASTER_BUILD_SPEC`, `MODEL_ROUTING_MAP`, `FOUNDATIONS_TO_CODE_MAP`, `AGENT_IDENTITY_UNIFICATION`) | 3-line placeholders — not folded; if they grow, fold then |
| `CYBERNETIC_LOOP_MAP.md` (311 lines), `WHAT_IT_WANTS_TO_BECOME.md` (243 lines), `WORLD_MODEL.md` (132 lines) | Substantive but not yet validated against `main` — left in worktree; promote selectively after operator review |

---

## How to use this map

- **"Where do I add current Sarathi/Holon guidance?"** → update `docs/SARATHI.md` or the canonical owner it names; do not extend this historical corpus by default.
- The 07 overbuild spec is historical design input, not the current work queue. Re-establish any proposal against code, tests, the census, and active-track ownership.
- **"Where do I add a per-agent seed file?"** → `docs/agents/<agent-uid>/` (follow the perplexity-computer shape). Reference from this MAP, do not copy into the holons folder.
- **"Where do I add a new hygiene pattern?"** → `dharma_swarm_pr_review_control/scripts/governance/hygiene/patterns/` and update [03_REGISTER_AS_HYGIENE.md](03_REGISTER_AS_HYGIENE.md).
- **"Where do I check live runtime state?"** → run onboarding/`make organism-status`, then inspect `docs/state/LIVE_OPS_DASHBOARD.md`.
- **"What is the order to read?"** → start at [`../SARATHI.md`](../SARATHI.md); use [INDEX.md](INDEX.md) only for June history.
