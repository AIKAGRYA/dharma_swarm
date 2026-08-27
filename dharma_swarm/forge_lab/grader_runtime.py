"""Custody and compatibility checks for the admitted SWE-bench evaluator."""

from __future__ import annotations

import csv
import hashlib
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
from typing import Any

from dharma_swarm.forge_lab.grader_isolation import (
    SUPPORTED_LINUX_RUNTIME_RECORD_DIGESTS,
    SUPPORTED_SWEBENCH_VERSION,
)

SUPPORTED_LINUX_RUNTIME_TREE_DIGESTS = {
    "swebench": "sha256:addf0f4b38b5e2e55b4670aa38f0953a1ae76f188701b8fc48d902dab84d666d",
    "docker": "sha256:b9d3c27ff1c365dbf142849d8d7b54011a2619510e5d0571ec47c19322ff183e",
    "datasets": "sha256:2ea94f915a6b08930affd88317609fa35d780983ff6a631d67618ce0515f6b96",
}


def _distribution_tree_digest(record: Path, import_root: Path) -> tuple[str, int]:
    """Hash every installed file named by RECORD within the dedicated venv."""

    try:
        venv_root = import_root.parents[2]
    except IndexError as exc:
        raise ValueError("invalid site-packages anchor") from exc
    checked: set[Path] = set()

    def require_host_owned(path: Path) -> None:
        if path in checked:
            return
        metadata = path.stat()
        if metadata.st_mode & 0o022:
            raise ValueError("runtime path is group/world writable")
        if hasattr(os, "geteuid") and os.geteuid() == 0 and metadata.st_uid != 0:
            raise ValueError("runtime path is not root owned")
        checked.add(path)

    for anchor in (
        venv_root.parent,
        venv_root,
        import_root.parents[1],
        import_root.parent,
        import_root,
    ):
        require_host_owned(anchor)
    mapping: dict[str, str] = {}
    with record.open(encoding="utf-8", newline="") as handle:
        for row in csv.reader(handle):
            if not row or not row[0] or row[0] in mapping:
                raise ValueError("invalid or duplicate RECORD path")
            path = (import_root / row[0]).resolve(strict=True)
            if not path.is_relative_to(venv_root) or not path.is_file():
                raise ValueError("RECORD path escaped the dedicated runtime")
            require_host_owned(path)
            for parent in path.parents:
                if not parent.is_relative_to(venv_root):
                    break
                require_host_owned(parent)
            mapping[row[0]] = hashlib.sha256(path.read_bytes()).hexdigest()
    if not mapping:
        raise ValueError("empty RECORD")
    canonical = json.dumps(
        mapping,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest(), len(mapping)


def swebench_runtime_readiness() -> dict[str, Any]:
    """Prove the Python evaluator APIs exist under the admitted runtime root."""

    configured = os.environ.get("RSI_LAB_SWEBENCH_PYDEPS", "").strip()
    dedicated_required = (
        os.environ.get("RSI_LAB_REQUIRE_SWEBENCH_PYDEPS", "").strip() == "1"
    )
    reasons: list[str] = []
    if dedicated_required and not configured:
        reasons.append("swebench_runtime_dedicated_required")
    modules: dict[str, Any] = {}
    run_evaluation: Any | None = None
    version: str | None = None
    import_error_class: str | None = None
    try:
        modules = {
            name: importlib.import_module(name)
            for name in ("swebench", "docker", "datasets")
        }
        run_evaluation = importlib.import_module("swebench.harness.run_evaluation")
        version = importlib.metadata.version("swebench")
    except Exception as exc:
        import_error_class = type(exc).__name__
        reasons.append("swebench_runtime_import_failed")

    required_apis = (
        "build_container",
        "cleanup_container",
        "copy_to_container",
        "exec_run_with_timeout",
        "make_test_spec",
        "main",
    )
    api_compatible = bool(
        run_evaluation is not None
        and all(callable(getattr(run_evaluation, name, None)) for name in required_apis)
    )
    if run_evaluation is not None and not api_compatible:
        reasons.append("swebench_runtime_api_incompatible")
    if version is not None and version != SUPPORTED_SWEBENCH_VERSION:
        reasons.append("swebench_runtime_version_unsupported")

    origins: dict[str, str] = {}
    for name, module in {**modules, "run_evaluation": run_evaluation}.items():
        origin = getattr(module, "__file__", None)
        if origin:
            origins[name] = str(Path(origin).resolve(strict=False))

    import_root: Path | None = None
    if configured:
        try:
            import_root = Path(configured).expanduser().resolve(strict=True)
        except OSError:
            reasons.append("swebench_runtime_anchor_missing")
        if import_root is not None:
            anchor_stat = import_root.stat()
            if anchor_stat.st_mode & 0o022:
                reasons.append("swebench_runtime_anchor_writable")
            if hasattr(os, "geteuid") and os.geteuid() == 0 and anchor_stat.st_uid != 0:
                reasons.append("swebench_runtime_anchor_not_root_owned")
            if set(origins) != {
                "swebench",
                "docker",
                "datasets",
                "run_evaluation",
            } or any(
                not Path(origin).is_relative_to(import_root)
                for origin in origins.values()
            ):
                reasons.append("swebench_runtime_import_escaped_anchor")

    record_digests: dict[str, str] = {}
    record_origins: dict[str, str] = {}
    tree_digests: dict[str, str] = {}
    tree_file_counts: dict[str, int] = {}
    if configured:
        for name, expected in SUPPORTED_LINUX_RUNTIME_RECORD_DIGESTS.items():
            try:
                record = (
                    Path(importlib.metadata.distribution(name)._path) / "RECORD"
                ).resolve(strict=True)
                digest = "sha256:" + hashlib.sha256(record.read_bytes()).hexdigest()
            except (OSError, importlib.metadata.PackageNotFoundError):
                reasons.append(f"swebench_runtime_{name}_record_missing")
                continue
            record_origins[name] = str(record)
            if import_root is not None and not record.is_relative_to(import_root):
                reasons.append(f"swebench_runtime_{name}_record_escaped_anchor")
            record_digests[name] = digest
            if digest != expected:
                reasons.append(f"swebench_runtime_{name}_record_mismatch")
            if import_root is None:
                continue
            try:
                tree_digest, file_count = _distribution_tree_digest(
                    record,
                    import_root,
                )
            except (OSError, UnicodeError, csv.Error, ValueError):
                reasons.append(f"swebench_runtime_{name}_tree_invalid")
                continue
            tree_digests[name] = tree_digest
            tree_file_counts[name] = file_count
            if tree_digest != SUPPORTED_LINUX_RUNTIME_TREE_DIGESTS[name]:
                reasons.append(f"swebench_runtime_{name}_tree_mismatch")

    return {
        "ready": not reasons and api_compatible,
        "configured_import_root": configured or None,
        "dedicated_runtime_required": dedicated_required,
        "version": version,
        "supported_version": SUPPORTED_SWEBENCH_VERSION,
        "api_compatible": api_compatible,
        "module_origins": origins,
        "record_digests": record_digests,
        "record_origins": record_origins,
        "tree_digests": tree_digests,
        "tree_file_counts": tree_file_counts,
        "import_error_class": import_error_class,
        "reasons": reasons,
    }


__all__ = [
    "SUPPORTED_LINUX_RUNTIME_RECORD_DIGESTS",
    "SUPPORTED_LINUX_RUNTIME_TREE_DIGESTS",
    "SUPPORTED_SWEBENCH_VERSION",
    "swebench_runtime_readiness",
]
