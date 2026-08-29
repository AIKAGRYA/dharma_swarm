#!/usr/bin/env python3
"""Record and verify exact versioned-to-installed Foundry deployment hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

_CANONICAL_ORIGIN = "https://github.com/AIKAGRYA/dharma_swarm.git"
_RUNTIME_ROOTS = (Path("dharma_swarm"), Path("scripts/foundry"))


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _metadata(path: Path, *, follow_symlinks: bool = True) -> dict[str, int | str]:
    details = path.stat() if follow_symlinks else path.lstat()
    return {
        "uid": details.st_uid,
        "gid": details.st_gid,
        "mode": f"{stat.S_IMODE(details.st_mode):04o}",
    }


def _head(repo: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    ).stdout.strip()


def _git(repo: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *arguments],
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("release identity could not be verified") from exc
    return result.stdout


def _runtime_inventory(repo: Path) -> list[dict[str, str]]:
    tracked_raw = _git(
        repo,
        "ls-files",
        "-z",
    )
    tracked = {Path(item) for item in tracked_raw.split("\0") if item}
    if not tracked:
        raise RuntimeError("release has no tracked Foundry runtime")
    observed: set[Path] = set()
    for relative_root in _RUNTIME_ROOTS:
        root = repo / relative_root
        if root.is_symlink() or not root.is_dir():
            raise RuntimeError("Foundry runtime root is missing or redirected")
        for path in root.rglob("*"):
            relative = path.relative_to(repo)
            if path.is_symlink():
                raise RuntimeError("Foundry runtime contains a symlink")
            if path.is_file():
                observed.add(relative)
    runtime_tracked = {
        path for path in tracked
        if any(path == root or root in path.parents for root in _RUNTIME_ROOTS)
    }
    if observed != runtime_tracked:
        raise RuntimeError("Foundry runtime inventory differs from the release")
    inventory = []
    for path in sorted(tracked):
        absolute = repo / path
        if absolute.is_symlink():
            inventory.append({
                "path": path.as_posix(),
                "kind": "symlink",
                "target": os.readlink(absolute),
            })
        elif absolute.is_file():
            inventory.append({
                "path": path.as_posix(),
                "kind": "file",
                "sha256": _sha(absolute),
            })
        else:
            raise RuntimeError("tracked release input is missing or invalid")
    return inventory


def _verify_release_identity(repo: Path, expected_sha: str) -> list[dict[str, str]]:
    """Bind execution to the canonical, exact, byte-clean release."""
    if repo.is_symlink() or not (repo / ".git").is_dir():
        raise RuntimeError("release repository path is invalid")
    if _git(repo, "rev-parse", "HEAD").strip() != expected_sha:
        raise RuntimeError("deployed release SHA mismatch")
    if _git(repo, "remote", "get-url", "origin").strip() != _CANONICAL_ORIGIN:
        raise RuntimeError("deployed release origin mismatch")
    if _git(repo, "status", "--porcelain", "--untracked-files=normal").strip():
        raise RuntimeError("deployed release checkout is not clean")
    return _runtime_inventory(repo)


def _atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.parent / f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    try:
        with temp.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, 0o644)
        os.replace(temp, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temp.unlink(missing_ok=True)


def _bindings(values: list[str]) -> list[tuple[Path, Path]]:
    out = []
    for value in values:
        source, separator, installed = value.partition("=")
        if not separator:
            raise ValueError("binding must be SOURCE=INSTALLED")
        destination = Path(installed)
        if not destination.is_absolute() or ".." in destination.parts:
            raise ValueError("installed binding destination must be absolute and canonical")
        out.append((Path(source).resolve(strict=True), destination))
    return out


def _symlinks(values: list[str]) -> list[tuple[Path, str]]:
    out = []
    for value in values:
        link, separator, target = value.partition("=")
        if not separator or not link or not target:
            raise ValueError("symlink must be LINK=TARGET")
        link_path = Path(link)
        if not link_path.is_absolute():
            raise ValueError("installed symlink path must be absolute")
        out.append((link_path, target))
    return out


def _secret_evidence(path: Path) -> dict[str, object]:
    canonical = path.resolve(strict=True)
    if path.is_symlink() or not canonical.is_file():
        raise RuntimeError("secret dependency must be a non-symlink regular file")
    evidence: dict[str, object] = {
        "path": str(canonical),
        "purpose": "provider_environment",
        # Deliberately do not read or hash credential bytes. The rendered unit
        # binds the exact absolute source path, while rotation can happen
        # without leaking stable key-derived material into a world-readable
        # deployment manifest.
        "content_digest_recorded": False,
    }
    evidence.update(_metadata(canonical))
    return evidence


def _public_evidence(path: Path) -> dict[str, object]:
    canonical = path.resolve(strict=True)
    if path.is_symlink() or not canonical.is_file():
        raise RuntimeError("public dependency must be a non-symlink regular file")
    evidence: dict[str, object] = {
        "path": str(canonical),
        "purpose": "resume_authority_public_key",
        "sha256": _sha(canonical),
    }
    evidence.update(_metadata(canonical))
    return evidence


def _runtime_executable_evidence(path: Path) -> dict[str, object]:
    if not path.is_absolute() or not (path.exists() or path.is_symlink()):
        raise RuntimeError("runtime executable path is invalid")
    requested = path.absolute()
    canonical = requested.resolve(strict=True)
    if not canonical.is_file() or canonical.is_symlink():
        raise RuntimeError("runtime executable target is invalid")
    target_stat = canonical.stat()
    target_mode = stat.S_IMODE(target_stat.st_mode)
    if not target_mode & 0o111 or target_mode & 0o022:
        raise RuntimeError("runtime executable permissions are unsafe")
    evidence: dict[str, object] = {
        "requested_path": str(requested),
        "requested_kind": "symlink" if requested.is_symlink() else "file",
        "requested_target": os.readlink(requested) if requested.is_symlink() else "",
        "resolved_path": str(canonical),
        "sha256": _sha(canonical),
        "resolved_uid": target_stat.st_uid,
        "resolved_gid": target_stat.st_gid,
        "resolved_mode": f"{target_mode:04o}",
    }
    if requested.is_symlink():
        evidence["requested_uid"] = requested.lstat().st_uid
        evidence["requested_gid"] = requested.lstat().st_gid
    return evidence


def record(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    runtime_inventory = _verify_release_identity(repo, args.expected_sha)
    installed: list[dict[str, object]] = []
    for source, destination in _bindings(args.binding):
        if source.read_bytes() != destination.read_bytes():
            raise RuntimeError(f"installed bytes differ from rendered source: {destination}")
        evidence: dict[str, object] = {
            "kind": "file",
            "path": str(destination),
            "sha256": _sha(destination),
        }
        evidence.update(_metadata(destination))
        if evidence["uid"] != 0 or int(str(evidence["mode"]), 8) & 0o022:
            raise RuntimeError("installed deployment file ownership/mode is unsafe")
        installed.append(evidence)
    for link, target in _symlinks(getattr(args, "symlink", [])):
        if not link.is_symlink() or os.readlink(link) != target:
            raise RuntimeError(f"installed deployment symlink mismatch: {link}")
        evidence = {"kind": "symlink", "path": str(link), "target": target}
        evidence.update(_metadata(link, follow_symlinks=False))
        installed.append(evidence)
    paths = [str(entry["path"]) for entry in installed]
    if len(paths) != len(set(paths)):
        raise RuntimeError("installed deployment paths must be unique")
    templates = [
        {"path": str(Path(path).resolve().relative_to(repo)), "sha256": _sha(Path(path))}
        for path in args.template
    ]
    secrets = [
        _secret_evidence(Path(path))
        for path in getattr(args, "secret_file", [])
    ]
    public_dependencies = [
        _public_evidence(Path(path))
        for path in getattr(args, "public_file", [])
    ]
    runtime_executables = [
        _runtime_executable_evidence(Path(path))
        for path in getattr(args, "runtime_executable", [])
    ]
    body = {
        "schema_version": "foundry_deployment_manifest.v2",
        "repo": str(repo),
        "release_sha": args.expected_sha,
        "installed": installed,
        "templates": templates,
        "runtime_inventory": runtime_inventory,
        "external_secret_dependencies": secrets,
        "external_public_dependencies": public_dependencies,
        "runtime_executables": runtime_executables,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    body["digest"] = "sha256:" + hashlib.sha256(
        json.dumps(
            body, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    ).hexdigest()
    _atomic(Path(args.manifest), body)
    return verify(args)


def verify(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    manifest = Path(args.manifest)
    if manifest.is_symlink() or not manifest.is_file():
        raise RuntimeError("deployment manifest path is invalid")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "foundry_deployment_manifest.v2":
        raise RuntimeError("deployment manifest schema invalid")
    body = {k: v for k, v in payload.items() if k != "digest"}
    expected_digest = "sha256:" + hashlib.sha256(
        json.dumps(
            body, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    ).hexdigest()
    if payload.get("digest") != expected_digest:
        raise RuntimeError("deployment manifest digest mismatch")
    if payload.get("repo") != str(repo):
        raise RuntimeError("deployment repository path mismatch")
    if payload.get("release_sha") != args.expected_sha:
        raise RuntimeError("deployed release SHA mismatch")
    runtime_inventory = _verify_release_identity(repo, args.expected_sha)
    if payload.get("runtime_inventory") != runtime_inventory:
        raise RuntimeError("deployed Foundry runtime hash inventory mismatch")
    for entry in payload.get("installed", []):
        path = Path(entry["path"])
        if entry.get("kind") == "symlink":
            if not path.is_symlink() or os.readlink(path) != entry.get("target"):
                raise RuntimeError(f"installed deployment symlink mismatch: {path}")
            observed = _metadata(path, follow_symlinks=False)
        elif entry.get("kind") == "file":
            if not path.is_file() or path.is_symlink() or _sha(path) != entry.get("sha256"):
                raise RuntimeError(f"installed deployment hash mismatch: {path}")
            observed = _metadata(path)
        else:
            raise RuntimeError("installed deployment entry kind invalid")
        if any(entry.get(key) != value for key, value in observed.items()):
            raise RuntimeError(f"installed deployment metadata mismatch: {path}")
    for entry in payload.get("templates", []):
        path = repo / entry["path"]
        if not path.is_file() or _sha(path) != entry["sha256"]:
            raise RuntimeError(f"versioned template hash mismatch: {path}")
    for entry in payload.get("external_secret_dependencies", []):
        path = Path(entry["path"])
        if entry.get("content_digest_recorded") is not False:
            raise RuntimeError("secret dependency must not expose a content digest")
        try:
            current = _secret_evidence(path)
        except (OSError, RuntimeError) as exc:
            raise RuntimeError("secret dependency provenance mismatch") from exc
        if current != entry:
            raise RuntimeError("secret dependency provenance mismatch")
    for entry in payload.get("external_public_dependencies", []):
        path = Path(entry["path"])
        try:
            current = _public_evidence(path)
        except (OSError, RuntimeError) as exc:
            raise RuntimeError("public dependency provenance mismatch") from exc
        if current != entry:
            raise RuntimeError("public dependency provenance mismatch")
    for entry in payload.get("runtime_executables", []):
        try:
            current = _runtime_executable_evidence(Path(entry["requested_path"]))
        except (KeyError, OSError, RuntimeError) as exc:
            raise RuntimeError("runtime executable provenance mismatch") from exc
        if current != entry:
            raise RuntimeError("runtime executable provenance mismatch")
    print(json.dumps({
        "deployment_verified": True,
        "manifest": str(Path(args.manifest).resolve()),
        "release_sha": args.expected_sha,
    }, sort_keys=True, allow_nan=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("record", "verify"))
    parser.add_argument("--repo", required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--binding", action="append", default=[])
    parser.add_argument("--symlink", action="append", default=[])
    parser.add_argument("--secret-file", action="append", default=[])
    parser.add_argument("--public-file", action="append", default=[])
    parser.add_argument("--runtime-executable", action="append", default=[])
    parser.add_argument("--template", action="append", default=[])
    args = parser.parse_args(argv)
    return record(args) if args.mode == "record" else verify(args)


if __name__ == "__main__":
    raise SystemExit(main())
