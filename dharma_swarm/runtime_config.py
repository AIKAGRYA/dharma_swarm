"""Canonical runtime configuration and state-root helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

EnvMap = Mapping[str, str | None]


def env_value(name: str, default: str = "", *, env: EnvMap | None = None) -> str:
    source = os.environ if env is None else env
    value = source.get(name)
    return str(value).strip() if value is not None else default


def env_bool(name: str, default: bool = False, *, env: EnvMap | None = None) -> bool:
    value = env_value(name, "", env=env).lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def env_int(name: str, default: int, *, env: EnvMap | None = None) -> int:
    value = env_value(name, "", env=env)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def env_float(name: str, default: float, *, env: EnvMap | None = None) -> float:
    value = env_value(name, "", env=env)
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def dharma_home(*, env: EnvMap | None = None) -> Path:
    configured = env_value("DHARMA_HOME", "", env=env)
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".dharma"


def dharma_path(*parts: str, env: EnvMap | None = None) -> Path:
    return dharma_home(env=env).joinpath(*parts)
