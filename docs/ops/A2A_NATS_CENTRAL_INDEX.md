# A2A/NATS Central Index

Date: 2026-07-02 (routing role superseded 2026-07-09)
Status: historical integration map for the A2A/NATS lane

> **2026-07-09:** For connect-time routing truth (who is live, on which
> broker, which subjects, which credential env vars), read
> `docs/ops/FLEET_FIELD_REGISTRY.yaml` first
> (`python3 scripts/runtime/fleet_field_registry.py`) — it is refreshed by
> probe receipts, per registry decision FFR-D3. The worktree/PR pointers
> below are operator-machine-local and historical; they are not reachable
> from a clean checkout.

## One Place

Use this as the simple address for the latest organized A2A/NATS work:

- Worktree: `/Users/dhyana/ds_a2a_always_on_spine_20260701`
- Branch: `codex/a2a-always-on-spine-20260701`
- PR: https://github.com/AmitabhainArunachala/dharma_swarm/pull/744
- Base: latest `origin/main` merged on 2026-07-02, including PR #745 worktree-readiness evidence

This is the central branch. The dirty root worktree at `/Users/dhyana/dharma_swarm` is not the central place.

## Plain Model

A2A is the contract between agents. NATS is the durable wire underneath that contract. Receipts are the truth layer that lets us prove what happened after the fact.

So the real spine is:

```text
operator intent
  -> A2A task envelope
  -> A2ANatsTransport / NATS JetStream
  -> agent handler
  -> receipt + artifact + reply
  -> operator-visible response
```

Anything that bypasses that path may still be useful, but it is not yet proof of a working always-on A2A system.

## Active Track Truth

`docs/governance/ACTIVE_TRACK.yaml` says `runtime-truth-nats-2026-06` is:

- `status: SHIPPED`
- `closure_kind: VERIFIED_SLICE`
- not a production live-readiness claim
- not a `SUBSTRATE_TRUSTED` claim

That distinction matters. The NATS lane has real verified transport work, but the repo should not claim full always-on production A2A until the remaining hard gaps are closed.

## Central Branch Contents

The central branch currently carries:

- `A2ANatsTransport` hardening for task envelopes, identity, idempotency, ack/nack, retry, MaxDeliver, DLQ, and duplicate handling.
- Live NATS production matrix runner and freshness/source-hash validator.
- Fresh local-live evidence generated on this branch, not just copied from an older drifted branch.
- `pramana_probe.py` as an evidence-tier conductor.
- The Claude reconciliation handoff, kept as a knowledge base.
- The anti-sprawl A2A coordination substrate doctrine, kept as architecture documentation.
- The always-on spine master plan that maps A2A, NATS, MCP, LangGraph, voice, planning, evaluation, and guardrails into one intended system shape.
- Latest main governance/worktree-readiness evidence from PR #745.

Primary files:

- `docs/architecture/A2A_ALWAYS_ON_SPINE_MASTER_PLAN.md`
- `docs/architecture/A2A_COORDINATION_SUBSTRATE.md`
- `docs/ops/A2A_LOCAL_RECONCILIATION_HANDOFF.md`
- `reports/governance/a2a_always_on_spine_reconciliation_2026-07-01.md`
- `reports/governance/nats_live_production_matrix/latest.json`
- `scripts/governance/run_nats_live_production_matrix.py`
- `scripts/governance/check_nats_live_production_evidence.py`
- `scripts/governance/pramana_probe.py`
- `dharma_swarm/a2a/nats_transport.py`

## Source Disposition

This table is the current operational index, not a claim that every historical A2A/NATS-adjacent branch has been exhaustively diffed. Historical archaeology is listed where it changes merge decisions; otherwise it remains representative background until a targeted diff proves unique value.

| Source | Local address / branch | PR | Disposition |
|---|---|---:|---|
| Central A2A/NATS spine | `/Users/dhyana/ds_a2a_always_on_spine_20260701`, `codex/a2a-always-on-spine-20260701` | #744 | Canonical integration place. Keep building here. |
| Dirty root worktree | `/Users/dhyana/dharma_swarm`, `agent/magpie-seed` | mixed | Not canonical. Contains valuable local A2A/NATS dirt, but also unrelated work. Harvest deliberately; do not merge wholesale. |
| Runtime Truth NATS live evidence | `/Users/dhyana/ds_runtime_truth_nats_clean_20260701`, `codex/runtime-truth-nats-live-evidence-20260701` | #739 | Merged. Useful code/evidence was ported into #744; stale generated evidence was regenerated. |
| Claude A2A/NATS review branch | `/private/tmp/ds_pr729_a2a_nats_review_20260630`, `claude/a2a-nats-review-test-ncol7c` | #729 | Merged to main. Keep docs, handoff, workflow, and `pramana_probe.py`. Do not wire superseded `coordination_substrate/**`. |
| A2A governance readiness | `/Users/dhyana/worktrees/ds_a2a_governance_readiness_20260626`, `codex/a2a-governance-readiness-20260626` | #703 | Historical merged readiness lane. Treat as background evidence, not current implementation owner. |
| NATS rebuild preflight | `/Users/dhyana/ds_a2a_nats_rebuild_preflight_20260618`, `runtime-truth/nats-rebuild-preflight-20260618` | none/currently preserved | Historical/superseded by #739 and #744 unless a later targeted diff proves unique value. |
| Worktree readiness closeout | `/Users/dhyana/ds_worktree_readiness_closeout_20260702`, `codex/worktree-readiness-closeout-20260702` | #745 | Merged into main and now merged into #744. Useful for inventory context. |
| LangGraph parity | `/Users/dhyana/ds_langgraph_parity_20260701`, `codex/langgraph-orchestration-parity-20260701` | #732 | Related next layer. Current PR state: draft and DIRTY against main. Do not fold into A2A/NATS core until canonical task transport is production-wired. |
| LangGraph parity verifier scratch | `/Users/dhyana/dharma_swarm/.claude/worktrees/langgraph-parity-verifier-20260701`, `worktree-langgraph-parity-verifier-20260701` | none/direct | Dirty verifier worktree with LangGraph/A2A verification scripts and reports. Human decision required before harvesting; do not merge wholesale. |
| LangGraph PR #727 local temp checkout | `/private/tmp/dharma-lgp-pr`, `main` behind `origin/main` | #727 | Dirty temp checkout around merged LangGraph parity readiness work. Covered indirectly by #727/#732/#746, but local dirty evidence needs explicit keep/drop review before deletion or reuse. |
| LangGraph production candidate | `/Users/dhyana/ds_langgraph_prod_candidate_20260702`, `codex/langgraph-prod-candidate-20260702` | #746 | Related runtime orchestration lane. Current PR state: draft, CLEAN, green. Sequence after transport truth. |
| Agentic design-pattern atlas | remote `claude/repo-implementation-planning-u3cayh` | #738 | Related design/planning lane. Ideas are represented in the master plan; do not mix its repo-wide planning artifacts into the transport branch without review. |
| Older A2A foundations | main history, including representative PRs #361, #362, #399, #402, #416, #477, #479-#482, #514, #557, #566, #568, #623, #639, #709, #727, #730 | merged/closed | Already inherited or historical. Treat as archaeology unless a targeted diff proves unique current value. |
| Remote historical A2A/NATS branches | examples: `codex/a2a-active-track-20260613`, `devin/1779946341-a2a-trace-persistence-e2e`, `devin/1780548631-spine-a2a-adoption`, `mmm-a2a-conditional-merge`, `perplexity-computer/a2a-activation-1780025504`, `preserve/runtime-truth-nats-rebuild-preflight-20260623` | mixed | Superseded or historical until proven otherwise by targeted diff. Do not block #744 on these without concrete unique code/evidence. |

## Current LangGraph Truth

- #732 is draft and currently DIRTY against main.
- #746 is draft, currently CLEAN, and green.
- Both are related orchestration lanes above transport truth.
- Neither substitutes for proving one canonical A2A/NATS production send path through `A2ANatsTransport.publish_task`.

## Keep / Drop Rules

Keep:

- Canonical A2A task envelope work.
- NATS JetStream delivery, ack, retry, redelivery, DLQ, and replayable evidence.
- Fresh evidence with source hashes tied to the current branch.
- Operator surfaces that can be routed through the canonical transport.
- Documentation that prevents duplicate coordination substrates.

Drop or quarantine:

- Unwired `coordination_substrate/**` code from the Claude branch.
- Generated evidence whose source hashes no longer match the branch.
- Any local `~/.dharma/a2a/nodes.json` content or other state containing API keys.
- Any claim that local `DHARMA_FLEET` and AGNI `DHARMA_A2A` are mirrored before a dual-broker survey proves it.
- Any "always-on speaking A2A" claim before voice uses receipted A2A tasks.

## Known Hard Gaps

These are the blockers between current central branch and the system you actually want:

1. Production callers are not yet proven to use `A2ANatsTransport.publish_task` as the single canonical send path.
2. Local `DHARMA_FLEET` and AGNI `DHARMA_A2A` are separate surfaces; no fleet-wide mirror is proven.
3. `NodeGateway.init_gateway()` is not proven live in the API lifespan.
4. Agent Card JWS signatures are declared but not enforced as a production trust gate.
5. Voice input/output is not yet a receipted A2A adapter.
6. LangGraph should not become the owner of task truth; it belongs above the transport as durable orchestration.
7. The dirty root worktree still has local A2A/NATS changes that need targeted harvesting or explicit abandonment.

## Next Build Order

1. Keep #744 as the central A2A/NATS branch and PR.
2. Land or continue reviewing #744 after the central index and latest main merge are green.
3. In the next implementation PR, wire one production caller through `A2ANatsTransport.publish_task`.
4. Add dual-broker survey output for local `DHARMA_FLEET` and AGNI `DHARMA_A2A`.
5. Decide whether to build a scoped mirror. If yes, use allowlisted subjects and loop-prevention headers.
6. Initialize `NodeGateway` where production can actually reach it.
7. Enforce Agent Card signatures or an equivalent trust gate.
8. Add the speaking adapter: speech-to-text -> operator intent -> A2A task -> reply/artifact -> text-to-speech.
9. Add LangGraph for long-running, interruptible workflows only after A2A task truth is stable.

## Operator Commands

Use these when you need the current central view:

```bash
cd /Users/dhyana/ds_a2a_always_on_spine_20260701
git status --short --branch
gh pr view 744 --repo AmitabhainArunachala/dharma_swarm --web
gh pr checks 744 --repo AmitabhainArunachala/dharma_swarm
sed -n '1,240p' docs/ops/A2A_NATS_CENTRAL_INDEX.md
```

Use these when validating the NATS slice:

```bash
/Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_a2a_cloud_contact.py tests/test_nats_transport.py tests/test_nats_substrate_contract.py tests/test_pramana_probe.py tests/test_track_portfolio.py -q
/Users/dhyana/dharma_swarm/.venv/bin/python scripts/governance/check_nats_live_production_evidence.py --max-age-hours 48
/Users/dhyana/dharma_swarm/.venv/bin/python scripts/governance/check_nats_substrate_contract.py
```

## Verification On This Index

Run on 2026-07-02 from the central worktree:

- `git diff --check`
- `/Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_a2a_cloud_contact.py tests/test_nats_transport.py tests/test_nats_substrate_contract.py tests/test_pramana_probe.py tests/test_track_portfolio.py -q` -> 64 passed
- `/Users/dhyana/dharma_swarm/.venv/bin/python scripts/governance/check_nats_substrate_contract.py` -> `NATS_CONTRACT_OK`
- `/Users/dhyana/dharma_swarm/.venv/bin/python scripts/governance/check_nats_live_production_evidence.py --max-age-hours 48` -> `NATS_LIVE_PRODUCTION_EVIDENCE_OK`

## Bottom Line

Yes: the one simple central place is PR #744, branch `codex/a2a-always-on-spine-20260701`, worktree `/Users/dhyana/ds_a2a_always_on_spine_20260701`.

But the honest status is not "done always-on A2A." It is "latest organized A2A/NATS spine, with the right evidence and a clean path to the always-on speaking system."
