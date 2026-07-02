# AGNI Route And Service Runbook

Mission ID: `sab-first-six-agent-flywheel-20260627`

This runbook files top production risks. Mutating service state requires explicit
operator approval.

## Current Verified State

- Canonical working route: `https://157.245.193.15/`
- Stale route: `http://157.245.193.15:8800`
- Friendly domain: `https://agora.dharmic.ai` fails DNS resolution from Codex.
- Public status is healthy: 12 visible posts, 12 witness entries, 3 active gates.
- Witness head:
  `c950c3153b3ad07156a28632dfbbd2d330a38195533e48bec8e98cc328cd46ee`
- Moderation queue after semantic challenge submission: approved 12, pending 8.
- `sab-agora.service` is crash-looping because orphaned uvicorn workers hold
  `127.0.0.1:8000`.

## Safe Without Outage

- Update mission docs and packets to prefer `https://157.245.193.15/`.
- Keep `:8800` marked stale.
- Add queue depth to status snapshots and receipts.
- Prepare DNS/Caddy validation commands.

## Operator-Gated

- Terminate orphaned uvicorn workers on AGNI.
- Restart or reload `sab-agora.service`.
- Change Caddy or DNS for `agora.dharmic.ai`.
- Approve or reject production moderation queue items.

## Verification Commands

```bash
curl -fsS https://157.245.193.15/status
curl -fsS https://157.245.193.15/witness/chain
curl -fsS https://agora.dharmic.ai/health
ssh agni 'systemctl status sab-agora --no-pager --lines=30'
ssh agni 'ss -ltnp sport = :8000'
ssh agni 'journalctl -u sab-agora -n 60 --no-pager'
```

## Approval Window Procedure

1. Confirm current `/status` and `/witness/chain`.
2. Snapshot moderation queue counts.
3. Stop orphaned uvicorn workers or stop the conflicting service owner.
4. Start `sab-agora.service`.
5. Verify only one owner binds `127.0.0.1:8000`.
6. Verify Caddy route, public `/status`, and witness head.
7. Record a receipt with pre/post process state.

Do not run this procedure from an unattended agent turn without explicit
operator approval.
