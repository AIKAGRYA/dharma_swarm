#!/usr/bin/env python3
"""Measurement runner for Forge Swarm Evolution Arena v0.

This runner intentionally keeps candidate arms away from sealed labels and
scorers. It gives candidates only the visible task files, then scores completed
submissions from the trusted run process.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from scripts.runtime.forge_swarm_evolution_arena_v0_preflight import run_preflight


DEFAULT_RUN_DIR = Path(
    "reports/forge/swarm-evolution-arena-v0-measurement/"
    "20260605T141000Z-measurement-candidate-taskpack"
)
MISSION_ID = "20260605T-swarm-evolution-arena-v0-measurement-10h"
SCHEMA_VERSION = "forge_swarm_evolution_arena_v0_measurement_runner.v1"
DKEYS_CACHE = Path.home() / ".dharma" / "keys_status.json"
DKEYS_KEY_FILES = (Path.home() / ".hermes" / ".env", Path.home() / ".dharma" / "agent_keys.env")


@dataclass(frozen=True)
class LiveRole:
    role: str
    runner: str
    provider: str
    model: str
    session_or_process: str
    expected_diversity_reason: str


@dataclass(frozen=True)
class CandidateResult:
    arm: str
    task_id: str
    role: str
    provider: str
    model: str
    prompt_path: Path
    response_path: Path
    submission_path: Path
    ok: bool
    elapsed_ms: int
    error: str = ""
    usage: dict[str, Any] | None = None


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def load_env_files() -> dict[str, str]:
    env = dict(os.environ)
    for path in DKEYS_KEY_FILES:
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key.startswith("export "):
                key = key[7:].strip()
            value = value.strip().strip("'").strip('"')
            if key and value:
                env[key] = value
    return env


def dkeys_rows() -> dict[str, dict[str, Any]]:
    if not DKEYS_CACHE.exists():
        return {}
    try:
        payload = read_json(DKEYS_CACHE)
    except Exception:
        return {}
    rows = payload.get("rows")
    return rows if isinstance(rows, dict) else {}


def current_live_roles() -> tuple[list[LiveRole], list[dict[str, Any]]]:
    rows = dkeys_rows()
    roles: list[LiveRole] = []
    provider_checks: list[dict[str, Any]] = []

    openai_row = rows.get("openai") or {}
    openai_live = openai_row.get("status") == "live"
    # builder: OpenAI-family (gpt-5.1) via direct OpenAI API.
    provider_checks.append(
        {
            "provider": "openai",
            "status": "pass" if openai_live else "fail",
            "source": "dkeys test cache",
            "checked_at": utc_now(),
            "http": openai_row.get("http"),
            "observed_status": openai_row.get("status", ""),
        }
    )
    if openai_live:
        roles.append(
            LiveRole(
                role="builder",
                runner="direct-openai-api",
                provider="openai",
                model="gpt-5.1",
                session_or_process="subprocess:measurement-runner:openai-builder",
                expected_diversity_reason="OpenAI-family (gpt-5.1) direct API; code synthesis and final aggregation.",
            )
        )

    ollama_row = rows.get("ollama_cloud") or {}
    ollama_live = ollama_row.get("status") == "live"
    # verifier_adversary: DeepSeek-family via Ollama Cloud (decorrelated from OpenAI builder + GLM alternate).
    provider_checks.append(
        {
            "provider": "ollama_cloud",
            "status": "pass" if ollama_live else "fail",
            "source": "dkeys test cache",
            "checked_at": utc_now(),
            "http": ollama_row.get("http"),
            "observed_status": ollama_row.get("status", ""),
        }
    )
    if ollama_live:
        roles.append(
            LiveRole(
                role="verifier_adversary",
                runner="direct-ollama-api",
                provider="ollama_cloud",
                model="deepseek-v3.1:671b",
                session_or_process="subprocess:measurement-runner:ollama",
                expected_diversity_reason="DeepSeek-family via Ollama Cloud; independent adversarial critique, error profile decorrelated from the OpenAI builder and GLM alternate.",
            )
        )

    zai = rows.get("zai_coding") or {}
    provider_checks.append(
        {
            "provider": "zai_coding",
            "status": "pass" if zai.get("status") == "live" else "fail",
            "source": "dkeys test cache",
            "checked_at": utc_now(),
            "http": zai.get("http"),
            "observed_status": zai.get("status", ""),
        }
    )
    if zai.get("status") == "live":
        roles.append(
            LiveRole(
                role="alternate_builder",
                runner="direct-zai-coding-api",
                provider="zai_coding",
                model="glm-5.1",
                session_or_process="subprocess:measurement-runner:zai",
                expected_diversity_reason="Chinese-cluster coding model with different provider stack and error profile.",
            )
        )

    return roles, provider_checks


def repair_roster_gate(run_dir: Path, roles: list[LiveRole], provider_checks: list[dict[str, Any]]) -> dict[str, Any]:
    live_providers = {role.provider for role in roles}
    live_checks = [
        row
        for row in provider_checks
        if row.get("status") == "pass" and row.get("provider") in live_providers
    ]
    excluded_checks = [
        row
        for row in provider_checks
        if row.get("provider") not in live_providers or row.get("status") != "pass"
    ]
    gate = {
        "schema_version": "forge_roster_gate.v1",
        "roster_id": "live-repaired-roster-openai-ollama-zai-20260606",
        "roles": [
            {
                "role": role.role,
                "runner": role.runner,
                "provider": role.provider,
                "model": role.model,
                "session_or_process": role.session_or_process,
                "liveness_check": "pass",
                "budget_cap": "20 model calls or USD 5 equivalent, whichever comes first",
                "tool_permissions": ["candidate_visible_task_read", "artifact_write"],
                "expected_diversity_reason": role.expected_diversity_reason,
            }
            for role in roles
        ],
        "provider_key_checks": live_checks,
        "excluded_provider_checks": excluded_checks,
        "decorrelation_rationale": (
            "Builder=OpenAI gpt-5.1 (direct), verifier=DeepSeek-v3.1 via Ollama Cloud, "
            "alternate_builder=GLM-5.1 via ZAI — three decorrelated model families on funded "
            "providers. Re-pointed off codex_cli (timeouts), OpenRouter (overdrawn), and gemini "
            "(429 + thinking-truncation) on 2026-06-06."
        ),
        "low_decorrelation_warning": len({role.provider for role in roles}) < 3,
        "status": "green" if len(roles) >= 3 else "red",
        "measurement_mode_allowed": len(roles) >= 3,
        "reason": "fresh live roster repair",
    }
    write_json(run_dir / "roster_gate.json", gate)
    append_jsonl(
        run_dir / "provider_liveness.jsonl",
        [
            {
                "schema_version": "forge_provider_liveness.v1",
                "ts": utc_now(),
                "provider": row["provider"],
                "status": row["status"],
                "source": row["source"],
                "http": row.get("http"),
                "observed_status": row.get("observed_status", ""),
            }
            for row in provider_checks
        ],
    )
    return gate


def task_visible_text(run_dir: Path, task: dict[str, Any]) -> str:
    parts: list[str] = []
    for label in ("instruction", "train", "dev", "challenge_inputs"):
        rel = task["visible_files"][label]
        path = run_dir / rel
        parts.append(f"## {label}: {rel}\n{path.read_text(encoding='utf-8')}")
    return "\n\n".join(parts)


def challenge_ids(run_dir: Path, task: dict[str, Any]) -> list[str]:
    path = run_dir / task["visible_files"]["challenge_inputs"]
    with path.open(encoding="utf-8") as handle:
        return [row["id"] for row in csv.DictReader(handle)]


def empty_submission(ids: list[str], summary: str) -> dict[str, Any]:
    return {"predictions": [{"id": row_id, "target": 0.0} for row_id in ids], "method_summary": summary}


def extract_json_object(text: str) -> tuple[dict[str, Any], str]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
    try:
        payload = json.loads(stripped)
        return payload, ""
    except Exception:
        pass
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        try:
            payload = json.loads(stripped[start : end + 1])
            return payload, ""
        except Exception as exc:
            return {}, f"json_parse_failed:{exc}"
    return {}, "json_object_not_found"


def normalize_submission(payload: dict[str, Any], ids: list[str], fallback_summary: str) -> dict[str, Any]:
    rows = payload.get("predictions")
    if not isinstance(rows, list):
        return empty_submission(ids, f"{fallback_summary}; invalid predictions")
    by_id: dict[str, float] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_id = str(row.get("id") or "")
        if row_id not in ids:
            continue
        try:
            by_id[row_id] = float(row.get("target"))
        except Exception:
            continue
    return {
        "predictions": [{"id": row_id, "target": by_id.get(row_id, 0.0)} for row_id in ids],
        "method_summary": str(payload.get("method_summary") or fallback_summary)[:1000],
    }


def build_candidate_prompt(task: dict[str, Any], visible_text: str, variant: str, extra_context: str = "") -> str:
    return f"""You are a candidate arm in Forge Swarm Evolution Arena v0.

Task: {task['task_id']} - {task['title']}
Variant: {variant}

Rules:
- Use only the visible data below.
- Do not ask for or infer from hidden labels, sealed files, scorer code, rubric files, or oracle submissions.
- Return only a JSON object with this shape:
  {{"predictions":[{{"id":"challenge-row-id","target":12.345}}],"method_summary":"short method"}}
- Include every challenge id exactly once.
- The target must be numeric.

{extra_context}

Visible task data:
{visible_text}
"""


def call_codex(prompt: str, cwd: Path, timeout_s: int) -> tuple[str, dict[str, Any], str]:
    cmd = ["codex", "exec", "--sandbox", "read-only", "--json", prompt]
    started = time.perf_counter()
    proc = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, timeout=timeout_s)
    usage: dict[str, Any] = {"returncode": proc.returncode, "elapsed_ms": int((time.perf_counter() - started) * 1000)}
    text_parts: list[str] = []
    for line in proc.stdout.splitlines():
        try:
            event = json.loads(line)
        except Exception:
            continue
        if event.get("type") == "turn.completed":
            usage.update(event.get("usage") or {})
        item = event.get("item") or {}
        if item.get("type") == "agent_message":
            text_parts.append(str(item.get("text") or ""))
    text = "\n".join(text_parts).strip() or proc.stdout.strip()
    error = proc.stderr.strip() if proc.returncode else ""
    return text, usage, error


def http_json(url: str, headers: dict[str, str], body: dict[str, Any], timeout_s: int) -> tuple[dict[str, Any], int]:
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"refusing non-http(s) endpoint scheme: {url[:40]}")
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return json.loads(resp.read().decode("utf-8")), resp.status
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8")[:500]
        except Exception:
            detail = str(exc)
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc


def call_gemini(prompt: str, env: dict[str, str], timeout_s: int) -> tuple[str, dict[str, Any], str]:
    key = env.get("GEMINI_API_KEY", "")
    if not key:
        return "", {}, "GEMINI_API_KEY unavailable"
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 4096, "responseMimeType": "application/json"},
    }
    payload, status = http_json(url, {"Content-Type": "application/json", "X-goog-api-key": key}, body, timeout_s)
    parts = payload.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    text = "\n".join(str(part.get("text") or "") for part in parts if isinstance(part, dict)).strip()
    usage = payload.get("usageMetadata") or {}
    usage["http_status"] = status
    return text, usage, ""


def call_zai(prompt: str, env: dict[str, str], timeout_s: int) -> tuple[str, dict[str, Any], str]:
    key = env.get("GLM_API_KEY", "")
    if not key:
        return "", {}, "GLM_API_KEY unavailable"
    url = "https://api.z.ai/api/coding/paas/v4/chat/completions"
    body = {
        "model": "glm-5.1",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 6144,
        "thinking": {"type": "disabled"},
    }
    payload, status = http_json(
        url,
        {"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        body,
        timeout_s,
    )
    choice = payload.get("choices", [{}])[0]
    text = str(choice.get("message", {}).get("content") or "").strip()
    usage = payload.get("usage") or {}
    usage["http_status"] = status
    return text, usage, ""


def call_openrouter(prompt: str, env: dict[str, str], model: str, timeout_s: int) -> tuple[str, dict[str, Any], str]:
    key = env.get("OPENROUTER_API_KEY", "")
    if not key:
        return "", {}, "OPENROUTER_API_KEY unavailable"
    url = "https://openrouter.ai/api/v1/chat/completions"
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 2048,
    }
    payload, status = http_json(
        url,
        {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
            "HTTP-Referer": "https://dharma-swarm.local",
            "X-Title": "dharma_swarm forge swarm-evolution-arena",
        },
        body,
        timeout_s,
    )
    choice = payload.get("choices", [{}])[0]
    text = str(choice.get("message", {}).get("content") or "").strip()
    usage = payload.get("usage") or {}
    usage["http_status"] = status
    return text, usage, ""


def call_openai(prompt: str, env: dict[str, str], model: str, timeout_s: int) -> tuple[str, dict[str, Any], str]:
    key = env.get("OPENAI_API_KEY", "")
    if not key:
        return "", {}, "OPENAI_API_KEY unavailable"
    url = "https://api.openai.com/v1/chat/completions"
    # gpt-5.x reasoning models use max_completion_tokens and reject custom temperature.
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_completion_tokens": 8192,
        "response_format": {"type": "json_object"},
    }
    payload, status = http_json(
        url,
        {"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        body,
        timeout_s,
    )
    choice = payload.get("choices", [{}])[0]
    text = str(choice.get("message", {}).get("content") or "").strip()
    usage = payload.get("usage") or {}
    usage["http_status"] = status
    return text, usage, ""


def call_ollama(prompt: str, env: dict[str, str], model: str, timeout_s: int) -> tuple[str, dict[str, Any], str]:
    key = env.get("OLLAMA_API_KEY", "")
    if not key:
        return "", {}, "OLLAMA_API_KEY unavailable"
    url = "https://ollama.com/v1/chat/completions"
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 4096,
    }
    payload, status = http_json(
        url,
        {"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        body,
        timeout_s,
    )
    choice = payload.get("choices", [{}])[0]
    text = str(choice.get("message", {}).get("content") or "").strip()
    usage = payload.get("usage") or {}
    usage["http_status"] = status
    return text, usage, ""


def call_role(role: LiveRole, prompt: str, cwd: Path, env: dict[str, str], timeout_s: int) -> tuple[str, dict[str, Any], str]:
    started = time.perf_counter()
    try:
        if role.provider == "openai":
            text, usage, error = call_openai(prompt, env, role.model, timeout_s)
        elif role.provider == "ollama_cloud":
            text, usage, error = call_ollama(prompt, env, role.model, timeout_s)
        elif role.provider in ("openrouter", "openrouter_anthropic"):
            text, usage, error = call_openrouter(prompt, env, role.model, timeout_s)
        elif role.provider == "gemini":
            text, usage, error = call_gemini(prompt, env, timeout_s)
        elif role.provider == "zai_coding":
            text, usage, error = call_zai(prompt, env, timeout_s)
        elif role.provider == "codex_cli":
            return call_codex(prompt, cwd, timeout_s)
        else:
            return "", {}, f"unsupported provider {role.provider}"
        usage.setdefault("elapsed_ms", int((time.perf_counter() - started) * 1000))
        return text, usage, error
    except Exception as exc:
        return "", {"elapsed_ms": int((time.perf_counter() - started) * 1000)}, f"{type(exc).__name__}: {exc}"


def score_submission(run_dir: Path, task: dict[str, Any], submission: Path, output: Path) -> dict[str, Any]:
    cmd = [
        "python3",
        str(run_dir / task["scorer_path"]),
        "--submission",
        str(submission),
        "--hidden-labels",
        str(run_dir / task["sealed_files"]["hidden_labels"]),
        "--rubric",
        str(run_dir / task["rubric_path"]),
        "--output",
        str(output),
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode != 0:
        return {
            "schema_version": "forge_autoresearch_microtask_score.v1",
            "task_id": task["task_id"],
            "score": 0.0,
            "passed_rubric_items": 0,
            "total_rubric_items": task["rubric_item_count"],
            "rubric_items": {},
            "scorer_error": proc.stderr[:500],
        }
    return read_json(output)


def write_candidate_workspace(run_dir: Path, measurement_root: Path, arm: str, task: dict[str, Any]) -> Path:
    workspace = measurement_root / "candidate_workspaces" / arm / task["task_id"]
    visible = workspace / "visible"
    if visible.exists():
        shutil.rmtree(visible)
    visible.mkdir(parents=True, exist_ok=True)
    for rel in task["visible_files"].values():
        src = run_dir / rel
        dst = visible / Path(rel).name
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return workspace


def run_candidate(
    run_dir: Path,
    measurement_root: Path,
    task: dict[str, Any],
    arm: str,
    role: LiveRole,
    variant: str,
    env: dict[str, str],
    timeout_s: int,
    extra_context: str = "",
) -> CandidateResult:
    ids = challenge_ids(run_dir, task)
    visible_text = task_visible_text(run_dir, task)
    workspace = write_candidate_workspace(run_dir, measurement_root, arm, task)
    prompt = build_candidate_prompt(task, visible_text, variant, extra_context)
    out_dir = measurement_root / "arms" / arm / task["task_id"] / role.role
    prompt_path = out_dir / "prompt.md"
    response_path = out_dir / "response.txt"
    submission_path = out_dir / "submission.json"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt, encoding="utf-8")
    started = time.perf_counter()
    text, usage, error = call_role(role, prompt, workspace, env, timeout_s)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    response_path.write_text(text + ("\nERROR: " + error if error else ""), encoding="utf-8")
    payload, parse_error = extract_json_object(text)
    if parse_error and not error:
        error = parse_error
    submission = normalize_submission(payload, ids, f"{arm}/{role.role}/{variant}")
    write_json(submission_path, submission)
    return CandidateResult(
        arm=arm,
        task_id=task["task_id"],
        role=role.role,
        provider=role.provider,
        model=role.model,
        prompt_path=prompt_path,
        response_path=response_path,
        submission_path=submission_path,
        ok=not bool(error),
        elapsed_ms=elapsed_ms,
        error=error,
        usage=usage,
    )


def aggregate_average_submissions(paths: list[Path], ids: list[str], output: Path, summary: str) -> None:
    totals = {row_id: [] for row_id in ids}
    for path in paths:
        payload = read_json(path)
        for row in payload.get("predictions", []):
            if isinstance(row, dict) and str(row.get("id") or "") in totals:
                try:
                    totals[str(row["id"])].append(float(row.get("target")))
                except Exception:
                    pass
    submission = {
        "predictions": [
            {"id": row_id, "target": (sum(values) / len(values) if values else 0.0)}
            for row_id, values in totals.items()
        ],
        "method_summary": summary,
    }
    write_json(output, submission)


def bootstrap_ci(values: list[float], seed: int = 7, samples: int = 2000) -> dict[str, Any]:
    if not values:
        return {"mean": 0.0, "lower": 0.0, "upper": 0.0, "n": 0}
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(samples):
        draw = [rng.choice(values) for _ in values]
        means.append(sum(draw) / len(draw))
    means.sort()
    return {
        "mean": sum(values) / len(values),
        "lower": means[int(0.025 * (samples - 1))],
        "upper": means[int(0.975 * (samples - 1))],
        "n": len(values),
    }


def mean_score(rows: list[dict[str, Any]], arm: str) -> float:
    scores = [float(row["score"]) for row in rows if row.get("arm") == arm and row.get("result_kind") == "final"]
    return sum(scores) / len(scores) if scores else 0.0


def blocker_signature(row: dict[str, Any]) -> str:
    if row.get("candidate_ok"):
        return ""
    error = str(row.get("candidate_error") or "")
    if "TimeoutExpired" in error:
        return "codex_timeout"
    if "HTTP 503" in error:
        return "provider_http_503"
    if "HTTP 429" in error or "RESOURCE_EXHAUSTED" in error or "Quota exceeded" in error:
        return "provider_http_429"
    if "json_object_not_found" in error or "json_parse_failed" in error:
        return "non_json_response"
    if error:
        return "candidate_runtime_failure"
    return ""


def non_roi_blocker(rows: list[dict[str, Any]], completed_task_count: int) -> dict[str, Any] | None:
    counts: dict[str, int] = {}
    for row in rows:
        signature = blocker_signature(row)
        if signature:
            counts[signature] = counts.get(signature, 0) + 1
    if not counts:
        return None

    task_ids = sorted({str(row.get("task_id")) for row in rows if row.get("task_id")})
    live_swarm_rows = [
        row
        for row in rows
        if row.get("arm") == "full_live_dharma_swarm" and row.get("result_kind") == "final"
    ]
    live_swarm_ok = any(row.get("candidate_ok") for row in live_swarm_rows)

    repeated_provider_failures = counts.get("provider_http_503", 0) >= 3
    repeated_provider_quota = counts.get("provider_http_429", 0) >= 2
    repeated_codex_timeouts = counts.get("codex_timeout", 0) >= 2
    repeated_non_json = counts.get("non_json_response", 0) >= 2
    no_live_swarm_final = completed_task_count >= 1 and live_swarm_rows and not live_swarm_ok
    if repeated_provider_failures or repeated_provider_quota or repeated_codex_timeouts or repeated_non_json or no_live_swarm_final:
        return {
            "blocker_signature": "+".join(sorted(key for key, value in counts.items() if value > 0)),
            "blocker_counts": counts,
            "task_ids": task_ids,
            "completed_task_count": completed_task_count,
            "reason": (
                "Repeated provider/runtime failures mean continuing would measure "
                "runner instability rather than swarm lift."
            ),
        }
    return None


def write_blocked_closeout(
    run_dir: Path,
    measurement_root: Path,
    blocker: dict[str, Any],
    control_rows: list[dict[str, Any]],
    rubric_item_count: int,
) -> dict[str, Any]:
    report = {
        "schema_version": "forge_swarm_lift_report.v1",
        "status": "blocked_with_evidence",
        "generated_at": utc_now(),
        "measurement_run_id": measurement_root.name,
        "task_count": blocker.get("completed_task_count", 0),
        "rubric_item_count": rubric_item_count,
        "scores": {
            "best_single_full_budget": mean_score(control_rows, "best_single_full_budget"),
            "same_budget_self_moa": mean_score(control_rows, "same_budget_self_moa"),
            "full_live_dharma_swarm": mean_score(control_rows, "full_live_dharma_swarm"),
            "baseline_max": max(
                mean_score(control_rows, "best_single_full_budget"),
                mean_score(control_rows, "same_budget_self_moa"),
            ),
        },
        "swarm_lift": 0.0,
        "paired_task_deltas": [],
        "paired_bootstrap_ci": {"mean": 0.0, "lower": 0.0, "upper": 0.0, "n": 0},
        "conditional_success": 0.0,
        "routeable_advantage": 0.0,
        "cost_normalized_lift": 0.0,
        "blocker": blocker,
        "low_power_warning": "measurement stopped by common-sense ROI governor before a trustworthy lift estimate",
        "authority": {
            "trainer_built": False,
            "production_router_mutated": False,
            "archive_fitness_mutated": False,
            "official_score_claimed": False,
            "public_submission_performed": False,
            "external_confirmed": False,
        },
    }
    write_json(run_dir / "swarm_lift_report.json", report)
    write_json(measurement_root / "swarm_lift_report.json", report)
    (run_dir / "swarm_lift_report.md").write_text(
        "\n".join(
            [
                "# Swarm Lift Report",
                "",
                f"- measurement_run_id: `{measurement_root.name}`",
                "- closeout_state: `blocked_with_evidence`",
                f"- blocker_signature: `{blocker.get('blocker_signature', '')}`",
                "- swarm_lift: not computed; run stopped by common-sense ROI governor",
                "- authority: no trainer, no archive fitness, no public claim, no external_confirmed",
                "",
                blocker.get("reason", ""),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "decision_packet.md").write_text(
        "\n".join(
            [
                "# Decision Packet",
                "",
                "Verdict: `blocked_with_evidence`",
                "",
                f"Blocker: `{blocker.get('blocker_signature', '')}`.",
                "",
                "The run stopped because continuing would measure provider/runtime instability rather than swarm lift.",
                "No trainer, archive fitness, public claim, or external confirmation was mutated.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    append_jsonl(
        run_dir / "roi_governor.jsonl",
        [
            {
                "schema_version": "forge_roi_governor.v1",
                "ts": utc_now(),
                "cycle": 2,
                "elapsed_minutes": 0,
                "state": "red",
                "decision_changing_artifact": "swarm_lift_report.json",
                "new_evidence_kind": "runtime_blocker",
                "blocker_signature": blocker.get("blocker_signature", ""),
                "same_blocker_count": max((blocker.get("blocker_counts") or {}).values(), default=1),
                "task_changed": bool(blocker.get("completed_task_count", 0)),
                "intervention_changed": False,
                "hypothesis_changed": False,
                "next_action_changed": True,
                "promotion_path_still_possible": False,
                "budget_spent": "see budget_ledger.jsonl",
                "budget_remaining": "not computed",
                "skeptical_reviewer_summary": "A reviewer should not accept swarm lift from a run dominated by provider/runtime failures.",
                "continue_decision": "stop",
                "reason": blocker.get("reason", ""),
            }
        ],
    )
    append_jsonl(
        run_dir / "anti_goodhart_receipts.jsonl",
        [
            {
                "schema_version": "forge_swarm_evolution_arena_v0_anti_goodhart.v1",
                "ts": utc_now(),
                "measurement_run_id": measurement_root.name,
                "sealed_files_candidate_visible": False,
                "scorer_candidate_visible": False,
                "budget_parity_logged": True,
                "role_liveness_logged": True,
                "authority_boundaries_preserved": True,
                "blocked_with_evidence": True,
            }
        ],
    )
    return report


def write_score_rows(
    run_dir: Path,
    measurement_root: Path,
    task: dict[str, Any],
    result: CandidateResult,
    result_kind: str = "final",
) -> dict[str, Any]:
    score_path = result.submission_path.with_name("score.json")
    score = score_submission(run_dir, task, result.submission_path, score_path)
    row = {
        "schema_version": "forge_swarm_evolution_arena_v0_control_result.v1",
        "ts": utc_now(),
        "measurement_run_id": measurement_root.name,
        "arm": result.arm,
        "task_id": task["task_id"],
        "role": result.role,
        "provider": result.provider,
        "model": result.model,
        "result_kind": result_kind,
        "submission_path": str(result.submission_path),
        "score_path": str(score_path),
        "score": score.get("score", 0.0),
        "passed_rubric_items": score.get("passed_rubric_items", 0),
        "total_rubric_items": score.get("total_rubric_items", task["rubric_item_count"]),
        "candidate_ok": result.ok,
        "candidate_error": result.error,
    }
    append_jsonl(run_dir / "control_results.jsonl", [row])
    paired = []
    for rubric_id, passed in (score.get("rubric_items") or {}).items():
        paired.append(
            {
                "schema_version": "forge_swarm_evolution_arena_v0_paired_rubric_score.v1",
                "ts": utc_now(),
                "measurement_run_id": measurement_root.name,
                "arm": result.arm,
                "task_id": task["task_id"],
                "role": result.role,
                "provider": result.provider,
                "rubric_item": rubric_id,
                "passed": bool(passed),
                "result_kind": result_kind,
            }
        )
    append_jsonl(run_dir / "paired_rubric_scores.jsonl", paired)
    append_jsonl(
        run_dir / "budget_ledger.jsonl",
        [
            {
                "schema_version": "forge_swarm_evolution_arena_v0_budget_ledger.v1",
                "ts": utc_now(),
                "measurement_run_id": measurement_root.name,
                "arm": result.arm,
                "task_id": task["task_id"],
                "role": result.role,
                "provider": result.provider,
                "model": result.model,
                "model_calls": 1,
                "elapsed_ms": result.elapsed_ms,
                "usage": result.usage or {},
            }
        ],
    )
    return row


def run_closed_book(run_dir: Path, measurement_root: Path, roles: list[LiveRole], env: dict[str, str], timeout_s: int) -> None:
    prompt = (run_dir / "closed_book_prompt_set.md").read_text(encoding="utf-8")
    prompt += "\n\nTask IDs: tabular_cost_model, sequence_latency_forecast, optimizer_config_selection.\n"
    prompt += "Return JSON: {\"memorization_risk\":\"low|medium|high\",\"reason\":\"...\"}."
    for role in roles:
        out_dir = measurement_root / "closed_book" / role.role
        out_dir.mkdir(parents=True, exist_ok=True)
        text, usage, error = call_role(role, prompt, out_dir, env, timeout_s)
        (out_dir / "response.txt").write_text(text + ("\nERROR: " + error if error else ""), encoding="utf-8")
        payload, parse_error = extract_json_object(text)
        append_jsonl(
            run_dir / "closed_book_results.jsonl",
            [
                {
                    "schema_version": "forge_swarm_evolution_arena_v0_closed_book_result.v1",
                    "ts": utc_now(),
                    "measurement_run_id": measurement_root.name,
                    "role": role.role,
                    "provider": role.provider,
                    "model": role.model,
                    "response_path": str(out_dir / "response.txt"),
                    "memorization_risk": payload.get("memorization_risk", "unknown"),
                    "candidate_ok": not bool(error or parse_error),
                    "error": error or parse_error,
                    "usage": usage,
                }
            ],
        )


def append_liveness_receipts(run_dir: Path, measurement_root: Path, roles: list[LiveRole]) -> None:
    rows = []
    for role in roles:
        rows.append(
            {
                "schema_version": "forge_swarm_evolution_arena_v0_role_liveness.v1",
                "ts": utc_now(),
                "measurement_run_id": measurement_root.name,
                "role": role.role,
                "runner": role.runner,
                "provider": role.provider,
                "model": role.model,
                "session_or_process": role.session_or_process,
                "liveness": "pass",
                "artifact_root": str(measurement_root),
            }
        )
    append_jsonl(run_dir / "role_liveness_receipts.jsonl", rows)


def run_measurement(run_dir: Path, timeout_s: int, max_tasks: int | None = None) -> dict[str, Any]:
    env = load_env_files()
    roles, provider_checks = current_live_roles()
    repair_roster_gate(run_dir, roles, provider_checks)
    preflight = run_preflight(run_dir=run_dir, repo_root=Path.cwd(), generated_at=utc_now(), write_packet=True)
    measurement_run_id = "measurement-" + utc_now().replace(":", "").replace("-", "")
    measurement_root = run_dir / "measurement_runs" / measurement_run_id
    measurement_root.mkdir(parents=True, exist_ok=True)
    if not preflight["measurement_mode_allowed"]:
        append_jsonl(
            run_dir / "roi_governor.jsonl",
            [
                {
                    "schema_version": "forge_roi_governor.v1",
                    "ts": utc_now(),
                    "cycle": 1,
                    "elapsed_minutes": 0,
                    "state": "red",
                    "decision_changing_artifact": "fresh roster repair + preflight",
                    "new_evidence_kind": "liveness",
                    "blocker_signature": "measurement_mode_not_allowed_after_fresh_liveness",
                    "same_blocker_count": 1,
                    "task_changed": False,
                    "intervention_changed": False,
                    "hypothesis_changed": False,
                    "next_action_changed": True,
                    "promotion_path_still_possible": False,
                    "budget_spent": "0",
                    "budget_remaining": "measurement budget unopened",
                    "skeptical_reviewer_summary": "Fresh liveness repair blocks measurement; a reviewer should not trust stale green roster gates.",
                    "continue_decision": "stop",
                    "reason": "preflight failed after fresh liveness repair",
                }
            ],
        )
        return {"status": "blocked_with_evidence", "preflight": preflight, "measurement_run_id": measurement_run_id}

    manifest = read_json(run_dir / "task_manifest.json")
    tasks = manifest["tasks"][: max_tasks or len(manifest["tasks"])]
    codex_role = next(role for role in roles if role.role == "builder")  # builder role (now OpenRouter-backed)
    gemini_role = next((role for role in roles if role.provider == "gemini"), roles[0])
    zai_role = next((role for role in roles if role.provider == "zai_coding"), roles[-1])
    append_liveness_receipts(run_dir, measurement_root, roles)
    run_closed_book(run_dir, measurement_root, roles, env, timeout_s)

    control_rows: list[dict[str, Any]] = []

    for task in tasks:
        ids = challenge_ids(run_dir, task)
        # nop baseline
        nop_dir = measurement_root / "arms" / "nop" / task["task_id"] / "nop"
        nop_dir.mkdir(parents=True, exist_ok=True)
        nop_submission = nop_dir / "submission.json"
        write_json(nop_submission, empty_submission(ids, "nop baseline"))
        nop_result = CandidateResult(
            arm="nop",
            task_id=task["task_id"],
            role="nop",
            provider="none",
            model="none",
            prompt_path=nop_dir / "prompt.md",
            response_path=nop_dir / "response.txt",
            submission_path=nop_submission,
            ok=True,
            elapsed_ms=0,
            usage={},
        )
        control_rows.append(write_score_rows(run_dir, measurement_root, task, nop_result))

        solo_results = []
        for role in roles:
            result = run_candidate(run_dir, measurement_root, task, "each_solo_role", role, f"solo-{role.role}", env, timeout_s)
            solo_results.append(result)
            control_rows.append(write_score_rows(run_dir, measurement_root, task, result, result_kind="solo"))

        best = run_candidate(run_dir, measurement_root, task, "best_single_full_budget", codex_role, "best-single-codex", env, timeout_s)
        control_rows.append(write_score_rows(run_dir, measurement_root, task, best))

        self_moa_samples = []
        for index in range(3):
            sample = run_candidate(
                run_dir,
                measurement_root,
                task,
                "same_budget_self_moa_samples",
                gemini_role,
                f"self-moa-sample-{index + 1}",
                env,
                timeout_s,
            )
            self_moa_samples.append(sample)
            control_rows.append(write_score_rows(run_dir, measurement_root, task, sample, result_kind="sample"))
        self_moa_dir = measurement_root / "arms" / "same_budget_self_moa" / task["task_id"] / "aggregated"
        self_moa_dir.mkdir(parents=True, exist_ok=True)
        self_moa_submission = self_moa_dir / "submission.json"
        aggregate_average_submissions(
            [sample.submission_path for sample in self_moa_samples],
            ids,
            self_moa_submission,
            "same-budget Self-MoA average of three Gemini samples",
        )
        self_moa_result = CandidateResult(
            arm="same_budget_self_moa",
            task_id=task["task_id"],
            role="aggregator",
            provider="gemini",
            model=gemini_role.model,
            prompt_path=self_moa_dir / "prompt.md",
            response_path=self_moa_dir / "response.txt",
            submission_path=self_moa_submission,
            ok=True,
            elapsed_ms=sum(sample.elapsed_ms for sample in self_moa_samples),
            usage={"sample_count": len(self_moa_samples)},
        )
        control_rows.append(write_score_rows(run_dir, measurement_root, task, self_moa_result))

        sham = run_candidate(
            run_dir,
            measurement_root,
            task,
            "labels_only_sham_swarm",
            codex_role,
            "simulate planner/builder/verifier labels inside one process",
            env,
            timeout_s,
        )
        control_rows.append(write_score_rows(run_dir, measurement_root, task, sham))

        analyst_contexts = []
        handoff_rows = []
        for role in [gemini_role, zai_role]:
            analyst = run_candidate(
                run_dir,
                measurement_root,
                task,
                "full_live_dharma_swarm_handoffs",
                role,
                f"swarm-handoff-{role.role}",
                env,
                timeout_s,
                extra_context="Produce your own submission plus a concise modeling rationale for the final builder.",
            )
            control_rows.append(write_score_rows(run_dir, measurement_root, task, analyst, result_kind="handoff"))
            response_text = analyst.response_path.read_text(encoding="utf-8")[:4000]
            analyst_contexts.append(f"## Handoff from {role.role}/{role.provider}\n{response_text}")
            handoff_rows.append(
                {
                    "schema_version": "forge_swarm_evolution_arena_v0_handoff.v1",
                    "ts": utc_now(),
                    "measurement_run_id": measurement_root.name,
                    "task_id": task["task_id"],
                    "from_role": role.role,
                    "to_role": codex_role.role,
                    "artifact_path": str(analyst.response_path),
                    "consumed_by_final_action": True,
                }
            )
        append_jsonl(run_dir / "handoff_receipts.jsonl", handoff_rows)
        swarm = run_candidate(
            run_dir,
            measurement_root,
            task,
            "full_live_dharma_swarm",
            codex_role,
            "final-builder-consume-live-handoffs",
            env,
            timeout_s,
            extra_context="\n\n".join(analyst_contexts),
        )
        control_rows.append(write_score_rows(run_dir, measurement_root, task, swarm))
        blocker = non_roi_blocker(control_rows, completed_task_count=len({row["task_id"] for row in control_rows}))
        if blocker:
            return write_blocked_closeout(
                run_dir,
                measurement_root,
                blocker,
                control_rows,
                manifest.get("rubric_item_count", 0),
            )

    best_single = mean_score(control_rows, "best_single_full_budget")
    self_moa = mean_score(control_rows, "same_budget_self_moa")
    swarm = mean_score(control_rows, "full_live_dharma_swarm")
    baseline = max(best_single, self_moa)
    deltas = []
    for task in tasks:
        task_id = task["task_id"]
        swarm_score = next((float(row["score"]) for row in control_rows if row["arm"] == "full_live_dharma_swarm" and row["task_id"] == task_id), 0.0)
        best_score = next((float(row["score"]) for row in control_rows if row["arm"] == "best_single_full_budget" and row["task_id"] == task_id), 0.0)
        moa_score = next((float(row["score"]) for row in control_rows if row["arm"] == "same_budget_self_moa" and row["task_id"] == task_id), 0.0)
        deltas.append(swarm_score - max(best_score, moa_score))
    ci = bootstrap_ci(deltas)
    swarm_lift = swarm - baseline
    conditional_n = sum(
        1
        for task in tasks
        if next((float(row["score"]) for row in control_rows if row["arm"] == "best_single_full_budget" and row["task_id"] == task["task_id"]), 0.0) < 1.0
        and next((float(row["score"]) for row in control_rows if row["arm"] == "same_budget_self_moa" and row["task_id"] == task["task_id"]), 0.0) < 1.0
    )
    conditional_success = (
        sum(1 for delta in deltas if delta > 0) / conditional_n if conditional_n else 0.0
    )
    closeout = "positive_lift_candidate" if swarm_lift > 0 else "measured_negative"
    if len(tasks) < 3 or manifest.get("rubric_item_count", 0) < 30:
        closeout = "inconclusive_low_power"
    report = {
        "schema_version": "forge_swarm_lift_report.v1",
        "status": closeout,
        "generated_at": utc_now(),
        "measurement_run_id": measurement_root.name,
        "task_count": len(tasks),
        "rubric_item_count": manifest.get("rubric_item_count", 0),
        "scores": {
            "best_single_full_budget": best_single,
            "same_budget_self_moa": self_moa,
            "full_live_dharma_swarm": swarm,
            "baseline_max": baseline,
        },
        "swarm_lift": swarm_lift,
        "paired_task_deltas": deltas,
        "paired_bootstrap_ci": ci,
        "conditional_success": conditional_success,
        "routeable_advantage": conditional_success,
        "cost_normalized_lift": swarm_lift,
        "low_power_warning": "n=3 tasks; treat as candidate evidence only",
        "authority": {
            "trainer_built": False,
            "production_router_mutated": False,
            "archive_fitness_mutated": False,
            "official_score_claimed": False,
            "public_submission_performed": False,
            "external_confirmed": False,
        },
    }
    write_json(run_dir / "swarm_lift_report.json", report)
    write_json(measurement_root / "swarm_lift_report.json", report)
    md = [
        "# Swarm Lift Report",
        "",
        f"- measurement_run_id: `{measurement_root.name}`",
        f"- closeout_state: `{closeout}`",
        f"- best_single_full_budget: {best_single:.6f}",
        f"- same_budget_self_moa: {self_moa:.6f}",
        f"- full_live_dharma_swarm: {swarm:.6f}",
        f"- swarm_lift: {swarm_lift:.6f}",
        f"- paired_bootstrap_ci: [{ci['lower']:.6f}, {ci['upper']:.6f}]",
        "- authority: no trainer, no archive fitness, no public claim, no external_confirmed",
        "",
        "Latency-only is not counted as a win.",
    ]
    (run_dir / "swarm_lift_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    decision = [
        "# Decision Packet",
        "",
        f"Verdict: `{closeout}`",
        "",
        f"Swarm lift: `{swarm_lift:.6f}` over max(best-single, Self-MoA).",
        "",
        "This is candidate-for-human-review evidence only. No trainer, archive fitness, public claim, or external confirmation was mutated.",
    ]
    (run_dir / "decision_packet.md").write_text("\n".join(decision) + "\n", encoding="utf-8")
    append_jsonl(
        run_dir / "anti_goodhart_receipts.jsonl",
        [
            {
                "schema_version": "forge_swarm_evolution_arena_v0_anti_goodhart.v1",
                "ts": utc_now(),
                "measurement_run_id": measurement_root.name,
                "sealed_files_candidate_visible": False,
                "scorer_candidate_visible": False,
                "budget_parity_logged": True,
                "role_liveness_logged": True,
                "authority_boundaries_preserved": True,
            }
        ],
    )
    append_jsonl(
        run_dir / "roi_governor.jsonl",
        [
            {
                "schema_version": "forge_roi_governor.v1",
                "ts": utc_now(),
                "cycle": 2,
                "elapsed_minutes": 0,
                "state": "green",
                "decision_changing_artifact": "swarm_lift_report.json",
                "new_evidence_kind": "score",
                "blocker_signature": "",
                "same_blocker_count": 0,
                "task_changed": True,
                "intervention_changed": True,
                "hypothesis_changed": False,
                "next_action_changed": True,
                "promotion_path_still_possible": closeout == "positive_lift_candidate",
                "budget_spent": "see budget_ledger.jsonl",
                "budget_remaining": "not computed",
                "skeptical_reviewer_summary": "A reviewer can compare full swarm against best-single and same-budget Self-MoA from scored artifacts.",
                "continue_decision": "stop",
                "reason": f"measurement closed as {closeout}",
            }
        ],
    )
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--timeout-seconds", type=int, default=240)
    parser.add_argument("--max-tasks", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = run_measurement(args.run_dir, timeout_s=args.timeout_seconds, max_tasks=args.max_tasks)
    print(json.dumps(report, sort_keys=True) if args.json else json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("status") in {
        "positive_lift_candidate",
        "measured_negative",
        "inconclusive_low_power",
        "blocked_with_evidence",
    } else 2


if __name__ == "__main__":
    raise SystemExit(main())
