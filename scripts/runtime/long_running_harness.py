#!/usr/bin/env python3
"""Filesystem scaffold for long-running planner/generator/evaluator harnesses.

This is not an autonomous runner. It creates and validates the durable
artifacts that make long-running agent work reviewable: a product spec, a
negotiated done contract, rubrics, progress state, trace index, and handoff.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE_ROOT = Path("~/.dharma/harness_runs")
SCHEMA_PATH = "schemas/long_running_harness.schema.json"
PGE_MIN_CONTRACT_CRITERIA = 20
PGE_MEMORY_RULE_PATH = "~/.claude/projects/-Users-dhyana/memory/feedback_pge_harness_standard.md"
PGE_WIKI_ATOM_PATH = "~/.dharma/knowledge/wiki/concepts/pge-harness-pattern.md"

REQUIRED_ARTIFACTS = [
    "run.json",
    "README.md",
    "planner/spec.md",
    "planner/plan.json",
    "contracts/done_contract.v0.md",
    "contracts/contract.json",
    "generator/GENERATOR_BRIEF.md",
    "evaluator/EVALUATOR_BRIEF.md",
    "rubrics/evaluator_rubric.json",
    "progress/progress.json",
    "traces/trace_index.jsonl",
    "handoff/HANDOFF.md",
]

DEFAULT_RUBRIC = [
    {
        "id": "functionality",
        "weight": 20,
        "threshold": 4,
        "question": "Does the implemented behavior work end-to-end under realistic use?",
    },
    {
        "id": "design_quality",
        "weight": 16,
        "threshold": 4,
        "question": "Does the user-facing surface feel coherent, intentional, and legible?",
    },
    {
        "id": "originality",
        "weight": 14,
        "threshold": 4,
        "question": "Does the work avoid generic AI-template defaults and borrowed SaaS chrome?",
    },
    {
        "id": "craft",
        "weight": 14,
        "threshold": 4,
        "question": "Are spacing, typography, state handling, errors, and edge cases handled cleanly?",
    },
    {
        "id": "context_density",
        "weight": 12,
        "threshold": 4,
        "question": "Does the change increase useful context carrying capacity without clutter?",
    },
    {
        "id": "evidence",
        "weight": 10,
        "threshold": 4,
        "question": "Are claims backed by tests, screenshots, logs, or witness artifacts?",
    },
    {
        "id": "governance_integrity",
        "weight": 8,
        "threshold": 5,
        "question": "Does the work obey active-track, protected-file, and no-new-substrate constraints?",
    },
    {
        "id": "traceability",
        "weight": 6,
        "threshold": 4,
        "question": "Can a later agent reconstruct what happened and why from files on disk?",
    },
]

PGE_RULES = [
    {
        "id": "self_evaluation_is_trap",
        "rule": "Use a separate adversarial evaluator; do not let the generator grade itself.",
    },
    {
        "id": "compaction_not_coherence",
        "rule": "Use filesystem state for sustained builds; chat compaction is not authoritative state.",
    },
    {
        "id": "structured_handoffs_clean_context",
        "rule": "Generator and evaluator negotiate a done contract via files before coding.",
    },
    {
        "id": "subjective_quality_is_gradable",
        "rule": "Use explicit weighted rubrics with thresholds for design, originality, craft, and function.",
    },
    {
        "id": "read_the_traces",
        "rule": "Trace reading is the primary debug loop before prompt or harness changes.",
    },
    {
        "id": "granular_contract_criteria",
        "rule": f"Contracts should carry at least {PGE_MIN_CONTRACT_CRITERIA} testable assertions for long builds.",
    },
    {
        "id": "harsh_evaluator",
        "rule": "Evaluator must be adversarial and willing to block partial or pretty-but-broken output.",
    },
    {
        "id": "do_not_muddy_contexts",
        "rule": "Evaluator judges outputs and evidence, not the generator hidden reasoning stream.",
    },
    {
        "id": "breadcrumbs_for_next_session",
        "rule": "Every run leaves timestamped JSON breadcrumbs plus a compact human handoff.",
    },
    {
        "id": "co_evolve_with_models",
        "rule": "Record which scaffold rules can sunset when a later model makes them redundant.",
    },
]

PGE_CONTRACT_CRITERIA = [
    "Planner stays high-level and does not dictate granular implementation choices that could cascade.",
    "Generator and evaluator operate as separate roles with separate context, prompts, or explicitly isolated handoff files.",
    "Evaluator judges artifacts, commands, screenshots, logs, diffs, and receipts; evaluator does not rely on generator self-assessment.",
    "Evaluator prompt/rubric is explicitly harsh and may block output that is partial, pretty-only, or unverified.",
    "Contract contains at least four rubric dimensions with thresholds and a hard-fail rule.",
    f"Contract grows to at least {PGE_MIN_CONTRACT_CRITERIA} testable assertions before implementation is considered ready.",
    "Filesystem state in this run directory is authoritative over chat history and compaction summaries.",
    "Each material attempt appends a trace event with timestamp, action, outcome, and whether the fix worked.",
    "UI claims require live browser, screenshot, or explicit unavailable-reason evidence.",
    "CLI/API claims require command output, exit code, or explicit unavailable-reason evidence.",
    "Handoff names current state, blockers, file scope, evidence paths, and next action.",
    "Trace critic or human reviewer reads traces before changing harness prompts or declaring the scaffold obsolete.",
    "If evaluation stalls, generator proposes a pivot or restart rather than endless patching.",
    "Sunset notes record which PGE rule could relax after a future model release and what evidence would justify that.",
]

COMMAND_PLANE_CRITERIA = [
    "No new route, API, store, daemon, or surface is added unless manifest-registered.",
    "The generator declares exact touched files before editing and stays inside that set.",
    "The evaluator verifies the live page or records why browser verification is unavailable.",
    "The evaluator checks desktop and narrow viewport context density for user-visible changes.",
    "The evaluator grades design_quality, originality, craft, functionality, and context_density.",
    "The evaluator may fail the run even when tests pass if UI capacity or taste regresses.",
    "Trace files include failed approaches, not only the final happy path.",
    "The handoff states what future agents must not touch.",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:80] or "harness-run"


def expand(path: Path | str) -> Path:
    return Path(os.path.expanduser(str(path)))


def write_text(path: Path, content: str, *, force: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        return
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=True) + "\n")


def read_active_track(repo_root: Path) -> dict[str, str]:
    path = repo_root / "docs/governance/ACTIVE_TRACK.yaml"
    if not path.exists():
        return {"id": "unknown", "name": "unknown", "status": "unknown"}
    active = False
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("active_track:"):
            active = True
            continue
        if active and line and not line.startswith(" "):
            break
        if active:
            stripped = line.strip()
            for key in ("id", "name", "status"):
                prefix = f"{key}:"
                if stripped.startswith(prefix):
                    result[key] = stripped[len(prefix):].strip().strip('"')
    return {
        "id": result.get("id", "unknown"),
        "name": result.get("name", "unknown"),
        "status": result.get("status", "unknown"),
    }


def git_output(repo_root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args],
            cwd=repo_root,
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=10,
        ).strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return ""


def git_snapshot(repo_root: Path) -> dict[str, Any]:
    status = git_output(repo_root, "status", "--short")
    dirty_entries = [line for line in status.splitlines() if line.strip()]
    return {
        "branch": git_output(repo_root, "branch", "--show-current") or "(detached-or-unknown)",
        "base_sha": git_output(repo_root, "rev-parse", "HEAD") or "unknown",
        "dirty_count": len(dirty_entries),
        "dirty_entries_sample": dirty_entries[:80],
        "is_clean": not dirty_entries,
    }


def run_dir(state_root: Path, run_id: str) -> Path:
    return expand(state_root) / run_id


def default_plan(goal: str, mode: str) -> dict[str, Any]:
    return {
        "version": 1,
        "mode": mode,
        "goal": goal,
        "harness_standard": "pge",
        "min_contract_criteria": PGE_MIN_CONTRACT_CRITERIA,
        "planning_rule": "Planner sets product/user/workflow boundaries, not granular implementation details.",
        "rounds": [
            {
                "round": 1,
                "intent": "Negotiate done contract before implementation.",
                "owner": "generator+evaluator",
                "status": "pending",
            },
            {
                "round": 2,
                "intent": "Build the smallest coherent slice inside declared files.",
                "owner": "generator",
                "status": "pending",
            },
            {
                "round": 3,
                "intent": "Evaluate with rubric, live evidence, and trace review.",
                "owner": "evaluator",
                "status": "pending",
            },
        ],
    }


def contract_markdown(goal: str, mode: str) -> str:
    mode_criteria = COMMAND_PLANE_CRITERIA if mode == "command-plane" else [
        "Generator declares exact touched files before editing.",
        "Evaluator approves a test plan before implementation starts.",
        "At least one automated or manual verification receipt is recorded.",
        "Progress state is updated after every round.",
        "Trace index records failures and pivots.",
        "Handoff states remaining risks and next action.",
    ]
    criteria = [*mode_criteria, *PGE_CONTRACT_CRITERIA]
    numbered = "\n".join(f"{idx + 1}. {item}" for idx, item in enumerate(criteria))
    return f"""# Done Contract v0

Goal: {goal}
Mode: {mode}
Harness standard: PGE — Planner / Generator / Evaluator
Minimum criteria target: {PGE_MIN_CONTRACT_CRITERIA}

## Contract Rule

The generator and evaluator must agree on this contract before implementation.
The evaluator grades against this file, not against vibes or the generator's
self-assessment.

This is the repo-side operationalization of the PGE governance standard in
`docs/ops/PGE_AUTONOMOUS_BUILD_SYSTEM.md`, `{PGE_MEMORY_RULE_PATH}`, and
`{PGE_WIKI_ATOM_PATH}`.

## Criteria

{numbered}

## Negotiation Log

- pending: generator proposes file scope and verification plan
- pending: evaluator accepts, rejects, or narrows the contract
"""


def generator_brief(goal: str) -> str:
    return f"""# Generator Brief

Goal: {goal}

You build only after the evaluator accepts the done contract.

Required behavior:

- Read `planner/spec.md`, `contracts/done_contract.v0.md`, and `progress/progress.json`.
- Declare intended file scope before editing.
- Prefer small, reviewable slices.
- Do not modify tests to make weak work pass.
- Record every material action in `traces/trace_index.jsonl`.
- Update `progress/progress.json` and `handoff/HANDOFF.md` before stopping.
- Treat PGE filesystem state as authoritative over chat memory.
- Do not read or edit evaluator private notes.
"""


def evaluator_brief() -> str:
    return """# Evaluator Brief

You are adversarial, not encouraging.

Required behavior:

- Review the done contract before implementation starts.
- Reject vague criteria.
- Prefer direct product evidence: tests, browser interaction, screenshots, logs, API calls.
- Fail display-only features when interaction is expected.
- Fail generic visual polish when the system has a specific design language.
- Record exact findings with file paths, commands, screenshots, or witness paths.
- Do not read the generator's hidden reasoning. Judge outputs and traces.
- Enforce the PGE standard: harsh review, separate context, concrete evidence,
  granular criteria, and no self-evaluation.
"""


def spec_markdown(goal: str, active_track: dict[str, str], mode: str) -> str:
    return f"""# Planner Spec

Goal: {goal}

Mode: {mode}
Active track: `{active_track['id']}` — {active_track['name']}

## Product Boundary

Define the user-visible outcome and the hard non-goals here. Keep this section
high level. Do not over-specify technical implementation details that downstream
agents should discover through context quorum and contract negotiation.

## Required Harness Behavior

- Planner provides product/workflow boundaries.
- Generator proposes a concrete done contract.
- Evaluator negotiates and grades the contract with independent evidence.
- Trace critic reads traces after the run and updates harness rules only when a
  failure pattern repeats.

## PGE Standard

This run applies the PGE Harness Standard: planner, generator, evaluator, harsh
rubric, filesystem state, structured handoff, trace reading, and per-rule sunset
criteria. Repo spec: `docs/ops/PGE_AUTONOMOUS_BUILD_SYSTEM.md`.
"""


def pge_standard_payload() -> dict[str, Any]:
    return {
        "id": "pge",
        "name": "Planner / Generator / Evaluator Harness Standard",
        "adopted_at": "2026-05-21",
        "applies_when": ">=30 minutes sustained build, >=3 iterations, or >=1 user-facing verifiable artifact",
        "repo_bridge": "docs/ops/PGE_AUTONOMOUS_BUILD_SYSTEM.md",
        "repo_scaffold": "docs/ops/LONG_RUNNING_HARNESS.md",
        "memory_rule_path": PGE_MEMORY_RULE_PATH,
        "wiki_atom_path": PGE_WIKI_ATOM_PATH,
        "min_contract_criteria": PGE_MIN_CONTRACT_CRITERIA,
        "rules": PGE_RULES,
    }


def create_run(args: argparse.Namespace) -> int:
    repo_root = expand(args.repo_root)
    state_root = expand(args.state_root)
    active_track = read_active_track(repo_root)
    repo_state = git_snapshot(repo_root)
    if args.require_clean and not repo_state["is_clean"]:
        print(f"error: repo has {repo_state['dirty_count']} dirty entries; rerun without --require-clean or use an isolated worktree", file=sys.stderr)
        return 4
    run_id = args.run_id or f"{utc_now()[:10]}-{slugify(args.goal)}"
    root = run_dir(state_root, run_id)
    if root.exists() and not args.force:
        print(f"error: run already exists: {root}", file=sys.stderr)
        return 2

    now = utc_now()
    contract_items = [
        *(COMMAND_PLANE_CRITERIA if args.mode == "command-plane" else []),
        *PGE_CONTRACT_CRITERIA,
    ]
    run_payload = {
        "version": 1,
        "run_id": run_id,
        "goal": args.goal,
        "mode": args.mode,
        "status": "initialized",
        "created_at": now,
        "repo_root": repo_root.as_posix(),
        "git_state": repo_state,
        "active_track": active_track,
        "risk_level": args.risk,
        "max_rounds": args.max_rounds,
        "schema": (repo_root / SCHEMA_PATH).as_posix(),
        "harness_standard": pge_standard_payload(),
        "roles": {
            "planner": "high-level product/workflow spec",
            "generator": "bounded implementation against accepted contract",
            "evaluator": "adversarial verification against contract",
            "trace_critic": "post-run trace reader and harness improver",
        },
        "artifacts": {artifact: (root / artifact).as_posix() for artifact in REQUIRED_ARTIFACTS},
        "context_quorum": {
            "required": args.risk.upper() in {"Q2", "Q3", "Q4"},
            "manifest_path": "",
            "status": "not_attached",
        },
        "scope": {
            "allowed_write_paths": [],
            "forbidden_paths": [
                "dashboard/src/lib/theme.ts",
                "dashboard/src/app/globals.css",
                "dashboard/src/lib/motion.ts",
                "dharma_swarm/terminal_bridge.py",
                ".github/workflows/**",
                "tests/**",
                "docs/governance/**",
            ],
        },
    }
    write_json(root / "run.json", run_payload)
    write_text(root / "README.md", f"# Harness Run {run_id}\n\nGoal: {args.goal}\n\nStart with `run.json` and `contracts/done_contract.v0.md`.\n")
    write_text(root / "planner/spec.md", spec_markdown(args.goal, active_track, args.mode))
    write_json(root / "planner/plan.json", default_plan(args.goal, args.mode))
    write_text(root / "contracts/done_contract.v0.md", contract_markdown(args.goal, args.mode))
    write_json(root / "contracts/contract.json", {
        "version": 1,
        "status": "draft",
        "goal": args.goal,
        "mode": args.mode,
        "criteria": contract_items,
        "generator_acceptance": None,
        "evaluator_acceptance": None,
        "updated_at": now,
    })
    write_text(root / "generator/GENERATOR_BRIEF.md", generator_brief(args.goal))
    write_text(root / "evaluator/EVALUATOR_BRIEF.md", evaluator_brief())
    write_json(root / "rubrics/evaluator_rubric.json", {
        "version": 1,
        "scale": "1-5",
        "passing_rule": "Every criterion must meet threshold; weighted average alone is insufficient.",
        "criteria": DEFAULT_RUBRIC,
        "updated_at": now,
    })
    write_json(root / "progress/progress.json", {
        "version": 1,
        "status": "initialized",
        "round": 0,
        "features": [],
        "open_findings": [],
        "updated_at": now,
    })
    write_text(root / "traces/trace_index.jsonl", "")
    append_jsonl(root / "traces/trace_index.jsonl", {
        "ts": now,
        "event": "harness_run_initialized",
        "run_id": run_id,
        "goal": args.goal,
        "mode": args.mode,
    })
    write_text(root / "handoff/HANDOFF.md", f"""# Harness Handoff

Run: {run_id}
Goal: {args.goal}
Status: initialized

## Next Step

Generator and evaluator negotiate `contracts/done_contract.v0.md`.

## Do Not Touch

- concurrent frontend palette lane files unless this run explicitly owns them
- protected governance/test files without context quorum and approval
""")
    print(root)
    return 0


def inspect_run(args: argparse.Namespace, *, fail_on_error: bool) -> int:
    root = run_dir(expand(args.state_root), args.run_id)
    missing = [artifact for artifact in REQUIRED_ARTIFACTS if not (root / artifact).exists()]
    run_path = root / "run.json"
    run_payload: dict[str, Any] = {}
    run_status = "missing"
    git_state_present = False
    context_quorum_status = "missing"
    if run_path.exists():
        try:
            run_payload = json.loads(run_path.read_text(encoding="utf-8"))
            run_status = str(run_payload.get("status", "unknown"))
            git_state = run_payload.get("git_state") or {}
            git_state_present = bool(git_state.get("base_sha") and "dirty_count" in git_state)
            context_quorum_status = str((run_payload.get("context_quorum") or {}).get("status", "missing"))
        except json.JSONDecodeError:
            run_status = "invalid_json"
    contract_path = root / "contracts/contract.json"
    criterion_count = 0
    contract_status = "missing"
    generator_acceptance = None
    evaluator_acceptance = None
    if contract_path.exists():
        try:
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            criterion_count = len(contract.get("criteria") or [])
            contract_status = str(contract.get("status", "unknown"))
            generator_acceptance = contract.get("generator_acceptance")
            evaluator_acceptance = contract.get("evaluator_acceptance")
        except json.JSONDecodeError:
            contract_status = "invalid_json"
    progress_status = "missing"
    progress_path = root / "progress/progress.json"
    if progress_path.exists():
        try:
            progress = json.loads(progress_path.read_text(encoding="utf-8"))
            progress_status = str(progress.get("status", "unknown"))
        except json.JSONDecodeError:
            progress_status = "invalid_json"
    scaffold_valid = not missing and contract_status != "invalid_json" and run_status != "invalid_json" and git_state_present
    contract_ready = scaffold_valid and contract_status == "accepted" and bool(generator_acceptance) and bool(evaluator_acceptance)
    complete_ready = contract_ready and progress_status in {"complete", "completed", "passed", "landed"}
    phase = getattr(args, "phase", "scaffold")
    phase_valid = {
        "scaffold": scaffold_valid,
        "contract": contract_ready,
        "complete": complete_ready,
    }[phase]
    payload = {
        "run_id": args.run_id,
        "run_root": root.as_posix(),
        "missing_artifacts": missing,
        "run_status": run_status,
        "contract_status": contract_status,
        "criterion_count": criterion_count,
        "git_state_present": git_state_present,
        "context_quorum_status": context_quorum_status,
        "progress_status": progress_status,
        "scaffold_valid": scaffold_valid,
        "contract_ready": contract_ready,
        "complete_ready": complete_ready,
        "phase": phase,
        "valid": phase_valid,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"run_root: {payload['run_root']}")
        print(f"valid: {payload['valid']}")
        print(f"phase: {phase}")
        print(f"run_status: {run_status}")
        print(f"contract_status: {contract_status}")
        print(f"criterion_count: {criterion_count}")
        print(f"git_state_present: {git_state_present}")
        print(f"context_quorum_status: {context_quorum_status}")
        print(f"progress_status: {progress_status}")
        if missing:
            print("missing_artifacts:")
            for item in missing:
                print(f"  - {item}")
    return 3 if fail_on_error and not payload["valid"] else 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Long-running harness artifact scaffold")
    p.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    p.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT)
    sub = p.add_subparsers(dest="cmd", required=True)

    init = sub.add_parser("init")
    init.add_argument("--goal", required=True)
    init.add_argument("--run-id", default="")
    init.add_argument("--mode", choices=["brownfield", "greenfield", "command-plane"], default="brownfield")
    init.add_argument("--risk", default="Q3")
    init.add_argument("--max-rounds", type=int, default=3)
    init.add_argument("--require-clean", action="store_true")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=create_run)

    status = sub.add_parser("status")
    status.add_argument("--run-id", required=True)
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=lambda args: inspect_run(args, fail_on_error=False))

    validate = sub.add_parser("validate")
    validate.add_argument("--run-id", required=True)
    validate.add_argument("--phase", choices=["scaffold", "contract", "complete"], default="scaffold")
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(func=lambda args: inspect_run(args, fail_on_error=True))
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
