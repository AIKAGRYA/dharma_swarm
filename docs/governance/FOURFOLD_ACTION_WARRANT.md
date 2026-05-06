# Fourfold Action Warrant

Status: read-only governance artifact.

The Fourfold Action Warrant turns the Shakti questions into an executable review
artifact for significant actions. It does not replace telos gates, pre-commit
guards, or ontology records. It provides a deterministic "should this action
proceed?" packet that can be attached to reviews, PRs, and operator decisions.

## Four Questions

| Shakti | Question | Engineering Check |
| --- | --- | --- |
| Maheshwari | Does this serve the larger pattern, telos, and emergence? | Names the system-level purpose and avoids local-only optimization. |
| Mahakali | Is this the right moment and force level? | Acts decisively on real blockers without unnecessary blast radius. |
| Mahalakshmi | Does this create harmony rather than noise? | Reuses existing seams and reduces fragmentation. |
| Mahasaraswati | Is every detail precise, evidenced, and verified? | Includes exact paths, deterministic checks, and tests. |

The default warrant requires at least two of four dimensions to pass. Explicitly
destructive actions without consent block regardless of score. Semantic
governance block claims also override the fourfold score.

## CLI

```bash
python3 scripts/governance/check_shakti_warrant.py \
  --intent "restore canonical governance architecture" \
  --content "fix blocker, reduce fragmentation, add deterministic pytest evidence" \
  --target scripts/governance/check_shakti_warrant.py \
  --target tests/test_shakti_warrant.py \
  --tool pytest \
  --metadata allowed_tools=pytest \
  --metadata telos_aligned=true \
  --metadata fixes_blocker=true \
  --metadata no_new_substrate=true \
  --metadata tests_planned=true
```

The command exits zero by default because the warrant is currently advisory.
Use `--fail-on block --fail-on hold` when a caller wants to make the report a
gate.

Tool authorization is advisory unless `--metadata enforce_tool_allowlist=true`
is supplied. With enforcement enabled, every `--tool` command must match a tool
name in `--metadata allowed_tools=tool1,tool2`; unauthorized tools block the
warrant.

## Diff-Bound Warrants

The warrant becomes much stronger when it is bound to actual git evidence:

```bash
python3 scripts/governance/check_shakti_warrant.py \
  --intent "stabilize the governance warrant seam" \
  --diff-scope unstaged \
  --tool "pytest -q tests/test_shakti_warrant.py" \
  --metadata allowed_tools=pytest \
  --metadata tests_planned=true \
  --metadata requires_diff_evidence=true
```

Supported scopes are `unstaged`, `staged`, `head`, and `base`. The `base` scope
diffs `origin/main...HEAD` unless `--base-ref` is supplied. Untracked files are
included by default; use `--no-include-untracked` when reviewing only tracked
changes.

Diff evidence is rendered in the report and copied into the JSON payload. It
also changes scoring: bounded diffs improve Mahalakshmi, git evidence and test
paths improve Mahasaraswati, and hot paths can be forced to block unless
`--metadata impact_checked=true` accompanies `--metadata enforce_hotpath_ack=true`.
The CLI also treats `DHARMA_UPLIFT_ACK=impact-checked` as `impact_checked=true`
so it composes with the existing hot-path acknowledgement guard.

The pre-commit uplift guard runs the staged warrant as part of
`scripts/uplift_guards/run_pre_commit.py`:

```bash
python3 scripts/governance/check_shakti_warrant.py \
  --intent "pre-commit staged diff fourfold governance warrant" \
  --diff-scope staged \
  --no-include-untracked \
  --pass-on-empty-diff \
  --metadata requires_diff_evidence=true \
  --metadata enforce_hotpath_ack=true \
  --fail-on block \
  --fail-on hold
```

## Scope Boundary

This is intentionally not another state system. The warrant is computed from an
action request and optional semantic claims, then rendered. Future integrations
may attach the warrant to `ActionProposal` or `GateDecisionRecord`, but the
current implementation remains read-only so it can review Devin/Codex/human
changes without mutating runtime state.
