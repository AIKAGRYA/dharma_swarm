"""Versioned workspace intent data. Profiles never contain executable shell text."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .config import DesktopConfig, DesktopError, NAME_RE, local_path
from .storage import MAX_STATE_BYTES, read_json

SCHEMA = "dharma.helm.desktop_profile.v1"


def default_profile(config: DesktopConfig) -> dict[str, Any]:
    plan = "docs/plans/helm_legone/HELM_LEGONE_SPEC.md"
    resources: list[dict[str, str]] = [{"id": "helm", "app": "terminal", "kind": "helm"}]
    if (config.repo_root / plan).is_file():
        resources.append({"id": "vision", "app": "editor", "kind": "path", "path": plan})
    resources.append({"id": "repository", "app": "browser", "kind": "url",
                      "url": "https://github.com/AIKAGRYA/dharma_swarm"})
    return {"schema": SCHEMA, "name": "research", "label": "Research",
            "project_root": str(config.repo_root), "resources": resources}


def validate_profile(value: dict[str, Any]) -> dict[str, Any]:
    if set(value) != {"schema", "name", "label", "project_root", "resources"}:
        raise DesktopError("profile must contain only schema, name, label, project_root and resources")
    if value["schema"] != SCHEMA:
        raise DesktopError(f"unsupported profile schema; expected {SCHEMA}")
    if not isinstance(value["name"], str) or not NAME_RE.fullmatch(value["name"]):
        raise DesktopError("profile name must be a short lowercase identifier")
    label = value["label"]
    if not isinstance(label, str) or not label.strip() or len(label) > 64 or any(ord(c) < 32 for c in label):
        raise DesktopError("profile label must be 1–64 printable characters")
    if not isinstance(value["project_root"], str):
        raise DesktopError("project_root must be an absolute directory path")
    project = local_path(value["project_root"], directory=True)
    resources = value["resources"]
    if not isinstance(resources, list) or not 1 <= len(resources) <= 16:
        raise DesktopError("profiles must have 1–16 resource intents")
    seen: set[str] = set()
    seen_resources: set[str] = set()
    for resource in resources:
        if not isinstance(resource, dict):
            raise DesktopError("each resource must be an object")
        identity = resource.get("id")
        if not isinstance(identity, str) or not NAME_RE.fullmatch(identity) or identity in seen:
            raise DesktopError("resource IDs must be unique lowercase identifiers")
        seen.add(identity)
        kind, app = resource.get("kind"), resource.get("app")
        fields = {"id", "app", "kind"}
        if (kind, app) == ("helm", "terminal"):
            key = "helm"
        elif (kind, app) == ("path", "editor"):
            fields.add("path")
            path_value = resource.get("path")
            if not isinstance(path_value, str):
                raise DesktopError("editor resource requires a relative path")
            path = Path(path_value)
            if path.is_absolute() or ".." in path.parts or any(ord(c) < 32 for c in path_value):
                raise DesktopError("editor paths must stay inside project_root")
            target = (project / path).resolve()
            if target != project and project not in target.parents:
                raise DesktopError("editor path escapes project_root through a symlink")
            if not target.exists():
                raise DesktopError(f"editor resource does not exist: {path_value}")
            key = str(target)
        elif (kind, app) == ("url", "browser"):
            fields.add("url")
            url = resource.get("url")
            if not isinstance(url, str) or len(url) > 4096 or any(ord(c) < 33 for c in url):
                raise DesktopError("browser resource requires a URL without whitespace")
            try:
                parsed = urlsplit(url)
                parsed.port  # Validate malformed ports before submitting to macOS.
            except ValueError as exc:
                raise DesktopError("browser URL is malformed") from exc
            if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
                raise DesktopError("browser URLs must be http(s) without embedded credentials")
            key = url
        else:
            raise DesktopError("supported intents are terminal/helm, editor/path and browser/url")
        if set(resource) != fields:
            raise DesktopError(f"unsupported fields in resource {identity}; arbitrary commands are not allowed")
        if key in seen_resources:
            raise DesktopError("duplicate resource identity in profile")
        seen_resources.add(key)
    return {**value, "project_root": str(project)}


def load_profile(config: DesktopConfig) -> dict[str, Any]:
    if NAME_RE.fullmatch(config.profile):
        value = read_json(config.state_dir, f"profiles/{config.profile}.json")
        if value is None and config.profile == "research":
            value = default_profile(config)
        if value is None:
            raise DesktopError(f"profile is not installed: {config.profile}")
    else:
        path = local_path(config.profile)
        try:
            if path.stat().st_size > MAX_STATE_BYTES:
                raise DesktopError("profile exceeds size limit")
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise DesktopError(f"cannot read profile: {exc}") from exc
        if not isinstance(value, dict):
            raise DesktopError("profile must be a JSON object")
    return validate_profile(value)


def resource_key(profile: dict[str, Any], resource: dict[str, Any]) -> str:
    payload = {"project_root": profile["project_root"], "resource": resource}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
