---
id: resource-leak-scan
version: 0.0.1
theme: 14-state-and-lifecycle
status: tested
invariant: >
  Every acquired resource (file, socket, DB connection, lock, subprocess) must have
  a guaranteed release on ALL paths, including exceptions. The proof is a scope-
  bound construct (`with` / RAII / try-finally), not "we close it at the end" —
  because the end isn't reached when an exception fires. An unguarded acquire is a
  leak under failure, which is exactly when you can least afford it.
lineage:
  - "Dijkstra — structured control flow; a resource's lifetime is a scope"
  - "RAII (Stroustrup) — bind acquisition to a scope so release is automatic"
  - "Gray — faults are normal; the exception path is the one that leaks"
ground_truth_tools: ["AST: acquire without a context manager / finally", "fd/handle counts under load", "the language's leak warnings (ResourceWarning)"]
returns_clean: true
---

## Prompt

> Scan for **resource leaks**. The invariant (RAII, Dijkstra): every acquired
> resource is released on **all** paths, including exceptions — proven by a
> scope-bound construct (`with`, `try/finally`, RAII), never by "we close it later."
> The exception path is the one that leaks, and faults are normal (Gray).
>
> **Find:** `open()` / `connect()` / `socket()` / `Lock()` / `Popen()` acquired
> **without** a context manager or `finally`. For each: `file:line`, the resource,
> the path on which release is skipped (which exception bypasses the close), and the
> fix (`with`-statement / `try-finally`). Rank by how hot the path is.
>
> **Confirm under failure, not just happy path.** Recommend enabling
> `ResourceWarning` / fd-count checks to verify. **Return clean** if every acquire
> is scope-bound — and note that's the common case in modern code; don't pad.

## Why it's built this way

The leak only manifests on the exception path, so a happy-path read misses it; the
discipline is to look for the *absence of the scope-binding construct*, which is
statically checkable, and to confirm with the runtime's own leak warning. RAII is
the canonical answer; `with` is Python's RAII.

## Demonstration run

**Target:** `dharma_swarm/`, 2026-06-25. Tool: AST scan for `= open(...)` not
inside a `with`.

- **3 candidate sites** repo-wide where `open()` is assigned without a `with` —
  a low number for an 1,800+ file codebase, i.e. the codebase is **largely
  scope-bound already** (mostly `with open(...)`).
- **Disciplined output:** a 3-line review checklist (each `file:line` + "confirm
  release on the exception path; wrap in `with`"), **not** a refactor — and the
  honest headline that this repo is mostly clean here. Confirm with
  `python -W error::ResourceWarning` on the relevant tests rather than eyeballing.

This is a **return-clean-leaning** result: 3 candidates, codebase otherwise sound.
A scanner that printed a scary wall here would be manufacturing alarm.

## Changelog

- **v0.0.1** (2026-06-25) — resource-leak scan (RAII/Gray); look for the missing
  scope-binding construct, confirm on the exception path via `ResourceWarning`.
  Tested on `dharma_swarm/`: only 3 unguarded `open()` candidates — reported as a
  short checklist with an honest "mostly clean" headline.
