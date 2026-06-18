# Model-Routing Consolidation — Run Report

**Branch:** `model-routing/consolidation-2026-06`
**Repo / worktree:** `/Users/dhyana/ds_model_pool`
**Goal spec:** `~/handoffs/MODEL_ROUTING_CONSOLIDATION_GOAL_2026-06-17.md`
**Run state:** **COMPLETE + FLOOR-DEMARCATED.** All surfaces migrated; the pool is now floor-aware with an unmistakable in-data demarcation. Guard GREEN, refined, **wired into pre-commit**, and committed.
**Guard green?** **YES** — `check_no_model_literals` exit 0, zero real model-id literals outside the pool.
**Verdict:** Branch is consolidation-complete, floor-demarcated, and self-defending. **Do NOT push or merge yet** — operator reviews the branch, runs the live E2E with real keys, then decides on merge.

---

## 0. Floor demarcation outcome (operator word 2026-06-17)

Operator word: *"sub-floor models can exist just for real grunt work only but ONLY
with a very clear demarcation."* That demarcation now lives in the **DATA**, not in
prose — commit `601853e34` (`model-pool: make the pool floor-aware with an
unmistakable demarcation`).

**The line:** `MODEL_POWER_FLOOR = "kimi-k2.6"` is declared once in
`evolution_roster.py` and re-exported by `model_defaults`, `model_hierarchy`, and
`model_pool` (single source — no second copy). `ModelSlot` and `ModelEntry` each
carry a `below_floor: bool`; the pool propagates it onto every entry
(`below_floor == True` iff a grouped slot is sub-floor).

**Floor entries are now in the pool, and they are the only path the picker/default sees:**

| Path | Source | Count | Members |
|------|--------|-------|---------|
| **FLOOR** (real path, `below_floor=False`) | `model_pool.floor_entries()` | **12** | claude-opus-4.8, claude-sonnet-4.6, gpt-5.5, gpt-5-codex, qwen3-235b-a22b, gemini-3-pro, kimi-k2.6, kimi-k2.7-code, deepseek-v4-pro, glm-5.1, minimax-m3, qwen3-coder:480b-cloud |
| **GRUNT** (sub-floor, grunt-only, `below_floor=True`) | `model_pool.grunt_entries()` | **18** | claude-opus-4, claude-sonnet-4, gpt-4o, kimi-k2.5, glm-5, deepseek-chat-v3-0324, qwen-2.5-coder-32b, mistral-large-2411, llama-3.3-70b, nemotron-ultra-253b, deepseek-r1, deepseek-v3.2, minimax-m2.7, gemma-3-27b, mistral-small-3.1, qwen2.5-coder:14b, deepseek-coder-v2:16b, llama3.2 |

Pool total = **30** = 12 floor + 18 grunt (the 26 sub-floor *slots* in the roster
group into 18 logical entries via casefolded `_logical_id`, so DeepSeek-V4-Pro and
friends group across providers). **Sub-floor entries were kept, not deleted** —
they remain reachable for genuine grunt work via the explicit `grunt_entries()`
opt-in.

**The picker / default path is FLOOR-ONLY.** `tui/model_routing.MODEL_TARGETS` is
a projection of `floor_entries()`: 10 floor-only targets, default chat brain
(index 1) = the FLOOR Claude `opus-4.8` on the Claude-Max oauth lane. Sub-floor
models are absent from the picker's main list and from every fallback chain.
`DEFAULT_MODELS` default-route compliance was tightened so no empty-model default
names a sub-floor id (OLLAMA glm-5 → glm-5.1, OPENROUTER k2.5 → k2.6).

**The demarcation has teeth — verified at runtime this session:**
- Partition is exhaustive and disjoint: `floor_entries() + grunt_entries() == MODEL_POOL`, every floor entry `below_floor=False`, every grunt entry `below_floor=True`.
- The picker's import-time guard `_validate_targets()` raises `AssertionError` if any target projects a sub-floor pool entry. Fed a **real sub-floor dispatch model_id** (`claude-opus-4-20250514`), it raised:
  `model_routing target 'leak-test' projects SUB-FLOOR pool entry 'claude-opus-4'; the picker's main list is FLOOR-ONLY …`
  (Note: the guard keys on provider-specific dispatch `model_ids`, the only form that can actually reach a dispatch — the logical `entry.id` is not a deployable string and is correctly a no-op.)

---

## 1. Final guard status

```
$ python3 scripts/uplift_guards/check_no_model_literals.py
check_no_model_literals: OK — no stray model-id literals outside the pool   (exit 0)
```

**GREEN.** Zero stray model-id literals remain outside `model_pool.py` across the entire
`dharma_swarm/` source tree. The pool (`dharma_swarm/model_pool.py`, seeded from
`evolution_roster.py`) is the single source of truth; every surface DERIVES from it.

The guard is now **wired** into the fail-closed pre-commit composition
(`scripts/uplift_guards/run_pre_commit.py`, `GUARDS` list, id `no-model-literals`) so drift
cannot re-accrete: a new vendor-prefixed (`moonshotai/…`, `z-ai/…`, `deepseek/…`, etc.) or
`:cloud` model-id literal outside `model_pool.py` now **blocks the commit**. Verified with teeth:
an injected drift literal (`moonshotai/kimi-k2.5-drift-test`) failed both standalone (exit 1)
and inside the composition (`✗ [no-model-literals]`); the guard returned green after removal.

---

## 2. Literals migrated: 84 → 0

| Stage | Real literals outside the pool |
|-------|-------------------------------|
| Guard introduced (commit `38eb679d3`) | **84** revealed across ~20 files |
| After false-positive refinement (`76d289294`) | 37 real literals, 4 confirmed false-positives excluded |
| After remaining surfaces migrated (`c5c420fa3`, `d8939880a`, `9daf31f07`, `f43c7e2fc`) | **0** |

The 4 false-positives are NOT migrated (they are not deployable model ids); they are excluded
surgically by a `(filename, snippet)`-keyed `FALSE_POSITIVES` set + an eval-only benchmark
candidate, never by blanket-allowlisting a file:

| Surface | Snippet | Why it is a FALSE POSITIVE |
|---------|---------|----------------------------|
| `agent_export.py` | `"qwen/agents"` | filesystem path component (export dir), not a model id |
| `identity.py` | `"meta/identity_history.jsonl"` | state-file path key in a `SUBSYSTEMS` dict |
| `providers.py` | `"nvidia/nemotron"` | `_PREFERRED_PREFIXES` substring token (`startswith`) — a bare family prefix |
| `providers.py` | `"google/gemma"` | same — `_PREFERRED_PREFIXES` substring token |
| `long_context_sidecar_eval.py` | `"moonshotai/Kimi-Linear-48B-A3B-Instruct"` (×2) | EVAL-ONLY benchmark candidate being *measured*, not a routing/dispatch target — must NOT be forced into the routing floor |

---

## 3. Surfaces done — all DERIVE from the pool

| Commit | Surface migrated |
|--------|------------------|
| `66293029e` | **Live-key filter** — `key_oracle.py` (`live_providers`); `providers.py` `_provider_chain` prunes dead-key providers. Fail-OPEN. |
| `c59017a2a` | **`model_pool.py` seeded from `evolution_roster`** — single source of truth (K2.6 Ollama-Cloud floor carried inside the pool). |
| `4f3d7fe7a` | **`DEFAULT_MODELS` + `runtime_provider.DEFAULT_*`** derived from the pool. |
| `99f3e8c48` | **`provider_matrix`** re-pointed to the pool + live oracle. |
| `1a463bae1` | **`tui/model_routing` + `terminal_bridge`** re-pointed; unroutable models rendered non-selectable. |
| `d1c5f7620` | **`provider_smoke` / `ollama_config` / `free_fleet`** frontier literals → pool generators. |
| `38eb679d3` | **No-model-literals CI guard** added (revealed 84 literals). |
| `19838d7ca` | **list-files** surface → pool at floor. |
| `bf0229515` | **certified-lanes** surface → pool at floor (kimi scout lane rides the K2.6 floor). |
| `fba9aa9de` | **agent-config** surface → pool at floor. |
| `0bdbb173b` | **ginko** surface → pool at floor. |
| `76d289294` | **Guard refinement** — 4 false-positives excluded by `(filename, snippet)` key. |
| `c5c420fa3` | **misc-surfaces** (scout_framework, startup_crew, external_agent_registration, tui adapters) → pool at floor. |
| `d8939880a` | **router_v1** → pool at floor. |
| `9daf31f07` | **model_manager** → pool at floor (`kimi-k2.5:cloud` sub-floor → `_cloud_id("kimi-k2.6")` FLOOR). |
| `f43c7e2fc` | **thinkodynamic_director** → pool at floor. |
| `7639b448e` | **Test baselines updated** for paid-down debt + K2.6 floor (see §4). |
| `1c93acafe` | **Guard wired** into `run_pre_commit.py`. |
| `0fd3b2414` | **E2E TUI verifier** — dry-run enumerates operable targets; `--live` drives `ds tui` + screenshots. |
| `601853e34` | **Floor demarcation** — pool is floor-aware (`below_floor` in data), `floor_entries()`/`grunt_entries()` split, picker is FLOOR-ONLY with an import-time guard. (see §0) |

**K2.6 floor honored:** no sub-floor string survives as a routing/dispatch target. `model_manager`'s
catalog now derives `_cloud_id("kimi-k2.6")`; the dashboard kimi scout lane (`certified_lanes.py`)
rides `moonshotai/kimi-k2.6` with label "Kimi K2.6 Scout". The only remaining `kimi-k2.5` strings
are inside the pool/roster (a legitimate live frontier-equivalent route, ranked below the floor)
and a `startswith("kimi-k2.5")` token-limit heuristic in `providers.py` (a substring check, not a
dispatch target).

---

## 4. Targeted test suite

```
python3 -m pytest tests/ -q -k "model or provider or routing or pool or hierarchy or runtime or director or ginko or router or manager"
```

**Result (post-floor-demarcation, this session): 7 failed, 2144 passed, 17 skipped,
9614 deselected, 2 xfailed, 4 xpassed** (~97s).

**NET-NEW failures: ZERO.** All 7 remaining failures were proven pre-existing by checking out
the branch base `8333e201c` in a clean detached worktree and running the same 7 node ids —
**identical 7 failures at base** (`7 failed, 1 passed` for that `-k` slice; the +1 is an
unrelated co-matched test). The floor-demarcation commit `601853e34` touched only its own
test files (`test_evolution_roster`, `test_model_pool`, `test_runtime_provider`,
`test_app_plan_mode`, `test_model_routing` — all GREEN) and **none** of the 7 failing test
files. The known pre-existing set:

- `test_provider_policy` ×3 (`…primary_driver_and_support_lane_contract`, `…prefers_tooling_lanes_when_requested`, `…swarm_role_allocation_is_deterministic`)
- `test_routing_surface_inventory` ×2 (`…inventory_matches_disk` — `create_runtime_provider` call-site list drift; `…autonomous_agent_exposes_model_router_and_codex_stays_direct`)
- `test_ginko_evolution::test_mutate_prompt_no_api_key` (environment key-leak: a live non-OpenRouter provider answers when the key is deleted)
- `test_ollama_config::test_default_local_model` (stale assertion: asserts a local default the config no longer carries)

**Two failures that this session FIXED** (they were the only net-new failures and PASSED at base,
so they were genuinely introduced by the migration and are now resolved, not masked):

- `test_model_key_routing_guard::test_model_literals_do_not_escape_canonical_registries` — the
  sibling debt-baseline guard. The migration paid down 18 baseline entries (24 literal
  occurrences) by moving them into the pool/roster; `KNOWN_MODEL_LITERAL_DEBT` was shrunk to match
  (93 → 69). **Zero net-new literals added** — debt strictly decreased.
- `test_dashboard_chat_router::test_chat_status_reports_runtime_settings` — the kimi scout profile
  now surfaces the K2.6 floor (`Kimi K2.6 Scout` / `moonshotai/kimi-k2.6`); the stale assertion
  pinning the sub-floor `Kimi K2.5 Scout` / `moonshotai/kimi-k2.5` was corrected to the floor.

---

## 5. Exact operator next action

1. **Review the branch** `model-routing/consolidation-2026-06` — 20 commits on base `8333e201c`
   (`git log --oneline 8333e201c..HEAD`). Spot-check `model_pool.py` (single source +
   `floor_entries()`/`grunt_entries()`), `evolution_roster.py` (`MODEL_POWER_FLOOR` +
   `below_floor` slot flags), `tui/model_routing.py` (FLOOR-ONLY `MODEL_TARGETS` + the
   `_validate_targets` import guard), `key_oracle.py` + `_provider_chain` dead-key pruning, the
   guard's `FALSE_POSITIVES` precision, and the K2.6-floor derivations in `model_manager.py` /
   `certified_lanes.py`.
2. **Run the live E2E with real keys** (no keys in this sandbox) to produce the operable /
   failed / unroutable routing matrix and confirm each pool entry's best-live-route resolves.
3. **Merge-or-not is the operator's call** after live-E2E-green. The guard is already wired, so
   the branch defends itself against re-drift from this point forward. The agent will **not**
   push or merge.

**Infra note (not in scope):** the `hotpath-ack` pre-commit guard reads
`repo_root/.git/COMMIT_EDITMSG`, but in a git worktree `.git` is a file pointer, so the
`[impact-checked]` commit tag is not seen inside a worktree — commits land via the
`DHARMA_UPLIFT_ACK=impact-checked` env var. Worth fixing so the tag works in worktrees.
