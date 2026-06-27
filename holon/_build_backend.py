"""Minimal local PEP 517 backend for holon-runtime.

This avoids a build-time dependency on setuptools in isolated operator
environments. It builds a pure-Python wheel for the package layout used in this
repo-within-repo directory.
"""

from __future__ import annotations

import base64
import hashlib
import os
import zipfile
from pathlib import Path

NAME = "holon-runtime"
NORMALIZED = "holon_runtime"
VERSION = "0.1.0"
DIST_INFO = f"{NORMALIZED}-{VERSION}.dist-info"


def get_requires_for_build_wheel(config_settings=None):  # noqa: D401
    return []


def prepare_metadata_for_build_wheel(metadata_directory, config_settings=None):
    dist_info = Path(metadata_directory) / DIST_INFO
    dist_info.mkdir(parents=True, exist_ok=True)
    _write_metadata(dist_info)
    return DIST_INFO


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    wheel_name = f"{NORMALIZED}-{VERSION}-py3-none-any.whl"
    wheel_path = Path(wheel_directory) / wheel_name
    root = Path(__file__).resolve().parent
    records: list[tuple[str, bytes]] = []
    with zipfile.ZipFile(wheel_path, "w", compression=zipfile.ZIP_DEFLATED) as wheel:
        for source in _package_files(root):
            archive = "holon/" + source.relative_to(root).as_posix()
            data = source.read_bytes()
            wheel.writestr(archive, data)
            records.append((archive, data))
        metadata_files = _metadata_payloads()
        for archive, data in metadata_files.items():
            wheel.writestr(archive, data)
            records.append((archive, data))
        record_path = f"{DIST_INFO}/RECORD"
        wheel.writestr(record_path, _record(records, record_path))
    return wheel_name


def build_sdist(sdist_directory, config_settings=None):
    raise NotImplementedError("sdist is not required for local Holon installs")


def _package_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root)
        if rel.parts[0] in {"tests", "__pycache__"}:
            continue
        if "__pycache__" in rel.parts or path.name == "_build_backend.py":
            continue
        files.append(path)
    for name in ("README.md", "pyproject.toml"):
        path = root / name
        if path.exists():
            files.append(path)
    return sorted(files)


def _metadata_payloads() -> dict[str, bytes]:
    return {
        f"{DIST_INFO}/METADATA": _metadata().encode("utf-8"),
        f"{DIST_INFO}/WHEEL": (
            "Wheel-Version: 1.0\n"
            "Generator: holon-local-backend\n"
            "Root-Is-Purelib: true\n"
            "Tag: py3-none-any\n"
            "\n"
        ).encode("utf-8"),
        f"{DIST_INFO}/entry_points.txt": (
            "[console_scripts]\n"
            "holon = holon.cli:main\n"
        ).encode("utf-8"),
    }


def _write_metadata(dist_info: Path) -> None:
    for archive, data in _metadata_payloads().items():
        name = archive.split("/", 1)[1]
        (dist_info / name).write_bytes(data)


def _metadata() -> str:
    readme = Path(__file__).resolve().parent / "README.md"
    description = readme.read_text(encoding="utf-8") if readme.exists() else ""
    return (
        "Metadata-Version: 2.4\n"
        f"Name: {NAME}\n"
        f"Version: {VERSION}\n"
        "Summary: Standalone Holon agent runtime\n"
        "Requires-Python: >=3.11\n"
        "License-Expression: MIT\n"
        "Description-Content-Type: text/markdown\n"
        "Provides-Extra: dev\n"
        "Requires-Dist: pytest>=7.0; extra == \"dev\"\n"
        "Requires-Dist: pytest-asyncio>=0.21; extra == \"dev\"\n"
        "\n"
        f"{description}\n"
    )


def _record(records: list[tuple[str, bytes]], record_path: str) -> str:
    lines = []
    for archive, data in records:
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode("ascii")
        lines.append(f"{archive},sha256={digest},{len(data)}")
    lines.append(f"{record_path},,")
    return "\n".join(lines) + "\n"
