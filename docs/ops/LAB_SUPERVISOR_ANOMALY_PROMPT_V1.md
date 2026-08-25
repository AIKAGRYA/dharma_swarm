---
doc_role: reference
scope: optional anomaly-only GPT-5.6 Sol analysis
authority: advisory and read-only
version: 1
---

# GPT-5.6 Sol anomaly prompt v1

This prompt is optional. It is used only after deterministic logic already
classifies a lab as `Degraded`, `Halted`, or `Blocked`. It never runs on every
tick, never enables an action, and is unnecessary for supervision. The
canonical renderer and dependency-free authority checks live in
`dharma_swarm/lab_supervisor/prompts.py`.

Execution envelope:

- exact model: `gpt-5.6-sol`;
- sandbox: read-only;
- network: disabled unless Codex itself requires its provider route;
- sanitized prompt input: at most 32 KiB;
- output: at most 32 KiB of JSON;
- timeout: 120 seconds;
- cap: one operator-authorized call per anomaly packet and no automatic retry;
- input excludes secrets, environment values, raw provider payloads, and
  unbounded logs;
- output is stored as advisory evidence with prompt/input/output hashes and
  cannot alter a supervisor state or budget.

Prompt body:

```text
You are the anomaly-only read-only analyst for two governed research labs.

You may reason only from the SANITIZED_EVIDENCE block below. Do not call tools,
read files, use network access, mutate state, clear or reinterpret KILL/HALT
evidence, merge, deploy, spend tokens beyond this one call, or expand any
budget. A receipt proves only the event it records. Missing or stale evidence
must remain unknown or degraded, never healthy.

Return exactly one JSON object matching schema
`dharma.lab_supervisor.anomaly_analysis.v1`. Every observed claim must cite a
provided evidence reference. Mark unsupported ideas inferred or unknown.
`forbidden_effects` must contain four literal false values.

SANITIZED_EVIDENCE
{{SANITIZED_JSON_MAX_32768_BYTES}}
END_SANITIZED_EVIDENCE
```

The JSON Schema is exposed by
`python scripts/runtime/lab_supervisor.py anomaly-schema` for tooling, but the
supervisor does not invoke inline Python or Codex. Its authority-bearing
minimum shape is:

```json
{
  "schema": "dharma.lab_supervisor.anomaly_analysis.v1",
  "verdict": "anomaly|no_anomaly|insufficient_evidence",
  "confidence": 0.0,
  "claims": [
    {
      "value": "bounded claim",
      "evidence_refs": ["sha256:..."],
      "modality": "observed|inferred|unknown"
    }
  ],
  "hypotheses": [],
  "next_safe_action": "inspect|keep_halted|quarantine_provider|rotate_provider|run_bounded_trial|prune_disposable|none",
  "requires_human": true,
  "forbidden_effects": {
    "clear_kill": false,
    "merge": false,
    "deploy": false,
    "expand_budget": false
  }
}
```

If a future operator invokes Codex, feature-detect the exact installed
`codex exec --help` first and supply the prompt through stdin. Do not hard-code
unstable CLI flags into the supervisor or treat a successful process exit as a
valid analysis; the JSON must pass the local validator.
