#!/usr/bin/env python3
"""Stage 1 — prompt-audit-run (Auditor) for the Cybernetic Ratchet Loop.

Reads a warrant + scope.json, invokes the Auditor for each scoped prompt, and
writes one audit JSON per prompt to ``runs/<run_id>/audit/<prompt_id>.json``.

In Phase 1 the Auditor is invoked via the stub/emit-and-capture backend
(``LOOP_AGENT_BACKEND=stub``). Full agent backends (droid, api) arrive in M2.

Every audit output is validated against ``schemas/expert_audit_output.schema.json``
via ``loop/validate_audit.py`` BEFORE it is written. A schema-invalid output is a
hard abort (exit 2): no partial artifact is written for the invalid prompt. An
audit with zero findings (``findings: []``) is valid — the run continues.

The warrant is re-validated on stage entry (``Warrant.load_and_check``); an
expired or invalid warrant aborts the run before any prompt is audited.

Usage:
    python3 scripts/governance/loop/prompt_audit_run.py --warrant <warrant.yaml> --run-id <run_id> \\
        [--scope <scope.json>] [--backend stub]

Exit codes:
    0   all scoped prompts produced schema-valid audit JSON
    2   warrant invalid/expired, scope unreadable, or a schema-invalid audit output (hard abort)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts.governance.loop.agent_backend import AgentBackend, BackendError, get_backend
from scripts.governance.loop.councils import resolve_prompt_path
from scripts.governance.loop.runs import Run, RunManager
from scripts.governance.loop.scoper import prompt_to_council
from scripts.governance.loop.validate_audit import validate_audit_doc
from scripts.governance.loop.warrant import Warrant, WarrantError


def _emit_error(message: str) -> int:
    sys.stderr.write(message + "\n")
    return 2


def _load_scope(scope_path: Path) -> dict:
    if not scope_path.is_file():
        raise FileNotFoundError(f"scope file not found: {scope_path}")
    return json.loads(scope_path.read_text())


def _resolve_prompt_text(prompt_id: str, council_id: str, repo_root: Path) -> str:
    """Read the prompt text from the ported PROMPTS.md (best-effort)."""
    path = resolve_prompt_path(council_id, prompt_id, repo_root=repo_root)
    if path is None or not path.is_file():
        return ""
    return path.read_text()


def run_audit(
    warrant_path: Path,
    run: Run,
    scope: dict,
    backend: AgentBackend,
    repo_root: Path | None = None,
) -> int:
    """Run Stage 1 for all scoped prompts.

    Returns 0 if every prompt produced schema-valid audit JSON, or 2 on the
    first schema-invalid output (hard abort — no artifact written for the
    invalid prompt).
    """
    root = repo_root or Path(__file__).resolve().parents[3]

    # Re-validate the warrant on stage entry (expiry, structural validity).
    try:
        warrant = Warrant.load_and_check(warrant_path)
    except WarrantError as exc:
        return _emit_error(f"warrant stage-entry refused: {exc}")

    selected = scope.get("selected_prompt_ids", [])
    if not selected:
        sys.stdout.write("no prompts selected — nothing to audit\n")
        return 0

    context = {
        "repo_path": str(root),
        "git_ref": warrant.scope.get("head_ref", ""),
        "run_id": run.run_id,
        "warrant_id": warrant.id,
    }

    written = 0
    for prompt_id in selected:
        council_id = prompt_to_council(prompt_id)
        if council_id is None:
            return _emit_error(
                f"cannot resolve council for prompt {prompt_id!r} — unknown prefix"
            )
        prompt_text = _resolve_prompt_text(prompt_id, council_id, root)

        try:
            audit_doc = backend.audit(prompt_id, council_id, prompt_text, dict(context))
        except BackendError as exc:
            return _emit_error(
                f"auditor backend failed for prompt {prompt_id!r} — hard abort (exit 2). "
                f"Error: {exc}"
            )

        # Hard gate: validate BEFORE writing. Schema-invalid = abort, no artifact.
        result = validate_audit_doc(audit_doc, repo_root=root)
        if not result.valid:
            errs = json.dumps(result.errors, sort_keys=True)
            return _emit_error(
                f"schema-invalid audit output for prompt {prompt_id!r} — hard abort (exit 2). "
                f"Errors: {errs}"
            )

        audit_path = run.audit_path(prompt_id)
        run.write_json(audit_path, audit_doc)
        written += 1
        sys.stdout.write(f"audit ok: {prompt_id} -> {audit_path}\n")

    sys.stdout.write(f"prompt-audit-run complete: {written}/{len(selected)} prompts audited\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stage 1 (Auditor): produce per-prompt audit JSON for scoped prompts.",
    )
    parser.add_argument("--warrant", required=True, help="path to the warrant YAML file")
    parser.add_argument("--run-id", required=True, help="the run id (locates the run dir)")
    parser.add_argument(
        "--scope",
        default=None,
        help="path to scope.json (defaults to <run_dir>/scope.json)",
    )
    parser.add_argument(
        "--backend",
        default=None,
        help="agent backend name (stub|droid|api); defaults to LOOP_AGENT_BACKEND env or stub",
    )
    args = parser.parse_args(argv)

    warrant_path = Path(args.warrant)

    # Select the backend (env var or explicit --backend).
    try:
        backend = get_backend(args.backend)
    except (BackendError, NotImplementedError) as exc:
        return _emit_error(f"backend selection failed: {exc}")

    # Open the run dir.
    try:
        run = RunManager.open_run(args.run_id)
    except FileNotFoundError as exc:
        return _emit_error(str(exc))

    # Load scope.json (explicit path or run dir default).
    scope_path = Path(args.scope) if args.scope else run.scope_path()
    try:
        scope = _load_scope(scope_path)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        return _emit_error(f"scope load failed: {exc}")

    return run_audit(warrant_path, run, scope, backend)


if __name__ == "__main__":
    sys.exit(main())
