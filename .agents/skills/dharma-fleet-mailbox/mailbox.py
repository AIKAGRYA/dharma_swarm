#!/usr/bin/env python3
"""Stdlib-only client for the Dharma A2A mailbox gateway.

Lets any agent that can make an HTTPS call (Hermes Agent, OpenClaw, Claude
Code, Devin, a cron job) join the fleet bus without nats-py, without a
dharma_swarm checkout, and without broker credentials.  The gateway
(``dharma_swarm/a2a/mailbox_gateway.py``) maps one bearer token to exactly one
agent identity; this script never invents a sender.

    export DHARMA_A2A_GATEWAY_URL=https://<gateway-host>:8422
    export DHARMA_A2A_GATEWAY_TOKEN=<token minted by scripts/ops/mint_a2a_gateway_token.py>

    mailbox.py whoami
    mailbox.py send hermes "gateway smoke"           # publishes to dharma.a2a.hermes
    mailbox.py send rushabdev --route agent-inbox --json '{"task":"..."}'
    mailbox.py inbox --batch 10 [--route agent-inbox]
    mailbox.py heartbeat                              # send a presence note to the fleet subject

Exit codes: 0 ok, 2 usage/config, 3 transport, 4 gateway rejected (4xx/5xx).
Output is one JSON document on stdout so an agent can parse it.  The token is
never printed and never placed in a URL.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

ENV_URL = "DHARMA_A2A_GATEWAY_URL"
ENV_TOKEN = "DHARMA_A2A_GATEWAY_TOKEN"
FLEET_PEER = "fleet"  # gateway route "a2a" -> dharma.a2a.fleet (broadcast)
DEFAULT_TIMEOUT_S = 15.0
MAX_TEXT_CHARS = 8_000


class MailboxError(Exception):
    def __init__(self, code: int, message: str, detail: object = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail


def _config() -> tuple[str, str]:
    url = (os.environ.get(ENV_URL) or "").strip().rstrip("/")
    token = (os.environ.get(ENV_TOKEN) or "").strip()
    if not url.startswith(("http://", "https://")):
        raise MailboxError(2, f"{ENV_URL} must be an absolute http(s) URL")
    if not token:
        raise MailboxError(2, f"{ENV_TOKEN} is not set")
    return url, token


def _call(
    method: str,
    path: str,
    *,
    body: dict | None = None,
    timeout: float = DEFAULT_TIMEOUT_S,
    opener=None,
) -> dict:
    url, token = _config()
    data = None
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if body is not None:
        data = json.dumps(body, sort_keys=True).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url + path, data=data, method=method, headers=headers)
    open_fn = opener or urllib.request.urlopen
    try:
        with open_fn(request, timeout=timeout) as response:  # noqa: S310 — operator-configured URL
            raw = response.read()
            status = getattr(response, "status", 200)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:2_000]
        try:
            detail = json.loads(detail)
        except ValueError:
            pass
        raise MailboxError(4, f"gateway rejected {method} {path}: HTTP {exc.code}", detail) from exc
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise MailboxError(3, f"gateway unreachable: {exc}") from exc
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except ValueError as exc:
        raise MailboxError(3, f"gateway returned non-JSON (HTTP {status})") from exc
    if not isinstance(parsed, dict):
        raise MailboxError(3, "gateway returned a non-object JSON document")
    return parsed


def whoami(**kw) -> dict:
    return _call("GET", "/a2a/mailbox/whoami", **kw)


def send(to: str, message: object, *, route: str = "a2a", **kw) -> dict:
    if isinstance(message, str):
        if len(message) > MAX_TEXT_CHARS:
            raise MailboxError(2, f"text exceeds {MAX_TEXT_CHARS} chars")
        message = {"text": message}
    return _call(
        "POST", "/a2a/mailbox/send", body={"to": to, "route": route, "body": message}, **kw
    )


def inbox(*, batch: int = 10, route: str = "a2a", **kw) -> dict:
    batch = max(1, min(int(batch), 25))
    return _call("GET", f"/a2a/mailbox/inbox?batch={batch}&route={route}", **kw)


def heartbeat(note: str = "", **kw) -> dict:
    """Publish a presence note on the fleet broadcast subject.

    This is a *reported* signal.  Fleet Hub labels it ``reported_unverified``
    until the hub ACL binds identity to transport; do not read it as liveness.
    """

    identity = whoami(**kw)
    body = {
        "kind": "presence.v1",
        "agent_uid": identity.get("agent_uid"),
        "at": datetime.now(timezone.utc).isoformat(),
        "text": note or f"heartbeat from {identity.get('agent_uid')}",
    }
    return send(FLEET_PEER, body, **kw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mailbox.py", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("whoami")
    p_send = sub.add_parser("send")
    p_send.add_argument("to")
    p_send.add_argument("text", nargs="?", default="")
    p_send.add_argument("--json", dest="json_body", default=None, help="JSON object body instead of text")
    p_send.add_argument("--route", choices=("a2a", "agent-inbox"), default="a2a")
    p_inbox = sub.add_parser("inbox")
    p_inbox.add_argument("--batch", type=int, default=10)
    p_inbox.add_argument("--route", choices=("a2a", "agent-inbox"), default="a2a")
    p_hb = sub.add_parser("heartbeat")
    p_hb.add_argument("note", nargs="?", default="")
    args = parser.parse_args(argv)
    try:
        if args.command == "whoami":
            result = whoami()
        elif args.command == "send":
            if args.json_body:
                try:
                    message = json.loads(args.json_body)
                except ValueError as exc:
                    raise MailboxError(2, f"--json is not valid JSON: {exc}") from exc
                if not isinstance(message, dict):
                    raise MailboxError(2, "--json must be a JSON object")
            elif args.text:
                message = args.text
            else:
                raise MailboxError(2, "send needs text or --json")
            result = send(args.to, message, route=args.route)
        elif args.command == "inbox":
            result = inbox(batch=args.batch, route=args.route)
        else:
            result = heartbeat(args.note)
    except MailboxError as exc:
        print(json.dumps({"ok": False, "error": exc.message, "detail": exc.detail}), file=sys.stdout)
        return exc.code
    print(json.dumps({"ok": True, **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
