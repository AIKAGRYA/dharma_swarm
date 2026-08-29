#!/usr/bin/env python3
"""Lossless, journaled install/rollback for Foundry host artifacts."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import stat
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

_ALLOWED_DESTINATIONS = (
    Path("/etc/systemd/system"),
    Path("/etc/logrotate.d"),
    Path("/etc/dharma-foundry"),
    Path("/etc/cron.d"),
    Path("/usr/local/bin"),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digest(body: dict) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(
        body, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")).hexdigest()


def _atomic_json(path: Path, body: dict) -> None:
    payload = {**body, "digest": _digest(body)}
    encoded = (json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.parent / f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    try:
        with temp.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temp.unlink(missing_ok=True)


def _load(transaction: Path) -> dict:
    payload = json.loads((transaction / "transaction.json").read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("deployment transaction is not an object")
    claimed = payload.pop("digest", "")
    if claimed != _digest(payload) or payload.get("schema_version") != "foundry_deploy_transaction.v1":
        raise RuntimeError("deployment transaction digest/schema mismatch")
    return payload


def _destination(raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("deployment destination must be absolute and canonical")
    allowed_root = next(
        (root for root in _ALLOWED_DESTINATIONS if path == root or root in path.parents),
        None,
    )
    if allowed_root is None:
        raise ValueError(f"deployment destination is outside allowed host paths: {path}")
    if allowed_root.is_symlink():
        raise ValueError(f"deployment root may not be a symlink: {allowed_root}")
    cursor = allowed_root
    relative_parts = path.relative_to(allowed_root).parts
    # The final leaf is allowed to be a symlink because replacing a masked
    # unit is a supported, journaled transition.  No parent component may
    # redirect the write outside the approved host tree.
    for part in relative_parts[:-1]:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError(f"deployment path traverses a symlink: {cursor}")
        if cursor.exists() and not cursor.is_dir():
            raise ValueError(f"deployment parent is not a directory: {cursor}")
    return path


def _binding(raw: str) -> tuple[Path, Path]:
    source, separator, destination = raw.partition("=")
    if not separator:
        raise ValueError("file binding must be SOURCE=DESTINATION")
    source_path = Path(source).resolve(strict=True)
    if not source_path.is_file() or source_path.is_symlink():
        raise ValueError("deployment source must be a non-symlink regular file")
    return source_path, _destination(destination)


def _sync_parent(path: Path) -> None:
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _remove_leaf(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        raise RuntimeError(f"refusing to replace non-file deployment destination: {path}")


@contextmanager
def _deployment_lock(root: Path):
    """Serialize transaction discovery and every subsequent state transition."""
    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / ".deployment.lock"
    fd = os.open(
        lock_path,
        os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    os.chmod(lock_path, 0o600)
    with os.fdopen(fd, "a+b", closefd=True) as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _transaction_path(raw: Path) -> Path:
    transaction = _destination(str(Path(raw)))
    if transaction.is_symlink() or not transaction.is_dir():
        raise ValueError("deployment transaction path must be a non-symlink directory")
    if not (transaction / "transaction.json").is_file():
        raise ValueError("deployment transaction journal is missing")
    return transaction


def _backup(transaction: Path, body: dict, destination: Path) -> dict:
    index = len(body["entries"])
    entry: dict = {
        "destination": str(destination),
        "existed": destination.exists() or destination.is_symlink(),
        "backup": "",
        "phase": "planned",
    }
    if entry["existed"]:
        if not (destination.is_file() or destination.is_symlink()):
            raise RuntimeError(f"refusing non-leaf deployment destination: {destination}")
        backup = transaction / "backups" / f"{index:04d}"
        backup.parent.mkdir(parents=True, exist_ok=True)
        entry["backup"] = str(backup.relative_to(transaction))
        entry["prior_kind"] = "symlink" if destination.is_symlink() else "file"
        entry["prior_target"] = os.readlink(destination) if destination.is_symlink() else ""
        entry["prior_sha256"] = (
            "" if destination.is_symlink()
            else hashlib.sha256(destination.read_bytes()).hexdigest()
        )
    # Journal intent before the first destructive rename. If power fails after
    # the rename, rollback can discover the already-present backup path.
    body["entries"].append(entry)
    _atomic_json(transaction / "transaction.json", body)
    if entry["existed"]:
        backup = transaction / entry["backup"]
        os.replace(destination, backup)
        entry["phase"] = "backed_up"
        _sync_parent(destination)
        _atomic_json(transaction / "transaction.json", body)
    return entry


def _install_file(transaction: Path, body: dict, source: Path, destination: Path) -> None:
    entry = _backup(transaction, body, destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.parent / f".{destination.name}.foundry.{uuid.uuid4().hex}.tmp"
    try:
        shutil.copyfile(source, temp, follow_symlinks=False)
        os.chmod(temp, 0o644)
        with temp.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temp, destination)
        _sync_parent(destination)
    finally:
        temp.unlink(missing_ok=True)
    entry.update({
        "phase": "installed",
        "installed_kind": "file",
        "source": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "installed_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        "installed_mode": f"{stat.S_IMODE(destination.stat().st_mode):04o}",
    })
    _atomic_json(transaction / "transaction.json", body)


def _install_symlink(transaction: Path, body: dict, link: Path, target: str) -> None:
    if not target.startswith("/"):
        raise ValueError("deployment symlink target must be absolute")
    entry = _backup(transaction, body, link)
    link.parent.mkdir(parents=True, exist_ok=True)
    temp = link.parent / f".{link.name}.foundry.{uuid.uuid4().hex}.tmp"
    os.symlink(target, temp)
    os.replace(temp, link)
    _sync_parent(link)
    entry.update({
        "phase": "installed",
        "installed_kind": "symlink",
        "installed_target": target,
    })
    _atomic_json(transaction / "transaction.json", body)


def _rollback_unlocked(transaction: Path) -> None:
    body = _load(transaction)
    if body.get("state") == "rolled_back":
        return
    if body.get("state") == "committed":
        raise RuntimeError("refusing automatic rollback of a committed transaction")
    errors: list[str] = []
    for entry in reversed(body.get("entries", [])):
        destination = _destination(str(entry["destination"]))
        try:
            backup = transaction / str(entry.get("backup", ""))
            backup_present = bool(entry.get("backup")) and (
                backup.exists() or backup.is_symlink()
            )
            # A new destination may have landed just before a crash updated
            # its phase. Presence is therefore authoritative for removal.
            if entry.get("phase") == "installed" or not entry.get("existed") or backup_present:
                _remove_leaf(destination)
            if entry.get("existed"):
                if not backup_present:
                    if entry.get("phase") == "planned" and (
                        destination.exists() or destination.is_symlink()
                    ):
                        continue
                    raise RuntimeError("deployment backup is missing")
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.replace(backup, destination)
            _sync_parent(destination)
        except (OSError, RuntimeError, ValueError) as exc:
            errors.append(f"{destination}:{type(exc).__name__}")
    body["state"] = "rollback_failed" if errors else "rolled_back"
    body["rolled_back_at"] = _now()
    body["rollback_errors"] = errors
    _atomic_json(transaction / "transaction.json", body)
    if errors:
        raise RuntimeError("deployment rollback failed closed: " + ",".join(errors))


def rollback(transaction: Path) -> None:
    transaction = _transaction_path(Path(transaction))
    with _deployment_lock(transaction.parent):
        _rollback_unlocked(transaction)


def apply_new(args: argparse.Namespace) -> Path:
    root = _destination(args.transaction_root)
    if root.is_symlink():
        raise ValueError("deployment transaction root may not be a symlink")
    with _deployment_lock(root):
        for journal in root.glob("*/transaction.json"):
            try:
                active = _load(journal.parent)
            except (OSError, ValueError, RuntimeError):
                raise RuntimeError(
                    f"unreadable prior deployment transaction: {journal.parent}"
                )
            if active.get("state") in {"active", "rollback_failed"}:
                raise RuntimeError(
                    f"unresolved prior deployment transaction: {journal.parent}"
                )
        transaction = root / (
            f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}__"
            f"{uuid.uuid4().hex}"
        )
        transaction.mkdir(mode=0o700)
        body = {
            "schema_version": "foundry_deploy_transaction.v1",
            "transaction_id": transaction.name,
            "state": "active",
            "created_at": _now(),
            "entries": [],
        }
        _atomic_json(transaction / "transaction.json", body)
        try:
            for raw in args.file:
                _install_file(transaction, body, *_binding(raw))
            for raw in args.symlink:
                link, separator, target = raw.partition("=")
                if not separator:
                    raise ValueError("symlink binding must be LINK=TARGET")
                _install_symlink(transaction, body, _destination(link), target)
        except BaseException:
            _rollback_unlocked(transaction)
            raise
        return transaction


def add_file(transaction: Path, raw: str) -> None:
    transaction = _transaction_path(Path(transaction))
    with _deployment_lock(transaction.parent):
        body = _load(transaction)
        if body.get("state") != "active":
            raise RuntimeError("deployment transaction is not active")
        try:
            _install_file(transaction, body, *_binding(raw))
        except BaseException:
            _rollback_unlocked(transaction)
            raise


def commit(transaction: Path) -> None:
    transaction = _transaction_path(Path(transaction))
    with _deployment_lock(transaction.parent):
        body = _load(transaction)
        if body.get("state") != "active":
            raise RuntimeError("deployment transaction is not active")
        body["state"] = "committed"
        body["committed_at"] = _now()
        _atomic_json(transaction / "transaction.json", body)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    apply_parser = sub.add_parser("apply")
    apply_parser.add_argument("--transaction-root", required=True)
    apply_parser.add_argument("--file", action="append", default=[])
    apply_parser.add_argument("--symlink", action="append", default=[])
    add_parser = sub.add_parser("add-file")
    add_parser.add_argument("--transaction", required=True)
    add_parser.add_argument("--file", required=True)
    for command in ("commit", "rollback"):
        item = sub.add_parser(command)
        item.add_argument("--transaction", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "apply":
            print(apply_new(args))
        elif args.command == "add-file":
            add_file(Path(args.transaction), args.file)
        elif args.command == "commit":
            commit(Path(args.transaction))
        else:
            rollback(Path(args.transaction))
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"deployment transaction refused: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
