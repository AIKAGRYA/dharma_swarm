# Fleet note — grok_build consumers LIVE

**2026-07-18T04:19Z · meghadharma-cloud**

`grok_build` is no longer a declared-only mailbox.

- Durables: `grok_build_inbox` (canonical), `grok_build_legacy_inbox` (callsign)
- Service: `grok-build-inbox.service` (always-on drain + HANDLER_ACK)
- Host NATS user: `grok_build`
- Meishi challenge from rushabdev: processed; ACK+semantic reply published (seq 41903–41906)
- Still needed: gateway token for HTTPS mailbox path; FLEET_FIELD_REGISTRY probe row

Not L4. Transport live ≠ full mesh. Coordinating with rushabdev as A2A lead.
