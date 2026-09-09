"""Isolated, reviewable installation and compare-before-restore lifecycle."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import shlex
import stat
import sys
from pathlib import Path
from typing import Any

from .config import DesktopConfig, DesktopError
from .profiles import load_profile
from .storage import MAX_STATE_BYTES, read_json, state_path, write_bytes, write_json

MANIFEST = "install/manifest.json"
SCHEMA = "dharma.helm.desktop_install.v1"
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _allowed(path: str) -> bool:
    return path in {"bin/helm-desktop", "config/aerospace.toml"} or bool(
        re.fullmatch(r"profiles/[a-z][a-z0-9_-]{0,47}\.json", path))


def _existing(root: Path, relative: str) -> tuple[bytes, int] | None:
    path = state_path(root, relative)
    try:
        info = path.stat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_STATE_BYTES:
        raise DesktopError(f"managed target must be a small regular file with one link: {relative}")
    return path.read_bytes(), stat.S_IMODE(info.st_mode)


def _manifest(config: DesktopConfig) -> dict[str, Any]:
    value = read_json(config.state_dir, MANIFEST)
    if value is None:
        return {"schema": SCHEMA, "state_dir": str(config.state_dir), "repo_root": str(config.repo_root), "files": {}}
    if (value.get("schema") != SCHEMA or value.get("state_dir") != str(config.state_dir)
            or value.get("repo_root") != str(config.repo_root) or not isinstance(value.get("files"), dict)):
        raise DesktopError("installation manifest does not match this state directory and repository")
    for path, entry in value["files"].items():
        if not _allowed(path) or not isinstance(entry, dict):
            raise DesktopError("installation manifest contains an unsupported path or entry")
        if set(entry) != {"installed_sha256", "installed_mode", "original"}:
            raise DesktopError("installation manifest entry has missing or unsupported fields")
        installed = entry.get("installed_sha256")
        if not isinstance(installed, str) or not _DIGEST.fullmatch(installed):
            raise DesktopError("installation manifest has an invalid installed digest")
        if entry.get("installed_mode") not in {0o600, 0o700}:
            raise DesktopError("installation manifest has an invalid installed mode")
        original = entry.get("original")
        if original is not None:
            if not isinstance(original, dict) or set(original) != {"base64", "sha256", "mode"}:
                raise DesktopError("installation manifest backup is invalid")
            try:
                data = base64.b64decode(original["base64"], validate=True)
            except (ValueError, TypeError) as exc:
                raise DesktopError("installation manifest backup is not valid base64") from exc
            mode = original["mode"]
            if digest(data) != original["sha256"] or type(mode) is not int or not 0 <= mode <= 0o777:
                raise DesktopError("installation manifest backup digest or mode is invalid")
    return value


def artifacts(config: DesktopConfig) -> dict[str, tuple[bytes, int]]:
    profile = load_profile(config)
    argv = [sys.executable, str(config.repo_root / "scripts/helm_desktop.py"), "--repo-root", str(config.repo_root),
            "--state-dir", str(config.state_dir), "--profile", profile["name"],
            "--socket", config.socket, "--session", config.session]
    script = "#!/bin/sh\n# Generated isolated Helm Desktop launcher.\nexec " + shlex.join(argv) + ' "$@"\n'
    launcher = str(config.state_dir / "bin/helm-desktop")
    focus_command = "exec-and-forget " + shlex.join([launcher, "focus"])
    research_command = "exec-and-forget " + shlex.join([launcher, "workspace", "open"])
    snippet = ("# Optional snippet: review and copy bindings into your existing AeroSpace configuration.\n"
               "# Installation does not change or reload that configuration.\n[mode.main.binding]\n"
               f"alt-space = {json.dumps(focus_command)}\nalt-shift-r = {json.dumps(research_command)}\n")
    return {f"profiles/{profile['name']}.json": ((json.dumps(profile, indent=2, sort_keys=True) + "\n").encode(), 0o600),
            "bin/helm-desktop": (script.encode(), 0o700), "config/aerospace.toml": (snippet.encode(), 0o600)}


def _plan(config: DesktopConfig) -> tuple[dict[str, Any], dict[str, tuple[bytes, int]], list[dict[str, Any]]]:
    manifest, wanted = _manifest(config), artifacts(config)
    actions: list[dict[str, Any]] = []
    for relative, (data, mode) in wanted.items():
        existing, entry = _existing(config.state_dir, relative), manifest["files"].get(relative)
        previous = digest(existing[0]) if existing else None
        expected = digest(data)
        reason = None
        if entry and existing and (previous != entry["installed_sha256"] or existing[1] != entry["installed_mode"]):
            action, reason = "conflict", "existing or later user changes are preserved"
        elif entry and not existing:
            action = "conflict"
            reason = ("this managed file was deleted after installation and is not recreated automatically; "
                      "drop it from the manifest with: restore --apply, then install apply --apply")
        elif existing and not entry and previous != expected:
            action, reason = "conflict", "existing or later user changes are preserved"
        elif existing and previous == expected and existing[1] == mode:
            action = "unchanged"
        else:
            action = "update" if existing else "create"
        actions.append({"path": str(config.state_dir / relative), "relative_path": relative, "action": action,
                        "sha256": expected, "mode": oct(mode), "content": data.decode(), "reason": reason})
    return manifest, wanted, actions


def preview(config: DesktopConfig) -> dict[str, Any]:
    _, _, actions = _plan(config)
    return {"action": "install.preview", "mutates": False, "state_dir": str(config.state_dir),
            "ready": all(a["action"] != "conflict" for a in actions), "files": actions,
            "manifest": str(config.state_dir / MANIFEST)}


def apply(config: DesktopConfig) -> dict[str, Any]:
    manifest, wanted, actions = _plan(config)
    conflicts = [a for a in actions if a["action"] == "conflict"]
    if conflicts:
        raise DesktopError("installation conflicts with the current state; preview lists every preserved path. "
                           + " ".join(f"{a['relative_path']}: {a['reason']}" for a in conflicts))
    for relative, (data, mode) in wanted.items():
        existing = _existing(config.state_dir, relative)
        old_entry = manifest["files"].get(relative)
        original = old_entry["original"] if old_entry else (
            {"base64": base64.b64encode(existing[0]).decode(), "sha256": digest(existing[0]), "mode": existing[1]}
            if existing else None)
        manifest["files"][relative] = {"installed_sha256": digest(data), "installed_mode": mode, "original": original}
    # Write the recovery ledger before installing any target. If interrupted,
    # restore still compares the current file with the intended installed hash.
    write_json(config.state_dir, MANIFEST, manifest)
    for item in actions:
        if item["action"] != "unchanged":
            data, mode = wanted[item["relative_path"]]
            write_bytes(config.state_dir, item["relative_path"], data, mode)
    return {"action": "install.apply", "outcome": "installed", "state_dir": str(config.state_dir),
            "files": [{k: v for k, v in item.items() if k != "content"} for item in actions],
            "launcher": str(config.state_dir / "bin/helm-desktop"), "manifest": str(config.state_dir / MANIFEST)}


def restore(config: DesktopConfig, *, apply_changes: bool = False) -> dict[str, Any]:
    manifest = _manifest(config)
    actions: list[dict[str, Any]] = []
    remaining: dict[str, Any] = {}
    for relative, entry in manifest["files"].items():
        existing = _existing(config.state_dir, relative)
        if existing is None:
            action = "already_absent" if entry["original"] is None else "preserved_deletion"
        elif digest(existing[0]) != entry["installed_sha256"] or existing[1] != entry["installed_mode"]:
            action = "preserved_user_edit"
        else:
            action = "restore_original" if entry["original"] is not None else "remove_installed"
        if action.startswith("preserved"):
            remaining[relative] = entry
        actions.append({"path": str(config.state_dir / relative), "relative_path": relative, "action": action})
    if apply_changes:
        # Recheck each target immediately before mutation. This catches edits
        # after preview; state-directory callers also hold the operation lock.
        for item in actions:
            relative, action = item["relative_path"], item["action"]
            if action not in {"restore_original", "remove_installed"}:
                continue
            entry, current = manifest["files"][relative], _existing(config.state_dir, relative)
            if current is None or digest(current[0]) != entry["installed_sha256"] or current[1] != entry["installed_mode"]:
                item["action"] = "preserved_user_edit"
                remaining[relative] = entry
                continue
            if action == "restore_original":
                original = entry["original"]
                write_bytes(config.state_dir, relative, base64.b64decode(original["base64"]), original["mode"])
            else:
                state_path(config.state_dir, relative).unlink()
        if read_json(config.state_dir, MANIFEST) is not None:
            write_json(config.state_dir, MANIFEST, {**manifest, "files": remaining})
    outcome = ("partial" if remaining else "restored") if apply_changes else "preview"
    return {"action": "restore", "mutates": apply_changes, "outcome": outcome,
            "files": actions, "preserved_count": len(remaining),
            "preserved_paths": sorted(remaining), "restores_fully": not remaining,
            "detail": "runtime sessions, status, receipts and unrelated files remain intact"}
