# DocOps Feed for Daily Operating Brief

**Status:** proposed input contract
**Runtime effect:** none

## Purpose

The Daily Operating Brief should eventually show doc drift as an operator
signal: what changed, what is stale, what is broken, and what cleanup would
reduce agent confusion fastest. This document defines the narrow DocOps feed
without changing the brief generator.

## Inputs

The feed is derived from the DocOps checker and corpus inventory:

| Field | Meaning |
|---|---|
| `docops_gate_passed` | Whether the blocking managed-doc check passed. |
| `docops_failure_count` | Number of blocking findings. |
| `docops_warning_count` | Number of advisory findings. |
| `managed_metrics` | Count-sensitive metrics from the checker. |
| `corpus_markdown_files` | Markdown files scanned in inventory mode. |
| `reserved_language_docs` | Docs containing high-trust wording. |
| `unregistered_reserved_language_docs` | High-trust wording outside allowed registry. |
| `absolute_local_path_refs` | Absolute machine-local repo path references. |
| `missing_reference_sample_count` | Capped sample of missing references. |
| `top_docops_move` | Conservative next cleanup recommendation. |

## Brief Sections

| Daily Brief Section | DocOps Contribution |
|---|---|
| What happened | DocOps gate and inventory ran. |
| What was real | Counts came from filesystem-backed checks. |
| What is broken | Blocking failures, stale assertions, missing managed paths. |
| What burned time/money | Excess doc ambiguity and repeated rediscovery risk. |
| What produced value | Clean gate, generated inventory, triage packets. |
| Human YDS ratings | No direct contribution. |
| Revenue/self-funding move | No direct contribution unless a revenue doc is flagged. |
| What should stop | Treating unreviewed planning docs as live governance. |
| Next highest-leverage move | Route the largest doc-confusion class to cleanup. |

## Current Feed Snapshot

From the 2026-05-05 local run:

| Signal | Value |
|---|---:|
| DocOps gate passed | yes |
| Markdown files scanned | 627 |
| Reserved-language docs | 256 |
| Unregistered reserved-language docs | 244 |
| Absolute local path references | 1,471 |
| Path references scanned | 10,002 |
| Missing references reported | 200 |

## Conservative Brief Text

Suggested wording for the next Daily Operating Brief:

> DocOps is green for the managed governance surface, but the broader corpus
> still contains a large doc-confusion backlog. The highest-leverage cleanup is
> to classify reserved-language docs into live governance, component guidance,
> historical plan, or archive before agents use them as decision inputs.

## Non-Goals

- Do not create a dashboard.
- Do not add runtime cron behavior here.
- Do not change the Daily Operating Brief generator in this branch.
- Do not promote codec packets into memory.
- Do not treat advisory DocOps inventory as blocking for every historical doc.
