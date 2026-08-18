# Running the Foundry non-stop (and what makes the signal "serious")

**Role:** reference (deploy + doctrine). No runtime/merge/governance authority.
Owned by `organism-rewire-2026-07` (next-item 15).

Straight answer to "how does it keep working non-stop so we get serious signal
and close serious loops": there are two always-on layers, and an honest ladder
from "runs non-stop" to "serious signal" to "loops closed." No hand-waving.

## The two always-on layers

1. **Cloud cron (light, already live).** `.github/workflows/foundry-lane.yml`
   runs on GitHub's infrastructure — no laptop, survives you sleeping,
   traveling, or offline. It runs the pipeline report-only and posts health to
   your walking brief. This is heartbeat + reporting, not volume.
2. **The standing daemon (the serious-signal engine).**
   `scripts/foundry/foundry_daemon.py` runs the inner loop *continuously* on an
   always-on host — many generations per hour, the volume real discovery needs.
   Cron alone can't do this (each Actions run is minutes-capped); a daemon can.

## Stand up the daemon (operator hands: a host)

On any always-on box with a fresh checkout of `origin/main`:

```ini
# /etc/systemd/system/foundry-daemon.service
[Unit]
Description=Sublimation Foundry non-stop engine
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/root/dharma_swarm
ExecStart=/usr/bin/python3 scripts/foundry/foundry_daemon.py --max-cycles 0 --interval-seconds 300 --budget 300
Restart=on-failure
RestartSec=30
# Once live model generation is wired, provider keys go here (never in git):
# EnvironmentFile=/root/.dharma/foundry.env

[Install]
WantedBy=multi-user.target
```

```
systemctl enable --now foundry-daemon
```

It halts itself cleanly (exit 0, stays stopped) on the kill-switch, on budget
exhaustion, or on a KILL kill-metric verdict — so `Restart=on-failure` only
brings it back after a genuine crash, never after an intentional halt. A KILL
shows up red in your walking brief; that's the signal to look.

## Why it can run non-stop safely

Every cycle, before doing anything, the daemon:

- checks the kill-switch (`~/.dharma/foundry/STOP` or the holon kill) and HALTS,
- checks cumulative spend against the `--budget` cap and HALTS when exhausted
  (free model lanes cost $0, so most cycles are nearly free),
- after the cycle, computes the five standing kill-metrics and HALTS on any
  KILL (survival collapse, discovery starvation, replication failure, target
  ban, commoditization) — it fails closed, it does not grind on a broken loop,
- writes `~/.dharma/foundry/kill_metrics.json` + `brief_fragment.md` so your
  phone always reflects the truth.

## The honest ladder: non-stop -> serious signal -> loops closed

The daemon runs non-stop **today** in dry mode (hermetic, synthetic proposer) —
that proves the engine and the safety rails, but synthetic cycles are rehearsal,
not signal. To make it serious, in order:

1. **Live generation** (operator: set the 4 provider keys as secrets;
   `docs/foundry/OPERATOR_UNBLOCKS.md`). Swap the daemon's dry cycle for a live
   cycle that runs the real army against a pinned target. This is the one code
   seam left (`_default_cycle` in `dharma_swarm/foundry/daemon.py`); it needs
   keys to test, which is why it is not wired blind.
2. **Real isolation for promotion** (host: Docker). Ring 2/3 promotion requires
   `docker --network none`; without it, cycles can EXPLORE but never CONFIRM.
   Free community GPU rails (GPU MODE / KernelBot) cover the kernel targets.
3. **Volume.** With 1+2, the daemon produces continuous, held-out-verified
   improvements — the serious signal. The kill-metrics tell you if the budget
   or target choice can't buy a real discovery rate.
4. **Loops close.** Serious signal becomes closed loops only through **ring-3
   external confirmation** across **three distinct domains**: merged upstream
   improvements (domain 1, already proven), one paid agent-behavior receipt
   (domain 2 — needs your wedge "yes"), and one externally-scored record or
   reviewed artifact (domain 3). When those exist,
   `dharma_swarm/foundry/guardian_feed.py` mints the One Wire quorum file and
   the swarm's blocked self-improvement loops (Cybernetic Loops 12/13) can go
   live — lawfully, fail-closed, with an explicit operator grant.

So: the daemon is the non-stop engine (built, safe, running dry today). Serious
signal is one key-set + one host + one small wiring away. Closed loops are that
plus your one wedge "yes" and the receipts the daemon itself mints.
