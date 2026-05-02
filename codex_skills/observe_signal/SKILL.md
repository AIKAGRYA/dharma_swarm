---
name: observe-signal
description: Capture a manual Signal into the ontology-native inquiry chain through TelicSeam.
metadata:
  short-description: Record an inquiry Signal
---

# Observe Signal

Use this skill when a human or agent needs to capture an observation before it
has been promoted into a Question, Claim, Evidence, or Doctrine.

The skill is a thin adapter over `TelicSeam.record_signal`. It must not create
sidecar files or durable state outside the ontology database.

## Command

```bash
python codex_skills/observe_signal/entry.py \
  --source user_note \
  --payload "Observed fact or signal text" \
  --observer-ref dhyana
```

Optional:

- `--source-kind`: defaults to `manual`
- `--sensitivity`: defaults to `internal`
- `--ontology-path`: override the ontology DB path for tests or sandboxes
