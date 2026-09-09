"""Typed workspace intents adapted to existing applications, with partial outcomes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import DesktopConfig, DesktopError
from .profiles import load_profile, resource_key
from .runtime import Runner, activate_pane, focus, run, wezterm_panes
from .storage import read_json, write_json


def preview(config: DesktopConfig) -> dict[str, Any]:
    profile = load_profile(config)
    actions: list[dict[str, Any]] = []
    for resource in profile["resources"]:
        action = {"id": resource["id"], "app": resource["app"], "kind": resource["kind"],
                  "identity": resource_key(profile, resource)}
        if resource["kind"] == "helm":
            action.update({"effect": "focus existing Helm seat", "seat": config.seat(), "starts_bridge": False})
        elif resource["kind"] == "path":
            path = str((Path(profile["project_root"]) / resource["path"]).resolve())
            action.update({"effect": "focus or open Neovim in WezTerm", "argv": ["nvim", "--", path]})
        else:
            action.update({"effect": "request browser URL once; --reopen requests it again",
                           "argv": ["open", resource["url"]]})
        actions.append(action)
    return {"action": "workspace.preview", "profile": profile, "actions": actions,
            "authority": "observation_only", "mutates": False}


def _editor(config: DesktopConfig, profile: dict[str, Any], resource: dict[str, Any], *, runner: Runner) -> dict[str, Any]:
    marker = f"Helm/{profile['name']}/{resource['id']}/{resource_key(profile, resource)[:12]}"
    panes = wezterm_panes(config, runner=runner)
    if panes is None:
        raise DesktopError("WezTerm is not ready; focus Helm first and retry the workspace")
    for pane in panes:
        if pane.get("tab_title") == marker and type(pane.get("pane_id")) is int:
            return activate_pane(config, pane["pane_id"], runner=runner)
    target = str((Path(profile["project_root"]) / resource["path"]).resolve())
    argv = ["wezterm", "cli", "--no-auto-start", "spawn", "--new-window", "--workspace", profile["label"],
            "--cwd", profile["project_root"], "--", "nvim", "--", target]
    result = runner(argv, env=config.environment())
    if result.returncode or not result.stdout.strip().isdigit():
        raise DesktopError("WezTerm could not open the editor resource")
    pane_id = int(result.stdout.strip())
    # Record the resource on the actual tab. A later process can reuse it, and
    # closing the tab means the next open creates a new one.
    panes = wezterm_panes(config, runner=runner)
    pane = next((p for p in panes or [] if p.get("pane_id") == pane_id), None)
    if pane is None or type(pane.get("tab_id")) is not int:
        return {"outcome": "opened_untracked", "pane_id": pane_id,
                "detail": "editor launched; its tab identity could not yet be observed"}
    titled = runner(["wezterm", "cli", "--no-auto-start", "set-tab-title", "--tab-id", str(pane["tab_id"]), marker],
                   env=config.environment())
    if titled.returncode:
        return {"outcome": "opened_untracked", "pane_id": pane_id,
                "detail": "editor launched; WezTerm refused its resource title"}
    return {"outcome": "opened", "pane_id": pane_id, "tab_id": pane["tab_id"], "identity": marker}


def open_workspace(config: DesktopConfig, *, runner: Runner = run, reopen: bool = False) -> dict[str, Any]:
    profile = load_profile(config)
    relative = f"workspaces/{profile['name']}.json"
    receipt = read_json(config.state_dir, relative) or {"schema": "dharma.helm.workspace_open.v1", "resources": {}}
    if receipt.get("schema") != "dharma.helm.workspace_open.v1" or not isinstance(receipt.get("resources"), dict):
        raise DesktopError("workspace receipt is invalid; no actions were run")
    outcomes: list[dict[str, Any]] = []
    for resource in profile["resources"]:
        key = resource_key(profile, resource)
        prior = receipt["resources"].get(key)
        try:
            if resource["kind"] == "helm":
                result = focus(config, runner=runner)
            elif resource["kind"] == "path":
                # If a tab launch could not be tracked, require an explicit retry
                # rather than duplicate an editor whose existence is uncertain.
                if isinstance(prior, dict) and prior.get("outcome") == "opened_untracked" and not reopen:
                    result = {"outcome": "untracked_existing_request", "detail": "inspect the editor or use --reopen"}
                else:
                    result = _editor(config, profile, resource, runner=runner)
            elif isinstance(prior, dict) and prior.get("outcome") == "launch_requested" and not reopen:
                result = {"outcome": "already_requested", "detail": "prior OS launch request recorded; page liveness is unknown"}
            else:
                launched = runner(["open", resource["url"]], env=config.environment())
                if launched.returncode:
                    raise DesktopError("macOS could not request the browser URL")
                result = {"outcome": "launch_requested", "detail": "OS accepted URL; page loading is not observed"}
            if result["outcome"] not in {"already_requested", "untracked_existing_request"}:
                receipt["resources"][key] = {"resource": resource, **result}
                write_json(config.state_dir, relative, receipt)
            outcomes.append({"id": resource["id"], **result})
        except DesktopError as exc:
            outcomes.append({"id": resource["id"], "outcome": "failed", "reason": str(exc)})
    partial = any(item["outcome"] in {"failed", "opened_untracked", "untracked_existing_request", "attached_elsewhere"}
                  for item in outcomes)
    return {"action": "workspace.open", "profile": profile["name"], "outcome": "partial" if partial else "complete",
            "resources": outcomes, "receipt": str(config.state_dir / relative)}
