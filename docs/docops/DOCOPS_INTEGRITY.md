# DocOps Integrity System

**Status:** v0 governance gate
**Owner:** `docs/governance/CANONICAL_DOC_STACK.md`
**Checker:** `scripts/docops/check_docops_integrity.py`

## Purpose

Documentation in a multi-agent repository decays at code-change speed. The
fix is not more prose. The fix is tested documentation infrastructure: claims,
paths, authority, generated inventory, review hints, and freshness are checked
by a repeatable script.

## Primitives

1. **Executable doc assertions**: `docs/docops/assertions.yaml` pairs selected
   count-sensitive claims with a metric and a human verification command. The
   checker fails when the doc claim and filesystem metric diverge.
2. **Path existence guards**: managed docs are scanned for Markdown links and
   simple backticked file paths. Missing repo paths fail the gate.
3. **Canonical registry enforcement**: managed docs that use authority terms
   such as "source of truth", "canonical", "authoritative", or "ground truth"
   must be registered in `docs/governance/CANONICAL_DOC_STACK.md`.
4. **Auto-generated sections**: generated blocks use markers of the form
   `<!-- DOCOPS:START metric=repo_inventory -->` and are refreshed by the
   checker with `--write-auto-sections`.
5. **Change-triggered doc review**: `--changed-from <ref>` reports docs that
   mention changed Python files. This is advisory so it can guide PR review
   without blocking unrelated code fixes.
6. **Staleness TTL**: the assertion config has `verified_at` and `ttl_days`.
   Expired assertions fail until the verification date is refreshed.

## Commands

Run the full managed check:

```bash
python scripts/docops/check_docops_integrity.py
```

Refresh generated sections:

```bash
python scripts/docops/check_docops_integrity.py --write-auto-sections
```

Review docs affected by code changes:

```bash
python scripts/docops/check_docops_integrity.py --changed-from origin/main
```

## Scope

This v0 intentionally checks the live governance and navigation surface first.
It does not try to make every historical plan, prompt, archive, generated
report, or research memo clean in one pass. Those files remain debt until they
are promoted, archived, or brought under managed DocOps scope.

## Failure Policy

- Assertion mismatch: blocking.
- Missing managed path reference: blocking.
- Unregistered authority term in managed docs or changed docs: blocking.
- Stale auto-generated section: blocking unless regenerated.
- Changed-code doc candidates: warning only.
- Expired `verified_at`: blocking.
