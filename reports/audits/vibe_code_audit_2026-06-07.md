# Vibe-Code Audit Report — dharma_swarm

**Date:** 2026-06-07
**Auditor:** Devin (Cognition AI) — session `7c5c93b8`
**Repo:** `AmitabhainArunachala/dharma_swarm` @ `fc2200758c` (main)
**Codebase:** 674 Python source files (285,749 LOC), 644 test files (179,929 LOC)
**Companion:** [`VIBE_CODE_ANTIPATTERNS_FIELD_GUIDE.md`](../../docs/governance/ANTI_SLOP_RULES.md) (anti-slop rules)

> **Role:** `report` — dated descriptive output. This document does not claim
> authority; it subordinates to `docs/governance/ANTI_SLOP_RULES.md` and
> `docs/governance/SOVEREIGN_MANIFEST.md`. See `docs/governance/CANONICAL_DOC_STACK.md`.

---

## Section 1 — Test Quality (Q1–Q6)

### Q1 — Positive-to-exception assertion ratio
- **Severity:** hygiene
- **Finding:** 42.7:1 (15,507 positive vs 363 exception-shape)
- **Evidence:**
  - `grep -rnE 'assert.*==' tests/` → 15,507
  - `grep -rnE 'pytest.raises|assertRaises' tests/` → 363
- **False-positive risk:** low — the ratio genuinely signals under-tested error paths
- **Recommendation:** Add `pytest.raises` tests for the top 10 most-called functions that declare exceptions in their docstrings.

### Q2 — Weak-only assertion test functions
- **Severity:** structural
- **Finding:** 254 test functions whose ONLY assertion is `assert result`, `assert x is not None`, or `assert len(x) > 0`
- **Evidence:**
  - `tests/test_cascade.py`: 28 funcs
  - `tests/test_evolution.py`: 23 funcs
  - `tests/test_selector.py`: 16 funcs
  - `tests/test_telos_gates.py`: 15 funcs
  - `tests/test_context.py`: 12 funcs
  - `tests/test_kaizen_stats.py`: 11 funcs
  - `tests/test_monitor.py`: 10 funcs
  - `tests/test_quality_gates.py`: 10 funcs
  - `tests/test_anekanta_gate.py`: 8 funcs
  - `tests/test_cli.py`: 7 funcs
- **False-positive risk:** medium — some may legitimately only need existence checks, but 254 is excessive
- **Recommendation:** Audit the top 5 files; replace weak assertions with structural checks on return shape, keys, types, or values.

### Q3 — Mock-to-integration test ratio
- **Severity:** structural
- **Finding:** 4,685 `MagicMock`/`patch`/`mock_` references; **0 integration test files** (`tests/integration/` does not exist)
- **Evidence:**
  - `grep -rnE 'MagicMock|patch|mock_' tests/` → 4,685
  - `find tests/integration/ -name '*.py'` → 0
- **False-positive risk:** none — the directory genuinely does not exist
- **Recommendation:** Create `tests/integration/` with at least 3 smoke tests covering the full dispatch path (spine → orchestrator → provider → receipt).

### Q4 — Tests importing production helpers for expected values
- **Severity:** hygiene
- **Finding:** 590 test files import from `dharma_swarm`
- **Evidence:**
  - `grep -rl 'from dharma_swarm' tests/ | wc -l` → 590
- **False-positive risk:** high — most imports are necessary to instantiate the SUT; only a subset recompute expected values from production code
- **Recommendation:** Spot-check the top 10 files for oracle contamination (where tests import production logic to compute expected outputs). Low priority.

### Q5 — Mutation testing score
- **Severity:** hygiene
- **Finding:** Never run. No `mutmut`, `cosmic-ray`, or `stryker` config found.
- **Evidence:**
  - `find . -name 'mutmut*' -o -name '.mutmut*'` → empty
  - `grep -r 'mutmut' pyproject.toml Makefile .github/` → empty
- **False-positive risk:** none
- **Recommendation:** Run `mutmut run --paths-to-mutate=dharma_swarm/spine/ dharma_swarm/telos_gates.py dharma_swarm/ontology.py` as a first pass on the 3 highest-invariant modules.

### Q6 — `time.sleep()` in tests
- **Severity:** cosmetic
- **Finding:** 30 `time.sleep()` calls across tests
- **Evidence:**
  - `tests/test_diff_applier.py:389` — `time.sleep(10)` (in a subprocess command string)
  - `tests/test_pr_merge_control.py:196` — `time.sleep(5)`
  - `tests/test_agent_memory_manager.py:289` — `time.sleep(1.1)`
  - `tests/test_jikoku_samaya.py:263` — `time.sleep(0.4)`
  - `tests/test_signal_bus.py:34` — `time.sleep(0.15)`
- **False-positive risk:** medium — some sleeps simulate real timing behavior intentionally
- **Recommendation:** Replace with `asyncio.sleep` or `freezegun`/`time-machine` where the sleep is purely for sequencing.

---

## Section 2 — Documentation (Q7–Q11)

### Q7 — README quickstart accuracy
- **Severity:** structural
- **Finding:** 6 of 6 `make` targets listed in README's "Common Commands" section **do not exist** in the Makefile
- **Evidence:**
  - README lists: `make xray`, `make compile`, `make test-smoke`, `make test-all`, `make dashboard-lint`, `make dashboard-build`
  - Makefile has: `make test`, `make test-fast`, `make lint` (different names)
  - `grep -c 'xray\|test-smoke\|test-all\|dashboard-lint\|dashboard-build\|compile' Makefile` → 0
- **False-positive risk:** none — the targets are genuinely absent
- **Recommendation:** Either create the 6 aliased targets or update README to match the actual Makefile targets (`test`, `test-fast`, `lint`).

### Q8 — Docstring inflation
- **Severity:** cosmetic
- **Finding:** clean — 0.60:1 docstring-to-def ratio, mean 4.9 lines per docstring
- **Evidence:**
  - 10,903 `def`/`class` blocks, 6,543 docstrings
- **False-positive risk:** none
- **Recommendation:** No action needed. Docstrings are appropriately sized.

### Q9 — Dead intra-repo markdown links
- **Severity:** structural
- **Finding:** **390 dead links** out of 1,173 intra-repo markdown links (33%)
- **Evidence:**
  - `README.md → AGENTS.md` (missing at root)
  - Bulk dead links in `reports/architectural/strange_loop_swarm_20260314/` — absolute paths like `/Users/dhyana/dharma_swarm/...` that never worked outside the original author's machine
  - 370+ additional broken references
- **False-positive risk:** low — absolute `/Users/dhyana/...` paths are genuinely broken
- **Recommendation:** Run a batch fix: convert absolute paths to repo-relative paths; delete or archive reports with >50% broken links.

### Q10 — Auto-generated vs hand-written docs ratio
- **Severity:** cosmetic
- **Finding:** 0 auto-generated LOC, 144,382 hand-written docs LOC
- **Evidence:**
  - No `docs/api/`, `site/`, or `_build/` directories exist
- **False-positive risk:** none
- **Recommendation:** No action needed.

### Q11 — Spec erosion
- **Severity:** hygiene
- **Finding:** Cannot reliably measure — git clone mtimes are unreliable. Noted: `docs/governance/ACTIVE_TRACK.yaml` TTL mechanism actively mitigates spec erosion.
- **Evidence:**
  - Track TTL: 3/14 days used (fresh)
  - Axiom A6: "Docs decay; verify numbers before citing"
- **False-positive risk:** N/A
- **Recommendation:** The existing TTL and A6 governance mechanisms are sufficient.

---

## Section 3 — Module Structure (Q12–Q16)

### Q12 — Files exceeding 1000 LOC
- **Severity:** structural
- **Finding:** **25 files** exceed 1000 LOC. Top 10:
- **Evidence:**
  - `thinkodynamic_director.py`: 5,173 LOC
  - `telos_substrate.py`: 4,512 LOC
  - `runtime_state.py`: 3,796 LOC
  - `evolution.py`: 3,465 LOC
  - `agent_runner.py`: 3,355 LOC
  - `swarm.py`: 3,227 LOC
  - `providers.py`: 3,022 LOC
  - `orchestrator.py`: 2,777 LOC
  - `terminal_bridge.py`: 2,539 LOC
  - `tui/app.py`: 2,520 LOC
- **False-positive risk:** none — Rule 10 already tracks grandfathered modules
- **Recommendation:** `runtime_state.py` (3,796 LOC) is NOT in the grandfathered list but exceeds 1000 LOC. Add it or decompose it. Also `ontology.py` (2,416), `orchestrate_live.py` (2,257), `operator_bridge.py` (1,819), `tui_legacy.py` (1,795) are absent from the allowlist.

### Q13 — Import cycles
- **Severity:** structural
- **Finding:** **11 import cycles** (SCCs with >1 module)
- **Evidence:**
  - Cycle 1 (4 modules): `router_v1 → smart_router → swarm_router → provider_policy`
  - Cycle 2 (2 modules): `providers → runtime_provider`
  - Cycle 3 (2 modules): `engine.retrieval_feedback → engine.hybrid_retriever`
  - Cycle 4 (9 modules): `revenue.telic_bridge → ontology_hub → ontology_runtime → lineage → ontology...`
  - Cycle 5 (2 modules): `docker_sandbox → sandbox`
- **False-positive risk:** low — deferred/conditional imports may break cycles at runtime, but the static analysis is valid
- **Recommendation:** Break the 9-module ontology cycle first (highest blast radius). Add `import-linter` to CI.

### Q14 — Dead code (vulture)
- **Severity:** hygiene
- **Finding:** 34 dead-code items at ≥80% confidence
- **Evidence:**
  - `providers_extended.py:100,162,223` — unreachable code after `raise`
  - `scout_framework.py:315` — unreachable code after `return`
  - `vector_store.py:23` — unused import `pickle`
  - `web_search.py:328` — unused import `HTMLParser`
  - `orchestrate_live.py:1691` — unused import `_random`
  - Multiple unused `exc_type/exc_val/exc_tb` variables in `__exit__` methods
- **False-positive risk:** medium — `__exit__` variables are convention-required
- **Recommendation:** Fix the unreachable code and unused imports; suppress `__exit__` variables with `_` prefix.

### Q15 — Grandfathered exemptions
- **Severity:** hygiene
- **Finding:** 60 `# noqa` + 123 `# type: ignore` = 183 suppression annotations
- **Evidence:**
  - `grep -rnc '# noqa' dharma_swarm/` → 60
  - `grep -rnc '# type: ignore' dharma_swarm/` → 123
- **False-positive risk:** low
- **Recommendation:** Audit `# type: ignore` annotations quarterly; many may be resolvable with proper typing.

### Q16 — Premature microservicing
- **Severity:** cosmetic
- **Finding:** 3 packages/spinouts with only 1 caller each
- **Evidence:**
  - `tools/world_scout_go`: 1 caller
  - `packages/telos-gatekeeper`: 1 caller
  - `spinouts/planetary_reciprocity_commons_seed`: 1 caller
- **False-positive risk:** medium — Go tools may be independently deployed
- **Recommendation:** No immediate action; document deploy stories for single-caller packages.

---

## Section 4 — Dependencies (Q17–Q21)

### Q17 — Unpinned dependencies
- **Severity:** cosmetic
- **Finding:** clean — all deps use `>=` minimum pins
- **Evidence:**
  - `pyproject.toml` uses `>=` for all 14 production deps
- **False-positive risk:** low — `>=` pins allow semver drift but are standard for libraries
- **Recommendation:** Consider adding upper-bound pins (`<major+1`) for `anthropic`, `openai`, and `pydantic` which have breaking-change histories.

### Q18 — Hallucinated package names (slopsquatting)
- **Severity:** safety
- **Finding:** clean — all imported package names resolve to installed packages
- **Evidence:**
  - 0 unresolvable third-party imports found
- **False-positive risk:** none
- **Recommendation:** No action needed.

### Q19 — Dev tools in production requirements
- **Severity:** cosmetic
- **Finding:** clean — dev tools (`pytest`, `pytest-asyncio`, `pytest-cov`, `pytest-timeout`) are correctly under `[project.optional-dependencies] dev`
- **Evidence:**
  - `pyproject.toml` line 33: `dev = ["pytest>=7.0", ...]`
- **False-positive risk:** none
- **Recommendation:** No action needed.

### Q20 — Vendored upstream copies
- **Severity:** cosmetic
- **Finding:** clean — no `vendor/` or `third_party/` directories in project code
- **Evidence:**
  - `find . -type d -name vendor -o -name third_party` → empty (excluding `.venv/`)
- **False-positive risk:** none
- **Recommendation:** No action needed.

### Q21 — Deprecated third-party API usage
- **Severity:** cosmetic
- **Finding:** clean — no deprecated `openai.ChatCompletion`, `stripe.Charge`, or legacy completion patterns found
- **Evidence:**
  - `grep -rnE 'openai.ChatCompletion|stripe.Charge' dharma_swarm/` → 0
- **False-positive risk:** none
- **Recommendation:** No action needed.

---

## Section 5 — Security (Q22–Q28)

### Q22 — Secrets scan (gitleaks)
- **Severity:** safety
- **Finding:** `gitleaks` binary not installed — **unable to scan**
- **Evidence:**
  - `make gitleaks` → `gitleaks: No such file or directory`
- **False-positive risk:** N/A
- **Recommendation:** Install `gitleaks` in the environment blueprint. The Makefile target exists but the binary is missing.

### Q23 — SQL string interpolation
- **Severity:** safety
- **Finding:** **41 f-string SQL interpolation sites**
- **Evidence:**
  - `ontology_hub.py:382` — `f"SELECT * FROM links WHERE {where}"`
  - `task_board.py:173` — `f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?"`
  - `telemetry_views.py:139,148,157` — `f"SELECT COUNT(*) FROM {table}{where}"`
  - `guardian_runtime_checks.py:262` — `f"SELECT COUNT(*) FROM {quoted_table}"`
  - Most use `noqa: S608` suppression
- **False-positive risk:** medium — many interpolate table/column names (not user input), and parameters are still `?`-bound
- **Recommendation:** Audit the 41 sites for user-input-sourced table names. Add a `_safe_table_name()` validator for dynamic table references.

### Q24 — eval/exec call sites
- **Severity:** safety
- **Finding:** clean — 0 `eval()`/`exec()` on user data. 2 `.eval()` calls are PyTorch `model.eval()` (inference mode)
- **Evidence:**
  - `rv.py:187` — `self._model.eval()` (PyTorch)
  - `tiny_router_shadow.py:355` — `model.eval()` (PyTorch)
  - `verify/scorer.py:285-291` — detection rules, not usage
- **False-positive risk:** none
- **Recommendation:** No action needed.

### Q25 — Weak cryptographic hashing
- **Severity:** safety
- **Finding:** 4 `hashlib.md5`/`sha1` sites — all used for content-hashing, not cryptography
- **Evidence:**
  - `vector_store.py:266` — corpus fingerprint (md5)
  - `memory_palace.py:107` — content dedup hash (md5)
  - `file_lock.py:124,284` — lock file naming (md5)
- **False-positive risk:** high — all are content-addressing, not security
- **Recommendation:** Add `usedforsecurity=False` parameter to silence bandit. Low priority.

### Q26 — LLM prompt injection surfaces
- **Severity:** hygiene
- **Finding:** 9 sites interpolate variables matching `request.*`/`user_*` patterns into strings that reach LLM prompts
- **Evidence:**
  - `evolution.py:2942` — `f"## Context\n{context}\n\n{user_msg}"`
  - `providers_extended.py:56` — `f"{request.system}\n\n"`
  - `build_engine.py:288` — `f"System: {system_prompt[:200]}...\n\nTask: {user_prompt}"`
- **False-positive risk:** medium — most are internal agent-to-agent messages, not external user input
- **Recommendation:** Add a `sanitize_prompt_input()` wrapper for any path that accepts external user text.

### Q27 — Permissive CORS/TLS/auth defaults
- **Severity:** hygiene
- **Finding:** CORS allows `allow_methods=["*"]`, `allow_headers=["*"]` with credentials; origins are env-configurable (not wildcard by default)
- **Evidence:**
  - `api/main.py:246-250` — `CORSMiddleware(allow_origins=_ALLOWED_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])`
  - Origins default to `localhost:3000,3001,8420`
  - 259 `debug=True` or `exc_info=True` references (all are `logger.debug()` calls — acceptable)
- **False-positive risk:** medium — wildcard methods/headers with credentials is permissive but origins are controlled
- **Recommendation:** Restrict `allow_methods` and `allow_headers` to the specific methods/headers the dashboard actually uses.

### Q28 — Bandit scan results
- **Severity:** safety
- **Finding:** 5 HIGH, 69 MEDIUM, 568 LOW (excluding B101/assert)
- **Evidence:**
  - 5 HIGH: all `hashlib.md5`/`sha1` (content-hashing, see Q25)
  - 69 MEDIUM: subprocess calls, temp file usage, SQL interpolation
  - 568 LOW: subprocess without `shell=True`, `try/except/pass` blocks
- **False-positive risk:** high for HIGHs (content-hashing), medium for MEDIUMs
- **Recommendation:** Triage MEDIUMs; add `usedforsecurity=False` to resolve HIGHs.

---

## Section 6 — DRY / Duplication (Q29–Q32)

### Q29 — Duplicate time helpers
- **Severity:** structural
- **Finding:** **76 separate definitions** of `_utc_now()`, `utc_now()`, `_now()`, or equivalent across the codebase
- **Evidence:**
  - `guardrails.py:43`, `swarm_health_api.py:46`, `operator_bridge.py:82`, `concept_parser.py:37`, `cron_scheduler.py:44`, `iteration_depth.py:40`, `agent_runner.py:441`, `ginko_sentiment.py:33`, `rv.py:45`, `cron_job_runtime.py:15`, `ginko_regime.py:34`, `a2a/node_gateway.py:206`, `a2a/node_registry.py:51`, `roaming_onboarding.py:36`, `memory_kernel/write_receipts.py:344`, `memory_kernel/promotion_gate.py:318`, `memory_kernel/census.py:686`, `memory_kernel/burn_in.py:196`, `sleep_time_agent.py:45`, `board/facade.py:38`, `ginko_sec.py:40`, `decision_ontology.py:26`, `logic_layer.py:42`, `synthesis_agent.py:47`, `dse_integration.py:54`, `ai_reciprocity_ledger.py:42`, `revenue/wedge_pipeline.py:54`, `custodians.py:46`, `ginko_brier.py:36` … and 46 more
- **False-positive risk:** none — these are genuinely 76 separate `def _utc_now()` implementations
- **Recommendation:** Extract to `dharma_swarm/_time.py` with a single `utc_now() -> datetime` and `utc_now_iso() -> str`. This is the #1 DRY violation in the codebase.

### Q30 — Block-level duplication
- **Severity:** hygiene
- **Finding:** Not measured — `jscpd`/`pmd-cpd` not available. The 76× `_utc_now` pattern (Q29) suggests significant block duplication.
- **Evidence:**
  - (estimated) — Q29 alone accounts for ~228 duplicated lines
- **False-positive risk:** N/A
- **Recommendation:** Install `jscpd` and run a baseline. Expect >5% duplication.

### Q31 — Module-local CONFIG/SETTINGS dicts
- **Severity:** cosmetic
- **Finding:** clean — 0 module-level `CONFIG = {}` or `SETTINGS = {}` dicts
- **Evidence:**
  - `grep -rnE '^(CONFIG|SETTINGS)' dharma_swarm/` → 0
- **False-positive risk:** none
- **Recommendation:** No action needed.

### Q32 — Custom retry/cache/debounce logic
- **Severity:** cosmetic
- **Finding:** clean — 0 custom retry/debounce functions; 0 `tenacity` usage
- **Evidence:**
  - `grep 'def retry\|def backoff\|def throttle' dharma_swarm/` → 0
- **False-positive risk:** none
- **Recommendation:** No action needed.

---

## Section 7 — Error Handling & Concurrency (Q33–Q37)

### Q33 — Broad exception handlers
- **Severity:** structural
- **Finding:** 1 bare `except:` + 793 `except Exception:` blocks; **128** followed by `pass`, `return None`, or bare `return` with no logging
- **Evidence:**
  - `terminal_commands/diagnostics.py:113,119,187,207,221` — `except Exception: pass` (5 sites)
  - `terminal_commands/stigmergy.py:191` — `except Exception: pass`
  - `terminal_commands/agents.py:79` — `except Exception: pass`
- **False-positive risk:** low — silent `pass` after `except Exception` is a known antipattern
- **Recommendation:** Add `logger.debug(..., exc_info=True)` to the 128 silent handlers. Existing governance already has many debug-logged handlers — apply the same pattern consistently.

### Q34 — Suppression annotations
- **Severity:** hygiene
- **Finding:** 60 `# noqa` + 123 `# type: ignore` + 0 `# pylint: disable` + 0 `warnings.filterwarnings`
- **Evidence:**
  - Total: 183 suppression annotations across 674 source files (0.27 per file)
- **False-positive risk:** low
- **Recommendation:** Acceptable density. Review `# type: ignore` annotations during quarterly type-coverage audits.

### Q35 — Test order dependence
- **Severity:** hygiene
- **Finding:** Not measured — `pytest-randomly` is not installed by default
- **Evidence:**
  - `pyproject.toml` does not include `pytest-randomly` in dev deps
- **False-positive risk:** N/A
- **Recommendation:** Add `pytest-randomly` to `[project.optional-dependencies] dev` and run one CI pass to baseline.

### Q36 — Re-raise without `from e`
- **Severity:** hygiene
- **Finding:** **35 sites** catch an exception and re-raise a different type without `from e`
- **Evidence:**
  - `cron_scheduler.py:108` — `raise ValueError(f"Invalid cron: {e}")` (no `from e`)
  - `mcp_server.py:25` — `raise ImportError(...)` (no `from e`)
  - `provider_policy.py:571` — `raise RaceError(...)` (no `from e`)
  - `providers.py:1996` — `raise KeyError(...)` (no `from e`)
  - `api.py:340` — `raise HTTPException(404, str(exc))` (no `from exc`)
- **False-positive risk:** low
- **Recommendation:** Add `from e` to all 35 sites. Easy batch fix via regex.

### Q37 — Module-level mutable globals
- **Severity:** hygiene
- **Finding:** **150 module-level mutable dicts/sets/lists**
- **Evidence:**
  - Most are configuration constants (e.g. `_PRIORITY_SALIENCE`, `EASE_SCORES`, `PROTECTED_FILES`)
  - `self_improve.py:39` — `PROTECTED_FILES = {...}`
  - `agent_runner.py:74` — `_PRIORITY_SALIENCE = {...}`
  - `agent_runner.py:161` — `_TRUE_VALUES = {"1", "true", ...}`
- **False-positive risk:** high — most are effectively frozen configs, not mutation targets
- **Recommendation:** Use `Final` typing annotation or `frozenset`/`MappingProxyType` for truly constant dicts. Low priority.

---

## Section 8 — Async / Performance (Q38–Q41)

### Q38 — Blocking I/O in async functions
- **Severity:** structural
- **Finding:** **23 blocking I/O calls** inside `async def` functions (out of 1,638 async defs)
- **Evidence:**
  - `orchestrator.py:1893` — sync `open("a")` in async method
  - `orchestrator.py:2612,2614` — sync `open()` writes
  - `cascade.py:435` — sync `open("a")` append
  - `autoresearch_loop.py:507` — `subprocess.run()` in async
  - `handoff.py:332,349` — sync `open()` in async artifact store
  - `dse_integration.py:969,977` — sync `open()` observation logging
  - `autonomous_agent.py:991` — sync `open()` note writing
  - `subconscious_v2.py:706` — sync `open()` dream logging
- **False-positive risk:** low — these are genuine sync I/O calls in async context
- **Recommendation:** Replace sync `open()` with `aiofiles.open()` (already a dependency). Replace `subprocess.run()` with `asyncio.create_subprocess_exec()`.

### Q39 — Fire-and-forget `asyncio.create_task()`
- **Severity:** hygiene
- **Finding:** 13 `asyncio.create_task()` calls; some results stored in `_`-prefixed variables (retained), others not
- **Evidence:**
  - `orchestrator.py:541` — result not obviously retained
  - `evolution.py:345` — `task = asyncio.create_task(...)` (retained)
  - `archaeology_ingestion.py:669` — `task = asyncio.create_task(...)` (retained)
  - `orchestrate_live.py:2184` — dict comprehension of tasks (retained)
- **False-positive risk:** medium — most are retained via assignment
- **Recommendation:** Audit the 2–3 sites where the task handle is not clearly retained. Add `task.add_done_callback(lambda t: t.result())` for error surfacing.

### Q40 — N+1 query patterns
- **Severity:** hygiene
- **Finding:** ~65 potential N+1 query sites (heuristic: query within 4 lines of a `for` loop)
- **Evidence:**
  - `runtime_state.py:478`, `task_board.py:343`, `agent_memory_manager.py:659`, `lineage.py:225` (top hits)
- **False-positive risk:** high — heuristic-based detection has many false positives
- **Recommendation:** Manually audit the top 10 hits. Most are likely batch operations or single-row lookups.

### Q41 — Module-level cache dicts without eviction
- **Severity:** cosmetic
- **Finding:** clean — 0 module-level `_cache = {}` patterns found
- **Evidence:**
  - `grep -rnE '_cache.*=' dharma_swarm/` → 0 module-level caches
- **False-positive risk:** none
- **Recommendation:** No action needed.

---

## Section 9 — API / Interface Design (Q42–Q45)

### Q42 — Functions with 2+ boolean parameters
- **Severity:** hygiene
- **Finding:** **37 public functions** accept 2+ `bool` parameters
- **Evidence:**
  - `guardrails.py: create_default_runner` — 5 bool params
  - `full_power_probe.py: run_full_power_probe` — 3 bool params
  - `overnight_director.py: run_overnight` — 3 bool params
  - 34 functions with 2 bool params
- **False-positive risk:** low
- **Recommendation:** Replace positional booleans with keyword-only params (`*, verbose: bool = False, dry_run: bool = False`). Start with `create_default_runner` (5 bools).

### Q43 — Inconsistent return types
- **Severity:** hygiene
- **Finding:** Not measured — no type checker run configured as a CI gate
- **Evidence:**
  - `pyproject.toml` does not include `mypy` or `pyright` in dependencies
  - No `mypy.ini` or `pyrightconfig.json` found
- **False-positive risk:** N/A
- **Recommendation:** Add gradual `mypy --strict` starting with `dharma_swarm/spine/` and `dharma_swarm/models.py`.

### Q44 — Synonym functions
- **Severity:** hygiene
- **Finding:** Multiple `get_task`/`load_task`, `get_agent`/`load_agent`, `get_state`/`load_state` synonyms across modules
- **Evidence:**
  - `get_task`: `operator_bridge.py:472`, `a2a/a2a_server.py:467`, `swarm.py:1346`
  - `load_task`: `roaming_mailbox.py:140`
  - `get_agent`: `ginko_agents.py:465`
  - `load_agent`: `agent_registry.py:329`
  - `load_state`: `loop_supervisor.py:434`, `samvara.py:508`, `ginko_orchestrator.py:91`
  - `get_state`: `landscape.py:406`
- **False-positive risk:** medium — different bounded contexts may legitimately use different verbs
- **Recommendation:** Standardize within bounded contexts: `get_*` for in-memory lookup, `load_*` for disk/DB hydration. Document the convention.

### Q45 — API endpoint versions
- **Severity:** cosmetic
- **Finding:** No internal API versioning (`/v1/`, `/v2/`). References to `/v1/` are all external OpenRouter/OpenAI SDK paths.
- **Evidence:**
  - `grep -rnE '/v[0-9]+/' api/ dharma_swarm/` → 31 hits, all external API URLs
- **False-positive risk:** none
- **Recommendation:** No action needed.

---

## Section 10 — Git / Process (Q46–Q49)

### Q46 — Lazy commit messages
- **Severity:** cosmetic
- **Finding:** **41 commits** in the last 7 days match `^(wip|fix|update|tmp|test|debug)` — however, all use conventional-commit format (`fix(scope): ...`, `test: ...`) with descriptive messages
- **Evidence:**
  - `fix(providers): dkeys ↔ dharma_swarm env alias normalization + dashboard fidelity audit [impact-checked]`
  - `test: expand coverage — contracts/runtime, revenue/spine, cascade_domains/skill`
  - `fix(guardian): bulletproof dedup — exact-title-match + PR-awareness + circuit breaker`
- **False-positive risk:** high — these match the `^fix` pattern but are well-structured conventional commits
- **Recommendation:** No action needed. The repo uses good commit conventions.

### Q47 — Force pushes to protected branches
- **Severity:** safety
- **Finding:** clean — 0 force pushes in reflog
- **Evidence:**
  - `git reflog --since="30 days ago" | grep -i force` → empty
- **False-positive risk:** none
- **Recommendation:** No action needed.

### Q48 — Large PRs (>1000 LOC)
- **Severity:** hygiene
- **Finding:** Cannot reliably measure from `git log --shortstat` alone (merge commits obscure per-PR stats)
- **Evidence:**
  - Git shortstat heuristic returned 0 commits with >1000 LOC changed
- **False-positive risk:** N/A
- **Recommendation:** Use `gh pr list --json additions,deletions` for accurate measurement. PR quality gates (#394) are already active.

### Q49 — Multi-concern commits
- **Severity:** hygiene
- **Finding:** Several recent commits touch 3+ concern categories (code, docs, governance, tests, CI)
- **Evidence:**
  - `feat(governance): PR quality gates...` — touched `.github/workflows/`, `docs/governance/`, `scripts/governance/`
  - `fix(providers): dkeys...` — touched `api/`, `dharma_swarm/`, `docs/`, `scripts/`, `tests/`
- **False-positive risk:** high — governance changes legitimately span categories; these are coherent changesets
- **Recommendation:** No action needed. The coherence delta gate already addresses this.

---

## Section 11 — Observability (Q50–Q53)

### Q50 — `print()` in production code
- **Severity:** hygiene
- **Finding:** **1,170 `print()` calls** in production code paths
- **Evidence:**
  - `terminal_commands/diagnostics.py`: 91 prints
  - `terminal_commands/governance.py`: 83 prints
  - `terminal_commands/infrastructure.py`: 76 prints
  - `terminal_commands/meta.py`: 67 prints
  - `terminal_commands/status.py`: 64 prints
  - `dgc_cli.py`: 64 prints
- **False-positive risk:** high — most are in CLI/TUI output paths where `print()` is the correct output mechanism
- **Recommendation:** Acceptable for CLI commands. Audit non-CLI modules for stray `print()` calls that should use `logger`.

### Q51 — Structured vs free-text logging
- **Severity:** hygiene
- **Finding:** **2.5% structured** — 45 structured (key=value) out of 1,793 total `logger.*()` calls
- **Evidence:**
  - Structured: 45
  - Free-text: 1,748
- **False-positive risk:** low
- **Recommendation:** Adopt structured logging for new code. Start with `dharma_swarm/spine/` and `dharma_swarm/orchestrator.py`.

### Q52 — Correlation/request ID propagation
- **Severity:** cosmetic
- **Finding:** clean — **984 references** to `correlation_id`/`trace_id`/`request_id` across the codebase. The spine module has canonical propagation.
- **Evidence:**
  - `spine/receipt.py:42` — `trace_id` field
  - `spine/adapters.py:18-19` — `trace_id`, `correlation_id` in adapter fields
  - `spine/adapters.py:93,131,132,202` — propagation through carriers
- **False-positive risk:** none
- **Recommendation:** No action needed. Correlation ID propagation is well-implemented.

### Q53 — Orphan metrics
- **Severity:** cosmetic
- **Finding:** 158 metric emit sites; 882 alert/dashboard references in docs
- **Evidence:**
  - Metric emits spread across many modules
  - Docs reference dashboards, alerts, and monitoring extensively
- **False-positive risk:** high — many "metric" references are conceptual, not actual Prometheus/StatsD emitters
- **Recommendation:** Low priority. If deploying production monitoring, audit actual metric names against dashboards.

---

## Section 12 — Build / CI (Q54–Q56)

### Q54 — CI auto-retry
- **Severity:** hygiene
- **Finding:** Yes — `pr-ci-health.yml` has a `rerun` mode that re-runs failed workflow runs
- **Evidence:**
  - `.github/workflows/pr-ci-health.yml:87-98` — `gh run rerun "$run_id" --repo "$REPO" --failed`
- **False-positive risk:** low
- **Recommendation:** Acceptable for flaky-test mitigation if retry count is bounded. Verify it doesn't mask real failures.

### Q55 — CI matrix coverage
- **Severity:** cosmetic
- **Finding:** Tests run on Python 3.11 and 3.12. 20 workflow files total.
- **Evidence:**
  - `.github/workflows/tests.yml:46` — `python-version: ["3.11", "3.12"]`
  - Other workflows pin `3.11` or `3.12` individually
- **False-positive risk:** none
- **Recommendation:** No action needed. Coverage is appropriate.

### Q56 — Stale/deprecated workflows
- **Severity:** hygiene
- **Finding:** 20 workflow files. Cannot verify run history without GitHub API access.
- **Evidence:**
  - `ls .github/workflows/*.yml | wc -l` → 20
- **False-positive risk:** N/A
- **Recommendation:** Run `gh run list --workflow=<name> --limit=1` for each workflow to identify stale ones.

---

## Section 13 — Architecture & Coherence (Q57–Q60)

### Q57 — Architectural invariant tests
- **Severity:** cosmetic
- **Finding:** Yes — 7 governance check scripts + spine persistence invariant test
- **Evidence:**
  - `scripts/governance/check_module_budget.py` — file size invariants
  - `scripts/governance/check_test_hygiene.py` — test quality invariants
  - `scripts/governance/check_ontology_alignment.py` — ontology invariants
  - `scripts/governance/check_spine_ownership.py` — spine ownership invariants
  - `scripts/governance/check_pr_coherence_delta.py` — PR coherence
  - `scripts/governance/check_shakti_warrant.py` — action warrant checks
  - `scripts/governance/check_track_status.py` — track lifecycle
  - `tests/test_spine_persistence_invariant.py` — A2A single-persistence
- **False-positive risk:** none
- **Recommendation:** Add `import-linter` for the 11 import cycles found in Q13.

### Q58 — Cross-cutting concern implementations
- **Severity:** hygiene
- **Finding:** Significant spread:
  - Logging: 267 files import `logging`
  - HTTP clients: 25 files use `httpx`/`requests`/`aiohttp`
  - Config loading: 9 distinct patterns
- **Evidence:**
  - HTTP: `httpx` (primary), `requests` (legacy), `aiohttp` (async)
  - Time: 76 separate `_utc_now()` defs (see Q29)
- **False-positive risk:** medium — multiple HTTP clients may serve different async/sync contexts
- **Recommendation:** Consolidate `_utc_now()` (Q29). Standardize on `httpx` for both sync and async HTTP.

### Q59 — Architecture Decision Records (ADRs)
- **Severity:** cosmetic
- **Finding:** 4 ADRs exist under `docs/architecture/adr/` and `docs/architecture/ADRs/`
- **Evidence:**
  - `adr/0001-next-seam-candidate.md`
  - `adr/0002-trace-coverage-gate.md`
  - `ADRs/ADR-006-shakti-ginko-organ.md`
  - `ADRs/ADR-007-autoproposer-darwin-submission.md`
  - `ADRs/ADR-008-ontology-api-name-grammar.md`
- **False-positive risk:** none
- **Recommendation:** Consolidate the two ADR directories (`adr/` and `ADRs/`) into one. Many significant architectural decisions lack ADRs.

### Q60 — Single-implementation abstractions
- **Severity:** structural
- **Finding:** **416 abstractions** (ABC/BaseModel/Protocol subclasses) have 0–1 concrete implementations
- **Evidence:**
  - Most are Pydantic `BaseModel` data classes (not true abstractions — they ARE the implementation)
  - True vestigial abstractions are a small subset
  - `Guardrail` (1 impl), `RecursiveReceipt` (1 impl) — genuine single-impl patterns
- **False-positive risk:** very high — Pydantic `BaseModel` subclasses inflate the count drastically
- **Recommendation:** Filter to only `ABC` and `Protocol` bases. The actual vestigial abstraction count is likely <20. Low priority.

---

## Executive Summary

### Top 10 Actionable Findings

| Rank | Question | Severity | Effort | Why this one |
|------|----------|----------|--------|--------------|
| 1 | Q29 | structural | low | 76 duplicate `_utc_now()` — one-line-per-file fix, highest DRY win |
| 2 | Q9 | structural | low | 390 dead markdown links — batch fixable, 33% link rot |
| 3 | Q7 | structural | low | README lists 6 nonexistent Make targets — breaks onboarding |
| 4 | Q23 | safety | medium | 41 f-string SQL sites — audit for user-sourced table names |
| 5 | Q38 | structural | medium | 23 sync I/O calls in async funcs — `aiofiles` is already available |
| 6 | Q13 | structural | high | 11 import cycles including a 9-module ontology cycle |
| 7 | Q3 | structural | medium | 0 integration tests — mock ratio is effectively infinite |
| 8 | Q33 | structural | low | 128 silent `except Exception: pass` blocks |
| 9 | Q36 | hygiene | low | 35 `raise FooError(...)` without `from e` — lost tracebacks |
| 10 | Q2 | structural | medium | 254 tests with only weak assertions — low mutation-test resilience |

### Risk Heatmap

| Cluster | Critical | Warning | Clean |
|---------|----------|---------|-------|
| Tests (Q1–Q6) | 2 | 3 | 1 |
| Docs (Q7–Q11) | 2 | 0 | 3 |
| Structure (Q12–Q16) | 2 | 2 | 1 |
| Deps (Q17–Q21) | 0 | 1 | 4 |
| Security (Q22–Q28) | 2 | 2 | 3 |
| DRY (Q29–Q32) | 1 | 1 | 2 |
| Errors (Q33–Q37) | 1 | 3 | 1 |
| Async (Q38–Q41) | 1 | 2 | 2 |
| API (Q42–Q45) | 0 | 3 | 2 |
| Git (Q46–Q49) | 0 | 1 | 3 |
| Observability (Q50–Q53) | 0 | 2 | 2 |
| CI (Q54–Q56) | 0 | 1 | 2 |
| Architecture (Q57–Q60) | 0 | 2 | 2 |

### Recommended Next Sprint

1. **`devin/utc-now-consolidation`** — Extract 76 `_utc_now()` definitions into `dharma_swarm/_time.py`. Impact: eliminates the single largest DRY violation. Effort: ~2 hours. (Note: requires Axiom A1 waiver for new top-level file, or place in an existing utils module.)

2. **`devin/readme-makefile-sync`** — Either create the 6 aliased Make targets or update README to match reality. Impact: fixes broken onboarding. Effort: ~30 minutes.

3. **`devin/dead-link-cleanup`** — Batch-fix 390 dead markdown links, starting with the `/Users/dhyana/...` absolute paths. Impact: 33% link rot → <5%. Effort: ~1 hour.

---

## Addendum — Relationship to Existing Governance

This audit validates and extends the existing anti-slop rules in `docs/governance/ANTI_SLOP_RULES.md`:

- **Rule 10 gap:** `runtime_state.py` (3,796 LOC), `ontology.py` (2,416), `orchestrate_live.py` (2,257), `operator_bridge.py` (1,819), and `tui_legacy.py` (1,795) exceed 1,000 LOC but are absent from the grandfathered modules list.
- **New signal for promotion:** The 76× `_utc_now()` duplication pattern should be considered for a new anti-slop rule (e.g. `dharma.no-duplicate-time-helpers`).
- **Import cycles (A7):** Axiom A7 says "no new circular imports" — but 11 existing cycles remain. Suggest tracking in the Broken Register.

---

*Auditor: Devin (Cognition AI) — session `7c5c93b8` — 2026-06-07*
*Method: automated shell commands + static analysis (bandit, vulture, custom scripts)*
*Subordinates to: `docs/governance/ANTI_SLOP_RULES.md`, `docs/governance/SOVEREIGN_MANIFEST.md`*
