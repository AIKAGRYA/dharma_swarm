"""Tests for dharma_swarm.operator_core.intent_payloads."""

from __future__ import annotations

import json

from dharma_swarm.operator_core.intent_payloads import (
    build_intent_plan,
    _classify_bridge_intent,
)


class TestClassifyBridgeIntent:
    def test_empty_prompt(self):
        result = _classify_bridge_intent("")
        assert result["kind"] == "chat"
        assert result["confidence"] == "low"

    def test_slash_command(self):
        result = _classify_bridge_intent("/status")
        assert result["kind"] == "command"
        assert result["command"] == "status"
        assert result["confidence"] == "high"

    def test_identity_request(self):
        result = _classify_bridge_intent("who are you")
        assert result["kind"] == "identity"

    def test_evolution_request(self):
        result = _classify_bridge_intent("evolve the system")
        assert result["kind"] == "evolution"

    def test_agent_request(self):
        result = _classify_bridge_intent("delegate to a subagent")
        assert result["kind"] == "agent"

    def test_chat_fallback(self):
        result = _classify_bridge_intent("add dark mode to dashboard")
        assert result["kind"] == "chat"

    def test_plain_language_command(self):
        result = _classify_bridge_intent("show runtime status")
        assert result["kind"] == "command"
        assert result["command"] == "runtime"


class TestBuildIntentPlan:
    def test_returns_json_serializable(self):
        data = build_intent_plan("add dark mode")
        serialized = json.dumps(data, default=str)
        assert isinstance(json.loads(serialized), dict)

    def test_has_required_sections(self):
        data = build_intent_plan("fix the tests")
        assert data["version"] == "v1"
        assert data["domain"] == "intent_plan"
        assert data["prompt"] == "fix the tests"
        assert "bridge_intent" in data
        assert "routing" in data
        assert "prescriptions" in data
        assert "mission" in data

    def test_decomposition_splits_compound(self):
        data = build_intent_plan(
            "debug the failing tests and then refactor the engine"
        )
        sub_tasks = data["routing"]["sub_tasks"]
        assert len(sub_tasks) >= 2

    def test_single_task_no_split(self):
        data = build_intent_plan("check status")
        sub_tasks = data["routing"]["sub_tasks"]
        assert len(sub_tasks) == 1

    def test_prescriptions_with_missing_db(self):
        data = build_intent_plan(
            "fix tests",
            knowledge_db="/nonexistent/knowledge.db",
        )
        assert data["prescriptions"] == []

    def test_mission_context_loaded(self):
        data = build_intent_plan("plan the next sprint")
        assert "mission" in data
