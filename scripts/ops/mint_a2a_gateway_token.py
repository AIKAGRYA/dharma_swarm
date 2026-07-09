#!/usr/bin/env python3
"""Mint a bearer token for the A2A mailbox gateway.

Generates a random token, prints it ONCE to stdout (hand it to the agent's
operator through a secret channel), and appends its SHA-256 hash + agent_uid
to the gateway's token file. Plaintext is never stored.

Usage (on the gateway host):
    python3 scripts/ops/mint_a2a_gateway_token.py <agent_uid>
    python3 scripts/ops/mint_a2a_gateway_token.py <agent_uid> --callsign <cs>
    python3 scripts/ops/mint_a2a_gateway_token.py <agent_uid> --revoke   # remove all tokens for uid

--callsign records the LEGACY fleet callsign when it differs from the uid
(e.g. uid devin-roaming-2987d222, callsign devin) so the gateway drains the
dharma.a2a.<callsign> subject the live fleet actually sends to.

The running gateway re-reads this file on mtime change, so mint/revoke take
effect without a restart.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import sys
from pathlib import Path

_UID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _tokens_path() -> Path:
    root = Path(os.environ.get("DHARMA_A2A_GATEWAY_DIR", "~/.dharma/a2a_gateway")).expanduser()
    return root / "agent_tokens.json"


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    uid = argv[0]
    if not _UID_RE.match(uid):
        print(f"[error] invalid agent_uid: {uid!r}", file=sys.stderr)
        return 2

    path = _tokens_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {"tokens": []}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        data.setdefault("tokens", [])

    if "--revoke" in argv[1:]:
        before = len(data["tokens"])
        data["tokens"] = [row for row in data["tokens"] if row.get("agent_uid") != uid]
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"revoked {before - len(data['tokens'])} token(s) for {uid}")
        return 0

    callsign = ""
    if "--callsign" in argv[1:]:
        try:
            callsign = argv[argv.index("--callsign") + 1]
        except IndexError:
            print("[error] --callsign requires a value", file=sys.stderr)
            return 2
        if not _UID_RE.match(callsign):
            print(f"[error] invalid callsign: {callsign!r}", file=sys.stderr)
            return 2

    token = secrets.token_urlsafe(32)
    row = {"token_sha256": hashlib.sha256(token.encode()).hexdigest(), "agent_uid": uid}
    if callsign:
        row["legacy_callsign"] = callsign
    data["tokens"].append(row)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)
    print(f"# token for {uid} — shown ONCE, hash stored in {path}")
    print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
