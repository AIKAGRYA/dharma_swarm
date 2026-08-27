"""Host-local status, anchors, and verification for RSI Lab releases."""

from __future__ import annotations

import json
import os
from pathlib import Path
import platform
from typing import Any

from dharma_swarm.forge_lab.sync_identity import (
    DEFAULT_REMOTE_ROOT,
    RELEASE_SCHEMA,
    SyncError,
    _checkout_identity,
    _identity_mismatches,
    _now,
    _run,
    validate_plan,
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
        "runtime": _runtime_fingerprint(target),
        "ready": bool(
            target
            and identity
            and release_manifest
            and identity.get("repo_clean")
            and anchors["state"]
            and anchors["runtime_venv"]
            and anchors["runtime_pydeps"]
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


def _python_abi(python: Path) -> str:
    try:
        abi = _run(
            [
                str(python),
                "-I",
                "-c",
                "import sys; print(f'python{sys.version_info.major}.{sys.version_info.minor}')",
            ],
            timeout=15,
        ).stdout.strip()
    except SyncError as exc:
        raise SyncError(
            "RUNTIME_INCOMPATIBLE",
            "unable to establish the Python ABI for the SWE-bench runtime",
        ) from exc
    if not abi.startswith("python") or not abi[6:].replace(".", "", 1).isdigit():
        raise SyncError("RUNTIME_INCOMPATIBLE", "invalid Python ABI marker")
    return abi


def _swebench_import_root(root: Path, *, release_python: Path) -> Path | None:
    """Return the ABI-bound host SWE-bench site-packages root, if provisioned."""

    venv = root / "runtime" / "swebench-venv"
    if not venv.is_dir():
        return None
    runtime_python = venv / "bin" / "python"
    if not runtime_python.exists():
        raise SyncError(
            "RUNTIME_INCOMPATIBLE",
            "SWE-bench runtime Python is missing",
        )
    release_abi = _python_abi(release_python)
    if _python_abi(runtime_python) != release_abi:
        raise SyncError(
            "RUNTIME_INCOMPATIBLE",
            "SWE-bench and release Python ABIs disagree",
        )
    expected = venv / "lib" / release_abi / "site-packages"
    candidates = [
        path.resolve()
        for path in sorted((venv / "lib").glob("python*/site-packages"))
        if all((path / package).is_dir() for package in ("swebench", "docker", "datasets"))
    ]
    if (
        len(candidates) != 1
        or candidates[0] != expected.resolve(strict=False)
        or not candidates[0].is_relative_to(venv.resolve())
    ):
        raise SyncError(
            "RUNTIME_INCOMPATIBLE",
            "SWE-bench runtime must expose one venv-owned site-packages root",
        )
    return candidates[0]


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
    swebench_pydeps = _swebench_import_root(root, release_python=python)
    runtime_required = bool(
        platform.system() == "Linux"
        and root.resolve() == DEFAULT_REMOTE_ROOT.resolve()
    )
    if runtime_required and swebench_pydeps is None:
        raise SyncError(
            "RUNTIME_INCOMPATIBLE",
            "canonical Linux activation requires the dedicated SWE-bench runtime",
        )
    env = os.environ.copy()
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONINSPECT", None)
    env.update(
        {
            "DHARMA_HOME": str(root / "state" / ".dharma"),
            "HF_DATASETS_OFFLINE": "1",
            "HF_HUB_OFFLINE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "PYTHONPATH": os.pathsep.join(
                item
                for item in (
                    str(repo),
                    str(pydeps),
                    str(swebench_pydeps) if swebench_pydeps else "",
                )
                if item
            ),
            "RSI_LAB_BASE": str(release),
            "RSI_LAB_REPO": str(repo),
            "RSI_LAB_PYTHON": str(python),
            "RSI_LAB_PYDEPS": str(pydeps),
            "RSI_LAB_SWEBENCH_PYDEPS": (
                str(swebench_pydeps) if swebench_pydeps else ""
            ),
            "RSI_LAB_REQUIRE_SWEBENCH_PYDEPS": "1" if runtime_required else "0",
            "RSI_LAB_STATE": str(root / "state"),
        }
    )
    started = _now()
    runtime_smoke = _run(
        [
            str(python),
            "-c",
            (
                "import json,sys; "
                "from dharma_swarm.forge_lab.operator_views import "
                "swebench_runtime_readiness as check; "
                "result=check(); print(json.dumps(result,sort_keys=True)); "
                "sys.exit(0 if result['ready'] else 9)"
            ),
        ],
        cwd=repo,
        env=env,
        timeout=60,
    )
    runtime_result = json.loads(runtime_smoke.stdout)
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
        "swebench_runtime": {
            "ready": True,
            "version": runtime_result["version"],
            "import_root": str(swebench_pydeps) if swebench_pydeps else None,
            "record_digests": runtime_result["record_digests"],
            "tree_digests": runtime_result["tree_digests"],
            "tree_file_counts": runtime_result["tree_file_counts"],
            "network_or_provider_calls": False,
        },
        "network_or_provider_calls": False,
    }
