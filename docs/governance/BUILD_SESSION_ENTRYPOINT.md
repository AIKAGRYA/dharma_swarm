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
| `make vision` | Purpose/telos transmission and vision-doc navigation (projection) | Session status, liveness, edit admission, ratification, merge |
| `make agent-build-preflight PACKET=<path>` | Fail-closed edit admission for one exact packet and baseline | Final scope proof or merge approval |
| `make agent-build-closeout PACKET=<path>` | Fail-closed changed-scope and governance closeout | Independent CI or human approval |
| Risk-triggered packet-scope CI | Committed-range packet coverage for an integration event | Packet gate execution, local preflight or closeout, human approval, merge authority |
| `make agent-register` | Persistent A2A identity registration and drift status | Repository session readiness |
| `make agent-onboard` | Compatibility alias for `make agent-register` | Session onboarding |

CI independently repeats the checks assigned to its required contexts. The
packet-scope check proves committed-range packet scope only; it does not prove
local preflight or closeout, packet gate execution, human approval, or merge
authority. A local READY verdict is evidence about the local session; it is
never a substitute for CI or human review.

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

Packet-bound preflight and closeout are required when changed paths match Merge
Master Mike's `HOT_PATH_PATTERNS` in `scripts/runtime/pr_merge_control.py`; they
are optional otherwise. A narrower lane or campaign contract may require them
more broadly. Risk matching uses the conservative union of those patterns at
the declared event base and event head, so a stale branch cannot miss a newer
base policy and a change cannot remove its own trigger. When a pull request
triggers the rule, its packet must cover the full committed event range, not
only the hot path.

## Build-session flow

1. Run `make onboard`.
2. Read `CLAUDE.md` and the selected entry in
   `docs/governance/ACTIVE_TRACK.yaml` when the task needs repository edits.
3. If the change matches Mike's `HOT_PATH_PATTERNS`, bind an exact work packet
   and run `make agent-build-preflight PACKET=<path>`. For other changes a
   packet is optional.
4. Make the smallest admitted change and run its focused tests.
5. When a packet is required or voluntarily used, run
   `make agent-build-closeout PACKET=<path>`.
6. Let CI and human review decide integration.

If onboarding is BLOCKED, repair the reported condition or stop and report it.
Do not reinterpret a blocked result as permission.

## Vocabulary

- **Session status:** evidence about the current checkout and environment.
- **Edit admission:** permission for one packet to change one exact baseline.
- **Closeout:** proof that the resulting change stayed inside its envelope.
- **Packet-scope CI:** committed-range coverage proof, with no claim that
  packet gates, local preflight/closeout, human approval, or merge authority
  occurred.
- **CI admission:** independent enforcement on the proposed integration.
- **Agent registration:** persistent A2A identity setup.

The former **One-Door** name described a retired hardening campaign. It is
not a live subsystem, packet namespace, or additional authority surface.
The original campaign was retired rather than verified. Its specifications,
packets, unresolved obligations, and immutable recovery commands are indexed
in `REPO_GOVERNANCE_AUDIT.md` under “One-Door scope reset and provenance —
2026-07-17”, anchored at
`55cf277be0dbf3b5a74da03eb1d7243024556806`.
