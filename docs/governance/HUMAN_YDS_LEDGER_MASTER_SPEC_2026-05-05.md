# Human YDS Ledger Master Spec

Date: 2026-05-05
Status: implementation-ready governance spec
Scope: first-class human quality memory for AgentOps, KaizenOps, and future Daily Operating Brief work

## 1. Executive Decision

Build `Human YDS Ledger v0` next.

The purpose is to make the human operator's quality judgment durable,
queryable, and explicitly separate from AI self-grading.

The system may ask for a YDS rating. It may summarize evidence. It may compare
artifacts. It must not assign an authoritative YDS rating by itself.

Authoritative YDS means:

- a human explicitly rated a specific artifact
- the rating was written to an append-only ledger
- the rating includes enough context to understand what was judged
- later agents can read it without rewriting it

This turns operator taste into system memory without letting the system launder
its own preferences into fake authority.

## 2. Why This Exists

AgentOps now creates bounded work packets and structured reports.
KaizenReview now reads those reports and explains what worked, what failed, and
what should happen next.

The missing closure is human quality memory.

Today, the operator can say "this was 5.12" or "this was not good enough", but
that signal does not become durable operating evidence. Future agents still
need the human to re-explain taste, quality bars, and what work actually
earned trust.

Human YDS Ledger v0 closes that gap.

It is the first slice of the broader operating ledger:

```text
AgentOps report
  -> KaizenReview
  -> human YDS rating
  -> Daily Operating Brief
  -> next AgentOps packet
```

## 3. Non-Goals

This phase must not implement:

- dashboard or API surfaces
- ontology writes
- memory consolidation
- Daily Operating Brief generation
- BurnReport
- RevenueWedge
- automatic playbook updates
- automatic integration queue promotion
- model-generated authoritative ratings
- broad quality-scoring replacement
- Rust or Go substrate

This is a local ledger and CLI/report contract only.

## 4. Design Principles

### 4.1 Human Authority

Only the operator can assign an authoritative YDS rating.

AI-generated quality signals are advisory and must use names such as:

- `forge_score`
- `advisory_quality_score`
- `candidate_rating_prompt`
- `quality_notes`

They must not be stored as `human_yds_rating`.

### 4.2 Append Only

Ratings are never edited in place.

Corrections create a new record with `supersedes_rating_id`.

Consumers compute the latest active rating by following supersession links.

### 4.3 Artifact Specific

Every rating must name the judged artifact.

Valid artifact kinds:

- `agentops_report`
- `kaizen_review`
- `commit`
- `pull_request`
- `file`
- `daily_brief`
- `operator_artifact`
- `external_artifact`

The rating must not float as a generic mood note.

### 4.4 Local First

The primary ledger is local operator state:

```text
~/.dharma/yds/human_quality_ratings.jsonl
```

Reason:

- YDS is human taste and may include private notes.
- It should survive repo checkouts and worktrees.
- It should not be accidentally committed.

Repo code defines the schema, tests, and tooling. The personal ledger remains
operator-local unless explicitly exported.

### 4.5 Report Readability

Generated reviews may display human YDS ratings only when they come from the
ledger. If no ledger rating exists, the field stays null and the report emits a
prompt for the operator.

## 5. Core Data Objects

### 5.1 HumanQualityRating

One append-only human rating record.

Required fields:

```json
{
  "schema_version": "human_yds_rating.v1",
  "rating_id": "yds_20260505T000000Z_ab12cd34",
  "created_at": "2026-05-05T00:00:00Z",
  "operator_id": "dhyana",
  "rating_scale": "YDS",
  "rating_value": "5.12",
  "artifact": {
    "kind": "agentops_report",
    "uri": "repo://reports/agentops/job/20260505T000000Z/report.json",
    "title": "AgentOps report for governed KaizenReview packet"
  },
  "human_note": "This captured the shape cleanly and kept boundaries intact.",
  "evidence_refs": [
    "repo://reports/agentops/job/20260505T000000Z/report.json",
    "repo://reports/kaizen/latest/kaizen_review.md"
  ],
  "context": {
    "branch": "chore/kaizen-review-v0",
    "commit": "f01b798",
    "source": "operator_cli"
  },
  "supersedes_rating_id": null
}
```

Optional fields:

```json
{
  "tags": ["agentops", "kaizen", "governance"],
  "difficulty_note": "Hard because it required scope discipline.",
  "reuse_signal": "Promote pattern into future AgentOps packets.",
  "stop_doing_signal": "Do not build dashboard before ledger closure.",
  "private_note": ""
}
```

`private_note` is allowed in the local ledger but must be omitted from any
tracked export unless the operator explicitly requests it.

### 5.2 ArtifactRef

Artifact references use stable URI-like strings.

Preferred forms:

```text
repo://path/to/file
git://commit/<sha>
pr://<number>
agentops://<job_id>/<timestamp>
kaizen://<review_id>
external://<url-or-label>
```

The first v0 CLI may accept plain paths and normalize them to `repo://`.

### 5.3 RatingPromptCandidate

Generated prompt asking the operator to rate something. This is not authority.

Fields:

```json
{
  "artifact": {},
  "prompt": "YDS rate this artifact when ready.",
  "why_rate": "Successful gated AgentOps packet with reusable pattern.",
  "suggested_evidence_refs": [],
  "advisory_quality_notes": []
}
```

### 5.4 HumanQualitySummary

Derived read model for reports.

Fields:

```json
{
  "artifact_uri": "repo://...",
  "latest_rating_value": "5.12",
  "latest_rating_id": "yds_...",
  "rating_count": 1,
  "last_rated_at": "2026-05-05T00:00:00Z",
  "human_note_excerpt": "This captured the shape cleanly..."
}
```

This is derived from the append-only ledger. It is not the source of truth.

## 6. YDS Working Scale

The ledger stores exact operator-entered labels. It does not enforce one final
philosophical rubric.

For v0, the CLI should accept:

- `5.6` through `5.15`
- optional suffixes such as `5.10a`, `5.11d`
- optional human aliases if explicitly mapped later

Working interpretation for reports:

| Band | Meaning |
|---|---|
| `5.6-5.8` | Useful but ordinary |
| `5.9-5.10` | Solid, worth retaining |
| `5.11` | Strong, reusable pattern |
| `5.12` | Excellent, should influence future playbooks |
| `5.13` | Rare, high-taste artifact |
| `5.14` | System-defining quality |
| `5.15` | Exceptional, only-you-can-do level |

AI must never infer a band as authoritative. It may only display this table and
ask the operator to choose.

## 7. CLI v0

Primary script:

```text
scripts/governance/record_human_yds_rating.py
```

Required command:

```bash
python scripts/governance/record_human_yds_rating.py rate \
  --artifact reports/agentops/job/20260505T000000Z/report.json \
  --kind agentops_report \
  --rating 5.12 \
  --note "Clean scoped packet; promote this pattern."
```

Required options:

- `rate`
- `--artifact`
- `--kind`
- `--rating`
- `--note`

Optional options:

- `--operator dhyana`
- `--ledger ~/.dharma/yds/human_quality_ratings.jsonl`
- `--title "..."`
- `--evidence repo://...`
- `--tag agentops`
- `--supersedes yds_...`
- `--private-note "..."`

Read commands:

```bash
python scripts/governance/record_human_yds_rating.py list
python scripts/governance/record_human_yds_rating.py show --artifact reports/agentops/...
python scripts/governance/record_human_yds_rating.py latest --artifact reports/agentops/...
```

The script must not:

- mutate git state
- run tests
- run live swarm/autonomy
- write source files
- call network APIs
- assign a rating without `--rating`
- accept `--source ai` as authoritative

## 8. KaizenReview Integration

`kaizen_review_from_agentops.py` should gain an optional read-only input:

```bash
python scripts/governance/kaizen_review_from_agentops.py \
  --input reports/agentops \
  --yds-ledger ~/.dharma/yds/human_quality_ratings.jsonl \
  --output reports/kaizen/latest
```

Behavior:

- If a source report has a matching human rating, include it in
  `human_yds_rating`.
- If no matching rating exists, keep `human_yds_rating` as null.
- Always include `yds_prompt_for_human`.
- Never generate a rating value.

Matching order:

1. exact artifact URI match
2. normalized repo path match
3. AgentOps `job_id` plus timestamp if present
4. commit hash match if the report produced a commit

If multiple active ratings match, use the newest non-superseded record and
include `rating_count`.

## 9. Daily Operating Brief Integration

Not in v0 implementation.

Future Daily Operating Brief should read:

- latest AgentOps reports
- latest KaizenReviews
- Human YDS Ledger
- cost/burn reports
- integration candidates

The YDS section should answer:

- What earned human trust?
- What failed the human quality bar?
- Which patterns should be repeated?
- Which work should stop?
- Which artifacts are candidates for public proof?

## 10. Tests Required For v0

Create:

```text
tests/test_human_yds_ledger.py
```

Minimum tests:

1. Records one valid rating to a temp JSONL ledger.
2. Preserves append-only behavior across multiple ratings.
3. Rejects invalid rating values.
4. Rejects missing artifact.
5. Rejects missing human note.
6. Normalizes repo-relative paths to `repo://`.
7. Supports `supersedes_rating_id` without modifying old records.
8. Resolves latest non-superseded rating for an artifact.
9. Omits `private_note` from export output.
10. Does not import or call subprocess.
11. KaizenReview remains null when no human rating exists.
12. KaizenReview reads a matching human rating only from the ledger.

## 11. Implementation Files

Allowed first implementation files:

```text
scripts/governance/record_human_yds_rating.py
tests/test_human_yds_ledger.py
scripts/governance/kaizen_review_from_agentops.py
tests/test_kaizen_review_from_agentops.py
docs/governance/HUMAN_YDS_LEDGER_MASTER_SPEC_2026-05-05.md
docs/governance/KAIZENOPS.md
docs/governance/AGENTOPS_DAILY_OPERATING_BRIEF_BRIDGE.md
```

Do not touch:

- dashboard
- api
- AgentRunner
- ExecutionPipeline
- TelicSeam
- ontology
- memory authority files
- provider/routing authority files
- Rust or Go code

## 12. Verification Gates

Use the repo venv:

```bash
PY="/Users/dhyana/dharma_swarm/.venv/bin/python"
```

Required focused gates:

```bash
$PY -m pytest -q \
  tests/test_human_yds_ledger.py \
  tests/test_kaizen_review_from_agentops.py

python3 -m compileall \
  scripts/governance/record_human_yds_rating.py \
  scripts/governance/kaizen_review_from_agentops.py

git diff --check

pre-commit run semgrep-local --all-files

$PY scripts/governance/check_module_budget.py \
  --base-ref origin/main --head-ref HEAD

DHARMA_PYTHON=/Users/dhyana/dharma_swarm/.venv/bin/python \
  pre-commit run dharma-contract-tests --all-files

DHARMA_PYTHON=/Users/dhyana/dharma_swarm/.venv/bin/python \
  pre-commit run dharma-uplift-guards --all-files
```

Collection is useful but not sufficient:

```bash
$PY -m pytest tests/ --collect-only -q
```

## 13. Acceptance Criteria

The phase is done when:

- a human can record a rating with one CLI command
- the record is append-only JSONL under `~/.dharma/yds`
- invalid ratings fail closed
- private notes are local-only
- KaizenReview can read real human ratings when supplied a ledger
- KaizenReview still does not self-assign YDS
- focused tests pass
- governance hooks pass
- only allowed files changed

## 14. Human Command Contract

The human should be able to say:

```text
YDS rate this 5.12: clean scoped packet, reusable pattern, no extra surface.
```

An agent should translate that into:

```bash
python scripts/governance/record_human_yds_rating.py rate \
  --artifact <current-artifact> \
  --kind <artifact-kind> \
  --rating 5.12 \
  --note "clean scoped packet, reusable pattern, no extra surface"
```

If the artifact is ambiguous, the agent must ask which artifact is being rated.

## 15. Relationship To ForgeScore

ForgeScore remains advisory.

Allowed:

- include ForgeScore in `advisory_quality_notes`
- compare ForgeScore with later human ratings for calibration
- use divergence to improve prompts and gates

Forbidden:

- store ForgeScore as `human_yds_rating`
- average ForgeScore into YDS
- auto-promote artifacts based only on ForgeScore
- tell the human an artifact is "5.12" without a human record

## 16. Relationship To Burn And Revenue

YDS is quality signal, not ROI by itself.

The future self-funding loop needs both:

```text
quality signal: HumanQualityRating
economic signal: BurnReport / RevenueWedge / ValueEvent
```

High YDS plus high burn may mean "excellent but expensive".

High YDS plus low burn may mean "repeat this pattern".

Low YDS plus high burn means "stop or redesign".

The ledger should make those later joins possible by keeping artifact, commit,
job, and report references stable.

## 17. Risks

| Risk | Mitigation |
|---|---|
| AI inflates ratings | AI cannot write authoritative ratings without explicit human value. |
| Ratings become vague vibes | Every rating must attach to an artifact. |
| Private notes leak | Local ledger by default; private notes omitted from exports. |
| Append-only ledger grows noisy | Derived summaries and supersession links, not mutation. |
| Report matching is brittle | Use normalized artifact URIs and exact paths first. |
| YDS blocks shipping | Rating is advisory for learning unless human marks it as a binding gate. |

## 18. One-Day Build Scope

Build only:

1. `record_human_yds_rating.py`
2. JSONL append/read/latest logic
3. tests for ledger behavior
4. optional KaizenReview read-only lookup
5. docs updated to point to this spec

Do not build dashboard, API, ontology projection, or Daily Operating Brief.

## 19. Later Phases

### Phase 2: Operating Ledger

Add first-class append-only ledgers for:

- `IntegrationCandidate`
- `StopDoingItem`
- `BurnReport`
- `NextPacketRecommendation`

### Phase 3: Daily Operating Brief

Daily brief reads AgentOps, KaizenReview, YDS, burn, and integration candidates.

### Phase 4: Ontology Projection

Project selected human ratings into ontology only after the ledger is stable and
the projection is read-only or explicitly approved.

### Phase 5: Playbook Calibration

Use repeated high-YDS patterns to propose playbook changes. Human approval
remains required before a playbook becomes binding.

## 20. Final Doctrine

The swarm can propose.

The gates can block.

The tests can verify.

The reports can explain.

The human assigns YDS.

That boundary is what keeps the system from confusing self-description with
real quality.
