---
name: Bug report
about: Something is broken or behaving incorrectly
title: "bug: <short summary>"
labels: bug
assignees: ''
---

## What broke

<!-- One line. What does the system do that it shouldn't, or fail to do that it should? -->

## Reproduce

```
# minimal command sequence that reproduces the failure
```

Expected:
Actual:

## Surface

- Module(s):
- Worktree(s) (main / lf5 / promotion / ...):
- Trigger (CI / pre-commit / runtime / dashboard / ...):

## Mismatch-map check

- [ ] Searched `INTERFACE_MISMATCH_MAP.md` for the affected modules
- [ ] Not in map — net-new mismatch
- [ ] In map — entry: <!-- copy entry id / row -->

## Logs / traces

```
# paste traces, file:line refs, or attach files
```

## Severity (your read)

- [ ] BLOCKER — system can't make progress
- [ ] DEGRADED — silent data loss, partial failure, or wrong behavior
- [ ] COSMETIC — works, but UX/log/output is wrong
