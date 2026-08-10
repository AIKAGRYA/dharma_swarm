"""Host-local status, anchors, and verification for RSI Lab releases."""

from __future__ import annotations

import json
import os
from pathlib import Path
import platform
from typing import Any

from dharma_swarm.forge_lab.sync_identity import (
    RELEASE_SCHEMA,
    SyncError,
    _checkout_identity,
    _identity_mismatches,
    _now,
    _run,
    default_local_root,
    validate_plan,
)


LEGACY_MUTATING_LAUNCHERS = (
    "rsi-run",
    "rsi-loop",
    "rsi-fix-substrate",
    "rsi-keys-refresh",
)
MEGHADHARMA_LEGACY_MUTATING_LAUNCHERS = (
    "rsi-env",
    "rsi-update-main",
)


def _path_present(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _current_target(root: Path) -> Path | None:
    current = root / "current"
    if not current.is_symlink():
        return None
    try:
        return current.resolve(strict=True)
    except OSError:
        return None


def _current_commit(root: Path) -> str | None:
    target = _current_target(root)
    if target is None or not (target / "repo" / ".git").exists():
        return None
    try:
        return _checkout_identity(target / "repo")["commit"]
    except SyncError:
        return None


def _entrypoint_dir(root: Path, node: str) -> Path:
    if node == "mac" and root == default_local_root().expanduser().resolve():
        return Path.home() / ".dharma" / "bin"
    return root / "bin"


def legacy_mutating_launchers(node: str) -> tuple[str, ...]:
    """Return only launchers that can mutate source/state or spend budget."""

    if node == "meghadharma":
        return (*LEGACY_MUTATING_LAUNCHERS, *MEGHADHARMA_LEGACY_MUTATING_LAUNCHERS)
    return LEGACY_MUTATING_LAUNCHERS


def _launcher_hygiene(
    root: Path,
    target: Path | None,
    *,
    node: str,
) -> dict[str, Any]:
    entrypoints = _entrypoint_dir(root, node)
    if target is None:
        return {
            "ok": False,
            "entrypoint_dir": str(entrypoints),
            "retired_target": None,
            "launchers": {},
            "errors": ["legacy launcher hygiene cannot be verified without current release"],
        }
    retired = target / "repo" / "scripts" / "forge_lab" / "rsi-legacy-retired"
    errors: list[str] = []
    launchers: dict[str, dict[str, Any]] = {}
    if not retired.is_file():
        errors.append(f"canonical legacy retirement stub is absent: {retired}")
    for name in legacy_mutating_launchers(node):
        path = entrypoints / name
        is_symlink = path.is_symlink()
        resolved = str(path.resolve(strict=False)) if is_symlink else None
        correct = bool(
            retired.is_file()
            and is_symlink
            and path.resolve(strict=False) == retired.resolve(strict=False)
        )
        launchers[name] = {
            "path": str(path),
            "is_symlink": is_symlink,
            "resolved": resolved,
            "retired": correct,
        }
        if not correct:
            errors.append(f"legacy mutating launcher is not retired: {path}")
    return {
        "ok": not errors,
        "entrypoint_dir": str(entrypoints),
        "retired_target": str(retired),
        "launchers": launchers,
        "errors": errors,
    }


def _runtime_fingerprint(release: Path | None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "node_python_version": platform.python_version(),
        "os": platform.system().lower(),
        "machine": platform.machine().lower(),
    }
    if release is None:
        result.update(
            {
                "python_executable": None,
                "python_version": None,
                "python_compatible": False,
            }
        )
        return result
    python = release / ".venv" / "bin" / "python"
    result["python_executable"] = str(python.resolve()) if python.exists() else None
    if not python.exists():
        result.update({"python_version": None, "python_compatible": False})
        return result
    try:
        version = _run(
            [str(python), "-c", "import platform; print(platform.python_version())"],
            timeout=15,
        ).stdout.strip()
    except SyncError as exc:
        result.update(
            {
                "python_version": None,
                "python_compatible": False,
                "runtime_error": str(exc),
            }
        )
        return result
    parts = tuple(int(item) for item in version.split(".")[:2])
    result.update({"python_version": version, "python_compatible": parts >= (3, 11)})
    return result


def node_status(root: Path, *, node: str) -> dict[str, Any]:
    root = root.expanduser().resolve()
    target = _current_target(root)
    identity: dict[str, Any] | None = None
    release_manifest: dict[str, Any] | None = None
    errors: list[str] = []
    if target is None:
        errors.append("current release is missing or is not an atomic symlink")
    else:
        try:
            identity = _checkout_identity(target / "repo")
        except (OSError, SyncError) as exc:
            errors.append(str(exc))
        manifest_path = target / "RELEASE_MANIFEST.json"
        if manifest_path.is_file():
            try:
                loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
                if (
                    not isinstance(loaded, dict)
                    or loaded.get("schema") != RELEASE_SCHEMA
                ):
                    raise SyncError(
                        "RELEASE_MANIFEST_MISMATCH", "unsupported release manifest"
                    )
                embedded = validate_plan(loaded.get("plan", {}))
                if loaded.get("plan_digest") != embedded["plan_digest"]:
                    raise SyncError(
                        "RELEASE_MANIFEST_MISMATCH", "release plan digest disagrees"
                    )
                if identity and embedded["commit"] != identity["commit"]:
                    raise SyncError(
                        "RELEASE_MANIFEST_MISMATCH", "release commit disagrees"
                    )
                release_manifest = loaded
            except (OSError, json.JSONDecodeError, SyncError) as exc:
                errors.append(f"release manifest unreadable: {exc}")
        else:
            errors.append("release manifest is absent")
    anchors = {
        "state": _path_present(root / "state"),
        "runtime_venv": _path_present(root / "runtime" / ".venv"),
        "runtime_pydeps": _path_present(root / "runtime" / "pydeps"),
        "secrets": _path_present(root / "secrets"),
    }
    launcher_hygiene = _launcher_hygiene(root, target, node=node)
    errors.extend(launcher_hygiene["errors"])
    return {
        "schema": "rsi_lab.node_status.v1",
        "node": node,
        "root": str(root),
        "current_target": str(target) if target else None,
        "identity": identity,
        "release_manifest_digest": (
            release_manifest.get("plan_digest") if release_manifest else None
        ),
        "anchors": anchors,
        "launcher_hygiene": launcher_hygiene,
        "runtime": _runtime_fingerprint(target),
        "ready": bool(
            target
            and identity
            and release_manifest
            and identity.get("repo_clean")
            and anchors["state"]
            and anchors["runtime_venv"]
            and anchors["runtime_pydeps"]
            and launcher_hygiene["ok"]
        ),
        "errors": errors,
    }


def _safe_symlink(target: Path, link: Path) -> None:
    if _path_present(link):
        if link.is_symlink() and link.resolve(strict=False) == target.resolve(
            strict=False
        ):
            return
        raise SyncError(
            "ANCHOR_CONFLICT", f"refusing to replace existing anchor: {link}"
        )
    link.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(str(target), str(link), target_is_directory=True)


def _stabilize_anchors(root: Path, *, node: str, local_venv: Path | None) -> None:
    root.mkdir(parents=True, exist_ok=True)
    previous = _current_target(root)

    state = root / "state"
    if not _path_present(state):
        previous_state = previous / "state" if previous else None
        if previous_state and previous_state.exists():
            _safe_symlink(previous_state.resolve(), state)
        else:
            state.mkdir(parents=True)

    runtime = root / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    venv = runtime / ".venv"
    if not _path_present(venv):
        previous_venv = previous / ".venv" if previous else None
        source = local_venv if local_venv and local_venv.exists() else previous_venv
        if source is None or not source.exists():
            raise SyncError(
                "RUNTIME_MISSING", "no compatible Python environment is available"
            )
        _safe_symlink(source.resolve(), venv)
    if not (venv / "bin" / "python").exists():
        raise SyncError("RUNTIME_MISSING", f"runtime Python is absent under {venv}")

    pydeps = runtime / "pydeps"
    if not _path_present(pydeps):
        previous_pydeps = previous / "pydeps" if previous else None
        if previous_pydeps and previous_pydeps.exists():
            _safe_symlink(previous_pydeps.resolve(), pydeps)
        else:
            pydeps.mkdir(parents=True)

    if node == "meghadharma" and not _path_present(root / "secrets"):
        recovery_secrets = root / "current-main" / "secrets"
        if recovery_secrets.exists():
            _safe_symlink(recovery_secrets.resolve(), root / "secrets")


def _ensure_release_links(release: Path, root: Path) -> None:
    for name, target in (
        ("state", root / "state"),
        (".venv", root / "runtime" / ".venv"),
        ("pydeps", root / "runtime" / "pydeps"),
    ):
        link = release / name
        if _path_present(link):
            if link.is_symlink() and link.resolve(strict=False) == target.resolve(
                strict=False
            ):
                continue
            raise SyncError(
                "RELEASE_INVALID", f"release runtime link conflicts: {link}"
            )
        os.symlink(str(target), str(link), target_is_directory=True)
    if _path_present(root / "secrets"):
        _safe_symlink(root / "secrets", release / "secrets")


def _verify_release(release: Path, plan: dict[str, Any]) -> dict[str, Any]:
    identity = _checkout_identity(release / "repo")
    mismatches = _identity_mismatches(identity, plan)
    if mismatches:
        raise SyncError(
            "RELEASE_IDENTITY_MISMATCH",
            f"release does not match plan fields: {', '.join(mismatches)}",
        )
    runtime = _runtime_fingerprint(release)
    if not runtime.get("python_compatible"):
        raise SyncError("RUNTIME_INCOMPATIBLE", "release requires Python 3.11 or newer")
    return {"identity": identity, "runtime": runtime}


def _run_offline_verification(
    release: Path, root: Path, plan: dict[str, Any]
) -> dict[str, Any]:
    python = release / ".venv" / "bin" / "python"
    repo = release / "repo"
    pydeps = release / "pydeps"
    env = os.environ.copy()
    env.update(
        {
            "DHARMA_HOME": str(root / "state" / ".dharma"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": os.pathsep.join(
                item
                for item in (str(repo), str(pydeps), env.get("PYTHONPATH", ""))
                if item
            ),
            "RSI_LAB_BASE": str(release),
            "RSI_LAB_REPO": str(repo),
            "RSI_LAB_PYTHON": str(python),
            "RSI_LAB_PYDEPS": str(pydeps),
            "RSI_LAB_STATE": str(root / "state"),
        }
    )
    started = _now()
    result = _run(
        [
            str(python),
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            *plan["verification_tests"],
        ],
        cwd=repo,
        env=env,
        timeout=900,
    )
    final_identity = _checkout_identity(repo)
    if not final_identity["repo_clean"]:
        raise SyncError(
            "VERIFICATION_DIRTIED_RELEASE",
            "offline tests changed the immutable checkout",
        )
    return {
        "started_at": started,
        "completed_at": _now(),
        "command": "python -m pytest -q -p no:cacheprovider "
        + " ".join(plan["verification_tests"]),
        "stdout_tail": result.stdout.strip()[-1200:],
        "network_or_provider_calls": False,
    }
