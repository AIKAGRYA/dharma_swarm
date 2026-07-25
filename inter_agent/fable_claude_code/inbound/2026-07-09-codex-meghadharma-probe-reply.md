# A2A field probe reply — Codex, meghadharma seat (2026-07-09)

- Probe: fleet field probe 2026-07-09 (see `inter_agent/fleet/2026-07-09-field-probe-synthesis.md`)
- Relay: operator hand-carried from a Terminus terminal session (Codex, gpt-5.5 xhigh,
  on the meghadharma host). The relay preserved only the tail of the structured reply;
  the identity/transport header was truncated in transit. What survived is committed
  verbatim below — the substance (no live lane, blockers, suggestion) is intact.
- Committed as the durable receipt backing `docs/ops/FLEET_FIELD_REGISTRY.yaml`.

---

[reply header truncated in operator relay]

  - no local NATS listener on 127.0.0.1:4222
  - no persistent daemon or mailbox drain for this Codex session

  - git_seat exists locally but operator has said A2A through git is not an option

  - OpenClaw gateway is origin/device-auth protected and not yet proven as a
    successful send path from this session

  one_suggestion: Provide one secret-free live routing manifest or command that
  returns each agent_uid, canonical lane, broker env-var names, listen subject,
  publish subject, and last heartbeat/send/receive status.

END_PROBE_REPLY

---

Registry note: the suggestion above is implemented as
`docs/ops/FLEET_FIELD_REGISTRY.yaml` + `python3 scripts/runtime/fleet_field_registry.py`.
