"""Tests for the Sarathi apex holon source package (gates 5-8).

Gate 5: runtime surfaces (state file, pulse receipts)
Gate 6: gateway wraps reversibility gate
Gate 7: pulse reads fleet state
Gate 8: brief produced
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from dharma_swarm.holon_system.sarathi.brief import generate_brief
from dharma_swarm.holon_system.sarathi.gateway import evaluate, gate_and_execute
from dharma_swarm.holon_system.sarathi.pulse import run_pulse
from dharma_swarm.holon_system.sarathi.roster import fleet_summary, load_seat


# Gate 7: roster reads live heartbeat files
class TestRoster:
    """Gate 7: pulse reads Hermes + Codex + Fable/Fugu state."""

    def test_fleet_summary_has_expected_shape(self):
        summary = fleet_summary()
        assert summary["schema_version"] == "dharma.sarathi.roster.v1"
        assert "total_seats" in summary
        assert "alive_seats" in summary
        assert "dead_seats" in summary
        assert "seats" in summary
        assert isinstance(summary["seats"], list)

    def test_roster_includes_known_seats(self):
        summary = fleet_summary()
        seat_names = [s["name"] for s in summary["seats"]]
        # The critical seats must appear in the roster
        for critical in ("codex_composer", "fable_composer", "hermes-m5"):
            assert critical in seat_names, f"{critical} missing from roster"

    def test_load_seat_returns_not_found_for_unknown(self):
        seat = load_seat("nonexistent_seat_12345")
        assert seat.status == "NOT_FOUND"
        assert seat.is_alive is False

    def test_seat_status_is_alive_flag_works(self):
        summary = fleet_summary()
        for seat in summary["seats"]:
            dead_states = {"NATS_CLIENT_MISSING", "scaffolded_not_alive", "NOT_FOUND"}
            if seat["status"] in dead_states:
                assert seat["is_alive"] is False
            else:
                assert seat["is_alive"] is True


# Gate 6: gateway wraps reversibility gate
class TestGateway:
    """Gate 6: gateway evaluates actions through the code-deterministic gate."""

    def test_safe_action_classified_reversible(self):
        result = evaluate("read fleet status", operator_reachable=False)
        assert result.gate_decision["action_class"] == "reversible_safe"
        assert result.gate_decision["may_execute_unattended"] is True
        assert result.executed is False  # evaluate does not execute

    def test_force_push_blocked(self):
        result = evaluate("git push --force origin main", operator_reachable=False)
        assert result.gate_decision["may_execute_unattended"] is False
        assert "operator_only" in result.gate_decision["action_class"] or \
               "irreversible" in result.gate_decision["action_class"]

    def test_rm_rf_blocked(self):
        result = evaluate("rm -rf /important", operator_reachable=False)
        assert result.gate_decision["may_execute_unattended"] is False

    def test_spend_blocked(self):
        result = evaluate("spend 1000 on api credits", operator_reachable=False)
        assert result.gate_decision["may_execute_unattended"] is False

    def test_send_email_blocked(self):
        result = evaluate("send email to partner", operator_reachable=False)
        assert result.gate_decision["may_execute_unattended"] is False

    def test_gateway_writes_receipt(self):
        result = evaluate("read fleet status", operator_reachable=False)
        assert result.receipt_path != ""
        assert Path(result.receipt_path).exists()
        receipt = json.loads(Path(result.receipt_path).read_text())
        assert receipt["schema_version"] == "dharma.sarathi.gateway.v1"

    def test_gate_and_execute_only_runs_safe(self):
        """execute_fn should only be called for reversible_safe actions."""
        call_log = []
        def fake_execute():
            call_log.append("called")
            return {"result": "ok"}

        # Safe action → executes
        safe_result = gate_and_execute("read note", execute_fn=fake_execute)
        assert safe_result.executed is True
        assert len(call_log) == 1

        # Dangerous action → does NOT execute
        call_log.clear()
        danger_result = gate_and_execute("rm -rf /", execute_fn=fake_execute)
        assert danger_result.executed is False
        assert len(call_log) == 0


# Gate 8: brief produced
class TestBrief:
    """Gate 8: operator brief is produced from roster + gate result."""

    def test_brief_has_required_sections(self):
        roster = fleet_summary()
        gate = evaluate("read fleet status", operator_reachable=False)
        brief = generate_brief(roster=roster, gate_result=gate)

        assert "SARATHI PULSE" in brief
        assert "TOP LANE" in brief
        assert "FLEET" in brief
        assert "GATE" in brief

    def test_brief_surfaces_dead_critical_seat(self):
        """If a critical seat is dead, the brief should surface it."""
        roster = {
            "total_seats": 2,
            "alive_seats": ["hermes-m5"],
            "dead_seats": ["fable_composer"],
            "seats": [
                {"name": "hermes-m5", "status": "IDLE", "is_alive": True},
                {"name": "fable_composer", "status": "scaffolded_not_alive", "is_alive": False},
            ],
        }
        gate = {"action_class": "reversible_safe", "risk": "safe", "action": "read"}
        brief = generate_brief(roster=roster, gate_result=type("X", (), {"gate_decision": gate})())
        assert "fable composer" in brief.lower()

    def test_brief_works_with_no_gate_result(self):
        roster = fleet_summary()
        brief = generate_brief(roster=roster, gate_result=None)
        assert "SARATHI PULSE" in brief


# Gate 5: pulse creates runtime surfaces
class TestPulse:
    """Gate 5: pulse creates state file + pulse receipts."""

    def test_pulse_returns_receipt_with_all_fields(self):
        receipt = run_pulse("read fleet status", operator_reachable=False)

        assert receipt["schema_version"] == "dharma.sarathi.pulse.v1"
        assert "timestamp" in receipt
        assert "planned_action" in receipt
        assert "gate_decision" in receipt
        assert "roster" in receipt
        assert "brief" in receipt
        assert "receipt_path" in receipt

    def test_pulse_writes_receipt_file(self):
        receipt = run_pulse("read fleet status", operator_reachable=False)
        receipt_path = Path(receipt["receipt_path"])
        assert receipt_path.exists()
        saved = json.loads(receipt_path.read_text())
        assert saved["schema_version"] == "dharma.sarathi.pulse.v1"

    def test_pulse_creates_state_file(self):
        run_pulse("read fleet status", operator_reachable=False)
        state_path = Path.home() / ".dharma/a2a_bus/state/sarathi.json"
        assert state_path.exists()
        state = json.loads(state_path.read_text())
        assert state["wake_loop_active"] is False  # NEVER flip before gate 9
        assert state["service_alive"] is True

    def test_pulse_increments_count(self):
        state_path = Path.home() / ".dharma/a2a_bus/state/sarathi.json"
        before = json.loads(state_path.read_text()) if state_path.exists() else {}
        before_count = before.get("pulse_count", 0)

        run_pulse("read fleet status", operator_reachable=False)

        after = json.loads(state_path.read_text())
        assert after["pulse_count"] == before_count + 1

    def test_pulse_brief_contains_fleet_data(self):
        receipt = run_pulse("read fleet status", operator_reachable=False)
        brief = receipt["brief"]
        # At least one known seat should appear
        assert "codex" in brief.lower() or "hermes" in brief.lower()
