#!/usr/bin/env python3
"""Explicit, signed, halt-bound Foundry resume entrypoint."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
)

from dharma_swarm.foundry.killswitch import (  # noqa: E402
    ResumeAuthorityError,
    latch_current_stop,
    read_halt,
    resume_with_authority,
)


def _load_object(path: str) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _write_unsigned_body(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(_canonical(payload))
        handle.flush()
        os.fsync(handle.fileno())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", required=True)
    parser.add_argument("--envelope")
    parser.add_argument("--body", help="canonical JSON body signed by ssh-keygen -Y sign")
    parser.add_argument("--signature", help="detached OpenSSH SSHSIG file for --body")
    parser.add_argument("--prepare-body", help="write an unsigned, halt-bound canonical body and exit")
    parser.add_argument("--authority-id")
    parser.add_argument("--lease-id")
    parser.add_argument("--nonce")
    parser.add_argument("--ttl-seconds", type=int, default=300)
    parser.add_argument(
        "--trusted-keys",
        help="JSON file containing {'ed25519_public_keys': ['<hex>', ...]}",
    )
    parser.add_argument(
        "--trusted-public-key",
        action="append",
        default=[],
        help="existing trusted OpenSSH Ed25519 public-key file (repeatable)",
    )
    args = parser.parse_args(argv)
    try:
        state_root = Path(args.state_root)
        if args.prepare_body:
            if args.envelope or args.body or args.signature:
                raise ValueError("--prepare-body cannot be combined with a signed input")
            if not args.authority_id or not args.lease_id:
                raise ValueError("--prepare-body requires --authority-id and --lease-id")
            if args.ttl_seconds < 1 or args.ttl_seconds > 900:
                raise ValueError("resume body TTL must be between 1 and 900 seconds")
            latch_current_stop(state_root=state_root)
            halt = read_halt(state_root)
            if not halt or not halt.get("halt_digest"):
                raise ValueError("no valid durable halt is present")
            now = datetime.now(timezone.utc)
            body = {
                "schema_version": "foundry_resume_authority.v1",
                "authority_id": args.authority_id,
                "lease_id": args.lease_id,
                "scope": "foundry.resume",
                "halt_digest": halt["halt_digest"],
                "issued_at": now.isoformat(),
                "expires_at": (now + timedelta(seconds=args.ttl_seconds)).isoformat(),
                "nonce": args.nonce or str(uuid.uuid4()),
            }
            output = Path(args.prepare_body)
            _write_unsigned_body(output, body)
            print(json.dumps({
                "prepared": True,
                "body": str(output),
                "namespace": "foundry-resume",
                "next": "ssh-keygen -Y sign -f <operator-private-key> -n foundry-resume <body>",
            }, sort_keys=True))
            return 0
        if args.envelope:
            if args.body or args.signature:
                raise ValueError("use either --envelope or --body/--signature")
            envelope = _load_object(args.envelope)
        else:
            if not args.body or not args.signature:
                raise ValueError("resume requires --envelope or both --body and --signature")
            body = _load_object(args.body)
            if Path(args.body).read_bytes() != _canonical(body):
                raise ValueError("resume body is not exact canonical JSON")
            armored = Path(args.signature).read_text(encoding="utf-8")
            envelope = {
                **body,
                "signature": {
                    "scheme": "openssh-sshsig",
                    "namespace": "foundry-resume",
                    "signature": armored,
                },
            }
        keys: list[str] = []
        if args.trusted_keys:
            trust = _load_object(args.trusted_keys)
            raw_keys = trust.get("ed25519_public_keys")
            if not isinstance(raw_keys, list) or not all(isinstance(key, str) for key in raw_keys):
                raise ValueError("trusted-key file lacks ed25519_public_keys string list")
            keys = raw_keys
        openssh_keys = [
            Path(path).read_text(encoding="utf-8").strip()
            for path in args.trusted_public_key
        ]
        receipt = resume_with_authority(
            state_root,
            envelope,
            trusted_public_keys=keys,
            trusted_openssh_public_keys=openssh_keys,
        )
    except (OSError, ValueError, ResumeAuthorityError) as exc:
        print(f"resume refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"resumed": True, "receipt": str(receipt)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
