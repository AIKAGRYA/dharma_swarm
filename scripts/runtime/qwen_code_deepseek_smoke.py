#!/usr/bin/env python3
"""Run a tiny Qwen Code -> DeepSeek V4 Pro smoke and write a receipt.

This script never logs API key values. It expects DEEPSEEK_API_KEY in the
environment and maps it to Qwen Code's OpenAI-compatible env vars.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path


DEFAULT_PROMPT = "Reply with exactly: QWEN_DEEPSEEK_V4_PRO_LIVE_OK"
DEFAULT_EXPECTED = "QWEN_DEEPSEEK_V4_PRO_LIVE_OK"
DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-pro"


def utcstamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def tail(text: str, limit: int = 1200) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def qwen_version() -> str:
    try:
        proc = subprocess.run(
            ["qwen", "--version"],
            check=False,
            text=True,
            capture_output=True,
            timeout=10,
        )
    except Exception as exc:  # noqa: BLE001
        return f"unavailable:{type(exc).__name__}"
    return (proc.stdout or proc.stderr).strip()


def write_receipt(receipt_dir: Path, payload: dict) -> Path:
    receipt_dir.mkdir(parents=True, exist_ok=True)
    path = receipt_dir / f"{payload['run_id']}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    ap.add_argument("--prompt", default=DEFAULT_PROMPT)
    ap.add_argument("--expected", default=DEFAULT_EXPECTED)
    ap.add_argument(
        "--receipt-dir",
        default="reports/agentops/deepseek_smokes",
        help="Directory for non-secret smoke receipts.",
    )
    ap.add_argument("--timeout-s", type=int, default=90)
    args = ap.parse_args()

    started = time.monotonic()
    run_id = f"qwen-code-deepseek-v4-pro-smoke-{utcstamp()}"
    receipt_dir = Path(args.receipt_dir)
    key_present = bool(os.environ.get("DEEPSEEK_API_KEY"))
    receipt = {
        "schema_version": "dharma.qwen_code_deepseek_smoke.v1",
        "run_id": run_id,
        "agent_uid": "qwen_code",
        "callsign": "qwen-code",
        "provider": "deepseek",
        "model": args.model,
        "base_url": args.base_url,
        "auth_env_var": "DEEPSEEK_API_KEY",
        "api_key_logged": False,
        "qwen_version": qwen_version(),
        "prompt_sha256": sha256_text(args.prompt),
        "expected": args.expected,
        "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "command_no_secret": [
            "qwen",
            "--bare",
            "--auth-type",
            "openai",
            "--model",
            args.model,
            "--output-format",
            "text",
            "--max-tool-calls",
            "0",
            "--max-wall-time",
            str(args.timeout_s),
            "--prompt",
            "<redacted prompt text; hash recorded>",
        ],
    }

    if not key_present:
        receipt.update(
            {
                "status": "blocked_missing_deepseek_api_key",
                "duration_s": round(time.monotonic() - started, 3),
            }
        )
        path = write_receipt(receipt_dir, receipt)
        print(path)
        return 2

    env = os.environ.copy()
    env["OPENAI_API_KEY"] = env["DEEPSEEK_API_KEY"]
    env["OPENAI_BASE_URL"] = args.base_url
    env["OPENAI_MODEL"] = args.model

    cmd = [
        "qwen",
        "--bare",
        "--auth-type",
        "openai",
        "--model",
        args.model,
        "--output-format",
        "text",
        "--max-tool-calls",
        "0",
        "--max-wall-time",
        str(args.timeout_s),
        "--prompt",
        args.prompt,
    ]

    try:
        proc = subprocess.run(
            cmd,
            check=False,
            text=True,
            capture_output=True,
            timeout=args.timeout_s + 15,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        receipt.update(
            {
                "status": "timeout",
                "duration_s": round(time.monotonic() - started, 3),
                "stdout_tail": tail(exc.stdout or ""),
                "stderr_tail": tail(exc.stderr or ""),
            }
        )
        path = write_receipt(receipt_dir, receipt)
        print(path)
        return 124

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    passed = proc.returncode == 0 and args.expected in stdout
    receipt.update(
        {
            "status": "pass" if passed else "fail",
            "returncode": proc.returncode,
            "duration_s": round(time.monotonic() - started, 3),
            "stdout_sha256": sha256_text(stdout),
            "stderr_sha256": sha256_text(stderr),
            "stdout_tail": tail(stdout),
            "stderr_tail": tail(stderr),
        }
    )
    path = write_receipt(receipt_dir, receipt)
    print(path)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
