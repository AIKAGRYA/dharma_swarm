#!/usr/bin/env python3
"""Capability profiling loop (v0).

Drives a fleet agent's real engine across a small task battery, scores each
output with a DECORRELATED judge (never the same engine), aggregates per-category
means into a capability profile, and persists via the EXISTING telemetry plane
(agent_reward_ledger + agent_reputation) plus a human-readable JSON.

Re-runnable for any agent: parameterize --agent-id / --engine / engine-api flags.
v0 default target: qwen_code / deepseek-v4-pro.

Persistence uses dharma_swarm.telemetry_plane:
  - TelemetryPlaneStore.record_reward_entry()   (telemetry_plane.py:725)
  - TelemetryPlaneStore.upsert_agent_reputation() (telemetry_plane.py:779)
No new table or ledger is created.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from dharma_swarm.telemetry_plane import (  # noqa: E402
    AgentReputationRecord,
    AgentRewardLedgerEntry,
    TelemetryPlaneStore,
)

QWEN_SETTINGS = Path.home() / ".qwen" / "settings.json"
KEYS_ENV = Path.home() / ".dharma" / "agent_keys.env"


class KeychainError(RuntimeError):
    """A `security find-generic-password` call failed for a non-not-found reason
    (e.g. access denied), as opposed to the item simply being absent."""

# --- real dharma_swarm snippets (verbatim from the tree, cited) ---------------
SNIP_JSON = (
    "def _json_dump(value):\n"
    "    return json.dumps(value, sort_keys=True, ensure_ascii=True)\n\n"
    "def _json_load(raw, fallback):\n"
    "    if not raw:\n"
    "        return fallback\n"
    "    try:\n"
    "        return json.loads(raw)\n"
    "    except Exception:\n"
    "        return fallback\n"
)  # telemetry_plane.py:219-230
SNIP_DENSITY = (
    "def density(self):\n"
    "    if not self._marks_file.exists():\n"
    "        return 0\n"
    "    count = 0\n"
    "    with open(self._marks_file, 'r') as f:\n"
    "        for line in f:\n"
    "            if line.strip():\n"
    "                count += 1\n"
    "    return count\n"
)  # stigmergy.py:394
# A real-shaped snippet with GENUINE duplication for the refactor task:
# three near-identical blocks differing only in field name + threshold.
SNIP_DUP = (
    "def classify(metrics):\n"
    "    results = {}\n"
    "    if metrics.get('cpu') is not None:\n"
    "        v = metrics['cpu']\n"
    "        if v > 90:\n"
    "            results['cpu'] = 'critical'\n"
    "        elif v > 70:\n"
    "            results['cpu'] = 'warn'\n"
    "        else:\n"
    "            results['cpu'] = 'ok'\n"
    "    if metrics.get('mem') is not None:\n"
    "        v = metrics['mem']\n"
    "        if v > 90:\n"
    "            results['mem'] = 'critical'\n"
    "        elif v > 70:\n"
    "            results['mem'] = 'warn'\n"
    "        else:\n"
    "            results['mem'] = 'ok'\n"
    "    if metrics.get('disk') is not None:\n"
    "        v = metrics['disk']\n"
    "        if v > 90:\n"
    "            results['disk'] = 'critical'\n"
    "        elif v > 70:\n"
    "            results['disk'] = 'warn'\n"
    "        else:\n"
    "            results['disk'] = 'ok'\n"
    "    return results\n"
)
# A real-shaped buggy snippet (off-by-one + mutparg) for debugging.
SNIP_BUGGY = (
    "def moving_average(values, window=3, acc=[]):\n"
    "    out = []\n"
    "    for i in range(len(values)):\n"
    "        chunk = values[i:i+window]\n"
    "        out.append(sum(chunk) / window)\n"
    "    acc.append(out)\n"
    "    return out\n"
)

# --- task battery: ~6 categories, 1-2 tasks each ------------------------------
BATTERY = [
    ("code_review",
     "Review this Python function for correctness, edge cases, and style. "
     "Give the top 3 concrete issues or improvements:\n\n" + SNIP_DENSITY),
    ("code_review",
     "Review this pair of helpers. Note any robustness, typing, or API-design "
     "concerns in <=4 bullet points:\n\n" + SNIP_JSON),
    ("refactor",
     "Refactor this for clarity and to remove duplication. Return only the "
     "improved code:\n\n" + SNIP_DUP),
    ("test_authoring",
     "Write a focused pytest test suite (3-5 cases incl. edge cases) for this "
     "function. Return only the test code:\n\n" + SNIP_DENSITY),
    ("debugging",
     "This function has bugs. Identify each bug precisely and give the corrected "
     "version:\n\n" + SNIP_BUGGY),
    ("debugging",
     "A user reports `density()` always returns 0 even though the marks file has "
     "lines. Given the code below, list the 3 most likely root causes ranked by "
     "probability:\n\n" + SNIP_DENSITY),
    ("summarization",
     "Summarize what this code does in exactly 2 sentences, precisely and "
     "without speculation:\n\n" + SNIP_JSON),
    ("reasoning",
     "A task board has 12 tasks. 3 fail and auto-retry once; 1 of those retries "
     "fails permanently. Each success emits 2 stigmergy marks, each permanent "
     "failure emits 1. How many marks total? Show your reasoning, then give the "
     "final number on its own line."),
]

JUDGE_RUBRIC = (
    "You are a strict, fair senior-engineer judge. Score the ANSWER to the TASK "
    "from 0 to 100 on: correctness, completeness, and usefulness for the stated "
    "category. 0=wrong/empty, 50=partially useful, 80=solid, 100=expert. "
    "Penalize empty, hand-wavy, or off-task answers hard. "
    'Respond with ONLY compact JSON: {"score": <int 0-100>, "rationale": "<one sentence>"}'
)


def _extract_engine_key(engine_base: str) -> str:
    """Resolve the engine (DeepSeek) API key with provider scoping.

    Order of precedence:
      1. DEEPSEEK_API_KEY env var (explicit, unambiguous).
      2. settings.json scoped to the provider whose baseUrl matches engine_base:
         read that provider's ``envKey`` and resolve it from settings["env"].
      3. settings["env"]["DEEPSEEK_API_KEY"] as a direct fallback.

    Avoids the prior bug where a bare ``sk-...`` regex over the whole file could
    grab a non-DeepSeek key (OpenAI/Anthropic keys also start with ``sk-``).
    """
    env_direct = os.environ.get("DEEPSEEK_API_KEY")
    if env_direct:
        return env_direct.strip()

    try:
        cfg = json.loads(QWEN_SETTINGS.read_text())
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"Cannot read {QWEN_SETTINGS}: {e}") from e

    env_map = cfg.get("env", {}) or {}
    host = urllib.parse.urlsplit(engine_base.rstrip("/")).netloc or engine_base

    # Find the provider whose baseUrl host matches the engine base; use its envKey.
    for provider_list in (cfg.get("modelProviders", {}) or {}).values():
        for prov in provider_list or []:
            base = (prov.get("baseUrl") or "").rstrip("/")
            if base and urllib.parse.urlsplit(base).netloc == host:
                env_key = prov.get("envKey")
                if env_key and env_map.get(env_key):
                    return str(env_map[env_key]).strip()

    # Direct fallback: the canonical DeepSeek env slot in settings.json.
    if env_map.get("DEEPSEEK_API_KEY"):
        return str(env_map["DEEPSEEK_API_KEY"]).strip()

    raise RuntimeError(
        f"No DeepSeek key found: set DEEPSEEK_API_KEY env var, or add it to "
        f"{QWEN_SETTINGS} under env / a provider matching {host}"
    )


def _auth_ping(base: str, key: str) -> None:
    """Cheap auth check against the engine base BEFORE running the battery.

    Sends a 1-token chat request. Treats HTTP 401/403 as a hard auth failure
    (fail fast). 4xx other than auth (e.g. 400 bad-request) means the key was
    accepted by auth, so we let it pass. 5xx / connection errors are transient
    and must not block a valid key, so they pass too (the retrying battery
    handles them).
    """
    payload = {
        "model": "deepseek-v4-pro",
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    data = json.dumps(payload).encode("utf-8")
    url = base.rstrip("/") + "/chat/completions"
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"refusing non-http(s) endpoint scheme: {url[:40]}")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30):
            return
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            body = ""
            try:
                body = e.read().decode()[:160]
            except Exception:  # noqa: BLE001
                pass
            raise RuntimeError(
                f"engine auth failed (HTTP {e.code}) at {url}: {body}"
            ) from e
        # Non-auth HTTP error: auth itself was accepted; let the battery proceed.
        return
    except (urllib.error.URLError, OSError):
        # Transient/connection issue at ping time — don't block a valid key.
        return


def _load_env_key(name: str) -> str | None:
    if KEYS_ENV.exists():
        for line in KEYS_ENV.read_text().splitlines():
            line = line.strip()
            if line.startswith("export "):
                line = line[len("export "):]
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    import os
    return os.environ.get(name)


def _post_json(url: str, payload: dict, headers: dict, timeout: int = 90,
               attempts: int = 3, backoff: float = 1.5) -> dict:
    """POST JSON with a small retry on transient failures.

    Retries on 5xx HTTP errors and connection/URL errors with exponential
    backoff. 4xx (incl. auth) is non-transient and raised immediately.
    """
    data = json.dumps(payload).encode("utf-8")
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"refusing non-http(s) endpoint scheme: {url[:40]}")
    last_exc: Exception | None = None
    for attempt in range(attempts):
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code >= 500:
                last_exc = e
            else:
                raise  # 4xx (auth, bad request) — not transient
        except (urllib.error.URLError, OSError) as e:  # connection/timeout
            last_exc = e
        if attempt < attempts - 1:
            time.sleep(backoff * (2 ** attempt))
    assert last_exc is not None
    raise last_exc


# --- engine: OpenAI-compatible chat/completions (DeepSeek) --------------------
def call_engine(base: str, key: str, model: str, prompt: str,
                max_tokens: int, usage_acc: dict) -> str:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.2,
        # NOTE: enable_thinking deliberately OMITTED. With it on, the model
        # spends the entire token budget on reasoning_tokens and returns "".
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    d = _post_json(base.rstrip("/") + "/chat/completions", payload, headers)
    u = d.get("usage", {}) or {}
    usage_acc["calls"] += 1
    usage_acc["prompt_tokens"] += int(u.get("prompt_tokens", 0))
    usage_acc["completion_tokens"] += int(u.get("completion_tokens", 0))
    usage_acc["total_tokens"] += int(u.get("total_tokens", 0))
    msg = d.get("choices", [{}])[0].get("message", {}) or {}
    content = msg.get("content") or ""
    # deepseek-v4-pro is an always-on reasoning model: it emits thinking into
    # reasoning_content and final answer into content. If the budget was too
    # small, content can be empty while reasoning_content holds a (truncated)
    # answer — harvest it as a defensive fallback rather than scoring as empty.
    if not content.strip():
        content = msg.get("reasoning_content") or ""
    return content


# --- judge: GLM-4.6 via z.ai coding endpoint (decorrelated from DeepSeek) -----
def call_judge(key: str, category: str, task: str, answer: str,
               usage_acc: dict) -> tuple[int, str]:
    user = (
        f"CATEGORY: {category}\n\nTASK:\n{task}\n\nANSWER:\n{answer if answer.strip() else '(empty answer)'}"
    )
    payload = {
        "model": "glm-4.6",
        "messages": [
            {"role": "system", "content": JUDGE_RUBRIC},
            {"role": "user", "content": user},
        ],
        "max_tokens": 400,  # GLM burns reasoning tokens; leave room for JSON
        "temperature": 0,
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    d = _post_json(
        "https://api.z.ai/api/coding/paas/v4/chat/completions", payload, headers
    )
    u = d.get("usage", {}) or {}
    usage_acc["calls"] += 1
    usage_acc["prompt_tokens"] += int(u.get("prompt_tokens", 0))
    usage_acc["completion_tokens"] += int(u.get("completion_tokens", 0))
    usage_acc["total_tokens"] += int(u.get("total_tokens", 0))
    raw = (d.get("choices", [{}])[0].get("message", {}) or {}).get("content", "") or ""
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return 0, f"unparseable judge output: {raw[:80]!r}"
    try:
        obj = json.loads(m.group(0))
        score = int(round(float(obj.get("score", 0))))
        score = max(0, min(100, score))
        return score, str(obj.get("rationale", ""))[:200]
    except Exception as e:  # noqa: BLE001
        return 0, f"judge json error: {e}: {raw[:80]!r}"


# --- hardened multi-judge panel (fully decorrelated from DeepSeek) ------------
# Each judge is an independent provider cluster. None is DeepSeek; the preferred
# set is non-"chinese_cluster" (Anthropic via Max CLI, OpenAI, NVIDIA) so the
# aggregate score is a genuinely independent read, not a same-family echo.
def _parse_score_json(raw: str) -> tuple[int, str]:
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return -1, f"unparseable: {raw[:80]!r}"
    try:
        obj = json.loads(m.group(0))
        score = int(round(float(obj.get("score", 0))))
        return max(0, min(100, score)), str(obj.get("rationale", ""))[:200]
    except Exception as e:  # noqa: BLE001
        return -1, f"json error: {e}: {raw[:80]!r}"


def _judge_user_msg(category: str, task: str, answer: str) -> str:
    return (
        f"CATEGORY: {category}\n\nTASK:\n{task}\n\n"
        f"ANSWER:\n{answer if answer.strip() else '(empty answer)'}"
    )


def judge_openai_compat(base: str, key: str, model: str,
                        category: str, task: str, answer: str,
                        usage_acc: dict) -> tuple[int, str]:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": JUDGE_RUBRIC},
            {"role": "user", "content": _judge_user_msg(category, task, answer)},
        ],
        "max_tokens": 400,
        "temperature": 0,
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    d = _post_json(base, payload, headers)
    u = d.get("usage", {}) or {}
    usage_acc["calls"] += 1
    usage_acc["prompt_tokens"] += int(u.get("prompt_tokens", 0))
    usage_acc["completion_tokens"] += int(u.get("completion_tokens", 0))
    usage_acc["total_tokens"] += int(u.get("total_tokens", 0))
    raw = (d.get("choices", [{}])[0].get("message", {}) or {}).get("content", "") or ""
    return _parse_score_json(raw)


def judge_claude_max(category: str, task: str, answer: str,
                     usage_acc: dict) -> tuple[int, str]:
    """Judge via the operator's Claude Max subscription (no API key, free,
    Anthropic cluster — fully decorrelated). Shells `claude -p` with a CLEAN
    env so it uses the Max sub, not the credit-dead ANTHROPIC_API_KEY."""
    import os
    import subprocess

    prompt = JUDGE_RUBRIC + "\n\n" + _judge_user_msg(category, task, answer)
    env = {k: v for k, v in os.environ.items()
           if k not in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "ANTHROPIC_API_KEY")}
    claude_bin = os.path.expanduser("~/.npm-global/bin/claude")
    if not os.path.exists(claude_bin):
        claude_bin = "claude"
    proc = subprocess.run(
        [claude_bin, "-p", prompt],
        capture_output=True, text=True, env=env, timeout=120,
    )
    usage_acc["calls"] += 1
    raw = (proc.stdout or "").strip()
    if proc.returncode != 0 and not raw:
        return -1, f"claude_max exit {proc.returncode}: {(proc.stderr or '')[:80]!r}"
    return _parse_score_json(raw)


def _median(xs: list[int]) -> float:
    xs = sorted(xs)
    n = len(xs)
    if n == 0:
        return 0.0
    mid = n // 2
    return float(xs[mid]) if n % 2 else (xs[mid - 1] + xs[mid]) / 2.0


def panel_score(judges: list[str], keys: dict, category: str, task: str,
                answer: str, usage: dict) -> tuple[int, str, dict]:
    """Run every requested judge; aggregate valid scores by MEDIAN (robust to a
    single outlier or a transient judge failure). Returns
    (aggregate_int, combined_rationale, per_judge_dict)."""
    per: dict[str, dict] = {}
    valid: list[int] = []
    for j in judges:
        ua = usage.setdefault(j, {"calls": 0, "prompt_tokens": 0,
                                  "completion_tokens": 0, "total_tokens": 0})
        try:
            if j == "claude_max":
                s, r = judge_claude_max(category, task, answer, ua)
            elif j == "openai":
                s, r = judge_openai_compat(
                    "https://api.openai.com/v1/chat/completions",
                    keys["openai"], keys.get("openai_model", "gpt-4o-mini"),
                    category, task, answer, ua)
            elif j == "nvidia":
                s, r = judge_openai_compat(
                    "https://integrate.api.nvidia.com/v1/chat/completions",
                    keys["nvidia"], keys.get("nvidia_model", "meta/llama-3.1-70b-instruct"),
                    category, task, answer, ua)
            elif j == "glm":
                s, r = call_judge(keys["glm"], category, task, answer, ua)
            else:
                s, r = -1, f"unknown judge {j}"
        except Exception as e:  # noqa: BLE001
            s, r = -1, f"{type(e).__name__}: {str(e)[:80]}"
        per[j] = {"score": s, "rationale": r}
        if s >= 0:
            valid.append(s)
    agg = int(round(_median(valid))) if valid else 0
    rat = " | ".join(f"{j}={per[j]['score']}" for j in judges)
    return agg, rat, per


async def persist(store: TelemetryPlaneStore, agent_id: str, engine: str,
                  judge_label: str, run_id: str, results: list[dict],
                  per_cat: dict, overall: float) -> None:
    # one reward entry per task
    for i, r in enumerate(results):
        entry = AgentRewardLedgerEntry(
            entry_id=f"capprobe_{run_id}_{i:02d}",
            agent_id=agent_id,
            reward_type="capability_probe",
            amount=float(r["score"]),
            unit="points",
            session_id=run_id,
            task_id=f"{r['category']}_{i:02d}",
            run_id=run_id,
            reason=r["category"],
            metadata={
                "category": r["category"],
                "engine": engine,
                "judge": judge_label,
                "rationale": r["rationale"],
            },
        )
        await store.record_reward_entry(entry)
    # rolling reputation with per-category breakdown
    band = "high" if overall >= 75 else "medium" if overall >= 50 else "low"
    rep = AgentReputationRecord(
        agent_id=agent_id,
        reputation=round(overall, 2),
        trust_band=band,
        last_reason=f"capability_probe {run_id}: overall {overall:.1f}/100 ({engine}, judge={judge_label})",
        evidence=[{
            "run_id": run_id,
            "engine": engine,
            "judge": judge_label,
            "overall": round(overall, 2),
            "per_category": {k: round(v, 2) for k, v in per_cat.items()},
            "n_tasks": len(results),
        }],
    )
    await store.upsert_agent_reputation(rep)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent-id", default="qwen_code")
    ap.add_argument("--engine", default="deepseek-v4-pro")
    ap.add_argument("--engine-base", default="https://api.deepseek.com")
    ap.add_argument("--engine-model", default="deepseek-v4-pro")
    ap.add_argument("--max-tokens", type=int, default=3000)
    ap.add_argument("--judge-label", default="glm-4.6")
    # Hardened multi-judge panel. Comma-list of: claude_max,openai,nvidia,glm.
    # Default is the fully-decorrelated (non-DeepSeek, non-chinese_cluster) panel.
    ap.add_argument("--judges", default="",
                    help="comma list of judges (claude_max,openai,nvidia,glm); "
                         "if set, overrides single GLM judge")
    args = ap.parse_args()

    run_id = f"capprofile_{int(time.time())}"
    try:
        engine_key = _extract_engine_key(args.engine_base)
    except Exception as e:  # noqa: BLE001
        print(f"BLOCKER: engine key: {e}", file=sys.stderr)
        return 2

    # Validate the engine key with one cheap auth ping BEFORE the battery, so a
    # wrong/expired key fails fast with a clear message instead of mid-run.
    try:
        _auth_ping(args.engine_base, engine_key)
    except Exception as e:  # noqa: BLE001
        print(f"BLOCKER: {e}", file=sys.stderr)
        return 2

    panel = [j.strip() for j in args.judges.split(",") if j.strip()]

    def _kc(svc: str) -> str | None:
        """Read a key from the macOS keychain, distinguishing failure modes.

        Returns the key on success, ``None`` only when the item genuinely does
        not exist (exit 44). Raises KeychainError with an actionable message for
        access-denied (exit 36/51) and any other failure (surfacing stderr), so
        a permissions prompt isn't silently misreported as "no key".
        """
        import subprocess
        try:
            proc = subprocess.run(
                ["security", "find-generic-password", "-s", svc, "-w"],
                capture_output=True, text=True)
        except FileNotFoundError as e:  # `security` not on PATH
            raise KeychainError(f"`security` not available: {e}") from e
        rc = proc.returncode
        if rc == 0:
            return proc.stdout.strip() or None
        if rc == 44:  # errSecItemNotFound — genuinely absent
            return None
        if rc in (36, 51):  # access denied / interaction not allowed
            raise KeychainError(
                f"keychain access denied for '{svc}' (exit {rc}): re-run and "
                f"click Allow when macOS prompts for keychain access")
        raise KeychainError(
            f"keychain error for '{svc}' (exit {rc}): "
            f"{(proc.stderr or '').strip()[:160]}")

    keys: dict = {}
    if panel:
        try:
            if "openai" in panel:
                keys["openai"] = _load_env_key("OPENAI_API_KEY") or _kc("openai-api-key")
                if not keys["openai"]:
                    print("BLOCKER: openai judge requested but no key", file=sys.stderr)
                    return 2
            if "nvidia" in panel:
                keys["nvidia"] = (_load_env_key("NVIDIA_NIM_API_KEY")
                                  or _load_env_key("NVIDIA_API_KEY")
                                  or _kc("nvidia-nim-api-key") or _kc("nim-api-key"))
                if not keys["nvidia"]:
                    print("BLOCKER: nvidia judge requested but no key", file=sys.stderr)
                    return 2
            if "glm" in panel:
                keys["glm"] = _load_env_key("GLM_API_KEY")
                if not keys["glm"]:
                    print("BLOCKER: glm judge requested but no key", file=sys.stderr)
                    return 2
        except KeychainError as e:
            print(f"BLOCKER: {e}", file=sys.stderr)
            return 2
        judge_label = "+".join(panel) + " (median panel)"
    else:
        keys["glm"] = _load_env_key("GLM_API_KEY")
        if not keys["glm"]:
            print("BLOCKER: GLM_API_KEY (judge) not found", file=sys.stderr)
            return 2
        panel = ["glm"]
        judge_label = args.judge_label

    eng_usage = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    jdg_usage: dict = {}
    results: list[dict] = []

    print(f"[run {run_id}] agent={args.agent_id} engine={args.engine} judges={judge_label}")
    for i, (cat, prompt) in enumerate(BATTERY):
        print(f"  [{i+1}/{len(BATTERY)}] {cat} ... ", end="", flush=True)
        try:
            ans = call_engine(args.engine_base, engine_key, args.engine_model,
                              prompt, args.max_tokens, eng_usage)
        except urllib.error.HTTPError as e:
            # Persistent after retries; skip this task rather than abort the run.
            body = ""
            try:
                body = e.read().decode()[:120]
            except Exception:  # noqa: BLE001
                pass
            print(f"ENGINE HTTP {e.code}: {body} -- skipping task")
            continue
        except Exception as e:  # noqa: BLE001
            print(f"ENGINE ERROR: {e} -- skipping task")
            continue
        score, rationale, per_judge = panel_score(
            panel, keys, cat, prompt, ans, jdg_usage)
        print(f"score={score}  [{rationale}]  ({len(ans)} chars)")
        results.append({"category": cat, "score": score, "rationale": rationale,
                        "per_judge": per_judge, "answer_chars": len(ans)})

    if not results:
        # Empty battery or every task skipped — degrade gracefully, persist
        # nothing, and signal failure rather than crash on a divide-by-zero.
        print("\nNo task results produced (empty battery or all tasks failed); "
              "nothing to persist.", file=sys.stderr)
        return 3

    per_cat: dict[str, float] = {}
    by_cat: dict[str, list[int]] = {}
    for r in results:
        by_cat.setdefault(r["category"], []).append(r["score"])
    for cat, scores in by_cat.items():
        per_cat[cat] = (sum(scores) / len(scores)) if scores else 0.0
    overall = (sum(r["score"] for r in results) / len(results)) if results else 0.0

    store = TelemetryPlaneStore()
    asyncio.run(persist(store, args.agent_id, args.engine, judge_label,
                        run_id, results, per_cat, overall))

    jdg_calls = sum(u.get("calls", 0) for u in jdg_usage.values())
    jdg_tokens = sum(u.get("total_tokens", 0) for u in jdg_usage.values())
    profile = {
        "agent_id": args.agent_id,
        "callsign": "qwen-code" if args.agent_id == "qwen_code" else args.agent_id,
        "engine": args.engine,
        "judge": judge_label,
        "judge_panel": panel,
        "aggregation": "median",
        "run_id": run_id,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "overall": round(overall, 2),
        "per_category": {k: round(v, 2) for k, v in sorted(per_cat.items(), key=lambda kv: -kv[1])},
        "n_tasks": len(results),
        "tasks": results,
        "cost": {
            "engine": eng_usage,
            "judge_per_backend": jdg_usage,
            "total_calls": eng_usage["calls"] + jdg_calls,
            "total_tokens": eng_usage["total_tokens"] + jdg_tokens,
        },
    }
    out_dir = Path.home() / ".dharma" / "agents" / args.agent_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "capability_profile.json"
    out_path.write_text(json.dumps(profile, indent=2))

    print("\n=== CAPABILITY PROFILE ===")
    print(f"overall: {overall:.1f}/100")
    for cat, v in sorted(per_cat.items(), key=lambda kv: -kv[1]):
        print(f"  {cat:16s} {v:5.1f}")
    print(f"engine calls={eng_usage['calls']} tokens={eng_usage['total_tokens']} | "
          f"judge calls={jdg_calls} tokens={jdg_tokens} (panel={'+'.join(panel)})")
    print(f"profile -> {out_path}")
    print(f"run_id  -> {run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
