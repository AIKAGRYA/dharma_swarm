# Six-Agent Swarm Uplift Critique Goal

Date: 2026-06-18
Status: prompt / handoff for a `/goal` mission
Authority: research and design only unless the operator explicitly grants a later build or live-run lease

## /goal

Run a six-agent critique and research mission whose purpose is to find the strongest practical way to uplift the entire Dharma Swarm, given the North Star v2 context, the current model pool, the Dharma Forge / Hydra history, the failed-or-weak Forge v0 ten-run measurement, the A2A/runtime-spine substrate, DGM-style open-ended evolution, Karpathy-style AutoResearch loops, and all relevant public benchmark/tooling evidence.

The mission must not merely improve the old Forge v0 runner. It must critique whether that runner was too infantile to test the real thesis: "a coordinated swarm, using the strongest available models in their correct roles, should beat a single frontier model and create learning signal that compounds through the organism."

## Plain Objective

We need six strong agents to tell us, without politeness or self-protection:

1. What did the previous Forge v0 design misunderstand?
2. What context did it ignore from the North Star, model pool, A2A substrate, Forge/Hydra archaeology, DGM, AutoResearch, and benchmark literature?
3. What is the most powerful realistic path to make the whole swarm evolve faster?
4. What exact benchmark stack should become the external goal?
5. What exact orchestration, role assignment, coordination telemetry, archive loop, and feedback mechanism are missing?
6. What should we build or run next, in what order, with what evidence gates?

Do not optimize for agreement. Optimize for finding the highest-leverage truth.

## Non-Negotiable Context To Read First

Every agent must read or inspect these before giving conclusions:

- `make onboard`
- `docs/vision_maps/NORTH_STAR.md`
- `reports/swarm_genome/2026-06-11/SYNTHESIS.md`
- `docs/governance/ACTIVE_TRACK.yaml`
- `docs/ops/MODEL_KEY_ROUTING.md`
- `dharma_swarm/model_hierarchy.py`
- `docs/ops/DHARMA_FORGE_HYDRA_ARCHAEOLOGY_2026-06-11.md`
- `docs/agent_tasks/2026-06-17_forge_v0_10x_measurement_goal_handoff.md`
- `docs/specs/forge_packets/FORGE_SWARM_EVOLUTION_ARENA_V0_MEASUREMENT_10H_LAUNCH.md`
- `reports/forge/swarm-evolution-arena-v0-measurement/20260617T135919Z-readiness-preflight/ten_run_aggregate.json`
- `reports/forge/swarm-evolution-arena-v0-measurement/20260617T135919Z-readiness-preflight/ten_run_aggregate.md`
- `docs/research/VERIFIED_EXPERIMENT_LOOP_RFC.md`
- `docs/research/DARWIN_ENGINE_PERPETUAL_EVOLUTION_RESEARCH.md`
- `dharma_swarm/dgm_loop.py`
- `dharma_swarm/autoresearch_loop.py`
- `scripts/organism_council.py`
- A2A/runtime-spine status from `make onboard`, especially loop closure and A2A cloud bridge status.

If any path is missing, stale, branch-only, or off-repo, record that as evidence instead of ignoring it.

## Required Public Research

Use public tools, web search, GitHub search, arXiv/paper search, benchmark leaderboards, and public-code search where available. Cite URLs and access dates for every public claim.

At minimum, investigate:

- SWE-bench, SWE-bench Verified, SWE-bench Lite, SWE-bench Multilingual, SWE-bench Multimodal.
- Multi-SWE-bench.
- CodeClash and other multi-round goal-oriented software engineering benchmarks.
- MARBLE / MultiAgentBench and any current benchmarks that directly measure multi-agent coordination.
- tau-bench, AgentBench, GAIA, SWE-Lancer, RE-Bench, METR/HCAST-style autonomy evals.
- Sakana/UBC Darwin Godel Machine and follow-up work on open-ended coding-agent self-improvement.
- Karpathy AutoResearch / autonomous research loops and any strong public replications or critiques.
- Research or postmortems on how multi-agent teams win hackathons, coding competitions, red-team exercises, eval competitions, or agent benchmark contests.
- Public model-routing, mixture-of-agents, debate, planner-builder-verifier, self-refine, reflection, and evaluator-optimizer patterns.
- Public evidence on when multi-agent systems underperform single frontier models because coordination cost overwhelms intelligence gain.

The research question is not "what benchmarks exist?" The question is: "Which benchmarks and protocols give the clearest learning signal for a self-evolving software organism?"

## Model Pool And Role Reality Check

Do not trust remembered model names. Verify live availability.

Start from the repo's canonical routing surface:

- `dharma_swarm/model_hierarchy.py`
- `docs/ops/MODEL_KEY_ROUTING.md`
- `dkeys` status/test helpers, without printing secrets
- `dharma_swarm.provider_smoke.run_provider_smoke()` or the current repo-approved provider-smoke wrapper
- live provider catalogs where available

The operator specifically expects the strongest available lanes to be considered, including but not limited to:

- highest available Codex / OpenAI coding lane, for primary engineering and final synthesis
- highest available Claude Opus / Claude Code lane, for architecture and adversarial coherence critique
- highest available GLM lane, for long-context system synthesis
- highest available Kimi lane, for research breadth and alternative reasoning
- highest available Qwen / Qwen-Coder lane, for code-heavy search and implementation critique
- strongest available DeepSeek, Cerebras, NVIDIA NIM, OpenRouter, Ollama Cloud, Groq, Together, Fireworks, SiliconFlow, or comparable challenger lanes

If names like `glm-5.2`, `codex-5.5`, `opus-4.8`, or `kimi-2.7` are not actually live, say so. If better current names exist, use those. Every agent must report:

- actual provider
- actual model
- transport path
- role assigned
- why that model is suited to the role
- known quirks or idiocies of that model
- timeout/rate-limit/cost risks
- fallback model

No "strongest model" claim counts unless backed by a live smoke receipt or a documented unavailable reason.

## Six Agent Roles

Use six independent agents. If possible, use six genuinely different model families or provider paths. Do not run six copies of the same frontier model and call it a swarm.

### Agent 1 - Frontier Swarm Architect

Primary duty: critique the whole prior understanding and propose the most powerful overall swarm architecture.

Must answer:

- Why was Forge v0 too weak or too narrow?
- What would a frontier single-model baseline do that v0 failed to challenge?
- What architecture gives the swarm a real chance to beat the best single model?
- Which parts of Dharma Swarm should be integrated first: A2A, Chetana, runtime spine, DGM, AutoResearch, Darwin archive, Verified Experiment Loop, model routing, or benchmark runner?

### Agent 2 - Benchmark And Public Evidence Lead

Primary duty: determine the benchmark ladder.

Must answer:

- Which public benchmarks should be used first, second, and later?
- Which are legitimacy benchmarks, which are learning benchmarks, and which are narrative/inbound benchmarks?
- What subset sizes make sense for 24-hour, 7-day, and 30-day runs?
- What is the exact acceptance threshold for "swarm beats best single model"?
- What public benchmark claims are forbidden until we have real submissions or reproducible receipts?

### Agent 3 - Coordination/A2A Bottleneck Auditor

Primary duty: prove whether coordination is the bottleneck.

Must inspect:

- A2A send receipts
- bridge receipts
- consume proof
- role liveness receipts
- handoff receipts
- stale inbox / dropped-message risk
- NATS subject topology
- composer background loop
- runtime-spine adoption status

Must design telemetry for:

- message sent
- message acknowledged
- message consumed
- reply produced
- final answer used the reply
- latency per edge
- token/cost per edge
- information gain per handoff
- disagreement quality
- contribution attribution
- consensus collapse
- duplicated work
- routing stalls

The current `consumed_by_final_action=true` style flag is not enough. It is a declared flag, not proof of useful use.

### Agent 4 - DGM / Evolutionary Systems Lead

Primary duty: turn benchmark results into safe self-evolution signal.

Must answer:

- How should DGM-style archive search be used here?
- What is the archive entry: prompt, roster, topology, benchmark harness, tool policy, memory policy, or code patch?
- What are the mutation operators?
- What are the fitness dimensions?
- How do we preserve diversity with MAP-Elites/speciation/novelty search?
- How do we avoid Goodharting benchmark scores?
- What is the safe promotion path from shadow candidate to real swarm behavior?
- Which mutations require explicit operator approval?

No autonomous mutation is allowed in this mission. Produce candidate designs only.

### Agent 5 - AutoResearch / Knowledge Loop Lead

Primary duty: make each run teach the swarm as much as possible.

Must answer:

- How should Karpathy-style AutoResearch be adapted to Dharma Swarm?
- What public papers, repos, benchmark traces, failure cases, and winning agent systems should be continuously mined?
- How should research claims become BetCards or hypotheses?
- How should failed experiments become memory without poisoning canon?
- How should Chetana / wiki / memory-kernel promotion record lessons?
- How should the swarm avoid rereading the same obvious public docs every run?

### Agent 6 - Adversarial Evaluator And Anti-Naivete Critic

Primary duty: attack everyone else's conclusions.

Must answer:

- Where are we fooling ourselves?
- Which proposed benchmark path is vanity?
- Which model-pool assumptions are stale?
- Which orchestration design will likely lose to one strong model?
- Which metrics can be gamed?
- Which receipts are theater?
- What would an external evaluator reject?
- What would make this credible to a hostile SWE-bench/METR/DGM-literate reviewer?

This agent must produce a kill-list: ideas that sound powerful but should not be pursued now.

## Debate Protocol

Run at least three rounds:

1. Independent briefs. Each agent writes its own diagnosis without seeing the others.
2. Cross-critique. Each agent reads the other five briefs and identifies the strongest disagreement, weakest assumption, and missing evidence.
3. Forced synthesis. A synthesis agent or council produces one final plan, but must preserve minority reports where disagreement remains real.

Do not average opinions. Resolve by evidence, expected whole-system ROI, and North Star alignment.

## Controls And Benchmark Protocol The Agents Must Design

The final design must include controls strong enough to test the real thesis:

- best single frontier model at equal or greater budget
- best-of-N same model
- same-budget self-MoA
- planner-builder-verifier with no A2A bus
- full A2A swarm
- topology variants: star, chain, debate, graph, blackboard, planner-builder-verifier, adversarial verifier loop
- no-memory baseline
- memory-enabled baseline
- tool-light baseline
- tool-rich baseline

Every benchmark result must track:

- resolved score or task score
- cost
- latency
- token count
- tool calls
- number of agents
- number of handoffs
- failed handoffs
- final answer attribution
- contamination risk
- judge/scorer independence
- exact provider/model roster
- seed and retry policy
- whether public benchmark submission happened

Minimum local repeated-run bar before any claim: 10 valid runs. Public benchmark subsets may start smaller for smoke tests, but no external claim may exceed the evidence.

## Required Final Deliverables

Write outputs under:

`reports/forge/swarm-uplift-six-agent-critique/<timestamp>/`

Required files:

- `README.md` - one-page mission summary and exact command log
- `model_pool_live_roster.json` - actual verified providers/models/transports/fallbacks
- `agent_briefs/agent_1_frontier_swarm_architect.md`
- `agent_briefs/agent_2_benchmark_public_evidence.md`
- `agent_briefs/agent_3_coordination_a2a_bottleneck.md`
- `agent_briefs/agent_4_dgm_evolutionary_systems.md`
- `agent_briefs/agent_5_autoresearch_knowledge_loop.md`
- `agent_briefs/agent_6_adversarial_evaluator.md`
- `cross_critique_matrix.md`
- `public_research_matrix.md`
- `coordination_bottleneck_report.md`
- `benchmark_roadmap.md`
- `forge_v1_or_v2_protocol.md`
- `dgm_autoresearch_integration_plan.md`
- `uplift_levers_ranked.md`
- `kill_list.md`
- `decision_packet.md`
- `receipts.jsonl`

The final `decision_packet.md` must include:

- the single highest-leverage next move
- 24-hour plan
- 7-day plan
- 30-day plan
- benchmark ladder
- proposed six-to-ten model roster
- coordination telemetry schema
- exact controls
- expected cost and time
- stop conditions
- authority boundaries
- what not to do

## Acceptance Criteria

The mission is not complete until:

- six independent agent briefs exist
- each agent reports actual provider/model identity or documented unavailability
- public research has citations
- the weak Forge v0 measurement is directly critiqued
- the North Star benchmark/evolution trust gate is explicitly addressed
- coordination/A2A bottlenecks are treated as first-class, not an afterthought
- DGM/archive/AutoResearch integration is concretely designed
- the benchmark ladder distinguishes internal learning, public legitimacy, and narrative/inbound value
- the final plan explains how the swarm can plausibly beat a single frontier model rather than just spend more tokens
- receipts exist for commands, model checks, research sources, and synthesis decisions
- no production router, trainer, archive fitness, external submission, push, merge, release, live spend authority, or autonomous mutation happened without explicit operator approval

## Suggested Opening Commands

```bash
make onboard
bash scripts/runtime/codex_toolbelt_status.sh
git status --short --branch
python - <<'PY'
import json
from dharma_swarm.model_hierarchy import dump_hierarchy
print(dump_hierarchy())
PY
python - <<'PY'
import json
from dharma_swarm.provider_smoke import run_provider_smoke
print(json.dumps(run_provider_smoke(), indent=2, sort_keys=True))
PY
```

If the provider smoke command risks long live calls or budget burn, ask the operator for explicit GO and record the blocked reason. Never print secrets.

## Tone For Agents

Be severe, specific, and useful.

Do not flatter the swarm.
Do not flatten the vision into generic "multi-agent AI."
Do not say "use better models" without role design, controls, and receipts.
Do not say "run SWE-bench" without saying which split, how many tasks, what budget, what controls, and what claim it can support.
Do not say "coordination matters" without measuring coordination.
Do not promote internal benchmark wins into external reality.

The desired output is a stronger organism, not a comforting report.
