# Complexity Code Testing Prompt Suite

Status: active prompt-test pack.

This directory contains a 50-prompt expert audit suite for Dharma Swarm testing,
complexity, runtime reliability, AI-slop prevention, and governance evidence.
It is designed for two use modes:

1. Issue or PR mode: run only the relevant prompts against a change.
2. Weekly mode: run all 50 prompts, synthesize by council, then triage findings.

Prompt output is advisory until it is backed by repo evidence and converted into
an executable test, gate, issue, or tracked remediation. These prompts are not
product truth, runtime truth, or architecture canon by themselves.

## Councils

| Council | File | Purpose |
|---|---|---|
| 01 Testing and Verification | `councils/01_testing_verification/PROMPTS.md` | Test collection, properties, replay, assertion strength, hygiene, and complexity gates. |
| 02 Architecture and Complexity | `councils/02_architecture_complexity/PROMPTS.md` | Module depth, fan-in, seams, source-of-truth duplication, blast radius, and reduction plans. |
| 03 Runtime and Distributed Reliability | `councils/03_runtime_distributed_reliability/PROMPTS.md` | Receipts, idempotency, A2A/NATS, state persistence, replay, fallback, and runtime-truth falsification. |
| 04 AI Slop and Prompt Security | `councils/04_ai_slop_prompt_security/PROMPTS.md` | Claim falsification, prompt injection, memory poisoning, dependency provenance, secrets, and gate gaming. |
| 05 Governance, Evidence, and Fitness | `councils/05_governance_evidence_fitness/PROMPTS.md` | Fitness functions, ratchets, baselines, evidence grading, active-track truth, and weekly governance. |

Each council has 10 expert prompts and a `SYNTHESIS_PROMPT.md` that combines the
10 outputs into a single council verdict.

## Required Evidence Discipline

Every audit output must separate:

- `observed`: direct evidence from files, commands, CI, receipts, or logs.
- `inferred`: reasoning from observed evidence.
- `not_proven`: claims the model could not verify.
- `recommendation`: concrete next action.
- `verification`: the smallest test, command, or gate that would prove the fix.

Evidence levels:

- `E0_none`: hypothesis only. Maximum severity: low.
- `E1_static`: source, doc, config, or test evidence. Maximum severity: medium.
- `E2_tested`: verified by local command or targeted test.
- `E3_cross_checked`: confirmed by two or more independent evidence sources.
- `E4_regression_proven`: failing-before and passing-after behavior shown.

## Hallucination Guard

An auditor must not claim:

- a test passed unless the command, cwd, and exit code are recorded;
- a runtime or CI state unless directly checked;
- a module ownership fact unless backed by file paths or repo docs;
- a dependency API fact unless checked against installed package metadata or current docs;
- a production-readiness claim from prose, comments, generated reports, or model agreement.

If evidence is missing, the correct output is `inconclusive`, not `pass`.

## Files

- `RUNBOOK.md`: operating procedure for issue, PR, and weekly runs.
- `WEEKLY_ROTATION.md`: suggested cadence for running the 50 prompts without overload.
- `OUTPUT_TEMPLATE.md`: required output skeleton for individual prompt runs.
- `schemas/expert_audit_output.schema.json`: machine-readable schema for prompt output.
- `schemas/council_synthesis_output.schema.json`: machine-readable schema for council synthesis.

## Minimal Weekly Command Set

Start every weekly run with:

```bash
make onboard
git status --short
python3 -m pytest tests --collect-only -q
python3 scripts/governance/hygiene/check_hygiene_integrity.py
python3 scripts/governance/check_test_hygiene.py
python3 scripts/repo_xray.py --repo-root .
```

Then run the prompt families. Store raw outputs under `runs/YYYY-WW/` if the run
is meant to become durable evidence.
