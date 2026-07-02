"""Unified model pool registry for routing, scouting, and operator inspection.

This module is intentionally broader than ``model_hierarchy``.  The hierarchy
owns canonical provider defaults; the pool registry inventories every known
routeable or soon-routeable model lane from local config, A2A cards, free-fleet
discovery, provider-matrix targets, and optional live provider catalogs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping
import json
import shutil
import subprocess
import urllib.request

from dharma_swarm.api_keys import (
    NVIDIA_API_KEY_ENV,
    NVIDIA_NIM_API_KEY_ENV,
    bootstrap_runtime_env,
    env_value,
)
from dharma_swarm.model_hierarchy import (
    CANONICAL_SEED_ORDER,
    DEFAULT_MODELS,
    get_tier,
    provider_lane_role,
)
from dharma_swarm.models import ProviderType
from dharma_swarm.ollama_config import OLLAMA_CLOUD_FRONTIER_MODELS
from dharma_swarm.runtime_provider import resolve_runtime_provider_config


DEFAULT_DHARMA_HOME = Path("~/.dharma").expanduser()
DEFAULT_OLLAMA_HOME = Path("~/.ollama").expanduser()

NIM_PRIORITY_MODELS: tuple[str, ...] = (
    "deepseek-ai/deepseek-v4-pro",
    "deepseek-ai/deepseek-v4-flash",
    "moonshotai/kimi-k2.6",
    "minimaxai/minimax-m3",
    "minimaxai/minimax-m2.7",
    "mistralai/mistral-large-3-675b-instruct-2512",
    "mistralai/mistral-medium-3.5-128b",
    "mistralai/mistral-large-2-instruct",
    "meta/llama-4-maverick-17b-128e-instruct",
    "nvidia/nemotron-3-ultra-550b-a55b",
    "nvidia/nemotron-3-super-120b-a12b",
    "nvidia/nemotron-4-340b-instruct",
    "qwen/qwen3.5-397b-a17b",
    "qwen/qwen3.5-122b-a10b",
    "qwen/qwen3-next-80b-a3b-instruct",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
)

DIRECT_KEY_CLUSTER_MODELS: dict[str, tuple[str, ...]] = {
    "zai_coding": ("z-ai/glm-5", "glm-5.2:cloud", "glm-5:cloud"),
    "zai_global": ("z-ai/glm-5",),
    "kimi": ("moonshotai/kimi-k2.6", "kimi-k2.7-code:cloud", "kimi-k2.5:cloud"),
    "minimax": ("minimaxai/minimax-m3", "minimax-m3:cloud", "minimax-m2.7:cloud"),
    "deepseek": ("deepseek-ai/deepseek-v4-pro", "deepseek-v3.2:cloud", "deepseek-v3.1:671b-cloud"),
    "gemini": ("gemini-2.5-flash",),
}


@dataclass(frozen=True, slots=True)
class ModelPoolEntry:
    provider: str
    model: str
    route: str
    cost_tier: str
    lane_role: str
    source: str
    availability: str = "unknown"
    status: str = ""
    power_score: int = 50
    context_length: int | None = None
    max_output_tokens: int | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["tags"] = list(self.tags)
        return data


@dataclass(frozen=True, slots=True)
class ModelPoolSnapshot:
    entries: tuple[ModelPoolEntry, ...]
    sources: tuple[str, ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def top(self, limit: int = 40) -> tuple[ModelPoolEntry, ...]:
        return self.entries[:limit]

    def to_dict(self) -> dict[str, Any]:
        by_provider: dict[str, int] = {}
        by_availability: dict[str, int] = {}
        for entry in self.entries:
            by_provider[entry.provider] = by_provider.get(entry.provider, 0) + 1
            by_availability[entry.availability] = by_availability.get(entry.availability, 0) + 1
        return {
            "total_models": len(self.entries),
            "sources": list(self.sources),
            "warnings": list(self.warnings),
            "by_provider": dict(sorted(by_provider.items())),
            "by_availability": dict(sorted(by_availability.items())),
            "entries": [entry.to_dict() for entry in self.entries],
        }


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in values:
        value = str(raw or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return tuple(out)


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _key_status_rows(dharma_home: Path) -> dict[str, dict[str, Any]]:
    payload = _load_json(dharma_home / "keys_status.json")
    rows = payload.get("rows", {}) if isinstance(payload, dict) else {}
    return rows if isinstance(rows, dict) else {}


def _status_for_provider(provider: str, status_rows: Mapping[str, Mapping[str, Any]]) -> tuple[str, str]:
    aliases = {
        "ollama": ("ollama_cloud",),
        "nvidia_nim": ("nvidia_nim",),
        "google_ai": ("gemini",),
        "claude_code": ("claude_code",),
        "codex": ("codex (openai-pro)",),
        "openrouter": ("openrouter",),
        "openrouter_free": ("openrouter",),
        "openai": ("openai",),
        "anthropic": ("anthropic",),
        "groq": ("groq",),
    }
    for key in aliases.get(provider, (provider,)):
        row = status_rows.get(key)
        if not row:
            continue
        status = str(row.get("status") or "")
        key_present = bool(row.get("key_present"))
        http = row.get("http")
        if status == "live" or http == 200:
            return "live_verified", status or "live"
        if "oauth present" in status or "Max plan" in status:
            return "credential_present", status
        if key_present and ("rate" in status.lower() or "funds=0" in status or http in {400, 403, 404, 429}):
            return "degraded", status
        if key_present:
            return "configured", status
        return "missing", status or "no key"
    return "unknown", ""


def _status_for_config(
    provider: ProviderType,
    status_rows: Mapping[str, Mapping[str, Any]],
    env: Mapping[str, str] | None,
) -> tuple[str, str]:
    availability, status = _status_for_provider(provider.value, status_rows)
    if availability != "unknown":
        return availability, status
    try:
        cfg = resolve_runtime_provider_config(provider, env=env)
    except Exception as exc:
        return "error", f"{type(exc).__name__}: {exc}"
    if cfg.available:
        return "configured", "runtime config available"
    return "missing", "runtime config unavailable"


def _tags_for_model(model: str) -> tuple[str, ...]:
    lowered = model.lower()
    tags: list[str] = []
    if any(token in lowered for token in ("code", "coder", "codex", "codestral", "starcoder")):
        tags.append("code")
    if any(token in lowered for token in ("opus", "gpt-5", "glm-5", "deepseek", "kimi", "nemotron", "qwen", "reason")):
        tags.append("reasoning")
    if any(token in lowered for token in ("vision", "vl", "multimodal", "omni", "gemma4", "maverick")):
        tags.append("multimodal")
    if any(token in lowered for token in ("embed", "retriever", "bge", "nomic-embed")):
        tags.append("embedding")
    if ":free" in lowered:
        tags.append("free")
    if ":cloud" in lowered:
        tags.append("cloud")
    return _ordered_unique(tags)


def estimate_power_score(model: str, provider: str = "", *, context_length: int | None = None) -> int:
    lowered = f"{provider}/{model}".lower()
    explicit: tuple[tuple[str, int], ...] = (
        ("claude-opus-4-8", 99),
        ("gpt-5.5", 99),
        ("codex-5.5", 99),
        ("claude-opus-4-7", 98),
        ("gpt-5.4", 97),
        ("claude-opus-4-6", 97),
        ("gpt-5", 96),
        ("glm-5.2", 96),
        ("kimi-k2.7", 96),
        ("minimax-m3", 96),
        ("deepseek-v4-pro", 96),
        ("nemotron-3-ultra-550b", 96),
        ("mistral-large-3-675b", 96),
        ("qwen3-coder:480b", 95),
        ("qwen3-coder-480b", 95),
        ("deepseek-v3.2", 95),
        ("deepseek-v3.1:671b", 95),
        ("kimi-k2.6", 95),
        ("qwen3.5-397b", 95),
        ("nemotron-4-340b", 94),
        ("gpt-oss-120b", 93),
        ("nemotron-3-super-120b", 93),
        ("hermes-3-llama-3.1-405b", 93),
        ("llama-4-maverick", 92),
        ("mistral-medium-3.5", 91),
        ("gemini-2.5-flash", 90),
    )
    for token, score in explicit:
        if token in lowered:
            return score
    score = 70
    if any(token in lowered for token in ("70b", "80b", "120b", "122b", "128b")):
        score = max(score, 86)
    if any(token in lowered for token in ("235b", "253b", "340b", "397b", "405b", "480b", "550b", "671b", "675b")):
        score = max(score, 92)
    if context_length and context_length >= 250_000:
        score += 2
    if context_length and context_length >= 1_000_000:
        score += 2
    if any(token in lowered for token in ("nano", "mini", "small", "flash")):
        score -= 4
    return max(1, min(score, 99))


def _entry(
    *,
    provider: str,
    model: str,
    route: str,
    cost_tier: str,
    lane_role: str,
    source: str,
    availability: str = "unknown",
    status: str = "",
    context_length: int | None = None,
    max_output_tokens: int | None = None,
    tags: Iterable[str] = (),
) -> ModelPoolEntry:
    merged_tags = _ordered_unique([*tags, *_tags_for_model(model)])
    return ModelPoolEntry(
        provider=provider,
        model=model,
        route=route,
        cost_tier=cost_tier,
        lane_role=lane_role,
        source=source,
        availability=availability,
        status=status,
        context_length=context_length,
        max_output_tokens=max_output_tokens,
        tags=merged_tags,
        power_score=estimate_power_score(model, provider, context_length=context_length),
    )


def _iter_canonical_entries(
    status_rows: Mapping[str, Mapping[str, Any]],
    env: Mapping[str, str] | None,
) -> Iterable[ModelPoolEntry]:
    for provider in CANONICAL_SEED_ORDER:
        model = DEFAULT_MODELS.get(provider)
        if not model:
            continue
        availability, status = _status_for_config(provider, status_rows, env)
        yield _entry(
            provider=provider.value,
            model=model,
            route="runtime_provider",
            cost_tier=get_tier(provider),
            lane_role=provider_lane_role(provider).value,
            source="model_hierarchy",
            availability=availability,
            status=status,
        )


def _iter_free_fleet_entries(status_rows: Mapping[str, Mapping[str, Any]]) -> Iterable[ModelPoolEntry]:
    from dharma_swarm.free_fleet import FREE_FLEET

    availability, status = _status_for_provider("openrouter_free", status_rows)
    for tier, models in sorted(FREE_FLEET.tier_models.items()):
        for model in models:
            yield _entry(
                provider="openrouter_free",
                model=model,
                route="openrouter_free",
                cost_tier=f"free_tier_{tier}",
                lane_role="research_delegate" if tier == 1 else "general_support",
                source="free_fleet",
                availability=availability,
                status=status,
                tags=(f"tier_{tier}",),
            )


def _iter_ollama_config_entries(
    ollama_home: Path,
    status_rows: Mapping[str, Mapping[str, Any]],
    *,
    include_ollama_list: bool,
) -> Iterable[ModelPoolEntry]:
    availability, status = _status_for_provider("ollama", status_rows)
    for model in OLLAMA_CLOUD_FRONTIER_MODELS:
        yield _entry(
            provider="ollama",
            model=model,
            route="ollama_cloud",
            cost_tier="free",
            lane_role="research_delegate",
            source="ollama_config",
            availability=availability,
            status=status,
        )

    recommendations = _load_json(ollama_home / "cache" / "model-recommendations.json")
    for item in recommendations.get("recommendations", []) if isinstance(recommendations, dict) else []:
        if not isinstance(item, dict) or not item.get("model"):
            continue
        yield _entry(
            provider="ollama",
            model=str(item["model"]),
            route="ollama_cloud" if str(item["model"]).endswith(":cloud") else "ollama_local_or_cloud",
            cost_tier=str(item.get("required_plan") or "local"),
            lane_role="bulk_builder" if "code" in str(item["model"]).lower() else "research_delegate",
            source="ollama_recommendations",
            availability=availability,
            status=status,
            context_length=int(item["context_length"]) if isinstance(item.get("context_length"), int) else None,
            max_output_tokens=int(item["max_output_tokens"]) if isinstance(item.get("max_output_tokens"), int) else None,
        )

    config = _load_json(ollama_home / "config.json")
    if isinstance(config, dict):
        for model in _ordered_unique([
            str(config.get("last_model") or ""),
            *[
                str(model)
                for integration in (config.get("integrations") or {}).values()
                if isinstance(integration, dict)
                for model in integration.get("models", [])
            ],
        ]):
            yield _entry(
                provider="ollama",
                model=model,
                route="ollama_config",
                cost_tier="configured",
                lane_role="research_delegate",
                source="ollama_config_file",
                availability=availability,
                status=status,
            )

    if include_ollama_list:
        yield from _iter_ollama_list_entries(availability=availability, status=status)


def _iter_ollama_list_entries(*, availability: str, status: str) -> Iterable[ModelPoolEntry]:
    if shutil.which("ollama") is None:
        return
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except Exception:
        return
    if result.returncode != 0:
        return
    for line in result.stdout.splitlines()[1:]:
        parts = line.split()
        if not parts:
            continue
        model = parts[0]
        yield _entry(
            provider="ollama",
            model=model,
            route="ollama_list",
            cost_tier="local_or_cloud",
            lane_role="research_delegate",
            source="ollama_list",
            availability=availability,
            status=status,
        )


def _iter_provider_matrix_entries(
    status_rows: Mapping[str, Mapping[str, Any]],
    env: Mapping[str, str] | None,
) -> Iterable[ModelPoolEntry]:
    try:
        from dharma_swarm.provider_matrix import build_default_matrix_targets
    except Exception:
        return
    try:
        targets = build_default_matrix_targets(profile="live25", include_unavailable=True, env=env)
    except Exception:
        return
    for target in targets:
        availability, status = _status_for_provider(target.provider.value, status_rows)
        if availability == "unknown":
            availability = "configured" if target.available else "missing"
            status = target.availability_reason
        yield _entry(
            provider=target.provider.value,
            model=target.model,
            route="provider_matrix",
            cost_tier=get_tier(target.provider),
            lane_role=target.lane_role.value,
            source="provider_matrix",
            availability=availability,
            status=status,
        )


def _iter_nim_priority_entries(status_rows: Mapping[str, Mapping[str, Any]]) -> Iterable[ModelPoolEntry]:
    availability, status = _status_for_provider("nvidia_nim", status_rows)
    for model in NIM_PRIORITY_MODELS:
        yield _entry(
            provider="nvidia_nim",
            model=model,
            route="nvidia_nim",
            cost_tier="free",
            lane_role="challenger",
            source="nim_priority",
            availability=availability,
            status=status,
        )


def _fetch_nim_model_ids(timeout_seconds: float = 20.0) -> tuple[str, ...]:
    bootstrap_runtime_env()
    token = env_value(NVIDIA_NIM_API_KEY_ENV) or env_value(NVIDIA_API_KEY_ENV)
    if not token:
        return ()
    req = urllib.request.Request(
        "https://integrate.api.nvidia.com/v1/models",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    ids = [
        str(item.get("id") or item.get("name") or "").strip()
        for item in payload.get("data", [])
        if isinstance(item, dict)
    ]
    return _ordered_unique(ids)


def _iter_nim_live_entries(status_rows: Mapping[str, Mapping[str, Any]]) -> Iterable[ModelPoolEntry]:
    availability, status = _status_for_provider("nvidia_nim", status_rows)
    for model in _fetch_nim_model_ids():
        yield _entry(
            provider="nvidia_nim",
            model=model,
            route="nvidia_nim_live_catalog",
            cost_tier="free",
            lane_role="general_support",
            source="nim_live_catalog",
            availability=availability,
            status=status,
        )


def _iter_direct_key_cluster_entries(status_rows: Mapping[str, Mapping[str, Any]]) -> Iterable[ModelPoolEntry]:
    for cluster, models in DIRECT_KEY_CLUSTER_MODELS.items():
        row = status_rows.get(cluster, {})
        status = str(row.get("status") or "")
        if status == "live" or row.get("http") == 200:
            availability = "live_verified"
        elif bool(row.get("key_present")):
            availability = "degraded" if row.get("http") in {400, 403, 404, 429} else "configured"
        else:
            availability = "missing"
        for model in models:
            yield _entry(
                provider=cluster,
                model=model,
                route="direct_key_cluster",
                cost_tier="external_key",
                lane_role="research_delegate",
                source="keys_status",
                availability=availability,
                status=status,
                tags=("needs_first_class_provider" if cluster not in {"gemini"} else "direct_supported",),
            )


def _iter_a2a_card_entries(a2a_cards_dir: Path) -> Iterable[ModelPoolEntry]:
    if not a2a_cards_dir.exists():
        return
    for path in sorted(a2a_cards_dir.glob("*.json")):
        payload = _load_json(path)
        if not isinstance(payload, dict):
            continue
        models: list[str] = []

        def walk(value: Any) -> None:
            if isinstance(value, dict):
                for key, nested in value.items():
                    if "model" in str(key).lower() and isinstance(nested, str):
                        models.append(nested)
                    walk(nested)
            elif isinstance(value, list):
                for nested in value:
                    walk(nested)

        walk(payload)
        for model in _ordered_unique(models):
            if not model or model in {"codex", "hermes-agent"}:
                continue
            yield _entry(
                provider=_provider_from_model_identity(model),
                model=model,
                route=f"a2a_card:{path.stem}",
                cost_tier="identity",
                lane_role="primary_driver" if any(token in model.lower() for token in ("opus", "gpt-5", "codex")) else "general_support",
                source="a2a_card",
                availability="identity_declared",
                status=path.name,
            )


def _provider_from_model_identity(model: str) -> str:
    lowered = model.lower()
    if "claude" in lowered or "anthropic" in lowered:
        return "claude_code"
    if "gpt" in lowered or "codex" in lowered or "openai" in lowered:
        return "codex"
    if "kimi" in lowered or "moonshot" in lowered:
        return "kimi"
    if "qwen" in lowered:
        return "qwen"
    return "a2a_identity"


def _dedupe_entries(entries: Iterable[ModelPoolEntry]) -> tuple[ModelPoolEntry, ...]:
    by_key: dict[tuple[str, str], ModelPoolEntry] = {}
    availability_rank = {
        "live_verified": 7,
        "credential_present": 6,
        "configured": 5,
        "identity_declared": 4,
        "degraded": 3,
        "unknown": 2,
        "missing": 1,
        "error": 0,
    }
    for entry in entries:
        key = (entry.provider, entry.model)
        previous = by_key.get(key)
        if previous is None:
            by_key[key] = entry
            continue
        source = ",".join(_ordered_unique([previous.source, entry.source]))
        tags = _ordered_unique([*previous.tags, *entry.tags])
        chosen = entry if availability_rank.get(entry.availability, 0) > availability_rank.get(previous.availability, 0) else previous
        by_key[key] = ModelPoolEntry(
            provider=previous.provider,
            model=previous.model,
            route=chosen.route,
            cost_tier=chosen.cost_tier if chosen.cost_tier != "unknown" else previous.cost_tier,
            lane_role=chosen.lane_role if chosen.lane_role != "general_support" else previous.lane_role,
            source=source,
            availability=chosen.availability,
            status=chosen.status or previous.status,
            power_score=max(previous.power_score, entry.power_score),
            context_length=previous.context_length or entry.context_length,
            max_output_tokens=previous.max_output_tokens or entry.max_output_tokens,
            tags=tags,
        )
    return tuple(
        sorted(
            by_key.values(),
            key=lambda item: (
                -item.power_score,
                item.availability not in {"live_verified", "credential_present", "configured"},
                item.provider,
                item.model,
            ),
        )
    )


def build_model_pool_snapshot(
    *,
    dharma_home: Path | None = None,
    ollama_home: Path | None = None,
    include_ollama_list: bool = True,
    include_a2a_cards: bool = True,
    refresh_nim: bool = False,
    env: Mapping[str, str] | None = None,
) -> ModelPoolSnapshot:
    """Build a merged model-pool snapshot without exposing secret values."""

    resolved_dharma_home = dharma_home or DEFAULT_DHARMA_HOME
    resolved_ollama_home = ollama_home or DEFAULT_OLLAMA_HOME
    status_rows = _key_status_rows(resolved_dharma_home)
    entries: list[ModelPoolEntry] = []
    warnings: list[str] = []

    collectors = (
        ("model_hierarchy", lambda: _iter_canonical_entries(status_rows, env)),
        ("free_fleet", lambda: _iter_free_fleet_entries(status_rows)),
        (
            "ollama",
            lambda: _iter_ollama_config_entries(
                resolved_ollama_home,
                status_rows,
                include_ollama_list=include_ollama_list,
            ),
        ),
        ("provider_matrix", lambda: _iter_provider_matrix_entries(status_rows, env)),
        ("nim_priority", lambda: _iter_nim_priority_entries(status_rows)),
        ("keys_status", lambda: _iter_direct_key_cluster_entries(status_rows)),
    )
    for name, collector in collectors:
        try:
            entries.extend(list(collector()))
        except Exception as exc:
            warnings.append(f"{name}: {type(exc).__name__}: {exc}")

    if include_a2a_cards:
        try:
            entries.extend(list(_iter_a2a_card_entries(resolved_dharma_home / "a2a" / "cards")))
        except Exception as exc:
            warnings.append(f"a2a_card: {type(exc).__name__}: {exc}")

    if refresh_nim:
        try:
            entries.extend(list(_iter_nim_live_entries(status_rows)))
        except Exception as exc:
            warnings.append(f"nim_live_catalog: {type(exc).__name__}: {exc}")

    sources = _ordered_unique(entry.source for entry in entries)
    return ModelPoolSnapshot(
        entries=_dedupe_entries(entries),
        sources=sources,
        warnings=tuple(warnings),
    )


def model_pool_summary(
    *,
    as_json: bool = False,
    limit: int = 40,
    refresh_nim: bool = False,
    include_ollama_list: bool = True,
) -> str:
    snapshot = build_model_pool_snapshot(
        refresh_nim=refresh_nim,
        include_ollama_list=include_ollama_list,
    )
    if as_json:
        payload = snapshot.to_dict()
        payload["entries"] = payload["entries"][:limit]
        return json.dumps(payload, indent=2)

    lines = [
        "MODEL_POOL — unified model inventory",
        f"  models: {len(snapshot.entries)}",
        f"  sources: {', '.join(snapshot.sources)}",
    ]
    if snapshot.warnings:
        lines.append(f"  warnings: {len(snapshot.warnings)}")
    lines.append("")
    lines.append("  Score  Availability       Provider          Model")
    lines.append("  -----  -----------------  ----------------  --------------------------------")
    for entry in snapshot.top(limit):
        lines.append(
            f"  {entry.power_score:>5}  {entry.availability:<17}  "
            f"{entry.provider[:16]:<16}  {entry.model}"
        )
    return "\n".join(lines)


__all__ = [
    "ModelPoolEntry",
    "ModelPoolSnapshot",
    "build_model_pool_snapshot",
    "estimate_power_score",
    "model_pool_summary",
]
