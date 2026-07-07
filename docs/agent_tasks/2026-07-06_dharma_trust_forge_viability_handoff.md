# Dharma Trust Forge Viability Handoff

Date: 2026-07-06
Status: handoff brief for one system-aware viability agent
Authority: read-only evaluation unless the operator grants a separate build lease
Primary target: Forge Agent Boundary CI

## Mission

Evaluate whether Dharma Trust Forge should proceed as the next focused swarm
target, and if yes, define the smallest test that can falsify or validate it
within 24 hours.

The working product is:

```text
Forge Agent Boundary CI:
replayable authority-boundary regressions for MCP/tool-using agents,
with a scorecard, remediation PR, and continuous eval harness.
```

Do not evaluate this as a generic agent observability platform, generic AI
security platform, academic paper, or grant lane. The narrow claim is:

```text
Given repo/tool/policy state R, untrusted context S cannot cause privileged
action A without an explicit authority lease, and the proof is replayable.
```

## Context Files

Read these first:

- `docs/agent_tasks/2026-07-06_dharma_trust_forge_overnight_autoresearch_goal.md`
- `scripts/governance/verify_dharma_trust_forge_goal.py`
- `tests/test_verify_dharma_trust_forge_goal.py`
- `docs/agent_tasks/2026-07-06_agent_governance_workbench_1000x_autoresearch_goal.md`
- `docs/vision_maps/NORTH_STAR.md`
- `foundations/THE_ORGANISM.md`
- `reports/forge/FORGE_CANONICAL_INDEX.md`
- `docs/research/VERIFIED_EXPERIMENT_LOOP_RFC.md`
- `dharma_swarm/autoresearch_loop.py`
- `dharma_swarm/auto_research/engine.py`
- `dharma_swarm/dgm_loop.py`

If a file is missing, stale, or contradicted by source/tests, record that as a
finding. Do not preserve mythology.

## Current Synthesis To Test

The previous pass converged on these claims:

1. The strongest buyer is a B2B agent builder or enterprise AI platform team
   whose agents touch repos, CI, credentials, tools, customer data, or business
   workflows.
2. The strongest wedge is CI-native authority-boundary regression, not generic
   tracing, evals, or red teaming.
3. The first SKU should be a fixed diagnostic or five-day pilot:
   - diagnostic: about `$2.5k`;
   - five-day pilot: about `$9.5k`;
   - remediation sprint: about `$18k+`.
4. The first MVP should be offline and boring:
   `dharma_swarm/forge_agent_boundary_ci/` with JSON fixtures, pure rules,
   receipts, Markdown/JSON/JUnit output, and no provider/network/live mutation.
5. The first five rules should be:
   - `FAB-01`: forbidden path writes block;
   - `FAB-02`: tools outside `allowed_tools` block;
   - `FAB-03`: live credentials or external URLs block when external policy is
     `none`;
   - `FAB-04`: authoritative claims without receipt evidence block;
   - `FAB-05`: attempts to edit verifier/gold fixture files block.
6. Every result should become both:
   - a semantically dense Karpathy-style wiki atom;
   - a future eval candidate.

## Required External Context

Use current public sources if making market or competitor claims. Minimum source
set:

- https://docs.langchain.com/langsmith/observability
- https://docs.langchain.com/langsmith/engine-overview
- https://langfuse.com/docs
- https://www.braintrust.dev/docs
- https://docs.agentops.ai/
- https://modelcontextprotocol.io/docs/getting-started/intro
- https://modelcontextprotocol.io/specification/2025-06-18
- https://0din.ai/scope
- https://www.grayswan.ai/
- https://arxiv.org/abs/2601.17549
- https://arxiv.org/abs/2603.22489

If browsing is unavailable, mark external claims as unverified and reason from
local evidence only.

## Viability Questions

Answer these directly:

1. Is this on-brand for Dharma Swarm/Telos, or is it still too myopic?
2. Does it aim the swarm at one thing, or does it fragment into paper/grant/
   security/Forge/wiki lanes again?
3. Is the wedge narrow enough to survive comparison against LangSmith,
   Langfuse, Braintrust, AgentOps, Gray Swan, 0DIN, Lakera, Protect AI,
   Semgrep/CodeQL, and consultants?
4. Can this become a massive feedback loop, not just a service?
5. Can it make money within 30 days without making dishonest claims?
6. What is the smallest local proof in 24 hours?
7. What is the smallest external proof in 7 days?
8. What would kill the thesis?
9. What should not be built yet?
10. What exact `/goal`, command, or build lease should launch next?

## Required Verdict Format

Write the viability result to:

```text
reports/agentops/work_packets/dharma-trust-forge-viability/VIABILITY_REVIEW.md
reports/agentops/work_packets/dharma-trust-forge-viability/viability_receipt.json
```

`VIABILITY_REVIEW.md` must include:

- verdict: `go`, `narrow_go`, `hold`, or `kill`;
- viability score: `0-100`;
- confidence: `0-100`;
- strongest reason to proceed;
- strongest reason to kill;
- 24-hour falsification test;
- 7-day external proof test;
- 30-day money test;
- first build slice;
- no-build list;
- required proof artifacts;
- exact next launch command.

`viability_receipt.json` must include:

```json
{
  "schema_version": "dharma.trust_forge_viability_review.v1",
  "reviewed_at_utc": "...",
  "repo": "/Users/dhyana/dharma_swarm",
  "branch": "...",
  "head": "...",
  "verdict": "go|narrow_go|hold|kill",
  "viability_score": 0,
  "confidence": 0,
  "external_claims_verified": false,
  "recommended_next_action": "...",
  "first_24h_test": "...",
  "first_7d_external_test": "...",
  "first_30d_money_test": "...",
  "sources": [],
  "verification_commands": [],
  "blockers": []
}
```

## Verification Commands

Run and record:

```bash
make onboard
bash scripts/runtime/codex_toolbelt_status.sh
/Users/dhyana/dharma_swarm/.venv/bin/python scripts/runtime/ds_goal_longrun_preflight.py --json
/Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_verify_dharma_trust_forge_goal.py -q
```

Optional if doing a deeper local proof:

```bash
/Users/dhyana/dharma_swarm/.venv/bin/python scripts/governance/verify_dharma_trust_forge_goal.py --json
```

The last command is expected to fail until the overnight artifact bundle exists.
Do not treat that failure as a blocker to viability; treat it as proof that the
closeout gate is not fake.

## Safety Boundary

Allowed:

- read repo files;
- inspect public sources;
- write the two viability artifacts above;
- run local tests;
- propose a build lease.

Forbidden without explicit operator authorization:

- external outreach;
- public claims;
- GitHub issue/PR creation;
- pushing, merging, releasing;
- paid spend escalation;
- credentialed browsing actions;
- deploy;
- live DGM mutation;
- trusted-memory promotion;
- provider routing mutation;
- archive-fitness mutation.

## Bias To Falsification

Do not sell the idea back to the operator. Try to kill it. It survives only if
the 24-hour test and 7-day external proof are concrete enough that another agent
can run them and produce receipts.
