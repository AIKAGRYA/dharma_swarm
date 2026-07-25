"""The provider egress-host helper derives the network-allowlist hosts from the
provider registry so an agent (or operator) hitting "Host not in allowlist"
learns exactly which hosts to allow — and the list cannot silently drift as
providers are added.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts/ops/provider_egress_hosts.py"


def _load():
    spec = importlib.util.spec_from_file_location("provider_egress_hosts", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_derives_first_party_provider_hosts():
    mod = _load()
    hosts = mod.hosts_from_urls(mod.derive_urls())
    # The wired first-party lanes that need direct egress must appear. z.ai is
    # the lane this whole thread surfaced; openrouter is the multi-model lane.
    for expected in ("api.z.ai", "openrouter.ai", "api.openai.com"):
        assert expected in hosts, f"{expected} missing from derived egress hosts: {hosts}"


def test_hosts_are_bare_hostnames():
    mod = _load()
    hosts = mod.hosts_from_urls(mod.derive_urls())
    assert hosts, "derivation returned no hosts"
    for host in hosts:
        assert "://" not in host and "/" not in host, f"{host} is not a bare hostname"


def test_urls_carry_scheme():
    mod = _load()
    urls = mod.derive_urls()
    assert urls and all(u.startswith("https://") for u in urls)
