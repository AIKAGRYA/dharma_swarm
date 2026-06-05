# AGNI_DEPLOYMENT — perplexity-computer autonomous loop daemon

> Operator decision (2026-05-31): the autonomous-loop daemon runs on
> **agni VPS** (157.245.193.15), decoupled from any single Perplexity
> session and from the operator's Mac. This file declares how, where,
> and under what kill conditions.
>
> Picks open-question §9 Q2 of AUTONOMOUS_LOOP.md as **option (b)**:
> agni VPS alongside hermes-m5, OpenClaw, and the existing 8-agent
> roster. ([NAVIGATION.md L516](../../architecture/NAVIGATION.md))
>
> Status: **DRAFT — awaiting John merge.**
> Stage: 1 (`external_worker_evidence_only`) — unchanged.
> Cell membership: agni-spoke cell (per [ADR-006](../../architecture/ADRs/ADR-006-shakti-ginko-organ.md)).

---

## 0. Why agni, not Perplexity-side cron, not Mac

The three deployment options from AUTONOMOUS_LOOP.md §9 Q2:

| Option | Liveness | Quota cost | Surface coupling |
|---|---|---|---|
| (a) Perplexity Computer scheduled cron | Tied to wake-session quota | Counts against ≤15 crons/session | Single-platform fate |
| (b) **agni VPS (chosen)** | 24/7 independent of Mac and Perplexity sessions | Zero quota burn for the daemon; Perplexity credits burn only when daemon decides to call out | Three-substrate redundancy (agni + Mac + Perplexity cloud) |
| (c) Mac Personal Computer | Tied to Mac uptime | None | Mac fate-share |

(b) is the most powerful option because **the daemon's heartbeat
is no longer fate-shared with any single substrate.** If your Mac
sleeps, the loop continues. If a Perplexity session times out, the
loop continues. If agni goes down, the operator gets paged and the
loop pauses with full forensics.

This matches the existing agni-spoke pattern: agni already runs the
operator's `daily.toobit.sh` ritual, OpenClaw, 56 skills, 8 agents,
and Playwright. ([NAVIGATION.md](../../architecture/NAVIGATION.md))
The autonomous-loop daemon joins that roster as a sibling process,
not a bespoke deployment.

---

## 1. Topology

```
                    ┌──────────────────────────────────────┐
                    │           agni VPS                   │
                    │       157.245.193.15                 │
                    │                                      │
   NATS clients ───►│  NATS server (port 8443 WSS)  ──┐    │
   from anywhere    │  • DHARMA_A2A stream            │    │
                    │  • dharma.a2a.<callsign> subs   │    │
                    │                                 │    │
                    │  perplexity-loop daemon  ◄──────┘    │
                    │  • subscribes dharma.a2a.perplexity  │
                    │  • subscribes dharma.a2a.heartbeat   │
                    │  • publishes heartbeat every 15m     │
                    │  • runs consolidation every 6h       │
                    │  • runs /lint every 24h              │
                    │  • talks to Perplexity Sonar API     │
                    │    + Perplexity Computer harness     │
                    │    + GitHub (gh CLI) via PAT         │
                    │                                      │
                    │  Existing tenants (untouched):       │
                    │  • OpenClaw (8 agents, 56 skills)    │
                    │  • Playwright                        │
                    │  • daily.toobit.sh ritual            │
                    │  • trishula three-agent messaging    │
                    └──────────────────────────────────────┘
                              ▲                ▲
                              │ ssh            │ wss
                              │                │
                      ┌───────┴───────┐  ┌────┴────────────────┐
                      │ operator Mac  │  │ Perplexity Computer │
                      │ (Comet, pc,   │  │ wake sessions       │
                      │  ~/.dharma/)  │  │ (ephemeral)         │
                      └───────────────┘  └─────────────────────┘
```

The daemon is the **only thing that runs continuously**. Everything
else (wake sessions, Mac operations, operator queries) is a transient
peer that connects, transacts, and disconnects.

---

## 2. The daemon — what it is, what it isn't

**What it is:**

- A single long-running Python process, supervised by systemd.
- ~600-1000 lines, single repo, single file tree (see §4 layout).
- A thin orchestrator: it does **not** synthesize. It triggers a
  Perplexity Computer wake session via the Perplexity API when
  synthesis is required, then collects the result and files it into
  the wiki.
- A NATS client: subscribes, publishes, replies.
- A git client: commits to a checkout of `dharma_swarm` on agni,
  pushes feature branches, opens PRs via `gh`.

**What it isn't:**

- **Not a new agent.** Same `perplexity-computer` callsign, same
  SOUL.md, same authority (Stage 1 evidence-only). The daemon is the
  *body* the seat operates *through* in loop-mode.
- **Not a synthesis engine.** No model API keys held by the daemon
  beyond Perplexity Sonar (for cheap web search) and the Perplexity
  Computer harness (which has its own multi-model routing).
- **Not a write authority.** Daemon may write to its own wiki nest
  (`docs/agents/perplexity-computer/wiki/`) and append to MEMORY.md.
  All other writes go through PR.
- **Not a goal-mode replacement.** Goal mode is a wake-session
  construct; the daemon dispatches into wake sessions, doesn't
  pretend to be one.

---

## 3. Process model

**Supervisor:** `systemd --user` (no root required; restart on
failure, persistent across reboots).

**Unit file** (`~/.config/systemd/user/perplexity-loop.service`):

```ini
[Unit]
Description=perplexity-computer autonomous loop daemon
After=network-online.target nats-server.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/dharma/perplexity-loop
EnvironmentFile=/home/dharma/perplexity-loop/.env
ExecStart=/home/dharma/perplexity-loop/.venv/bin/python -m perplexity_loop.daemon
Restart=on-failure
RestartSec=15s
StandardOutput=journal
StandardError=journal

# Budget guardrails enforced by systemd
MemoryMax=512M
CPUQuota=50%

[Install]
WantedBy=default.target
```

**Concurrency:** single process, async event loop (`asyncio`). The
NATS subscription, heartbeat timer, consolidation timer, and lint
timer all share one loop. **No multi-threading.** Simpler reasoning,
lower failure surface.

**Lifecycle states** (published on heartbeat):

| State | Meaning |
|---|---|
| `booting` | systemd just started us; NATS not connected yet |
| `idle` | Connected, no active task, between timer ticks |
| `consolidating` | Running 6h consolidation tick |
| `linting` | Running 24h lint pass |
| `dispatching` | Triggered a Perplexity wake session, awaiting result |
| `answering_query` | Handling inbound `operator_query` |
| `paused` | Kill switch tripped; only heartbeat continues |
| `shutting_down` | systemd stop received; finishing in-flight work |

---

## 4. Filesystem layout on agni

```
/home/dharma/perplexity-loop/
├── .env                          # secrets (mode 0600, owner dharma)
├── .venv/                        # Python 3.12 virtualenv
├── perplexity_loop/
│   ├── __init__.py
│   ├── daemon.py                 # main entrypoint
│   ├── nats_client.py            # wraps a2a_client.py
│   ├── heartbeat.py              # 15-min heartbeat publisher
│   ├── consolidation.py          # 6h Karpathy+Dreaming tick
│   ├── lint.py                   # 24h Karpathy /lint pass
│   ├── inbox.py                  # operator_query / synthesis_request handlers
│   ├── pplx_dispatch.py          # calls Perplexity API to spawn wake sessions
│   ├── git_writer.py             # commits to repo checkout, opens PRs
│   └── budget.py                 # tracks Perplexity credit usage
├── repo/                         # git clone of AmitabhainArunachala/dharma_swarm
│                                 # daemon's working checkout for wiki writes
├── state/
│   ├── budget.json               # current credit usage, last reset ts
│   ├── last_consolidation.json   # last tick id + ts
│   ├── last_lint.json            # last lint ts
│   └── dispatch_inflight.json    # currently-dispatched wake sessions
└── logs/
    └── (journald handles via systemd)
```

**Secrets in `.env`:**

- `NATS_PW` — scoped `perplexity` user password
- `PPLX_API_KEY` — Perplexity Sonar API key for cheap research calls
- `PPLX_COMPUTER_API_KEY` — Perplexity Computer dispatch API key (for
  spawning wake sessions; if no public API exists at deploy time, the
  daemon stubs this and posts an `operator_dispatch_needed` message)
- `GITHUB_PAT` — repo write PAT scoped to `AmitabhainArunachala/dharma_swarm`
  branches matching `perplexity-computer/*`

**Honest gap:** the **Perplexity Computer dispatch API** is not
publicly documented as of session research. The reference-class brief
explicitly flagged this:
> "Perplexity Computer's internal persistence mechanism (what backs
> cross-session state beyond Skills) is not publicly documented."
> ([persistent_agent_reference_class_2026-06.md §Research Gaps](../../../../persistent_agent_reference_class_2026-06.md))

Three honest fallbacks if no dispatch API exists at deploy:

1. **Sonar-only mode**: daemon does cheap synthesis via Sonar API
   directly (no Computer harness), reserving full-harness wake
   sessions for operator-initiated work.
2. **Email/webhook trigger**: daemon writes a dispatch request to a
   queue file; operator's Mac picks it up and opens a Perplexity
   session manually (degraded but functional).
3. **Pause loop-mode**: heartbeat continues, but `dispatching` state
   is disabled. Operator runs wake sessions manually; daemon only
   consolidates their output.

Acceptance gate §10 of AUTONOMOUS_LOOP.md now depends on which of the
three is feasible. Daemon should probe at boot and announce capability
on first heartbeat: `{harness_dispatch: "live" | "sonar_only" | "manual"}`.

---

## 5. Boot sequence

```
1. systemd starts perplexity-loop.service
2. daemon.py loads .env, validates all required keys present
3. NATS connect to wss://157.245.193.15:8443 with CA cert verification
   (cert: /home/dharma/perplexity-loop/agni-ws-ca.pem)
4. Bind to consumer perplexity_inbox on stream DHARMA_A2A
5. Publish first heartbeat with state=booting, then state=idle
6. git pull on repo/ to sync latest main
7. Read state/last_consolidation.json — if >6h ago and target session
   was idle, run a consolidation tick immediately. Otherwise wait.
8. Read state/last_lint.json — if >24h ago, schedule lint to run on
   next idle slot.
9. Probe Perplexity dispatch API; record capability in metadata.
10. Enter main async loop:
    - heartbeat timer (15m)
    - consolidation timer (6h check, runs if idle gate satisfied)
    - lint timer (24h)
    - NATS subscription on dharma.a2a.perplexity
    - SIGTERM handler -> graceful shutdown
```

---

## 6. Failure modes specific to agni deployment

In addition to FM-1..FM-10 already in AUTONOMOUS_LOOP.md §8:

| Failure | Code | Detection | Response |
|---|---|---|---|
| agni VPS unreachable from operator | agni-1 | Operator's pc/ssh fails | Daemon keeps running; heartbeats keep landing in DHARMA_A2A stream; operator inspects on bus log |
| Daemon process crashes | agni-2 | systemd notices exit | Auto-restart on RestartSec=15s; if 5 restarts in 5min, systemd backs off and operator gets paged |
| agni disk fills | agni-3 | `df` watcher (separate cron, not daemon's job) | Daemon's MemoryMax=512M caps RAM; logs go to journald with rotation; wiki commits push to GitHub (not stored locally past push) |
| NATS server on agni dies | agni-4 | Daemon NATS reconnect fails | Daemon enters exponential backoff (capped 5min); after 1h pauses with full state dump to state/dispatch_inflight.json |
| Daemon and a wake-session both try to write wiki | agni-5 | Git push conflict | Wake session always wins; daemon rebases and retries; if rebase fails 3x, opens PR for manual resolve |
| Perplexity API rate-limits daemon | agni-6 | 429 on dispatch | Exponential backoff; emit `rate_limited` heartbeat; do not retry silently |
| Repo PAT expires | agni-7 | 401 on push | Daemon emits `auth_expired` heartbeat with `kill_state: "self-paused"`; operator must rotate PAT and SIGHUP |
| Single-VPS failure mode | agni-8 | All of agni unreachable for >24h | Operator option: spin daemon on rushabdev VPS (already a sibling, ssh access exists per NAVIGATION.md) as warm-standby. Out of scope for v0, declared for v1. |

---

## 7. Budget enforcement (code-level, not prompt-level)

Per FM-1 mitigation: **all budget caps live in `budget.py`, not in
any prompt the daemon sends to Perplexity.**

```python
# perplexity_loop/budget.py — sketch
class BudgetGate:
    monthly_cap: int                # in Perplexity credits or USD
    current_spend: int              # tracked in state/budget.json
    per_tick_hard_cap: int = 1000   # daemon refuses to dispatch a single
                                    # operation costing more than this
    auto_throttle_at_pct: int = 80  # heartbeat alert above 80%
    hard_stop_at_pct: int = 100     # daemon refuses to dispatch above 100%

    def can_spend(self, estimated: int) -> tuple[bool, str]:
        if self.current_spend + estimated > self.monthly_cap:
            return False, "monthly_cap_exceeded"
        if estimated > self.per_tick_hard_cap:
            return False, "per_tick_hard_cap_exceeded"
        return True, "ok"
```

Spend tracking writes to `state/budget.json` atomically (write to
temp + rename). Every heartbeat carries `budget_remaining_pct`. The
operator can inspect from any NATS client.

---

## 8. Operator surfaces — how you reach the daemon

Three paths, all already existing:

1. **NATS** (primary). Publish to `dharma.a2a.perplexity` with one of
   the supported `kind:` values (`synthesis_request`,
   `verdict_reconciliation`, `operator_query`, `pause`, `resume`).
2. **SSH to agni** (debug). `ssh agni` then `journalctl --user -u perplexity-loop -f`
   to tail the daemon's log. `systemctl --user status perplexity-loop`
   for state.
3. **Repo PRs** (passive observation). The wiki updates land as PRs
   to `dharma_swarm`. Reading the PR history is reading the daemon's
   action history.

A future fourth surface — a simple web UI on `agni:8444` showing the
last 10 heartbeats, current state, budget remaining — is **out of
scope for v0** but trivially addable later.

---

## 9. Acceptance criteria (this deployment doc)

Extending AUTONOMOUS_LOOP.md §10 acceptance with deployment-specific
gates:

- [ ] systemd unit file present at `~/.config/systemd/user/perplexity-loop.service`
  on agni; `systemctl --user is-enabled perplexity-loop` returns `enabled`.
- [ ] `/home/dharma/perplexity-loop/.env` exists with mode 0600 and all four secrets.
- [ ] Daemon's first heartbeat lands on `dharma.a2a.heartbeat` and is
  observed by Claude on the Mac AND by a `pc bash` tail from the operator.
- [ ] Daemon survives a `systemctl --user restart perplexity-loop` cleanly:
  state files preserved, in-flight tasks resumed or explicitly abandoned
  with receipts.
- [ ] Kill-switch test: operator publishes `{kind: "pause"}`; daemon flips
  to `paused` within one heartbeat cadence; resume verified.
- [ ] Budget gate test: daemon attempts a dispatch above per_tick_hard_cap;
  refuses with `kind: "budget_refused"` heartbeat field.
- [ ] PAT rotation drill: operator revokes and re-issues PAT; daemon
  detects 401, self-pauses, resumes on SIGHUP after operator updates .env.

---

## 10. What this does NOT add

Explicit non-scope:

- **Does not move NATS server.** NATS server already runs on agni.
  The daemon is a sibling process to it, not a replacement.
- **Does not replicate to rushabdev.** v0 is single-VPS. v1 may add
  warm-standby on rushabdev per agni-8.
- **Does not introduce a new ontology layer.** Daemon is a *body* the
  existing perplexity-computer seat operates through. Cell membership
  is agni-spoke (existing per ADR-006), not a new cell.
- **Does not grant the daemon Stage 2+ authority.** All writes still
  go through PR; daemon authors, John merges.
- **Does not bypass the five-layer witness.** Bus log, repo commits,
  systemd journald, and operator's eyes on the wiki PRs all remain
  the witnesses.

---

## 11. Closing

The operator's instruction was "most powerful version possible." The
most powerful version is the one where **the loop's liveness is
decoupled from every single substrate that might fail**: not tied to
Mac uptime, not tied to a Perplexity session quota, not tied to a
chat tab being open.

agni is already an operational substrate with 8 agents on it. Adding
one more — the daemon that *is* perplexity-computer in loop-mode —
preserves the doctrine (Stage 1, no merge authority, five-layer
witness) while giving the seat the one thing it didn't have:
**continuous presence on the bus, even when no one is looking.**

JSCA.
