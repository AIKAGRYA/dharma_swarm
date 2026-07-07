# Dharma Trust Forge Overnight AutoResearch Goal

Date: 2026-07-06
Status: launch prompt / handoff for a bounded ten-lane Codex `/goal`
Authority: research, specification, MVP planning, and local artifact generation only
Target: one sellable, paid-or-countersigned pilot for agent authority-boundary CI

## Pasteable Goal Envelope

```text
/goal Follow docs/agent_tasks/2026-07-06_dharma_trust_forge_overnight_autoresearch_goal.md.
Mission: run a ten-lane, receipt-backed AutoResearch loop for Dharma Trust Forge: a paid, public or private, continuously improving reliability/security scorecard plus remediation PR plus continuous eval harness for MCP/tool-using agents and autonomous coding systems. The loop must brainstorm, research, spec, MVP, validate, step back, cross-critique, and repeat until it emits one sellable pilot package with fixture catalog, scorecard schema, remediation offer, target buyer, verification ladder, and exact next build command.
No external outreach, public claims, production deploy, paid spend escalation, live DGM mutation, credentialed site action, GitHub issue/PR creation, push, merge, trusted-memory promotion, or archive-fitness mutation without explicit operator authorization.
Close only when scripts/governance/verify_dharma_trust_forge_goal.py passes on reports/agentops/work_packets/dharma-trust-forge-overnight-autoresearch/.
```

## One Target

Dharma Trust Forge is not a generic observability tool, not a grant-paper lane,
and not "the AI security platform." The narrow product name for this overnight
loop is:

```text
Forge Agent Boundary CI:
replayable authority-boundary regressions for MCP/tool-using agents,
with a scorecard, remediation PR, and continuous eval harness.
```

The paid unit is a countersigned pilot. A customer or maintainer gives a repo,
agent trace, MCP server, prompt pack, or workflow. The Forge returns:

- reproducible failures;
- scored reliability/security dimensions;
- evidence bundle with traces, fixtures, hashes, and claim obligations;
- remediation PR or patch plan;
- rerun proof showing before/after delta;
- a countersignature surface: accepted finding, maintainer comment, paid invoice,
  merged PR, or buyer signoff.

Do not optimize for insight. Optimize for one artifact a stranger can inspect,
pay for, reject, or countersign.

The core evaluator claim is:

```text
Given repo/tool/policy state R, untrusted context S cannot cause privileged
action A without an explicit authority lease, and the proof is replayable.
```

Acceptable claim statuses are `untested`, `falsified`, `observed`,
`reproduced`, `remediated`, `verified-in-scope`, `countersigned`, `waived`, and
`expired`. Never say "safe" without the `verified-in-scope` boundary.

## Market Grounding

The loop must compare against current tools and papers rather than internal
mythology.

Required public sources include at least:

- LangSmith observability: https://docs.langchain.com/langsmith/observability
- Langfuse docs: https://langfuse.com/docs
- Braintrust docs: https://www.braintrust.dev/docs
- AgentOps docs: https://docs.agentops.ai/
- MCP official intro: https://modelcontextprotocol.io/docs/getting-started/intro
- MCP 2025-06-18 specification: https://modelcontextprotocol.io/specification/2025-06-18
- 0DIN/Mozilla GenAI bug bounty scope: https://0din.ai/scope
- Gray Swan AI security and adversarial evaluation: https://www.grayswan.ai/
- MCP security paper: https://arxiv.org/abs/2601.17549
- MCP prompt-injection/tool-poisoning paper: https://arxiv.org/abs/2603.22489
- AI-assisted development prompt-injection paper: https://arxiv.org/abs/2603.21642

Use source links and access date for every market, security, or competitor
claim. If a source cannot be checked, mark the claim as unverified.

## First Reads

Run or read fresh evidence before lane work:

```bash
make onboard
bash scripts/runtime/codex_toolbelt_status.sh
/Users/dhyana/dharma_swarm/.venv/bin/python scripts/runtime/ds_goal_longrun_preflight.py --json
docs/vision_maps/NORTH_STAR.md
foundations/THE_ORGANISM.md
docs/agent_tasks/2026-07-06_agent_governance_workbench_1000x_autoresearch_goal.md
reports/forge/FORGE_CANONICAL_INDEX.md
docs/research/VERIFIED_EXPERIMENT_LOOP_RFC.md
docs/research/DARWIN_ENGINE_PERPETUAL_EVOLUTION_RESEARCH.md
dharma_swarm/autoresearch_loop.py
dharma_swarm/auto_research/engine.py
dharma_swarm/dgm_loop.py
scripts/governance/verify_dharma_trust_forge_goal.py
```

If a file is missing or stale, record that as evidence. Do not silently preserve
old doctrine.

## Round Structure

Round 0 - Baseline:

- capture repo branch, dirty summary, live ds-goal state, toolbelt state;
- state the target in one sentence;
- list known blockers and authority boundaries.

Round 1 - Independent lanes:

- ten lanes write without reading each other;
- every lane emits claims with evidence, confidence, and kill criteria;
- no lane may claim market superiority without a cited comparison.

Round 2 - Cross-critique:

- each lane reads all other lane outputs;
- each records strongest agreement, strongest disagreement, weakest assumption,
  missing evidence, and one forced change.

Round 3 - Forced synthesis:

- pick one pilot offer and one first build slice;
- preserve minority reports;
- write a verifier-backed closeout receipt.

Round 4 - Step-back/repeat:

- run one adversarial pass over the chosen pilot;
- revise the scorecard, pricing, fixtures, and MVP spec;
- final decision must say what changed because of the adversarial pass.

## Ten Lanes

### Agent 1 - Buyer Wound and ICP

Question: who urgently needs this and can pay or countersign?

Deliver:

- three ICPs, two rejected ICPs, and why;
- buyer titles, budget path, trigger events, and procurement friction;
- twenty named prospect categories or example organizations;
- first proof a buyer would need before paying;
- kill criteria for the buyer thesis.

Verifier: another lane can state the 90-second offer and name who signs.

### Agent 2 - Competitive Edge

Question: why this over LangSmith, Langfuse, Braintrust, AgentOps, Gray Swan,
0DIN, Lakera, Protect AI, Semgrep/CodeQL, or consultants?

Deliver:

- competitor matrix with source URLs;
- what each competitor does better;
- narrow defensible wedge;
- claims forbidden because they are too broad;
- dismissal risks.

Verifier: at least one competitor could plausibly beat the broad version; the
lane must narrow the offer until this is no longer fatal.

Forbidden default claims:

- "We replace LangSmith/Braintrust/Langfuse."
- "We are the AI security platform."
- "We solve prompt injection."
- "Formal proof of agent safety."
- "100/100 trust score means safe."

Preferred claim:

```text
We catch scoped authority-boundary regressions and prove remediations in CI.
```

### Agent 3 - MCP and Agent Threat Surface

Question: what failure modes should the Forge score?

Deliver taxonomy for:

- prompt injection and tool poisoning;
- capability attestation and false tool descriptions;
- excessive agency and unsafe tool invocation;
- filesystem roots and path traversal;
- auth/session leakage;
- multi-server trust propagation;
- missing audit logging;
- sandbox escape and code execution;
- memory poisoning;
- rollback/undo failure;
- evidence/provenance overclaim.

Verifier: each top threat maps to a runnable local fixture or a clear external
scope that is not attempted without authorization.

Required typed rule:

```text
Data<origin=untrusted, server=A> must not flow into
ToolCall<server=B, effect=write|send|network|secret-read>
unless accompanied by Authority<UserConsent, scope, server_pair=A->B, expiry>
and an audit trace.
```

### Agent 4 - Eval Fixture Factory

Question: what failures can be repeatedly induced overnight?

Deliver:

- twenty-five fixture candidates;
- for each: setup, stimulus, expected failure, pass condition, artifact captured,
  and scorecard row;
- mark which ten can run locally first;
- mark which require sandbox, external system, or authorization.

Verifier: a separate reproducer should be able to implement three fixtures from
the description without asking follow-up questions.

### Agent 5 - Scorecard and Typed Claims

Question: what is the smallest typed semantics contribution?

Deliver:

- `TrustForgeScorecard.v1`;
- `Finding.v1`;
- `EvidenceRef.v1`;
- `RemediationDelta.v1`;
- `Countersignature.v1`;
- authority and modality rules for observed, reproduced, remediated,
  countersigned, waived, and expired claims.

Verifier: one fixture must fail if authority semantics are removed.

### Agent 6 - Remediation Playbook

Question: what can be sold beyond reporting?

Deliver:

- fix catalog for each top failure class;
- patch package shapes: policy gate, sandbox, eval, logging, approval flow,
  rollback guard, root boundary, tool manifest hardening;
- before/after evidence required;
- "do not fix" and waiver handling.

Verifier: each package has a concrete artifact a buyer receives.

### Agent 7 - MVP Architecture

Question: what can be built first in one day and one week?

Default MVP shape:

```text
dharma_swarm/trust_forge/
  models.py
  ingest.py
  fixtures.py
  scorecard.py
  report.py
  cli.py
```

Default CLI:

```bash
dharma-swarm trust-forge scorecard \
  --target <repo-or-trace-dir> \
  --fixtures <fixture-dir> \
  --receipts <receipt-dir> \
  --out <report-dir>
```

Deliver:

- one-day slice;
- one-week slice;
- data models and file interfaces;
- acceptance tests;
- what not to build.

Verifier: an end-to-end temp-dir test can generate Markdown and JSON from one
fixture and one sample trace.

### Agent 8 - Karpathy Wiki and Memory Metabolism

Question: how does this become always-on culture, not another report?

Deliver:

- wiki atom schema for failures, fixtures, remediations, buyer objections,
  competitor claims, source pages, and pilot outcomes;
- orphan prevention rules;
- `make onboard` / `make orient` adoption surface;
- daily metabolism loop;
- how agents query the wiki before work.

Verifier: every new pilot finding becomes at least one linked wiki atom and one
future eval candidate.

### Agent 9 - Revenue Packaging and Delivery Ops

Question: what exactly can be sold tomorrow?

Deliver:

- three packages: diagnostic scorecard, remediation sprint, retained trust
  monitoring;
- price hypotheses and boundaries;
- five-day pilot SOP;
- intake checklist and access requirements;
- external acted receipt definition;
- first outreach script as a draft only, not sent.

Verifier: the package has a deliverable, buyer signer, and explicit non-goals.

Default package hypotheses:

- Diagnostic scorecard: one agent/tool surface, fixed scope, fixed fee.
- Remediation sprint: failing fixtures plus PR-ready fixes and CI gates.
- Retained boundary CI: monthly fixture updates, model/tool upgrade gates, and
  customer-facing evidence pack refresh.

### Agent 10 - Adversarial Go/No-Go Council

Question: where are we fooling ourselves?

Deliver:

- strongest reasons this is dead;
- overclaim traps;
- operational risks;
- evidence that would change the recommendation;
- final go/no-go with confidence;
- exact kill criteria after 7 days and 30 days.

Verifier: if the synthesis is too soft, this lane must force a narrower pilot
or a no-go.

## Required Output Directory

Write all mission artifacts under:

```text
reports/agentops/work_packets/dharma-trust-forge-overnight-autoresearch/
```

Required files:

- `mission_baseline.md`
- `agent_01_buyer_wound.md`
- `agent_02_competitive_edge.md`
- `agent_03_mcp_threat_surface.md`
- `agent_04_eval_fixture_factory.md`
- `agent_05_scorecard_typed_claims.md`
- `agent_06_remediation_playbook.md`
- `agent_07_mvp_architecture.md`
- `agent_08_karpathy_wiki_memory.md`
- `agent_09_revenue_packaging_ops.md`
- `agent_10_adversarial_go_no_go.md`
- `cross_critique_matrix.md`
- `DHARMA_TRUST_FORGE_OVERNIGHT_DECISION.md`
- `mvp_scorecard_spec.md`
- `eval_fixture_catalog.md`
- `remediation_playbook.md`
- `pricing_packaging_offer.md`
- `adoption_and_memory_plan.md`
- `validation_and_metrics_plan.md`
- `closeout_receipt.json`

## Closeout Receipt

`closeout_receipt.json` must be valid JSON:

```json
{
  "schema_version": "dharma.trust_forge_overnight_autoresearch.v1",
  "mission_id": "...",
  "started_at_utc": "...",
  "completed_at_utc": "...",
  "repo": "/Users/dhyana/dharma_swarm",
  "branch": "...",
  "head": "...",
  "dirty_worktree_summary": "...",
  "lanes_completed": 10,
  "required_outputs_present": true,
  "recommended_next_action": "build_mvp_scorecard|run_customer_probe|kill_or_pause|narrow_scope",
  "decision_confidence": "low|medium|high",
  "sellable_pilot_present": true,
  "first_customer_proof_required": true,
  "external_actions_performed": false,
  "public_claims_authorized": false,
  "runtime_mutation_performed": false,
  "autoresearch_dgm_mode": "shadow_only",
  "verification_commands": [],
  "sources": [],
  "blockers": [],
  "next_launch_command": "..."
}
```

## Verification

Required commands:

```bash
make onboard
bash scripts/runtime/codex_toolbelt_status.sh
/Users/dhyana/dharma_swarm/.venv/bin/python scripts/runtime/ds_goal_longrun_preflight.py --json
/Users/dhyana/dharma_swarm/.venv/bin/python scripts/governance/verify_dharma_trust_forge_goal.py --report-dir reports/agentops/work_packets/dharma-trust-forge-overnight-autoresearch --json
```

Verifier rule: the final command must pass before the mission can claim closure.
Until it passes, the mission is useful but not closed.

## Repo-Native Ledger Commands

The current `ds-goal` supervisor is a ledger and verifier wrapper; it does not
itself fan out ten reasoning agents. Use it to register and monitor the mission,
not to overclaim ten-agent execution.

```bash
cd /Users/dhyana/dharma_swarm
MISSION_ID="dharma-trust-forge-overnight-$(date -u +%Y%m%dT%H%M%SZ)"

DHARMA_SWARM_REPO=/Users/dhyana/dharma_swarm \
PATH=/Users/dhyana/dharma_swarm/.venv/bin:$PATH \
/Users/dhyana/.dharma/bin/ds-goal init \
  --mission-id "$MISSION_ID" \
  --title "Dharma Trust Forge Overnight AutoResearch" \
  --goal "Follow docs/agent_tasks/2026-07-06_dharma_trust_forge_overnight_autoresearch_goal.md. Produce the required ten-lane artifact bundle and pass scripts/governance/verify_dharma_trust_forge_goal.py. No external outreach, public claims, live mutation, push, PR, deploy, or paid spend." \
  --allowed-write reports/agentops/work_packets/dharma-trust-forge-overnight-autoresearch \
  --allowed-write docs/agent_tasks \
  --verifier-command "/Users/dhyana/dharma_swarm/.venv/bin/python scripts/governance/verify_dharma_trust_forge_goal.py --report-dir reports/agentops/work_packets/dharma-trust-forge-overnight-autoresearch" \
  --json

DHARMA_SWARM_REPO=/Users/dhyana/dharma_swarm \
PATH=/Users/dhyana/dharma_swarm/.venv/bin:$PATH \
/Users/dhyana/.dharma/bin/ds-goal status \
  --mission-id "$MISSION_ID" \
  --board-cards \
  --json
```

Do not run `ds-goal run` as proof of ten-agent cognition unless the actual
ten-lane artifacts are already written by a live `/goal` or explicitly managed
subagents. The verifier will block placeholder closure.

## Authority Boundaries

Allowed:

- local repo reads;
- public web research;
- local report/spec artifacts;
- local verifier and tests;
- shadow-only AutoResearch/DGM proposals;
- draft outreach copy, not sent.

Forbidden without explicit operator authorization:

- external outreach, posting, commenting, voting, submitting bounties, or filing
  GitHub issues/PRs;
- credentialed browsing actions;
- paid spend escalation;
- production deploy;
- trusted memory promotion;
- live DGM mutation;
- public superiority claims;
- changing provider routing, archive fitness, or protected runtime state.

## Success Definition

The overnight loop succeeds if it produces a verifier-passing bundle whose
decision file names:

1. the first buyer or maintainer segment;
2. the exact scorecard dimensions;
3. ten locally runnable first fixtures or a clear reason fewer are possible;
4. the first one-day MVP slice;
5. the five-day paid/countersigned pilot offer;
6. one next command that starts implementation.

Anything less is a research packet, not a closed mission.
