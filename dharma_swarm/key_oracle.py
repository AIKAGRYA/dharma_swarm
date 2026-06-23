"""Live-key oracle: which providers actually have a working key *right now*.

THE ONE WAY note: this module never reads or holds key material. It reads only
the liveness summary `dkeys test` writes to ``~/.dharma/keys_status.json``
(glyph + status, no secrets) and answers a single question: which provider
names currently have a live key?

FAIL-OPEN is the load-bearing contract. If the status file is missing, stale,
or unparseable, :func:`live_providers` returns ``None`` — the signal "I don't
know, keep today's env-presence behaviour". Callers MUST treat ``None`` as
"do not filter" so the oracle can never strand the fleet by going blind.

Glyph semantics (from dkeys):
  ✓ / oauth present  -> LIVE
  ~  (HTTP 429)       -> NOT live (rate-limited; pruned-but-recoverable)
  ✗  (auth/HTTP err)  -> NOT live
  ·  (no key)         -> NOT live
  $  (valid, funds=0) -> NOT live
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_TTL_S = 900  # 15 min interactive default (operator decision in GOAL doc)

# Glyphs (or any field) that count as a live key. oauth rows carry ✓ already;
# we also accept an explicit "oauth" marker defensively.
_LIVE_GLYPHS = frozenset({"✓", "oauth"})  # ✓
# Glyphs that are explicitly NOT live (documented for clarity; anything not in
# _LIVE_GLYPHS is non-live, but these are the ones we expect to see).
_DEAD_GLYPHS = frozenset({"✗", "~", "·", "$"})  # ✗ ~ · $


def _status_path(home: Path | None = None) -> Path:
    base = home or Path.home()
    return base / ".dharma" / "keys_status.json"


# Map a logical ProviderType value (or any provider-name string callers use) to
# the row key inside keys_status.json. dkeys clusters use different names than
# the dharma_swarm ProviderType enum, so we translate. ANTHROPIC liveness is
# the CLAUDE_CODE oauth row, per the consolidation goal (the metered Anthropic
# API row is usually dead; the Max-plan oauth is what actually serves).
_PROVIDER_TO_ROW: dict[str, str] = {
    "anthropic": "claude_code",
    "claude_code": "claude_code",
    "codex": "codex (openai-pro)",
    "openai": "openai",
    "openrouter": "openrouter",
    "openrouter_free": "openrouter",
    "nvidia_nim": "nvidia_nim",
    "ollama": "ollama_cloud",
    "groq": "groq",
    "cerebras": "cerebras",
    "google_ai": "gemini",
    "mistral": "mistral",
    "deepseek": "deepseek",
    "kimi": "kimi",
    "minimax": "minimax",
    "qwen": "qwen",
    "xai": "xai",
    "zai_coding": "zai_coding",
    "zai_global": "zai_global",
}

# Providers that need no remote key to be "live" — detected at RUNTIME, not
# assumed. This is the fix for the recurring "we have no provider" lie: the
# dispatcher (runtime_provider.py) treats claude_code as "always available if the
# claude binary is installed", but this oracle used to omit it — so a fresh
# session with no keys_status.json reported nothing and every reader concluded
# "no provider". claude_code IS keyless-live whenever the `claude` binary is on
# PATH (verified: it dispatches real completions with zero keys set).
_KEYLESS_LIVE = frozenset({"local"})  # legacy static fallback; prefer detection


def _detect_keyless_live() -> set[str]:
    """The keyless lanes usable RIGHT NOW, detected from the environment.

    - ``claude_code`` whenever the ``claude`` CLI is on PATH (the keyless
      Max-plan dispatch lane; this is what makes Claude Code web/remote/CI
      sessions able to dispatch with no API key at all).
    - ``local`` / ``ollama`` when an ollama runtime is reachable.
    """
    live: set[str] = set()
    if shutil.which("claude"):
        live.add("claude_code")
    if shutil.which("ollama") or os.environ.get("OLLAMA_HOST"):
        live.add("local")
        live.add("ollama")
    return live


def _provider_name(provider: object) -> str:
    """Coerce a ProviderType / enum / string into its lowercase value string."""
    value = getattr(provider, "value", provider)
    return str(value).strip().lower()


def _is_row_live(row: dict) -> bool:
    glyph = str(row.get("glyph", "")).strip()
    if glyph in _LIVE_GLYPHS:
        return True
    # Defensive: some oauth rows might omit the glyph but carry an oauth status.
    status = str(row.get("status", "")).lower()
    if glyph not in _DEAD_GLYPHS and ("oauth" in status and "present" in status):
        return True
    return False


def _load_status(home: Path | None = None) -> dict | None:
    path = _status_path(home)
    try:
        raw = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def live_providers(
    ttl_s: float = DEFAULT_TTL_S,
    *,
    home: Path | None = None,
    now: float | None = None,
) -> set[str] | None:
    """Return the set of provider-value strings with a live key, or None.

    FAIL-OPEN: returns ``None`` (meaning "unknown — do not filter") when the
    status file is missing, malformed, or older than ``ttl_s`` seconds. A
    real-but-empty set (all keys dead) is a *valid* answer and is NOT the same
    as None; callers must distinguish them.

    The returned set uses ProviderType *value* strings (e.g. ``"openai"``,
    ``"anthropic"``, ``"ollama"``) so callers can intersect directly with
    ``ProviderType`` members, plus the keyless-live providers (``"local"``).
    """
    data = _load_status(home)
    if data is None:
        return None

    rows = data.get("rows")
    if not isinstance(rows, dict) or not rows:
        return None

    last_test = data.get("last_test_ts")
    try:
        last_test_f = float(last_test)
    except (TypeError, ValueError):
        return None

    current = time.time() if now is None else now
    age = current - last_test_f
    if age < 0:
        # Clock skew / future timestamp: treat as fresh rather than stale.
        age = 0.0
    if age > ttl_s:
        logger.warning(
            "key_oracle: keys_status.json is stale (age=%.0fs > ttl=%.0fs); "
            "falling back to env-presence (run `dkeys test`).",
            age,
            ttl_s,
        )
        return None

    live: set[str] = _detect_keyless_live()
    for provider_name, row_key in _PROVIDER_TO_ROW.items():
        row = rows.get(row_key)
        if isinstance(row, dict) and _is_row_live(row):
            live.add(provider_name)
    return live


def is_provider_live(
    provider: object,
    ttl_s: float = DEFAULT_TTL_S,
    *,
    home: Path | None = None,
    now: float | None = None,
) -> bool | None:
    """Liveness for a single provider. None = unknown (fail-open).

    Keyless lanes detected at runtime (claude_code if the claude binary is
    present, local/ollama) are LIVE regardless of the status file — so a fresh
    session can never report claude_code as 'no provider' when it is right there.
    """
    name = _provider_name(provider)
    if name in _detect_keyless_live():
        return True
    live = live_providers(ttl_s, home=home, now=now)
    if live is None:
        return None
    return name in live


def dispatchable_now(
    ttl_s: float = DEFAULT_TTL_S,
    *,
    home: Path | None = None,
    now: float | None = None,
) -> set[str]:
    """The honest set of providers usable RIGHT NOW — never None, never blind.

    Keyless lanes detected from the environment (claude_code if the claude binary
    is on PATH, local/ollama) UNION any keyed providers proven live by the last
    ``dkeys test``. Unlike :func:`live_providers` (which returns None when the
    status file is missing), this always reflects the keyless lanes — so onboard
    and agents can never again conclude "we have no provider" when claude_code is
    present. This is the single canonical, repo-wide answer to "what can I
    dispatch to?".
    """
    keyed = live_providers(ttl_s, home=home, now=now)
    return _detect_keyless_live() | (keyed or set())


__all__ = [
    "DEFAULT_TTL_S",
    "dispatchable_now",
    "is_provider_live",
    "live_providers",
]
