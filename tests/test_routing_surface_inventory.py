"""Guards for the repository's known direct runtime-routing surfaces.

Adds are intentional: extend ``KNOWN_DIRECT_CREATE_RUNTIME_PROVIDER_FILES`` and note the
tier in comments. Scope excludes ``scripts/`` (operator utilities).

``KNOWN_NATIVE_PROCESS_REPLACEMENT_SINKS`` is a separate, deliberately narrow
inventory of Python ``os.exec*`` process-replacement calls under ``dharma_swarm``
and ``api``.  It classifies shell handoffs as well as the native interactive
provider handoff, but does not claim to cover subprocess calls, SDK calls, shell
scripts, or every possible inference sink.

Routing truth (2026 maintenance):
- ``api/routers/chat.py`` remains the in-repo **dashboard** bypass (per-request provider).
- ``AutonomousAgent`` injected path: ``anthropic`` and ``openrouter`` →
  ``ModelRouter.complete_for_task`` when the router registers overlapping runtime
  providers; ``codex`` always uses
  ``create_runtime_provider(..., working_dir=identity.working_directory)``;
  fallbacks use direct runtime chain. ``cli_wake`` documents no router (legacy CLI).
- ``holon_bridge.py`` is the read-only agent-as-itself bridge and resolves through the
  canonical runtime-provider door.
- ``living_agent_kernel_provider_worker.py`` is the promoted kernel provider execution
  boundary after promotion admission.
Also asserts shared ``create_default_router()`` is invoked once per long-running
``orchestrate_live`` loop (source-inspect guard).
"""

from __future__ import annotations

import ast
from pathlib import Path

import inspect

from dharma_swarm import orchestrate_live


REPO_ROOT = Path(__file__).resolve().parents[1]

# Tuple: path relative to repo root — file must contain at least one literal call
# ``create_runtime_provider(`` (not merely an import).
KNOWN_DIRECT_CREATE_RUNTIME_PROVIDER_FILES: frozenset[str] = frozenset(
    {
        "dharma_swarm/api_key_audit.py",
        "dharma_swarm/autonomous_agent.py",
        "dharma_swarm/consolidation.py",
        "dharma_swarm/dgm_loop.py",
        "dharma_swarm/forge_v1/canonical.py",
        "dharma_swarm/forge_v1/providers.py",
        "dharma_swarm/holon_bridge.py",
        "dharma_swarm/operator_core/living_agent_kernel_provider_worker.py",
        "dharma_swarm/provider_matrix.py",
        "dharma_swarm/provider_smoke.py",
        "dharma_swarm/runtime_provider.py",
        "dharma_swarm/thinkodynamic_director.py",
        "api/routers/chat.py",
    }
)

DASHBOARD_CHAT_ROUTER_BYPASS = "api/routers/chat.py"

# Tuple: (path, enclosing function, os.exec* method, executable expression,
# occurrence within that function/expression).  The occurrence makes duplicate
# additions visible without pinning the inventory to fragile source line numbers.
KNOWN_NATIVE_PROCESS_REPLACEMENT_SINKS: dict[
    tuple[str, str, str, str, int], str
] = {
    (
        "dharma_swarm/terminal_commands/lifecycle.py",
        "cmd_up",
        "execvpe",
        "'bash'",
        1,
    ): "shell_handoff",
    (
        "dharma_swarm/terminal_commands/lifecycle.py",
        "cmd_swarm",
        "execvp",
        "'bash'",
        1,
    ): "shell_handoff",
    (
        "dharma_swarm/terminal_commands/lifecycle.py",
        "cmd_setup",
        "execvp",
        "'bash'",
        1,
    ): "shell_handoff",
    (
        "dharma_swarm/terminal_commands/surfaces.py",
        "cmd_chat",
        "execvpe",
        "runtime.binary_path",
        1,
    ): "provider_interactive:claude_code:provider_resolved:model_native_deferred",
}


def _py_files_under(rel: str) -> list[Path]:
    root = REPO_ROOT / rel
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*.py") if p.is_file())


def _call_sites() -> set[str]:
    found: set[str] = set()
    for base in ("dharma_swarm", "api"):
        for path in _py_files_under(base):
            text = path.read_text(encoding="utf-8", errors="replace")
            if "create_runtime_provider(" in text:
                found.add(str(path.relative_to(REPO_ROOT)))
    return found


class _NativeExecVisitor(ast.NodeVisitor):
    def __init__(self, relative_path: str) -> None:
        self.relative_path = relative_path
        self.function_stack: list[str] = []
        self.counts: dict[tuple[str, str, str], int] = {}
        self.sites: set[tuple[str, str, str, str, int]] = set()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.function_stack.append(node.name)
        self.generic_visit(node)
        self.function_stack.pop()

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "os"
            and func.attr in {"execvp", "execvpe", "execlp", "execlpe"}
            and node.args
        ):
            enclosing_function = (
                self.function_stack[-1] if self.function_stack else "<module>"
            )
            executable = ast.unparse(node.args[0])
            count_key = (enclosing_function, func.attr, executable)
            occurrence = self.counts.get(count_key, 0) + 1
            self.counts[count_key] = occurrence
            self.sites.add(
                (
                    self.relative_path,
                    enclosing_function,
                    func.attr,
                    executable,
                    occurrence,
                )
            )
        self.generic_visit(node)


def _native_process_replacement_sites() -> set[tuple[str, str, str, str, int]]:
    found: set[tuple[str, str, str, str, int]] = set()
    for base in ("dharma_swarm", "api"):
        for path in _py_files_under(base):
            relative_path = str(path.relative_to(REPO_ROOT))
            visitor = _NativeExecVisitor(relative_path)
            visitor.visit(ast.parse(path.read_text(encoding="utf-8")))
            found.update(visitor.sites)
    return found


def test_create_runtime_provider_inventory_matches_disk() -> None:
    found = _call_sites()
    assert found == KNOWN_DIRECT_CREATE_RUNTIME_PROVIDER_FILES, (
        "Update KNOWN_DIRECT_CREATE_RUNTIME_PROVIDER_FILES to match create_runtime_provider"
        f" call sites. Found={sorted(found)} expected={sorted(KNOWN_DIRECT_CREATE_RUNTIME_PROVIDER_FILES)}"
    )


def test_native_process_replacement_inventory_matches_disk() -> None:
    found = _native_process_replacement_sites()
    expected = set(KNOWN_NATIVE_PROCESS_REPLACEMENT_SINKS)
    assert found == expected, (
        "Classify each Python os.exec* process-replacement call. This inventory "
        "does not cover subprocess, SDK, or shell-script sinks. "
        f"Found={sorted(found)} expected={sorted(expected)}"
    )


def test_dgc_chat_native_provider_exec_is_runtime_and_policy_resolved() -> None:
    provider_sinks = {
        site: classification
        for site, classification in KNOWN_NATIVE_PROCESS_REPLACEMENT_SINKS.items()
        if classification.startswith("provider_interactive:")
    }
    assert provider_sinks == {
        (
            "dharma_swarm/terminal_commands/surfaces.py",
            "cmd_chat",
            "execvpe",
            "runtime.binary_path",
            1,
        ): "provider_interactive:claude_code:provider_resolved:model_native_deferred"
    }

    source = (REPO_ROOT / "dharma_swarm/terminal_commands/surfaces.py").read_text(
        encoding="utf-8"
    )
    assert "resolve_runtime_provider_config(" in source
    assert "ProviderPolicyRouter(" in source
    assert "ProviderRoutingConfig(default_model_hints={})" in source
    assert ").route(" in source
    assert "available_providers=[ProviderType.CLAUDE_CODE]" in source
    assert '"ANTHROPIC_API_KEY"' in source
    assert '"ANTHROPIC_AUTH_TOKEN"' in source
    assert "        os.execvpe(runtime.binary_path, command, env)" in source.splitlines()
    assert 'os.execvpe("claude"' not in source


def test_dashboard_chat_bypass_remains_inventoried() -> None:
    assert DASHBOARD_CHAT_ROUTER_BYPASS in KNOWN_DIRECT_CREATE_RUNTIME_PROVIDER_FILES
    chat = REPO_ROOT / DASHBOARD_CHAT_ROUTER_BYPASS
    assert chat.is_file()
    assert "create_runtime_provider(" in chat.read_text(encoding="utf-8")


def test_autonomous_agent_exposes_model_router_and_codex_stays_direct() -> None:
    src = (REPO_ROOT / "dharma_swarm/autonomous_agent.py").read_text(encoding="utf-8")
    assert "def __init__(self, identity: AgentIdentity, *, model_router:" in src
    assert src.count("await self._model_router.complete_for_task(") == 2
    codex_start = src.index("async def _call_codex")
    nxt = src.find("\n    async def ", codex_start + 1)
    codex_block = src[codex_start:nxt] if nxt != -1 else src[codex_start:]
    assert "complete_for_task" not in codex_block


def test_cli_wake_standalone_construct_without_router() -> None:
    src = (REPO_ROOT / "dharma_swarm/autonomous_agent.py").read_text(encoding="utf-8")
    cli_start = src.index("async def cli_wake")
    cli_end = src.index("\n\nif __name__", cli_start)
    block = src[cli_start:cli_end]
    hit = [ln for ln in block.splitlines() if "AutonomousAgent(identity)" in ln]
    assert len(hit) == 1
    assert "model_router" not in hit[0]


def test_run_conductor_loop_instantiates_default_router_once() -> None:
    src = inspect.getsource(orchestrate_live.run_conductor_loop)
    assert src.count("create_default_router()") == 1


def test_replication_monitor_instantiates_default_router_once() -> None:
    src = inspect.getsource(orchestrate_live._run_replication_monitor_loop)
    assert src.count("create_default_router()") == 1
