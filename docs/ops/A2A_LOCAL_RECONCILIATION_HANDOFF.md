# A2A/NATS System — Complete Knowledge Base + Local Reconciliation Mission

> This document is self-contained. You (the local agent) have this plus your local repo. It was written by a container agent that pushed today's remote work but **cannot see your local git state** (worktrees, dirty files, local-only branches). Every file:line below was cite-checked against the repo at branch `claude/a2a-nats-review-test-ncol7c` (HEAD `d7e1fc5`) unless marked otherwise. Treat it as ground truth to **verify and extend**, not to trust blindly — re-confirm anything you act on.

---

## 0. Your mission (one paragraph, unambiguous)

Scour the operator's local machine — every git worktree, every local-only branch, all dirty/uncommitted files, the active-track declarations, and the full git history — to discover what A2A/NATS work has already been built **locally that this container never saw**, then **architect (do not execute) a reconciliation plan** that folds three sources into `origin/main`: **[A]** today's remote work on `claude/a2a-nats-review-test-ncol7c` (5 commits, HEAD `d7e1fc5`), **[B]** whatever exists only on the operator's local machine, and **[C]** what is already canonical on `origin/main`. The plan must say precisely what to merge, in what order, onto what base; what to DROP as superseded (starting with today's `coordination_substrate/**` unless a real local consumer needs it); which items require coordination with another active track's owner; and the conflict risk of each — all under a hard safety contract (no push to main, no force-push, dry-run before any destructive git op, secrets never committed). Deliver the plan as a written artifact; do not merge anything without operator sign-off.

---

## 1. The A2A/NATS system as it actually exists (the knowledge base)

### 1.1 The WIRED stack (this is production-real — do not reinvent it)

| Component | Location | What it is | Status |
|---|---|---|---|
| **A2A task lifecycle (8 states)** | `dharma_swarm/a2a/a2a_server.py:51-65` | A2A 1.0 enum: SUBMITTED, WORKING, INPUT_REQUIRED, COMPLETED, FAILED, CANCELLED, REJECTED, AUTH_REQUIRED. `terminal_states()` = {COMPLETED,FAILED,CANCELLED,REJECTED}. | REAL_WIRED |
| **A2AServer.submit() — single wired ingress** | `dharma_swarm/a2a/a2a_server.py:313` | Mints `ExecutionIdentity`, guards exactly-once via `try_begin_idempotent_side_effect_sync` (~:345), dispatches to handler, emits **exactly one** `RuntimeReceipt` (`receipt_type='a2a_task'`), appends JSONL task log. `runtime_state` optional (None ⇒ no receipt/idempotency). | REAL_WIRED |
| **A2ATask model** | `dharma_swarm/a2a/a2a_server.py:186-235` | id, context_id, from/to_agent, status, history (+`messages` back-compat alias merged in `__post_init__`), artifacts, capability, dharma_task_id, trace_id, extensions. `capability` routing is a dharma extension of spec. | REAL_WIRED |
| **A2APart (strict one-of)** | `dharma_swarm/a2a/a2a_server.py:68-136` | Types {TEXT,RAW,URL,DATA,FILE}; rejects empty content. FILE type exempt from validation (`_skip_validation` escape hatch). | REAL_PARTIAL |
| **A2AArtifact / A2AMessage / A2AExtension** | `dharma_swarm/a2a/a2a_server.py:139-183` | Deliverables vs conversation split (spec-compliant). Artifacts field exists but no handler populates it in this surface. | REAL_WIRED |
| **AgentCard model** | `dharma_swarm/a2a/agent_card.py:197-380` | A2A-1.0 card: name, agent_uid, skills (+`capabilities` alias), endpoint, security_schemes, `signatures[]`, supported_interfaces. `standardize_internal_contact()` stamps AgentUID + NATS inbox binding. | REAL_WIRED |
| **AgentSkill (AgentCapability alias)** | `dharma_swarm/a2a/agent_card.py:155-194` | id/name/desc/modes/tags; `matches(query)` case-insensitive. `AgentCapability = AgentSkill` alias at :194. | REAL_WIRED |
| **A2AInboxRoute + AgentUID** | `dharma_swarm/a2a/agent_card.py:41-120, 353-380` | Maps card name → stable AgentUID → NATS subject `dharma.agent.{uid}.inbox` (+`.ack.{id}`, `.reply.{id}`). Aliases hardcoded (codex→codex_composer, opus→opus_composer, devin→devin-roaming-2987d222, …). dharma-specific, not A2A spec. | REAL_WIRED |
| **CardRegistry** | `dharma_swarm/a2a/agent_card.py:468-651` | In-memory + JSON-on-disk (`~/.dharma/a2a/cards/<name>.json`), discovery by capability/role, `get()` resolves name → agent_uid → scan. | REAL_WIRED |
| **A2AClient.delegate / delegate_to** | `dharma_swarm/a2a/a2a_client.py:207-333` | Discover best agent → dispatch local (in-process) vs remote (httpx POST `{endpoint}/tasks`, X-A2A-Key). Remote path does **NOT** go through the spine. | REAL_WIRED |
| **A2AClient cycle + depth detection** | `dharma_swarm/a2a/a2a_client.py:141-205` | Rejects repeat (from,to,capability) within a context_id, or depth ≥ `_MAX_DELEGATION_DEPTH`(10). Only active when context_id is set. | REAL_WIRED |
| **A2ABridge.submit_via_spine** | `dharma_swarm/a2a/a2a_bridge.py:78-207` | Wraps `A2AServer.submit()` in `invoke_agent()` → one `EvidenceReceipt`. **Called ONLY from tests** — no production caller. This is the open spine-adoption blocker. | REAL_PARTIAL |
| **A2ABridge.ingest_trishula_inbox** | `dharma_swarm/a2a/a2a_bridge.py:274-320` | Production TRISHULA inbound; calls `self._server.submit()` directly (**bypasses spine**) at ~:307. Flagged in `spine_bypass_report.py`. | REAL_WIRED |
| **task_receipt ingress schema** | `dharma_swarm/a2a/task_receipt.py:33-65` | The "receipt or it didn't happen" gate. Requires `schema=='dharma_a2a_task_receipt.v1'`, non-empty claim/next_action, `verdict∈{verified,refuted,unknown}`, evidence list of `{kind∈command|path, value}`, files_changed list. | REAL_WIRED |
| **task_receipt quarantine/bounce** | `dharma_swarm/a2a/task_receipt.py:68-153` | Invalid payloads → `~/.dharma/a2a_bus/quarantine/`; `read_receipted_inbox` returns valid, quarantines rest; `bounce_payload` returns refuted essay-rejection. | REAL_WIRED |
| **A2ANatsTransport** | `dharma_swarm/a2a/nats_transport.py:90-374` | Receipted JetStream adapter. `publish_task`/`consume_message` on `dharma.a2a.task.<target>.<capability>`, stream `DHARMA_A2A`. Full idempotency **both sides**. **Fully built + tested but NO production caller instantiates it** — only `tests/test_nats_transport.py`. | **REAL_PARTIAL** |
| **NodeGateway (HTTP transport)** | `dharma_swarm/a2a/node_gateway.py:83` | FastAPI router (`/.well-known/agent-card.json`, `/tasks`, `/health`, `/skills`). **`init_gateway()` never called in `api/main.py` lifespan** ⇒ singletons stay None ⇒ task/skills endpoints return 503 in prod. | REAL_PARTIAL |
| **NodeRegistry** | `dharma_swarm/a2a/node_registry.py:103` | Fleet node directory; single `~/.dharma/a2a/nodes.json`. Populated only via REST `POST /api/fleet/nodes`. **Writes `api_key` cleartext at rest** (`_persist` uses `asdict()`; `to_dict()` redaction not used on disk). | REAL_WIRED |
| **registry_hydrator.hydrate_from_receipts** | `dharma_swarm/a2a/registry_hydrator.py:79` | Bridges onboarding receipts + CardRegistry → NodeRegistry. **No production caller** — tests only. | REAL_PARTIAL |
| **agent_presence.list_agent_presence** | `dharma_swarm/a2a/agent_presence.py:42` | Read-only projection; GREEN/RED off a flat 2-hour heartbeat-age threshold. Consumed by `orientation_graph.py:781` (`make orient`). | REAL_WIRED |
| **IdempotencyRecord (exactly-once substrate)** | `dharma_swarm/runtime_state.py:659` (class); DDL `:251-265`; `try_begin` `:3182`/`:3240` (sync); `complete` `:3299`/`:3340` | **The true write-boundary CAS.** `PRIMARY KEY (idempotency_key, side_effect_key)` (confirmed at `:264`) makes `INSERT OR IGNORE … rowcount==1` an atomic first-writer-wins. Wired at `a2a_server.submit`, `nats_transport.publish_task`, `nats_transport.consume_message`. | REAL_WIRED |
| **spine warrant fails closed on idempotency** | `dharma_swarm/spine/warrant.py:181,252,262,273` | `issue_runtime_warrant` requires `idempotency_inserted==True` + matching IdempotencyRecord before granting. The spine **consumes** IdempotencyRecord — it does NOT mint a competing store. | REAL_WIRED |
| **single-persistence invariant** | `dharma_swarm/spine/persistence.py:50-75` | Orchestrator surface writes `delegation_runs.receipt_json`; A2A surface persists canonically via RuntimeReceipt+IdempotencyRecord and leaves `receipt_json` empty. This is the "do not mint a second RuntimeReceipt for A2A" guard. | REAL_WIRED |
| **pr_merge_control.build_gate** | `scripts/runtime/pr_merge_control.py:1128-1298` | 10+ deterministic merge blockers (draft, mergeable, failing/pending checks, CHANGES_REQUESTED, missing Coherence Delta, unresolved threads, required-reviewer receipts, HIGH/CRITICAL risk). Emits `dharma.pr_review.merge_gate.v1`. | REAL_WIRED |
| **merge = git-ref CAS** | `scripts/runtime/pr_merge_control.py:1448-1476` | `gh pr merge <n> --squash --delete-branch --match-head-commit <gate.head_sha>` — GitHub refuses if head SHA moved (cross-process compare-and-set). Emits `mike_merge_receipt.v1`. | REAL_WIRED |
| **native-review→receipt bridge (Slice 1)** | `scripts/runtime/pr_merge_control.py:881-1008` | Trusted-App native reviews count as receipts: codex=`chatgpt-codex-connector[bot]`, copilot=`copilot-pull-request-reviewer[bot]` (EXACT login incl `[bot]`). Additive-only, never overrides a present local receipt, stale-head rejected. **Live in cloud**: `codex-mention-router.yml` sets `DHARMA_PR_ACCEPT_GITHUB_REVIEWS=true`. | REAL_WIRED |

**The A2A idempotency contract, in one line:** every A2A side-effect (submit, NATS publish, NATS consume) pairs `try_begin_idempotent_side_effect` with `complete_idempotent_side_effect` on a `side_effect_key` and emits exactly one `RuntimeReceipt`; a duplicate short-circuits without re-doing the effect. Tested in `tests/test_nats_transport.py` and `tests/test_a2a_send.py`.

### 1.2 NATS / broker facts

| Fact | Detail |
|---|---|
| **AGNI shared broker** | `wss://157.245.193.15:8443`, users `trishula`/`devin`/`mike`, CA `dharma_swarm/a2a/nats/agni-ws-ca.pem` (CN `agni-dharma-nats`, valid 2026-05-31…2028-09-02), stream `DHARMA_A2A`. |
| **Reachability** | Sandbox/container has **NO egress** to AGNI. Only a **GitHub Actions runner** (`.github/workflows/a2a-agni-live-contact.yml`, merged as PR #729) reaches it. Local machine may or may not — verify. |
| **Two-broker split** | Local fleet hub `DHARMA_FLEET` mirrored to AGNI `DHARMA_A2A`. Split is **real in ops docs + env** (`docs/ops/DEVIN_NATS_PR_JANITOR_PLAYBOOK.md`); **no Python code configures the mirror** — it is broker/ops-side. `nats_transport.py` defaults to **loopback** `nats://127.0.0.1:4222` (confirmed `:56`), not AGNI. |
| **Subjects (from `NATS_SUBSTRATE_MASTER_SPEC.md`)** | `dharma.fleet.*`, `dharma.agent.<uid>.inbox/outbox`, `dharma.a2a.task.*`, `dharma.a2a.receipt`, `dharma.operator.hot_contact`. `A2ANatsTransport` uses `dharma.a2a.task.<agent>.<capability>` (subject_prefix `dharma.a2a`, stream `DHARMA_A2A` — confirmed `:57-58`). |
| **`a2a_send.py` envelope** (the actual live send agents use) | `scripts/runtime/a2a_send.py:95-357` — `dharma.a2a.send.v1` envelope to `dharma.a2a.<agent>`; ack/reply on `.ack.<id>`/`.reply.<id>` core-NATS subs. **Separate protocol** from `A2ANatsTransport` (does NOT use it). Ack tiers: `PUBLISH_ACKED` / `<AGENT>_CONSUMED` / `<AGENT>_REPLIED`. Receipts under `reports/a2a/send_receipts/` (gitignored). |
| **Ack-tier ladder (honesty doctrine)** | `PUBLISH_ACCEPTED < DELIVERED_TO_CONSUMER < HANDLER_ACKED < DOMAIN_RECEIPTED`. A bare open TCP port is **never** liveness. `live_contact_claim=True` only at HANDLER_ACK. |
| **Server-side per-key TTL (NATS 2.11, ADR-48)** | `Nats-TTL` header. **NOT USED by any transport in this repo** — `nats_transport.py` sets no `Nats-TTL`. Gotchas to remember: (1) stream `MaxAge` takes precedence over per-key TTL; (2) updating a key's value before TTL does **NOT** reset the TTL (nats-server issue #6959). Only discussed (not used) in the superseded KV lease docstring. |
| **Durable consumer / DLQ / MaxDeliver / AckWait / backoff** | **NONE implemented in `nats_transport.py`.** `consume_message` operates on an already-delivered message; it creates no stream, no durable, no DLQ. Durable consumers (`devin_inbox`, `perplexity_inbox`) exist only in the AGNI workflow + agent daemon scripts. Stream retention is a recommend-only doc (`docs/plans/2026-06-11-dharma-a2a-stream-retention-proposal.md`). |
| **Operator NATS trio (the wired live-contact/verify/project path)** | `operator_core/nats_live_contact.py:43-159` (honest JetStream round-trip, ephemeral MEMORY probe stream, TCP pre-gate), `nats_substrate_status.py:45-154` (claim-safe status), `ingest_nats.py:30-227` (receipt→NATS hot projection, gated on `DHARMA_INGEST_NATS=1` + ack proof). |
| **Governance gate** | `make nats-substrate-contract` → `scripts/governance/check_nats_substrate_contract.py:30-113` (asserts spec doctrine phrases, honest-status markers, probes an unreachable endpoint to prove `ack_verified` stays False). Included in `make governance-all` (`Makefile:386`). |

### 1.3 Identity / presence / registry — what enforcement is MISSING

| Missing enforcement | Location | Reality |
|---|---|---|
| **JWS card signatures** | `dharma_swarm/a2a/agent_card.py:233` | `signatures: list[str]` field exists; **ZERO signing/verification code anywhere in `a2a/`**. Any card on disk is trusted unconditionally. `node_gateway.py:53` docstring lists it as "declared but not yet enforced (Tier 2)". This is the one flagged TODO. |
| **OAuth2 / HTTPAuth / mTLS / OpenIdConnect** | `SecurityScheme` `dharma_swarm/a2a/agent_card.py:129-152` | Card metadata that **advertises but does not enforce** (docstring is explicit). |
| **Only enforced auth** | `node_gateway._verify_api_key` `dharma_swarm/a2a/node_gateway.py:143` | `X-A2A-Key` vs `~/.dharma/a2a/allowed_keys.json`. Empty keyset ⇒ 403 deny-all (safe default). Localhost bypass only if `A2A_ALLOW_LOCAL_NOAUTH=1`. Plaintext `in`-comparison (not constant-time). |
| **Two declared-but-absent modules** | `dharma_swarm/a2a/a2a_nats_contact.py`, `a2a_core_contact.py` | **DO NOT EXIST** on this branch or `origin/main` (verified: `ls` returns "No such file or directory"; zero refs in any `.py`/`.md`). CLAUDE.md/ACTIVE_TRACK.yaml name them as owned surfaces of `runtime-truth-nats-2026-06`. **A merge plan MUST NOT assume they exist.** The track's real live code lives in `operator_core/nats_live_contact.py` + `scripts/runtime/a2a_send.py` + `scripts/runtime/devin_a2a_agent.py`. |

**Data-cold note:** in the container environment only `~/.dharma/a2a/task_log.jsonl` existed; `cards/`, `nodes.json`, `allowed_keys.json`, `a2a_bus/`, `agents/`, `onboarding/` were absent. **Your local machine likely has real data here — inspect it (§4).**

---

## 2. What I (the remote agent) did today, and the honest verdict

**Branch:** `claude/a2a-nats-review-test-ncol7c` · **HEAD:** `d7e1fc5`. Five commits (oldest→newest, verified via `git log`):

| SHA | Subject |
|---|---|
| `81871f7` | feat(coordination-substrate): A2A anti-sprawl substrate spec + lease/fencing primitive |
| `6c92d1e` | feat(coordination-substrate): real distributed NATS-KV lease store, adversarially verified |
| `42297ed` | docs(coordination-substrate): adversarial validation evidence + clock-skew finding |
| `01b85a5` | docs(coordination-substrate): expert-panel verdict — deflate overclaims, mark DORMANT |
| `d7e1fc5` | docs(coordination-substrate): SUPERSEDED — the corrected summit already exists, wired |

**Files touched today:**
- `dharma_swarm/coordination_substrate/{leases.py, nats_kv_leases.py, __init__.py}` — **NOW MARKED SUPERSEDED**
- `tests/test_coordination_substrate.py` (13 tests, in-memory), `tests/test_coordination_substrate_live.py` (4 live tests, skip without broker)
- `docs/architecture/A2A_COORDINATION_SUBSTRATE.md` (spec; §7 deflated smoke evidence; §8 = expert verdict; §8.6 = SUPERSEDED file:line signpost)
- `scripts/governance/pramana_probe.py` + `tests/test_pramana_probe.py` (tiered verification conductor; arthapatti blocking floor)
- `dharma_swarm/native_substrate/*` + `native/dharma_kernels/*` (canalization ratchet; ed25519 + Rust cdylib)
- `.github/workflows/a2a-agni-live-contact.yml` (merged separately as PR #729)

### THE HONEST VERDICT (verified against code this session)

**`dharma_swarm/coordination_substrate/**` is SUPERSEDED — a parallel reinvention. Do NOT wire it into production.**

Verified facts backing the verdict:
- **Zero production importers.** `grep` for `coordination_substrate | LeaseManager | NatsKvLeaseStore | InMemoryLeaseStore | validate_fencing_at_merge` across `dharma_swarm/ scripts/ api/` (excluding the package itself) returned **empty**. Only its own 3 files + 2 test files + the design doc reference it.
- **`validate_fencing_at_merge` (the only thing making leases Kleppmann-correct) has ZERO callers** — `leases.py:215`, `nats_kv_leases.py:197` definitions + tests only.
- **Self-declared defects** (in `nats_kv_leases.py:18-29` docstring): fence token is bucket-**global** not per-surface (violates Kleppmann fence); default bucket has no fsync-before-ack/replicas≥3 → Jepsen NATS 2.12.1 split-brain; TTL is Python `now`-vs-`acquired_at`, **not** broker-enforced. `history=8` is wrong-for-a-lock.
- **Not exported** from `coordination_substrate/__init__.py` (only in-memory leases are).
- The one non-redundant idea (surface mutual exclusion) is already covered **for the only write that matters** by git three-way merge + `pr_merge_control.py` + `runtime_state.IdempotencyRecord`.

**KEEPERS from today (the only artifacts worth landing):**
1. **`docs/architecture/A2A_COORDINATION_SUBSTRATE.md`** — especially **§8** (expert-panel verdict) and **§8.6** (SUPERSEDED file:line equivalence map pointing every "corrected summit" capability back to its already-wired `a2a/`+`runtime_state.py` owner). This doc is the anti-sprawl signpost; its doctrine line is *"scan `a2a/` and `runtime_state.py` before writing new coordination code."*
2. **`scripts/governance/pramana_probe.py` + `tests/test_pramana_probe.py`** — tiered verification conductor (evidence tiers VERIFIED/SUPPORTED/WEAK/REFUTED; arthapatti blocking floor; receipt `dharma.pramana_probe.receipt.v1` as a projection, not authority). Non-redundant. **Orphaned** — no track owns `scripts/governance/pramana_probe.py`; assign an owner or land under an existing governance track.

The `native_substrate/*` + `native/dharma_kernels/*` work is out-of-scope for A2A/NATS reconciliation — evaluate it separately, do not bundle it into this plan.

---

## 3. The sprawl + ownership boundaries you MUST respect

### 3.1 Sprawl reality (from GitHub + PR #737 ledger, 2026-07-01)

- **~567 branches total** (~295 remote heads); PR #737 metabolization ledger: **252 flagged_for_operator**, 20 pr_opened, 13 archived, 592 keep_active, 49 worktrees.
- **Stalled DRAFT PR cluster** (merge bottleneck): #742, #740, #739, #738 (non-draft), #737, #736, #734, #732, #723, #719, #718, #704. Several committed with `--no-verify` because pre-existing gates crash (`check_shakti_warrant.py` ModuleNotFoundError, Py3.9 typing crash in assurance-diff, spine-ownership dataclass-slots failure). **Gate infra is partially broken** — do not assume green CI equals healthy.

### 3.2 In-flight A2A/NATS branches/PRs (duplicate-work + rebase hazards)

| Ref / PR | What it is | Hazard |
|---|---|---|
| **PR #739** (`codex/runtime-truth-nats-live-evidence-20260701`, sha `ca297f5`) | **The live `A2ANatsTransport` hardening lane** — schema/identity/idempotency/ack-nack/redelivery/MaxDeliver/DLQ; adds `run_nats_live_production_matrix.py` + `check_nats_live_production_evidence.py`. Serves `runtime-truth-nats`. | **Based off `agent/magpie-seed`, NOT main** — rebase hazard. Committed `--no-verify`. Touches `nats_transport.py` (the orphaned hot surface). |
| **`agent/magpie-seed`** (sha `b6e6ae8`) | Base branch under #739; carries seed A2A-NATS work. | **~27 ahead / ~308 behind origin/main** — heavily drifted. Any plan must rebase #739 onto current main, not trust this base. |
| **`codex/runtime-convergence-hardening`** (sha `4f38296`) | Runtime-convergence lane in the codex family. | No open PR; likely stalled/superseded by #739. Duplicate-work signal. |
| **PR #738** (`claude/repo-implementation-planning-u3cayh`) | Agentic Design Patterns atlas. **Not A2A** but a named duplicate signal (same book atlas'd elsewhere). | Sprawl signal only. |
| **PR #737** (`codex/metabolization-ledger-20260701`, DRAFT) | The sprawl census itself + fixes an `orchestrator.py` failure-ledger race. | **Touches `orchestrator.py`** (spine-adoption owned surface) — overlap risk. |

Other A2A/NATS-tagged remote branches to look for: `codex/runtime-truth-spine-v1`, `codex/a2a-active-track-20260613`, `feat/a2a-correlation-spine-phase2a`, `mmm-a2a-conditional-merge`, `devin/*-a2a-*` (×4), `perplexity-computer/a2a-activation-*`, `preserve/runtime-truth-nats-rebuild-preflight`.

### 3.3 ACTIVE-track owned surfaces — the DO-NOT-STOMP map

`docs/governance/ACTIVE_TRACK.yaml` declares 11 ACTIVE tracks (all serving `substrate-nativeness`; warn ceiling 5 exceeded). Four own A2A/NATS/merge surfaces:

| Track (owner) | Owned surfaces you must NOT stomp | Notes |
|---|---|---|
| **runtime-truth-nats-2026-06** (@codex) | `docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md`, `a2a/a2a_nats_contact.py`, `a2a/a2a_core_contact.py` | The two modules **don't exist** (§1.3). Spec exists. `verified_at 2026-06-07`, TTL 21 ⇒ **STALE**. PR #739 is this track's live lane. |
| **truth-graph-platform-2026-06** (@codex) | `a2a/task_receipt.py`, `a2a/agent_presence.py`, `tests/test_a2a_gate.py`, `tests/test_agent_registry_presence.py`, `orientation_graph.py`, `reports/orientation/**` | Fresh (`verified_at 2026-06-23`). Both modules present + wired. |
| **runtime-truth-spine-adoption-2026-06** | `dharma_swarm/spine/**`, `a2a/a2a_bridge.py`, `orchestrator.py`, `agent_runner.py`, `check_spine_ownership.py` | **4 OPEN blockers** (submit_via_spine bypass at `a2a_bridge.py:307`, etc.). Any A2A merge touching `a2a_bridge.py`/`orchestrator.py` collides here. |
| **merge-master-mike-d4-2026-06** | `scripts/runtime/pr_merge_control.py`, `merge_master_mike_daemon.py`, `.github/workflows/{automerge,codex-mention-router,merge-master-mike-backlog}.yml`, `tests/test_pr_merge_control_github_reviews.py` | Fresh; production-active gate. |

**Orphaned surfaces (no track owns them) — hot and dangerous:**
- `dharma_swarm/a2a/nats_transport.py` — the **actual wired transport**, not in any `owned_surfaces` list, actively hardened by #739. Highest merge-conflict risk.
- `scripts/governance/pramana_probe.py` — today's keeper conductor.
- `docs/architecture/A2A_COORDINATION_SUBSTRATE.md`, `tests/test_coordination_substrate*.py` — today's off-portfolio work.

---

## 4. Your concrete tasks (numbered, exact commands)

Run all of these from the repo root. **Read-only discovery first — do nothing destructive in this section.**

### Task 1 — Snapshot local git reality
```bash
# 1a. Where are the worktrees?
git worktree list

# 1b. All local branches with upstream + ahead/behind
git branch -vv

# 1c. Every local ref with ahead/behind vs origin/main (fetch first)
git fetch origin --prune
git for-each-ref --format='%(refname:short) %(upstream:short) [ahead %(ahead) behind %(behind)]' refs/heads/ 2>/dev/null || \
  for b in $(git for-each-ref --format='%(refname:short)' refs/heads/); do \
    echo "$b: $(git rev-list --left-right --count origin/main...$b)"; done

# 1d. Dirty / uncommitted state in the current tree
git status --porcelain=v1 --branch

# 1e. Any stashes
git stash list
```

### Task 2 — Find A2A/NATS work in local history that the container never saw
```bash
# 2a. Commits touching A2A/NATS/coordination on ANY local ref, not on origin/main
git log --oneline --all --not origin/main -- \
  dharma_swarm/a2a/ dharma_swarm/coordination_substrate/ \
  dharma_swarm/operator_core/nats_*.py scripts/runtime/a2a_send.py \
  docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md

# 2b. Local-only A2A modules NOT present on origin/main (use Glob/Grep tools, not find):
#     - list local a2a/ files, then diff against the tree on origin/main
git ls-tree -r --name-only origin/main -- dharma_swarm/a2a/ > /tmp/main_a2a.txt
git ls-tree -r --name-only HEAD        -- dharma_swarm/a2a/ > /tmp/head_a2a.txt
diff /tmp/main_a2a.txt /tmp/head_a2a.txt   # lines with '>' = local-only

# 2c. Confirm the two declared-only modules are still absent locally
ls dharma_swarm/a2a/a2a_nats_contact.py dharma_swarm/a2a/a2a_core_contact.py 2>&1
```
> Use the **Grep/Glob tools** (not `find`/`grep` in Bash) to hunt for local-only A2A modules, e.g. Glob `dharma_swarm/a2a/**` and Grep for `A2ANatsTransport`, `coordination_substrate`, `LeaseManager` to see whether any **local consumer** imports the superseded package (which would change the drop decision).

### Task 3 — Inspect the local `~/.dharma` A2A state (data the container lacked)
```bash
ls -la ~/.dharma/a2a/ 2>&1
ls -la ~/.dharma/a2a/cards/ ~/.dharma/a2a_bus/ ~/.dharma/agents/ ~/.dharma/onboarding/ 2>&1
# NEVER print secrets. If ~/.dharma/a2a/nodes.json or allowed_keys.json exist,
# note their PRESENCE only — do not paste contents into any artifact or commit.
```

### Task 4 — Read the governance ground truth locally
```bash
# Active tracks + owned surfaces (the DO-NOT-STOMP map)
sed -n '1,60p' docs/governance/ACTIVE_TRACK.yaml   # header + WIP limits
# then read the four A2A/NATS track blocks (search for the track ids in §3.3)
make onboard        # renders live track/ops/broken state — trust this over any doc
```

### Task 5 — Reconcile against remote in-flight lanes
```bash
gh pr list --state open --limit 50
gh pr view 739 --json headRefName,baseRefName,mergeable,isDraft,files
gh pr view 737 --json headRefName,baseRefName,files   # touches orchestrator.py
# Confirm PR #739's base is agent/magpie-seed and quantify its drift:
git rev-list --left-right --count origin/main...origin/agent/magpie-seed 2>/dev/null || \
  echo "magpie-seed not fetched — git fetch origin agent/magpie-seed first"
```

### Task 6 — Classify every local branch/worktree
For each local ref from Task 1, assign exactly one label and record the evidence:

| Label | Test |
|---|---|
| **merged** | `git rev-list --left-right --count origin/main...<branch>` shows 0 ahead (fully in main). |
| **unmerged-valuable** | Ahead of main with A2A/NATS commits **not** duplicated on `claude/a2a-nats-review-test-ncol7c`, #739, or #737. |
| **duplicate-of-remote** | Its diff overlaps #739 (nats_transport hardening), today's `coordination_substrate`, or #738. |
| **superseded** | Reinvents the wired `a2a/`+`runtime_state.IdempotencyRecord` stack, or is the `coordination_substrate` lane. |
| **abandoned** | Stale (weeks behind), no unique A2A/NATS value, no open PR. |

### Task 7 — Three-way overlap detection ([A] remote-today × [B] local-only × [C] main)
```bash
# For each local-only A2A/NATS file or commit, check whether the same path/idea
# already lands on origin/main OR on the remote branch:
git diff --stat origin/main..HEAD -- dharma_swarm/a2a/ dharma_swarm/coordination_substrate/
# Compare a local candidate branch against both anchors:
git diff --stat origin/main..<local-branch> -- dharma_swarm/a2a/
git diff --stat HEAD..<local-branch>        -- dharma_swarm/a2a/
```
Flag as **conflict-risk HIGH** any local edit to `nats_transport.py` (collides with #739), `a2a_bridge.py`/`orchestrator.py` (collides with spine-adoption / #737), `pr_merge_control.py` (collides with Mike-D4), or `task_receipt.py`/`agent_presence.py` (collides with truth-graph).

---

## 5. The reconciliation plan you must PRODUCE (deliverable format)

Produce a written plan (an artifact for the operator — put it under `docs/` or `reports/`, **never root**, or return it as text). It must contain all of the following.

### 5.1 Disposition table — every source item, one row
| Item (branch / PR / local file / today's commit) | Source [A/B/C] | Classification (§6) | Action: MERGE / REBASE / DROP / COORDINATE / HOLD | Onto what base | Owning track (if any) | Conflict risk | Evidence (file:line or git output) |
|---|---|---|---|---|---|---|---|

### 5.2 Merge/rebase order (dependency-aware)
1. Land **keepers from today first** if clean: the doc `A2A_COORDINATION_SUBSTRATE.md` (§8/§8.6 signpost) and `pramana_probe.py`+test — on a **fresh branch off current `origin/main`**, with an owning track assigned (governance track for `pramana_probe`). These carry the anti-sprawl doctrine and have no surface collisions.
2. Coordinate with **@codex** before touching `nats_transport.py` — PR #739 is the live owner-adjacent lane. Prefer **rebasing #739 onto current main** over any parallel edit. Do not open a competing transport PR.
3. Sequence **local `unmerged-valuable`** items after #739 lands, rebased onto the post-#739 main, so the hardened transport is the base.
4. Anything touching `a2a_bridge.py`, `orchestrator.py`, `pr_merge_control.py`, `task_receipt.py`, `agent_presence.py` → **COORDINATE** with the owning track (§3.3); do not merge unilaterally.

### 5.3 Explicit DROP list (today's remote commits — keep vs drop)
| Commit | Keep or Drop | Reason |
|---|---|---|
| `81871f7` (spec + lease primitive) | **Keep doc, drop code** | Keep `A2A_COORDINATION_SUBSTRATE.md`; drop `coordination_substrate/leases.py` (SUPERSEDED, 0 callers). |
| `6c92d1e` (NATS-KV lease store) | **DROP** | `nats_kv_leases.py` — self-declared defective, 0 production callers, redundant vs IdempotencyRecord. |
| `42297ed` (adversarial evidence) | **Keep** (folds into §7 of the doc) | Honest clock-skew finding is load-bearing context. |
| `01b85a5` (deflate/DORMANT verdict) | **Keep** | The §8 verdict is the keeper doctrine. |
| `d7e1fc5` (SUPERSEDED signpost) | **Keep** | §8.6 file:line equivalence map — the anti-sprawl payload. |

> **Recommended concrete shape:** land the doc + `pramana_probe` on a clean branch; leave `coordination_substrate/**` + its two test files **either dormant** (unmerged, documented as reference in the doc) **or deleted** — decide based on Task 2b (does any *local* consumer import it? If yes, that consumer is itself likely superseded — flag it, don't wire it). Never wire `coordination_substrate` into production.

### 5.4 Coordination-required list
List each item that needs an owner's sign-off, with the owner handle and the specific surface. At minimum: `nats_transport.py` (@codex / runtime-truth-nats), any `a2a_bridge.py`/`orchestrator.py` edit (spine-adoption), any `pr_merge_control.py` edit (Mike-D4).

### 5.5 Safety contract (must appear verbatim in the deliverable)
- Dry-run every git operation first (`git merge --no-commit --no-ff`, `git rebase --dry-run`-equivalent via a scratch branch, `git cherry-pick -n`).
- **No force-push. No push to `main`.** All work on its own branch off current `origin/main`.
- Secrets never committed (`~/.dharma/a2a/allowed_keys.json`, `nodes.json` api_keys, `DEVIN_NATS_*`, `MERGE_MASTER_MIKE_NATS_*`, AGNI creds).
- Do not stomp another active track's owned_surfaces; coordinate on shared/orphaned-but-hot surfaces.
- Runtime receipts stay under `~/.dharma/`, never git.

---

## 6. Hard constraints (verbatim — non-negotiable)

- **NEVER commit secrets, credentials, or `.env` files.** This includes AGNI/NATS creds (`DEVIN_NATS_*`, `MERGE_MASTER_MIKE_NATS_*`), `~/.dharma/a2a/allowed_keys.json`, and any `api_key` inside `~/.dharma/a2a/nodes.json`. Do not paste their contents into any artifact.
- **NEVER push to `main`.** Never force-push any branch.
- **All work goes on its own branch** created off current `origin/main` (after `git fetch origin`).
- **Dry-run before any destructive git op** (merge/rebase/cherry-pick/branch-delete/worktree-remove). Compost branch lists to `~/.claude/cabinet/_compost/` before removing any worktree.
- **Do not stomp another active track's `owned_surfaces`** (§3.3). Where a surface is shared or orphaned-but-hot (`nats_transport.py`, `a2a_bridge.py`, `orchestrator.py`, `pr_merge_control.py`, `task_receipt.py`, `agent_presence.py`), **coordinate with the owner** (`@codex` for the NATS/truth-graph lanes) before editing — do not open a competing PR.
- **Runtime receipts go under `~/.dharma/`, never into git** (`reports/a2a/*_receipts/`, `reports/model_*/e2e/`, `reports/model_pool/` are gitignored loop artifacts).
- **Do not wire `coordination_substrate/**` into production** under any circumstance — it is SUPERSEDED with zero production callers; keep dormant or delete only.
- **Before opening any PR that closes/demotes/adds a BR-id**, run `gh pr list --state open --search "BR-NNN"` for each cited id and coordinate on collisions.

---

*End of handoff. Everything above was cite-checked against the repo at `claude/a2a-nats-review-test-ncol7c` HEAD `d7e1fc5`; re-verify each file:line locally before you act on it, and trust `make onboard` over any frozen doc where they disagree.*