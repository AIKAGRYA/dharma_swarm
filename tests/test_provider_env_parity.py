"""Provider env-surface parity: api_keys.py registry ↔ compose ↔ .env.example.

The provider/key truth has ONE owner: dharma_swarm/api_keys.py
(PROVIDER_API_KEY_ENV_KEYS, PROVIDER_BASE_URL_ENV_KEYS, ENV_ALIASES).
Everything else — the docker-compose provider env block, .env.example —
is a projection of it. Historically these projections were hand-copied
and drifted (compose passed 3 of 17 lanes to the swarm container; fresh
VPS agents concluded "we're low on keys"). This test makes that drift a
CI failure instead of a weeks-long confusion:

- every registry lane, base-URL override, and documented alias must be
  passed through to the web, swarm, and cron services in docker-compose;
- every registry API-key lane must be listed in .env.example;
- .env.example must not contain placeholder values that look like real
  secrets (sk-..., gsk_..., "...") — fake keys read as configured lanes.

To add a provider: registry first, then the compose x-provider-env block,
then .env.example. This test stays green only when all three agree.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from dharma_swarm.api_keys import (
    ENV_ALIASES,
    MOONSHOT_API_KEY_ENV,
    PROVIDER_API_KEY_ENV_KEYS,
    PROVIDER_BASE_URL_ENV_KEYS,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
COMPOSE_PATH = REPO_ROOT / "docker-compose.yml"
ENV_EXAMPLE_PATH = REPO_ROOT / ".env.example"

# Services that execute dharma code and therefore need the full lane surface.
DHARMA_SERVICES = ("web", "swarm", "cron")

# DEEPSEEK_API_KEY maps to itself (forward-compat alias, no first-class lane).
ALIAS_ENV_KEYS = frozenset(ENV_ALIASES.keys())
CANONICAL_KEY_ENVS = frozenset(PROVIDER_API_KEY_ENV_KEYS.values()) | {
    MOONSHOT_API_KEY_ENV
}
BASE_URL_ENVS = frozenset(PROVIDER_BASE_URL_ENV_KEYS.values())

COMPOSE_REQUIRED = CANONICAL_KEY_ENVS | BASE_URL_ENVS | ALIAS_ENV_KEYS
ENV_EXAMPLE_REQUIRED = CANONICAL_KEY_ENVS


def _compose_service_env_keys(service: str) -> set[str]:
    compose = yaml.safe_load(COMPOSE_PATH.read_text())
    env = compose["services"][service].get("environment") or {}
    if isinstance(env, dict):
        return set(env.keys())
    # list form: ["KEY=value", ...]
    return {item.split("=", 1)[0].lstrip("- ").strip() for item in env}


def _env_example_entries() -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in ENV_EXAMPLE_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        entries[key.strip()] = value.split("#", 1)[0].strip()
    return entries


def test_compose_passes_full_provider_surface_to_every_dharma_service():
    for service in DHARMA_SERVICES:
        present = _compose_service_env_keys(service)
        missing = sorted(COMPOSE_REQUIRED - present)
        assert not missing, (
            f"docker-compose service '{service}' does not receive these "
            f"provider env vars from the canonical registry "
            f"(dharma_swarm/api_keys.py): {missing}. Add them to the "
            f"x-provider-env block in docker-compose.yml."
        )


def test_env_example_lists_every_canonical_provider_lane():
    entries = _env_example_entries()
    missing = sorted(ENV_EXAMPLE_REQUIRED - set(entries))
    assert not missing, (
        f".env.example is missing canonical provider lanes {missing} — a "
        f"fresh agent reading it will not know these lanes exist. Keep it "
        f"in lockstep with PROVIDER_API_KEY_ENV_KEYS in api_keys.py."
    )


def test_env_example_has_no_fake_looking_secret_placeholders():
    suspicious: list[str] = []
    for key, value in _env_example_entries().items():
        if not key.endswith("_API_KEY") and not key.endswith("_SECRET_KEY"):
            continue
        # blank = honest "not configured"; anything else reads as a real key
        # to agents and humans skimming the file (the sk-or-... trap).
        if value:
            suspicious.append(f"{key}={value}")
    assert not suspicious, (
        f".env.example carries placeholder secret values that make unfunded "
        f"lanes look configured: {suspicious}. Leave key values blank."
    )
