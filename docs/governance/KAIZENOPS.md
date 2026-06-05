# KaizenReview Bridge v0

KaizenReview Bridge v0 converts AgentOps run evidence into a concise review
artifact for operator decision support.

It is intentionally narrow:

- input: one or more AgentOps `report.json` files (or directories)
- output: `kaizen_review.json` and `kaizen_review.md`
- scope: local file processing only
- runtime truth: read-only trace, receipt, and identity references copied from
  source AgentOps reports
- no dashboard/API/runtime/ontology ownership

## Command

```bash
python scripts/governance/kaizen_review_from_agentops.py \
  reports/agentops \
  --id kaizen-20260506 \
  --output-root reports/kaizen
```

## Output

```text
reports/kaizen/<id>/kaizen_review.json
reports/kaizen/<id>/kaizen_review.md
```

The review includes:

- gate classification (`green`/`red`/`unknown`)
- scope classification (`clean`/`violation`/`unknown`)
- commit classification (`created`/`no_commit`/`approval_blocked`)
- waste patterns
- stop-doing items
- playbook candidates
- exactly one next-work-packet recommendation
- runtime truth reference summary when the source reports include trace,
  receipt, or identity refs

## Runtime Truth Boundary

KaizenReview may copy runtime truth references from AgentOps reports so the
review can be traced back to execution evidence. It does not create receipt
authority, claim NATS live contact, dispatch work, mutate ontology, or decide
Forge fitness. Missing runtime refs make the review less bound to the runtime
truth spine; invented refs are invalid.

## Human YDS Boundary

`human_yds_rating` is always `null` in this bridge output.
AI-generated content is advisory only and cannot assign final YDS.
