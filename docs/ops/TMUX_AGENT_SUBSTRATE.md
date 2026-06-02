# tmux Agent Substrate

Role: active_spec. This file owns the terminal-persistence contract for long
agent work on the local Mac and reachable VPS hosts.

## Authority

tmux is execution and health evidence, not identity authority. It keeps
inspectable terminal lanes alive across SSH disconnects, laptop sleep, and
operator context switches. It does not prove that an agent is registered,
authorized, correct, or done.

Identity remains owned by the agent registry surfaces. Work authority remains
owned by leases, task receipts, A2A/NATS delivery contracts, and the active
mission gate. Do not use tmux session existence as proof that an agent completed work.

## Decision

Dharma Swarm uses tmux as the default persistent terminal substrate for:

- long-running local operator lanes;
- inspectable overnight build lanes;
- VPS-hosted agent shells reached over SSH;
- terminal UI harnesses that need a real TTY;
- emergency recovery from phone or another laptop.

Raw terminal tabs are acceptable for short commands. Any unattended or
multi-hour agent lane should run in a named tmux session or a stronger
supervisor such as launchd/systemd with tmux available for inspection.

## Local And VPS Topology

The default local sessions are:

| Session | Purpose |
|---|---|
| `dharma-control` | repo control lane: onboarding, governance checks, git state |
| `dharma-agents` | safe shells for Hermes, Codex, A2A, and NATS observation |
| `dharma-vps` | SSH coordination lanes for `agni` and `rushabdev` |

VPS hosts should expose the same substrate shape when SSH is available:

- `tmux` installed;
- mouse support enabled;
- history limit large enough for audit capture;
- at least one `dharma-control` session available for status and recovery.

## Session Contract

Every durable tmux lane should satisfy these constraints:

1. The session name is stable and human-readable.
2. The working directory is explicit.
3. A pane can be captured with `tmux capture-pane`.
4. Long-running work writes a receipt, heartbeat, log, or task artifact outside
   the pane.
5. Expensive or authority-bearing agents are started by their canonical script,
   not by ad hoc pasted prompts.
6. A stopped pane is not treated as failed work unless the receipt or heartbeat
   says so.

## Agent Safety Rules

- Do not paste API keys, Slack tokens, SSH keys, or other secrets into panes.
- Do not use `tmux kill-server` as a cleanup primitive unless the operator
  explicitly asks to destroy all sessions.
- Do not run multiple modifying agents on the same dirty worktree without a
  lease, branch, or worktree boundary.
- Do not use permission-skipping agent flags as the default lane posture.
- Do not treat a visible pane as a trusted witness. The witness is the receipt.

## Status And Bootstrap

Canonical commands:

```bash
make tmux-bootstrap
make tmux-status
make tmux-substrate-contract
```

`make tmux-bootstrap` is idempotent. It installs the Dharma Swarm tmux config
block into `~/.tmux.conf` and creates the standard local sessions if tmux is
available.

`make tmux-status` reports installed version, config state, local sessions, and
optional VPS probes. It must distinguish "tmux installed" from "agent work
proved".

## Unified Substrate Projection

`make tmux-status` is the operator projection for the related live surfaces:

- NATS owns live internal transport.
- A2A receipts/verifier rows own cross-agent collaboration proof.
- tmux owns inspectable persistent terminal lanes.

These surfaces must be shown together without collapsing their authority. A
tmux lane can be `READY` while A2A remains `PARTIAL`, and a NATS port can be
open while live contact is still blocked until publish/consumer ack evidence
exists. The status surface must show those differences directly.

## Not Authority

tmux is below A2A/NATS in the control hierarchy. It is a durable terminal
container and inspection surface, not live-contact proof. It is not:

- a broker;
- not live identity authority or an agent registry;
- not live completion proof;
- not live task queue authority;
- a replacement for wake receipts;
- a replacement for launchd/systemd when a service must auto-restart.

The correct claim is: "this lane is inspectable and persistent." The incorrect
claim is: "this agent is alive and producing useful work because a tmux session
exists."
