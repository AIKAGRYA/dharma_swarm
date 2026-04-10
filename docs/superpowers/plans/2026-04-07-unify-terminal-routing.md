# Unify Terminal Routing with Canonical Model Hierarchy

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the terminal's model list and routing logic derive from `model_hierarchy.py` (the single source of truth) instead of maintaining a parallel hardcoded list.

**Architecture:** `tui/model_routing.py` stops defining its own `MODEL_TARGETS` tuple and instead generates it from `model_hierarchy.DEFAULT_MODELS` filtered through an adapter availability map. The adapter map (which `ProviderType` values the terminal can actually reach) moves from a private function in `terminal_bridge.py` to a shared constant in `tui/model_routing.py`. All downstream code (`terminal_bridge.py`, tests, TypeScript model picker) keeps working because the public API of `tui/model_routing.py` doesn't change — same functions, same `ModelTarget` dataclass, same signatures.

**Tech Stack:** Python 3.11+, pytest, existing dharma_swarm types

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `dharma_swarm/tui/model_routing.py` | **Modify** | Replace hardcoded `MODEL_TARGETS` with generated list from `model_hierarchy.DEFAULT_MODELS` + adapter map |
| `dharma_swarm/terminal_bridge.py` | **Modify** | Delete `_bridge_provider_id()`, import `ADAPTER_MAP` from `tui/model_routing` |
| `tests/tui/test_model_routing.py` | **Modify** | Add tests for hierarchy derivation, adapter map completeness |
| `tests/test_terminal_bridge.py` | **Modify** | Verify `_bridge_provider_id` removal doesn't break anything |

No new files. No new dependencies. The existing `model_hierarchy.py`, `models.py`, and `provider_matrix.py` are read-only — we consume them, don't touch them.

---

## Key Design Decisions

**1. The adapter map lives in `tui/model_routing.py`, not `terminal_bridge.py`.**

The terminal has 4 adapters: `claude`, `codex`, `openrouter`, `ollama`. The map says which `ProviderType` enum values can be reached through which adapter. This is routing logic, so it belongs with the routing module.

```
ProviderType.CLAUDE_CODE  → "claude"
ProviderType.ANTHROPIC    → "claude"
ProviderType.CODEX        → "codex"
ProviderType.OPENROUTER   → "openrouter"
ProviderType.OPENROUTER_FREE → "openrouter"
ProviderType.OLLAMA       → "ollama"
```

Everything else (GROQ, CEREBRAS, NVIDIA_NIM, etc.) has no adapter — excluded from terminal targets.

**2. Alias and display data come from model_hierarchy, not from tui/model_routing.**

The canonical file already has `DEFAULT_MODELS`, `get_tier()`, `provider_lane_role()`. We use those directly. The `ModelTarget.label` is generated, not handwritten.

**3. Fallback chain derives from `model_hierarchy.CANONICAL_SEED_ORDER`.**

The current hardcoded fallback chains (`_FALLBACK_ORDER_BY_STRATEGY`) get replaced with logic that reads the canonical ordering and filters to reachable adapters. The three strategies (responsive/cost/genius) still exist, but they reorder by tier priority rather than by handwritten alias lists.

**4. Public API doesn't change.**

Every function in `tui/model_routing.py` keeps its signature: `all_targets()`, `default_target()`, `resolve_model_target()`, `resolve_strategy()`, `fallback_chain()`, `format_model_list()`, `format_model_status()`, `detect_inline_switch_intent()`, `target_by_index()`, `route_key()`, `target_for_route()`. The `ModelTarget` dataclass doesn't change. Callers don't know the data source changed.

---

### Task 1: Add adapter map and hierarchy-derived target generation

**Files:**
- Modify: `dharma_swarm/tui/model_routing.py` (lines 1-101)
- Test: `tests/tui/test_model_routing.py`

- [ ] **Step 1: Write failing test — targets derive from hierarchy**

```python
# Add to tests/tui/test_model_routing.py

from dharma_swarm.model_hierarchy import DEFAULT_MODELS
from dharma_swarm.models import ProviderType
from dharma_swarm.tui.model_routing import (
    ADAPTER_MAP,
    MODEL_TARGETS,
    all_targets,
)


def test_adapter_map_covers_all_terminal_adapters() -> None:
    adapter_ids = set(ADAPTER_MAP.values())
    assert adapter_ids == {"claude", "codex", "openrouter", "ollama"}


def test_targets_derived_from_hierarchy() -> None:
    """Every MODEL_TARGET should correspond to a DEFAULT_MODELS entry."""
    targets = all_targets()
    assert len(targets) > 0
    for t in targets:
        # Find the ProviderType that maps to this adapter
        matching_providers = [
            pt for pt, adapter in ADAPTER_MAP.items() if adapter == t.provider_id
        ]
        assert matching_providers, f"No ProviderType maps to adapter '{t.provider_id}'"
        # At least one of those providers should have this model in DEFAULT_MODELS
        hierarchy_models = {DEFAULT_MODELS.get(pt, "") for pt in matching_providers}
        assert t.model_id in hierarchy_models, (
            f"Target {t.alias} ({t.provider_id}:{t.model_id}) not found in "
            f"DEFAULT_MODELS for providers {matching_providers}. "
            f"Hierarchy has: {hierarchy_models}"
        )


def test_no_unreachable_targets() -> None:
    """Every target must have an adapter."""
    for t in all_targets():
        assert t.provider_id in {"claude", "codex", "openrouter", "ollama"}, (
            f"Target {t.alias} has provider_id '{t.provider_id}' "
            f"which has no terminal adapter"
        )


def test_ollama_targets_present() -> None:
    """Ollama Cloud models (GLM-5, DeepSeek, Kimi, etc.) must be in targets."""
    targets = all_targets()
    ollama_targets = [t for t in targets if t.provider_id == "ollama"]
    assert len(ollama_targets) >= 1, "No Ollama Cloud targets found"
    aliases = {t.alias for t in ollama_targets}
    assert "glm-5" in aliases, "GLM-5 missing from targets"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/dharma_swarm && python3 -m pytest tests/tui/test_model_routing.py -v -x 2>&1 | tail -20
```

Expected: FAIL — `ADAPTER_MAP` not importable yet.

- [ ] **Step 3: Replace hardcoded MODEL_TARGETS with hierarchy-derived generation**

Replace lines 1-101 of `dharma_swarm/tui/model_routing.py` with:

```python
"""Model routing helpers for TUI model switching, strategy, and fallback.

Targets are derived from model_hierarchy.DEFAULT_MODELS filtered to providers
that have a terminal adapter. This ensures the terminal always reflects the
canonical source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
import time

from dharma_swarm.model_hierarchy import (
    CANONICAL_SEED_ORDER,
    DEFAULT_MODELS,
    TIER_FREE,
    TIER_CHEAP,
    TIER_SUBSCRIPTION,
    TIER_PAID_API,
    get_tier,
    provider_lane_role,
)
from dharma_swarm.models import ProviderType

INDIGO = "#9C7444"
VERDIGRIS = "#62725D"
OCHRE = "#A17A47"
BENGARA = "#8C5448"
WISTERIA = "#74677D"


# Which ProviderType values the terminal can reach via its 4 adapters.
# If a ProviderType is not here, its models won't appear in the terminal.
ADAPTER_MAP: dict[ProviderType, str] = {
    ProviderType.CLAUDE_CODE: "claude",
    ProviderType.ANTHROPIC: "claude",
    ProviderType.CODEX: "codex",
    ProviderType.OPENROUTER: "openrouter",
    ProviderType.OPENROUTER_FREE: "openrouter",
    ProviderType.OLLAMA: "ollama",
}


@dataclass(frozen=True, slots=True)
class ModelTarget:
    alias: str
    provider_id: str
    model_id: str
    label: str
    aliases: tuple[str, ...] = field(default_factory=tuple)


# ─── Human-friendly aliases and search terms ───────────────────────────
# Keys are (ProviderType, model_id) tuples. Values are (alias, extra_aliases).
# If a DEFAULT_MODELS entry is not here, it gets an auto-generated alias.

_ALIAS_OVERRIDES: dict[tuple[ProviderType, str], tuple[str, tuple[str, ...]]] = {
    (ProviderType.OLLAMA, "glm-5:cloud"): (
        "glm-5", ("glm5", "glm 5", "zhipu"),
    ),
    (ProviderType.OLLAMA, "deepseek-v3.2:cloud"): (
        "deepseek-v3.2", ("deepseek", "ds", "deepseek v3"),
    ),
    (ProviderType.OLLAMA, "kimi-k2.5:cloud"): (
        "kimi-k2.5", ("kimi", "moonshot"),
    ),
    (ProviderType.OLLAMA, "minimax-m2.7:cloud"): (
        "minimax-m2.7", ("minimax", "m2.7", "minimax m2.7"),
    ),
    (ProviderType.OLLAMA, "qwen3-coder:480b-cloud"): (
        "qwen3-coder", ("qwen", "qwen3", "qwen coder"),
    ),
    (ProviderType.CLAUDE_CODE, "claude-code"): (
        "sonnet-4.5", ("sonnet", "sonnet 4.5", "claude sonnet 4.5"),
    ),
    (ProviderType.ANTHROPIC, "claude-opus-4-6"): (
        "opus-4.6", ("opus", "opus 4.6", "claude opus 4.6"),
    ),
    (ProviderType.CODEX, "codex"): (
        "codex-5.4", ("codex", "codex 5.4", "gpt 5 codex"),
    ),
    (ProviderType.OPENROUTER, "xiaomi/mimo-v2-pro"): (
        "mimo-v2", ("mimo", "mimo v2", "xiaomi"),
    ),
    (ProviderType.OPENROUTER_FREE, "meta-llama/llama-3.3-70b-instruct:free"): (
        "llama-3.3-70b", ("llama", "llama 3.3", "meta llama"),
    ),
}


def _auto_alias(model_id: str) -> str:
    """Generate a short alias from a model ID."""
    normalized = model_id.split("/")[-1].split(":")[0].strip().lower()
    normalized = re.sub(r"[^a-z0-9.+-]+", "-", normalized)
    return normalized.strip("-") or "model"


def _build_label(adapter_id: str, model_id: str, provider: ProviderType) -> str:
    """Generate a human-readable label from provider metadata."""
    tier = get_tier(provider)
    role = provider_lane_role(provider).value.replace("_", " ")
    tier_label = {"free": "FREE", "cheap": "CHEAP"}.get(tier, tier)
    return f"{model_id} [{adapter_id} | {role} | {tier_label}]"


def _generate_targets() -> tuple[ModelTarget, ...]:
    """Build MODEL_TARGETS from model_hierarchy.DEFAULT_MODELS."""
    targets: list[ModelTarget] = []
    seen: set[tuple[str, str]] = set()

    # Walk the canonical seed order so targets appear in the right priority
    for provider_type in CANONICAL_SEED_ORDER:
        adapter_id = ADAPTER_MAP.get(provider_type)
        if adapter_id is None:
            continue
        model_id = DEFAULT_MODELS.get(provider_type, "")
        if not model_id:
            continue
        key = (adapter_id, model_id)
        if key in seen:
            continue
        seen.add(key)

        override = _ALIAS_OVERRIDES.get((provider_type, model_id))
        if override:
            alias, extra_aliases = override
        else:
            alias = _auto_alias(model_id)
            extra_aliases = ()

        targets.append(ModelTarget(
            alias=alias,
            provider_id=adapter_id,
            model_id=model_id,
            label=_build_label(adapter_id, model_id, provider_type),
            aliases=extra_aliases,
        ))

    return tuple(targets)


MODEL_TARGETS: tuple[ModelTarget, ...] = _generate_targets()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ~/dharma_swarm && python3 -m pytest tests/tui/test_model_routing.py -v 2>&1 | tail -20
```

Expected: All pass, including the new hierarchy derivation tests AND the existing tests (`test_default_target_is_claude_sonnet`, `test_resolve_alias_and_model_id`, `test_inline_switch_detection`, `test_fallback_chain_excludes_current`, `test_strategy_aliases_resolve`, `test_target_by_index_maps_in_model_list_order`).

- [ ] **Step 5: Commit**

```bash
cd ~/dharma_swarm
git add dharma_swarm/tui/model_routing.py tests/tui/test_model_routing.py
git commit -m "feat(tui): derive MODEL_TARGETS from model_hierarchy instead of hardcoded list"
```

---

### Task 2: Replace hardcoded fallback chains with hierarchy-derived ordering

**Files:**
- Modify: `dharma_swarm/tui/model_routing.py` (lines ~100-128 — `_FALLBACK_ORDER_BY_STRATEGY`)
- Test: `tests/tui/test_model_routing.py`

- [ ] **Step 1: Write failing test — fallback chain respects tier ordering**

```python
# Add to tests/tui/test_model_routing.py

def test_cost_strategy_prefers_free_tier() -> None:
    """Cost strategy should put free-tier models before paid ones."""
    chain = fallback_chain("claude", "claude-sonnet-4-5", strategy="cost")
    if not chain:
        return  # No fallbacks available is OK
    # First fallback should be free or cheap tier
    first = chain[0]
    assert first.provider_id in {"ollama", "openrouter"}, (
        f"Cost strategy first fallback is {first.provider_id}:{first.model_id}, "
        f"expected a free/cheap provider"
    )


def test_genius_strategy_prefers_frontier() -> None:
    """Genius strategy should put frontier models first."""
    chain = fallback_chain("ollama", "glm-5:cloud", strategy="genius")
    if not chain:
        return
    first = chain[0]
    assert first.provider_id in {"claude", "codex"}, (
        f"Genius strategy first fallback is {first.provider_id}:{first.model_id}, "
        f"expected a frontier provider"
    )


def test_fallback_chain_all_entries_have_adapters() -> None:
    """Every entry in the fallback chain must have a working adapter."""
    for provider_id in ("claude", "codex", "openrouter", "ollama"):
        for model_id in [t.model_id for t in all_targets() if t.provider_id == provider_id][:1]:
            chain = fallback_chain(provider_id, model_id)
            for entry in chain:
                assert entry.provider_id in {"claude", "codex", "openrouter", "ollama"}, (
                    f"Fallback entry {entry.alias} has unreachable provider {entry.provider_id}"
                )
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/dharma_swarm && python3 -m pytest tests/tui/test_model_routing.py::test_cost_strategy_prefers_free_tier -v
```

Expected: May pass or fail depending on current hardcoded order. The key test is `test_fallback_chain_all_entries_have_adapters`.

- [ ] **Step 3: Replace hardcoded fallback chains with tier-derived ordering**

Replace `_FALLBACK_ORDER_BY_STRATEGY` and the `fallback_chain()` function body in `dharma_swarm/tui/model_routing.py`:

```python
ROUTING_STRATEGIES: tuple[str, ...] = ("responsive", "cost", "genius")

# Strategy → tier ordering. The function walks these tiers and collects
# targets in order, filtered to reachable adapters.
_TIER_ORDER_BY_STRATEGY: dict[str, tuple[tuple[ProviderType, ...], ...]] = {
    "responsive": (TIER_SUBSCRIPTION, TIER_FREE, TIER_CHEAP, TIER_PAID_API),
    "cost":       (TIER_FREE, TIER_CHEAP, TIER_SUBSCRIPTION, TIER_PAID_API),
    "genius":     (TIER_SUBSCRIPTION, TIER_PAID_API, TIER_FREE, TIER_CHEAP),
}


def _build_fallback_order(strategy: str) -> tuple[str, ...]:
    """Build alias ordering for a strategy from tier priority."""
    tier_order = _TIER_ORDER_BY_STRATEGY.get(strategy, _TIER_ORDER_BY_STRATEGY["responsive"])
    by_alias = {t.alias: t for t in MODEL_TARGETS}
    ordered: list[str] = []
    seen: set[str] = set()
    for tier in tier_order:
        for pt in tier:
            adapter = ADAPTER_MAP.get(pt)
            if adapter is None:
                continue
            model = DEFAULT_MODELS.get(pt, "")
            if not model:
                continue
            # Find the target with this adapter + model
            for t in MODEL_TARGETS:
                if t.provider_id == adapter and t.model_id == model and t.alias not in seen:
                    ordered.append(t.alias)
                    seen.add(t.alias)
    return tuple(ordered)


_FALLBACK_ORDER_BY_STRATEGY: dict[str, tuple[str, ...]] = {
    s: _build_fallback_order(s) for s in ROUTING_STRATEGIES
}
```

- [ ] **Step 4: Run all tui/model_routing tests**

```bash
cd ~/dharma_swarm && python3 -m pytest tests/tui/test_model_routing.py -v 2>&1 | tail -20
```

Expected: All pass.

- [ ] **Step 5: Commit**

```bash
cd ~/dharma_swarm
git add dharma_swarm/tui/model_routing.py tests/tui/test_model_routing.py
git commit -m "feat(tui): derive fallback chains from model_hierarchy tier ordering"
```

---

### Task 3: Wire terminal_bridge.py to shared adapter map

**Files:**
- Modify: `dharma_swarm/terminal_bridge.py` (lines 61-68 — `_bridge_provider_id()`)
- Test: `tests/test_terminal_bridge.py`

- [ ] **Step 1: Write failing test — bridge uses shared adapter map**

```python
# Add to tests/test_terminal_bridge.py

from dharma_swarm.tui.model_routing import ADAPTER_MAP
from dharma_swarm.models import ProviderType


def test_adapter_map_includes_ollama() -> None:
    """The adapter map must include OLLAMA — it was previously missing."""
    assert ProviderType.OLLAMA in ADAPTER_MAP
    assert ADAPTER_MAP[ProviderType.OLLAMA] == "ollama"
```

- [ ] **Step 2: Run test to verify it passes** (should pass — we added OLLAMA in Task 1)

```bash
cd ~/dharma_swarm && python3 -m pytest tests/test_terminal_bridge.py::test_adapter_map_includes_ollama -v
```

Expected: PASS (ADAPTER_MAP already has OLLAMA from Task 1).

- [ ] **Step 3: Replace `_bridge_provider_id()` with import from shared map**

In `dharma_swarm/terminal_bridge.py`, replace lines 61-68:

```python
# BEFORE:
def _bridge_provider_id(provider: ProviderType) -> str | None:
    if provider == ProviderType.CODEX:
        return "codex"
    if provider in {ProviderType.ANTHROPIC, ProviderType.CLAUDE_CODE}:
        return "claude"
    if provider in {ProviderType.OPENROUTER, ProviderType.OPENROUTER_FREE}:
        return "openrouter"
    return None
```

```python
# AFTER:
from dharma_swarm.tui.model_routing import ADAPTER_MAP as _ADAPTER_MAP

def _bridge_provider_id(provider: ProviderType) -> str | None:
    return _ADAPTER_MAP.get(provider)
```

- [ ] **Step 4: Run terminal_bridge tests + full tui routing tests**

```bash
cd ~/dharma_swarm && python3 -m pytest tests/test_terminal_bridge.py tests/tui/test_model_routing.py -v 2>&1 | tail -30
```

Expected: All pass.

- [ ] **Step 5: Verify bridge handshake still returns all 14 models**

```bash
cd ~/dharma_swarm && echo '{"id":"1","type":"handshake"}' | timeout 5 .venv/bin/python -m dharma_swarm.terminal_bridge stdio 2>/dev/null | python3 -c "
import sys, json
for line in sys.stdin:
    d = json.loads(line)
    if d.get('type') == 'handshake.result':
        providers = d.get('providers', [])
        total = sum(len(p.get('models', [])) for p in providers)
        print(f'{len(providers)} providers, {total} models')
        for p in providers:
            ids = [m['id'] for m in p.get('models', [])]
            print(f'  {p[\"provider_id\"]}: {ids}')
"
```

Expected: 4 providers, 14 models (same as before, confirming no regression).

- [ ] **Step 6: Commit**

```bash
cd ~/dharma_swarm
git add dharma_swarm/terminal_bridge.py tests/test_terminal_bridge.py
git commit -m "refactor: bridge uses shared ADAPTER_MAP from tui.model_routing"
```

---

### Task 4: Verify model.policy.result reflects canonical hierarchy

**Files:**
- No code changes — verification only
- Test: `tests/test_terminal_bridge.py`

- [ ] **Step 1: Write test — policy targets come from hierarchy**

```python
# Add to tests/test_terminal_bridge.py

def test_model_policy_targets_use_adapter_provider_ids() -> None:
    """model.policy.result targets must use adapter provider IDs, not ProviderType values."""
    from dharma_swarm.terminal_bridge import TerminalBridge
    import asyncio

    bridge = TerminalBridge()
    bridge._ensure_adapters()
    policy = bridge._build_model_policy_summary(
        selected_provider="claude",
        selected_model="claude-sonnet-4-5",
        strategy="responsive",
    )
    targets = policy.get("targets", [])
    valid_adapters = {"claude", "codex", "openrouter", "ollama"}
    for target in targets:
        provider = target.get("provider", "")
        assert provider in valid_adapters, (
            f"Policy target {target.get('alias')} has provider '{provider}' "
            f"which is not a valid adapter ID"
        )
```

- [ ] **Step 2: Run test**

```bash
cd ~/dharma_swarm && python3 -m pytest tests/test_terminal_bridge.py::test_model_policy_targets_use_adapter_provider_ids -v
```

Expected: PASS — `_bridge_provider_id` now maps OLLAMA correctly so all canonical providers with adapters show up.

- [ ] **Step 3: Commit**

```bash
cd ~/dharma_swarm
git add tests/test_terminal_bridge.py
git commit -m "test: verify model policy targets use adapter provider IDs"
```

---

### Task 5: Run full test suite and verify terminal E2E

**Files:**
- No code changes — verification only

- [ ] **Step 1: Run full tui test suite**

```bash
cd ~/dharma_swarm && python3 -m pytest tests/tui/ -v 2>&1 | tail -20
```

Expected: All pass.

- [ ] **Step 2: Run bridge handshake + model.policy E2E check**

```bash
cd ~/dharma_swarm && echo '{"id":"1","type":"handshake"}
{"id":"2","type":"model.policy","provider":"claude","model":"claude-sonnet-4-5","strategy":"responsive"}' | timeout 5 .venv/bin/python -m dharma_swarm.terminal_bridge stdio 2>/dev/null | python3 -c "
import sys, json
for line in sys.stdin:
    d = json.loads(line)
    t = d.get('type', '')
    if t == 'handshake.result':
        providers = d.get('providers', [])
        total = sum(len(p.get('models', [])) for p in providers)
        print(f'handshake: {len(providers)} providers, {total} models')
    elif t == 'model.policy.result':
        targets = d.get('payload', {}).get('targets', d.get('policy', {}).get('targets', []))
        adapters = set(t.get('provider', '') for t in targets)
        print(f'policy: {len(targets)} targets, adapters: {sorted(adapters)}')
        # Verify ollama is present
        ollama_targets = [t for t in targets if t.get('provider') == 'ollama']
        print(f'ollama targets: {len(ollama_targets)}')
"
```

Expected: Ollama targets should now appear in the policy (they were previously missing because `_bridge_provider_id` didn't handle OLLAMA).

- [ ] **Step 3: Run terminal-v2 bridge chat test**

```bash
cd ~/dharma_swarm/terminal-v2 && bun -e '
import { DharmaBridge } from "./src/core/bridge.js";
const bridge = new DharmaBridge((evt) => {
  if (evt.type === "handshake.result") {
    const n = (evt.providers ?? []).reduce((s, p) => s + (p.models?.length ?? 0), 0);
    console.log("PASS handshake:", (evt.providers ?? []).length, "providers,", n, "models");
  }
  if (evt.type === "text_complete") console.log("PASS chat:", JSON.stringify(evt.content).slice(0, 60));
  if (evt.type === "session_end") { bridge.close(); process.exit(evt.success ? 0 : 1); }
  if (evt.type === "error" || evt.type === "bridge.error") console.log("ERROR:", evt.message);
});
setTimeout(() => bridge.send("handshake"), 500);
setTimeout(() => bridge.send("session.start", {
  provider: "ollama", model: "glm-5:cloud",
  prompt: "Say hello.", system_prompt: "Be brief.",
}), 2000);
setTimeout(() => { console.log("TIMEOUT"); bridge.close(); process.exit(1); }, 20000);
' 2>&1
```

Expected: `PASS handshake` followed by `PASS chat` with a response.

- [ ] **Step 4: Commit if any test adjustments were needed**

If all passed with no changes, skip this step.
