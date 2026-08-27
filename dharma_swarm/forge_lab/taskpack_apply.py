"""Idempotent execution and receipt membrane for governed taskpack intake."""

from __future__ import annotations

import fcntl
import json
import os
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, cast

from dharma_swarm.forge_lab.state_io import (
    content_digest,
    dharma_home,
    forge_state_root,
    now_utc,
    safe_json,
    validate_digest,
    validate_safe_id,
    write_json_exclusive,
)
from dharma_swarm.forge_lab.taskpack_validation import ORACLE_SCHEMA, TaskpackError

INTENT_SCHEMA = "rsi_lab.taskpack_apply_intent.v1"
ACTION_SCHEMA = "rsi_lab.taskpack_action.v1"
_SECRET_KEYS = (
    "api_key",
    "apikey",
    "token",
    "secret",
    "password",
    "credential",
)
PlanBuilder = Callable[..., dict[str, Any]]
ImporterRunner = Callable[..., Any]


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _redact(value: Any, secrets: set[str] | None = None) -> Any:
    secrets = (
        secrets
        if secrets is not None
        else {
            item
            for key, item in os.environ.items()
            if len(item) >= 8 and any(part in key.lower() for part in _SECRET_KEYS)
        }
    )
    if isinstance(value, str):
        for secret in secrets:
            value = value.replace(secret, "[REDACTED_SECRET]")
        return value
    if isinstance(value, list):
        return [_redact(item, secrets) for item in value]
    if isinstance(value, dict):
        return {
            str(key): (
                "[REDACTED_SECRET]"
                if any(part in str(key).lower() for part in _SECRET_KEYS)
                else _redact(item, secrets)
            )
            for key, item in value.items()
        }
    return value


def _action_root() -> Path:
    state = forge_state_root()
    root = state / "taskpack_actions"
    if (
        state.is_symlink()
        or root.is_symlink()
        or not root.resolve(strict=False).is_relative_to(dharma_home())
    ):
        raise TaskpackError(
            "ACTION_ROOT_UNSAFE", "taskpack action root escaped DHARMA_HOME"
        )
    return root


@contextmanager
def _apply_lock() -> Iterator[None]:
    root = _action_root()
    existed = root.exists()
    try:
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not existed:
            os.chmod(root, 0o700)
            _fsync_directory(root.parent)
    except OSError as exc:
        raise TaskpackError("ACTION_ROOT_UNSAFE", str(exc)) from exc
    with (root / "apply.lock").open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise TaskpackError(
                "TASKPACK_BUSY", "another taskpack apply holds the lock"
            ) from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _checked_receipt(
    path: Path,
    request_id: str,
    plan_digest: str,
    schema: str,
    digest_field: str,
) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
        raise TaskpackError(
            "ACTION_RECEIPT_INVALID", f"unsafe taskpack evidence: {path}"
        )
    payload = safe_json(path)
    unsigned = {
        key: value for key, value in (payload or {}).items() if key != digest_field
    }
    if (
        not payload
        or payload.get("schema") != schema
        or payload.get("request_id") != request_id
        or payload.get("plan_digest") != plan_digest
        or payload.get(digest_field) != content_digest(unsigned)
    ):
        raise TaskpackError(
            "ACTION_RECEIPT_INVALID", f"invalid taskpack evidence: {path}"
        )
    return payload


def _apply_result(
    receipt: dict[str, Any],
    path: Path,
    *,
    replay: bool,
) -> dict[str, Any]:
    if receipt.get("status") != "succeeded":
        error = cast(Mapping[str, Any], receipt.get("error") or {})
        raise TaskpackError(
            str(error.get("code") or "IMPORTER_FAILED"),
            str(error.get("message") or "taskpack importer failed"),
            receipt_path=path,
        )
    return {
        "request_id": receipt["request_id"],
        "plan_digest": receipt["plan_digest"],
        "mode": receipt["mode"],
        "epistemic_modality": receipt["epistemic_modality"],
        "promotion_eligible": receipt["promotion_eligible"],
        "confirm_eligible": receipt["confirm_eligible"],
        "idempotent": replay,
        "receipt_path": str(path),
        "receipt": receipt,
    }


def _fresh_plan(claimed: Mapping[str, Any], builder: PlanBuilder) -> dict[str, Any]:
    try:
        manifest = claimed["manifest"]
        policy = claimed["policy"]
        source = claimed["execution_source"]
        return builder(
            manifest["path"],
            manifest_digest=manifest["digest"],
            model_cutoff=claimed["model_cutoff"],
            mode=claimed["mode"],
            taskbed_db=claimed["taskbed_db"],
            source=policy["source"],
            taskbed=policy["taskbed"],
            max_uses_per_epoch=policy["max_uses_per_epoch"],
            repo=Path(source["repo"]),
        )
    except TaskpackError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise TaskpackError("PLAN_INVALID", "invalid taskpack plan shape") from exc


def _importer_result_matches(
    result: Any,
    plan: Mapping[str, Any],
) -> bool:
    if not isinstance(result, dict):
        return False
    imported = result.get("imported_task_ids")
    skipped = result.get("skipped")
    row_count = plan["manifest"]["row_count"]
    return bool(
        isinstance(imported, list)
        and isinstance(skipped, list)
        and not skipped
        and all(isinstance(task_id, str) and task_id for task_id in imported)
        and len(set(imported)) == len(imported)
        and content_digest(imported) == plan["manifest"]["task_ids_digest"]
        and result.get("schema") == ORACLE_SCHEMA
        and result.get("source") == plan["policy"]["source"]
        and result.get("taskbed") == plan["policy"]["taskbed"]
        and result.get("model_cutoff") == plan["model_cutoff"]
        and result.get("input_count") == row_count
        and result.get("imported_count") == len(imported)
        and result.get("skipped_count") == len(skipped)
        and len(imported) == row_count
    )


def apply_taskpack_impl(
    plan: Mapping[str, Any],
    *,
    plan_digest: str,
    request_id: str,
    timeout_seconds: int,
    max_timeout_seconds: int,
    plan_builder: PlanBuilder,
    importer_runner: ImporterRunner,
    executable: str,
) -> dict[str, Any]:
    if (
        not isinstance(plan_digest, str)
        or not isinstance(request_id, str)
        or _redact(request_id) != request_id
    ):
        raise TaskpackError(
            "APPLY_REQUEST_INVALID", "digest and request_id must be strings"
        )
    try:
        validate_digest(plan_digest)
        validate_safe_id(request_id, field="request_id")
    except (TypeError, ValueError) as exc:
        raise TaskpackError("APPLY_REQUEST_INVALID", str(exc)) from exc
    if (
        not isinstance(timeout_seconds, int)
        or isinstance(timeout_seconds, bool)
        or not 1 <= timeout_seconds <= max_timeout_seconds
    ):
        raise TaskpackError(
            "TIMEOUT_INVALID",
            f"timeout_seconds must be between 1 and {max_timeout_seconds}",
        )

    claimed = dict(plan)
    unsigned = {key: value for key, value in claimed.items() if key != "plan_digest"}
    if claimed.get("plan_digest") != plan_digest:
        raise TaskpackError("PLAN_DIGEST_MISMATCH", "plan digest claim differs")
    if content_digest(unsigned) != plan_digest:
        raise TaskpackError("PLAN_TAMPERED", "plan content digest differs")
    fresh = _fresh_plan(claimed, plan_builder)
    if fresh != claimed:
        raise TaskpackError("PLAN_STALE", "plan no longer matches current bytes/source")

    root = _action_root()
    action_path = root / f"{request_id}.json"
    intent_path = root / f"{request_id}.intent.json"
    with _apply_lock():
        if action_path.exists():
            receipt = _checked_receipt(
                action_path,
                request_id,
                plan_digest,
                ACTION_SCHEMA,
                "action_digest",
            )
            return _apply_result(receipt, action_path, replay=True)
        if intent_path.exists():
            _checked_receipt(
                intent_path,
                request_id,
                plan_digest,
                INTENT_SCHEMA,
                "intent_digest",
            )
            raise TaskpackError(
                "APPLY_OUTCOME_UNKNOWN",
                "prior intent has no terminal receipt",
                receipt_path=intent_path,
            )

        intent_unsigned = {
            "schema": INTENT_SCHEMA,
            "request_id": request_id,
            "plan_digest": plan_digest,
            "mode": fresh["mode"],
            "manifest_digest": fresh["manifest"]["digest"],
            "source_commit": fresh["execution_source"]["commit"],
            "custody": fresh["custody"],
            "started_at": now_utc(),
        }
        try:
            write_json_exclusive(
                intent_path,
                {
                    **intent_unsigned,
                    "intent_digest": content_digest(intent_unsigned),
                },
            )
            _fsync_directory(root)
        except OSError as exc:
            raise TaskpackError(
                "INTENT_WRITE_FAILED",
                "taskpack importer was not started because intent durability failed",
                receipt_path=intent_path if intent_path.exists() else None,
            ) from exc

        status = "failed"
        result: dict[str, Any] | None = None
        returncode: int | None = None
        stderr = ""
        error: dict[str, str] | None = None
        try:
            env = {
                "PATH": (
                    f"{Path(executable).resolve().parent}:"
                    "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"
                ),
                "PYTHONPATH": fresh["execution_source"]["repo"],
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONNOUSERSITE": "1",
            }
            completed = importer_runner(
                fresh["importer_argv"],
                cwd=fresh["execution_source"]["repo"],
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=timeout_seconds,
            )
            returncode = completed.returncode
            stderr = completed.stderr[-4096:]
            if returncode:
                error = {
                    "code": "IMPORTER_FAILED",
                    "message": f"importer exited with code {returncode}",
                }
            else:
                try:
                    decoded = json.loads(completed.stdout)
                except json.JSONDecodeError as exc:
                    raise TaskpackError(
                        "IMPORTER_OUTPUT_INVALID", "importer output is not JSON"
                    ) from exc
                if not isinstance(decoded, dict):
                    raise TaskpackError(
                        "IMPORTER_OUTPUT_INVALID",
                        "importer output is not an object",
                    )
                if not _importer_result_matches(decoded, fresh):
                    raise TaskpackError(
                        "IMPORTER_RESULT_MISMATCH",
                        "importer result differs from plan",
                    )
                result = decoded
                status = "succeeded"
        except subprocess.TimeoutExpired:
            status = "timed_out"
            error = {
                "code": "IMPORTER_TIMEOUT",
                "message": f"importer exceeded {timeout_seconds} seconds",
            }
        except OSError:
            error = {
                "code": "IMPORTER_UNAVAILABLE",
                "message": "importer could not execute",
            }
        except TaskpackError as exc:
            error = {"code": exc.code, "message": str(exc)}

        action_unsigned = {
            "schema": ACTION_SCHEMA,
            "request_id": request_id,
            "plan_digest": plan_digest,
            "mode": fresh["mode"],
            "status": status,
            "manifest": {
                "digest": fresh["manifest"]["digest"],
                "row_count": fresh["manifest"]["row_count"],
            },
            "taskbed_db": fresh["taskbed_db"],
            "policy": fresh["policy"],
            "custody": fresh["custody"],
            "epistemic_modality": fresh["epistemic_modality"],
            "model_cutoff_authority": fresh["model_cutoff_authority"],
            "promotion_eligible": fresh["promotion_eligible"],
            "confirm_eligible": fresh["confirm_eligible"],
            "oracle_preflight": fresh["oracle_preflight"],
            "execution_source": fresh["execution_source"],
            "importer": fresh["importer"],
            "importer_argv_digest": content_digest(fresh["importer_argv"]),
            "importer_returncode": returncode,
            "importer_result": _redact(result),
            "stderr": _redact(stderr),
            "error": _redact(error),
            "finished_at": now_utc(),
        }
        receipt = {
            **action_unsigned,
            "action_digest": content_digest(action_unsigned),
        }
        try:
            write_json_exclusive(action_path, receipt)
            _fsync_directory(root)
        except OSError as exc:
            raise TaskpackError(
                "APPLY_OUTCOME_UNKNOWN",
                "importer completed but terminal action durability failed; inspect the "
                "intent and taskbed before any explicit replacement",
                receipt_path=intent_path,
            ) from exc
        return _apply_result(receipt, action_path, replay=False)


__all__ = [
    "ACTION_SCHEMA",
    "INTENT_SCHEMA",
    "apply_taskpack_impl",
]
