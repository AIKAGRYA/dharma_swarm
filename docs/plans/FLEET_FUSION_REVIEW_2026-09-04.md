---
role: working_plan
date: 2026-09-04
status: REVIEW — operator-ordered fusion review of dharma_swarm + fleet-hub + AgentKanban against the "Living Brain" pattern; carries a build receipt and a yes-sheet; no runtime, merge, or governance authority
subordinates_to: docs/governance/CANONICAL_DOC_STACK.md
world:
  commit: d2b2f40447cf (+ this branch) · host: Claude Code cloud sandbox (Linux 6.18) · branch: claude/dharma-swarm-fusion-review-voer57
---

# FLEET FUSION REVIEW — why nothing fuses, what was wired today, what is yours to say yes to

**Read this first if you read nothing else.** The fleet does not fuse because
three small doors are shut, not because the architecture is wrong. Two of the
three are operator acts that take under an hour each. The third was code, and
it is built and proven on this branch. Everything else on the page you sent
(one brain, one loop, one agent per outcome) you already own in stronger
form; what you do not own is a single write-back path that every seat uses.

Glossary for this document: **bus** = the NATS/JetStream message broker on
AGNI that agents talk through. **ACL** = the broker's permission list saying
who may publish and subscribe where. **gateway** = an HTTPS door that lets an
agent use the bus with a token instead of broker credentials. **owner
adapter** = the piece of Fleet Hub that reads the real task database instead
of showing "unavailable".

## 1. The three doors

| Door | State on 2026-09-04 | Who can open it | Evidence |
|---|---|---|---|
| Peer-to-peer publish on the hub (FFR-D1) | Ratified 2026-07-09, **never applied**; the live fleet can only broadcast, it cannot DM | Operator, on AGNI, ~30 min | `docs/ops/FLEET_FIELD_REGISTRY.yaml:47-59`; template `scripts/ops/agni_hub_acl_ffr_d1.conf:30-60`; steps `docs/ops/A2A_LIVE_WIRE_RUNBOOK.md:16-43` |
| HTTPS mailbox gateway (the door for Hermes, Claude Code, Devin, cron seats) | Code merged and tested since 2026-07-09, **never deployed** | Operator, on AGNI, ~60 min | `dharma_swarm/a2a/mailbox_gateway.py:1-21`; `docs/ops/A2A_LIVE_WIRE_RUNBOOK.md:45-96`; `docs/ops/FLEET_FIELD_REGISTRY.yaml:243-248` |
| Fleet Hub owner adapter (Board / Helm / Needs-John light up) | **Built on this branch**, proven end to end on one machine | Done in code; production config is one env file on AGNI | `fleet-hub/src/hub/mission_http_provider.py`; `api/routers/mission_control.py`; `fleet-hub/docs/FLEET_HUB_OWNER_ADAPTER_EVIDENCE.md` |

Everything downstream of these three (agents seeing each other's work, the
phone page directing the fleet, Hermes seats reporting in) is blocked on them
and on nothing else the audits could find.

## 2. What the fleet actually is (measured from the repo, not from memory)

The registry names two live VPSes plus the Mac, not three VPSes; the third
box, meghadharma, is not on the bus at all.

| Host | Role | On the bus? | Cite |
|---|---|---|---|
| AGNI `157.245.193.15` | The only broker anyone reaches (`DHARMA_A2A`); AGNI Hermes bridge | Yes, hub-local | `docs/ops/FLEET_FIELD_REGISTRY.yaml:30-40,84-101` |
| rushabdev / openclaw23 | Hermes revenue seat, Telegram gateway | Yes, as a client of AGNI; **collides with AGNI Hermes on `dharma.a2a.hermes`** (FFR-D2, open) | `docs/ops/FLEET_FIELD_REGISTRY.yaml:60-68,103-122` |
| meghadharma | Codex seat, Forge Lab host | **No** (operator relay only) | `docs/ops/FLEET_FIELD_REGISTRY.yaml:161-177` |
| Operator Mac | Second, **unbridged** broker (`DHARMA_FLEET`), `hermes-m5` dock, often off | Separate island | `docs/ops/FLEET_FIELD_REGISTRY.yaml:41-45,198-222` |

Hard receipts of agents on the bus: one. AGNI Hermes replied on
`dharma.a2a.fleet` at sequence 8118692 on 2026-07-09
(`inter_agent/hermes/outbound/2026-07-09-hermes-agni-probe-reply.md:6`). Every
session-based seat (Claude Code, Codex, Devin, Perplexity) lists
`last_verified_send: never (live NATS)` and routes through you
(`docs/ops/FLEET_FIELD_REGISTRY.yaml:129-136,166-173`). The canonical
transport module still defaults to stream names that exist on no broker
(`dharma_swarm/a2a/nats_transport.py:71-74` vs the live inventory in
`docs/architecture/FLEET_COMMAND_OPERATOR_SURFACE.md:96-98`).

Presence is file modification times with a two-hour green window and no HTTP
surface (`dharma_swarm/a2a/agent_presence.py:80,98-100`); Fleet Hub, by
design, will not mark a seat "heard" without identity-bound transport
(`fleet-hub/src/hub/presence.py:13-15,88-91`), which the ACL above is what
provides. So the Roster tab cannot show a live agent until door 1 opens.

Memory: twelve or more parallel stores; the unifier is read-only
(`dharma_swarm/memory_kernel/facade.py:1-5`); the second brain, chetana, has
three importers and is graded RED (`docs/governance/REALITY_DEBT_LEDGER.md`).
The operator chat path keeps no memory across sessions
(`api/routers/chat.py:1197-1199`). This is the "eight arms and no centre"
failure from the page you sent, at a hundred times the scale.

## 3. Against the "Living Brain" page and the 2026 harness field

The page (Gabriel Judah, Two Hour CEO) is a sales guide for a paid community;
its system is one Hermes agent, one nine-folder brain, five cron jobs, one
agent per outcome, and a human who taps send. No novel technology. Its one
load-bearing rule is the one this repo lacks: **every agent reads the brain
before acting and writes back after, with no gate on the write.**

Outside sources, for calibration (URLs in the session record of 2026-09-04):

- Harness engineering consensus: a decent model with a great harness beats
  the reverse; rule files under ~60 lines, each rule earned from a failure;
  ten focused tools beat fifty (Osmani, 2026). This repo's behavioral
  contract alone is ~200 lines and the audit measures 29 lines of governance
  per line an outsider can touch (`docs/plans/PLAYING_SMALL_AUDIT_2026-08-18.md` §8).
- Anthropic's long-running harness is three artifacts: a JSON feature list,
  a progress file, one commit per session. Structured hand-offs, not gates.
- gbrain (Garry Tan): markdown in git is the system of record, the database
  only indexes it; 66 cron jobs over 155k pages. One write path.
- Hermes Agent: four memories (skills files, two tiny markdown facts files,
  SQLite full-text episodic log, context compressor), weekly curator cron;
  46k stars, MIT. Also nine CVEs in four days in May 2026 including
  unauthenticated remote code execution through its memory scanner. OpenClaw:
  42k exposed instances, hundreds of malicious registry skills. Either runs
  in a container, never on a public port, never with third-party skills.
- Multi-agent failure research: most breakages are stale shared state and
  under-specified hand-offs, not model quality; a single agent over the same
  information usually beats a delegated network without new signals.

Verdict on "use someone else's system": **adopt the harness, keep the
thesis.** Hermes seats are already in the fleet; the bus and Fleet Hub are
the organizing station the page cannot offer. What must not be rebuilt in
house is memory plumbing, messaging gateways, and gate batteries with zero
feed. What must not be given up is the Witness: receipts, calibrated
forecasts, the axioms.

## 4. What was built and proven on this branch (receipt)

Locus for every row: commit `d2b2f40447cf` + this branch's commits, host
Claude Code cloud sandbox, branch `claude/dharma-swarm-fusion-review-voer57`.

| Change | Repo | Test evidence |
|---|---|---|
| `api/routers/mission_control.py`: read-only `GET /api/mission-control/missions` and `/missions/{id}/snapshot`, behind the existing bearer middleware, reading disposable immutable copies of the owner DBs (`mission_control_mcp._ImmutableSnapshotMissionControl`) | dharma_swarm | `tests/test_api_mission_control.py` 11 passed; neighbours `tests/test_api_auth.py` + `tests/test_api_main_bootstrap.py` 53 passed; manifest-check, lint-blockers, import-provenance, module-budget all OK |
| `src/hub/mission_http_provider.py`: first real `MissionProvider`, bearer-authenticated, fail-closed, configured-only; selected by `FLEET_HUB_MISSION_PROVIDER_URL` + `_TOKEN` + `FLEET_HUB_MISSION_IDS`; bootstrap reports `mission_provider_kind` | fleet-hub | `src/tests/test_mission_http_provider.py` 30 new; suite 256 passed (was 226) |
| End-to-end: seeded owner DB → owner API on :8420 → Fleet Hub on :8444 → `/api/v1/missions`, `/snapshot`, `/needs-john`, `/bootstrap` all `available: true`; anonymous owner read 401; zero credential leakage | both | `fleet-hub/docs/FLEET_HUB_OWNER_ADAPTER_EVIDENCE.md` |
| `.agents/skills/dharma-fleet-mailbox/`: stdlib-only `mailbox.py` (whoami / send / inbox / heartbeat) plus `SKILL.md` so any Hermes, OpenClaw, Claude Code, or cron seat joins the bus through the gateway with one token | dharma_swarm | `tests/test_fleet_mailbox_skill.py` 9 passed against the real gateway router with a fake broker |

Not built, on purpose: no ACL change, no deployment, no credential minting,
no Fleet Hub command enablement. Each is an operator act or requires an
owner compare-and-swap primitive that does not exist (`fleet-hub/HANDOFF.md:31-37`).

## 5. The new repo: what is already staged

Sources agree on one target and one gate. The target is `dharma`, unnamed: a
~55k-line canon monorepo with a ~9k-line frozen-interface kernel, six
import-isolated organs, three books, three TypeScript instruments, Go
ingestors as sibling processes (`docs/plans/THE_BLUEPRINT_2026-08-29.md:224-243`).
`dharma_swarm` becomes a frozen archive; `dharma-lab` the messy chamber.

Already real as boundary-enforced code inside this trunk:

- `packages/telos-kernel/` — own package, TCB ≤5,000 lines CI-ratcheted,
  import allow-list, four dedicated CI workflows. A repo in everything but
  location. Caveat: only invariant U5 enforced, stub signer keys
  (`packages/telos-kernel/README.md`).
- `packages/titanium-verify/` — the Z3 verifier that polices it.
- `dharma_swarm/operator_core/` — identity + runtime truth, ~20 modules,
  tests; `world_identity.py` built by ONE WORLD S4.
- The constitution that crosses is two files: `dharma_swarm/dharma_kernel.py`
  and `dharma_swarm/telos_gates.py` (`THE_BLUEPRINT_2026-08-29.md:156-214`).
- House style for birthing a repo is proven twice: `fleet-hub` (clean source
  drop, 11 commits) and `AgentKanban` (clean public import, honest provenance).

The gate: no canon repo until one ring-three external receipt exists, or an
honest negative (`THE_BLUEPRINT_2026-08-29.md:265`; adversarial audit
`reports/2026-08-30_blueprint_adversarial_audit.md:167-183`). That receipt is
ONE WORLD S5, still open on two operator acts
(`docs/plans/ONE_WORLD_2026-08-30.md:48`). Decision 4, the repo's name, is
unanswered (`THE_BLUEPRINT_2026-08-29.md:352`).

Smallest unblocked first commit that makes the new repo real without
violating the gate: move `dharma_kernel.py` and `telos_gates.py` behind
`packages/telos-kernel/`'s existing allow-list and ratchet, with
`dharma_swarm/` importing them as a dependency. When S5 goes green,
`git subtree split packages/telos-kernel` is the new repo's initial commit.

## 6. Yes-sheet — each line answerable with one word

FYI lines carry no question mark and need nothing from you.

1. Apply the FFR-D1 hub ACL on AGNI per `docs/ops/A2A_LIVE_WIRE_RUNBOOK.md:16-43` so seats can DM each other and Fleet Hub can mark a seat heard. Yes or no?
2. Deploy the mailbox gateway on AGNI per `docs/ops/A2A_LIVE_WIRE_RUNBOOK.md:45-96` and mint tokens for `hermes`, `rushabdev`, `meghadharma_hermes`, `fable_claude_code`. Yes or no?
3. Set the three `FLEET_HUB_MISSION_PROVIDER_*` values in `/etc/dharma/fleet-hub.env` on AGNI against the running owner API, so the Board tab shows real missions. Yes or no?
4. Resolve FFR-D2 by giving rushabdev its own subject (`dharma.a2a.rushabdev`, already in `fleet-hub/src/roster.json`) instead of sharing `dharma.a2a.hermes`. Yes or no?
5. Land the kernel extraction (`dharma_kernel.py` + `telos_gates.py` into `packages/telos-kernel/`) as the first staged commit of the new repo, name deferred. Yes or no?
6. Name the canon repo (Blueprint Decision 4). One word, or "later".

FYI: the `fleet-advancement-2026-08` track's 14-day TTL expired on
2026-09-03 (`docs/governance/ACTIVE_TRACK.yaml:143-172`); its second blocker
item, "owner-adapters-qualified", is what section 4 advances. FYI: Fleet Hub
commands stay disabled regardless of any yes above until the owner grows an
atomic expected-version transition.
