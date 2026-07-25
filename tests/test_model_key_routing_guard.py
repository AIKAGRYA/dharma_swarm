"""Guard the one-way model/key routing contract.

New model literals belong in model_hierarchy/model catalogs. New provider key
reads belong in api_keys.py and runtime_provider.py, not feature code.
"""

from __future__ import annotations

import ast
import re
from collections import Counter
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = ("dharma_swarm", "scripts", "api")

MODEL_REGISTRY_FILES = {
    "api/routers/chat.py",
    "dharma_swarm/certified_lanes.py",
    "dharma_swarm/cost_tracker.py",
    "dharma_swarm/evolution_roster.py",
    "dharma_swarm/free_fleet.py",
    "dharma_swarm/model_catalog.py",
    "dharma_swarm/model_hierarchy.py",
    "dharma_swarm/model_manager.py",
    "dharma_swarm/model_pool_registry.py",
    "dharma_swarm/model_registry.py",
    "dharma_swarm/model_routing.py",
    "dharma_swarm/ollama_config.py",
    "dharma_swarm/provider_matrix.py",
    "dharma_swarm/provider_smoke.py",
    "dharma_swarm/providers.py",
    "dharma_swarm/router_v1.py",
    "dharma_swarm/tui/model_routing.py",
}

KEY_REGISTRY_FILES = {
    "dharma_swarm/api_keys.py",
    "dharma_swarm/runtime_provider.py",
}

SEMANTIC_COMMONS_FILES = (
    "docs/ontology/SEMANTIC_COMMONS.md",
    "docs/ontology/semantic_aliases.yaml",
    "docs/ontology/semantic_objects.yaml",
)

BRANCH_LOCAL_SEMANTIC_COMMONS_GUARD = "docs/ops/MODEL_ROUTING_SEMANTIC_COMMONS_GUARD.md"

SEMANTIC_COMMONS_REQUIRED_TERMS = (
    "ModelKeyRouting",
    "DKeysKeyStore",
    "RuntimeProvider",
    "ModelHierarchy",
    "ProviderPolicyRouter",
    "ModelRouter",
    "RoutingMemory",
    "parallel model routing layer",
    "project .env keys",
    "direct provider factory",
    "scattered model order",
)

MODEL_LITERAL_RE = re.compile(
    r"(?:"
    r"claude-(?:opus|sonnet|haiku)[\w.-]*|"
    r"anthropic/claude-[\w./:-]+|"
    r"(?:openai/)?gpt-[\w.:-]+|"
    r"moonshotai/kimi[\w./:-]*|"
    r"kimi-k2[\w./:-]*|"
    r"z-ai/glm[\w./:-]*|"
    r"zai-org/GLM-[\w./:-]*|"
    r"glm-[\w.:/-]+|"
    r"qwen[\w./:-]+|"
    r"meta-llama/[\w./:-]+|"
    r"meta/llama[\w./:-]+|"
    r"nvidia/[\w./:-]+|"
    r"deepseek[\w./:-]+|"
    r"mistralai/[\w./:-]+|"
    r"gemini-[\w.-]+|"
    r"minimax[\w./:-]+|"
    r"accounts/fireworks/models/[\w./:-]+"
    r")"
)

PROVIDER_KEY_ENV_RE = re.compile(
    r"(?:"
    r"ANTHROPIC|OPENAI|OPENROUTER|NVIDIA_NIM|NVIDIA|NIM|OLLAMA|"
    r"GROQ|CEREBRAS|SILICONFLOW|TOGETHER|FIREWORKS|GOOGLE_AI|"
    r"GEMINI|SAMBANOVA|MISTRAL|CHUTES|MOONSHOT|NGC|DASHBOARD|"
    r"FRED|FINNHUB|EXA|BRAVE|PPLX|PERPLEXITY|JINA|FIRECRAWL|"
    r"DGC_[A-Z0-9_]+"
    r")_API_KEY"
)

KNOWN_MODEL_LITERAL_DEBT: Counter[tuple[str, str]] = Counter(
    {
        ("dharma_swarm/assurance/agents.py", "claude-opus-4-20250514"): 1,
        ("dharma_swarm/assurance/agents.py", "claude-sonnet-4-20250514"): 1,
        ("dharma_swarm/daemon_config.py", "anthropic/claude-sonnet-4"): 1,
        ("dharma_swarm/dharma_context_mcp.py", "meta-llama/llama-3.3-70b-instruct:free"): 1,
        ("dharma_swarm/llm_burn.py", "glm-5"): 1,
        ("dharma_swarm/llm_burn.py", "kimi-k2.5"): 1,
        ("dharma_swarm/llm_burn.py", "minimax-m2.7"): 1,
        ("dharma_swarm/master_prompt_engineer.py", "anthropic/claude-3.5-sonnet"): 1,
        ("dharma_swarm/master_prompt_engineer.py", "claude-sonnet-4-20250514"): 1,
        ("dharma_swarm/models.py", "claude-sonnet-4-20250514"): 1,
        ("dharma_swarm/orchestrate_live.py", "deepseek/deepseek-chat-v3-0324:free"): 1,
        ("dharma_swarm/orchestrate_live.py", "meta-llama/llama-3.3-70b-instruct:free"): 1,
        ("dharma_swarm/orchestrate_live.py", "qwen/qwen3-4b:free"): 1,
        ("dharma_swarm/orchestrate_live.py", "qwen/qwen3-coder:free"): 1,
        ("dharma_swarm/orchestrate_live.py", "qwen/qwen3-next-80b-a3b-instruct:free"): 1,
        ("dharma_swarm/subconscious_hum.py", "claude-sonnet-4-20250514"): 1,
        ("dharma_swarm/terminal_adapters/claude.py", "claude-haiku-4-5"): 1,
        ("dharma_swarm/terminal_adapters/claude.py", "claude-opus-4"): 1,
        ("dharma_swarm/terminal_adapters/claude.py", "claude-opus-4-6"): 1,
        ("dharma_swarm/terminal_adapters/claude.py", "claude-sonnet-4-5"): 2,
        ("dharma_swarm/terminal_adapters/claude.py", "claude-sonnet-4-6"): 1,
        ("dharma_swarm/terminal_bridge.py", "glm-5"): 1,
        ("dharma_swarm/tui/engine/adapters/claude.py", "claude-haiku-4-5"): 1,
        ("dharma_swarm/tui/engine/adapters/claude.py", "claude-opus-4"): 1,
        ("dharma_swarm/tui/engine/adapters/claude.py", "claude-opus-4-6"): 1,
        ("dharma_swarm/tui/engine/adapters/claude.py", "claude-sonnet-4-5"): 1,
        ("dharma_swarm/tui/engine/adapters/claude.py", "claude-sonnet-4-6"): 1,
        ("dharma_swarm/tui/engine/adapters/codex.py", "gpt-5.4"): 1,
        ("dharma_swarm/tui/engine/adapters/openrouter.py", "openai/gpt-5-codex"): 1,
        ("scripts/demos/demo_jikoku.py", "claude-opus-4"): 1,
        ("scripts/full_stack_smoke.py", "deepseek/deepseek-chat-v3-0324"): 1,
        ("scripts/full_stack_smoke.py", "google/gemini-2.5-flash"): 1,
        ("scripts/full_stack_smoke.py", "meta-llama/llama-3.3-70b-instruct"): 1,
        ("scripts/full_stack_smoke.py", "mistralai/mistral-small-3.1-24b-instruct"): 1,
        ("scripts/full_stack_smoke.py", "qwen/qwen3-30b-a3b"): 1,
        ("scripts/lattice_test.py", "google/gemini-2.5-flash"): 1,
        ("scripts/lattice_test.py", "meta-llama/llama-3.3-70b-instruct"): 1,
        ("scripts/lattice_test.py", "qwen/qwen3-30b-a3b"): 1,
        ("scripts/launch_singularity_research.py", "claude-opus-4-6"): 1,
        ("scripts/live_fanout.py", "anthropic/claude-sonnet-4"): 1,
        ("scripts/live_genome_test.py", "anthropic/claude-sonnet-4"): 2,
        ("scripts/live_test.py", "anthropic/claude-sonnet-4"): 1,
        ("scripts/mirror_test.py", "google/gemini-2.5-flash"): 1,
        ("scripts/onboard_cybernetics_stewards.py", "deepseek-v3.2:cloud"): 1,
        ("scripts/onboard_cybernetics_stewards.py", "glm-5:cloud"): 1,
        ("scripts/onboard_cybernetics_stewards.py", "kimi-k2.5:cloud"): 1,
        ("scripts/onboard_cybernetics_stewards.py", "qwen3-coder:480b-cloud"): 1,
        ("scripts/organism_council.py", "glm-5:cloud"): 1,
        ("scripts/organism_with_intelligence.py", "google/gemini-2.0-flash-001"): 1,
        ("scripts/organism_with_intelligence.py", "meta-llama/llama-3.3-70b-instruct"): 1,
        ("scripts/organism_with_intelligence.py", "mistralai/mistral-small-2501"): 1,
        ("scripts/organism_with_intelligence.py", "qwen/qwen-2.5-72b-instruct"): 1,
        ("scripts/runtime/capability_profile_loop.py", "deepseek-v4-pro"): 1,
        ("scripts/runtime/capability_profile_loop.py", "glm-4.6"): 1,
        ("scripts/runtime/forge_swarm_evolution_arena_v0_measurement_runner.py", "deepseek-v3.1:671b"): 1,
        ("scripts/runtime/forge_swarm_evolution_arena_v0_measurement_runner.py", "glm-5.1"): 2,
        ("scripts/runtime/forge_swarm_evolution_arena_v0_measurement_runner.py", "gpt-5.1"): 1,
        ("scripts/runtime/forge_swarm_evolution_arena_v0_taskpack_builder.py", "gemini-2.5-pro"): 1,
        ("scripts/runtime/forge_swarm_evolution_arena_v0_taskpack_builder.py", "gpt-5.5"): 1,
        ("scripts/system_integration_probe.py", "glm-5:cloud"): 1,
    }
)

KNOWN_RAW_KEY_READ_DEBT: Counter[tuple[str, str, str]] = Counter(
    {
        ("dharma_swarm/tui_legacy.py", "os.getenv", "MOONSHOT_API_KEY"): 1,
        ("dharma_swarm/tui_legacy.py", "os.getenv", "OLLAMA_API_KEY"): 1,
        ("scripts/allout_autopilot.py", "os.getenv", "NGC_API_KEY"): 1,
        ("scripts/allout_autopilot.py", "os.getenv", "NVIDIA_API_KEY"): 1,
        ("scripts/allout_autopilot.py", "os.getenv", "OPENROUTER_API_KEY"): 1,
        ("scripts/demos/demo_jikoku.py", "os.environ.get", "ANTHROPIC_API_KEY"): 1,
        ("scripts/dgc_max_stress.py", "os.getenv", "NGC_API_KEY"): 1,
        ("scripts/dgc_max_stress.py", "os.getenv", "NVIDIA_API_KEY"): 1,
        ("scripts/dgc_max_stress.py", "os.getenv", "OPENAI_API_KEY"): 2,
        ("scripts/dgc_max_stress.py", "os.getenv", "OPENROUTER_API_KEY"): 2,
        ("scripts/lattice_test.py", "os.environ.get", "OPENROUTER_API_KEY"): 1,
        ("scripts/live_fanout.py", "os.environ.get", "OPENROUTER_API_KEY"): 1,
        ("scripts/live_genome_test.py", "os.environ.get", "OPENROUTER_API_KEY"): 1,
        ("scripts/live_organism_run.py", "os.environ.get", "OPENROUTER_API_KEY"): 1,
        ("scripts/live_test.py", "os.environ.get", "OPENROUTER_API_KEY"): 1,
        ("scripts/mirror_test.py", "os.environ.get", "OPENROUTER_API_KEY"): 1,
        ("scripts/organism_with_intelligence.py", "os.environ.get", "OPENROUTER_API_KEY"): 1,
        ("scripts/strange_loop.py", "os.getenv", "NGC_API_KEY"): 1,
        ("scripts/strange_loop.py", "os.getenv", "NVIDIA_API_KEY"): 1,
        ("scripts/strange_loop.py", "os.getenv", "OPENROUTER_API_KEY"): 1,
    }
)


def _python_files() -> Iterable[Path]:
    for root_name in SCAN_ROOTS:
        root = REPO_ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            rel = path.relative_to(REPO_ROOT).as_posix()
            if "/tests/" in rel:
                continue
            yield path


def _target_names(target: ast.AST) -> list[str]:
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, ast.Attribute):
        return [target.attr]
    if isinstance(target, (ast.Tuple, ast.List)):
        names: list[str] = []
        for item in target.elts:
            names.extend(_target_names(item))
        return names
    return []


def _is_relevant_model_literal(
    node: ast.Constant,
    parent: ast.AST | None,
    grandparent: ast.AST | None,
) -> bool:
    if isinstance(parent, ast.keyword) and parent.arg and "model" in parent.arg.lower():
        return True
    if isinstance(parent, ast.Dict):
        for key, value in zip(parent.keys, parent.values):
            if value is not node:
                continue
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                if "model" in key.value.lower():
                    return True
    if isinstance(parent, ast.Assign):
        return any(
            "model" in name.lower()
            for target in parent.targets
            for name in _target_names(target)
        )
    if isinstance(parent, ast.AnnAssign):
        return any("model" in name.lower() for name in _target_names(parent.target))
    if isinstance(parent, (ast.List, ast.Tuple)) and isinstance(
        grandparent, (ast.Assign, ast.AnnAssign)
    ):
        targets = grandparent.targets if isinstance(grandparent, ast.Assign) else [grandparent.target]
        tracked_names = [
            name
            for target in targets
            for name in _target_names(target)
        ]
        return any(
            any(token in name.lower() for token in ("model", "provider", "roster", "lane", "mind", "attempt"))
            for name in tracked_names
        )
    return False


def _parse_python(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _parent_map(tree: ast.Module) -> dict[ast.AST, ast.AST]:
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def _model_literal_debt() -> Counter[tuple[str, str]]:
    debt: Counter[tuple[str, str]] = Counter()
    for path in _python_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel in MODEL_REGISTRY_FILES:
            continue
        tree = _parse_python(path)
        parents = _parent_map(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            if not MODEL_LITERAL_RE.search(node.value):
                continue
            parent = parents.get(node)
            if isinstance(parent, ast.Expr):
                continue
            if _is_relevant_model_literal(node, parent, parents.get(parent)):
                debt[(rel, node.value)] += 1
    return debt


def _raw_key_read_debt() -> Counter[tuple[str, str, str]]:
    debt: Counter[tuple[str, str, str]] = Counter()
    for path in _python_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel in KEY_REGISTRY_FILES:
            continue
        tree = _parse_python(path)
        for node in ast.walk(tree):
            finding = _raw_key_read_finding(rel, node)
            if finding is not None:
                debt[finding] += 1
    return debt


def _raw_key_read_finding(rel: str, node: ast.AST) -> tuple[str, str, str] | None:
    key: str | None = None
    kind: str | None = None
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in {"get", "setdefault", "pop"}:
            value = func.value
            if _is_os_environ(value) and _constant_string_arg(node):
                key = _constant_string_arg(node)
                kind = f"os.environ.{func.attr}"
        if isinstance(func, ast.Attribute) and func.attr == "getenv":
            if isinstance(func.value, ast.Name) and func.value.id == "os" and _constant_string_arg(node):
                key = _constant_string_arg(node)
                kind = "os.getenv"
    if isinstance(node, ast.Subscript) and _is_os_environ(node.value):
        if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
            key = node.slice.value
            kind = "os.environ[]"
    if key is not None and kind is not None and PROVIDER_KEY_ENV_RE.fullmatch(key):
        return (rel, kind, key)
    return None


def _is_os_environ(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "environ"
        and isinstance(node.value, ast.Name)
        and node.value.id == "os"
    )


def _constant_string_arg(node: ast.Call) -> str | None:
    if node.args and isinstance(node.args[0], ast.Constant):
        if isinstance(node.args[0].value, str):
            return node.args[0].value
    return None


def _counter_delta(actual: Counter, expected: Counter) -> str:
    added = actual - expected
    removed = expected - actual
    lines: list[str] = []
    if added:
        lines.append("New disallowed entries:")
        lines.extend(f"  + {item!r} x{count}" for item, count in sorted(added.items()))
    if removed:
        lines.append("Baseline entries removed; shrink the allowlist:")
        lines.extend(f"  - {item!r} x{count}" for item, count in sorted(removed.items()))
    return "\n".join(lines)


def test_model_literals_do_not_escape_canonical_registries() -> None:
    actual = _model_literal_debt()
    assert actual == KNOWN_MODEL_LITERAL_DEBT, _counter_delta(
        actual,
        KNOWN_MODEL_LITERAL_DEBT,
    )


def test_provider_key_reads_do_not_escape_key_registry() -> None:
    actual = _raw_key_read_debt()
    assert actual == KNOWN_RAW_KEY_READ_DEBT, _counter_delta(
        actual,
        KNOWN_RAW_KEY_READ_DEBT,
    )


def test_semantic_commons_is_registered_or_branch_local_guarded() -> None:
    semantic_commons_paths = [REPO_ROOT / rel for rel in SEMANTIC_COMMONS_FILES]
    if all(path.exists() for path in semantic_commons_paths):
        contents = "\n".join(path.read_text(encoding="utf-8") for path in semantic_commons_paths)
        missing_terms = [term for term in SEMANTIC_COMMONS_REQUIRED_TERMS if term not in contents]
        assert not missing_terms, f"Semantic Commons missing routing terms: {missing_terms}"
        return

    guard_path = REPO_ROOT / BRANCH_LOCAL_SEMANTIC_COMMONS_GUARD
    assert guard_path.exists(), (
        "Semantic Commons files are absent in this worktree; add the ontology files "
        f"or maintain {BRANCH_LOCAL_SEMANTIC_COMMONS_GUARD}."
    )
    guard = guard_path.read_text(encoding="utf-8")
    missing_terms = [term for term in SEMANTIC_COMMONS_REQUIRED_TERMS if term not in guard]
    assert not missing_terms, f"Branch-local Semantic Commons guard missing routing terms: {missing_terms}"
