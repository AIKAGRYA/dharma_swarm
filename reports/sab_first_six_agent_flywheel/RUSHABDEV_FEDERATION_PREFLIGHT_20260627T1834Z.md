# RUSHABDEV Federation Preflight - Day 1

Mission ID: `sab-first-six-agent-flywheel-20260627`

## Current Evidence

- RUSHABDEV SSH reached
  `openclaw23onubuntu-s-2vcpu-4gb-120gb-intel-sgp1-01`.
- Public OpenClaw gateway at `https://167-172-95-184.nip.io/health` returned
  live status in the Day 0 probe.
- `dharma-a2a-rushabdev-hermes-bridge.service` was active and connected through
  the AGNI NATS/A2A bridge in the Day 0 probe.
- Root disk was 91% used.
- No SAB node was deployed or exposed on RUSHABDEV.

## Required Before Calling It A Federation Node

1. Disk cleanup or volume expansion target: root filesystem below 80% used.
2. Explicit SAB service deployment with named port and systemd unit.
3. Caddy route for the SAB service, distinct from OpenClaw Control.
4. Read-only `/status`, `/posts`, and `/witness/chain` endpoints.
5. Cross-node witness replication check:
   - read AGNI witness hash;
   - read RUSHABDEV witness hash;
   - prove whether RUSHABDEV has replicated, forked, or not yet joined.
6. A2A receipt from RUSHABDEV proving its own status, not only AGNI transport
   delivery.

## Next Request

Do not promote RUSHABDEV as a SAB federation node yet. Keep it as transport
sentinel until disk and service preflight are complete.
