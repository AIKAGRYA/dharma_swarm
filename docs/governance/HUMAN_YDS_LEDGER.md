# Human YDS Ledger v0

The Human YDS Ledger is the first small authority surface for operator quality
ratings. It records what the human explicitly judged as good, bad, difficult,
or worth trusting.

It is not a self-grader, dashboard, API, ontology migration, memory writer, or
automated reward model.

## Purpose

Daily Operating Brief v0 already reads a `yds_ratings_path`. This ledger provides
the append-only JSONL writer for that path so human ratings can become regular
operating evidence instead of scattered chat comments.

## Record Shape

Each line is one JSON object:

```json
{
  "timestamp": "2026-05-06T01:02:00Z",
  "rating": "5.10a",
  "artifact": "daily-brief-v0",
  "source": "human_operator",
  "human_comment": "clear enough to operate from",
  "operator_id": "dhyana",
  "metadata": {
    "branch": "chore/daily-operating-brief-v0"
  }
}
```

Required fields:

- `timestamp`
- `rating`
- `artifact`
- `source`

Optional fields:

- `human_comment`
- `operator_id`
- `metadata`

## Authority Rule

Only sources that clearly identify a human/operator are authoritative. The v0
writer rejects sources like `ai_self_grader`. Advisory AI scores may exist in
other files, but they are not written through this ledger.

## Use From Python

```python
from pathlib import Path

from dharma_swarm.human_yds_ledger import append_human_yds_rating

append_human_yds_rating(
    Path("reports/yds/human_ratings.jsonl"),
    artifact="docops-integrity-v0",
    rating="5.10b",
    human_comment="useful enough to merge after review",
    source="operator_dhyana",
)
```

Then pass the same path to Daily Operating Brief:

```python
from dharma_swarm.daily_operating_brief import DailyOperatingBriefInputs

inputs = DailyOperatingBriefInputs(
    yds_ratings_path=Path("reports/yds/human_ratings.jsonl")
)
```

## Boundaries

- No default write to `~/.dharma`
- No live runtime/autonomy call
- No dashboard/API surface
- No YDS auto-assignment
- No memory consolidation
- No ontology schema change

## Still Missing

- Operator CLI command
- Canonical rating vocabulary beyond preserving the human's string
- Artifact identity registry
- Daily Brief output path convention
- Contribution to Memory tail
