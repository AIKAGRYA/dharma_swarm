"""Private OpenCode configuration; credentials travel only in the child environment."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from dharma_swarm.api_keys import ENV_ALIASES, PROVIDER_API_KEY_ENV_KEYS, bootstrap_runtime_env

from .config import DesktopConfig, DesktopError
from .storage import MAX_STATE_BYTES, read_json, state_path, write_bytes, write_json
from .workbench_context import prepare_workbench_context

API_PROVIDERS = ("openai", "anthropic", "openrouter")
MANIFEST = "workbench/config-manifest.json"
_STRING = r'"(?:\\.|[^"\\])*"'
_SECRET = re.compile(r"^(?:api.?key|(?:access.?|refresh.?|auth.?|bearer.?)?token|password|(?:client.?)?secret|authorization)$", re.I)
_BASE_ENV = {"PATH", "HOME", "USER", "LOGNAME", "SHELL", "TERM", "COLORTERM",
             "LANG", "TZ", "TMPDIR", "TERM_PROGRAM", "TERM_PROGRAM_VERSION", "SSH_AUTH_SOCK"}


@dataclass(frozen=True)
class PreparedWorkbench:
    """Internal launch arguments. Report only public_report(), never asdict()."""

    argv: tuple[str, ...]
    environment: dict[str, str] = field(repr=False)
    config_path: str
    tui_config_path: str
    model: str
    enabled_providers: tuple[str, ...]
    api_access: bool

    def public_report(self) -> dict[str, Any]:
        return {"argv": list(self.argv), "config_path": self.config_path,
                "tui_config_path": self.tui_config_path, "model": self.model,
                "enabled_providers": list(self.enabled_providers), "api_access": self.api_access,
                "api_access_semantics": "import_existing_metered_keys; later /connect choices belong to the operator",
                "resume_scope": "private_project_store",
                "model_semantics": "startup_preference; OpenCode restores the resumed session model",
                "subscription_auth": "For ChatGPT use /connect > OpenAI > ChatGPT Plus/Pro and sign in. "
                                     "Native Codex OAuth is not copied; use native Claude Code for Claude subscriptions."}


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _jsonc(text: str) -> dict[str, Any]:
    # Match strings first so URL slashes, escaped quotes, and commas inside strings survive.
    text = re.sub(f"({_STRING})|/\\*[\\s\\S]*?\\*/|//[^\\r\\n]*",
                  lambda m: m.group(1) or " ", text)
    text = re.sub(f"({_STRING})|,\\s*(?=[}}\\]])", lambda m: m.group(1) or "", text)
    value = json.loads(text, object_pairs_hook=_object,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError("invalid constant")))
    if not isinstance(value, dict):
        raise ValueError("JSON object required")
    return value


def _glm_source() -> tuple[dict[str, Any], str]:
    path = Path.home() / ".config/opencode/opencode.jsonc"
    try:
        if path.stat().st_size > MAX_STATE_BYTES:
            raise ValueError("oversized configuration")
        source = _jsonc(path.read_text(encoding="utf-8"))
        provider = source["provider"]["glm-coding"]
        if (not isinstance(provider, dict) or not isinstance(provider.get("models"), dict)
                or not provider["models"]):
            raise ValueError("invalid provider")
        if provider.get("npm") not in {"@ai-sdk/openai-compatible", "@ai-sdk/openai"}:
            raise ValueError("unsupported SDK")
        if not isinstance(provider["options"]["baseURL"], str):
            raise ValueError("invalid endpoint")
        endpoint = urlsplit(provider["options"]["baseURL"])
        if (endpoint.scheme != "https" or not endpoint.hostname or endpoint.username
                or endpoint.password or endpoint.query or endpoint.fragment):
            raise ValueError("invalid endpoint")
        if not isinstance(provider["options"].get("apiKey"), str) or not provider["options"]["apiKey"]:
            raise ValueError("missing credential")
        default = source.get("model")
        if not isinstance(default, str) or not default.startswith("glm-coding/"):
            default = "glm-coding/" + next(iter(provider["models"]))
        return {key: provider[key] for key in ("npm", "name", "options", "models") if key in provider}, default
    except (OSError, UnicodeError, ValueError, KeyError, TypeError):
        raise DesktopError("Define a valid glm-coding provider with at least one model in ~/.config/opencode/opencode.jsonc") from None


def _lift_credentials(value: Any, environment: dict[str, str], path: str = "glm",
                      sensitive: bool = False) -> Any:
    if isinstance(value, dict):
        return {key: _lift_credentials(item, environment, f"{path}.{key}",
                                      sensitive or key == "headers" or bool(_SECRET.search(key)))
                for key, item in value.items()}
    if isinstance(value, list):
        return [_lift_credentials(item, environment, f"{path}.{i}", sensitive)
                for i, item in enumerate(value)]
    if not isinstance(value, str):
        if sensitive:
            raise DesktopError("GLM credential fields must contain strings")
        return value
    if "{file:" in value:
        raise DesktopError("File substitutions are not imported into the private workbench")
    if sensitive:
        match = re.fullmatch(r"\{env:([A-Za-z_][A-Za-z0-9_]*)\}", value)
        secret = os.environ.get(match[1], "") if match else value
        if match and not secret:
            canonical = ENV_ALIASES.get(match[1], match[1])
            secret = os.environ.get(canonical, "")
            if not secret:
                credentials: dict[str, str] = {}
                bootstrap_runtime_env(env=credentials)
                secret = credentials.get(match[1]) or credentials.get(canonical, "")
        if not secret or "\0" in secret or "{env:" in secret:
            raise DesktopError("A referenced GLM credential is unavailable")
        name = "HELM_WORKBENCH_GLM_" + hashlib.sha256(path.encode()).hexdigest()[:12].upper()
        environment[name] = secret
        return "{env:" + name + "}"
    if "{env:" in value:
        raise DesktopError("Only credential environment substitutions are imported for GLM")
    return value


def _private_directory(config: DesktopConfig, relative: str) -> Path:
    path = state_path(config.state_dir, relative)
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.is_dir() or path.stat().st_uid != os.getuid():
        raise DesktopError("workbench directories must belong to the current user")
    path.chmod(0o700)
    return path


def _write_configs(config: DesktopConfig, files: dict[str, dict[str, Any]]) -> None:
    manifest = read_json(config.state_dir, MANIFEST)
    if manifest is not None and (manifest.get("schema") != "dharma.helm.workbench_config.v1"
                                 or manifest.get("repo_root") != str(config.repo_root)
                                 or not isinstance(manifest.get("files"), dict)):
        raise DesktopError("workbench configuration manifest does not match this project")
    previous = manifest["files"] if manifest else {}
    encoded = {name: (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
               for name, value in files.items()}
    for name in encoded:
        path = state_path(config.state_dir, name)
        if path.exists():
            info = path.stat()
            if not path.is_file() or info.st_nlink != 1 or info.st_size > MAX_STATE_BYTES:
                raise DesktopError("unsafe existing workbench configuration file")
            if hashlib.sha256(path.read_bytes()).hexdigest() != previous.get(name):
                raise DesktopError("workbench configuration has unowned or later edits; preserving it")
    for name, data in encoded.items():
        write_bytes(config.state_dir, name, data)
    write_json(config.state_dir, MANIFEST,
               {"schema": "dharma.helm.workbench_config.v1", "repo_root": str(config.repo_root),
                "files": {name: hashlib.sha256(data).hexdigest() for name, data in encoded.items()}})


def _advisory_state(config: DesktopConfig, relative: str) -> dict[str, Any]:
    """OpenCode owns these files; an unreadable hint is ignored, never a launch failure."""
    state_path(config.state_dir, relative)
    try:
        return read_json(config.state_dir, relative) or {}
    except DesktopError:
        return {}


def prepare_workbench(config: DesktopConfig, *, model: str | None = None,
                      api_access: bool = False) -> PreparedWorkbench:
    """Prepare an isolated store without running OpenCode, providers, or installers.

    GLM coding credentials come from its existing declaration. api_access opts
    into importing existing metered keys, not control over later user /connect
    choices. OpenAI remains discoverable for explicit ChatGPT sign-in; native
    Codex/Claude OAuth is never copied.
    """
    executable = shutil.which("opencode")
    if not executable:
        raise DesktopError("OpenCode is not installed or is missing from PATH")
    executable = str(Path(executable).resolve())
    if (Path.home() / ".opencode").exists() or (Path.home() / ".opencode").is_symlink():
        raise DesktopError("A legacy ~/.opencode directory prevents isolated discovery; it was left untouched")
    provider, default = _glm_source()
    project = hashlib.sha256(str(config.repo_root).encode()).hexdigest()[:16]
    config_relative = f"workbench/{project}/config/opencode/opencode.json"
    tui_relative = f"workbench/{project}/config/opencode/tui.json"
    previous = read_json(config.state_dir, config_relative) or {}
    saved_model = _advisory_state(config, f"workbench/{project}/state/opencode/model.json")
    saved_ui = _advisory_state(config, f"workbench/{project}/state/opencode/kv.json")
    previous_tui = read_json(config.state_dir, tui_relative) or {}
    selected = model if model is not None else previous.get("model", default)
    environment = {key: value for key, value in os.environ.items()
                   if key in _BASE_ENV or key.startswith("LC_")}
    providers = {"glm-coding": _lift_credentials(provider, environment)}
    enabled = ["glm-coding", "opencode", "openai"]
    if api_access:
        credentials: dict[str, str] = {key: os.environ[key] for key in
                                       (PROVIDER_API_KEY_ENV_KEYS[p] for p in API_PROVIDERS) if key in os.environ}
        bootstrap_runtime_env(env=credentials)
        for name in API_PROVIDERS:
            key = PROVIDER_API_KEY_ENV_KEYS[name]
            if credentials.get(key):
                environment[key] = credentials[key]
                providers[name] = {"options": {"apiKey": "{env:" + key + "}"}}
                if name not in enabled:
                    enabled.append(name)
    if model is None and isinstance(saved_model.get("recent"), list):
        for recent in saved_model["recent"]:
            if (isinstance(recent, dict) and recent.get("providerID") in enabled
                    and isinstance(recent.get("modelID"), str)):
                selected = f"{recent['providerID']}/{recent['modelID']}"
                break
    if not isinstance(selected, str) or not re.fullmatch(
            r"[a-z0-9][a-z0-9_-]*/[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}", selected):
        raise DesktopError("model must be a provider/model identifier")
    provider_id, model_id = selected.split("/", 1)
    if provider_id not in enabled:
        raise DesktopError("Selected provider is unavailable; importing metered API keys requires explicit API access")
    if provider_id == "glm-coding" and model_id not in provider["models"]:
        raise DesktopError("Selected GLM model is not declared in the existing coding provider")
    _private_directory(config, "workbench")
    _private_directory(config, f"workbench/{project}")
    for kind in ("config", "data", "state", "cache"):
        path = _private_directory(config, f"workbench/{project}/{kind}")
        environment[f"XDG_{kind.upper()}_HOME"] = str(path)
    config_dir = _private_directory(config, f"workbench/{project}/config/opencode")
    config_path, tui_path = str(config_dir / "opencode.json"), str(config_dir / "tui.json")
    environment.update({"OPENCODE_CONFIG": config_path, "OPENCODE_CONFIG_DIR": str(config_dir),
                        "OPENCODE_TUI_CONFIG": tui_path, "OPENCODE_DISABLE_PROJECT_CONFIG": "1"})
    fragment = prepare_workbench_context(config)
    runtime = {"$schema": "https://opencode.ai/config.json", "model": selected,
               "enabled_providers": enabled, "provider": providers,
               "autoupdate": False, "share": "disabled", **fragment}
    theme = next((candidate for candidate in (saved_ui.get("theme"), previous_tui.get("theme"), "tokyonight")
                  if isinstance(candidate, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,80}", candidate)), "tokyonight")
    tui = {"$schema": "https://opencode.ai/tui.json", "theme": theme, "mouse": True,
           "diff_style": "auto", "keybinds": {"leader": "ctrl+x", "command_list": "ctrl+p",
           "model_list": "f4,<leader>m", "model_cycle_recent": "f2",
           "model_cycle_recent_reverse": "shift+f2", "session_list": "<leader>l",
           "session_interrupt": "escape,ctrl+c", "app_exit": "ctrl+q,ctrl+d,<leader>q"}}
    _write_configs(config, {config_relative: runtime, tui_relative: tui})
    argv = (executable, str(config.repo_root), "--continue")
    if model is not None or not previous:
        argv += ("--model", selected)
    return PreparedWorkbench(argv,
                             environment, config_path, tui_path, selected, tuple(enabled), api_access)
