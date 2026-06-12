#!/usr/bin/env python3
"""F-172 scripted stub bridge — speaks the wire protocol on stdio (bridge_events.md shapes).

Pointed at via DHARMA_PYTHON; ignores the `-m dharma_swarm.terminal_bridge stdio`
argv the TS side passes. Completes exactly one turn per session.start with a
response text and multiple trace steps, using hex session/request ids so the
F-172 no-raw-ids rule is exercised end to end.

Scenarios (STUB_BRIDGE_SCENARIO env var):
  default (unset)        — F-172 tooled turn: ack + thinking + tool + text_complete + session_end.
  assistant_then_empty   — F-173: first session.start answers via the identity-intent
                           shortcut shape {type:"assistant", request_id, message} + synth
                           session_end (bridge_events.md §1.16 — no timestamp on the wire);
                           the second session.start ends with NO response-bearing event
                           (ack + session_end only).
"""
import json
import os
import sys
import time

SESSION_HEX = "9f86d081884c7d659a2feaa0c55ad015"
TOOL_CALL_HEX = "c0ffee00c0ffee00deadbeef"
RESPONSE_TEXT = "The Helm hears you loud and clear."
ASSISTANT_TEXT = "I am the Helm. Identity intents route straight through me."


def emit(payload):
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def stream_envelope(event_type, request_id, **extra):
    base = {
        "type": event_type,
        "schema_version": 1,
        "timestamp": time.time(),
        "provider_id": "codex",
        "session_id": SESSION_HEX,
        "raw": None,
        "request_id": request_id,
    }
    base.update(extra)
    return base


def main():
    scenario = os.environ.get("STUB_BRIDGE_SCENARIO", "")
    turn_count = 0
    emit({"type": "bridge.ready", "schema_version": 1, "protocol": "dharma-terminal-bridge"})
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except ValueError:
            continue
        request_id = str(request.get("id", ""))
        request_type = str(request.get("type", ""))
        if request_type == "handshake":
            emit({
                "type": "handshake.result",
                "request_id": request_id,
                "providers": [{
                    "provider_id": "codex",
                    "default_model": "gpt-5.4",
                    "models": [{"id": "gpt-5.4", "display_name": "gpt-5.4", "capabilities": []}],
                }],
                "default_provider": "codex",
                "legacy_terminal": {"stack": "python-textual", "replacement_target": "bun-ink"},
                "adapter_boot_error": None,
            })
        elif request_type == "status":
            emit({
                "type": "status.result",
                "request_id": request_id,
                "active_session_id": None,
                "active_provider": "codex",
                "providers": ["codex"],
            })
        elif request_type == "session.bootstrap":
            emit({
                "type": "session.bootstrap.result",
                "request_id": request_id,
                "prompt": str(request.get("prompt", "")),
                "active_tab": str(request.get("active_tab", "chat")),
                "intent": {"kind": "chat", "auto_execute": False, "confidence": "high", "reason": "stub chat intent"},
                "selected_provider": "codex",
                "selected_model": "gpt-5.4",
                "routing_strategy": "responsive",
                "system_prompt": "",
            })
        elif request_type == "session.start":
            turn_count += 1
            emit({
                "type": "session.ack",
                "request_id": request_id,
                "session_id": SESSION_HEX,
                "provider": "codex",
                "model": "gpt-5.4",
            })
            if scenario == "assistant_then_empty":
                if turn_count == 1:
                    emit({"type": "assistant", "request_id": request_id, "message": ASSISTANT_TEXT})
                emit(stream_envelope("session_end", request_id, success=True, error_code=None, error_message=None))
                continue
            emit(stream_envelope("thinking_complete", request_id, content="weighing the reply", is_redacted=False))
            emit(stream_envelope(
                "tool_call_complete", request_id,
                tool_call_id=TOOL_CALL_HEX, tool_name="exec_command",
                arguments="{\"cmd\": \"true\"}", provider_options={},
            ))
            emit(stream_envelope(
                "tool_result", request_id,
                tool_call_id=TOOL_CALL_HEX, tool_name="exec_command",
                content="ok", is_error=False, structured_result=None, duration_ms=12,
            ))
            emit(stream_envelope("text_complete", request_id, content=RESPONSE_TEXT, content_index=0, role="assistant"))
            emit(stream_envelope("session_end", request_id, success=True, error_code=None, error_message=None))


if __name__ == "__main__":
    main()
