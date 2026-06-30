#!/usr/bin/env python3
"""AgentBackend interface for the Cybernetic Ratchet Loop (architecture §12).

Pluggable LLM invocation for the Auditor / Implementer / Verifier stages. In
Phase 1 the ``StubBackend`` emits schema-valid canned audit output for
deterministic testing. Phase 2 adds real invocation backends while preserving
the core invariant: the backend proposes; deterministic validators dispose.

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
import hashlib
import json
import os
import shutil
import subprocess
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4


DEFAULT_DROID_PATH = "/Users/dhyana/.local/bin/droid"
DEFAULT_DROID_PRIMARY_MODEL = "glm-5.2"
DEFAULT_DROID_VERIFIER_MODEL = "gpt-5.2"

API_KEY_NAMES = (
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "GEMINI_API_KEY",
    "ANTHROPIC_API_KEY",
)


class BackendError(RuntimeError):
    """Base class for agent backend failures."""


class BackendUnavailableError(BackendError):
    """Raised when an explicitly selected backend cannot be launched."""


class BackendInvocationError(BackendError):
    """Raised when a backend invocation fails or returns unusable output."""

    def __init__(self, message: str, result: "AgentInvocationResult | None" = None) -> None:
        super().__init__(message)
        self.result = result


@dataclass
class AgentInvocationResult:
    """Receipt for one isolated agent role invocation."""

    invocation_id: str
    role: str
    model: str
    model_family: str
    command: list[str]
    cwd: str
    return_code: int
    stdout: str
    stderr: str
    prompt_sha256: str
    context_keys: list[str] = field(default_factory=list)
    started_utc: str = ""
    ended_utc: str = ""
    model_independence: str = "not_proven"
    degraded: bool = False

    def to_receipt(self) -> dict:
        return {
            "invocation_id": self.invocation_id,
            "role": self.role,
            "model": self.model,
            "model_family": self.model_family,
            "command": self.command,
            "cwd": self.cwd,
            "return_code": self.return_code,
            "prompt_sha256": self.prompt_sha256,
            "context_keys": self.context_keys,
            "started_utc": self.started_utc,
            "ended_utc": self.ended_utc,
            "model_independence": self.model_independence,
            "degraded": self.degraded,
            "stderr_excerpt": self.stderr[:500],
            "stdout_excerpt": self.stdout[:500],
        }


class AgentBackend(ABC):
    """Abstract base for LLM backends used by the loop stages."""

    def invoke(self, role: str, prompt: str, context: dict) -> AgentInvocationResult:
        """Invoke a role and return a receipt.

        Phase-1 custom test backends implement only ``audit``; this default
        keeps that interface backward-compatible.
        """
        raise NotImplementedError(f"{type(self).__name__} does not implement role invocation")

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


def _model_family(model: str) -> str:
    if model.startswith("custom:"):
        model = model.split(":", 1)[1]
    return model.split("-", 1)[0].split(".", 1)[0] or model


def _prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def _audit_prompt(prompt_id: str, council_id: str, prompt_text: str, context: dict) -> str:
    return (
        "ROLE: Auditor\n"
        "Return ONLY a JSON object conforming to schemas/expert_audit_output.schema.json.\n"
        f"prompt_id: {prompt_id}\n"
        f"council_id: {council_id}\n"
        "context_json:\n"
        f"{json.dumps(context, indent=2, sort_keys=True)}\n"
        "prompt_text:\n"
        f"{prompt_text}\n"
    )


def _json_from_stdout(stdout: str) -> dict:
    text = stdout.strip()
    if not text:
        raise ValueError("stdout was empty")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise


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
                    "evidence_refs": [0],
                }
            ],
            "not_proven": ["stub backend — no real audit performed"],
            "open_questions": [],
            "follow_up_issues": [],
        }

    def invoke(self, role: str, prompt: str, context: dict) -> AgentInvocationResult:
        now = _utc_now_iso()
        return AgentInvocationResult(
            invocation_id=f"stub-{uuid4().hex}",
            role=role,
            model="stub",
            model_family="stub",
            command=["stub"],
            cwd=str(context.get("repo_path", "")),
            return_code=0,
            stdout="stub invocation",
            stderr="",
            prompt_sha256=_prompt_hash(prompt),
            context_keys=sorted(context.keys()),
            started_utc=now,
            ended_utc=now,
            model_independence="not_proven",
        )


class DroidBackend(AgentBackend):
    """Backend that shells out to ``droid exec`` for isolated role invocations."""

    def __init__(
        self,
        droid_path: str | Path | None = None,
        cwd: str | Path | None = None,
        primary_model: str | None = None,
        verifier_model: str | None = None,
        timeout_seconds: int = 600,
        auto_level: str | None = None,
    ) -> None:
        self.droid_path = Path(droid_path or os.environ.get("LOOP_DROID_PATH", DEFAULT_DROID_PATH))
        self.cwd = Path(cwd or os.getcwd())
        self.primary_model = primary_model or os.environ.get(
            "LOOP_DROID_PRIMARY_MODEL", DEFAULT_DROID_PRIMARY_MODEL
        )
        self.verifier_model = verifier_model or os.environ.get(
            "LOOP_DROID_VERIFIER_MODEL", DEFAULT_DROID_VERIFIER_MODEL
        )
        self.timeout_seconds = timeout_seconds
        # The real droid CLI needs `--auto high` to proceed autonomously (medium
        # bails out with "insufficient permission to proceed"). Configurable via
        # the LOOP_DROID_AUTO_LEVEL env var; default `high` for live runs.
        self.auto_level = auto_level or os.environ.get("LOOP_DROID_AUTO_LEVEL", "high")

    def _resolve_droid(self) -> str:
        if self.droid_path.is_file() and os.access(self.droid_path, os.X_OK):
            return str(self.droid_path)
        if self.droid_path.exists():
            raise BackendUnavailableError(
                f"droid CLI path exists but is not executable at {self.droid_path}; "
                "no silent fallback to stub"
            )
        if str(self.droid_path) == DEFAULT_DROID_PATH:
            found = shutil.which("droid")
            if found:
                return found
        raise BackendUnavailableError(
            f"droid CLI unavailable at {self.droid_path}; no silent fallback to stub"
        )

    def _select_model(self, role: str, context: dict) -> tuple[str, str]:
        severity = str(context.get("severity", "")).lower()
        if role == "verifier" and severity in {"high", "critical"}:
            model = self.verifier_model
            independence = (
                "proven"
                if _model_family(model) != _model_family(self.primary_model)
                else "not_proven"
            )
            return model, independence
        return self.primary_model, "not_proven"

    def invoke(self, role: str, prompt: str, context: dict) -> AgentInvocationResult:
        droid = self._resolve_droid()
        model, model_independence = self._select_model(role, context)
        started = _utc_now_iso()
        invocation_id = f"droid-{role}-{uuid4().hex}"
        context_keys = sorted(context.keys())

        with NamedTemporaryFile("w", encoding="utf-8", suffix=".prompt", delete=True) as fh:
            fh.write(prompt)
            fh.flush()
            command = [
                droid,
                "exec",
                "--cwd",
                str(self.cwd),
                "--auto",
                self.auto_level,
                "--model",
                model,
                "--output-format",
                "text",
                "-f",
                fh.name,
            ]
            try:
                proc = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                timed_out = AgentInvocationResult(
                    invocation_id=invocation_id,
                    role=role,
                    model=model,
                    model_family=_model_family(model),
                    command=command,
                    cwd=str(self.cwd),
                    return_code=-1,
                    stdout=exc.stdout or "",
                    stderr=exc.stderr or "",
                    prompt_sha256=_prompt_hash(prompt),
                    context_keys=context_keys,
                    started_utc=started,
                    ended_utc=_utc_now_iso(),
                    model_independence=model_independence,
                    degraded=True,
                )
                raise BackendInvocationError(
                    f"droid CLI invocation timed out for role {role!r} "
                    f"after {self.timeout_seconds}s",
                    result=timed_out,
                ) from exc
            except OSError as exc:
                failed = AgentInvocationResult(
                    invocation_id=invocation_id,
                    role=role,
                    model=model,
                    model_family=_model_family(model),
                    command=command,
                    cwd=str(self.cwd),
                    return_code=-1,
                    stdout="",
                    stderr=str(exc),
                    prompt_sha256=_prompt_hash(prompt),
                    context_keys=context_keys,
                    started_utc=started,
                    ended_utc=_utc_now_iso(),
                    model_independence=model_independence,
                    degraded=True,
                )
                raise BackendInvocationError(
                    f"droid CLI could not launch for role {role!r}: {exc}",
                    result=failed,
                ) from exc

        result = AgentInvocationResult(
            invocation_id=invocation_id,
            role=role,
            model=model,
            model_family=_model_family(model),
            command=command,
            cwd=str(self.cwd),
            return_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            prompt_sha256=_prompt_hash(prompt),
            context_keys=context_keys,
            started_utc=started,
            ended_utc=_utc_now_iso(),
            model_independence=model_independence,
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            raise BackendInvocationError(
                f"droid CLI invocation failed for role {role!r} with exit {proc.returncode}: {detail}",
                result=result,
            )
        return result

    def audit(
        self,
        prompt_id: str,
        council_id: str,
        prompt_text: str,
        context: dict,
    ) -> dict:
        prompt = _audit_prompt(prompt_id, council_id, prompt_text, context)
        invocation = self.invoke("auditor", prompt, context)
        try:
            audit_doc = _json_from_stdout(invocation.stdout)
        except (json.JSONDecodeError, ValueError) as exc:
            raise BackendInvocationError(
                f"droid auditor did not return parseable audit JSON: {exc}",
                result=invocation,
            ) from exc
        return audit_doc


class ApiBackend(AgentBackend):
    """API backend placeholder that degrades gracefully when keyless."""

    def __init__(self, cwd: str | Path | None = None) -> None:
        self.cwd = Path(cwd or os.getcwd())

    def _present_keys(self) -> list[str]:
        return [name for name in API_KEY_NAMES if os.environ.get(name)]

    def invoke(self, role: str, prompt: str, context: dict) -> AgentInvocationResult:
        now = _utc_now_iso()
        keys = self._present_keys()
        if keys:
            stdout = "api backend live invocation is not enabled in this mission; use droid"
            return_code = 2
        else:
            stdout = "api backend keyless degradation: no API keys present; using deterministic fallback"
            return_code = 0
        return AgentInvocationResult(
            invocation_id=f"api-{role}-{uuid4().hex}",
            role=role,
            model="api-keyless" if not keys else "api-disabled",
            model_family="api",
            command=["api-backend", role],
            cwd=str(self.cwd),
            return_code=return_code,
            stdout=stdout,
            stderr="",
            prompt_sha256=_prompt_hash(prompt),
            context_keys=sorted(context.keys()),
            started_utc=now,
            ended_utc=now,
            model_independence="not_proven",
            degraded=True,
        )

    def audit(
        self,
        prompt_id: str,
        council_id: str,
        prompt_text: str,
        context: dict,
    ) -> dict:
        invocation = self.invoke(
            "auditor",
            _audit_prompt(prompt_id, council_id, prompt_text, context),
            context,
        )
        if invocation.return_code != 0:
            raise BackendInvocationError(invocation.stdout, result=invocation)
        audit_doc = StubBackend().audit(prompt_id, council_id, prompt_text, context)
        audit_doc["operator"] = "api-keyless-fallback"
        audit_doc["model"] = "api-keyless"
        audit_doc["not_proven"].append(
            "api backend keyless degradation — deterministic stub audit fallback used"
        )
        return audit_doc


def get_backend(name: str | None = None) -> AgentBackend:
    """Return the backend selected by ``name`` or the ``LOOP_AGENT_BACKEND`` env var.

    Default is ``stub``. Unknown / unimplemented backends raise a clear error
    (the caller maps it to a non-zero exit) — the loop never silently falls
    back to stub when a different backend was explicitly requested.
    """
    backend_name = name or os.environ.get("LOOP_AGENT_BACKEND", "stub")
    if backend_name == "stub":
        return StubBackend()
    if backend_name == "droid":
        return DroidBackend()
    if backend_name == "api":
        return ApiBackend()
    raise NotImplementedError(
        f"unknown agent backend {backend_name!r}; expected stub|droid|api"
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
    except (BackendError, NotImplementedError) as exc:
        sys.stderr.write(f"backend error: {exc}\n")
        return 2
    sys.stdout.write(f"backend: {type(backend).__name__}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
