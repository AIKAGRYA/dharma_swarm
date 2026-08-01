#!/usr/bin/env python3
"""One-shot branch bootstrap for Humming V2 A0 portfolio admission.

This script is intentionally temporary. It mutates only the exact governance
projection and ledger paths named below; it grants no implementation, merge,
deployment, or runtime authority. The branch controller deletes this file
before the final A0 head is reviewed.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

EXPECTED_BASE = "e1c5dffda158b9f2590567880b8278ee44437e87"
TRACK_PATH = Path("docs/governance/ACTIVE_TRACK.yaml")
LEDGER_PATH = Path(
    "docs/plans/handoffs/HUMMING_V2_EXECUTION_LEDGER_2026-08-01.md"
)


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def track_span(text: str, track_id: str) -> tuple[int, int]:
    marker = f"  - id: {track_id}\n"
    start = text.find(marker)
    if start < 0:
        raise SystemExit(f"missing active track: {track_id}")
    next_track = text.find("\n  - id: ", start + len(marker))
    closed_tracks = text.find("\nclosed_tracks:", start + len(marker))
    ends = [pos for pos in (next_track, closed_tracks) if pos >= 0]
    if not ends:
        raise SystemExit(f"cannot find end of active track: {track_id}")
    return start, min(ends)


def replace_track(text: str, track_id: str, block: str) -> str:
    start, end = track_span(text, track_id)
    return text[:start] + block + text[end:]


def add_owned_surfaces(text: str, track_id: str, paths: list[str]) -> str:
    start, end = track_span(text, track_id)
    block = text[start:end]
    if "    owned_surfaces:\n" not in block:
        raise SystemExit(f"{track_id}: no owned_surfaces list")
    anchor = "\n    moves_vital_signs:\n"
    if anchor not in block:
        raise SystemExit(f"{track_id}: cannot locate moves_vital_signs anchor")

    existing_region = block[
        block.index("    owned_surfaces:\n") : block.index(anchor)
    ]
    missing = [
        path for path in paths if f"      - {path}\n" not in existing_region
    ]
    if missing:
        additions = "".join(f"      - {path}\n" for path in missing)
        block = block.replace(anchor, additions + anchor, 1)
    return replace_track(text, track_id, block)


def add_next_item(text: str, track_id: str, item_id: str, yaml_body: str) -> str:
    start, end = track_span(text, track_id)
    block = text[start:end]
    if f"      - id: {item_id}\n" in block:
        return text
    if "    next_items:\n" not in block:
        raise SystemExit(f"{track_id}: no next_items list")
    anchor = "\n    non_goals:\n"
    if anchor not in block:
        raise SystemExit(f"{track_id}: cannot locate non_goals anchor")
    body = yaml_body.strip("\n")
    block = block.replace(anchor, "\n" + body + anchor, 1)
    return replace_track(text, track_id, block)


def main() -> int:
    subprocess.run(["git", "fetch", "origin", "main"], check=True)
    merge_base = git("merge-base", "HEAD", "origin/main")
    if merge_base != EXPECTED_BASE:
        raise SystemExit(
            "stale A0 bootstrap base: "
            f"expected {EXPECTED_BASE}, observed {merge_base}; "
            "refresh from live main before admission"
        )

    text = TRACK_PATH.read_text(encoding="utf-8")
    if "humming-v2-p0-k" in text:
        raise SystemExit("Humming V2 A0 appears already applied; refusing duplicate admission")

    safety_surfaces = [
        "dharma_swarm/action_effects/**",
        "dharma_swarm/tool_registry.py",
        "dharma_swarm/semantic_governance.py",
        "dharma_swarm/shakti_warrant.py",
        "dharma_swarm/telos_gates.py",
        "dharma_swarm/shell_command_policy.py",
        "hooks/telos_gate.py",
        ".claude/settings.json",
        "tests/test_action_effects.py",
        "tests/test_tool_registry.py",
        "tests/test_semantic_governance.py",
        "tests/test_shakti_warrant.py",
        "tests/test_shell_command_policy.py",
        "tests/test_telos_hook.py",
        str(LEDGER_PATH),
    ]
    titanium_surfaces = [
        "api/chat_tool_execution.py",
        "tests/test_shell_policy_consumers.py",
        "tests/test_action_provenance.py",
        "tests/test_sandbox_limits.py",
        "tests/test_budget_accounting_adapters.py",
    ]
    loop_surfaces = [
        "agent_loop.sh",
        "cron_jobs.json",
        "scripts/cron_unify.py",
        "dharma_swarm/cron_job_runtime.py",
        "tests/test_agent_loop_budget.py",
        "tests/test_cron_unify.py",
        "tests/test_cron_authority.py",
    ]
    graph_surfaces = [
        "tests/test_action_effect_graph_adapter.py",
        "tests/test_graph_budget_lineage.py",
    ]

    text = add_owned_surfaces(
        text, "sovereign-safety-tcb-2026-07", safety_surfaces
    )
    text = add_owned_surfaces(
        text, "repository-titanium-hardening-2026-07", titanium_surfaces
    )
    text = add_owned_surfaces(text, "loop-closure-2026-06", loop_surfaces)
    text = add_owned_surfaces(
        text, "dharmagraph-engine-2026-07", graph_surfaces
    )

    safety_items = {
        "humming-v2-p0-k": r"""
      - id: humming-v2-p0-k
        what: >-
          ADMITTED ONLY AFTER THE A0 GOVERNANCE PR MERGES. Build the typed
          constitutional ActionEnvelope and one action-effect dispatcher under
          dharma_swarm/action_effects/**, reusing ExecutionIdentity,
          RuntimeStateStore idempotency, Shakti warrants, EvidenceReceipt,
          reversibility gates, and existing runtime storage. The action class,
          never the caller, derives required fields. Initial migrated coverage
          is exactly ToolRegistry plus one read-only action and one
          consequential non-production test action. Dependencies: merged A0.
          Cross-track acknowledgements: repository-titanium-hardening-2026-07
          and dharmagraph-engine-2026-07. Completion: scoped
          live/record/replay/shadow/deny handlers; wrong or missing identity,
          expired authority, duplicate side-effect identity, prepared without
          commit, commit without required evidence, rollback, and one sabotage
          mutation per protected field all fail as specified. Target closure:
          VERIFIED_SLICE. Non-goals: no new truth store, no parallel receipt or
          identity system, no universal enforcement claim, and no whole-runtime
          replacement.
        kind: code
        blocker: true
""",
        "humming-v2-p0-h1a": r"""
      - id: humming-v2-p0-h1a
        what: >-
          H1a, before installation: harden hooks/telos_gate.py with strict input
          schema validation, inspection of every GATED_TOOLS member, and
          fail-closed consequential behavior for empty, malformed, unknown, and
          exception paths. Denial evidence must be written before return, and
          an unavailable logger may never convert denial to permission.
          Dependencies: merged A0. Completion: per-tool positive and sabotage
          tests plus malformed/empty/logger-failure negative controls.
          Cross-track acknowledgement: repository-titanium-hardening-2026-07.
          Target closure: VERIFIED_SLICE. Non-claim: this seat-specific hook is
          not the universal action-effect boundary.
        kind: code
        blocker: true
""",
        "humming-v2-p0-h1b": r"""
      - id: humming-v2-p0-h1b
        what: >-
          H1b, installation only after humming-v2-p0-h1a is independently
          reviewed and merged: register the hardened PreToolUse hook in
          .claude/settings.json and prove one real end-to-end consequential
          denial with its denial evidence. Dependency: H1a exact merged head.
          Completion: tracked settings, hook invocation receipt, denial, and
          rollback proof. Target level: RUNTIME_BLOCKING for the declared
          Claude Code seat only. Non-goal: no universal effect-boundary claim.
        kind: code
        blocker: true
""",
        "humming-v2-p0-h2a": r"""
      - id: humming-v2-p0-h2a
        what: >-
          Implement deterministic capability and argument provenance through
          ActionEnvelope. External text may populate data fields but may never
          choose capability, destination, authority class, graph edge,
          approval state, budget, or policy mode. A stochastic judge may deny,
          abstain, or escalate but may never grant authority denied or
          unestablished by deterministic code. Dependencies: humming-v2-p0-k.
          Cross-track acknowledgement: repository-titanium-hardening-2026-07.
          Completion: an end-to-end external-content injection attempts to
          change the selected consequential tool with the judge disabled; the
          deterministic layer blocks and receipts why. Target level:
          RUNTIME_BLOCKING. Non-goals: no positive LLM authorization oracle and
          no metadata-only provenance theater.
        kind: code
        blocker: true
""",
        "humming-v2-p0-h3-contract": r"""
      - id: humming-v2-p0-h3-contract
        what: >-
          Define one deterministic shell-command policy in
          dharma_swarm/shell_command_policy.py. Freeze its policy digest,
          normalize paths and arguments, classify read-only versus
          consequential commands, and preserve the union of the strictest
          protections currently present in sandbox.py, autonomous_agent.py,
          and api/chat_tool_execution.py. Dependencies: merged A0.
          Completion: seeded corpus parity and sabotage tests that weaken each
          protected family and fail. Cross-track acknowledgement:
          repository-titanium-hardening-2026-07, which owns consumer migration.
          Target closure: VERIFIED_SLICE. Non-goal: no policy weakening or
          caller-specific shadow copies.
        kind: code
        blocker: true
""",
        "humming-v2-p0-b-contract": r"""
      - id: humming-v2-p0-b-contract
        what: >-
          Establish one hierarchical parent/child budget reservation contract
          for loops, graph nodes, retries, provider fallbacks, and
          consequential tool calls, integrated with existing runtime state and
          receipts. A parent may not authorize unbounded downstream work while
          reporting only direct spend. Dependencies: merged A0 and
          humming-v2-p0-k schema coordination. Completion: reservation,
          consume, release, expiry, retry, child-overrun, duplicate-consume,
          and crash-recovery negative controls. Cross-track acknowledgements:
          repository-titanium-hardening-2026-07,
          dharmagraph-engine-2026-07, and loop-closure-2026-06. Target closure:
          VERIFIED_SLICE. Until authoritative downstream adapters land,
          aggregate token or cost-cap claims are prohibited. Non-goal: no new
          economic ledger or durable truth store.
        kind: code
        blocker: true
""",
    }
    for item_id, body in safety_items.items():
        text = add_next_item(
            text, "sovereign-safety-tcb-2026-07", item_id, body
        )

    titanium_items = {
        "humming-v2-p0-harness-consumers": r"""
      - id: humming-v2-p0-harness-consumers
        what: >-
          Migrate the Titanium-owned consequential consumers
          (autonomous_agent.py, sandbox.py, and api/chat_tool_execution.py) to
          the merged ActionEnvelope/provenance contract and the single frozen
          shell policy. Dependencies: humming-v2-p0-k,
          humming-v2-p0-h2a, and humming-v2-p0-h3-contract merged at exact
          heads. Completion: identical seeded command-policy behavior across
          every migrated consumer; external-content capability-selection
          injection blocked with the judge disabled; exact migrated coverage,
          feature-flag rollback, and sabotage negatives reported. Target
          closure: VERIFIED_SLICE. Non-claims: no universal runtime coverage
          and no weakening of the API consumer's current stricter controls.
        kind: code
        blocker: true
""",
        "humming-v2-p0-h6": r"""
      - id: humming-v2-p0-h6
        what: >-
          Add honest LocalSandbox CPU, memory, process, file-size, wall-clock,
          and output limits where the host supports them, with explicit
          isolation tiers. A requested network-isolated mode must fail rather
          than silently fall back when default-deny networking is unavailable.
          Dependencies: humming-v2-p0-h3-contract and the scoped
          ActionEnvelope adapter. Completion: resource-exhaustion negatives,
          process-tree cleanup, output truncation receipt, unsupported-network
          refusal, and declared-tier checks. Target closure: VERIFIED_SLICE.
          Non-claim: LocalSandbox is not network-isolated merely because a
          Docker-preferred manager can fall back to it.
        kind: code
        blocker: true
""",
        "humming-v2-p0-b-adapters": r"""
      - id: humming-v2-p0-b-adapters
        what: >-
          Wire authoritative child accounting adapters for Titanium-owned
          agent/tool/provider paths into humming-v2-p0-b-contract. Dependencies:
          the merged budget contract and ActionEnvelope. Completion: child
          reservations reconcile to parent limits across retries and provider
          fallback, unpriced or missing downstream usage blocks aggregate-cap
          claims, and duplicate receipts do not double-charge. Cross-track
          acknowledgements: loop-closure-2026-06 and
          dharmagraph-engine-2026-07. Target closure: VERIFIED_SLICE.
          Non-goal: do not reinterpret daemon-direct spend or EconomicLedger
          P&L as aggregate authorization.
        kind: code
        blocker: true
""",
    }
    for item_id, body in titanium_items.items():
        text = add_next_item(
            text, "repository-titanium-hardening-2026-07", item_id, body
        )

    loop_items = {
        "humming-v2-p0-b-root-loop": r"""
      - id: humming-v2-p0-b-root-loop
        what: >-
          Bound root agent_loop.sh with cycle, wall-clock, and stall limits and
          consume the merged hierarchical budget contract. Token/cost limits
          may be advertised only where authoritative child accounting exists.
          Dependencies: humming-v2-p0-b-contract and the applicable Titanium
          accounting adapters. Completion: cycle/wall/stall stops, child budget
          exhaustion, crash/restart, and no-output negative controls with
          receipts. Cross-track acknowledgement:
          repository-titanium-hardening-2026-07. Target closure:
          VERIFIED_SLICE. Non-goal: no false aggregate-spend claim from a
          direct-spend-only ledger.
        kind: code
        blocker: true
""",
        "humming-v2-e1-cron-authority": r"""
      - id: humming-v2-e1-cron-authority
        what: >-
          OWNERSHIP RESOLUTION ONLY AT A0: loop-closure owns cron_jobs.json,
          scripts/cron_unify.py, and cron_job_runtime.py for the future E1
          authority-unification slice. Implementation is dependency-blocked
          until the constitutional harness, bounded-loop P1, and scoped graph
          P2 prerequisites are merged. Completion when executable: one durable
          scheduler authority, source-derived orphan count zero, scheduling
          receipts, rollback, and host-bound observation. Cross-track
          acknowledgement: organism-rewire-2026-07 for the running host.
          Target closure: CLOSED_NOT_PROD before any live-host promotion.
          Non-goals: A0 performs no scheduler swap, deployment, credential
          access, or BR-004 closure claim.
        kind: governance
        blocker: false
""",
    }
    for item_id, body in loop_items.items():
        text = add_next_item(text, "loop-closure-2026-06", item_id, body)

    graph_item = r"""
      - id: humming-v2-p0-graph-adapter
        what: >-
          Add the DharmaGraph adapter for ActionEnvelope graph/checkpoint
          identity, parent/child budget propagation, and side-effect identity
          derived from (run_id, superstep, node_id, attempt), reusing
          durable_invoker and RuntimeStateStore idempotency. Dependencies:
          humming-v2-p0-k and humming-v2-p0-b-contract merged at exact heads.
          Completion: same-attempt crash/resume invokes the provider exactly
          once; new retry attempt receives a distinct identity; budget and
          envelope failures prevent commit; no new store. Cross-track
          acknowledgements: sovereign-safety-tcb-2026-07 and
          repository-titanium-hardening-2026-07. Target closure:
          VERIFIED_SLICE. Non-goal: this does not authorize P2 graph promotion
          or claim neutral-engine production parity.
        kind: code
        blocker: true
"""
    text = add_next_item(
        text,
        "dharmagraph-engine-2026-07",
        "humming-v2-p0-graph-adapter",
        graph_item,
    )

    host_item = r"""
      - id: humming-v2-host-ack
        what: >-
          Cross-track host acknowledgement for Humming V2: preserve
          deployment authority with organism-rewire and provide later
          host-bound evidence for actual sandbox/network tier, scheduler
          authority, loop causality, and rollback. Dependencies: no host action
          before the owning implementation PRs merge. Completion: exact
          deployed SHA, host identity, live owner-surface observation, negative
          control, and rollback receipt. Target closure: host evidence only.
          Non-goals: A0 authorizes no deployment, restart, secret use, paid
          infrastructure, or CLOSED_LIVE promotion.
        kind: ops
        blocker: false
"""
    text = add_next_item(
        text, "organism-rewire-2026-07", "humming-v2-host-ack", host_item
    )

    mike_item = r"""
      - id: humming-v2-enforcement-ack
        what: >-
          Cross-track enforcement acknowledgement for Humming V2: preserve the
          existing required-check, stale-head, conflict, unresolved-thread,
          CHANGES_REQUESTED, reviewer-quorum, and human-risk gates. New Humming
          checks remain OBSERVED or CHECKED until the existing policy
          independently promotes them; advisory jobs are never described as
          enforced. Dependencies: each owning implementation PR supplies its
          exact deterministic checker and negative control. Target closure:
          VERIFIED_SLICE for merge-policy consumption only. Non-goals: no new
          merge authority, waiver, self-approval, silent merge, or reduced
          required-context set.
        kind: governance
        blocker: false
"""
    text = add_next_item(
        text,
        "merge-master-mike-d4-2026-06",
        "humming-v2-enforcement-ack",
        mike_item,
    )

    TRACK_PATH.write_text(text, encoding="utf-8")

    pr_number = os.environ.get("HUMMING_A0_PR_NUMBER", "PENDING")
    head_sha = git("rev-parse", "HEAD")
    ledger = f"""# Humming V2 Execution Ledger

**Status:** A0 admission projection; implementation remains unauthorized until
the A0 governance PR is independently reviewed and merged.
**Authority:** none. Git, `docs/governance/ACTIVE_TRACK.yaml`, CI, current owner
files, and runtime receipts remain authoritative.
**Base:** `{EXPECTED_BASE}`
**Bootstrap head before generated A0 commit:** `{head_sha}`
**Branch:** `codex/humming-v2-a0-portfolio-admission`
**Pull request:** `#{pr_number}`
**Governing design:** `docs/plans/HARNESS_LOOP_GRAPH_HUMMING_SPEC_V2_2026-08-01.md`
**Adversarial review:** `docs/plans/handoffs/CODEX_HUMMING_SPEC_ADVERSARIAL_REVIEW_2026-08-01.md`

This file is append-only after A0 merges. Corrections append a superseding row;
they do not rewrite history. It is a projection and cannot overrule an owner.

| Work item | Owning track | Dependencies | Enforcement now | Positive proof | Negative control | Rollback | Live host | State | Remaining blocker |
|---|---|---|---|---|---|---|---|---|---|
| A0 portfolio admission | cross-track governance | #1187 and #1186 merged | CHECKED after CI only | ACTIVE_TRACK diff + owner map | no new track; no implementation diff | revert A0 | no | ADMISSION_PENDING_MERGE | independent review and human merge |
| P0-K ActionEnvelope + dispatcher | sovereign-safety-tcb | A0 merged | OBSERVED design only | none yet | none yet | additive feature flag required | no | NOT_STARTED | A0 merge |
| P0-H1a hook hardening | sovereign-safety-tcb | A0 merged | OBSERVED design only | none yet | malformed/empty/logger sabotage required | hook remains uninstalled | no | NOT_STARTED | A0 merge |
| P0-H1b hook installation | sovereign-safety-tcb | H1a merged | OBSERVED design only | none yet | real denied tool call required | remove tracked hook registration | seat | BLOCKED_DEPENDENCY | H1a |
| P0-H2a deterministic provenance | sovereign-safety-tcb + Titanium adapter | P0-K | OBSERVED design only | none yet | external-content capability injection required | additive adapter flag | no | BLOCKED_DEPENDENCY | P0-K |
| P0-H3 shell policy | safety contract + Titanium consumers | A0 then contract | OBSERVED design only | none yet | policy-weakening mutations required | consumer-by-consumer rollback | no | NOT_STARTED | A0 merge |
| P0-H6 sandbox limits | repository-titanium-hardening | H3 + envelope adapter | OBSERVED design only | none yet | resource exhaustion and unsupported network mode | retain honest prior tier | host later | BLOCKED_DEPENDENCY | H3 |
| P0-B hierarchical budgets | safety contract + three adapters | P0-K coordination | OBSERVED design only | none yet | overrun/duplicate/crash tests required | prohibit aggregate claim | host later | NOT_STARTED | A0 merge |
| Root agent loop bounds | loop-closure | P0-B + accounting | OBSERVED design only | none yet | no-output/stall/budget controls required | `.STOP` behavior preserved | no | BLOCKED_DEPENDENCY | P0-B |
| DharmaGraph envelope/budget adapter | dharmagraph-engine | P0-K + P0-B | OBSERVED design only | none yet | crash/resume exactly-once required | adapter removal | no | BLOCKED_DEPENDENCY | P0-K/P0-B |
| E1 cron authority | loop-closure + organism host ack | P0/P1/P2 | OBSERVED ownership only | none yet | source-derived orphan test required | no live swap in A0 | yes | BLOCKED_DEPENDENCY | P0/P1/P2 |

## A0 non-claims

- No implementation authority exists before A0 merges.
- No active track was created.
- No One Wire, chamber, Safety TCB, human, deployment, credential, or merge
  authority changed.
- No `CLOSED_LIVE`, production, universal enforcement, aggregate-budget, or
  neutral-graph parity claim is made.
- PR #1177 remains a serialized governance collision; its Titanium amendment
  must merge first or this branch must be refreshed while preserving both
  changes before A0 can become Ready.
"""
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEDGER_PATH.write_text(ledger, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
