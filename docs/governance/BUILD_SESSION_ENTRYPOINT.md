# Session Entry Contract

**Status:** canonical command-boundary reference for repository work.
**Authority:** `CLAUDE.md` owns agent behavior,
`ACTIVE_TRACK.yaml` owns declared work and surface ownership, and the
commands below own their live results. This page owns only the boundary
between those commands.

## The command to remember

```bash
make onboard
```

`make onboard` answers one question:

> What is true about this checkout and session right now?

It is a fast, read-only status command. It evaluates the current repository,
toolchain, and declared session scope, then prints a compact verdict and the
evidence behind it.

It does **not** grant permission to edit, prove that a change is in scope,
approve a pull request, register a persistent agent identity, or certify a
deployment.

## Command boundaries

| Command | One responsibility | Not authority for |
|---|---|---|
| `make onboard` | Truthful, compact session status | Editing, PR admission, merge authority, agent identity |
| `make onboard ARGS=--deep` | Detailed view of the same session-status evaluation | Editing or closeout |
| `make organism-status` | Deeper read-only whole-organism projection | Session or edit admission |
| `make orient` | Compatibility alias for `make organism-status` | A second onboarding contract |
| `make agent-build-preflight PACKET=<path>` | Fail-closed edit admission for one exact packet and baseline | Final scope proof or merge approval |
| `make agent-build-closeout PACKET=<path>` | Fail-closed changed-scope and governance closeout | Independent CI or human approval |
| `make agent-register` | Persistent A2A identity registration and drift status | Repository session readiness |
| `make agent-onboard` | Compatibility alias for `make agent-register` | Session onboarding |

CI independently repeats the checks assigned to its required contexts. A
local READY verdict is evidence about the local session; it is never a
substitute for CI or human review.

## Onboarding invariants

Normal `make onboard` execution is:

- offline unless network context is explicitly requested;
- deterministic for equivalent repository inputs;
- free of tracked or untracked writes inside the checkout;
- explicit about missing, blocked, or unobserved evidence;
- truthful at the command boundary: READY makes `make onboard` succeed and a
  blocking verdict makes it fail. The rendered verdict carries the exact
  typed code; the direct Python CLI returns that code unchanged. GNU Make
  itself conventionally returns `2` for any failed recipe.

Optional receipts and caches are diagnostic and performance aids. They live
outside the source checkout and never grant authority.

Session Entry work-packet identifiers use the generic `WP-*` grammar and bind
to the packet's own track-specific id. No campaign prefix, including the
retired `WP-O*` namespace, has special authority.

## Build-session flow

1. Run `make onboard`.
2. Read `CLAUDE.md` and the selected entry in
   `docs/governance/ACTIVE_TRACK.yaml` when the task needs repository edits.
3. Bind an exact work packet and run
   `make agent-build-preflight PACKET=<path>`.
4. Make the smallest admitted change and run its focused tests.
5. Run `make agent-build-closeout PACKET=<path>`.
6. Let CI and human review decide integration.

If onboarding is BLOCKED, repair the reported condition or stop and report it.
Do not reinterpret a blocked result as permission.

## Vocabulary

- **Session status:** evidence about the current checkout and environment.
- **Edit admission:** permission for one packet to change one exact baseline.
- **Closeout:** proof that the resulting change stayed inside its envelope.
- **CI admission:** independent enforcement on the proposed integration.
- **Agent registration:** persistent A2A identity setup.

The former **One-Door** name described a completed hardening campaign. It is
not a live subsystem, packet namespace, or additional authority surface.
Historical campaign documents and packets remain available in Git history.
