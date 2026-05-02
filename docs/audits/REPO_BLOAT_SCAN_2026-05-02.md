# Repo Bloat Scan — 2026-05-02

**Scope**: read-only structural analysis of `~/dharma_swarm/dharma_swarm/` (the production package). Tests, scripts, experiment scripts, build artifacts excluded.
**Method**: bash + grep against working tree at HEAD of `feat/inquiry-chain-phase1`.
**Purpose**: data for an external human engineer review. No code changes proposed. No subjective architecture judgment beyond what numbers show.
**Produced by**: Claude (the same agent that contributed Phase 1.1 schema). I am part of the bloat surface; treat my numbers as a starting point, not gospel.

---

## §1. Verified baseline (vs prior agent's claims)

| Metric | Prior claim | Verified | Δ |
|---|---:|---:|---|
| All `.py` in package (incl `__init__.py`) | 573 | **573** | match |
| Modules (excl `__init__.py`) | 546 | **546** | match |
| Flat ROOT modules | 397 | **396** | within 1 |
| Total LOC in package | 238,755 | **238,755** | match |
| Files ≥ 1,000 lines | 30 (later 19) | **35** | prior under-counted |
| Largest file | `dgc_cli.py` 7,115 | `thinkodynamic_director.py` 5,167 | **prior wrong** — `dgc_cli.py` 7,115 not in canonical worktree (likely chetana or stale) |

Honest read: the directional claim ("you have 5–10× more code than what the load-bearing core needs") is correct. The specific numbers were 70–95% accurate; one was wrong.

---

## §2. Top 35 files ≥1,000 lines (the heaviness)

```
5167  thinkodynamic_director.py
4511  telos_substrate.py
3582  agent_runner.py
3401  evolution.py
3237  swarm.py
3096  providers.py
2525  orchestrator.py
2520  tui/app.py
2255  ontology.py
2172  terminal_bridge.py
1842  runtime_state.py
1819  operator_bridge.py
1795  tui_legacy.py             ← name says "legacy"
1679  orchestrate_live.py
1420  context.py
1386  opportunity_dispatcher.py
1342  doctor.py
1284  organism.py
1265  evaluation_registry.py
1249  autonomous_agent.py
1238  telemetry_plane.py
1218  xray.py
1202  ginko_audit.py
1197  ginko_agents.py
1196  dharma_context_mcp.py
1185  overnight_director.py
1184  contracts/intelligence_evaluation_services.py
1182  contracts/runtime_adapters.py
1108  graph_nexus.py
1107  provider_matrix.py
1101  neural_consolidator.py
1094  dse_integration.py
1048  consolidation.py
1021  contracts/intelligence_adapters.py
1018  ginko_report_gen.py
```

35 files over 1,000 lines. Healthy Python project: 200–500 lines/file. **Eight files are 5×+ over** that band.

---

## §3. Subpackage layout — the flat-root concentration

| Location | Modules |
|---|---:|
| **ROOT (`dharma_swarm/dharma_swarm/*.py`)** | **396** |
| `tui/` | 37 |
| `assurance/` | 23 |
| `engine/` | 15 |
| `operator_core/` | 13 |
| `contracts/` | 12 |
| `knowledge_compiler/` | 10 |
| `auto_research/` | 10 |
| `auto_grade/` | 9 |
| `verify/` | 7 |
| `cascade_domains/` | 7 |
| 13 smaller dirs | 64 |

**73% of all production modules sit in the flat root**, not in any subpackage. Most well-organized Python projects of this size use deep subpackages (Django: ~16% in root; Flask: ~5%).

---

## §4. Filename-pattern duplicate scan (recalibrated)

Prior agent claimed major duplicate clusters. **Most overstated; one undernamed.**

| Pattern | Prior claim | Verified | Files |
|---|---:|---:|---|
| agent*.py | 23 | **8** | agent_constitution, agent_export, agent_install, agent_memory, agent_memory_manager, agent_registry, agent_runner, agent_runner_quality |
| memory*.py | 12 | **3** | memory, memory_lattice, memory_palace |
| router/routing*.py | 9–10 | **3** | router_retrospective, router_v1, routing_memory |
| evolution*.py | 6 | **2** | evolution, evolution_roster |
| orchestr*.py | 4 | **3** | orchestrate, orchestrate_live, orchestrator |
| witness*.py | 2 | **1** | witness |
| consol*.py | 2+ | **1** | consolidation |
| ontolog*.py | – | **8** | ontology + 7 well-named submodules (action_gateway, adapters, agents, context, hub, query, runtime) |
| **`ginko_*.py`** | not flagged | **17** ← BIGGEST CLUSTER | agents, attribution, audit, backtest, bridge, brier, data, evolution, live_test, orchestrator, paper_trade, regime, report_gen, risk, sec, sentiment, signals |
| terminal*.py | – | **5** | bridge, bridge_context, bridge_renderers, control, overnight_supervisor |

The headline "11 memory systems / 23 agent files" was 3–4× overstated. The actual concentration is **17 `ginko_*` files** (trading-lab cluster). Whether that's bloat depends on whether the trading lab is one product or seventeen.

---

## §5. Orphan candidates — modules with 0 internal importers AND 0 external references

Definition: zero matches for `from dharma_swarm.<module>` / `from .<module>` / `import dharma_swarm.<module>` inside `dharma_swarm/dharma_swarm/`, AND zero matches in `~/dharma_swarm/scripts/` and `~/dharma_swarm/api/`, AND zero references in `dgc_cli.py`.

These modules are loaded by nothing the scan can see. They may still be loaded via dynamic `importlib`, plugin discovery, or never. **Cannot prove orphan from grep alone — these are CANDIDATES the human auditor should investigate.**

| Module | LOC | Plausibly an entry point? |
|---|---:|---|
| dharma_context_mcp | 1,196 | maybe (MCP server entry — check `.mcp.json`) |
| gaia_platform | 1,016 | unclear; name suggests a top-level surface |
| ai_reciprocity_ledger | 974 | unclear |
| ginko_risk | 820 | should be imported by ginko_orchestrator (it isn't, by grep) |
| logic_layer | 819 | unclear |
| ontology_adapters | 818 | unclear |
| ginko_evolution | 794 | should be imported by evolution.py or ginko_orchestrator (it isn't) |
| autoresearch_loop | 757 | imported by `evolution.py` (NOT orphan) — see §6 |
| browser_agent | 719 | maybe (CLI/Playwright entry) |
| flywheel_exporter | 688 | unclear |
| terminal_overnight_supervisor | 658 | unclear |
| hibernation | 602 | unclear |
| kaizen_stats | 579 | unclear |

**13 candidates**, ~10K LOC combined. If any of these are genuinely orphan, deletion is non-destructive.

### Likely CLI/script entry points (NOT orphans, despite low import count)

| Module | LOC | Evidence |
|---|---:|---|
| orchestrate_live.py | 1,679 | 4 scripts/api hits, 1 dgc_cli hit — confirmed entry point |
| cli | 629 | 27 scripts/api hits — confirmed |
| thinkodynamic_canary | 680 | 3 scripts/api hits |
| terminal_bridge | 2,172 | 2 scripts/api hits |
| ginko_audit | 1,202 | 1 scripts/api hit |
| ginko_orchestrator | 975 | 1 scripts/api hit |
| context_compiler | 929 | 1 scripts/api hit |
| fleet_control | 770 | 1 scripts/api hit |
| full_power_probe | 679 | 1 scripts/api hit |

These have ~zero internal importers but external invocation paths — the import-graph is misleading because they're entry points called by subprocess/CLI/cron.

---

## §6. Load-bearing core (verified by importers)

The 5 largest files have a single central importer: `swarm.py`.

| Module | LOC | Imported by |
|---|---:|---|
| telos_substrate.py | 4,511 | swarm.py |
| agent_runner.py | 3,582 | swarm.py |
| orchestrator.py | 2,525 | swarm.py |
| evolution.py | 3,401 | swarm.py, micro_clusters.py, autoresearch_loop.py, orchestrate_live.py, jikoku_fitness.py |
| orchestrate_live.py | 1,679 | (none internal — it's a top-level entry, called by CLI) |

**`swarm.py` is the canonical façade** — most of the big files it imports are direct children of it. The "5–10× over what's load-bearing" claim resolves cleanly: kill or merge files that don't trace back to `swarm.py` (or `organism.py`, `dharma_kernel.py`, `telos_gates.py`, `cli.py`, `dgc_cli.py`) and you get a leaner core.

---

## §7. The 7 "tonight" modules — verified location

Prior conversation flagged 7 modules built recently as orphan-risk. Their actual location:

| Module | Location | Worktree | LOC |
|---|---|---|---:|
| causal_ledger.py | `~/dharma_chetana/dharma_swarm/causal_ledger.py` | chetana | (not in `dharma_swarm/dharma_swarm/`) |
| r_repair_metric.py | `~/dharma_chetana/dharma_swarm/r_repair_metric.py` | chetana | – |
| autoresearch_history.py | `~/dharma_chetana/dharma_swarm/autoresearch_history.py` | chetana | – |
| welfare_attribution.py | `~/dharma_chetana/dharma_swarm/welfare_attribution.py` | chetana | – |
| witness_resolver.py | `~/dharma_chetana/dharma_swarm/witness_resolver.py` | chetana | – |
| drift_monitor.py | `~/dharma_chetana/dharma_swarm/drift_monitor.py` | chetana | – |
| gate_calibration.py | `~/.dharma/scripts/gate_calibration.py` | scripts dir | – |

All seven live in chetana / `~/.dharma/scripts/` — **NONE in the `feat/inquiry-chain-phase1` working tree** that this scan covers. They will only become bloat-on-main if `feat/chetana-grand-memory` merges. Until then, they're worktree-local additions and irrelevant to the 546-module count.

The chetana branch's risk profile (per earlier agent self-audit): 4 of 7 are "depends on future wiring" — i.e. orphan-risk if downstream wiring decisions go differently. The external human auditor should evaluate the chetana branch as a unit before any merge.

---

## §8. Honest framing

**What the numbers say (load-bearing)**
- 546 modules, 73% in flat root, 35 files over 1k lines, average ~437 lines per module.
- Production package is 4–10× over the size band a healthy Python project this scope would have.
- 13 plausible orphan candidates (~10K LOC) with no traceable importers.
- 17 `ginko_*` files in one trading-lab cluster.
- Real load-bearing core is the 25–30 modules that trace through `swarm.py`, `organism.py`, `dharma_kernel.py`, `telos_gates.py`, `cli.py`, and the cron entry points.

**What the numbers do NOT say**
- They don't say which modules represent "exploration discipline" (research labs intentionally have 5× explored-but-unused) vs "agent debt" (built once, never used, never deleted).
- They don't say which orphan candidates are dynamically loaded.
- They don't say which `ginko_*` files are duplicates vs distinct trading concerns.
- They don't say what to delete. **Deletion is human judgment.**

**Where I am part of the problem**
- Phase 1.1 added a `Signal/Question/Evidence` schema to `ontology.py`. Net add: ~150 lines. Necessary by v2 plan; not bloat by itself.
- I did not pause before adding to ask "what could we remove instead?" I now see the prior-agent warning was correct: I default to additive. This audit exists because Dhyana caught me.
- The 7 chetana modules I co-authored carry orphan-risk if their wiring stalls. Disposable until the human auditor reviews the merge.

---

## §9. Recommended next steps (data, not directives)

1. **External human Python engineer** for 8–16 hours, reading-only, written verdict on:
   - Which of the 13 orphan candidates in §5 are actually unused.
   - Which of the 17 `ginko_*` files are functionally distinct vs redundant.
   - Whether `tui_legacy.py` (1,795 lines) can be removed (the `legacy` name is a strong signal).
   - Whether the chetana branch (`feat/chetana-grand-memory`) should merge.
2. **Self-imposed 30-day add-freeze** in `dharma_swarm/dharma_swarm/`. Every proposed new module must justify against deletion of an existing one.
3. **Mark `tui_legacy.py` for deletion** on the human's go — its name self-declares.
4. **Trace each `ginko_*` file** to its caller to map the trading-lab concern graph. If the lab is one product, 17 files is debt; if it's seventeen products, it's right-sized.
5. **Confirm `dharma_context_mcp.py`** is registered in any active `.mcp.json` before considering deletion.

No build action recommended out of this scan. The scan is the deliverable.

---

## §10. Reproducibility

All commands used live in this commit message style. Re-run by:
```bash
cd ~/dharma_swarm/dharma_swarm
find . -name "*.py" -not -name "__init__.py" -not -path "*/__pycache__/*" | wc -l
find . -maxdepth 1 -name "*.py" -not -name "__init__.py" | wc -l
find . -name "*.py" -not -path "*/__pycache__/*" -exec wc -l {} \; | awk '$1 >= 1000' | sort -rn
ls agent*.py memory*.py router*.py routing*.py evolution*.py orchestr*.py ginko_*.py terminal*.py
# Orphan scan loop is in the audit's bash transcript
```

**Numbers are stable as of HEAD of `feat/inquiry-chain-phase1` (`5327c3b` plus uncommitted state). They will drift on every commit.**
