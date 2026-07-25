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
import subprocess
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
    "kimi_code": "kimi",
    "minimax": "minimax",
    "qwen": "qwen",
    "xai": "xai",
    "zhipu": "zai_coding",
    "zai_coding": "zai_coding",
    "zai_global": "zai_global",
}

# Providers that need no project API key to be "live" — detected at RUNTIME,
# not assumed. A binary on PATH is not enough: `claude auth status` can report a
# Max login while headless `claude -p` still fails with a 401.  The liveness
# oracle must answer "can this lane complete a headless dispatch now?", not "is
# a binary installed?".
_KEYLESS_LIVE = frozenset({"local"})  # legacy static fallback; prefer detection
_CLAUDE_CODE_SMOKE_TTL_S = 300.0
_claude_code_smoke_cache: tuple[float, bool, str] | None = None


def _claude_code_dispatchable_now(*, now: float | None = None) -> bool:
    """Return True only when the Claude CLI can complete a headless prompt now.

    This intentionally probes the same headless surface the provider uses
    (`claude -p`).  It is cached briefly in-process to avoid re-smoking on every
    router decision, and it never reads or logs secrets.
    """
    global _claude_code_smoke_cache

    binary = shutil.which("claude")
    if not binary:
        return False

    current = time.time() if now is None else now
    if _claude_code_smoke_cache is not None:
        checked_at, ok, _detail = _claude_code_smoke_cache
        if current - checked_at <= _CLAUDE_CODE_SMOKE_TTL_S:
            return ok

    env = dict(os.environ)
    env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
    env.pop("CLAUDECODE", None)
    env.pop("CLAUDE_CODE_ENTRYPOINT", None)
    env.pop("CLAUDE_CODE_INCLUDE_PARTIAL_MESSAGES", None)
    try:
        result = subprocess.run(
            [
                binary,
                "-p",
                "Reply with exactly: OK_DHARMA_CLAUDE_CODE_SMOKE",
                "--output-format",
                "text",
            ],
            capture_output=True,
            text=True,
            timeout=20,
            env=env,
            stdin=subprocess.DEVNULL,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001 - liveness probe must fail closed
        _claude_code_smoke_cache = (current, False, f"{type(exc).__name__}: {exc}")
        logger.debug("claude_code headless smoke failed", exc_info=True)
        return False

    output = (result.stdout or result.stderr or "").strip()
    ok = result.returncode == 0 and "OK_DHARMA_CLAUDE_CODE_SMOKE" in output
    if not ok:
        logger.warning(
            "claude_code binary exists but headless dispatch is not live "
            "(rc=%s, output=%r)",
            result.returncode,
            output[:160],
        )
    _claude_code_smoke_cache = (current, ok, output[:160])
    return ok


def _detect_keyless_live() -> set[str]:
    """The keyless lanes usable RIGHT NOW, detected from the environment.

    - ``claude_code`` only when the ``claude`` CLI can complete a headless
      `claude -p` smoke now. Binary presence and `auth status` are insufficient.
    - ``local`` / ``ollama`` when an ollama runtime is reachable.
    """
    live: set[str] = set()
    if _claude_code_dispatchable_now():
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


def _rows_by_key(data: dict) -> dict[str, dict]:
    """Return keys_status rows keyed by dkeys row name.

    Historical fixtures used ``{"rows": {"openai": {...}}}``, while current
    ``dkeys test`` writes ``{"rows": [{"name": "openai", ...}, ...]}``.
    Accept both shapes so the oracle follows the live cache instead of silently
    treating a fresh array-shaped file as unreadable.
    """

    rows = data.get("rows")
    if isinstance(rows, dict):
        return {str(key): row for key, row in rows.items() if isinstance(row, dict)}
    if not isinstance(rows, list):
        return {}

    keyed: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = row.get("name") or row.get("provider") or row.get("id") or row.get("key")
        if not name:
            continue
        keyed[str(name)] = row
    return keyed


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
    ``ProviderType`` members, plus the keyless-live providers
    (``"local"``, ``"ollama"``, and only-smoke-proven ``"claude_code"``).
    """
    data = _load_status(home)
    if data is None:
        return None

    rows = _rows_by_key(data)
    if not rows:
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

    Keyless lanes detected at runtime (claude_code only if headless dispatch
    smokes green, local/ollama) are LIVE regardless of the status file.
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

    Keyless lanes detected from the environment (claude_code only if a headless
    smoke completes, local/ollama) UNION any keyed providers proven live by the
    last ``dkeys test``. Unlike :func:`live_providers` (which returns None when
    the status file is missing), this always reflects proven keyless lanes. This
    is the single canonical, repo-wide answer to "what can I dispatch to?".
    """
    keyed = live_providers(ttl_s, home=home, now=now)
    return _detect_keyless_live() | (keyed or set())


__all__ = [
    "DEFAULT_TTL_S",
    "dispatchable_now",
    "is_provider_live",
    "live_providers",
]
