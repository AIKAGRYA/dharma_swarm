#!/usr/bin/env python3
"""dkeys — instant lookup + live test of every LLM provider key on this Mac.

Subcommands:
  dkeys              — status table of all providers (uses cache, <50ms)
  dkeys list         — same as no-arg
  dkeys test         — live ping every provider in parallel, refresh cache
  dkeys find <term>  — locate key references by variable-name fragment (never values)
  dkeys add <var> [--test]         — hidden prompt; atomically upsert safely
  dkeys add <var> --stdin [--test] — read from stdin (never argv/history)
  dkeys safe-json          — machine-readable provider status with no secret metadata
  dkeys exec <var>... -- <command> [args...] — inject only named keys into one child
  dkeys path         — print canonical key files in priority order
  dkeys env          — disabled: raw secret export is intentionally forbidden

Canonical key store: ~/.dharma/agent_keys.env  (mode 600, sourced by ~/.zshrc)
Cache:               ~/.dharma/keys_status.json (last test results + timestamps)

Canonical source: repository scripts/dkeys.py; install to ~/.dharma/bin/dkeys.
Design: ONE file, no deps beyond httpx (already in dharma_swarm venv).
"""
from __future__ import annotations

import asyncio
import fcntl
import getpass
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
KEY_FILE = HOME / ".dharma" / "agent_keys.env"
HERMES_ENV = HOME / ".hermes" / ".env"
CACHE_FILE = HOME / ".dharma" / "keys_status.json"

# All providers we know about. Each entry has the env var name, cluster, endpoint
# spec, model to test, and how to authenticate. The test request is always
# minimal (~10 tokens). Adding a provider = adding one dict here.
# OAuth/subscription providers (no API key) use a "probe": presence/auth check
# instead of an HTTP key-test, so they are visible alongside metered keys.


def _probe_codex():
    p = os.path.expanduser("~/.codex/auth.json")
    if not os.path.exists(p):
        return ("·", "no codex auth", "—")
    try:
        d = json.load(open(p))
    except Exception as e:
        return ("?", f"codex parse: {type(e).__name__}", "—")
    mode = d.get("auth_mode") or ("chatgpt-pro" if d.get("tokens") else ("api" if d.get("OPENAI_API_KEY") else ""))
    if mode:
        return ("✓", f"oauth present ({mode})", "~/.codex/auth.json")
    return ("·", "codex auth empty", "—")


def _probe_qwen():
    import os
    d = os.path.expanduser("~/.qwen")
    if not os.path.isdir(d):
        return ("·", "no qwen CLI login", "—")
    for f in ("oauth_creds.json", "creds.json", "source.json"):
        if os.path.exists(os.path.join(d, f)):
            return ("✓", "qwen CLI oauth present", "~/.qwen")
    return ("·", "qwen dir, no creds", "—")


def _probe_claude_code():
    import subprocess
    try:
        r = subprocess.run(
            ["security", "find-generic-password", "-s", "Claude Code-credentials"],
            capture_output=True, timeout=5,
        )
        if r.returncode == 0:
            return ("✓", "Max plan (keychain oauth)", "Keychain")
    except Exception:
        pass
    return ("·", "no claude_code keychain", "—")


PROVIDERS = [
    {
        "name": "anthropic",
        "env": "ANTHROPIC_API_KEY",
        "cluster": "anthropic",
        "url": "https://api.anthropic.com/v1/messages",
        "auth_header": "x-api-key",
        "extra_headers": {"anthropic-version": "2023-06-01"},
        "body": lambda: {
            "model": "claude-3-5-haiku-20241022",
            "max_tokens": 5,
            "messages": [{"role": "user", "content": "ping"}],
        },
    },
    {
        "name": "openrouter",
        "env": "OPENROUTER_API_KEY",
        "cluster": "multi",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
        "body": lambda: {
            "model": "z-ai/glm-4.5-air:free",
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 5,
        },
    },
    {
        "name": "ollama_cloud",
        "env": "OLLAMA_API_KEY",
        "cluster": "chinese_cluster",
        "url": "https://ollama.com/api/chat",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
        "body": lambda: {
            "model": "glm-5:cloud",
            "messages": [{"role": "user", "content": "ping"}],
            "stream": False,
            "options": {"num_predict": 5},
        },
    },
    {
        "name": "gemini",
        "env": "GEMINI_API_KEY",
        "cluster": "deepmind",
        "url_template": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
        "auth_header": "X-goog-api-key",
        "body": lambda: {
            "contents": [{"role": "user", "parts": [{"text": "ping"}]}],
            "generationConfig": {"maxOutputTokens": 5},
        },
    },
    {
        "name": "xai",
        "env": "XAI_API_KEY",
        "cluster": "xai",
        "url": "https://api.x.ai/v1/chat/completions",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
        "body": lambda: {
            "model": "grok-4-fast",
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 5,
        },
    },
    {
        "name": "zai_coding",
        "env": "GLM_API_KEY",
        "cluster": "chinese_cluster",
        "url": "https://api.z.ai/api/coding/paas/v4/chat/completions",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
        "body": lambda: {
            "model": "glm-5.2",
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 5,
        },
    },
    {
        "name": "zai_global",
        "env": "GLM_API_KEY",
        "cluster": "chinese_cluster",
        "url": "https://api.z.ai/api/paas/v4/chat/completions",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
        "body": lambda: {
            "model": "glm-4.5-air",
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 5,
        },
    },
    {
        "name": "minimax",
        "env": "MINIMAX_API_KEY",
        "cluster": "chinese_cluster",
        "url": "https://api.minimax.io/v1/text/chatcompletion_v2",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
        "body": lambda: {
            "model": "MiniMax-M2",
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 5,
        },
    },
    {
        "name": "deepseek",
        "env": "DEEPSEEK_API_KEY",
        "cluster": "chinese_cluster",
        "url": "https://api.deepseek.com/chat/completions",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
        "body": lambda: {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 5,
        },
    },
    {
        "name": "groq",
        "env": "GROQ_API_KEY",
        "cluster": "groq",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
        "body": lambda: {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 5,
        },
    },
    {
        "name": "nvidia_nim",
        "env": "NVIDIA_API_KEY",
        "cluster": "nvidia",
        "url": "https://integrate.api.nvidia.com/v1/chat/completions",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
        "body": lambda: {
            "model": "nvidia/llama-3.3-nemotron-super-49b-v1.5",
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 5,
        },
    },
    {
        "name": "openai",
        "env": "OPENAI_API_KEY",
        "cluster": "openai",
        "url": "https://api.openai.com/v1/chat/completions",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
        "body": lambda: {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 5,
        },
    },
    {
        "name": "codex (openai-pro)",
        "env": "OPENAI_API_KEY",
        "cluster": "openai",
        "probe": _probe_codex,
    },
    {
        "name": "qwen",
        "env": "QWEN_OAUTH",
        "cluster": "qwen",
        "probe": _probe_qwen,
    },
    {
        "name": "claude_code",
        "env": "CLAUDE_CODE_OAUTH",
        "cluster": "anthropic",
        "probe": _probe_claude_code,
    },
    {
        "name": "kimi",
        "env": "KIMI_API_KEY",
        "cluster": "chinese_cluster",
        "url": "https://api.kimi.com/coding/v1/chat/completions",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
        "body": lambda: {
            "model": "kimi-for-coding",
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 5,
        },
    },
]


def load_env_files() -> dict:
    """Read all sources of keys, in priority order. Later wins."""
    env = dict(os.environ)
    for path in [HERMES_ENV, KEY_FILE]:
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            if k.startswith("export "):
                k = k[7:].strip()
            v = v.strip()
            if re.fullmatch(r"\$[A-Za-z_][A-Za-z0-9_]*", v):
                v = env.get(v[1:], "")
            else:
                try:
                    parsed = shlex.split(f"VALUE={v}", comments=False, posix=True)
                except ValueError:
                    continue
                if len(parsed) != 1 or not parsed[0].startswith("VALUE="):
                    continue
                v = parsed[0].split("=", 1)[1]
            if v:
                env[k] = v
    return env


def mask(val: str) -> str:
    if not val:
        return "(not set)"
    return "<set>"


def load_cache() -> dict:
    if not CACHE_FILE.exists():
        return {}
    try:
        cache = json.loads(CACHE_FILE.read_text())
        for row in (cache.get("rows") or {}).values():
            if row.get("key_present") and str(row.get("masked") or "").startswith("<set"):
                row["masked"] = "<set>"
        return cache
    except Exception:
        return {}


def save_cache(cache: dict) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_FILE.with_name(f".{CACHE_FILE.name}.tmp.{os.getpid()}")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(cache, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, CACHE_FILE)
        os.chmod(CACHE_FILE, 0o600)
    finally:
        if tmp.exists():
            tmp.unlink()


def status_glyph(http: int | None, body: str) -> tuple[str, str]:
    if http is None:
        return ("·", "no key")
    if 200 <= http < 300:
        return ("✓", "live")
    body_l = (body or "").lower()
    if "insufficient balance" in body_l or "no resource package" in body_l or "all available credits" in body_l or "spending limit" in body_l:
        return ("$", "valid · funds=0")
    if "rate limit" in body_l or http == 429:
        return ("~", f"HTTP {http} rate-limited")
    if http in (401, 403):
        if "credits" in body_l or "balance" in body_l or "limit" in body_l:
            return ("$", "valid · funds=0")
        return ("✗", f"HTTP {http} auth")
    if 500 <= http:
        return ("?", f"HTTP {http} server")
    return ("✗", f"HTTP {http}")


async def test_one(client, p, env) -> dict:
    if p.get("probe"):
        glyph, status, detail = p["probe"]()
        return {"name": p["name"], "cluster": p["cluster"], "env_var": p.get("env", "—"), "key_present": glyph in ("✓", "$", "~"), "http": None, "status": status, "glyph": glyph, "ms": 0, "masked": detail}
    key = env.get(p["env"])
    if not key:
        return {"name": p["name"], "cluster": p["cluster"], "env_var": p["env"], "key_present": False, "http": None, "status": "no key", "glyph": "·", "ms": 0}
    url = p.get("url_template", p.get("url"))
    headers = {"Content-Type": "application/json"}
    prefix = p.get("auth_prefix", "")
    headers[p["auth_header"]] = f"{prefix}{key}"
    headers.update(p.get("extra_headers", {}))
    body = p["body"]()
    t0 = time.perf_counter()
    try:
        r = await client.post(url, headers=headers, json=body, timeout=15.0)
        ms = int((time.perf_counter() - t0) * 1000)
        try:
            body_str = r.text[:300]
        except Exception:
            body_str = ""
        glyph, status = status_glyph(r.status_code, body_str)
        return {"name": p["name"], "cluster": p["cluster"], "env_var": p["env"], "key_present": True, "http": r.status_code, "status": status, "glyph": glyph, "ms": ms, "masked": mask(key)}
    except Exception as e:
        ms = int((time.perf_counter() - t0) * 1000)
        return {"name": p["name"], "cluster": p["cluster"], "env_var": p["env"], "key_present": True, "http": None, "status": f"error: {type(e).__name__}", "glyph": "✗", "ms": ms, "masked": mask(key)}


async def test_all(env) -> list[dict]:
    try:
        import httpx
    except ImportError:
        fallback = HOME / ".hermes" / "hermes-agent" / "venv" / "bin" / "python3"
        if fallback.exists() and Path(sys.executable).resolve() != fallback.resolve():
            os.execv(str(fallback), [str(fallback), str(Path(__file__)), *sys.argv[1:]])
        sys.stderr.write("httpx not installed (pip install httpx)\n")
        sys.exit(2)
    async with httpx.AsyncClient() as client:
        return await asyncio.gather(*[test_one(client, p, env) for p in PROVIDERS])


def render_table(rows: list[dict], last_test_ts: float | None) -> str:
    if last_test_ts:
        age_s = int(time.time() - last_test_ts)
        if age_s < 60:
            age = f"{age_s}s ago"
        elif age_s < 3600:
            age = f"{age_s // 60}m ago"
        else:
            age = f"{age_s // 3600}h ago"
    else:
        age = "never"
    out = []
    out.append(f"╔═ LLM PROVIDER KEYS — last live-test: {age}  ═════════════════════════════════════════════")
    out.append("║ glyph  provider          cluster           HTTP   status              key                     env var")
    out.append("║ ───────────────────────────────────────────────────────────────────────────────────────────────────")
    cluster_seen = set()
    for r in rows:
        http = str(r.get("http") or "—")
        masked = r.get("masked", "(not set)") if r.get("key_present") else "—"
        out.append(f"║  {r['glyph']:<5} {r['name']:<17} {r['cluster']:<17} {http:<6} {r['status']:<19} {masked:<23} {r['env_var']}")
        cluster_seen.add(r["cluster"])
    out.append("║")
    n_live = sum(1 for r in rows if r["glyph"] == "✓")
    n_funds = sum(1 for r in rows if r["glyph"] == "$")
    n_noauth = sum(1 for r in rows if r["glyph"] == "✗")
    n_nokey = sum(1 for r in rows if r["glyph"] == "·")
    clusters_live = {r["cluster"] for r in rows if r["glyph"] == "✓"}
    out.append(f"║ summary: {n_live} live  ·  {n_funds} valid-but-no-funds  ·  {n_noauth} auth-fail  ·  {n_nokey} no-key-yet")
    out.append(f"║ decorrelation clusters with at-least-one live key: {len(clusters_live)} ({', '.join(sorted(clusters_live)) or '—'})")
    out.append("╚════════════════════════════════════════════════════════════════════════════════════════════════")
    out.append("")
    out.append("legend:  ✓ live   $ valid-but-no-funds   ~ rate-limited   ✗ auth-fail   · no-key   ? server-err")
    out.append("hint:    dkeys test  ←  refresh live status     dkeys find <term>  ←  scour disk for a key")
    return "\n".join(out)


def cmd_list(args):
    env = load_env_files()
    cache = load_cache()
    rows = []
    cached_rows = cache.get("rows", {})
    for p in PROVIDERS:
        cached = cached_rows.get(p["name"], {})
        if p.get("probe"):
            if cached:
                row = dict(cached)
            else:
                glyph, status, detail = p["probe"]()
                row = {
                    "name": p["name"],
                    "cluster": p["cluster"],
                    "env_var": p.get("env", "—"),
                    "key_present": glyph in ("✓", "$", "~"),
                    "http": None,
                    "status": status,
                    "glyph": glyph,
                    "ms": 0,
                    "masked": detail,
                }
            rows.append(row)
            continue
        key = env.get(p["env"])
        if key:
            row = {
                "name": p["name"], "cluster": p["cluster"], "env_var": p["env"], "key_present": True,
                "http": cached.get("http"), "status": cached.get("status", "(unknown — run: dkeys test)"),
                "glyph": cached.get("glyph", "?"), "masked": mask(key), "ms": cached.get("ms", 0),
            }
        else:
            row = {"name": p["name"], "cluster": p["cluster"], "env_var": p["env"], "key_present": False, "http": None, "status": "no key", "glyph": "·"}
        rows.append(row)
    print(render_table(rows, cache.get("last_test_ts")))


def cmd_test(args):
    env = load_env_files()
    t0 = time.perf_counter()
    rows = asyncio.run(test_all(env))
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    cache = {"last_test_ts": time.time(), "rows": {r["name"]: r for r in rows}}
    save_cache(cache)
    print(render_table(rows, cache["last_test_ts"]))
    print(f"\nlive-tested {len(rows)} providers in {elapsed_ms}ms (parallel)")


def cmd_find(args):
    if not args:
        print("usage: dkeys find <variable-name-fragment>  (e.g. 'minimax', 'glm', 'xai')", file=sys.stderr)
        sys.exit(2)
    term = args[0]
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", term):
        print("find accepts variable-name fragments only", file=sys.stderr)
        sys.exit(2)
    t0 = time.perf_counter()
    env_hits, spot_env, spot_other = [], [], []
    # 1. Canonical key files — show matching VARIABLE NAMES only.
    for path in [KEY_FILE, HERMES_ENV]:
        if not path.exists():
            continue
        for i, line in enumerate(path.read_text().splitlines(), 1):
            candidate = line.lstrip()
            commented = candidate.startswith("#")
            if commented:
                candidate = candidate[1:].lstrip()
            match = re.match(r"(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=", candidate)
            if match and term.lower() in match.group(1).lower():
                env_hits.append((str(path), i, commented, match.group(1)))
    # 2. Spotlight — bucketed: env-like files (high signal) vs other (just count)
    env_re = re.compile(r"(?:\.env(?:\.|$)|\.envrc$|api_keys\.(?:py|json|toml)$|keys\.(?:json|toml|env)$|credentials\.(?:json|toml)$)")
    ignore_segs = ("/node_modules/", "/.git/", "/__pycache__/", "/site-packages/", "/build/", "/dist/")
    ignore_dirs = ("migration_delta", "agentic-ui-refs", "/Library/Developer/", "/usr/local/include/", "/usr/share/", "test_", "/tests/")
    try:
        out = subprocess.check_output(["mdfind", term], timeout=3, stderr=subprocess.DEVNULL).decode()
        for p in out.splitlines():
            if not p:
                continue
            if any(s in p for s in ignore_segs):
                continue
            if any(s in p for s in ignore_dirs):
                continue
            if env_re.search(p):
                spot_env.append(p)
            else:
                spot_other.append(p)
    except Exception:
        pass
    # 3. Keychain
    keychain_hit = None
    try:
        out = subprocess.check_output(["security", "find-generic-password", "-l", term], timeout=2, stderr=subprocess.STDOUT).decode()
        if "attributes:" in out:
            keychain_hit = out.split("\n")[0]
    except Exception:
        pass
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    total = len(env_hits) + len(spot_env) + len(spot_other) + (1 if keychain_hit else 0)
    print(f"=== dkeys find '{term}' — searched in {elapsed_ms}ms ===")
    if env_hits:
        print(f"\n[direct env-file hits — {len(env_hits)}]")
        for path, lineno, commented, variable in env_hits:
            flag = " [COMMENTED]" if commented else " [ACTIVE]"
            print(f"  {path}:{lineno}{flag}")
            print(f"    {variable}=<redacted>")
    if spot_env:
        print(f"\n[other env/credentials files on disk — {len(spot_env)}]")
        for p in spot_env[:15]:
            print(f"  {p}")
        if len(spot_env) > 15:
            print(f"  … + {len(spot_env) - 15} more")
    if keychain_hit:
        print(f"\n[macOS Keychain] {keychain_hit}")
    if spot_other:
        print(f"\n[other files mentioning '{term}' — {len(spot_other)} (suppressed; run `mdfind {term}` to see them all)]")
    if total == 0:
        print("  (no occurrences anywhere — key was never on this Mac)")


# dkeys ↔ api_keys.py key-name contract (INTERFACE_MISMATCH_MAP.md IMM-26).
# dharma_swarm/api_keys.py reads canonical runtime names; dkeys/dev habit uses
# vendor names. Adding either side of a pair writes BOTH so a key added under
# one name is never invisible to the runtime (the 2026-06-06 GEMINI_API_KEY
# failure class). Extending: append a tuple here, mirror it in the IMM entry.
ALIAS_PAIRS = [
    ("GEMINI_API_KEY", "GOOGLE_AI_API_KEY"),   # api_keys.py canonical: GOOGLE_AI_API_KEY
    ("NVIDIA_API_KEY", "NVIDIA_NIM_API_KEY"),  # api_keys.py canonical: NVIDIA_NIM_API_KEY
]


def runtime_aliases(var: str) -> list[str]:
    out = []
    for a, b in ALIAS_PAIRS:
        if var == a:
            out.append(b)
        elif var == b:
            out.append(a)
    return out


def _upsert_export(text: str, var: str, value: str) -> str:
    """Replace any `VAR=` or `export VAR=` line with `export VAR=value`; append if absent."""
    pattern = re.compile(rf"^(?:export\s+)?{re.escape(var)}=.*$", re.M)
    line = f"export {var}={shlex.quote(value)}"
    if pattern.search(text):
        return pattern.sub(lambda m: line, text)
    return (text.rstrip() + f"\n{line}\n") if text.strip() else f"{line}\n"


def _atomic_upsert_key_file(var: str, value: str) -> list[str]:
    """Lock, re-read, and atomically upsert ``var`` plus runtime aliases.

    Reading inside the lock matters: a read-before-lock implementation can
    silently discard a concurrent ``dkeys add`` even when its final rename is
    atomic.
    """
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock_path = KEY_FILE.with_suffix(KEY_FILE.suffix + ".lock")
    lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    with os.fdopen(lock_fd, "r+", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        existing = KEY_FILE.read_text(encoding="utf-8") if KEY_FILE.exists() else ""
        new = _upsert_export(existing, var, value)
        written = [var]
        for alias in runtime_aliases(var):
            new = _upsert_export(new, alias, value)
            written.append(alias)
        tmp = KEY_FILE.with_name(f".{KEY_FILE.name}.tmp.{os.getpid()}")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(new)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, KEY_FILE)
            os.chmod(KEY_FILE, 0o600)
        finally:
            if tmp.exists():
                tmp.unlink()
        fcntl.flock(lock, fcntl.LOCK_UN)
    return written


def cmd_add(args):
    if not args:
        print("usage: dkeys add VAR [--stdin]  (value is never accepted in argv)", file=sys.stderr)
        sys.exit(2)
    raw = args[0].strip()
    if "=" in raw:
        print("refusing inline secret: use `dkeys add VAR` or pipe to `dkeys add VAR --stdin`", file=sys.stderr)
        sys.exit(2)
    var = raw
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", var):
        print(f"invalid env var name: {var!r}", file=sys.stderr)
        sys.exit(2)
    options = set(args[1:])
    unknown = options - {"--stdin", "--test"}
    if unknown:
        print("unknown add option(s): " + ", ".join(sorted(unknown)), file=sys.stderr)
        sys.exit(2)
    if "--stdin" in options:
        value = sys.stdin.read().rstrip("\r\n")
    else:
        value = getpass.getpass(f"Paste {var} value (hidden): ").strip()
    if not value or "\x00" in value or "\n" in value or "\r" in value:
        print("empty or multiline values are not accepted", file=sys.stderr)
        sys.exit(2)
    written = _atomic_upsert_key_file(var, value)
    for name in written:
        suffix = "" if name == var else "  (runtime alias — dkeys↔api_keys contract)"
        print(f"wrote export {name} → {KEY_FILE} (value redacted){suffix}")
    if "--test" in options:
        print("running operator-requested live test ...")
        cmd_test([])
    else:
        print("not live-tested; run `dkeys test` when provider calls are intended")


def cmd_path(args):
    print(f"canonical key file:  {KEY_FILE}")
    print(f"  exists: {KEY_FILE.exists()}  mode: {oct(KEY_FILE.stat().st_mode & 0o777) if KEY_FILE.exists() else '—'}")
    print(f"legacy hermes .env:  {HERMES_ENV}")
    print(f"  exists: {HERMES_ENV.exists()}")
    print(f"cache file:          {CACHE_FILE}")
    print(f"  exists: {CACHE_FILE.exists()}")


def cmd_safe_json(args):
    """Emit status/provenance fields only; never masks, values, or lengths."""
    cache = load_cache()
    cached_rows = cache.get("rows", {})
    payload = {
        "schema_version": "dharma.dkeys.safe_status.v1",
        "last_test_ts": cache.get("last_test_ts"),
        "providers": [
            {
                "name": provider["name"],
                "cluster": provider["cluster"],
                "env_var": provider.get("env", ""),
                "glyph": cached_rows.get(provider["name"], {}).get("glyph", "?"),
                "http": cached_rows.get(provider["name"], {}).get("http"),
                "status": cached_rows.get(provider["name"], {}).get("status", "untested"),
            }
            for provider in PROVIDERS
        ],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


def _stored_variable_names() -> set[str]:
    names: set[str] = set()
    for path in (KEY_FILE, HERMES_ENV):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            match = re.match(
                r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=",
                line,
            )
            if match:
                names.add(match.group(1))
    names.update(
        str(provider.get("env") or "")
        for provider in PROVIDERS
        if provider.get("env")
    )
    for first, second in ALIAS_PAIRS:
        names.update((first, second))
    return names


def cmd_exec(args):
    """Replace this process with a child that receives only named key refs."""
    if "--" not in args:
        print("usage: dkeys exec VAR [VAR ...] -- command [args ...]", file=sys.stderr)
        sys.exit(2)
    split = args.index("--")
    requested = args[:split]
    command = args[split + 1 :]
    if not requested or not command:
        print("usage: dkeys exec VAR [VAR ...] -- command [args ...]", file=sys.stderr)
        sys.exit(2)
    for var in requested:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", var):
            print(f"invalid secret reference: {var!r}", file=sys.stderr)
            sys.exit(2)

    resolved = load_env_files()
    missing = [var for var in requested if not resolved.get(var)]
    if missing:
        print("missing requested secret reference(s): " + ", ".join(missing), file=sys.stderr)
        sys.exit(2)

    child_env = dict(os.environ)
    for var in _stored_variable_names():
        child_env.pop(var, None)
    for var in requested:
        child_env[var] = resolved[var]
    os.execvpe(command[0], command, child_env)


def cmd_env(args):
    print(
        "refusing raw secret export; use scripts/load_runtime_env.sh or a scoped process launcher",
        file=sys.stderr,
    )
    sys.exit(2)


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("list", "status", "ls"):
        cmd_list(args[1:])
    elif args[0] == "test":
        cmd_test(args[1:])
    elif args[0] == "find":
        cmd_find(args[1:])
    elif args[0] == "add":
        cmd_add(args[1:])
    elif args[0] == "path":
        cmd_path(args[1:])
    elif args[0] in ("safe-json", "status-json"):
        cmd_safe_json(args[1:])
    elif args[0] == "exec":
        cmd_exec(args[1:])
    elif args[0] == "env":
        cmd_env(args[1:])
    elif args[0] in ("-h", "--help", "help"):
        print(__doc__)
    else:
        print(f"unknown subcommand: {args[0]}\nrun 'dkeys help' for usage", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
