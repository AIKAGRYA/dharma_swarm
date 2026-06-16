"""Model routing helpers for TUI model switching, strategy, and fallback."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
import time

INDIGO = "#9C7444"
VERDIGRIS = "#62725D"
OCHRE = "#A17A47"
BENGARA = "#8C5448"
WISTERIA = "#74677D"


@dataclass(frozen=True, slots=True)
class ModelTarget:
    alias: str
    provider_id: str
    model_id: str
    label: str
    aliases: tuple[str, ...] = field(default_factory=tuple)


# Frontier-only roster (>= Kimi K2.6 power floor). Every sub-floor model
# (glm-5, deepseek-v3.x, kimi-k2.5, minimax-m2.x, sonnet-4.5, opus-4.6,
# haiku-4.5, gemini-2.5) is BANISHED — never listed, never selectable, never
# a fallback. Claude Opus 4.8 leads (the master lane); the Ollama-cloud open
# frontier is the free workhorse stable.
MODEL_TARGETS: tuple[ModelTarget, ...] = (
    # Subscription frontier — Claude Max (no metered cost)
    ModelTarget(
        alias="opus-4.8",
        provider_id="claude",
        model_id="claude-opus-4-8",
        label="Claude Opus 4.8",
        aliases=("opus", "opus 4.8", "claude opus", "claude opus 4.8"),
    ),
    ModelTarget(
        alias="sonnet-4.6",
        provider_id="claude",
        model_id="claude-sonnet-4-6",
        label="Claude Sonnet 4.6",
        aliases=("sonnet", "sonnet 4.6", "claude sonnet 4.6"),
    ),
    # Free frontier (Ollama Cloud — the open-frontier gateway)
    ModelTarget(
        alias="kimi-k2.6",
        provider_id="ollama",
        model_id="kimi-k2.6:cloud",
        label="Kimi K2.6 [FREE]",
        aliases=("kimi", "k2.6", "kimi k2.6", "moonshot"),
    ),
    ModelTarget(
        alias="glm-5.1",
        provider_id="ollama",
        model_id="glm-5.1:cloud",
        label="GLM-5.1 [FREE]",
        aliases=("glm", "glm5.1", "glm 5.1", "zhipu"),
    ),
    ModelTarget(
        alias="deepseek-v4-pro",
        provider_id="ollama",
        model_id="deepseek-v4-pro:cloud",
        label="DeepSeek V4 Pro [FREE]",
        aliases=("deepseek", "ds", "deepseek v4", "deepseek v4 pro"),
    ),
    ModelTarget(
        alias="minimax-m3",
        provider_id="ollama",
        model_id="minimax-m3:cloud",
        label="MiniMax M3 [FREE]",
        aliases=("minimax", "m3", "minimax m3"),
    ),
    ModelTarget(
        alias="qwen3-coder",
        provider_id="ollama",
        model_id="qwen3-coder:480b-cloud",
        label="Qwen3-Coder 480B [FREE]",
        aliases=("qwen", "qwen3", "qwen coder", "qwen3 coder"),
    ),
    # Paid frontier
    ModelTarget(
        alias="codex-5.5",
        provider_id="codex",
        model_id="gpt-5.5",
        label="Codex GPT-5.5",
        aliases=("codex", "codex 5.5", "gpt 5 codex", "gpt-5.5"),
    ),
    ModelTarget(
        alias="gemini-3",
        provider_id="openrouter",
        model_id="google/gemini-3-pro",
        label="Gemini 3 Pro (via OpenRouter)",
        aliases=("gemini", "gemini 3", "gemini 3 pro", "google gemini"),
    ),
)


_DEFAULT_TARGET = MODEL_TARGETS[0]
ROUTING_STRATEGIES: tuple[str, ...] = ("responsive", "cost", "genius")
_FALLBACK_ORDER_BY_STRATEGY: dict[str, tuple[str, ...]] = {
    # Claude-first (operator doctrine), then codex as the first non-claude
    # frontier fallback for usage-exhaustion, then the free Ollama frontier.
    "responsive": (
        "sonnet-4.6",
        "codex-5.5",
        "kimi-k2.6",
        "glm-5.1",
        "opus-4.8",
        "deepseek-v4-pro",
    ),
    # "cost" = free-frontier-first (still entirely >= K2.6).
    "cost": (
        "kimi-k2.6",
        "glm-5.1",
        "deepseek-v4-pro",
        "minimax-m3",
        "qwen3-coder",
        "sonnet-4.6",
    ),
    "genius": (
        "opus-4.8",
        "deepseek-v4-pro",
        "kimi-k2.6",
        "codex-5.5",
        "sonnet-4.6",
        "gemini-3",
    ),
}


def _norm(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9.\-/ ]+", " ", text)
    return " ".join(text.split())


def all_targets() -> list[ModelTarget]:
    return list(MODEL_TARGETS)


def route_key(provider_id: str, model_id: str) -> str:
    return f"{provider_id}:{model_id}"


def default_target() -> ModelTarget:
    return _DEFAULT_TARGET


def resolve_strategy(text: str | None) -> str | None:
    if not text:
        return None
    q = _norm(text)
    aliases = {
        "responsive": "responsive",
        "fast": "responsive",
        "speed": "responsive",
        "balanced": "responsive",
        "cost": "cost",
        "cheap": "cost",
        "budget": "cost",
        "frugal": "cost",
        "genius": "genius",
        "quality": "genius",
        "max": "genius",
        "best": "genius",
    }
    return aliases.get(q)


def resolve_model_target(text: str) -> ModelTarget | None:
    q = _norm(text)
    if not q:
        return None
    for t in MODEL_TARGETS:
        if q == _norm(t.alias):
            return t
        if q == _norm(t.model_id):
            return t
        for a in t.aliases:
            if q == _norm(a):
                return t
    # relaxed match: "switch to opus 4.6"
    for t in MODEL_TARGETS:
        keys = (_norm(t.alias), _norm(t.model_id), *(_norm(a) for a in t.aliases))
        if any(k and k in q for k in keys):
            return t
    return None


def target_for_route(provider_id: str, model_id: str) -> ModelTarget | None:
    for target in MODEL_TARGETS:
        if target.provider_id == provider_id and target.model_id == model_id:
            return target
    return None


def target_by_index(index: int) -> ModelTarget | None:
    if index < 1 or index > len(MODEL_TARGETS):
        return None
    return MODEL_TARGETS[index - 1]


def _cooldown_remaining_seconds(
    *,
    alias: str,
    cooldown_until: dict[str, float] | None,
    now_ts: float,
) -> int:
    if not cooldown_until:
        return 0
    until = cooldown_until.get(alias, 0.0)
    if until <= 0.0:
        return 0
    remain = int(until - now_ts)
    return remain if remain > 0 else 0


def format_model_list(
    current_provider: str,
    current_model: str,
    *,
    auto_fallback: bool = True,
    strategy: str = "responsive",
    preferred_key: str | None = None,
    available_keys: set[str] | None = None,
    cooldown_until: dict[str, float] | None = None,
    model_stats_by_alias: dict[str, dict[str, float | int | str]] | None = None,
    now_ts: float | None = None,
) -> str:
    strategy = resolve_strategy(strategy) or "responsive"
    now = now_ts if now_ts is not None else time.time()
    lines = ["Available models:", ""]
    for idx, t in enumerate(MODEL_TARGETS, start=1):
        active = (
            t.provider_id == current_provider and t.model_id == current_model
        )
        key = route_key(t.provider_id, t.model_id)
        preferred = preferred_key == key
        mark = f"[{VERDIGRIS}]*[/{VERDIGRIS}]" if active else " "
        remain = _cooldown_remaining_seconds(
            alias=t.alias,
            cooldown_until=cooldown_until,
            now_ts=now,
        )
        if remain > 0:
            readiness = f"[{OCHRE}]cooldown {remain}s[/{OCHRE}]"
        elif available_keys is not None and key not in available_keys:
            readiness = f"[{BENGARA}]blocked[/{BENGARA}]"
        else:
            readiness = f"[{VERDIGRIS}]ready[/{VERDIGRIS}]"
        stats_suffix = ""
        if model_stats_by_alias:
            stats = model_stats_by_alias.get(t.alias, {})
            ok = int(stats.get("successes", 0) or 0)
            bad = int(stats.get("failures", 0) or 0)
            latency = float(stats.get("ema_latency_ms", 0.0) or 0.0)
            if ok or bad:
                if latency > 0.0:
                    stats_suffix = f" [dim]ok:{ok} fail:{bad} ~{latency:.0f}ms[/dim]"
                else:
                    stats_suffix = f" [dim]ok:{ok} fail:{bad}[/dim]"
        pref = f" [{WISTERIA}](preferred)[/{WISTERIA}]" if preferred else ""
        lines.append(
            f"{mark} [bold]{idx:02d}[/bold] [{INDIGO}]{t.alias}[/{INDIGO}] -> {t.label}"
            f"{pref} {readiness} [dim]({key})[/dim]{stats_suffix}"
        )
    lines.append("")
    lines.append(
        f"Auto-fallback: {'ON' if auto_fallback else 'OFF'} | "
        f"Strategy: {strategy}"
    )
    lines.append(
        "Usage: /model list | /model status | /model set <alias|index> | "
        "/model auto <on|off|status|responsive|cost|genius>"
    )
    lines.append("Natural language: 'switch to opus 4.8' or 'switch to codex 5.5'")
    return "\n".join(lines)


def format_model_status(
    current_provider: str,
    current_model: str,
    auto_fallback: bool,
    *,
    strategy: str = "responsive",
    preferred: ModelTarget | None = None,
    cooldown_count: int = 0,
) -> str:
    t = resolve_model_target(current_model) or resolve_model_target(
        f"{current_provider} {current_model}"
    )
    label = t.label if t else current_model
    state = "ON" if auto_fallback else "OFF"
    resolved_strategy = resolve_strategy(strategy) or "responsive"
    preferred_label = preferred.label if preferred else "unset"
    return (
        f"Current model: [{INDIGO}]{label}[/{INDIGO}]\n"
        f"Provider/model: [dim]{current_provider}:{current_model}[/dim]\n"
        f"Auto-fallback: [{OCHRE}]{state}[/{OCHRE}]\n"
        f"Strategy: [{OCHRE}]{resolved_strategy}[/{OCHRE}]\n"
        f"Preferred model: [{INDIGO}]{preferred_label}[/{INDIGO}]\n"
        f"Cooling models: [{OCHRE}]{cooldown_count}[/{OCHRE}]"
    )


def fallback_chain(
    current_provider: str,
    current_model: str,
    *,
    strategy: str = "responsive",
    allowed_aliases: set[str] | None = None,
    cooldown_until: dict[str, float] | None = None,
    now_ts: float | None = None,
) -> list[ModelTarget]:
    current = target_for_route(current_provider, current_model)
    resolved_strategy = resolve_strategy(strategy) or "responsive"
    order = _FALLBACK_ORDER_BY_STRATEGY.get(
        resolved_strategy,
        _FALLBACK_ORDER_BY_STRATEGY["responsive"],
    )
    ordered: list[ModelTarget] = []
    by_alias = {t.alias: t for t in MODEL_TARGETS}
    now = now_ts if now_ts is not None else time.time()
    for alias in order:
        t = by_alias.get(alias)
        if t is None:
            continue
        if allowed_aliases is not None and t.alias not in allowed_aliases:
            continue
        if _cooldown_remaining_seconds(
            alias=t.alias,
            cooldown_until=cooldown_until,
            now_ts=now,
        ) > 0:
            continue
        if current and t.alias == current.alias:
            continue
        ordered.append(t)
    return ordered


def detect_inline_switch_intent(text: str) -> ModelTarget | None:
    q = _norm(text)
    if not q:
        return None
    patterns = (
        "switch to ",
        "change to ",
        "use ",
        "set model to ",
        "move to ",
        "switch model to ",
        "go to ",
    )
    if any(p in q for p in patterns):
        return resolve_model_target(q)
    return None
