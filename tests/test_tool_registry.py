"""Tests for the Tool Registry (Hermes-inspired)."""

from __future__ import annotations

import asyncio
import json

import pytest

from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.spine.identity import ExecutionIdentity
from dharma_swarm.tool_registry import ToolRegistry, registry


def _identity(**overrides: str) -> ExecutionIdentity:
    payload = {
        "task_id": "task-tool-registry",
        "agent_id": "agent-tool-registry",
        "session_id": "session-tool-registry",
        "trace_id": "trace-tool-registry",
        "correlation_id": "corr-tool-registry",
        "run_id": "run-tool-registry",
        "claim_id": "claim-tool-registry",
        "idempotency_key": "idem-tool-registry",
    }
    payload.update(overrides)
    return ExecutionIdentity.new(**payload)


class TestToolRegistration:
    """Tests for tool registration and lookup."""

    def test_register_and_lookup(self):
        reg = ToolRegistry()
        reg.register(
            name="test_tool",
            toolset="core",
            schema={"name": "test_tool", "description": "A test", "parameters": {}},
            handler=lambda args, **kw: json.dumps({"ok": True}),
        )
        assert "test_tool" in reg
        assert len(reg) == 1
        assert reg.get_all_tool_names() == ["test_tool"]

    def test_get_toolset_for_tool(self):
        reg = ToolRegistry()
        reg.register(
            name="alpha",
            toolset="group_a",
            schema={"name": "alpha", "description": "A"},
            handler=lambda args, **kw: "{}",
        )
        assert reg.get_toolset_for_tool("alpha") == "group_a"
        assert reg.get_toolset_for_tool("nonexistent") is None

    def test_tool_to_toolset_map(self):
        reg = ToolRegistry()
        reg.register(name="a", toolset="x", schema={"name": "a"}, handler=lambda a, **kw: "{}")
        reg.register(name="b", toolset="y", schema={"name": "b"}, handler=lambda a, **kw: "{}")
        mapping = reg.get_tool_to_toolset_map()
        assert mapping == {"a": "x", "b": "y"}

    def test_contains(self):
        reg = ToolRegistry()
        reg.register(name="foo", toolset="t", schema={"name": "foo"}, handler=lambda a, **kw: "{}")
        assert "foo" in reg
        assert "bar" not in reg


class TestToolDefinitions:
    """Tests for schema retrieval with availability checks."""

    def test_get_all_definitions(self):
        reg = ToolRegistry()
        reg.register(name="a", toolset="t", schema={"name": "a", "description": "A"}, handler=lambda a, **kw: "{}")
        reg.register(name="b", toolset="t", schema={"name": "b", "description": "B"}, handler=lambda a, **kw: "{}")
        defs = reg.get_definitions()
        assert len(defs) == 2
        assert all(d["type"] == "function" for d in defs)

    def test_get_definitions_filtered(self):
        reg = ToolRegistry()
        reg.register(name="a", toolset="t", schema={"name": "a"}, handler=lambda a, **kw: "{}")
        reg.register(name="b", toolset="t", schema={"name": "b"}, handler=lambda a, **kw: "{}")
        defs = reg.get_definitions(tool_names={"a"})
        assert len(defs) == 1

    def test_check_fn_filters_unavailable(self):
        reg = ToolRegistry()
        reg.register(
            name="available", toolset="t",
            schema={"name": "available"}, handler=lambda a, **kw: "{}",
            check_fn=lambda: True,
        )
        reg.register(
            name="unavailable", toolset="t",
            schema={"name": "unavailable"}, handler=lambda a, **kw: "{}",
            check_fn=lambda: False,
        )
        defs = reg.get_definitions()
        assert len(defs) == 1
        assert defs[0]["function"]["name"] == "available"

    def test_check_fn_exception_skips(self):
        reg = ToolRegistry()
        def bad_check():
            raise RuntimeError("broken")
        reg.register(
            name="broken", toolset="t",
            schema={"name": "broken"}, handler=lambda a, **kw: "{}",
            check_fn=bad_check,
        )
        defs = reg.get_definitions(quiet=True)
        assert len(defs) == 0


class TestToolDispatch:
    """Tests for tool execution dispatch."""

    def test_dispatch_sync(self):
        reg = ToolRegistry()
        reg.register(
            name="echo",
            toolset="core",
            schema={"name": "echo"},
            handler=lambda args, **kw: json.dumps({"echo": args.get("msg")}),
        )
        result = json.loads(reg.dispatch("echo", {"msg": "hello"}))
        assert result == {"echo": "hello"}

    def test_dispatch_unknown_tool(self):
        reg = ToolRegistry()
        result = json.loads(reg.dispatch("nonexistent", {}))
        assert "error" in result
        assert "Unknown tool" in result["error"]

    def test_dispatch_error_handling(self):
        reg = ToolRegistry()
        def bad_handler(args, **kw):
            raise ValueError("boom")
        reg.register(name="bad", toolset="t", schema={"name": "bad"}, handler=bad_handler)
        result = json.loads(reg.dispatch("bad", {}))
        assert "error" in result
        assert "boom" in result["error"]

    def test_dispatch_records_idempotent_side_effect_receipts(self, tmp_path):
        calls: list[str] = []
        runtime = RuntimeStateStore(tmp_path / "runtime.db")
        identity = _identity()
        reg = ToolRegistry(runtime_state=runtime, require_identity=True)
        reg.register(
            name="mutate",
            toolset="core",
            schema={"name": "mutate"},
            handler=lambda args, **kw: calls.append(args["value"]) or json.dumps({"ok": True}),
        )

        result = json.loads(
            reg.dispatch("mutate", {"value": "first"}, execution_identity=identity)
        )

        ledger = asyncio.run(runtime.get_run_ledger(identity.run_id))
        receipt_types = [receipt.receipt_type for receipt in ledger["receipts"]]
        consumed_statuses = [
            receipt.status
            for receipt in ledger["receipts"]
            if receipt.receipt_type == "idempotency_consumed"
        ]

        assert result == {"ok": True}
        assert calls == ["first"]
        assert receipt_types.count("side_effect_intent") == 1
        assert receipt_types.count("side_effect_complete") == 1
        assert consumed_statuses == ["accepted"]

    def test_dispatch_suppresses_duplicate_side_effects(self, tmp_path):
        calls: list[str] = []
        runtime = RuntimeStateStore(tmp_path / "runtime.db")
        identity = _identity()
        reg = ToolRegistry(runtime_state=runtime, require_identity=True)
        reg.register(
            name="mutate",
            toolset="core",
            schema={"name": "mutate"},
            handler=lambda args, **kw: calls.append(args["value"]) or json.dumps({"ok": True}),
        )

        first = json.loads(
            reg.dispatch("mutate", {"value": "first"}, execution_identity=identity)
        )
        duplicate = json.loads(
            reg.dispatch("mutate", {"value": "first"}, execution_identity=identity)
        )

        ledger = asyncio.run(runtime.get_run_ledger(identity.run_id))
        receipt_types = [receipt.receipt_type for receipt in ledger["receipts"]]
        consumed_statuses = [
            receipt.status
            for receipt in ledger["receipts"]
            if receipt.receipt_type == "idempotency_consumed"
        ]

        assert first == {"ok": True}
        assert duplicate == {
            "duplicate": True,
            "tool_name": "mutate",
            "side_effect_key": "tool_registry.dispatch:mutate:task-tool-registry",
        }
        assert calls == ["first"]
        assert receipt_types.count("side_effect_intent") == 1
        assert receipt_types.count("side_effect_complete") == 1
        assert consumed_statuses == ["accepted", "duplicate"]

    def test_dispatch_conflicting_duplicate_args_fail_before_handler(self, tmp_path):
        calls: list[str] = []
        runtime = RuntimeStateStore(tmp_path / "runtime.db")
        identity = _identity()
        reg = ToolRegistry(runtime_state=runtime, require_identity=True)
        reg.register(
            name="mutate",
            toolset="core",
            schema={"name": "mutate"},
            handler=lambda args, **kw: calls.append(args["value"]) or json.dumps({"ok": True}),
        )

        first = json.loads(
            reg.dispatch("mutate", {"value": "first"}, execution_identity=identity)
        )
        conflict = json.loads(
            reg.dispatch("mutate", {"value": "second"}, execution_identity=identity)
        )

        ledger = asyncio.run(runtime.get_run_ledger(identity.run_id))
        consumed_statuses = [
            receipt.status
            for receipt in ledger["receipts"]
            if receipt.receipt_type == "idempotency_consumed"
        ]

        assert first == {"ok": True}
        assert "error" in conflict
        assert "operation_hash conflict" in conflict["error"]
        assert calls == ["first"]
        assert consumed_statuses == ["accepted", "conflict"]


class TestToolsetAvailability:
    """Tests for toolset-level checks."""

    def test_toolset_available_no_check(self):
        reg = ToolRegistry()
        reg.register(name="a", toolset="open", schema={"name": "a"}, handler=lambda a, **kw: "{}")
        assert reg.is_toolset_available("open") is True

    def test_toolset_available_with_check(self):
        reg = ToolRegistry()
        reg.register(
            name="a", toolset="gated",
            schema={"name": "a"}, handler=lambda a, **kw: "{}",
            check_fn=lambda: True,
        )
        assert reg.is_toolset_available("gated") is True

    def test_toolset_unavailable(self):
        reg = ToolRegistry()
        reg.register(
            name="a", toolset="locked",
            schema={"name": "a"}, handler=lambda a, **kw: "{}",
            check_fn=lambda: False,
        )
        assert reg.is_toolset_available("locked") is False

    def test_check_toolset_requirements(self):
        reg = ToolRegistry()
        reg.register(name="a", toolset="yes", schema={"name": "a"}, handler=lambda a, **kw: "{}", check_fn=lambda: True)
        reg.register(name="b", toolset="no", schema={"name": "b"}, handler=lambda a, **kw: "{}", check_fn=lambda: False)
        reqs = reg.check_toolset_requirements()
        assert reqs["yes"] is True
        assert reqs["no"] is False

    def test_get_available_toolsets(self):
        reg = ToolRegistry()
        reg.register(
            name="x", toolset="ts1",
            schema={"name": "x"}, handler=lambda a, **kw: "{}",
            requires_env=["API_KEY"],
        )
        toolsets = reg.get_available_toolsets()
        assert "ts1" in toolsets
        assert "x" in toolsets["ts1"]["tools"]
        assert "API_KEY" in toolsets["ts1"]["requirements"]


class TestModuleSingleton:
    """Test the module-level singleton."""

    def test_singleton_exists(self):
        assert isinstance(registry, ToolRegistry)
