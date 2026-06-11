# Agent 5 Receipt: Organs / Runtime / DevOps Systems Engineer

Date: 2026-06-11
Mode: read-only scan
Question: Which organs actually exist in code, and how healthy are they?

## Files Read By Family

Spec:
- `docs/agent_tasks/2026-06-11_swarm_genome_convergence_spec.md`

Core scans:
- `dharma_swarm/`
- `api/`
- `scripts/runtime/`
- `scripts/governance/`
- `tests/`
- `reports/anatomy_altitude_2026-06-10/`
- `reports/governance/`

Ops and control:
- `docs/ops/LIVE_OPS_COCKPIT.md`
- `docs/ops/TMUX_AGENT_SUBSTRATE.md`
- `scripts/runtime/live_ops_census.py`
- `scripts/governance/agent_onboard.py`
- `Makefile`

Organs:
- `dharma_swarm/runtime_state.py`
- `dharma_swarm/operator_core/*`
- `dharma_swarm/a2a/*`
- `dharma_swarm/capital_lab/*`
- `dharma_swarm/revenue/*`
- `dharma_swarm/memory_kernel/*`
- `dharma_swarm/knowledge_ops/*`
- `dharma_swarm/chetana/*`
- `dharma_swarm/holon_*`
- `dharma_swarm/cron_*`
- `dharma_swarm/dgc_cli.py`
- `dharma_swarm/terminal_bridge.py`
- `dharma_swarm/tui/*`
- `terminal/*`
- `docs/loomwork/*`

## Make Onboard Snapshot

Command run by lane: `env PYTHONDONTWRITEBYTECODE=1 make onboard`.

Observed:
- Branch: `qwen/spine-adoption`
- Dirty files: 341
- Active tracks: 4
- Gaps: `revenue-external-humans-served`, `research-depth`
- Runtime DB: `~/.dharma/state/runtime.db`
- Runtime row counts: `artifact_records 1475`, `delegation_runs 3938`, `execution_identities 2089`, `runtime_receipts 3332`, `task_claims 3972`
- Receipt fill gap: `delegation_runs 0/3938`
- Live ops: 15 surfaces, with 6 live, 7 stopped, 1 stale, 1 blocked
- A2A readiness edge imports missing `dharma_swarm.operator_core.a2a_task_lifecycle`

## Claims With Source References

1. `make onboard` is informational and owns no facts. Sources: `scripts/governance/agent_onboard.py:1-17`, `Makefile:312-317`, `tests/test_agent_onboard.py:181-204`.
2. Runtime truth projector is read-only and opens SQLite with `mode=ro`; RuntimeStateStore is canonical SQLite spine. Sources: `dharma_swarm/operator_core/runtime_truth.py:1-6`, `:179-187`, `dharma_swarm/runtime_state.py:1-7`, `:396-435`.
3. Control surface separates declared intent from observed reality; manifest is not truth. Sources: `dharma_swarm/operator_core/control_surface.py:1-12`, `api/routers/control_surface.py:46-56`, `:116-124`.
4. Live Ops Cockpit is read-only and must not start/stop/kill/message/spend/merge. Source: `docs/ops/LIVE_OPS_COCKPIT.md:7-11`.
5. tmux is terminal persistence, not identity, work, or completion authority. Source: `docs/ops/TMUX_AGENT_SUBSTRATE.md:8-15`, `:103-117`.
6. A2A exists with protocol/server/NATS tests, but readiness currently imports a missing module. Sources: `dharma_swarm/a2a/a2a_server.py:1-23`, `:51-65`, `:399-434`, `scripts/governance/check_a2a_readiness.py:12-16`, `tests/test_a2a_readiness_gate.py:6-7`.
7. Capital Lab hard-fences live trading authority. Sources: `dharma_swarm/capital_lab/alpha_evidence.py:1-6`, `:26-29`, `dharma_swarm/capital_lab/broker_paper_membrane.py:1-6`, `:24-30`.
8. Revenue scout/spine/API exist, but no autonomous spam and human approval is required. Sources: `dharma_swarm/revenue/scout_daemon.py:1-18`, `:406-443`, `api/routers/revenue.py:74-85`.
9. MemoryKernel is read-only with readiness tests. Sources: `dharma_swarm/memory_kernel/facade.py:1-5`, `:59-80`, `dharma_swarm/memory_kernel/readiness.py:94-178`.
10. Holon runtime exists but launch proof is not closed. Sources: `dharma_swarm/holon_runtime.py:1-19`, `:52-86`, `reports/sovereign_holons/BUILD_A_90_READINESS_PACKET.md:1-15`, `:120-174`.
11. Loomwork is design-only in this scan: portfolio marks it design-only and no `dharma_swarm/wiki_loom` package was found. Source: `docs/governance/VENTURE_CELL_PORTFOLIO.yaml:114-118`.

## Organ Inventory

- RuntimeState / RuntimeTruth: working core, semi-working saturation.
- API gateway: semi-working; routers registered; dev auth opens API when `DASHBOARD_API_KEY` absent.
- Control surface / cockpit: semi-working read model; rows depend on many adapters.
- Live ops census: working read-only.
- A2A / NATS: semi-working with broken readiness edge.
- Capital Lab: semi-working paper/evidence, aspirational live, dangerous if treated live.
- Revenue / CashClaw / RevenueSpine: semi-working, blocked external loop.
- MemoryKernel / KnowledgeOps: working read-only, semi-working write path.
- Chetana: semi-working CLI/tests, not fully MCP-integrated.
- Holon: semi-working, launch proof incomplete.
- Loomwork: aspirational/stale design.
- Cron/schedulers: semi-working with repo/live split-brain risk.
- tmux substrate: working persistence, dangerous if treated as proof.
- Merge Master Mike / PR merge control: semi-working and authority-bearing.
- Terminal / TUI: duplicate/bloated.
- Evolution / DGM: semi-working/stale/dangerous overclaim risk.

## Health Labels

- Working: RuntimeState core, live ops census, tmux as persistence, MemoryKernel read-only readiness.
- Semi-working: API, control surface, A2A/NATS, revenue, Chetana, Holon, cron.
- Aspirational: live trading, Loomwork code organ, external broker-paper, fully metabolic self-evolution.
- Stale: Loomwork implementation claims, branch-specific anatomy reports in dirty checkout.
- Duplicate: terminal/TUI surfaces; overlapping operator truth surfaces.
- Bloated: runtime god-files and dashboard/control surface adapter sprawl.
- Dangerous: API dev-auth open mode, live-trading surfaces, merge-control authority, treating mirrors as truth.
- Unknown: exact live daemon/process state without mutating checks.

## Top 10 Findings

1. Runtime ledger/projection stack is the healthiest core organ.
2. Dispatch evidence is not fully saturated.
3. Control surface and live ops are honest read models, not authority.
4. A2A/NATS has real implementation but broken readiness gate.
5. Capital Lab is honest because live authority is zero.
6. Revenue has code but no external metabolism proof.
7. MemoryKernel/KnowledgeOps is healthy because it narrows its authority.
8. Chetana is real as CLI/tested package, not fully MCP-integrated.
9. Holon exists but is not launch-proven.
10. Terminal/operator surfaces are overgrown and duplicate authority.

## Top 10 Weak Spots

1. Missing A2A readiness module.
2. Runtime receipt propagation partial across legacy paths.
3. Dirty, divergent branch state.
4. Cron live/repo split-brain.
5. Revenue external proof absent.
6. API dev-auth open mode.
7. Duplicate terminal/TUI layers.
8. Loomwork docs overrun implementation.
9. Evolution/DGM lineage and selection pressure broken/dormant.
10. Reports describe different branches/trees.

## Cleanup Candidates

1. Restore or retire `dharma_swarm.operator_core.a2a_task_lifecycle`.
2. Consolidate terminal surfaces.
3. Mark Loomwork design-only unless code exists.
4. Reduce god-file bloat.
5. Clarify cron authority and revenue scout env injection.
6. Split control-surface heavy rows from cheap liveness.
7. Update stale dashboard/live-ops prose.
8. Promote MemoryKernel writes through one canonical gate.
9. Align anatomy reports with current branch state.
10. Keep live trading and merge authority guarded.

## Do Not Touch Until Understood

- `dharma_swarm/runtime_state.py`
- `~/.dharma/state/runtime.db`
- `dharma_swarm/operator_core/runtime_truth.py`
- `dharma_swarm/operator_core/control_surface.py`
- `ACTIVE_SURFACE_MANIFEST.yaml`
- A2A/NATS secrets, subjects, ack receipts, and `scripts/runtime/a2a_send.py`
- Capital/AGNI/Hyperliquid/live trading surfaces
- Revenue outreach/CashClaw gates
- `pr_merge_control.py` and `merge_master_mike_daemon.py`
- Chetana trusted wiki/promote paths
- Dashboard API/web restarts

## Final Command Map Must Include

- Runtime ledger and receipt counts.
- Read-only control surface truth boundary.
- A2A readiness status and missing module warning.
- Capital live-readiness zeros.
- Revenue external proof status.
- MemoryKernel/KnowledgeOps authority boundary.
- Chetana status.
- Holon launch proof status.
- Loomwork design-only status.
- Terminal/TUI duplicate map.

## Uncertainties

- Full test suite was not run.
- Live process state was inferred from onboarding and receipts, not restarts.
- Some reports are branch/time-specific.
- Loomwork implementation conflict remains unresolved.

## Suggested Verifiers

```bash
env PYTHONDONTWRITEBYTECODE=1 make onboard
.venv/bin/python scripts/runtime/live_ops_census.py --write
.venv/bin/python -m pytest tests/test_agent_onboard.py tests/test_control_surface.py tests/test_live_ops_census.py -q
.venv/bin/python -m pytest tests/test_a2a.py tests/test_a2a_e2e.py tests/test_a2a_spec_conformance.py tests/test_nats_transport.py -q
.venv/bin/python -m pytest tests/test_a2a_readiness_gate.py -q
.venv/bin/python -m pytest tests/test_capital_lab_alpha_evidence.py tests/test_capital_lab_broker_paper_membrane.py tests/test_capital_lab_contracts.py tests/test_capital_lab_risk_governor.py -q
make memory-kernel-readiness
```

