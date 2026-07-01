"""Deterministic Forge packet guard with optional NVIDIA/NIM critic.

The guard is a receipt battery around an already-emitted Forge packet.  It never
runs grades, mutates archive fitness, mutates routers, or makes public claims.
The deterministic review is primary; the NVIDIA/NIM critic is optional and
decorrelated.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import time
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from dharma_swarm.model_hierarchy import default_model
from dharma_swarm.models import ProviderType

SCHEMA_VERSION = "forge_v2.packet_guard.v1"
DEFAULT_MODEL = default_model(ProviderType.NVIDIA_NIM)
DEFAULT_OUT_NAME = "nvidia_guard_review.json"
DEFAULT_MD_NAME = "nvidia_guard_review.md"
DEFAULT_PREREGISTERED_MDE = 0.056
MIN_CONFIRM_N = 500
MIN_EFFECT = 0.05

VALID_CLOSEOUT_STATES = {
    "positive_lift_candidate",
    "measured_negative",
    "inconclusive_low_power",
    "contaminated_quarantine",
    "blocked_with_evidence",
    "invalid_budget",
    "dry_run",
}

REQUIRED_PACKET_FILES = (
    "run_manifest.json",
    "task_manifest.jsonl",
    "model_roster.json",
    "budget_ledger.jsonl",
    "coordination_edges.jsonl",
    "results.jsonl",
    "control_comparison.md",
    "failure_taxonomy.md",
    "decision_record.md",
)

MUTATION_FLAGS = (
    "trainer_built",
    "production_router_mutated",
    "archive_fitness_mutated",
    "official_score_claimed",
    "public_submission_performed",
    "external_confirmed",
)

SUPERIORITY_PATTERNS = (
    "beats the best single model",
    "swarm beats",
    "dharma swarm beats",
    "superior to best single",
    "outperforms the best single",
)

CANONICAL_CONTROL_ARM_ALIASES = {
    "frontier_single_full_budget": {"frontier_single_full_budget", "best_single_full_budget"},
    "best_of_n_same_model": {"best_of_n_same_model"},
    "same_budget_self_moa": {"same_budget_self_moa", "self_moa"},
    "planner_builder_verifier_no_a2a": {"planner_builder_verifier_no_a2a", "labels_only_sham_swarm"},
    "full_a2a_swarm": {"full_a2a_swarm", "full_live_dharma_swarm"},
}


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    message: str
    evidence: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "evidence": self.evidence,
        }


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {"_non_object_json": data}


def read_jsonl(path: Path, *, max_rows: int = 50_000) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError:
            row = {"_parse_error": stripped[:300]}
        rows.append(row if isinstance(row, dict) else {"_non_object_json": row})
        if len(rows) >= max_rows:
            break
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def sha256_path(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    return sha256(path.read_bytes()).hexdigest()


def extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, flags=re.S)
        if not match:
            raise
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("expected JSON object")
    return data


def _canonical_files(packet_dir: Path) -> dict[str, dict[str, Any]]:
    return {
        name: {"exists": (packet_dir / name).exists(), "sha256": sha256_path(packet_dir / name)}
        for name in REQUIRED_PACKET_FILES
    }


def _scheduler_report(packet_dir: Path, run_manifest: dict[str, Any], result_rows: list[dict[str, Any]]) -> dict[str, Any]:
    decision = read_json(packet_dir / "decision_record.json")
    campaigns_raw = decision.get("campaigns")
    campaigns = [row for row in campaigns_raw if isinstance(row, dict)] if isinstance(campaigns_raw, list) else []
    task_ids = {
        str(row.get("task_id") or row.get("instance_id") or "")
        for row in result_rows
        if row.get("task_id") or row.get("instance_id")
    }
    if not task_ids:
        for row in campaigns:
            task_ids.update(str(item) for item in row.get("instances", []) or [] if item)
    last_closeout = (
        run_manifest.get("status")
        or decision.get("last_closeout")
        or next((row.get("closeout") for row in reversed(campaigns) if row.get("closeout")), "")
    )
    lift_rows = [
        row.get("lift")
        for row in campaigns
        if isinstance(row, dict) and isinstance(row.get("lift"), dict)
    ]
    last_lift = next((row for row in reversed(lift_rows) if row), {})
    return {
        "schema_version": "forge_v2_scheduler_packet_guard.v1",
        "status": last_closeout,
        "task_count": safe_int(run_manifest.get("task_count"), len({task for task in task_ids if task})),
        "rubric_item_count": 0,
        "swarm_lift": safe_float(last_lift.get("mean"), 0.0),
        "paired_bootstrap_ci": last_lift or {"lower": 0.0, "upper": 0.0, "n": safe_int(run_manifest.get("task_count"))},
        "authority": run_manifest.get("authority") or {},
        "taskbed_allocation": run_manifest.get("taskbed_allocation"),
    }


def collect_packet(packet_dir: Path) -> dict[str, Any]:
    packet_dir = packet_dir.expanduser().resolve()
    run_manifest = read_json(packet_dir / "run_manifest.json")
    task_rows = read_jsonl(packet_dir / "task_manifest.jsonl")
    model_roster = read_json(packet_dir / "model_roster.json")
    budget_rows = read_jsonl(packet_dir / "budget_ledger.jsonl")
    edge_rows = read_jsonl(packet_dir / "coordination_edges.jsonl")
    result_rows = read_jsonl(packet_dir / "results.jsonl")
    run_report = read_json(packet_dir / "swarm_lift_report.json")
    if not run_report:
        measurement_reports = sorted(packet_dir.glob("measurement_runs/*/swarm_lift_report.json"))
        if measurement_reports:
            run_report = read_json(measurement_reports[-1])
    if not run_report and run_manifest:
        run_report = _scheduler_report(packet_dir, run_manifest, result_rows)
    decision_text = ""
    for name in ("decision_record.md", "decision_packet.md"):
        path = packet_dir / name
        if path.exists():
            decision_text = path.read_text(encoding="utf-8", errors="replace")[:12000]
            break
    return {
        "packet_dir": str(packet_dir),
        "run_manifest": run_manifest,
        "task_manifest_rows": task_rows,
        "model_roster": model_roster,
        "budget_rows": budget_rows,
        "coordination_edges": edge_rows,
        "result_rows": result_rows,
        "run_report": run_report,
        "decision_text": decision_text,
        "files": _canonical_files(packet_dir),
    }


def task_count(packet: dict[str, Any]) -> int:
    report = packet.get("run_report") or {}
    if report.get("task_count") is not None:
        return safe_int(report.get("task_count"))
    rows = packet.get("task_manifest_rows") or []
    if rows:
        return len(rows)
    return len({str(row.get("task_id") or row.get("instance_id") or "") for row in packet.get("result_rows") or []})


def closeout_state(packet: dict[str, Any]) -> str:
    report = packet.get("run_report") or {}
    state = str(report.get("status") or "").strip()
    if state:
        return state
    text = str(packet.get("decision_text") or "")
    for candidate in VALID_CLOSEOUT_STATES:
        if candidate in text:
            return candidate
    return ""


def arms_present(packet: dict[str, Any]) -> set[str]:
    arms: set[str] = set()
    for row in packet.get("result_rows") or []:
        arm = str(row.get("arm") or row.get("control_arm") or row.get("topology") or "").strip()
        if arm:
            arms.add(arm)
    roster = packet.get("model_roster") or {}
    for key in ("arms", "control_arms", "routes"):
        value = roster.get(key)
        if not isinstance(value, list):
            continue
        for item in value:
            if isinstance(item, dict):
                arm = str(item.get("arm") or item.get("name") or "").strip()
                if arm:
                    arms.add(arm)
            elif item:
                arms.add(str(item))
    return arms


def canonical_arm_coverage(arms: set[str]) -> dict[str, bool]:
    return {
        canonical: bool(aliases & arms)
        for canonical, aliases in CANONICAL_CONTROL_ARM_ALIASES.items()
    }


def invalid_run_rate(packet: dict[str, Any]) -> float | None:
    rows = packet.get("result_rows") or []
    if not rows:
        return None
    invalid = 0
    total = 0
    for row in rows:
        if row.get("result_kind") == "sample":
            continue
        total += 1
        status = str(row.get("status") or row.get("result") or "").lower()
        if row.get("candidate_ok") is False or row.get("invalid") is True or status in {"invalid", "failed", "timeout", "error"}:
            invalid += 1
    if total == 0:
        return None
    return invalid / total


def final_use_ratio(packet: dict[str, Any]) -> float | None:
    rows = packet.get("coordination_edges") or []
    if not rows:
        return None
    target = [row for row in rows if row.get("swarm_only_win") or row.get("edge_kind") == "swarm_only_win"] or rows
    if not target:
        return None
    used = sum(
        1
        for row in target
        if row.get("final_use_proof") or row.get("consumed_by_final_action") or row.get("final_incorporated")
    )
    return used / len(target)


def budget_parity(packet: dict[str, Any]) -> dict[str, Any]:
    budgets: dict[str, float] = {}
    for row in packet.get("budget_rows") or []:
        arm = str(row.get("arm") or row.get("control_arm") or "").strip()
        if not arm:
            continue
        amount = row.get("total_tokens") or row.get("tokens") or row.get("budget_tokens") or row.get("cost_usd") or row.get("actual_cost_usd")
        budgets[arm] = budgets.get(arm, 0.0) + safe_float(amount)
    if not budgets:
        return {"status": "missing", "by_arm": {}}
    values = [value for value in budgets.values() if value > 0]
    if len(values) < 2:
        return {"status": "insufficient", "by_arm": budgets}
    ratio = max(values) / min(values)
    return {"status": "pass" if ratio <= 1.10 else "mismatch", "max_to_min_ratio": ratio, "by_arm": budgets}


def claim_requests_superiority(claim_text: str, report: dict[str, Any]) -> bool:
    lowered = claim_text.lower()
    if any(pattern in lowered for pattern in SUPERIORITY_PATTERNS):
        return True
    explicit = report.get("claim_superiority")
    return explicit if isinstance(explicit, bool) else False


def _ci_half_width(ci: dict[str, Any]) -> float:
    return max(0.0, (safe_float(ci.get("upper")) - safe_float(ci.get("lower"))) / 2.0)


def _preregistered_mde(packet: dict[str, Any]) -> float:
    report = packet.get("run_report") or {}
    manifest = packet.get("run_manifest") or {}
    power = report.get("power_receipt") if isinstance(report.get("power_receipt"), dict) else {}
    return safe_float(
        report.get("pre_registered_mde")
        or manifest.get("pre_registered_mde")
        or power.get("pre_registered_mde")
        or power.get("mde"),
        DEFAULT_PREREGISTERED_MDE,
    )


def taskbed_power(packet: dict[str, Any]) -> dict[str, Any]:
    report = packet.get("run_report") or {}
    manifest = packet.get("run_manifest") or {}
    allocation = report.get("taskbed_allocation") or manifest.get("taskbed_allocation") or {}
    if not isinstance(allocation, dict):
        allocation = {}
    split = str(allocation.get("split") or "")
    task_n = safe_int(allocation.get("task_count"), task_count(packet))
    ci = report.get("paired_bootstrap_ci") if isinstance(report.get("paired_bootstrap_ci"), dict) else {}
    mde = _preregistered_mde(packet)
    return {
        "split": split,
        "task_count": task_n,
        "full_confirm": split == "confirm" and task_n >= MIN_CONFIRM_N,
        "no_split_confirm": split == "confirm" and bool(allocation.get("explore_separate_from_confirm", True)),
        "clean_confirm": split != "confirm" or bool(allocation.get("contamination_clean", True)),
        "ci_half_width": _ci_half_width(ci),
        "pre_registered_mde": mde,
    }


def evaluate_deterministic(packet: dict[str, Any], *, claim_text: str = "") -> dict[str, Any]:
    findings: list[Finding] = []
    missing = [name for name, meta in (packet.get("files") or {}).items() if not meta.get("exists")]
    if missing:
        findings.append(Finding("warning", "minimum_packet_incomplete", "Canonical Forge packet files are missing.", missing))

    state = closeout_state(packet)
    if not state:
        findings.append(Finding("error", "closeout_state_missing", "No valid closeout state found.", []))
    elif state not in VALID_CLOSEOUT_STATES:
        findings.append(Finding("error", "closeout_state_invalid", f"Invalid closeout state: {state}", [state]))

    report = packet.get("run_report") or {}
    tasks = task_count(packet)
    ci = report.get("paired_bootstrap_ci") if isinstance(report.get("paired_bootstrap_ci"), dict) else {}
    ci_lower = safe_float(ci.get("lower"))
    swarm_lift = safe_float(report.get("swarm_lift"))
    invalid_rate = invalid_run_rate(packet)
    use_ratio = final_use_ratio(packet)
    parity = budget_parity(packet)
    arms = arms_present(packet)
    coverage = canonical_arm_coverage(arms)
    power = taskbed_power(packet)
    superiority_claim = claim_requests_superiority(claim_text, report)

    if tasks < 3:
        findings.append(Finding("warning", "low_power_under_3_tasks", "Fewer than 3 tasks.", [f"task_count={tasks}"]))
    if tasks < MIN_CONFIRM_N:
        findings.append(Finding("info", "below_e4_confirm_floor", "Fewer than the E4 full CONFIRM task floor.", [f"task_count={tasks}", f"required={MIN_CONFIRM_N}"]))
    if power["split"] == "confirm":
        if not power["full_confirm"]:
            findings.append(Finding("error", "confirm_taskbed_underpowered", "CONFIRM taskbed is below the full E4 floor.", [f"task_count={power['task_count']}"]))
        if not power["no_split_confirm"]:
            findings.append(Finding("error", "confirm_task_previously_explored", "CONFIRM taskbed is not separate from EXPLORE.", []))
        if not power["clean_confirm"]:
            findings.append(Finding("error", "confirm_taskbed_contaminated", "CONFIRM taskbed is not contamination-clean.", []))
    if power["ci_half_width"] > power["pre_registered_mde"]:
        findings.append(
            Finding(
                "error",
                "confirm_power_insufficient",
                "Achieved CI half-width exceeds preregistered MDE.",
                [f"half_width={power['ci_half_width']}", f"mde={power['pre_registered_mde']}"],
            )
        )

    missing_arms = [arm for arm, ok in coverage.items() if not ok]
    if missing_arms:
        findings.append(Finding("warning", "control_arms_incomplete", "Not all canonical control arms are visible.", missing_arms))
    if parity["status"] == "missing":
        findings.append(Finding("warning", "budget_ledger_missing", "No budget ledger rows found.", []))
    elif parity["status"] == "mismatch":
        findings.append(Finding("error", "budget_parity_failed", "Budget parity exceeds 10% max/min tolerance.", [json.dumps(parity["by_arm"], sort_keys=True)]))
    if invalid_rate is None:
        findings.append(Finding("warning", "invalid_run_rate_unknown", "No result rows available to compute invalid-run rate.", []))
    elif invalid_rate >= 0.05:
        findings.append(Finding("error", "invalid_run_rate_too_high", "Invalid-run rate is >= 5%.", [f"invalid_run_rate={invalid_rate:.4f}"]))
    if use_ratio is None:
        findings.append(Finding("warning", "final_use_proof_missing", "No coordination-edge final-use proof found.", []))
    elif use_ratio < 0.30:
        findings.append(Finding("error", "final_use_proof_below_gate", "Final-use proof covers less than 30% of relevant edges.", [f"final_use_ratio={use_ratio:.4f}"]))

    authority = report.get("authority") if isinstance(report.get("authority"), dict) else {}
    mutated = [flag for flag in MUTATION_FLAGS if authority.get(flag) is True]
    if mutated:
        findings.append(Finding("error", "authority_boundary_mutated", "Forbidden authority boundary flag is true.", mutated))
    if state == "positive_lift_candidate" and swarm_lift <= 0:
        findings.append(Finding("error", "positive_lift_without_positive_delta", "Positive closeout without positive lift.", [f"swarm_lift={swarm_lift}"]))

    if superiority_claim:
        claim_blockers: list[str] = []
        if not power["full_confirm"]:
            claim_blockers.append("full_confirm<500")
        if power["ci_half_width"] > power["pre_registered_mde"]:
            claim_blockers.append("ci_half_width>mde")
        if any(not ok for ok in coverage.values()):
            claim_blockers.append("missing_control_arms")
        if ci_lower <= 0:
            claim_blockers.append("ci_lower<=0")
        if swarm_lift < MIN_EFFECT:
            claim_blockers.append("swarm_lift<0.05")
        if invalid_rate is None or invalid_rate >= 0.05:
            claim_blockers.append("invalid_run_rate_missing_or_high")
        if use_ratio is None or use_ratio < 0.30:
            claim_blockers.append("final_use_proof<0.30")
        if claim_blockers:
            findings.append(Finding("error", "superiority_claim_forbidden", "The requested superiority claim fails Forge claim gates.", claim_blockers))

    severities = [finding.severity for finding in findings]
    if "error" in severities:
        verdict = "blocked_with_evidence"
    elif state in {"blocked_with_evidence", "contaminated_quarantine", "invalid_budget"}:
        verdict = state
    elif "warning" in severities or state in {"inconclusive_low_power", "dry_run"}:
        verdict = "revise_protocol"
    else:
        verdict = "pass_for_next_scale"

    return {
        "verdict": verdict,
        "claim_superiority_requested": superiority_claim,
        "closeout_state": state,
        "task_count": tasks,
        "swarm_lift": swarm_lift,
        "paired_ci_lower": ci_lower,
        "invalid_run_rate": invalid_rate,
        "final_use_ratio": use_ratio,
        "budget_parity": parity,
        "arms_present": sorted(arms),
        "canonical_arm_coverage": coverage,
        "taskbed_power": power,
        "findings": [finding.as_dict() for finding in findings],
    }


def compact_packet_summary(packet: dict[str, Any], deterministic: dict[str, Any], *, max_chars: int) -> str:
    summary = {
        "schema_version": SCHEMA_VERSION,
        "packet_dir": packet.get("packet_dir"),
        "deterministic_review": deterministic,
        "run_manifest": packet.get("run_manifest") or {},
        "file_presence": packet.get("files") or {},
        "result_rows_sample": (packet.get("result_rows") or [])[:20],
        "budget_rows_sample": (packet.get("budget_rows") or [])[:20],
        "coordination_edges_sample": (packet.get("coordination_edges") or [])[:20],
        "decision_text_excerpt": str(packet.get("decision_text") or "")[:4000],
    }
    text = json.dumps(summary, indent=2, sort_keys=True, default=str)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n...[truncated {len(text) - max_chars} chars]"


def build_nim_prompt(packet: dict[str, Any], deterministic: dict[str, Any], *, claim_text: str, max_chars: int) -> str:
    return (
        "You are the NVIDIA/NIM external critic lane for Dharma Forge Proving Ground.\n"
        "Return JSON only. Be strict. Deterministic gates are primary.\n\n"
        "Claim under review:\n"
        f"{claim_text or '(no explicit superiority claim)'}\n\n"
        "Packet summary:\n"
        f"{compact_packet_summary(packet, deterministic, max_chars=max_chars)}\n"
    )


async def call_nvidia_nim(prompt: str, *, model: str, timeout_seconds: int, max_tokens: int) -> dict[str, Any]:
    from dharma_swarm.models import LLMRequest
    from dharma_swarm.runtime_provider import create_runtime_provider, resolve_runtime_provider_config

    config = resolve_runtime_provider_config(ProviderType.NVIDIA_NIM, model=model, timeout_seconds=timeout_seconds)
    if not config.available:
        raise RuntimeError("NVIDIA_NIM_API_KEY is not available")
    provider = create_runtime_provider(config)
    request = LLMRequest(
        model=config.default_model or model,
        system="Return JSON only. Do not flatter.",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=max_tokens,
    )
    try:
        response = await provider.complete(request)
        content = str(response.content or "")
        parsed = extract_json_object(content)
        parsed["model_identity"] = {"provider": "nvidia_nim", "model": response.model or model}
        parsed["usage"] = response.usage
        return parsed
    finally:
        close = getattr(provider, "close", None)
        if callable(close):
            result = close()
            if asyncio.iscoroutine(result):
                await result


def render_markdown(review: dict[str, Any]) -> str:
    deterministic = review["deterministic_review"]
    nim = review.get("nvidia_nim_review") or {}
    lines = [
        "# Forge Packet Guard Review",
        "",
        f"- generated_at: `{review['generated_at']}`",
        f"- packet_dir: `{review['packet_dir']}`",
        f"- deterministic_verdict: `{deterministic['verdict']}`",
        f"- closeout_state: `{deterministic.get('closeout_state')}`",
        f"- task_count: `{deterministic.get('task_count')}`",
        f"- invalid_run_rate: `{deterministic.get('invalid_run_rate')}`",
        f"- final_use_ratio: `{deterministic.get('final_use_ratio')}`",
        "",
        "## Deterministic Findings",
        "",
    ]
    findings = deterministic.get("findings") or []
    if not findings:
        lines.append("- none")
    for finding in findings:
        evidence = "; ".join(str(item) for item in finding.get("evidence") or [])
        suffix = f" Evidence: {evidence}" if evidence else ""
        lines.append(f"- `{finding.get('severity')}` `{finding.get('code')}`: {finding.get('message')}{suffix}")
    lines.extend(["", "## NVIDIA/NIM Critic", ""])
    if nim:
        lines.append(f"- verdict: `{nim.get('verdict', '')}`")
        lines.append(f"- claim_allowed: `{nim.get('claim_allowed', '')}`")
        lines.append(f"- summary: {nim.get('summary', '')}")
    else:
        lines.append("- not run")
    lines.extend([
        "",
        "## Authority",
        "",
        "This guard does not run benchmarks, mutate archive fitness, mutate trainers, mutate routers, make public claims, or submit to external benchmarks.",
    ])
    return "\n".join(lines) + "\n"


def run_guard(
    *,
    packet_dir: Path,
    out_dir: Path | None = None,
    claim_text: str = "",
    with_nim: bool = False,
    nim_model: str = DEFAULT_MODEL,
    mock_nim_response_file: Path | None = None,
    timeout_seconds: int = 120,
    max_prompt_chars: int = 14000,
    max_tokens: int = 900,
) -> dict[str, Any]:
    packet = collect_packet(packet_dir)
    deterministic = evaluate_deterministic(packet, claim_text=claim_text)
    prompt = build_nim_prompt(packet, deterministic, claim_text=claim_text, max_chars=max_prompt_chars)
    nim_review: dict[str, Any] | None = None
    if mock_nim_response_file is not None:
        nim_review = extract_json_object(mock_nim_response_file.expanduser().read_text(encoding="utf-8"))
        nim_review.setdefault("model_identity", {"provider": "mock_nvidia_nim", "model": "mock"})
    elif with_nim:
        try:
            nim_review = asyncio.run(
                call_nvidia_nim(prompt, model=nim_model, timeout_seconds=timeout_seconds, max_tokens=max_tokens)
            )
        except Exception as exc:  # noqa: BLE001 - optional critic must not erase deterministic output.
            nim_review = {
                "verdict": "revise_protocol",
                "summary": "NVIDIA NIM critic call failed; deterministic guard output remains authoritative.",
                "strongest_blockers": [f"nvidia_nim_call_failed: {type(exc).__name__}: {exc}"],
                "claim_allowed": False,
                "confidence": 0.0,
                "model_identity": {"provider": "nvidia_nim", "model": nim_model},
                "usage": {},
                "failure_type": type(exc).__name__,
            }
    review = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "packet_dir": str(Path(packet_dir).expanduser().resolve()),
        "guard_prompt_sha256": sha256(prompt.encode("utf-8")).hexdigest(),
        "deterministic_review": deterministic,
        "nvidia_nim_review": nim_review,
        "authority": {
            "benchmarks_run": False,
            "trainer_mutated": False,
            "archive_fitness_mutated": False,
            "production_router_mutated": False,
            "public_claim_made": False,
            "external_submission_performed": False,
        },
    }
    target_dir = (out_dir or packet_dir).expanduser().resolve()
    json_path = target_dir / DEFAULT_OUT_NAME
    md_path = target_dir / DEFAULT_MD_NAME
    review["artifact_paths"] = {"json": str(json_path), "markdown": str(md_path)}
    write_json(json_path, review)
    md_path.write_text(render_markdown(review), encoding="utf-8")
    return review


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Forge deterministic packet guard with optional NVIDIA/NIM critic")
    parser.add_argument("--packet-dir", required=True)
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--claim", default="")
    parser.add_argument("--with-nim", action="store_true")
    parser.add_argument("--nim-model", default=DEFAULT_MODEL)
    parser.add_argument("--mock-nim-response-file", default="")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--max-prompt-chars", type=int, default=14000)
    parser.add_argument("--max-tokens", type=int, default=900)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    review = run_guard(
        packet_dir=Path(args.packet_dir),
        out_dir=Path(args.out_dir) if args.out_dir else None,
        claim_text=args.claim,
        with_nim=args.with_nim,
        nim_model=args.nim_model,
        mock_nim_response_file=Path(args.mock_nim_response_file) if args.mock_nim_response_file else None,
        timeout_seconds=args.timeout_seconds,
        max_prompt_chars=args.max_prompt_chars,
        max_tokens=args.max_tokens,
    )
    payload = {
        "status": "FORGE_PACKET_GUARD_REVIEW_WRITTEN",
        "deterministic_verdict": review["deterministic_review"]["verdict"],
        "nim_verdict": (review.get("nvidia_nim_review") or {}).get("verdict", ""),
        "artifact_paths": review.get("artifact_paths", {}),
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"{payload['status']} deterministic={payload['deterministic_verdict']} "
            f"nim={payload['nim_verdict'] or 'not_run'}"
        )
    return 0


__all__ = [
    "CANONICAL_CONTROL_ARM_ALIASES",
    "REQUIRED_PACKET_FILES",
    "collect_packet",
    "evaluate_deterministic",
    "run_guard",
    "taskbed_power",
]
