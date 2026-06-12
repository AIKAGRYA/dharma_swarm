# AGENT-HOME RECONCILIATION — "all agents at one obvious place"

**Date:** 2026-06-09 · **Trigger:** operator caught the spec assuming agents live at `~/.dharma/ginko/agents/` when the chosen first holon (opus_composer) lives at `~/.dharma/agents/`. Directive: *"fix that and any and all assumptions. all agents should live at a more obvious place."*
**Method:** 3-lens audit + integrator (agent-home fork ∥ spec assumptions ∥ code-path surface). 29 assumptions checked: **15 confirmed, 8 wrong.**

---

## The fork (verified)

| Home | Dirs | Who uses it | mtime |
|------|------|-------------|-------|
| `~/.dharma/agents/` | 41 | `roaming_onboarding.py:142` (canonical onboarding) + opus_composer / strategy_librarian / merge_master_mike | Jun 6 10:12 |
| `~/.dharma/ginko/agents/` | **46** | `AgentRegistry` default (`agent_registry.py:201`) + 10+ `ginko_*` modules + `agent_runner.py` + `neural_consolidator.py` + `graphql_router.py` | Jun 6 10:56 (**newer**) |
| `~/.dharma/external_agents/` | 15 | hermes / codex / CLI workers (sandbox isolation) | — keep separate |

**The code disagrees with itself:** the *forward* convention (roaming onboarding) writes `agents/`; the *bulk* of live code reads `ginko/agents/`. opus_composer is in `agents/`; the registry looks in `ginko/agents/`.

## Recommendation

> **✅ DECISION (2026-06-09, operator):** Canonical home = **`~/.dharma/agents/`**. Two tracks follow:
> - **Holon build (now unblocked):** `load_holon` reads `~/.dharma/agents/<name>/` — opus_composer is already there, so spec criteria #1/#2 are satisfiable. No migration needed to *read* the holon.
> - **Full consolidation (separate, supervised hygiene):** repoint the 10+ `ginko_*`/registry modules + migrate the 46-dir `ginko/agents` tree onto `agents/`. This does NOT gate the holon read-only v1; it's its own cleanup, sequenced when the operator can watch + git is free.

**Canonical = `~/.dharma/agents/`** (the obvious name; code-intent-aligned via `roaming_onboarding.py`). Migrate `ginko/agents/` → `agents/`. Keep `external_agents/` separate.

**HONEST CAVEAT — this is NOT a clean 5-file fix:**
- **10+ modules** hardcode `ginko/agents`: `agent_registry.py:30/201`, `ginko_agents.py`, `ginko_evolution.py`, `ginko_orchestrator.py`, `ginko_regime.py`, `ginko_brier.py`, `ginko_signals.py`, `ginko_sentiment.py`, `ginko_attribution.py`, `ginko_audit.py`, `agent_runner.py:890/1109/1117`, `neural_consolidator.py:398`, `graphql_router.py:265`.
- `ginko/agents` is **newer and has 5 dirs NOT in `agents/`** → a blind merge could orphan them. **Per KILL-NOTHING: compost the source, verify, then retire — never blind-delete.**
- `agent_registry.py` is mirrored across **5 worktrees**; `get_blast_radius` before touching the default.
- The `ginko_*` family is the **trading/evolution subsystem** — repointing it is system-wide, full-suite-test territory (`pytest tests/ -q`, ~6 min), under watch.

**The decision is genuinely yours:** `agents/` (obvious name, but ~10-module churn across the ginko trading stack) **vs** accept `ginko/agents` as de-facto canonical (less churn, keeps the opaque name you dislike). Code intent says `agents/`; I can't trade "obvious naming" vs "churn risk" for you.

---

## The 8 wrong assumptions (logged; his instinct was right)

1. **ginko path** — spec criterion 1 reads `~/.dharma/ginko/agents/opus_composer/active.txt`; file exists ONLY at `~/.dharma/agents/opus_composer/`. *(the one you caught)*
2. **`provider.stream_completion()`** — used in a verifier; exists NOWHERE in the repo. Real: `provider.stream(LLMRequest)` / `complete_via_preferred_runtime_providers` (`runtime_provider.py:604`).
3. **hardcoded `claude_haiku_4_5` fallback** — forbidden; use identity model + live `resolve_runtime_provider_config` fallback.
4. **new `~/.dharma/holon_witness/` tree** — violates active-track non-goal; reuse `~/.dharma/witness/`.
5. **merge_master_mike as first holon** (`05_RECONCILED_PLAN:52,80`) — superseded by opus_composer (`BUILD_STEP_ZERO`).
6. **build deliverables mislabeled as existing-state** (`holon_bridge.py`, `RunningHolon`, `POST /holon-chat` at spec :129-152) — these are to-build, not assumptions.
7. **`graphql_router.py:265`** — hardcodes `~/.dharma/ginko/agents/...` via `os.path.expanduser`, bypassing its own `GINKO_AGENTS_DIR` var (line 86) and `dharma_state_dir()`; breaks if `DHARMA_HOME` set.
8. **`AgentRegistry` default = `ginko/agents`** — the system-wide deviation that holds the whole fork in place.

## Supervised substrate tasks (the real migration — NEVER auto-run)

1. Repoint `AgentRegistry` default (`agent_registry.py:30/201`) → introduce `AGENTS_DIR = state_dir/'agents'`. `get_blast_radius` first (5 worktrees); test `test_agent_registry.py` + `test_ginko_agents.py`.
2. Migrate `ginko/agents/` (46) → `agents/` (41), reconciling the 5 unique dirs; archive `ginko/tournament_history.jsonl` first; compost source.
3. Fix `graphql_router.py:265` → use `GINKO_AGENTS_DIR` or delegate to `AgentRegistry.load_agent` (hot router path → dual-audit).
4. Edit the 10+ `ginko_*` / `agent_runner` / `neural_consolidator` hardcoded paths; full suite under watch.
5. Merge `living_agent_kernel.py` into main (BUILD_STEP_ZERO #3).
6. Port the 17-line `identity_invariant` delta (`external_agent_registration.py` 510→527).

## Doc fixes (safe, applied/superseded via the spec correction banner)
The 8 spec/plan citation+path corrections are captured in `02_FIRST_BRICK_SPEC.md`'s correction banner (top) + the v1 build-ready appendix (bottom), which are authoritative over the original body.
