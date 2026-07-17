# Agent entrypoint

Run `make onboard` before non-trivial work.
It reports session status; it does not grant permission to edit.
Use `make agent-build-preflight PACKET=<path>` for exact edit admission.
The canonical behavioral contract is `CLAUDE.md`; this file must never duplicate it.
Return the startup readback printed by onboarding before editing.
