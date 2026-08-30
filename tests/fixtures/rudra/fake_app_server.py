#!/usr/bin/env python3
"""Scripted fake Codex app-server for offline protocol tests.

Reads a JSON script from argv[1] and plays it back over stdio, one JSON-RPC
line per frame. Steps:

  {"expect_method": "initialize", "result": {...}}  read a request, reply
  {"send": {...}}                                   write one message verbatim
  {"send_raw": "...", "chunks": N, "delay": S}      write raw bytes in chunks
  {"read_error_response": true}                     read one line, must be error
  {"read_request": true}                            read one request, discard
  {"exit": true}                                    terminate immediately (EOF)
"""

from __future__ import annotations

import json
import sys
import time


def main() -> int:
    with open(sys.argv[1]) as fh:
        steps = json.load(fh)
    for step in steps:
        if "send_raw" in step:
            data = step["send_raw"].encode()
            chunks = int(step.get("chunks", 1))
            delay = float(step.get("delay", 0.0))
            size = max(1, len(data) // chunks)
            for index in range(0, len(data), size):
                sys.stdout.buffer.write(data[index : index + size])
                sys.stdout.buffer.flush()
                if delay:
                    time.sleep(delay)
        elif "send" in step:
            sys.stdout.buffer.write(
                (json.dumps(step["send"]) + "\n").encode()
            )
            sys.stdout.buffer.flush()
        elif step.get("read_error_response"):
            line = sys.stdin.buffer.readline()
            message = json.loads(line)
            assert "error" in message, f"expected error response, got {message}"
        elif step.get("read_request"):
            sys.stdin.buffer.readline()
        elif "expect_method" in step:
            line = sys.stdin.buffer.readline()
            if not line:
                return 1
            request = json.loads(line)
            assert request["method"] == step["expect_method"], (
                f"expected {step['expect_method']}, got {request['method']}"
            )
            response = {
                "jsonrpc": "2.0",
                "id": request["id"],
                "result": step.get("result", {}),
            }
            sys.stdout.buffer.write((json.dumps(response) + "\n").encode())
            sys.stdout.buffer.flush()
        elif step.get("exit"):
            return 0
    # Drain stdin so the client sees a clean EOF when we finish.
    return 0


if __name__ == "__main__":
    sys.exit(main())
