# Daily Operating Brief v0

The Daily Operating Brief is a local markdown generator for the solo operator.
It answers the practical morning questions: what happened, what was real, what
is broken, what burned time or money, what produced value, whether the human
gave YDS quality ratings, what revenue or self-funding move is visible, what
should stop, and what the next highest-leverage move is.

It is not a dashboard, API route, runtime authority, autonomy loop, ontology
migration, memory consolidation path, or YDS self-grader.

## Inputs

`dharma_swarm.daily_operating_brief.DailyOperatingBriefInputs` accepts explicit
paths only:

- `agentops_reports_dir`: scans `**/report.json` for AgentOps run reports.
- `kaizen_reports_dir`: scans `**/kaizen_review.json` when KaizenReview reports
  exist.
- `yds_ratings_path`: reads JSON or JSONL human rating records.
- `cost_report_path`: reads JSON or JSONL burn/cost records.
- `llm_burn_state_dir`: optionally reads local LLM usage from
  `cost_log.jsonl`, `traces/cost_ledger.jsonl`, and dated trace JSONL files.
- `docops_check_report_path`: optionally reads the DocOps integrity check
  report, usually `reports/docops/check.json`.
- `docops_inventory_path`: optionally reads the DocOps corpus inventory,
  usually `reports/docops/corpus_inventory.json`.
- `operator_ground_truth_path`: optionally reads
  `reports/operator_ground_truth/latest.json` for repository state and
  repo cleanup pressure.
- `hot_items_path`: reads current stop/next-move signals.
- `revenue_notes_path`: reads plain text or markdown revenue notes.

The generator does not read `~/.dharma` unless the caller explicitly passes a
path there.

## LLM Burn Normalization

The brief can ingest the recent LLM burn upgrade through an explicit
`llm_burn_state_dir`. That logic is implemented in `dharma_swarm.llm_burn` and
normalizes local LLM usage records into OpenInference-style spans without adding
OpenInference, OpenTelemetry, Langfuse, or LiteLLM as runtime dependencies.

The normalizer reads:

- `cost_log.jsonl`
- `traces/cost_ledger.jsonl`
- `traces/traces_YYYY-MM-DD.jsonl`

It reports span count, token count, logged cost, estimated cost, zero-token
spans, unpriced spans, source breakdown, cost-source breakdown, and failure hot
spots. If unpriced spans are present, the conservative next move is to close the
pricing gap before scaling another long autonomous run.

## Output

`render_markdown()` emits these sections:

1. What happened
2. Gate health
3. Value produced
4. Burn / cost signals
5. Human YDS ratings
6. Revenue / self-funding moves
7. Stop doing
8. Next highest-leverage move
9. Doc drift / claim integrity
10. Missing sources

`write_daily_operating_brief()` writes markdown only to the explicit output path
provided by the caller.

`scripts/governance/morning_cockpit.py` is the thin evidence runner for the
morning loop. It runs Operator Ground Truth, runs DocOps report generation,
builds the brief, and writes a manifest at
`reports/morning_cockpit/latest.json`. It does not schedule agents, allocate
worktrees, or merge branches. `make morning-cockpit` runs the non-strict
version, and `make morning-cockpit-strict` exits non-zero when major evidence
sources such as AgentOps or KaizenReview reports are missing.

## Missing Sources

The v0 brief fails visible, not silent:

- No AgentOps reports: `No AgentOps reports found.`
- No KaizenReview reports: `No KaizenReview reports found.`
- No YDS ledger: `No human YDS ratings found.`
- No cost source: `No burn source found.`
- No revenue notes: `No revenue source found.`
- No DocOps integrity report: `No DocOps integrity report found.`
- No DocOps corpus inventory: `No DocOps corpus inventory found.`
- No Operator Ground Truth repo cleanup pressure:
  `No operator ground truth repo cleanup pressure found.`

Missing sources also appear in the final `Missing sources` section.

## YDS Authority

YDS ratings are human-authoritative only. Records are treated as authoritative
only when their `source` clearly identifies the human/operator. AI or self
ratings may be surfaced as advisory notes if they are explicitly present in the
source file, but the brief never assigns authoritative YDS itself.

Supported rating fields include:

- `timestamp`
- `rating`
- `artifact`
- `human_comment`
- `source`

Legacy live rows may use `grade` or `normalized_grade` for the rating, `target`
for the artifact, and `note` for the human comment. The human/operator source
check still applies.

## AgentOps Bridge

AgentOps v0 reports already contain enough structure for the brief:

- job id
- branch and worktree
- gate exit codes
- scope status and changed files
- commit hash when present
- final status

The brief summarizes these reports as operating evidence. Failed gates or failed
scope checks become stop-doing signals until resolved.

## Operator Ground Truth Bridge

The brief may read the generated Operator Ground Truth JSON report for
repository state and repo cleanup pressure. Operator Ground Truth is the
sensor: it measures worktrees, branches, dirty paths, runtime databases, and
processes. The repository fact adapter interprets that raw state into
cleanup-pressure categories. The brief renders the pressure; it does not retire
branches, delete worktrees, or become a canonical architecture source. Dirty hot
lanes become stop-doing signals; cleanup candidates stay advisory until a human
retires, salvages, or quarantines the branch/worktree.

## DocOps Bridge

The brief can read the DocOps integrity artifacts produced by
`make docops-report`:

- `reports/docops/check.json`
- `reports/docops/corpus_inventory.json`

This keeps documentation drift visible in the same morning cockpit as runtime
gates, burn, and revenue signals. A failing DocOps report does not mutate docs
or become a new authority, but it does become a conservative next-move signal:
fix claim/path/canonical-doc failures before adding or promoting more
documentation.

## Deliberately Not Included Yet

- Dashboard or API surface
- BurnReport canonical schema
- RevenueWedge canonical schema
- Contribution to Memory implementation
- Integration queue
- Full-suite certification
