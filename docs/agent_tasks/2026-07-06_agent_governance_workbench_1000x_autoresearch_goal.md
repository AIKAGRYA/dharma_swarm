# Agent Governance Workbench 1000x AutoResearch Goal

Date: 2026-07-06
Status: launch prompt / handoff for a bounded `ds-goal` mission
Authority: research, design, and planning only unless the operator grants a later build lease
Intended runner: Codex `/goal` or repo `ds-goal`

## Pasteable Goal Envelope

```text
/goal Codex: follow docs/agent_tasks/2026-07-06_agent_governance_workbench_1000x_autoresearch_goal.md. Mission: run a six-agent, receipt-backed strategy and architecture mission to determine the single most powerful one-week move for turning Dharma Swarm into a credible Agent Governance/Audit Workbench that can compete with current agent observability, evaluation, security, and governance tools. Integrate Karpathy-style AutoResearch, the repo AutoResearch engine, DGM/open-ended evolution, Forge Proving Ground, and Verified Experiment Loop evidence gates. Decide whether the best move is a demonstrable app, system hardening, a benchmark/proof harness, or a hybrid. No public claims, external outreach, paid spend escalation, production routing mutation, archive-fitness mutation, live DGM patching, memory-canon promotion, deploy, push, PR, or release without explicit operator approval. Close with evidence-linked decision packet, six agent briefs, kill criteria, one-week build plan, verification ladder, and exact next commands.
```

## `ds-goal` Launch Commands

The installed wrapper on this machine should be invoked with the repo venv first
on `PATH`, because direct system Python may be too old for repo runtime imports.

```bash
cd /Users/dhyana/dharma_swarm
MISSION_ID="agent-governance-workbench-1000x-autoresearch-$(date -u +%Y%m%dT%H%M%SZ)"

DHARMA_SWARM_REPO=/Users/dhyana/dharma_swarm PATH=/Users/dhyana/dharma_swarm/.venv/bin:$PATH /Users/dhyana/.dharma/bin/ds-goal init \
  --mission-id "$MISSION_ID" \
  --title "Agent Governance Workbench 1000x AutoResearch" \
  --goal "Follow docs/agent_tasks/2026-07-06_agent_governance_workbench_1000x_autoresearch_goal.md. Run six independent lanes to decide the best one-week move and produce receipt-backed architecture, product, verification, and build packets. Shadow-mode AutoResearch/DGM only; no runtime mutation or public claims." \
  --allowed-write /Users/dhyana/dharma_swarm \
  --verifier-command "make onboard; /Users/dhyana/dharma_swarm/.venv/bin/python scripts/runtime/ds_goal_longrun_preflight.py --json; verify required closeout artifacts, six lane packets, claim/evidence links, authority boundaries, and no unsupported superiority claims." \
  --json

DHARMA_SWARM_REPO=/Users/dhyana/dharma_swarm PATH=/Users/dhyana/dharma_swarm/.venv/bin:$PATH /Users/dhyana/.dharma/bin/ds-goal run \
  --mission-id "$MISSION_ID" \
  --duration-hours 8 \
  --dispatch-mode tmux \
  --json

DHARMA_SWARM_REPO=/Users/dhyana/dharma_swarm PATH=/Users/dhyana/dharma_swarm/.venv/bin:$PATH /Users/dhyana/.dharma/bin/ds-goal status \
  --mission-id "$MISSION_ID" \
  --board-cards \
  --json
```

## Mission Thesis

The best 1000x move is unlikely to be "add more ideas." The repo already has
many ideas. The mission must identify the move that converts those ideas into a
compounding proof machine:

1. a customer-legible artifact that demonstrates what the system claims to do;
2. an internal verifier that can falsify those claims;
3. a research loop that turns failures into better hypotheses;
4. a shadow evolution loop that proposes improvements without mutating trusted
   runtime state;
5. a decision packet that explains why this path beats other repo ideas.

The working product hypothesis is:

```text
Dharma Agent Audit Workbench: given a repo, agent trace, prompt pack, PR,
or autonomous-run artifact, extract claims, classify authority, bind evidence,
score unsupported claims and coordination usefulness, emit a receipt bundle,
and produce a replayable improvement plan.
```

This hypothesis must be treated as falsifiable. The long run may reject it if
another path is stronger.

## Seed Corrections From Fast Six-Lane Precheck

The launch mission starts with these preloaded corrections. The six agents may
falsify them, but they must not ignore them:

- Do not position this as generic agent observability. LangSmith, AgentOps,
  Langfuse, Galileo, Phoenix, Braintrust, Lakera, and Protect AI already occupy
  broad tracing, eval, monitoring, and security ground.
- The sharper wedge is repo-local agent governance proof: was an agent action
  authorized, tested, attributable, blocked or promoted correctly, and repairable?
- The most likely one-week build is CLI-first, not dashboard-first:
  `dharma-swarm governance audit --diff <file> --receipts <dir> --out <dir>`.
- Outputs should be `audit_report.md`, `audit_report.json`, and
  `semantic_receipt.json` for one real repo-local diff plus one real receipt or
  report folder.
- "1000x" must type as a strategy hypothesis until measured against a declared
  baseline such as time-to-proof, cost per verified learning, unsupported-claim
  reduction, first-customer conversion, or benchmark/control lift.
- Six agents do not imply superiority. Prior Forge v0 evidence was negative, so
  any swarm-superiority language must use Forge v1 gates or be forbidden.
- DGM and AutoResearch are proposal engines in this mission, not authority. They
  stay shadow-only unless a later operator lease explicitly permits mutation.

## 1000x Definition

For this mission, "1000x" means leverage, not hype. A valid 1000x path must make
one week of work do at least three of the following:

- become a demo that a skeptical buyer, collaborator, or evaluator can inspect;
- become a verifier that improves internal swarm quality;
- become a benchmark or task suite for Forge/DGM learning;
- become sales collateral with concrete receipts instead of claims;
- become a reusable primitive for claim/evidence/authority type semantics;
- reduce future agent slop by making unsupported claims mechanically visible.

If a proposed path does not create this compounding artifact, it is probably not
the right one-week move.

## First Reads

Every lane must ground conclusions in fresh repo evidence, not memory.

- `make onboard`
- `bash scripts/runtime/codex_toolbelt_status.sh`
- `docs/governance/ACTIVE_TRACK.yaml`
- `reports/forge/FORGE_CANONICAL_INDEX.md`
- `reports/forge/swarm-uplift-six-agent-critique/20260618T020732Z/decision_packet.md`
- `reports/forge/swarm-uplift-six-agent-critique/20260618T020732Z/forge_v1_or_v2_protocol.md`
- `docs/research/VERIFIED_EXPERIMENT_LOOP_RFC.md`
- `docs/research/DARWIN_ENGINE_PERPETUAL_EVOLUTION_RESEARCH.md`
- `dharma_swarm/autoresearch_loop.py`
- `dharma_swarm/auto_research/engine.py`
- `dharma_swarm/dgm_loop.py`
- `tests/test_autoresearch_loop.py`
- `tests/test_auto_research_engine.py`
- `tests/test_dgm_loop.py`
- `scripts/runtime/ds_goal_longrun_preflight.py`
- `docs/archive/DHARMA_SWARM_1000X_MASTERPLAN_2026-03-16.md`
- nearest relevant wiki/docs entries discovered by `rg -n "agent governance|audit|observability|eval|security|claim|evidence|authority|1000x" docs reports dharma_swarm`

If a cited file is missing, stale, branch-only, or contradicted by source/tests,
record that as evidence. Do not silently carry stale mythology forward.

## External Comparison Required

Use current public sources and cite URLs for claims. At minimum compare against:

- LangSmith / LangChain observability and eval workflows;
- AgentOps-style agent observability;
- Langfuse-style open-source LLM observability;
- Galileo-style eval, guardrail, and monitoring platforms;
- Lakera-style agent and prompt security;
- Protect AI / model and AI application security;
- GitHub/CI-native code review and security workflows;
- any stronger current agent governance, eval, red-team, or audit products found.

The comparison must answer:

1. What do they already do better than us?
2. What can we uniquely prove because this repo has receipts, Forge, VEL, DGM,
   AutoResearch, and claim/evidence governance?
3. What buyer or evaluator would care in the next 30 days?
4. What would make them dismiss us immediately?
5. Could LangSmith/Langfuse/AgentOps plus Semgrep/CodeQL produce the same buyer
   artifact in under one day? If yes, narrow or kill the wedge.

The default offer to test is "Agentic Code Governance Sprint": a three-to-seven
day service that installs provenance records, CI gates, audit ledger, and
governed repair PR workflow into one repo. A lower-friction entry offer may be
"Agent PR Risk Audit." These are hypotheses, not claims.

## Six Agent Lanes

Run six independent lanes before synthesis. Use different model families or
reasoning styles where available. If only one runtime family is available,
preserve independence through separate prompts, separate artifacts, and
cross-critique.

### Agent 1 - Product Wedge and Competitor Falsifier

Question: who would use this first, and why would they believe it?

Deliver:

- competitor matrix with source links and access dates;
- three strongest ICPs and why two should be rejected;
- first-customer proof requirement, not just persona language;
- one-page offer for a one-week demo;
- kill criteria for the workbench product hypothesis.

### Agent 2 - Demonstration App Architect

Question: if we are this good, what should we be able to show in one week?

Deliver:

- proposed demo app or CLI workflow from input artifact to receipt bundle;
- minimal screens or CLI commands;
- file/interface candidates in this repo;
- exact acceptance tests;
- what not to build first.

The demo must process at least one real repo-local artifact, not a toy string.
Default candidate if the evidence does not beat it:

- package: `dharma_swarm/agent_governance_workbench/`;
- models: `AuditInput`, `AuditClaim`, `EvidenceRef`, `AuditFinding`,
  `AuditReport`;
- ingestion: unified diff, JSONL receipts, Markdown reports, semantic receipts;
- analyzer: map claims to evidence, flag unsupported claims and authority risk;
- reporter: write matching Markdown and JSON;
- CLI: `dharma-swarm governance audit --diff <file> --receipts <dir> --out <dir>`;
- tests: model serialization, ingest fixtures, unsupported-claim detection,
  Markdown/JSON consistency, CLI end-to-end temp-dir run.

Do not build a web dashboard, SaaS auth/billing, live GitHub App, autonomous DGM
activation, or new receipt ontology before the CLI proof works.

### Agent 3 - AutoResearch and DGM Integrator

Question: how should Karpathy-style AutoResearch and evolved AutoResearch fit
without becoming unsafe self-mutation theater?

Use these local surfaces:

- `dharma_swarm/autoresearch_loop.py` as the Karpathy-style self-improvement
  loop over mutable modules;
- `dharma_swarm/auto_research/engine.py` as the deterministic research report
  substrate;
- `dharma_swarm/dgm_loop.py` as shadow-mode, open-ended DGM proposal machinery;
- `docs/research/DARWIN_ENGINE_PERPETUAL_EVOLUTION_RESEARCH.md` for meta-evolution,
  novelty, MAP-Elites, and anti-convergence gaps.

Deliver:

- safe integration architecture for shadow-mode proposal generation;
- mutation candidates limited to prompts, checks, report schemas, scanners, role
  allocation, task selection, and scoring rubrics unless a later build lease
  authorizes code edits;
- protected surfaces and forbidden mutations;
- tests and dry-run commands required before any live evolution;
- how archived winners and losers become learning signal.

### Agent 4 - Forge and Verified Experiment Loop Lead

Question: how does the workbench prove improvement instead of producing more
convincing documents?

Use:

- `reports/forge/FORGE_CANONICAL_INDEX.md`
- Forge v1 protocol and claim gates;
- `docs/research/VERIFIED_EXPERIMENT_LOOP_RFC.md`

Deliver:

- verification ladder for the workbench;
- baseline/control arms: single-agent audit, generic LLM audit, no-receipt
  audit, workbench audit;
- receipt schema for workbench outputs;
- claim gates for "better than generic audit";
- stop conditions for unsupported superiority.

The verifier is the fitness function. Self-report is not fitness.

### Agent 5 - Typed Claim, Evidence, and Authority Designer

Question: what is the smallest typed semantics contribution this product should
make?

Keep the standing question in view:

```text
How do we develop an AI-native programming language where epistemic modality and
authority are typechecker/evaluator semantics, not just runtime receipts?
```

Deliver one small, challengeable contribution, not a manifesto:

- typed claim shape for the workbench;
- authority levels and promotion rules;
- proof obligations for each claim type;
- evaluator behavior for unsupported, contradicted, ungrounded, or over-authorized
  claims;
- one fixture that would fail without authority semantics.

Minimum schema to include:

```text
TypedClaim.v1:
  claim_id, text, modality, scope, owner_agent, confidence, status,
  created_at, expires_at, evidence_refs[], counterevidence_refs[],
  authority_ref, promotion_state

EvidenceRef.v1:
  evidence_id, kind, uri_or_path, line_ref, sha256, observed_at, produced_by,
  verifier, privacy_tag, freshness_policy

AuthorityLease.v1:
  lease_id, granted_by, holder, authority_kind, allowed_actions[],
  forbidden_actions[], expires_at, receipt_ref

EvaluationPacket.v1:
  packet_id, agent_id, model_identity, task_lane, claims[], decision,
  acceptance_gates[], missing_evidence[], verdict, confidence
```

Allowed claim modalities: `repo_observation`, `runtime_observation`,
`external_source_claim`, `benchmark_result`, `forecast`,
`strategy_hypothesis`, `recommendation`, `authority_claim`.

Type obligations:

- `repo_observation` needs file-line or command-output evidence;
- `runtime_observation` needs runtime receipt or explicit blocked reason;
- `external_source_claim` needs URL, access date, and freshness policy;
- `benchmark_result` needs scorer, dataset/split, raw artifact hash, budget,
  retry policy, and baseline;
- `forecast` and `strategy_hypothesis` need success criteria, kill criteria,
  and expiry;
- `recommendation` must cite at least one supported claim and one rejected
  alternative;
- `authority_claim` requires an authority lease or must be blocked.

### Agent 6 - Adversarial Reviewer and Revenue Gatekeeper

Question: where are we fooling ourselves, and what would make this commercially
or epistemically dead?

Deliver:

- overclaim traps;
- budget and scope boundaries;
- no-go list;
- pricing and packaging hypotheses;
- external acted receipt requirement;
- final dissent if the synthesis is too soft.

## Coordination Protocol

Round 1: independent briefs. Each lane writes without reading the other lane
outputs.

Round 2: cross-critique. Each lane reads the other five outputs and records:

- strongest agreement;
- strongest disagreement;
- weakest assumption;
- missing evidence;
- one change it would force in the final plan.

Round 3: forced synthesis. The synthesis must choose one one-week move and
preserve real minority reports.

Do not average opinions. Resolve by evidence, buyer/evaluator credibility,
verification strength, and compounding value.

## Required Outputs

Write artifacts under:

```text
reports/agentops/work_packets/agent-governance-workbench-1000x/
```

Required files:

- `mission_baseline.md`
- `agent_1_product_wedge.md`
- `agent_2_demo_architect.md`
- `agent_3_autoresearch_dgm.md`
- `agent_4_forge_vel.md`
- `agent_5_typed_claims.md`
- `agent_6_adversarial_revenue.md`
- `cross_critique_matrix.md`
- `AGENT_GOVERNANCE_WORKBENCH_1000X_DECISION.md`
- `agent_governance_workbench_mvp_spec.md`
- `autoresearch_dgm_integration_plan.md`
- `verification_ladder.md`
- `one_week_build_plan.md`
- `typed_claims_authority_spec.md`
- `competitor_icp_falsification_matrix.md`
- `six_agent_closeout_receipt.json`

The decision file must answer plainly:

1. Should the next week be spent building a demonstration app?
2. If yes, what exactly is the app and why this over other repo ideas?
3. If no, what beats it and what proof makes that true?
4. What is the smallest first slice that can be verified in one day?
5. What exact command or prompt should launch the build after this strategy run?

## Closeout Receipt Schema

`six_agent_closeout_receipt.json` must be valid JSON with at least:

```json
{
  "schema_version": "dharma.agent_governance_workbench_1000x.v1",
  "mission_id": "...",
  "started_at_utc": "...",
  "completed_at_utc": "...",
  "repo": "/Users/dhyana/dharma_swarm",
  "branch": "...",
  "head": "...",
  "dirty_worktree_summary": "...",
  "lanes_completed": 6,
  "required_outputs_present": true,
  "recommended_one_week_move": "demo_app|verification_harness|system_hardening|hybrid|kill",
  "decision_confidence": "low|medium|high",
  "claim_gate_status": "pass|amber|fail",
  "typed_claim_packets_valid": false,
  "first_customer_proof_required": true,
  "autoresearch_dgm_mode": "shadow_only",
  "runtime_mutation_performed": false,
  "public_claims_authorized": false,
  "external_outreach_performed": false,
  "verification_commands": [],
  "blockers": [],
  "next_launch_command": "..."
}
```

## Verification Commands

Run and record:

```bash
make onboard
bash scripts/runtime/codex_toolbelt_status.sh
/Users/dhyana/dharma_swarm/.venv/bin/python scripts/runtime/ds_goal_longrun_preflight.py --json
/Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_autoresearch_loop.py tests/test_auto_research_engine.py tests/test_dgm_loop.py tests/test_ds_goal_longrun_preflight.py -q
```

If any command fails, do not hide it. The final decision may still be useful,
but the claim gate becomes `amber` or `fail` depending on severity.

## Authority Boundaries

This mission may inspect, design, and write report artifacts. It may not:

- perform external outreach;
- spend paid API budget beyond already configured normal agent use;
- submit public benchmarks;
- deploy services;
- push, merge, tag, or release;
- mutate production routing, provider hierarchy, trusted memory, archive fitness,
  or DGM target code;
- run live DGM mutation with `DHARMA_EVOLUTION_SHADOW=0`;
- edit protected files listed by AutoResearch or DGM;
- claim market superiority or benchmark superiority.

Any build implementation after this mission requires a separate explicit build
lease with owned files, tests, budget, rollback plan, and definition of done.

## Valid Closeout States

- `recommended_demo_app`: build the workbench demo next.
- `recommended_verification_harness`: build the proof harness first.
- `recommended_system_hardening`: system is not credible enough for demo yet.
- `recommended_hybrid`: build a narrow demo whose core is the verifier.
- `kill_or_pause`: product thesis failed or evidence is too weak.
- `blocked_with_evidence`: mission could not complete because of a concrete
  external, tooling, or authority blocker.

Unsupported optimism is not a valid closeout state.
