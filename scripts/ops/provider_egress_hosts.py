#!/usr/bin/env python3
"""Print the network-egress hosts the LLM providers need.

WHY THIS EXISTS (read once, never reverse-engineer it again):
A wired key is not enough to use a model. The runtime environment also has a
network *egress allowlist*; if a provider's API host is not on it, the call
dies with::

    PermissionDeniedError: Host not in allowlist: <host>.
    Add this host to your network egress settings to allow access.

That error is the *environment's* egress proxy, not the code and not the key.
The fix is to add the host to the environment's egress settings (its network
policy) — see docs/ops/MODEL_KEY_ROUTING.md § Egress. More hosts allowed = more
models reachable = more freedom. This script tells you which hosts to allow.

The list is DERIVED from the provider source (the `base_url` defaults in
``dharma_swarm/providers.py`` / ``runtime_provider.py``), not hand-maintained,
so it stays correct as providers are added — add an adapter with a base_url and
it shows up here automatically.

Usage:
    python3 scripts/ops/provider_egress_hosts.py          # one host per line
    python3 scripts/ops/provider_egress_hosts.py --json    # {"hosts": [...]}
    python3 scripts/ops/provider_egress_hosts.py --urls    # full base URLs
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]

# Source files whose provider `base_url` defaults declare the first-party hosts.
_SOURCES = (
    "dharma_swarm/providers.py",
    "dharma_swarm/runtime_provider.py",
)

# A base-url binding near an https literal — keeps random API references
# (telemetry, search, market data) out of the egress list. Case-insensitive so
# both `base_url = "https://…"` and `OPENAI_BASE_URL = "https://…"` constants
# are caught.
_BASE_URL_LINE = re.compile(
    r"base_url.{0,60}?(https://[A-Za-z0-9._\-]+)",
    re.IGNORECASE,
)

# Hosts reachable through a path that needs no direct egress entry, noted for
# the operator so the picture is complete rather than silently omitted.
_SPECIAL = {
    "claude_code (Anthropic Max)": "CLI subprocess — no HTTP egress host "
    "(force the metered API with DHARMA_FORCE_ANTHROPIC_API=1 → api.anthropic.com)",
    "ollama": "local daemon (127.0.0.1 / OLLAMA_BASE_URL) — no public egress",
    "moonshot / deepseek / perplexity": "routed via OpenRouter today → openrouter.ai",
}


def derive_urls() -> list[str]:
    urls: set[str] = set()
    for rel in _SOURCES:
        path = REPO_ROOT / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in _BASE_URL_LINE.finditer(text):
            urls.add(match.group(1).rstrip("/"))
    return sorted(urls)


def hosts_from_urls(urls: list[str]) -> list[str]:
    hosts = {urlparse(u).netloc for u in urls if urlparse(u).netloc}
    return sorted(hosts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument("--urls", action="store_true", help="full base URLs, not just hosts")
    args = parser.parse_args()

    urls = derive_urls()
    hosts = hosts_from_urls(urls)

    if args.json:
        print(json.dumps({"hosts": hosts, "urls": urls, "special": _SPECIAL}, indent=2))
        return 0

    if args.urls:
        for url in urls:
            print(url)
        return 0

    for host in hosts:
        print(host)
    sys.stderr.write(
        "\n# Add these to the environment's egress allowlist (network policy).\n"
        "# Special cases (no direct egress entry needed):\n"
    )
    for name, note in _SPECIAL.items():
        sys.stderr.write(f"#   {name}: {note}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
