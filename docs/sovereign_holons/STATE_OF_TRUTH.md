# STATE OF TRUTH — Historical 2026-06-08 Snapshot

> **Superseded for current operations (2026-07-13):** This file accurately
> preserves a June audit, but its missing-body verdict predates the landed holon
> bridge/runtime work. Read
> [`../architecture/HOLON_RUNTIME_FULL_ESTATE_MAP.md`](../architecture/HOLON_RUNTIME_FULL_ESTATE_MAP.md)
> for current-main body synthesis, a dated witness, and remaining gaps; use
> onboarding/Live Ops for current operating state. Do not use the score below as
> a present-tense claim.

**Written:** 2026-06-08 (evening) · **Author:** opus_composer, by reading the actual source, not the docs
**Why this file exists:** Everything else in this folder describes what we *intend* to build. This file
is the one place that separates **what the docs promise** from **what the code already does** from
**what is actually wired up and runs**. It was written by reading the functions line-by-line with a
hostile verifier, because narration has outrun the build before.

---

## The one-paragraph truth

We are building a **sovereign holon**: taking a *registered persistent agent* (an identity on disk —
name, soul, memory, authority, banks) and giving it a path to **actually run as itself, under its own
gate and authority**, while still being a governed cell of the swarm. The **design is fully written
and now consolidated in this folder.** The **runtime is mostly not built.** Of the six pieces the design
calls "organs," **one is genuinely wired and working** (the model/provider door), **two exist but don't
enforce** (the gate fails open; the authority policy is never read at run time), **two exist only as
inert data** (the registry returns a dict nobody runs; only 5 hardcoded preset agents are reachable, not
the 15+ registered ones), and **the central piece — the bridge from a registration record to a running,
gated agent — does not exist at all.** Tonight's `talk_sl.py` spike proved you can *talk* to an agent by
feeding its identity as a prompt, but that path bypasses the gate, the authority limits, and the banks —
so it is the cheap shell, not the governed bridge.

---

## The map (verified 2026-06-08 against `/Users/dhyana/dharma_swarm/dharma_swarm/`)

| # | Organ | What the DOCS say | What the CODE actually is (file:line) | Wired & running? |
|---|-------|-------------------|----------------------------------------|------------------|
| 1 | **Agent registry** | "Load a registered agent and run it" | `agent_registry.py:329` `load_agent()` returns a **plain dict**. Callers (`agent_runner.py:2502/2632/3276`) use it for **metrics/logging only**. No path turns the dict into a running agent. | ❌ Data only — read, never run |
| 2 | **Wake loop + gate** | "Each cycle is telos-gated; unsafe actions blocked" | `persistent_agent.py:425` `_check_gate()` → **fail-open**: any exception `return None` (line ~442), and the caller treats `None` as "proceed." Gate is **advisory**, not mandatory. | ⚠️ Exists, **fails open** |
| 3 | **Reasoning brain** | "Any registered agent wakes with its own identity" | `autonomous_agent.py:1457` `PRESET_AGENTS` = **5 hardcoded** (researcher, coder, scout, reviewer, witness). A registered name like `strategy_librarian` falls through to a **generic stub identity** (`autonomous_agent.py:~1563`). The 15+ registered selves are **not reachable**. | ⚠️ Real for 5 presets, **not** for registered agents |
| 4 | **Authority / autonomy policy** | "A registered agent may only do what its policy allows" | `external_agent_registration.py:136` `AutonomyPolicy` is **validated at registration** (refuses dangerous flags) but its **own docstring says it is not read back at runtime**. Grep confirms: **zero** runtime reads of `autonomy_policy.can_*`. | ❌ Metadata only — never enforced on a running agent |
| 5 | **Model / provider door** | "Free-first model routing, live fallback" | `runtime_provider.py:158/434` `resolve_runtime_provider_config()` / `create_runtime_provider()` are **actually called** by the run path (`autonomous_agent.py:1584`, `thinkodynamic_director.py`, `consolidation.py`). | ✅ **Genuinely wired** — the one real organ |
| 6 | **THE BRIDGE** (record → running gated agent) | "First brick: turn `merge_master_mike`'s record into a running, gated holon" | **Absent.** No `SovereignBridge`, no `record_to_runtime()`, no `dgc agent run-registered`. `dgc agent` exposes only `wake`/`list`/`runs`, all **preset-only** (`dgc_cli.py:590-600`). | ❌ **Does not exist** |

Legend: ✅ wired & enforcing · ⚠️ exists but weak/partial · ❌ doc-only or absent.

**Score: 1 of 6 real-and-wired · 2 exist-but-don't-enforce · 2 inert data · 1 absent.**

---

## What this means for the build (step zero the plan currently skips)

The reconciled plan (`05_RECONCILED_PLAN.md`) is right about *what* to build, but it assumes a clean
single codebase. Two facts found by hand on 2026-06-08 change the first step:

1. **`living_agent_kernel.py` — the governance organ the "governed bridge" depends on — is NOT in the
   main repo at all.** It lives only in `dharma_capital_lab/` and `dharma_swarm_lak_e2e/` (both checkouts
   of the same GitHub repo), and those two copies have **drifted** from each other.
2. **The literal first-brick file, `external_agent_registration.py`, is forked**: 510 lines in
   `dharma_swarm/` vs. 527 in `dharma_capital_lab/`. ~40 top-level checkouts of the same repo exist.

So **step zero is "pick the canonical runtime and get `living_agent_kernel` into it"** — before writing
the bridge, decide which of the ~40 copies is the source of truth. The plan jumps straight to step one.

---

## The honest build sequence (corrected)

0. **Decide the canonical runtime worktree** and pull `living_agent_kernel` + reconcile the 510/527
   `external_agent_registration` fork into it. *(Not in the current plan — add it.)*
1. Write the **bridge**: a function/CLI (`dgc agent run-registered <name>`) that loads a registration
   record, resolves its provider (organ 5 ✅ already works), builds a `PersistentAgent` with the
   record's real identity, and starts its wake loop. *(Organ 6 — the absent piece.)*
2. **Make the gate mandatory**: remove the fail-open `except → return None` in `_check_gate` (organ 2).
3. **Enforce `autonomy_policy` at runtime**: read `can_*` before the agent acts (organ 4).
4. Make registered agents reachable (organ 3) — load identity from the registry, not `PRESET_AGENTS`.
5. Prove it on **`merge_master_mike` first**, then the richer Perplexity/seed shape.

When all five are done, organs 1–6 go green and the holon is real — not narrated.

---

## Provenance of this file

Every claim above was verified by reading source on 2026-06-08 via gitnexus + contextplus + direct read.
The gate fail-open and the `autonomy_policy`-never-read findings are the two load-bearing ones; both were
confirmed by quoting the exact code. If you change any of these files, re-verify and update this table —
this is the file that must never be allowed to drift from the code.
