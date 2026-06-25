#!/usr/bin/env python3
"""AgentBackend interface for the Cybernetic Ratchet Loop (architecture §12).

Pluggable LLM invocation for the Auditor / Implementer / Verifier stages. In
Phase 1 only the ``StubBackend`` is implemented — it emits schema-valid canned
audit output for deterministic testing. The ``droid`` and ``api`` backends are
implemented in M2 (agent-backend-roles feature).

Backend selection is via the ``LOOP_AGENT_BACKEND`` environment variable
(``stub`` | ``droid`` | ``api``). The default is ``stub`` (deterministic).

Core Invariant: the backend's output is always validated by a deterministic
oracle (schema validation, exit codes) before it is accepted as truth. The
backend proposes; the deterministic oracle disposes.

Exit codes (CLI):
    0   backend selected and ready
    2   unknown / unimplemented backend requested
"""

from __future__ import annotations

import argparse
import os
import sys
from abc import ABC, abstractmethod
from datetime import datetime, timezone


class AgentBackend(ABC):
    """Abstract base for LLM backends used by the loop stages."""

    @abstractmethod
    def audit(
        self,
        prompt_id: str,
        council_id: str,
        prompt_text: str,
        context: dict,
    ) -> dict:
        """Produce an audit JSON dict for one prompt.

        ``context`` carries run-level fields (repo_path, git_ref, run_id, etc.)
        that the backend should stamp into the output.

        The returned dict MUST conform to ``schemas/expert_audit_output.schema.json``.
        The caller validates it before accepting — a schema-invalid return is a
        hard abort (exit 2), not a silent pass.
        """


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class StubBackend(AgentBackend):
    """Deterministic stub backend that emits schema-valid canned audit output.

    Always available. Produces a valid audit document with one canned finding
    (E2_tested, medium severity) so downstream triage has something to work
    with. The ``prompt_id`` and ``council_id`` are stamped from the invocation
    so each scoped prompt gets a distinct, identifiable artifact.
    """

    def audit(
        self,
        prompt_id: str,
        council_id: str,
        prompt_text: str,
        context: dict,
    ) -> dict:
        repo_path = context.get("repo_path", "/tmp/ds_loop")
        git_ref = context.get("git_ref", "ratchet/loop-phases-1-3")
        run_id = context.get("run_id", "")
        return {
            "prompt_id": prompt_id,
            "council_id": council_id,
            "run_id": run_id,
            "operator": "stub",
            "model": "stub",
            "repo_path": repo_path,
            "git_ref": git_ref,
            "timestamp_utc": _utc_now_iso(),
            "mode": "weekly",
            "scope": {
                "files_examined": [],
                "commands_run": [
                    {
                        "command": "pytest --collect-only -q",
                        "cwd": repo_path,
                        "exit_code": 0,
                        "key_output": "stub: collection ok",
                    }
                ],
                "commands_not_run": [
                    {"command": "pytest -x", "reason": "stub backend — no real commands run"}
                ],
            },
            "summary": {
                "verdict": "warn",
                "confidence": "medium",
                "evidence_floor": "E2_tested",
            },
            "findings": [
                {
                    "id": f"F-{prompt_id}-001",
                    "title": f"Stub finding for {prompt_id}",
                    "severity": "medium",
                    "evidence_level": "E2_tested",
                    "confidence": "medium",
                    "files": [],
                    "line_refs": [],
                    "observed": "stub backend canned observation",
                    "inferred": "stub backend canned inference",
                    "risk": "stub: no real risk assessed",
                    "failure_class": "STUB_FINDING",
                    "recommendation": "stub: replace with real auditor output in M2",
                    "verification": "stub: validate via schema + downstream gates",
                }
            ],
            "not_proven": ["stub backend — no real audit performed"],
            "open_questions": [],
            "follow_up_issues": [],
        }


def get_backend(name: str | None = None) -> AgentBackend:
    """Return the backend selected by ``name`` or the ``LOOP_AGENT_BACKEND`` env var.

    Default is ``stub``. Unknown / unimplemented backends raise a clear error
    (the caller maps it to a non-zero exit) — the loop never silently falls
    back to stub when a different backend was explicitly requested.
    """
    backend_name = name or os.environ.get("LOOP_AGENT_BACKEND", "stub")
    if backend_name == "stub":
        return StubBackend()
    raise NotImplementedError(
        f"agent backend {backend_name!r} is not implemented in Phase 1 "
        f"(stub|droid|api; droid/api arrive in M2). Set LOOP_AGENT_BACKEND=stub for deterministic testing."
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Select and report the agent backend for the Cybernetic Ratchet Loop.",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="backend name (stub|droid|api); defaults to LOOP_AGENT_BACKEND env or stub",
    )
    args = parser.parse_args(argv)
    try:
        backend = get_backend(args.name)
    except NotImplementedError as exc:
        sys.stderr.write(f"backend error: {exc}\n")
        return 2
    sys.stdout.write(f"backend: {type(backend).__name__}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
