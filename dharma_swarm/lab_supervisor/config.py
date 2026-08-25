"""Strict JSON configuration for the bounded lab supervisor."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence


CONFIG_SCHEMA = "dharma.lab_supervisor.config.v1"
_SECRET = re.compile(
    r"(?i)(api[-_]?key|authorization|bearer|password|secret|token)(?:\s|=|:|$)"
)
_SHELLS = frozenset({"sh", "bash", "zsh", "fish", "dash", "csh", "tcsh"})
_FORBIDDEN_TOOLS = frozenset(
    {"env", "sudo", "ssh", "scp", "rsync", "rm", "mv", "git", "gh", "curl", "wget"}
)
_FORBIDDEN_VERBS = frozenset(
    {
        "merge",
        "deploy",
        "push",
        "delete",
        "reset",
        "checkout",
        "clean",
        "install",
        "start",
        "restart",
        "enable",
        "disable",
        "reload",
        "daemon-reload",
        "unmask",
    }
)
_EVIDENCE_FORBIDDEN = re.compile(r"(?i)(\.env|credential|secret|api[-_]?key|token|wallet)")


class ConfigError(ValueError):
    """Configuration is unsafe, ambiguous, or malformed."""


def _keys(data: Mapping[str, Any], allowed: set[str], context: str) -> None:
    extra = sorted(set(data) - allowed)
    if extra:
        raise ConfigError(f"{context} has unknown fields: {extra}")


def _positive_int(value: Any, field_name: str, *, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > maximum:
        raise ConfigError(f"{field_name} must be an integer in 1..{maximum}")
    return value


def _non_negative(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ConfigError(f"{field_name} must be a non-negative number")
    return float(value)


def _boolean(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"{field_name} must be a boolean")
    return value


def _path(value: Any, field_name: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{field_name} must be a non-empty path")
    if "\x00" in value:
        raise ConfigError(f"{field_name} contains a NUL byte")
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        raise ConfigError(f"{field_name} must be absolute")
    if any(_EVIDENCE_FORBIDDEN.search(part) for part in candidate.parts):
        raise ConfigError(f"{field_name} looks secret-bearing and cannot be inspected")
    return candidate


@dataclass(frozen=True)
class CommandSpec:
    argv: tuple[str, ...]
    timeout_seconds: int = 30
    max_output_bytes: int = 32_768
    feature_argv: tuple[str, ...] = ()
    cwd: Path | None = None

    @classmethod
    def from_raw(cls, raw: Any, field_name: str) -> CommandSpec | None:
        if raw is None:
            return None
        if not isinstance(raw, Mapping):
            raise ConfigError(f"{field_name} must be an object")
        _keys(
            raw,
            {"argv", "timeout_seconds", "max_output_bytes", "feature_argv", "cwd"},
            field_name,
        )

        def normalized_argv(value: Any, nested_name: str, *, required: bool) -> tuple[str, ...]:
            if value is None and not required:
                return ()
            argv = value
            if not isinstance(argv, Sequence) or isinstance(argv, (str, bytes)) or not argv:
                raise ConfigError(f"{nested_name} must be a non-empty string array")
            normalized: list[str] = []
            for token in argv:
                if not isinstance(token, str) or not token or "\x00" in token:
                    raise ConfigError(f"{nested_name} entries must be non-empty strings")
                if _SECRET.search(token):
                    raise ConfigError(f"{nested_name} must not contain secrets")
                normalized.append(token)
            if not Path(normalized[0]).is_absolute():
                raise ConfigError(f"{nested_name} executable must be an absolute path")
            executable = Path(normalized[0]).name.lower()
            if executable in _SHELLS or executable in _FORBIDDEN_TOOLS:
                raise ConfigError(f"{nested_name} uses forbidden executable {executable!r}")
            if executable in {"docker", "podman"}:
                raise ConfigError(f"{nested_name} cannot invoke a container runtime directly")
            if executable.startswith("python") and "-c" in normalized[1:]:
                raise ConfigError(f"{nested_name} cannot run inline Python")
            lowered = {token.lower() for token in normalized[1:]}
            forbidden = sorted(lowered & _FORBIDDEN_VERBS)
            if forbidden:
                raise ConfigError(f"{nested_name} contains forbidden operations: {forbidden}")
            if executable == "systemctl":
                permitted = field_name.endswith(".keep_halted") and normalized[1:2] == ["stop"]
                if not permitted:
                    raise ConfigError(f"{nested_name} cannot control systemd")
            return tuple(normalized)

        argv = raw.get("argv")
        if not isinstance(argv, Sequence) or isinstance(argv, (str, bytes)) or not argv:
            raise ConfigError(f"{field_name}.argv must be a non-empty string array")
        normalized = normalized_argv(argv, f"{field_name}.argv", required=True)
        feature_argv = normalized_argv(
            raw.get("feature_argv"), f"{field_name}.feature_argv", required=False
        )
        cwd = _path(raw.get("cwd"), f"{field_name}.cwd") if raw.get("cwd") else None
        return cls(
            argv=normalized,
            timeout_seconds=_positive_int(
                raw.get("timeout_seconds", 30), f"{field_name}.timeout_seconds", maximum=3600
            ),
            max_output_bytes=_positive_int(
                raw.get("max_output_bytes", 32_768),
                f"{field_name}.max_output_bytes",
                maximum=1_048_576,
            ),
            feature_argv=feature_argv,
            cwd=cwd,
        )


@dataclass(frozen=True)
class LabConfig:
    name: str
    kind: str
    state_root: Path
    evidence_paths: tuple[Path, ...]
    halt_paths: tuple[Path, ...] = ()
    max_stale_seconds: float = 1800.0
    require_evidence: bool = True
    status_probe: CommandSpec | None = None
    keep_halted: CommandSpec | None = None
    quarantine_provider: CommandSpec | None = None
    rotate_provider: CommandSpec | None = None
    bounded_trial: CommandSpec | None = None
    trial_interval_seconds: float = 3600.0
    disposable_paths: tuple[Path, ...] = ()
    disposable_min_age_seconds: float = 86_400.0
    max_evidence_files: int = 64
    max_scan_entries: int = 4096

    @classmethod
    def from_raw(cls, raw: Any, index: int) -> LabConfig:
        context = f"labs[{index}]"
        if not isinstance(raw, Mapping):
            raise ConfigError(f"{context} must be an object")
        _keys(
            raw,
            {
                "name",
                "kind",
                "state_root",
                "evidence_paths",
                "halt_paths",
                "max_stale_seconds",
                "require_evidence",
                "status_probe",
                "keep_halted",
                "quarantine_provider",
                "rotate_provider",
                "bounded_trial",
                "trial_interval_seconds",
                "disposable_paths",
                "disposable_min_age_seconds",
                "max_evidence_files",
                "max_scan_entries",
            },
            context,
        )
        name = raw.get("name")
        kind = raw.get("kind")
        if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{1,63}", name):
            raise ConfigError(f"{context}.name must be a stable lowercase identifier")
        if kind not in {"sublimation_foundry", "rsi_lab", "generic"}:
            raise ConfigError(f"{context}.kind is unsupported")
        state_root = _path(raw.get("state_root"), f"{context}.state_root")

        def paths(field_name: str) -> tuple[Path, ...]:
            values = raw.get(field_name, [])
            if not isinstance(values, list):
                raise ConfigError(f"{context}.{field_name} must be an array")
            result = tuple(_path(value, f"{context}.{field_name}") for value in values)
            if len(set(result)) != len(result):
                raise ConfigError(f"{context}.{field_name} contains duplicates")
            return result

        evidence = paths("evidence_paths")
        if raw.get("require_evidence", True) and not evidence:
            raise ConfigError(f"{context}.evidence_paths cannot be empty when evidence is required")
        disposable = paths("disposable_paths")
        for candidate in disposable:
            if not candidate.is_relative_to(state_root):
                raise ConfigError(f"disposable path {candidate} must be below {state_root}")
            lowered = {part.lower() for part in candidate.relative_to(state_root).parts}
            if not lowered & {"tmp", "temp", "cache", "caches"}:
                raise ConfigError(f"disposable path {candidate} is not explicitly temp/cache named")
            if lowered & {"receipt", "receipts", "evidence", "archive", "archives", "runs"}:
                raise ConfigError(f"disposable path {candidate} overlaps durable evidence")
        return cls(
            name=name,
            kind=kind,
            state_root=state_root,
            evidence_paths=evidence,
            halt_paths=paths("halt_paths"),
            max_stale_seconds=_non_negative(
                raw.get("max_stale_seconds", 1800), f"{context}.max_stale_seconds"
            ),
            require_evidence=_boolean(
                raw.get("require_evidence", True), f"{context}.require_evidence"
            ),
            status_probe=CommandSpec.from_raw(raw.get("status_probe"), f"{context}.status_probe"),
            keep_halted=CommandSpec.from_raw(raw.get("keep_halted"), f"{context}.keep_halted"),
            quarantine_provider=CommandSpec.from_raw(
                raw.get("quarantine_provider"), f"{context}.quarantine_provider"
            ),
            rotate_provider=CommandSpec.from_raw(
                raw.get("rotate_provider"), f"{context}.rotate_provider"
            ),
            bounded_trial=CommandSpec.from_raw(
                raw.get("bounded_trial"), f"{context}.bounded_trial"
            ),
            trial_interval_seconds=_non_negative(
                raw.get("trial_interval_seconds", 3600), f"{context}.trial_interval_seconds"
            ),
            disposable_paths=disposable,
            disposable_min_age_seconds=_non_negative(
                raw.get("disposable_min_age_seconds", 86_400),
                f"{context}.disposable_min_age_seconds",
            ),
            max_evidence_files=_positive_int(
                raw.get("max_evidence_files", 64), f"{context}.max_evidence_files", maximum=1024
            ),
            max_scan_entries=_positive_int(
                raw.get("max_scan_entries", 4096),
                f"{context}.max_scan_entries",
                maximum=100_000,
            ),
        )


@dataclass(frozen=True)
class SupervisorPolicy:
    dry_run: bool = True
    cadence_seconds: int = 300
    max_subprocess_calls_per_tick: int = 8
    max_actions_per_lab_per_day: int = 24
    max_trials_per_lab_per_day: int = 5
    max_provider_actions_per_lab_per_day: int = 6
    max_cleanup_actions_per_lab_per_day: int = 2
    probe_retry_attempts: int = 2
    circuit_failure_threshold: int = 3
    circuit_cooldown_seconds: int = 1800
    min_free_disk_bytes: int = 1_073_741_824
    max_load_per_cpu: float = 2.0

    @classmethod
    def from_raw(cls, raw: Any) -> SupervisorPolicy:
        if raw is None:
            return cls()
        if not isinstance(raw, Mapping):
            raise ConfigError("policy must be an object")
        allowed = set(cls.__dataclass_fields__)
        _keys(raw, allowed, "policy")
        kwargs: dict[str, Any] = {
            "dry_run": _boolean(raw.get("dry_run", True), "policy.dry_run")
        }
        maxima = {
            "cadence_seconds": 86_400,
            "max_subprocess_calls_per_tick": 64,
            "max_actions_per_lab_per_day": 1000,
            "max_trials_per_lab_per_day": 100,
            "max_provider_actions_per_lab_per_day": 100,
            "max_cleanup_actions_per_lab_per_day": 100,
            "probe_retry_attempts": 5,
            "circuit_failure_threshold": 100,
            "circuit_cooldown_seconds": 604_800,
            "min_free_disk_bytes": 10**15,
        }
        defaults = cls()
        for field_name, maximum in maxima.items():
            kwargs[field_name] = _positive_int(
                raw.get(field_name, getattr(defaults, field_name)), field_name, maximum=maximum
            )
        # The v1 installer ships one fixed five-minute timer.  Reject a config
        # that would receipt a cadence the scheduler does not actually enforce.
        if kwargs["cadence_seconds"] != 300:
            raise ConfigError("policy.cadence_seconds must equal 300 for the v1 timer")
        load = raw.get("max_load_per_cpu", defaults.max_load_per_cpu)
        if isinstance(load, bool) or not isinstance(load, (int, float)) or not 0.1 <= load <= 100:
            raise ConfigError("max_load_per_cpu must be in 0.1..100")
        kwargs["max_load_per_cpu"] = float(load)
        return cls(**kwargs)


@dataclass(frozen=True)
class SupervisorConfig:
    labs: tuple[LabConfig, ...]
    policy: SupervisorPolicy = field(default_factory=SupervisorPolicy)
    schema: str = CONFIG_SCHEMA
    config_sha256: str = ""

    @classmethod
    def from_raw(cls, raw: Any) -> SupervisorConfig:
        if not isinstance(raw, Mapping):
            raise ConfigError("configuration must be a JSON object")
        _keys(raw, {"schema", "labs", "policy"}, "configuration")
        if raw.get("schema") != CONFIG_SCHEMA:
            raise ConfigError(f"schema must equal {CONFIG_SCHEMA!r}")
        labs_raw = raw.get("labs")
        if not isinstance(labs_raw, list) or not labs_raw:
            raise ConfigError("labs must be a non-empty array")
        labs = tuple(LabConfig.from_raw(value, index) for index, value in enumerate(labs_raw))
        names = [lab.name for lab in labs]
        if len(set(names)) != len(names):
            raise ConfigError("lab names must be unique")
        digest = hashlib.sha256(
            json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
                "utf-8"
            )
        ).hexdigest()
        return cls(
            labs=labs,
            policy=SupervisorPolicy.from_raw(raw.get("policy")),
            config_sha256=f"sha256:{digest}",
        )


def load_config(path: Path | str) -> SupervisorConfig:
    source = Path(path).expanduser()
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigError(f"cannot load supervisor config: {exc}") from exc
    return SupervisorConfig.from_raw(data)


def safe_subprocess_environment() -> dict[str, str]:
    """Return a static environment with no inherited credentials or import path."""

    return {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TMPDIR": "/tmp",
    }
