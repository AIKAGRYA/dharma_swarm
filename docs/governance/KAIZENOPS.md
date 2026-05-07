# KaizenReview Bridge v0

KaizenReview Bridge v0 converts AgentOps run evidence into a concise review
artifact for operator decision support.

It is intentionally narrow:

- input: one or more AgentOps `report.json` files (or directories)
- output: `kaizen_review.json` and `kaizen_review.md`
- scope: local file processing only
- no dashboard/API/runtime/ontology wiring

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

## Human YDS Boundary

`human_yds_rating` is always `null` in this bridge output.
AI-generated content is advisory only and cannot assign final YDS.
