---
name: assert-claim
description: Capture a proposed Claim into the ontology-native inquiry chain through TelicSeam.
metadata:
  short-description: Record an inquiry Claim
---

# Assert Claim

Use this skill when a human or agent needs to turn a signal or question into a
tracked proposition that can later receive Evidence.

The skill is a thin adapter over `TelicSeam.record_claim`. It must not create
sidecar files or durable state outside the ontology database.

## Command

```bash
python codex_skills/assert_claim/entry.py \
  --statement "The claim text" \
  --proposer-ref dhyana \
  --confidence 0.5
```

Optional:

- `--parent-question-id`: link the Claim as an answer to an open Question
- `--ontology-path`: override the ontology DB path for tests or sandboxes
