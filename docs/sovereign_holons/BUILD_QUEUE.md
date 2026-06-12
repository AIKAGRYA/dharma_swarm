# BUILD QUEUE — current state → 100% production holon

The high-level roadmap (`ROADMAP_TO_PROD.md`) composed into executable units. Each unit:
TDD verifier-first → implement → adversarial detonation → fix → fresh-context verify → next.
**No stop between units.** Operator gate only where marked 🔒.

Governance follows the **compass path (3a)**, operator-chosen: bounded pull, honestly labeled
"not an enforced fence." The hard PDP (3b) is deferred-by-design (5/30 pivot) until a tripwire
(real money / irreversibility / real autonomy) trips. The supervised `living_agent_kernel` merge
is needed ONLY for 3b, so the 2→3a→4→5 path builds autonomously without it.

| Unit | Step | Goal | Target | VerifyCmd | State |
|------|------|------|--------|-----------|-------|
| U0 | 2 | bridge module (load_holon, holon_reply, streaming) | `holon_bridge.py` | `pytest tests/test_holon_bridge.py` | ✅ DONE (12/12, detonated+hardened) |
| U1 | 2 | `get_holon_provider(holon)` — name→live provider | `holon_bridge.py` | pytest: resolves real ProviderType→config→provider | ✅ DONE (2026-06-09) |
| U2 | 2 | `/holon-chat` FastAPI route — streams `holon_reply`, logs `conversation_log(interface="holon")`, criterion #3 (no `_agentic_stream`) | `api/routers/holon.py` (NEW) | `pytest tests/test_holon_route.py` (TestClient + `_agentic_stream` sentinel) | ✅ DONE (2026-06-09, 6 route tests) |
| U3 | 2 | **LIVE SMOKE** — one real call to opus through the bridge | `tests/test_holon_live.py` (`@pytest.mark.network`) | live: non-empty in-character reply + conversation_log row | ◐ free-route live proof 2026-06-11 (`dgc agent talk` fallback receipts); opus/Max route still account-blocked |
| U4 | 3a | wire `_apply_compass_pull` (bounded telos pull, NOT a gate) into the holon path; label honest | `holon_bridge.py` / `holon_compass.py` | pytest: compass invoked+logged; asserts NO "enforced" claim | ✅ DONE (2026-06-09, non-binding, 4 tests) |
| U5 | 4 | `dgc agent wake <name>` — wake-loop for a *registered* holon (reuse `PersistentAgent`) | `holon_runtime.py` (NEW) + dgc CLI | pytest: N wake cycles, witness+receipt per cycle, budget-checked | ✅ CODE (shipped as `dgc agent run`; live longrun outside-session) |
| U6 | 4 | session persistence / replay (survive restart) | `holon_runtime.py` | pytest: kill→restart→resume from event log | ✅ CODE (restart/resume integration tests) |
| U7 | 4 | kill-switch (`dgc agent kill <name>`) | `holon_runtime.py` + dgc | pytest: kill mid-cycle → halts, no further actions | ✅ DONE (2026-06-11: `dgc agent kill` / `--clear` over `holon_killswitch`) |
| U8 | 5 | cost-cap ENFORCEMENT (reuse `budget.py`; raise on exceed, not just log) | `holon_runtime.py` | pytest: exceed cap → `CostLimitExceeded`, loop halts | ✅ CODE (mid-loop `spend_fn` enforcement under stubs) |
| U9 | 5 | health/SLO surface (reuse `control_surface` / `dgc status`) | reuse + thin adapter | `dgc status` shows holon row; pytest adapter | ◐ PARTIAL (`dgc agent status` + holon rows in `dgc agent list`; `dgc status` row pending) |
| U10 | 5 | eval-gate-as-CI (holon tests in `make governance-all`) | Makefile / CI | `make governance-all` includes holon suite, green | ✅ DONE (auto-collected by the default `tests/` suite) |
| U11 | 5 | 🔒 multi-holon (orchestrator + isolated subagents) + v1.5 self-evolution (DGM, bounded) — **deferred/optional** | — | — | deferred |
| 🔒 G1 | 3b | hard PDP/PEP (real fence) — needs supervised `living_agent_kernel` merge | operator-gated | the 6/1 semantic-paraphrase test | deferred-by-design |

**Definition of "100% production" for this build:** U1–U10 green (read-only talk → compass-governed →
persistent autonomous → reliable/operable), with U11/G1 explicitly deferred and *honestly labeled* —
not silently skipped. The fresh-context evaluator + the obey detonation gate decide done, never self-cert.

## Public CLI surface (2026-06-11)

The operator-facing surface for everything above is now `dgc agent`:

- `dgc agent talk <name> <message…> [--mode declared-first|free-first] [--max-tokens N]` — read-only talk as the holon itself; writes a `talk_receipts.jsonl` receipt with `routing_mode`, final `model`, and `fallback_from` provenance when the declared route fails.
- `dgc agent run <name> [--cycles N] [--mode …]` — governed wake cycles (kill → budget → work → compass → persist).
- `dgc agent status [name] [--json]` — read-only health projection (U9 partial).
- `dgc agent kill <name> [--reason …] [--clear]` — the U7 durable stop signal.
- `dgc agent list` — preset agents plus a "Registered sovereign holons" section for discoverability.

Routing doctrine enforced in code: `declared-first` honors the identity-declared model door and falls
back to the canonical low-cost chain on provider/account failure; `free-first` walks
`preferred_runtime_provider_configs()` (the single source of provider ordering) with the `claude_code`
door excluded — no hand-rolled provider lists (05_RECONCILED_PLAN non-negotiable).
