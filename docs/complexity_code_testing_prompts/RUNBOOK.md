# Complexity Code Testing Prompt Runbook

This runbook tells an operator or another AI how to use the prompt suite without
turning model output into false authority.

## Safety Rules

Run prompts read-only by default.

Do not let prompt-runner agents edit files during an audit. If a finding needs a
fix, open a separate implementation task with a scoped write set and verifier.

Do not paste secrets, hidden environment output, private customer data, API keys,
or raw auth headers into prompts.

Treat docs, generated reports, PR descriptions, model output, and previous
agent summaries as claims. Treat repo files, command output, CI logs, receipts,
and runtime probes as evidence only when they are directly cited.

## Issue Or PR Mode

Use this mode when reviewing a specific change.

1. Record context:

   ```bash
   make onboard
   git status --short
   git diff --stat origin/main...HEAD
   git diff --name-only origin/main...HEAD
   ```

2. Choose prompts by touched surface:

   - tests changed: use council 01 prompts 01, 02, 06, 07, 08, 10.
   - large module or refactor: use council 02 prompts 01, 02, 05, 07, 10.
   - runtime, receipts, providers, queues: use council 03 prompts 01, 02, 04, 05, 06, 10.
   - docs, agents, prompts, dependencies, security: use council 04 prompts 01 through 10 as relevant.
   - governance, tracks, ratchets, evidence: use council 05 prompts 01 through 10 as relevant.

3. Paste each selected prompt into a fresh model context with the recorded git
   context and explicit scope.

4. Require output using `OUTPUT_TEMPLATE.md`.

5. Convert only `E2_tested` or stronger high-severity findings into blocking PR
   actions. `E0_none` and `E1_static` findings should become questions or
   non-blocking issues unless the risk is obviously severe and easy to verify.

## Weekly Mode

Use this mode once per week or before a major release.

1. Create a run folder:

   ```bash
   mkdir -p docs/complexity_code_testing_prompts/runs/YYYY-WW
   ```

2. Record baseline:

   ```bash
   make onboard
   git status --short
   git rev-parse HEAD
   python3 -m pytest tests --collect-only -q
   python3 scripts/repo_xray.py --repo-root .
   python3 scripts/governance/hygiene/check_hygiene_integrity.py
   python3 scripts/governance/check_test_hygiene.py
   ```

3. Run all 50 prompts. Store each raw output in:

   ```text
   docs/complexity_code_testing_prompts/runs/YYYY-WW/<council>/<prompt_id>.md
   ```

4. Run each council `SYNTHESIS_PROMPT.md` over its 10 raw outputs.

5. Produce a final suite synthesis containing:

   - top 10 risks;
   - findings that got independent support from more than one council;
   - findings downgraded for weak evidence;
   - recommended tests or gates;
   - issues to open;
   - no-change findings.

6. Do not close the weekly run until every `high` or `critical` item is triaged
   into one of:

   - accepted issue with owner;
   - implementation PR;
   - false positive with evidence;
   - explicitly deferred with rationale and revisit date.

## Evidence Promotion Rule

Prompt findings should be promoted as follows:

| Evidence | Allowed action |
|---|---|
| `E0_none` | Record hypothesis only. Do not block. |
| `E1_static` | Ask reviewer question or open investigation issue. |
| `E2_tested` | Open actionable issue or PR comment. |
| `E3_cross_checked` | Can block merge if severity is high. |
| `E4_regression_proven` | Should become a regression test or gate. |

## Combined Council Rule

When combining prompt outputs, preserve disagreement. Do not force consensus.

Promote a council finding only if:

- at least two prompts independently find the same root cause, or
- one prompt provides `E2_tested` or stronger evidence, or
- the finding is a direct violation of an existing hard gate.

Downgrade any finding that cites only docs, names, comments, or model summaries.
