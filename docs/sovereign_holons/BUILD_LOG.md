# BUILD LOG — sovereign holon

Real code, real verifiers, independently confirmed. No self-certified "done."

## 2026-06-09 — first code shipped: the bridge module (Step 2, unit 1 of ~3)

**Shipped + independently verified (fresh-context no-write evaluator → PASS, pytest 8/8 exit-0):**
- `dharma_swarm/holon_bridge.py` — `load_holon(name)` reads `~/.dharma/agents/<name>/` (canonical home) → `RunningHolon` with the agent's OWN model (`identity.json`) + system prompt (`prompt_variants/active.txt`, byte-for-byte, logged fallback). `build_request` routes through that model via a real `LLMRequest`. `guard_outcome_claim` refuses outcome claims lacking a `verifier_artifact` (anti-narration). `holon_reply` streams from the holon's own provider. **Does NOT import `living_agent_kernel`** (governance organ, Step-3 only) and **never calls `_agentic_stream`**.
- `tests/test_holon_bridge.py` — 8 tests = the hardened acceptance criteria #1/#2/#4: golden prompt match, fallback branch, missing-agent raise, **real opus_composer integration**, stub-model-routing (proves the model comes FROM identity), artifact-refusal (3 cases).

**Verifier (the longrun verifyCmd):** `cd ~/dharma_swarm && python3 -m pytest tests/test_holon_bridge.py -v` → 8 passed, exit 0.

**Honest scope of this unit:** the bridge *module* is built + verified. NOT yet done in Step 2: (a) the FastAPI `/holon-chat` route (criteria #3 no-`_agentic_stream` at the route layer, #5 confirmation header — deferred to read-only), (b) a **live-model smoke** (the routing test uses a *stub* by design — we have not yet spent tokens calling the real opus model end-to-end). So you cannot yet open a UI and talk to it — but the core that makes that possible exists and is verified.

**Not in canonical git yet** — new files in the working tree (git lock was stale; commit + lane when supervised). No existing code mutated; only two new files added.

**Adversarial detonation (3 decorrelated lenses) — found 5 real defects the green tests + confirmatory evaluator MISSED, all fixed + regression-tested (now 12/12 green):**
1. **CRITICAL (2 lenses converged):** `provider_type` was an UPPERCASE string (`"CLAUDE_CODE"`) — `ProviderType("CLAUDE_CODE")` *raises*; the stub test hid it. Fixed → valid lowercase value, validated against the enum, + 2 regression tests.
2. **DESIGN category-error:** the anti-narration guard was applied to the read-only path, where the agent has no tools and would refuse normal conversation ("I've *created* a model", "that's *done*") + forced non-streaming. **Removed from `holon_reply` → true token streaming + free conversation.** Guard retained as a documented Step-3 tool-boundary utility. ⚠️ *operator-ratify: guard moved, not deleted.*
3. UTF-8 BOM not stripped → `utf-8-sig` + test. 4. Malformed `identity.json` crashed ugly → clean `ValueError` + test. 5. Real-opus_composer test was CI-fragile → skips when absent.

**Lesson:** green tests + a confirmatory fresh-context evaluator both PASSED defective code, because the tests encoded a design flaw (the guard) and a stub hid the enum bug. Only the *adversarial* "find what's wrong" detonation caught them. This is the canonical reason a verifier-going-green is not a finish line.

**Open risk (next unit, not a current defect):** the bridge has STILL never run against a real provider. Lens 1 flagged `ClaudeCodeProvider` may reject `--model claude-opus-4-8` (the CLI manages model selection). Resolve in the live-smoke unit.

## 2026-06-09 (cont.) — /longrun: Step 2 (read-only bridge) COMPLETE in-session

Built unit-by-unit, TDD verifier-first, no stop between units. **17/17 tests green, independently verified, adversarially hardened.**
- **U1 `get_holon_provider(holon)`** — name→live provider (`ProviderType(holon.provider_type)`→`resolve_runtime_provider_config`→`create_runtime_provider`). +1 test.
- **U2 `/holon/{name}/chat` route** (`api/routers/holon.py`) — streams `holon_reply` from the holon's OWN model, logs `conversation_log(interface="holon")`, **never calls `_agentic_stream`** (sentinel test), 404s unknown. Wired into `api/main.py`; `/holon/{name}/chat` registered; `api.main` imports clean. +4 tests.
- **U3 live smoke** — `scripts/holon_smoke.py` (+ marked test). STAGED for **outside-session** run: `unset CLAUDECODE && python3 scripts/holon_smoke.py`. Cannot run in-session (CLAUDECODE blocks the Max `claude` CLI; the metered ANTHROPIC_API_KEY returns HTTP 400).
- **U10 eval-gate-as-CI** — the 17 holon tests are auto-collected by the default `tests/` suite → already part of `make test-all` / CI. Done by construction.

**Where the in-session autonomous build genuinely ENDS (real gates, not skimping):**
- **U4 (compass / Step 3a) BLOCKED:** `_apply_compass_pull` is NOT in the working tree — it's on the uncommitted `trust-build-compass` branch. Needs a supervised merge (like `living_agent_kernel`) or a reimplement decision.
- **U5–U8 (autonomous wake loop / persistence / kill-switch / cost-cap):** must NOT be built/run before governance exists (animate-after-govern principle) — and they execute outside-session anyway.
- **G1 (hard PDP / Step 3b):** deferred-by-design (5/30 pivot) until a tripwire trips.

**Net:** Step 2 — the read-only, talkable bridge — is built, hardened, verified, wired, and CI-gated. You can SEE it talk with one outside-session command.

## 2026-06-09 (cont.) — detonation refuted the premature stop; built 4 more units (32 tests green)

An adversarial detonation on my own "Step 2 done + 3 walls" stop-claim found **2 of 3 walls were convenient**, plus a false green. Harvested all of it:
- **Closed the false green:** added multi-turn-history threading test + provider-error-path test to the route. Step 2 now honestly complete (continuity + failure proven). 6/6 route tests.
- **U7 kill-switch** (`holon_killswitch.py`, 4 tests) — durable file stop signal the wake loop must honor. Pure signaling, no animation.
- **U8 cost-cap enforcement** (`holon_budget_guard.py`, 5 tests) — `CostLimitExceeded` raised when spend ≥ cap (the halt `economic_spine` lacks). Pure validation.
- **U4 compass / Step 3a** (`holon_compass.py`, 4 tests) — NON-BINDING telos signal reusing `ThinkodynamicScorer`; wired into the route best-effort. **Defining test: it never blocks/raises even on low alignment** (compass, not fence). Honestly labeled; the 3b fence stays deferred. *This satisfies "animate-after-govern" for the honest-compass path → U5 wake-loop code is now unblocked in-session.*

**Holon suite: 32 green** (13 bridge + 6 route + 4 kill-switch + 5 budget + 4 compass). Real compass signal: an opus-flavored telos reply scores telos_alignment 0.80.

**Genuinely remaining:** U9 (health/observability surface — buildable in-session); U5/U6 wake-loop body + persistence (CODE buildable in-session with stubs; the live RUN is outside-session); U3 live smoke + the running loop (outside-session, real `CLAUDECODE` constraint); G1/3b hard PDP (deferred-by-design). The supervised `living_agent_kernel` merge is needed ONLY for 3b — NOT for the compass path that's now built.

## 2026-06-09 (cont.) — autonomous Workflow built U9/U5/U6; detonation caught it was INFLATED; fixed

A background Workflow (7 agents, 495k tok) autonomously built U9 (health), U5 (wake loop), U6 (persistence) with per-unit mutation-tested verify — claimed "75%, 68 tests". **Independently verified 68 pass — then detonated on the agent-written code and found the 75% was inflated:** the classic per-unit autonomous-build failure — **isolated islands**:
1. **CRITICAL — wake loop ↔ persistence DISCONNECTED:** `holon_runtime.py` made zero calls to `holon_persistence`; the holon could NOT survive restart (0% on the defining property of a *persistent* agent).
2. **CRITICAL — budget gate was a FROZEN value:** `spent_usd` passed unchanged every cycle → could never trip mid-loop. "Mid-run budget governance" was cargo-cult.
3. **HIGH — runner exceptions bypassed governance:** no try/except around the agent call; a real model error would crash the cycle ungoverned.

**Fixed the keystone myself (delegation produced islands):** wired persistence into the loop (resume at cycle N+1), added an injected `spend_fn` so budget is re-evaluated each cycle (real mid-loop enforcement), and made runner exceptions governed into `halted:error`. +6 integration regression tests proving: restart continuity `[0,1,2,3,4]` + `resume_point=4`, budget halts mid-loop on accumulating spend, runner exception → `halted:error` not a crash. **74 holon tests green; the loop now genuinely COMPOSES** kill+budget+work+compass+persistence.

**Honest state:** CODE is now ~80% and *coherent* (composes + survives restart, under stubs). The **LIVE autonomous run is still 0% proven** — a real model, real `economic_spine` spend wired to `spend_fn`, the launchd plist, multi-holon, real-world hardening — all outside-session (`CLAUDECODE`). The lesson, logged: autonomous per-unit builds produce plausible-but-disconnected code; only adversarial integration-detonation catches it. Never trust an autonomous build's self-reported %.
