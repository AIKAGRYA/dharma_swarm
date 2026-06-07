# PROD_READINESS_TOP10 — top-ROI initiatives to take dharma_swarm to production

**Status:** ACTIVE (seeded 2026-06-07)
**Owner:** @AmitabhainArunachala
**Companion:** `docs/governance/ACTIVE_TRACK.yaml` (current track), `docs/state/LIVE_OPS_DASHBOARD.md` (operator brief)
**Not authority:** this file is a *plan*. Authority for any individual item lives in its tracking issue and the canonical owner-doc listed alongside it.

## Reading guide

Each item is ranked by *leverage* (impact × inverse-effort relative to impact). The first three are the only items whose absence is currently blocking the claim "dharma_swarm is a production system." Items 4–10 are the table stakes once the foundation is honest.

Pattern across all ten: the repo has world-class governance scaffolding (anti-slop, guardian crew, interface mismatch map, active-track, broken register, CI gates) but several of those scaffolds are themselves drifting. The highest-ROI work over the next four sprints is to **make the existing gates honest** and **close the three real blockers behind them** before adding any new capability.

---

## 1. Guardian dedup leak — kill the false-issue stream  ✅ FIXED in #520

**Status:** done (this PR).

72 `[GUARDIAN] PalaceQuery.__init__() missing` issues plus 91 sibling stale-daemon issues (TelosGraph.get_by_name, TaskBoard.get_by_title, File-not-found-for-…) were filed in the last 30 days against contracts that already exist in the code. PR #520 fixes the root cause three ways:

1. Drops `__init__` rows from `_METHOD_EXISTENCE_CHECKS` — that check is meaningless because every class inherits `object.__init__` and dataclass/pydantic/attrs synthesize one.
2. Adds `_has_pydantic_base` + `_has_attrs_decorator` + `_has_synthesized_init` to extend the dataclass-recognition work from #383.
3. Defense in depth: any `__init__`-missing, `File not found for …`, or `Class … not found in …` finding is downgraded to WARNING at the call site, so a stale-checkout daemon can never spam GitHub issues again.

163 false issues closed alongside this PR. Restart the live Guardian daemon from a fresh `git pull` of main after merge.

**Tracking:** #520.

---

## 2. Close the apply gate (BR-003) — without it "evolution" is theater

**Severity:** BLOCKER. **Owner doc:** `docs/state/BROKEN_REGISTER.md` BR-003.

`DHARMA_EVOLUTION_SHADOW=1` is still the default; `evolution.py:2156` `apply_diff_and_test` has never crystallized a mutation. Last audit: 96 dryruns, 0 `applied` markers. The shadow-apply seam is in place (`tools/build_protocol/cli.py:shadow-apply`); end-to-end live-apply on a single canonical proposal behind an explicit env flip, with a rollback receipt in `~/.dharma/evolution/archive.jsonl`, is what promotes the DGC pillar from "shape-only" to "actually self-modifying."

**Definition of done:**
- One real live-apply commit reaches main via the apply gate.
- `archive.jsonl` shows `applied:true` (not just `shadow:true`).
- `DHARMA_EVOLUTION_SHADOW=0` documented for the canonical operator path.
- BR-003 moves to CLOSED with the apply-commit SHA as evidence.

---

## 3. Land Runtime Truth Spine *runtime* wiring — finish what 13/13 string-checks started

**Severity:** BLOCKER for `runtime-truth-reconciliation-2026-06`. **Owner doc:** `docs/state/LIVE_OPS_DASHBOARD.md`.

`LIVE_OPS_DASHBOARD` is explicit: the 13/13 acceptance criteria are file-presence-only and "do NOT prove runtime dispatch flows through the spine — the spine is defined but not yet wired through `agent_runner.py` or `orchestrator.py`." This is the single highest-leverage runtime change because every downstream truth packet (operator UI, reconciliation track #428, trace coverage gate #328) is derived from it.

**Definition of done:**
- `invoke_agent` is called on every dispatch path inside `agent_runner.run_task`.
- One real `EvidenceReceipt` is produced per dispatch and persisted via the canonical receipt adapter.
- Spine adoption metric (the metric the bot-PR-stream has been refreshing at 81.2% for days) actually moves because real receipts now exist.
- NEW-07 (trace_id across 54 stores) moves from PARTIAL to RESOLVED.

---

## 4. Split the top-7 god-modules — they're the source of every cascading break

**Severity:** structural. **Owner doc:** `xray_report.md`.

X-ray names the offenders: `thinkodynamic_director.py` (4,757 LOC / cc 786), `telos_substrate.py` (4,324), `evolution.py` (2,888 / cc 340), `agent_runner.py` (2,711 / cc 499, with one 596-line / cc-85 `run_task`), `swarm.py` (2,691 / cc 449, with a cc-88 `tick`), `providers.py` (2,676 / cc 481), `tui/app.py` (2,254 / cc 511).

PRs #389 (`provider_registry`), #390 (`storage_schema_registry`), and #391 (openapi-typescript codegen) are the right shape but landed as scaffolds. Finishing them eliminates the "swarm.py imports 55 internal modules" coupling that produces every BLOCKER on the interface-mismatch map.

**Definition of done:**
- `providers.py` ≤ 800 LOC; concrete providers live in `dharma_swarm/providers/<name>.py`.
- `agent_runner.run_task` decomposed into ≤ 6 helpers, each cc ≤ 20.
- `swarm.tick` decomposed similarly.
- Module-line-budget CI gate (`.github/workflows/module-budget.yml`) tightened to fail any module > 1,500 LOC.

---

## 5. Real test pyramid — coverage gating + executable contract

**Severity:** DEGRADED. **Owner doc:** `xray_report.md` (Test ratio = 72%).

638 test files but no published line/branch coverage number, and the interface-mismatch map admits pre-existing failures (`test_runner_fails_closed_for_tooling_task_on_api_only_provider`). The "Module Pair Status" table at the bottom of `INTERFACE_MISMATCH_MAP.md` is aspirational, not executable.

**Definition of done:**
- `pytest --cov` with a floor in CI, starts at today's number, gates +1pp/sprint.
- `coverage.xml` published as a CI artifact and a dashboard widget.
- `make test-smoke` reduced to a < 60 s contract test for every row in the Module Pair Status table.
- The known pre-existing failure either fixed or formally `xfail`-ed with a tracking issue.

---

## 6. Secrets hardening — currently one leaked `.env` from a full provider breach

**Severity:** prod-launch blocker. **Owner doc:** `.env.example`, `dharma_swarm/providers.py`.

`providers.py` reads 10+ API keys directly from `os.environ` (Anthropic, OpenAI, OpenRouter, NVIDIA, Groq, Ollama, Moonshot, Langfuse). `.env.example` ships literal key prefixes. `gitleaks` runs in CI but there is no rotation policy, no per-provider scope guard, and no fail-closed if a key is missing for a "critical-only" provider. Anti-slop Rule 6 (`providers-canonical`) admits known offenders including `autonomous_agent.py:468` (direct `from anthropic import AsyncAnthropic`).

**Definition of done:**
- A `SecretsBroker` shim that all providers (and `autonomous_agent.py`) go through — closes Rule 6 properly.
- Rotation receipts in `~/.dharma/secrets/` with operator UI.
- Per-call provider-scope logging so an exfil event shows up in the algedonic stream.
- `.env.example` ships placeholders only (no `sk-` / `gsk_` prefixes).

---

## 7. Observability — structured logs, traces, SLOs

**Severity:** DEGRADED. **Owner doc:** `INTERFACE_MISMATCH_MAP.md` NEW-07.

`LIVE_OPS_DASHBOARD`, `algedonic_signals.jsonl`, `runtime.db`, `archive.jsonl`, `task_board`, `runtime_state`, `telemetry_plane`, `stigmergy`, `traces`, `artifact_manifest`, `handoff` all write in parallel; NEW-07 says trace_id propagation is PARTIAL across 54 stores. Without unified traces, "did the swarm work last night?" requires an audit.

**Definition of done:**
- OpenTelemetry exporter behind a `plugin-sink` role (vocabulary already exists in `ANTI_SLOP_RULES.md` §Rule 2).
- One `trace_id` covers every cross-store row; CI fails any new store missing the column.
- Three SLOs published to the read-only ops cockpit (#465): task-completion latency p95, gate-block rate, provider-error rate.

---

## 8. Bot-PR + governance noise reduction — fix the signal/noise on PRs

**Severity:** DEGRADED. **Owner doc:** `.github/workflows/bot-pr-limit.yml`.

Last 24 h on `gh pr list`: 6 of the 8 newest PRs are `chore(governance): refresh spine adoption metric 81.2%` automated draft PRs stuck at the same percentage for 3+ days. PR #394 added `bot-pr-limit` but it is clearly not throttling correctly.

**Definition of done:**
- Cap automated metric-refresh PRs at one open at a time per metric (or roll into a single rolling PR), or replace with a daily direct commit to `main` against `metrics/`.
- Recovers ~80% of PR-review attention.
- Unblocks #428 (`runtime_state.py` split) which is the actual structural work.

---

## 9. Stop the doc sprawl — promote one canonical roadmap, archive the rest

**Severity:** DEGRADED. **Owner doc:** `README.md`, `docs/governance/ACTIVE_TRACK.yaml`.

Root contains `MASTER_BUILD_SPEC.md` (archived stub), `MODEL_ROUTING_MAP.md` (stub), `WHAT_IT_WANTS_TO_BECOME.md` (36k), `LIVING_LAYERS.md`, `CYBERNETIC_LOOP_MAP.md`, `WORLD_MODEL.md`, `LOOMWORK_v0_MASTER.md`, `GNANI_LODESTONE.md`, plus 27 dirs in `docs/` and 20M in `reports/`. BR-009 was "fixed" by archiving two but the root issue — agents don't know what to trust — is unresolved.

The fix is already half-built: `ACTIVE_TRACK.yaml` + `make onboard` is the right pattern. Enforce it.

**Definition of done:**
- Every root-level `.md` not referenced by `agent_onboard.py` archived to `docs/_archive/2026-06/`.
- `structure.yml` extended to fail PRs re-adding root `.md` files (Anti-slop Rule 8 already partially covers this).
- Onboarding agents converge on `make onboard` as the single door.
- BR-009/010/011/012 all close permanently.

---

## 10. Dashboard convergence + OpenAPI codegen — single product surface, typed end-to-end

**Severity:** prod-launch table stake. **Owner doc:** `PRODUCT_SURFACE.md`.

`PRODUCT_SURFACE.md` is unambiguous: the dashboard is the product. X-ray flags `qwen35/page.tsx` (2,209 LOC), `glm5/page.tsx` (1,794), `agents/[id]/page.tsx` (1,085), `CommandPostWorkspace.tsx` (1,214) — page-as-app monoliths that won't survive a real user. PR #391 scaffolded `openapi-typescript` codegen against `:8420/openapi.json`.

**Definition of done:**
- `npm run gen:types:check` gated in CI; build fails on type drift.
- Top-4 monolithic pages refactored into typed feature modules consuming the generated client.
- All API calls type-checked end-to-end (no `any`).

---

## Tracking

Each item above is shadowed by a GitHub issue. The active build track at any moment is one of these, declared in `docs/governance/ACTIVE_TRACK.yaml`. Closure is by the per-item "Definition of done" — not by editing this file.

| # | Item | Tracking issue |
|---|---|---|
| 1 | Guardian dedup leak | #520 (this PR) |
| 2 | Apply gate closure (BR-003) | #521 |
| 3 | Runtime Truth Spine runtime wiring | #523 |
| 4 | God-module split | #525 |
| 5 | Test pyramid + coverage gate | #527 |
| 6 | Secrets hardening | #529 |
| 7 | Observability — traces + SLOs | #531 |
| 8 | Bot-PR noise reduction | #533 |
| 9 | Doc sprawl collapse | #535 |
| 10 | Dashboard convergence + OpenAPI codegen | #537 |
