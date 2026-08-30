"""Hardened, read-only SSH preflight for a remote sovereign holon.

This module proves only that a configured SSH alias can authenticate and run one
fixed inventory probe.  It never deploys, synchronizes, bootstraps, copies
secrets, or treats authentication as authority for any of those actions.
"""

from __future__ import annotations

import ipaddress
import re
import subprocess
from typing import Any


SCHEMA_VERSION = "dharma.remote_holon_ssh_preflight.v1"
AUTHENTICATION_NOT_AUTHORIZATION = (
    "SSH authentication is observed connectivity, not authorization for deployment, "
    "synchronization, bootstrap, secret movement, or any command beyond this fixed "
    "read-only probe."
)

_SSH_ALIAS_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_HOLON_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_DOTTED_QUAD_RE = re.compile(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$")
_SAFE_REMOTE_TOKEN_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_MODE_RE = re.compile(r"^[0-7]{3,4}$")
_MAX_PROBE_OUTPUT_CHARS = 8192

_REPO_TAGS = frozenset(
    {
        "none",
        "home_dharma_swarm",
        "home_dharma-swarm",
        "opt_dharma_swarm",
        "opt_dharma-swarm",
    }
)
_PROBE_KEYS = frozenset(
    {
        "probe_version",
        "remote_user",
        "platform_system",
        "platform_machine",
        "repo_tag",
        "repo_present",
        "venv_present",
        "package_present",
        "bootstrap_present",
        "identity_present",
        "active_prompt_present",
        "key_store_present",
        "key_store_mode",
    }
)
_BOOLEAN_PROBE_KEYS = frozenset(
    {
        "repo_present",
        "venv_present",
        "package_present",
        "bootstrap_present",
        "identity_present",
        "active_prompt_present",
        "key_store_present",
    }
)

_FIXED_SSH_OPTIONS = (
    "BatchMode=yes",
    "IdentitiesOnly=yes",
    "StrictHostKeyChecking=yes",
    "ForwardAgent=no",
    "ClearAllForwardings=yes",
    "PermitLocalCommand=no",
    "ControlMaster=no",
    "ControlPath=none",
    "ProxyCommand=none",
    "ProxyJump=none",
    "UpdateHostKeys=no",
    "RequestTTY=no",
    "ConnectionAttempts=1",
    "LogLevel=ERROR",
)

# POSIX-sh only.  It emits an allowlisted line protocol, reads no file content,
# and performs no filesystem or service mutation.  Candidate paths are fixed;
# the only argument is a locally validated holon name.
REMOTE_PROBE = r"""set -u
holon_name=${1-}
home=${HOME:-}

remote_user=$(id -un 2>/dev/null || printf 'unknown')
platform_system=$(uname -s 2>/dev/null || printf 'unknown')
platform_machine=$(uname -m 2>/dev/null || printf 'unknown')

repo_tag=none
repo_path=
if [ -n "$home" ] && [ -f "$home/dharma_swarm/pyproject.toml" ]; then
    repo_tag=home_dharma_swarm
    repo_path=$home/dharma_swarm
elif [ -n "$home" ] && [ -f "$home/dharma-swarm/pyproject.toml" ]; then
    repo_tag=home_dharma-swarm
    repo_path=$home/dharma-swarm
elif [ -f /opt/dharma_swarm/pyproject.toml ]; then
    repo_tag=opt_dharma_swarm
    repo_path=/opt/dharma_swarm
elif [ -f /opt/dharma-swarm/pyproject.toml ]; then
    repo_tag=opt_dharma-swarm
    repo_path=/opt/dharma-swarm
fi

repo_present=0
venv_present=0
package_present=0
bootstrap_present=0
if [ -n "$repo_path" ]; then
    repo_present=1
    [ -x "$repo_path/.venv/bin/python" ] && venv_present=1
    [ -f "$repo_path/dharma_swarm/__init__.py" ] && package_present=1
    [ -f "$repo_path/dharma_swarm/holon_system/identity/bootstrap.py" ] && bootstrap_present=1
fi

identity_present=0
active_prompt_present=0
if [ -n "$home" ]; then
    identity_path=$home/.dharma/agents/$holon_name/identity.json
    active_prompt_path=$home/.dharma/agents/$holon_name/prompt_variants/active.txt
    [ -f "$identity_path" ] && identity_present=1
    [ -f "$active_prompt_path" ] && active_prompt_present=1
fi

key_store_present=0
key_store_mode=none
if [ -n "$home" ]; then
    key_store_path=$home/.dharma/agent_keys.env
    if [ -f "$key_store_path" ] && [ ! -L "$key_store_path" ]; then
        key_store_present=1
        key_store_mode=$(stat -c '%a' "$key_store_path" 2>/dev/null || true)
        if [ -z "$key_store_mode" ]; then
            key_store_mode=$(stat -f '%Lp' "$key_store_path" 2>/dev/null || true)
        fi
        [ -n "$key_store_mode" ] || key_store_mode=unknown
    fi
fi

printf 'probe_version\t1\n'
printf 'remote_user\t%s\n' "$remote_user"
printf 'platform_system\t%s\n' "$platform_system"
printf 'platform_machine\t%s\n' "$platform_machine"
printf 'repo_tag\t%s\n' "$repo_tag"
printf 'repo_present\t%s\n' "$repo_present"
printf 'venv_present\t%s\n' "$venv_present"
printf 'package_present\t%s\n' "$package_present"
printf 'bootstrap_present\t%s\n' "$bootstrap_present"
printf 'identity_present\t%s\n' "$identity_present"
printf 'active_prompt_present\t%s\n' "$active_prompt_present"
printf 'key_store_present\t%s\n' "$key_store_present"
printf 'key_store_mode\t%s\n' "$key_store_mode"
"""


class RemoteHolonPreflightError(ValueError):
    """Raised when local preflight inputs violate the fixed safety contract."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _validate_ssh_alias(alias: str) -> str:
    if not isinstance(alias, str) or not alias:
        raise RemoteHolonPreflightError("invalid_ssh_alias", "SSH alias is required.")
    if "@" in alias:
        raise RemoteHolonPreflightError(
            "invalid_ssh_alias",
            "SSH destination must be a configured alias, not user@host.",
        )
    if _DOTTED_QUAD_RE.fullmatch(alias):
        raise RemoteHolonPreflightError(
            "invalid_ssh_alias",
            "IP literals are not accepted; use a configured SSH alias.",
        )
    try:
        ipaddress.ip_address(alias)
    except ValueError:
        pass
    else:
        raise RemoteHolonPreflightError(
            "invalid_ssh_alias",
            "IP literals are not accepted; use a configured SSH alias.",
        )
    if not _SSH_ALIAS_RE.fullmatch(alias):
        raise RemoteHolonPreflightError(
            "invalid_ssh_alias",
            "SSH alias contains unsupported characters.",
        )
    return alias


def _validate_holon_name(name: str) -> str:
    if not isinstance(name, str) or not _HOLON_NAME_RE.fullmatch(name):
        raise RemoteHolonPreflightError(
            "invalid_holon_name",
            "Holon name must be a single safe identity token.",
        )
    return name


def _validate_timeout(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 15:
        raise RemoteHolonPreflightError(
            "invalid_timeout",
            "Connect timeout must be an integer from 1 through 15 seconds.",
        )
    return value


def _parse_ssh_config(alias: str, stdout: str) -> None:
    values: dict[str, str] = {}
    if len(stdout) > _MAX_PROBE_OUTPUT_CHARS * 4:
        raise ValueError("oversized SSH configuration output")
    for raw_line in stdout.splitlines():
        key, separator, value = raw_line.partition(" ")
        if separator and key in {"hostname", "user", "port"} and key not in values:
            values[key] = value.strip()
    if not values.get("hostname") or not values.get("user"):
        raise ValueError("incomplete SSH configuration")
    # ``ssh -G`` also succeeds for arbitrary DNS names through ``Host *``.
    # Requiring a distinct resolved HostName makes the supplied token prove it
    # is an actual configured alias for this control surface.
    if values["hostname"].casefold() == alias.casefold():
        raise ValueError("SSH destination is not an explicitly mapped alias")
    try:
        port = int(values.get("port", "22"))
    except ValueError as exc:
        raise ValueError("invalid SSH port") from exc
    if not 1 <= port <= 65535:
        raise ValueError("invalid SSH port")


def _ssh_probe_argv(alias: str, holon_name: str, connect_timeout: int) -> list[str]:
    argv = ["ssh", "-T"]
    for option in _FIXED_SSH_OPTIONS:
        argv.extend(("-o", option))
    argv.extend(
        (
            "-o",
            f"ConnectTimeout={connect_timeout}",
            "--",
            alias,
            "sh",
            "-s",
            "--",
            holon_name,
        )
    )
    return argv


def _parse_bool(value: str) -> bool:
    if value not in {"0", "1"}:
        raise ValueError("invalid boolean probe value")
    return value == "1"


def _parse_probe(stdout: str) -> dict[str, Any]:
    if len(stdout) > _MAX_PROBE_OUTPUT_CHARS:
        raise ValueError("oversized probe output")
    values: dict[str, str] = {}
    for raw_line in stdout.splitlines():
        key, separator, value = raw_line.partition("\t")
        if not separator or key not in _PROBE_KEYS or key in values:
            raise ValueError("unexpected probe output")
        if len(value) > 128:
            raise ValueError("oversized probe field")
        values[key] = value
    if values.keys() != _PROBE_KEYS or values.get("probe_version") != "1":
        raise ValueError("incomplete probe output")

    for key in _BOOLEAN_PROBE_KEYS:
        _parse_bool(values[key])
    for key in ("remote_user", "platform_system", "platform_machine"):
        if not _SAFE_REMOTE_TOKEN_RE.fullmatch(values[key]):
            raise ValueError("unsafe remote identity field")
    if values["repo_tag"] not in _REPO_TAGS:
        raise ValueError("unknown repository location")

    repo_present = _parse_bool(values["repo_present"])
    if repo_present == (values["repo_tag"] == "none"):
        raise ValueError("inconsistent repository observation")

    key_store_present = _parse_bool(values["key_store_present"])
    mode: str | None = None
    mode_is_safe = False
    raw_mode = values["key_store_mode"]
    if key_store_present:
        if not _MODE_RE.fullmatch(raw_mode):
            raise ValueError("invalid key-store mode")
        mode_digits = raw_mode[-3:]
        mode = f"0{mode_digits}"
        mode_is_safe = mode_digits in {"400", "600"}
    elif raw_mode != "none":
        raise ValueError("unexpected absent key-store mode")

    return {
        "user": values["remote_user"],
        "platform": {
            "system": values["platform_system"],
            "machine": values["platform_machine"],
        },
        "runtime_candidate": {
            "repository_present": repo_present,
            "repository_location": values["repo_tag"] if repo_present else None,
            "venv_python_present": _parse_bool(values["venv_present"]),
            "package_source_present": _parse_bool(values["package_present"]),
            "bootstrap_module_present": _parse_bool(values["bootstrap_present"]),
        },
        "canonical_identity": {
            "identity_present": _parse_bool(values["identity_present"]),
            "active_prompt_present": _parse_bool(values["active_prompt_present"]),
        },
        "key_store": {
            "present": key_store_present,
            "mode": mode,
            "safe_mode": mode_is_safe,
            "content_read": False,
        },
    }


def _authority(authentication_observed: bool) -> dict[str, Any]:
    return {
        "authentication_observed": authentication_observed,
        "authorization_granted": False,
        "mutation_authority": False,
        "claim": AUTHENTICATION_NOT_AUTHORIZATION,
    }


def _operation_contract() -> dict[str, Any]:
    return {
        "mode": "fixed_read_only_probe",
        "remote_writes_requested": False,
        "deploy_requested": False,
        "sync_requested": False,
        "bootstrap_requested": False,
        "secret_values_read": False,
    }


def _failure_result(
    *,
    code: str,
    message: str,
    ssh_alias: str | None,
    holon_name: str | None,
    config_resolved: bool,
    authentication_observed: bool,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": False,
        "status": "error",
        "ssh": {
            "alias": ssh_alias,
            "config_resolved": config_resolved,
            "authentication_observed": authentication_observed,
        },
        "holon": {"name": holon_name},
        "observations": None,
        "readiness": {
            "materialization_ready": False,
            "identity_ready": False,
            "activation_ready": False,
            "provider_readiness_inferred": False,
            "key_store_required_for_materialization": False,
        },
        "authority": _authority(authentication_observed),
        "operation_contract": _operation_contract(),
        "error": {"code": code, "message": message},
    }


def _runtime_failure(
    alias: str,
    name: str,
    code: str,
    message: str,
    *,
    config_resolved: bool = False,
    authentication_observed: bool = False,
) -> dict[str, Any]:
    return _failure_result(
        code=code,
        message=message,
        ssh_alias=alias,
        holon_name=name,
        config_resolved=config_resolved,
        authentication_observed=authentication_observed,
    )


def invalid_input_result(error: RemoteHolonPreflightError) -> dict[str, Any]:
    """Return a structured CLI-safe result without reflecting rejected input."""
    return _failure_result(
        code=error.code,
        message=str(error),
        ssh_alias=None,
        holon_name=None,
        config_resolved=False,
        authentication_observed=False,
    )


def run_remote_holon_preflight(
    ssh_alias: str,
    holon_name: str,
    *,
    connect_timeout: int = 5,
) -> dict[str, Any]:
    """Run the fixed read-only probe through a configured SSH alias."""
    alias = _validate_ssh_alias(ssh_alias)
    name = _validate_holon_name(holon_name)
    timeout = _validate_timeout(connect_timeout)

    try:
        config = subprocess.run(
            ["ssh", "-G", "--", alias],
            check=False,
            capture_output=True,
            text=True,
            timeout=min(timeout, 5),
        )
    except FileNotFoundError:
        return _runtime_failure(
            alias, name, "ssh_unavailable", "OpenSSH client is unavailable."
        )
    except subprocess.TimeoutExpired:
        return _runtime_failure(
            alias, name, "ssh_config_timeout", "SSH alias resolution timed out."
        )

    if config.returncode != 0:
        return _runtime_failure(
            alias,
            name,
            "ssh_config_failed",
            "SSH alias could not be resolved through local OpenSSH configuration.",
        )
    try:
        _parse_ssh_config(alias, config.stdout)
    except ValueError:
        return _runtime_failure(
            alias,
            name,
            "ssh_config_invalid",
            "SSH alias resolution returned an incomplete configuration.",
        )

    try:
        completed = subprocess.run(
            _ssh_probe_argv(alias, name, timeout),
            check=False,
            capture_output=True,
            text=True,
            input=REMOTE_PROBE,
            timeout=timeout + 5,
        )
    except FileNotFoundError:
        return _runtime_failure(
            alias,
            name,
            "ssh_unavailable",
            "OpenSSH client is unavailable.",
            config_resolved=True,
        )
    except subprocess.TimeoutExpired:
        return _runtime_failure(
            alias,
            name,
            "ssh_probe_timeout",
            "SSH authentication or the fixed read-only probe timed out.",
            config_resolved=True,
        )

    authentication_observed = completed.returncode != 255
    if completed.returncode != 0:
        code = "ssh_authentication_failed" if completed.returncode == 255 else "remote_probe_failed"
        message = (
            "SSH authentication or transport failed under noninteractive policy."
            if completed.returncode == 255
            else "The fixed read-only remote probe did not complete."
        )
        return _runtime_failure(
            alias,
            name,
            code,
            message,
            config_resolved=True,
            authentication_observed=authentication_observed,
        )

    try:
        observations = _parse_probe(completed.stdout)
    except ValueError:
        return _runtime_failure(
            alias,
            name,
            "remote_probe_output_invalid",
            "The fixed read-only remote probe returned invalid structured output.",
            config_resolved=True,
            authentication_observed=True,
        )

    runtime = observations["runtime_candidate"]
    identity = observations["canonical_identity"]
    materialization_ready = all(
        (
            runtime["repository_present"],
            runtime["venv_python_present"],
            runtime["package_source_present"],
            runtime["bootstrap_module_present"],
        )
    )
    identity_ready = all(
        (
            identity["identity_present"],
            identity["active_prompt_present"],
        )
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "status": "observed",
        "ssh": {
            "alias": alias,
            "config_resolved": True,
            "authentication_observed": True,
        },
        "holon": {"name": name},
        "observations": observations,
        "readiness": {
            "materialization_ready": materialization_ready,
            "identity_ready": identity_ready,
            "activation_ready": False,
            "provider_readiness_inferred": False,
            "key_store_required_for_materialization": False,
        },
        "authority": _authority(True),
        "operation_contract": _operation_contract(),
        "error": None,
    }


__all__ = [
    "AUTHENTICATION_NOT_AUTHORIZATION",
    "REMOTE_PROBE",
    "RemoteHolonPreflightError",
    "invalid_input_result",
    "run_remote_holon_preflight",
]
