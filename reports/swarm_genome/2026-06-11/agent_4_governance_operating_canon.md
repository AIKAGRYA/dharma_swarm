# Agent 4 Receipt: Operating System / Governance Architect

Date: 2026-06-11
Mode: read-only scan
Question: What rules tell agents how to work safely, and what do those rules hide?

## Files Read By Family

Mission and onboarding:
- `docs/agent_tasks/2026-06-11_swarm_genome_convergence_spec.md`
- `CLAUDE.md`
- `AGENTS.md`
- `docs/AGENTS.md`
- `docs/ops/AGENT_ONBOARDING.md`
- `Makefile`
- `scripts/governance/agent_onboard.py`

Operating canon:
- `docs/governance/CANONICAL_DOC_STACK.md`
- `docs/governance/SOVEREIGN_MANIFEST.md`
- `docs/governance/BUILD_SESSION_ENTRYPOINT.md`
- `ACTIVE_SURFACE_MANIFEST.yaml`

Active work and evidence:
- `docs/governance/ACTIVE_TRACK.yaml`
- `reports/governance/active_track_evidence.md`
- `reports/governance/track_portfolio.json`

Safety and gates:
- `docs/governance/ANTI_SLOP_RULES.md`
- `docs/governance/PR_QUALITY_GATES.md`
- `docs/governance/CI_GATES.md`
- `docs/governance/hygiene/AI_AGENT_GOVERNANCE.md`

Breakage and todo surfaces:
- `docs/state/BROKEN_REGISTER.md`
- `docs/plans/NEXT_10_SUBSTRATE_TODO.md`
- `docs/governance/AGENTOPS.md`
- `docs/governance/KAIZENOPS.md`
- `docs/governance/DAILY_OPERATING_BRIEF.md`
- `docs/governance/METABOLIC_CLOCK.md`
- `docs/governance/VENTURE_CELL_PORTFOLIO.yaml`

## Claims With Source References

1. The current canon makes agents safe around code but does not put whole-organism vision into the first-token path. Source: `docs/agent_tasks/2026-06-11_swarm_genome_convergence_spec.md:10-21`.
2. The governance lane is explicitly about hidden substrate-repair bias. Source: `docs/agent_tasks/2026-06-11_swarm_genome_convergence_spec.md:148-170`.
3. The first gate is `make onboard`; `CLAUDE.md` instructs agents to run it before non-trivial work and trust live state over stale prose. Source: `CLAUDE.md:3-16`.
4. `make onboard` is a renderer, not authority. Sources: `scripts/governance/agent_onboard.py:1-17`, `Makefile:312-317`.
5. Current active portfolio is substrate-biased: all four active tracks serve `substrate-nativeness`; revenue and research are uncovered. Sources: `CLAUDE.md:24-30`, `reports/governance/active_track_evidence.md:6-10`, `:78-83`.
6. `ACTIVE_TRACK.yaml` defines revenue and research as real spine objectives, but no current active track serves them. Sources: `docs/governance/ACTIVE_TRACK.yaml:56-68`, active serves at `:130-136`, `:240-247`, `:293-300`, `:405-412`.
7. The canonical source-of-truth model is strong: intent, surface, and state have distinct owners. Source: `docs/governance/CANONICAL_DOC_STACK.md:16-28`, `:50-90`, `:94-102`.
8. Safety rules emphasize no duplicate substrates, read-before-edit, no secrets, no root docs, tests, semgrep/gitleaks, module budgets, and PR hygiene. Sources: `CLAUDE.md:177-187`, `docs/governance/ANTI_SLOP_RULES.md:13-24`, `docs/governance/PR_QUALITY_GATES.md:14-37`.
9. Broader telos exists mostly outside first-read: Darshan, Loomwork, Shakti Ginko, SAB, Web4, venture cells. Source: `docs/governance/VENTURE_CELL_PORTFOLIO.yaml:1-31`, `:50-66`, `:73-123`, `:181-193`.
10. Self-evolution is safety-gated and partially blocked. Sources: `docs/state/BROKEN_REGISTER.md:30-39`, `ACTIVE_SURFACE_MANIFEST.yaml:386-394`, `:423-430`, `:623-657`.

## Current First-Read Stack

The documented first-read stack is:

1. `make onboard`
2. `CLAUDE.md`
3. `docs/governance/SOVEREIGN_MANIFEST.md`
4. `docs/governance/ACTIVE_TRACK.yaml`
5. `docs/governance/ANTI_SLOP_RULES.md`

Source: `docs/governance/CANONICAL_DOC_STACK.md:32-47`; repeated in `docs/ops/AGENT_ONBOARDING.md:36-49`.

Missing from first-read:
- `foundations/THE_ORGANISM.md`
- `docs/vision_maps/2026-05-30_binocular_witness_seer_northstar.md`
- `reports/anatomy_altitude_2026-06-10/`
- `docs/governance/VENTURE_CELL_PORTFOLIO.yaml`
- `docs/loomwork/`
- revenue/capital docs
- research and Chetana docs

## Governance Source-Of-Truth Map

- Intent/current work: `docs/governance/ACTIVE_TRACK.yaml`
- Surface inventory: `ACTIVE_SURFACE_MANIFEST.yaml`
- Live state: runtime receipts and live dashboards rendered by onboarding
- Known breakage: `docs/state/BROKEN_REGISTER.md`
- Behavior: `CLAUDE.md`
- Architecture/invariants: `docs/governance/SOVEREIGN_MANIFEST.md`
- Doc ownership: `docs/governance/CANONICAL_DOC_STACK.md`
- Safety/hygiene: `docs/governance/ANTI_SLOP_RULES.md`
- Venture/cells/revenue/media: `docs/governance/VENTURE_CELL_PORTFOLIO.yaml`

## Health Labels

- Working: `make onboard`, `CANONICAL_DOC_STACK.md`, `ACTIVE_TRACK.yaml`, PR/CI gates, anti-slop gates.
- Semi-working: `SOVEREIGN_MANIFEST.md`, `AGENT_ONBOARDING.md`, `ACTIVE_SURFACE_MANIFEST.yaml`, Daily Operating Brief, AgentOps.
- Aspirational: `SWARM_GENOME.md`, whole-organism first-token map, revenue/research/media active loops.
- Stale: `NEXT_10_SUBSTRATE_TODO.md`; old Venture portfolio active-build comments.
- Duplicate: active-track blocks rendered in multiple docs.
- Bloated: `SOVEREIGN_MANIFEST.md` and memory-heavy agent contexts.
- Dangerous: treating substrate-nativeness as the whole telos; treating model agreement as proof.
- Unknown: current live media/revenue systems beyond YAML and receipts.

## Top 10 Findings

1. Safety canon is strong and operational.
2. First-read stack is optimized for safe code work, not whole-organism comprehension.
3. All current active tracks serve substrate-nativeness.
4. Revenue and research are recognized spine objectives but uncovered.
5. Media/memetics exists in Venture Cell portfolio, not active tracks.
6. Self-evolution is documented but still gated/partial.
7. The source-of-truth model is coherent and should be reused.
8. Active work surfaces confuse method with object: wire substrate versus become organism.
9. Some todo/portfolio surfaces still assume older single-track doctrine.
10. `SWARM_GENOME.md` is absent except as this mission concept.

## Top 10 Weak Spots

1. No canonical 10-second organism map.
2. No active revenue track.
3. No active research-depth track.
4. No active media/publication track.
5. Shippable substrate tracks remain open.
6. Stale todo docs conflict with v2 active-track model.
7. Venture portfolio carries broader telos but is not first-read.
8. Broken Register dates are old in places.
9. PR gates do not enforce objective portfolio balance.
10. Governance may reduce diversity despite its own warnings.

## Final Command Map Must Include

- 10-second identity and telos map.
- Source-of-truth hierarchy.
- Active tracks and uncovered objectives.
- Organ health table.
- Revenue/research/media/self-evolution map.
- Stale, duplicate, and dangerous surfaces.
- Verifier commands.
- Exact source index.

## Uncertainties

- GitNexus was stale and used only for orientation.
- Live external revenue/media systems were not revalidated.
- Private wiki was not fully traversed in this lane.
- Worktree was already dirty.

## Suggested Verifiers

```bash
make onboard
python3 scripts/governance/check_track_status.py
python3 scripts/governance/render_active_track_includes.py --check
make docops-integrity
rg -n "SWARM_GENOME|COMMAND_MAP|Swarm Genome|Command Map" docs reports foundations
rg -n "serves: revenue-external-humans-served|serves: research-depth" docs/governance/ACTIVE_TRACK.yaml
```

