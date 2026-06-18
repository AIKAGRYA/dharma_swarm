# LIVE OPS DASHBOARD — Morning Brief

**Path:** `docs/state/LIVE_OPS_DASHBOARD.md`
**Snapshot date:** 2026-06-14
**Status:** CURRENT — refreshed to main at `9c76b21` (799 commits, +97 since 2026-05-29 snapshot)
**Read first if tired:** this is the place to learn what shipped, where the live swarm is running, and what not to rediscover tomorrow.

The previous 2026-05-29 dashboard was archived to `docs/state/_archive/LIVE_OPS_DASHBOARD_2026-05-29.md`.

---

## What This Is

This file is the morning briefing for agents.

It is not a feature spec and not a final architecture document. It is the current operational truth: what is on `main`, what the live runtime is actually running, what was merged, and what remains unsafe or unfinished.

It is the **State** layer of the Three-Layer SSoT model declared in `docs/governance/ACTIVE_TRACK.yaml`:

| Layer | File | Job |
|---|---|---|
| Intent | `docs/governance/ACTIVE_TRACK.yaml` | What we are working on now (portfolio of active tracks) |
| Surface | `ACTIVE_SURFACE_MANIFEST.yaml` | What exists in the codebase (machine-readable surface map) |
| State | `docs/state/LIVE_OPS_DASHBOARD.md` (this file) | What is live now; plain-language operator handoff |

The Intent layer is authoritative for the active-track list. This dashboard is the human handoff that explains the current operational situation — counts, recent merges, broken register, what to do next.

## Biggest So What

Two large shifts since the last snapshot:

1. **`runtime-truth-spine-2026-06` was closed 2026-06-04** with all 13 string-presence completion criteria met. It was superseded by `runtime-truth-reconciliation-2026-06` (move from substrate existence to read-only runtime truth reconciliation). The closure is recorded in `docs/governance/ACTIVE_TRACK.yaml` under `closed_tracks`.
2. **The track model went multi-track** (`ACTIVE_TRACK.yaml` schema v2 via PR #555). The portfolio is now 1..N co-equal active tracks under a WIP limit, not a single privileged slot. Six tracks are currently ACTIVE; one is SHIPPABLE (criteria met, awaiting closure).

Two large structural rescue PRs landed this cycle:

- **PR #585** — production-tree rescue / one main / holon spine v1 + multi-lane rescue (the big consolidation merge).
- **PR #574** — Qwen/spine adoption (integration lane: spine adoption, chetana, security rounds 1–4, provider+status work).

Together they re-grounded `main` after a multi-lane drift period. They also tripped most of the rebase conflicts seen in older open PRs.

**Operator decision needed:** review the inbound bugs/cleanup/anti-slop wave (PRs #592, #597, #598) before the corral lands as live debt. See section 5.

---

## 1. Main / CI

**Current main:** `9c76b21` ("Merge pull request #585 from AmitabhainArunachala/holon/spine-v1")
**Total commits:** 799 (+97 since 2026-05-29)
**Latest main CI:** green (per recent merge history)

| Workflow | Notes |
|---|---|
| pytest (3.11, 3.12) | gating |
| semgrep | gating; ruleset under `.semgrep/dharma-anti-slop.yml` |
| CodeQL | gating |
| gitleaks | gating |
| DocOps integrity | gating |
| go-adapter-contracts | gating |
| go-evidence-ingestor | gating |
| governance-all | new umbrella; runs semgrep+gitleaks+test-hygiene+test-contracts+nats-substrate-contract+uplift-guards+module-budget+docops-integrity |

`make help` is now the authoritative target list — README's hand-maintained list drifted (AS-06; fix proposed in PR #597).

---

## 2. Active Tracks (Intent layer reconciliation)

Six tracks currently ACTIVE per `docs/governance/ACTIVE_TRACK.yaml`. All serve `substrate-nativeness` (the primary spine objective from `SOVEREIGN_MANIFEST.md`).

| Track | Status | Notes |
|---|---|---|
| `runtime-truth-reconciliation-2026-06` | SHIPPABLE | All completion criteria met; awaiting close. Successor to the closed Runtime Truth Spine. |
| `runtime-truth-nats-2026-06` | SHIPPABLE | NATS transport for runtime truth; PR #514 landed. |
| `runtime-truth-spine-adoption-2026-06` | ACTIVE (7/8) | Blocker: 5 intentional bypass sites allowlisted in `scripts/governance/spine_bypass_report.py:46-67`. PR #557 (orchestrator dispatch through `invoke_agent` behind default-OFF flag) landed. |
| `loop-closure-2026-06` | ACTIVE (3/5) | Phase 0 dossier landed in PR #575. Provider hardening (#577) is a Phase 1a deliverable. |
| `orientation-graph-2026-06` | SHIPPABLE | Onboard / WHY-section / orientation served on first token (PR #573). |
| `composer-holon-spine-longrun-2026-06` | ACTIVE | Long-run composer + holon spine track. |

For acceptance criteria, evidence pointers, and TTL on each, see `docs/governance/ACTIVE_TRACK.yaml` and `make onboard`.

---

## 3. What Shipped Since Last Dashboard (2026-05-29)

Selected high-signal merges to `main`:

| PR | What |
|---|---|
| #585 | **Production-tree rescue → one main** (holon spine v1 + multi-lane rescue) |
| #584 | Auto-enroll bot/automated PRs in automerge lane and dedupe draft duplicates |
| #579 | Make Coherence Delta gate malleable in form, strict in substance |
| #577 | Providers: separate rate-limit / quota / billing failure classes + fix dead fast-trip (loop-closure Phase 1a) |
| #575 | Loop-closure Phase 0 Research Dossier + `loop-closure-2026-06` track |
| #574 | Qwen/spine adoption integration lane |
| #573 | Orientation served on token one; venv-aware Makefile |
| #570 | NORTH_STAR v2 — locked-in operator vision (lattice of loops, trust gate, canon-metabolism rule) |
| #568 | DHARMA_A2A retention proposal + outbound A2A reply packet |
| #567 | `make pr-mike` and `mike-*` targets advertised in PR_REVIEW_CONTROL.md |
| #566 | `a2a_send.py` — one-command operator surface to send a packet |
| #563 | Onboard single-door v2 |
| #561 | Providers never collapse reasoning-only responses to empty string |
| #557 | Spine: route orchestrator dispatch through `invoke_agent` behind default-OFF flag |
| #556 | Evolution: single-writer flock on `archive.py` append (WS2) |
| #555 | **`ACTIVE_TRACK` v2 — single-track → multi-track portfolio** |
| #551 | Hygiene lifecycle + AI-agent guardrails |
| #550 | 60-question vibe-code audit report + anti-slop rules addendum |
| #549 | Canonical vibe-code hygiene catalogue + scan + onboard wire-in |
| #545 | Metabolize unreferenced raw outputs + hyperfile runtime state (−27 MB) |
| #544 | MMM merge authority charter — closes A3 seam |
| #543 | Throttle PRs by intent (`headRef`), not author |
| #542 | `ontology_action_tollbooth` → joined (slice 1 of #539) |
| #514 | Runtime-truth NATS transport |
| #490 | Self-healing DocOps count auto-refresh feeder |
| #489 | CI truth gate for Mike |
| #487 | Operator-core runtime truth projector |

---

## 4. Repo Counts (do not hand-maintain)

From `docs/docops/AUTO_INVENTORY.md` (sourced via `make docops-report`, validated by `make docops-integrity`):

| Metric | 2026-05-29 | 2026-06-14 | Delta |
|---|---:|---:|---:|
| Dharma Python modules | 674 | 739 | +65 |
| Top-level Dharma modules | 391 | 399 | +8 |
| Dharma Python LOC | 279,695 | 305,811 | +26,116 |
| Test files | 617 | 702 | +85 |
| Test function occurrences | 10,734 | 11,512 | +778 |
| Markdown files | 757 | 1,011 | +254 |
| Markdown total lines | 190,990 | 239,173 | +48,183 |
| Total commits | 702 | 799 | +97 |

The markdown explosion (+254 files / +48k lines) is mostly governance docs from the multi-lane rescue and the corral; treat with skepticism — AS-05 (dead intra-repo doc links) is OPEN and almost certainly larger now than the corral records.

---

## 5. Open PR Queue — high-signal subset

The repo has ~260 open PR refs. Most are stale or zombies. This list focuses on items an operator should look at first:

### Inbound bugs/cleanup/anti-slop wave (this session)

| PR | Title | Status |
|---|---|---|
| #592 | DE_BUG_CORRAL — Phase B (consolidated) | DRAFT — see corral re-verifier note below |
| #597 | docs(readme): replace fake make targets with real ones (AS-06) | DRAFT |
| #598 | feat(governance): corral re-verifier — gate against importing stale findings | DRAFT |

**Corral re-verifier**: hand-spot-checking PR #592 against `9c76b21` showed at least TV-01 (CRITICAL, `execute_action logs success without mutating`) is **fully fixed** on current main — `dharma_swarm/ontology.py:774-975` reads `action_def.modifies`, calls `update_object`, writes a receipt. TV-02 (`InterruptGate auto-approves`) is partially stale — default is now `False`. PR #598 ships a structural re-verifier (`make verify-corral`) to gate against importing the rest as live debt.

### Recently rebased

| PR | Title | Notes |
|---|---|---|
| #576 | chore(docops): re-verify assertions, renew TTL | Rebased to single 1-line diff (TTL 2026-06-04 → 2026-06-12) |
| #562 | fix(evolution): honest archive status, real `gates_passed`, lineage `parent_id` | Rebased; obsolete docops-refresh commit dropped |
| #546 | chore(hygiene): move 17 MB semantic-graph evidence to release artifacts | Rebased; stale docops snapshots replaced with main's fresher counts |

### Awaiting operator decision

| PR | Title | Why blocked |
|---|---|---|
| #558 | governance/ws4-gate-pep | Explicit GATE 2 — operator review on WS4b semantic classifier gap |
| #591 | (duplicate of #594) | **CLOSED** this session; #594 plus governance report #595 superseded |

### Older near-ready (carried from prior dashboard, status unverified)

| PR | Title | Status |
|---|---|---|
| #375 | perplexity-computer identity nest | Needs rebase |
| #371 / #374 | 11-step chain verdict v6/v2 | Needs rebase |

Recommendation: triage the ~260 open PR refs in a dedicated session; many are zombies and bulk-closeable.

---

## 6. Broken Register Summary

Per `docs/state/BROKEN_REGISTER.md`. OPEN/PARTIAL items only:

| BR-ID | Issue | Status |
|---|---|---|
| BR-003 | Evolution apply gate present but closed (live apply intentionally gated) | PARTIAL |
| BR-004 | Cron split-brain (repo vs live) | PARTIAL |
| BR-005 | Algedonic stream — causal consumption/action coverage open | PARTIAL |
| BR-013 | Agent contract fragmented across 8+ surfaces | PARTIAL (CLAUDE.md pointer-stub landed; consolidation outstanding) |
| BR-014 | `BHED_GNAN` telos gate always passes | OPEN — closure must go through `GateRegistry.propose()`, not direct edit |

Closed: BR-001, BR-002, BR-006, BR-007, BR-008, BR-009, BR-010, BR-011, BR-012, BR-015, BR-016, BR-017, BR-018, BR-019.

Next ID: BR-020.

**Note on BR-020/BR-021 drafts**: this session originally planned to file BR-020 (`execute_action` silent no-op) and BR-021 (`InterruptGate` auto-approve). Both turned out to be stale findings on current main and were not filed. The honest debt those investigations surfaced was the corral-staleness problem itself, addressed by PR #598.

---

## 7. What To Do Tomorrow Morning

1. **Audit the bug-corral PR (#592)** with PR #598's re-verifier. Drop stale findings before merge.
2. **Review #597** (README fake make targets) and #576 (TTL renewal) — both small, both rebased clean.
3. **Decide on PR #558** (WS4b gate-PEP) — it's explicitly waiting on operator review.
4. **Close `runtime-truth-reconciliation-2026-06`** if criteria are still met; declare follow-on or open a successor.
5. **Triage the ~260 open PR refs.** Many are stale and closeable in bulk.
6. **Continue the hygiene delta-ratchet** wire-up into `verify-quality-membrane` — see PR #599 (forthcoming this session).

---

## One-Line Verdict

`main` is green at 799 commits, the spine substrate track is shipped and the reconciliation successor is SHIPPABLE, the bug corral needs re-verification before its findings land as debt, and the operator-decision bottleneck is shifting from "what to ship" to "what to close."
