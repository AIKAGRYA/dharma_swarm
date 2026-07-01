# Expert Audit Output Template

Use this template for every prompt output.

```yaml
prompt_id:
council_id:
run_id:
operator:
model:
repo_path:
git_ref:
timestamp_utc:
mode: issue | pr | weekly | release
scope:
  files_examined: []
  commands_run:
    - command:
      cwd:
      exit_code:
      key_output:
  commands_not_run:
    - command:
      reason:
summary:
  verdict: pass | warn | fail | inconclusive
  confidence: low | medium | high
  evidence_floor: E0_none | E1_static | E2_tested | E3_cross_checked | E4_regression_proven
findings:
  - id:
    title:
    severity: low | medium | high | critical
    evidence_level: E0_none | E1_static | E2_tested | E3_cross_checked | E4_regression_proven
    confidence: low | medium | high
    files: []
    line_refs: []
    observed:
    inferred:
    risk:
    failure_class:
    recommendation:
    verification:
not_proven: []
open_questions: []
follow_up_issues: []
```

Rules:

- Do not omit `commands_not_run`.
- Do not claim a pass when required commands were not run.
- Use `not_proven` for any attractive claim that lacks evidence.
- Keep raw command output excerpts short; cite artifact paths for long logs.
