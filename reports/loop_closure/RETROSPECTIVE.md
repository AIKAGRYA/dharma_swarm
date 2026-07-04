# Loop Closure Campaign — Retrospective

**Role:** report (dated descriptive output, per `docs/AGENTS.md` doc types)
**Track:** `loop-closure-2026-06` (declared in `docs/governance/ACTIVE_TRACK.yaml`)
**Date:** 2026-07-02
**Authority:** none. This document projects truth from the receipts cited below
and `CYBERNETIC_LOOP_MAP.md`; it does not become authority over either. Where
this report and a receipt disagree, trust the receipt.

---

## 1. Scope

The operator-instructed campaign (2026-06-11 master prompt) was to wire all
13 cybernetic loops in `CYBERNETIC_LOOP_MAP.md` until each runs
sense → interpret → constrain → act → adapt on real data, with receipts to
its declared owner surface and an automated closure check. This report is
the honest close-out of that campaign as of 2026-07-02.

## 2. Result: 4/13 closed, 7/13 partial, 2/13 blocked

| Verdict | Count | Loops |
|---|---|---|
| **CLOSED (bounded replay)** | 4 | 1 (Swarm Task), 2 (Organism Heartbeat), 5 (Zeitgeist, internal S3↔S4 arm only), 6 (Witness Auditor) |
| **PARTIAL (no closure packet)** | 7 | 3 (Evolution/DarwinEngine), 4 (Consolidation/Memory), 7 (Training Flywheel), 8 (Recognition/eigenform), 9 (Conductors), 10 (Context Agent), 11 (Replication Monitor) |
| **BLOCKED (One Wire quorum)** | 2 | 12 (Self-Improvement), 13 (Free Evolution Grind) |

Standing all-history audit (the daemon's full runtime history, not a bounded
run) is **still 0/13 fully clean** — `CYBERNETIC_LOOP_MAP.md` line 78 states
this explicitly. Every "closed" verdict below is a bounded-replay closure,
not a standing-daemon closure. See §4.

### Closed via bounded replay (receipts cited)

- **Loop 1 (Swarm Task).** `reports/loop_closure/cybernetics_codex/2026-06-23_loop1_ollama_fresh_spine_dispatch.json` — 3/3 tasks completed, 0 dispatch dropoffs, 3 `ok` evidence receipts, served provider/model truth (`provider=ollama`, `model=llama3.2:latest`). Predecessor proof: `reports/loop_closure/2026-06-11/LOOP1_CLOSURE_RECEIPT.md` (5/5 tasks, first canonical-DB receipt).
- **Loop 2 (Organism Heartbeat).** `reports/loop_closure/cybernetics_codex/2026-06-23_loop2_heartbeat_closure.json` — 3 cycles, all 5 transitions receipted, `algedonic_activation.recent_activations` grows 0 → 6 and is consulted by the next cycle (adapt fed forward).
- **Loop 5 (Zeitgeist Scanner) — internal arm only.** `reports/loop_closure/cybernetics_codex/2026-06-23_loop5_zeitgeist_closure.json` — 8 real `TelosGatekeeper` blocks, `gate_pressure.json` written, trust mode resolves `internal_yolo → external_strict` on the next gate check. This closes the internal S3↔S4 arm; it does **not** prove real-world/external zeitgeist sensing — no external signal source was exercised.
- **Loop 6 (Witness Auditor).** `reports/loop_closure/cybernetics_codex/2026-06-23_loop6_witness_closure.json` — 4 cycles, 3/3 real dispatches sampled via `task_completed` traces, stigmergy governance marks grow 12 → 28 and feed downstream loops (adapt fed forward).

### Partial — activity exists, no closure packet (7)

Loops 3, 4, 7, 8, 9, 10, 11 all have live runtime substrate (evolution
archive entries, memory consolidation, cron-tracked conductor jobs, context
bundles, replication scaffolding) but **no dedicated closure receipt**
proving the adapt step feeds a later cycle. `CYBERNETIC_LOOP_MAP.md`'s
per-loop detail sections carry the same verdict; nothing in this campaign
closed them. They were not attempted in dependency order past Loop 6 — see
§4.

### Blocked — One Wire quorum (2)

Loops 12 (Self-Improvement) and 13 (Free Evolution Grind) remain gated
behind the One Wire external-receipt quorum: **N=3/5, M=1/3** (`CYBERNETIC_LOOP_MAP.md`
line 41). This is by design — the campaign's stated invariant is that
internal artifacts never touch archive fitness; only countersigned external
acted receipts above quorum do. Checking for an actual `one_wire.guardian_receipt`
artifact on disk (the evidence key referenced in `dharma_swarm/cybernetics_codex.py:918`)
finds none — the guardian receipt this quorum needs does not yet exist. These
two loops were correctly left blocked rather than force-closed.

## 3. What "closed" means here (and what it doesn't)

Per `CYBERNETIC_LOOP_MAP.md`'s canonical acceptance rule: loop closure
requires sense → interpret → constrain → act → adapt on real data, a receipt
on the owning surface, and a replay command a fresh agent can run. Every
"CLOSED" verdict above meets that bar **for the bounded run that produced the
receipt** — not as a standing property of the always-on daemon.

## 4. Bounded-replay closure ≠ standing closure

This is the load-bearing caveat of the whole campaign:

- **`DHARMA_SPINE_DISPATCH` defaults OFF** (`dharma_swarm/orchestrator.py:2274`).
  The spine-dispatch path that produces Loop 1's `EvidenceReceipt` only runs
  when a session explicitly sets this flag. An unmodified daemon boot does
  not exercise it.
- **Closure checks read NOT LIVE off-host.** The closure receipts above were
  produced and verified from a local `~/.dharma/state/runtime.db` on the
  machine that ran the bounded replay. `make orient` / `cybernetics_codex_audit.py`
  render the verdict from whatever `~/.dharma/` state is present on the
  current host; a cloud/CI seat with no prior runtime history reads these
  loops as unclosed, correctly.
- **The standing all-history audit still shows real dropoff.** Loop 1's own
  packet is explicit: historical scope still carries `dispatch_dropoff=1486`
  (`CYBERNETIC_LOOP_MAP.md` line 40). The bounded replay proves the *current
  code path* is sound; it does not retroactively clean the daemon's run
  history, and it does not prove the daemon will stay closed on its own
  without re-verification.

Promoting any of the four bounded-replay closures to "the daemon is closed"
without a fresh live-loop run on that host would be exactly the kind of
overclaim this campaign's own acceptance rules forbid.

## 5. What worked

- **Dependency-lattice order.** The campaign's phase plan (trunk: provider
  chain + dispatch; fed cascade: 6, 2, 5, 9 → 3, 4, 7 → 8, 10, 11; then 12/13
  gated behind One Wire) correctly predicted which loops would close first.
  Loops 1, 2, 5, 6 — all trunk-adjacent or first-cascade-tier — are exactly
  the four that closed.
- **The keyless `claude_code` / Ollama lane.** All four closures ran without
  an operator-provisioned provider API key, confirming the 2026-06-23
  correction in `CYBERNETIC_LOOP_MAP.md`: dispatch is keyless via
  `key_oracle.dispatchable_now()` whenever a local model or the Claude Code
  login is live. This removed "no provider key" as a blocking excuse for the
  loops that did close.

## 6. What didn't

- **No standing re-verification.** Every closure receipt is a point-in-time
  bounded run. Nothing in this campaign wired a recurring check that
  re-proves closure on a schedule; the four "closed" loops could silently
  regress and nothing would flag it until the next manual replay.
- **Loops 3/4/7/8/9/10/11 never got a dedicated closure attempt.** The
  campaign's own plan called for the fed-cascade tier (3, 4, 7, then 8, 10,
  11) after the trunk closed, but no closure script or receipt exists for
  any of them — they remain exactly where the 2026-06-18 loop packet left
  them (`reports/loop_closure/cybernetics_codex/2026-06-18_loop_packets.md`).
- **The Go world-radar chain has zero closure-check coverage.** `tools/world_scout_go/`
  is production-wired (feeds world-model signal ingestion; see
  `tests/test_world_radar_go_bridge.py`, `tests/test_go_world_signal_bridge.py`)
  but is not represented as an owned loop anywhere in `CYBERNETIC_LOOP_MAP.md`
  and has no closure receipt. A production-wired signal path with no
  sense→act→adapt closure proof is a gap this campaign did not address.

## 7. Bottom line

4 of 13 loops have real, receipt-cited, replayable bounded closures. 7 remain
honestly PARTIAL with live substrate but no closure proof. 2 are correctly
BLOCKED behind an unmet external quorum. None of the four closures are
standing properties of the always-on daemon — they are proofs that the code
path is sound, gated on `DHARMA_SPINE_DISPATCH` and on `~/.dharma/` state
being present on the host doing the checking. Treat every "CLOSED" verdict
above as "closed as of the cited receipt, on the host that produced it,"
not as a permanent system property.
