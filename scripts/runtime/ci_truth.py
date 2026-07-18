#!/usr/bin/env python3
"""Evaluate GitHub check rollups against the Dharma CI truth contract."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT_PATH = REPO_ROOT / "docs" / "governance" / "CI_TRUTH_CONTRACT.json"
DEFAULT_PARITY_MANIFEST_PATH = (
    REPO_ROOT / "scripts" / "governance" / "ci_parity_manifest.json"
)
BAD_CONCLUSIONS = {"FAILURE", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED"}
PASS_CONCLUSIONS = {"SUCCESS", "SKIPPED", "NEUTRAL"}


class CITruthError(Exception):
    """Raised when CI truth cannot be evaluated."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Fail closed on duplicate keys in any JSON object (WP-0F1, TIT-006).

    Plain ``json.loads`` keeps the last duplicate silently, which once erased
    the pytest and gitleaks classifications from this very contract; a
    duplicate key is configuration corruption, never a merge strategy.
    """
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CITruthError(f"duplicate JSON key {key!r} in CI truth configuration")
        result[key] = value
    return result


def load_json(path: str | Path) -> Any:
    try:
        return json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except OSError as exc:
        raise CITruthError(f"could not read JSON file {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise CITruthError(f"invalid JSON file {path}: {exc}") from exc


def load_contract(path: str | Path = DEFAULT_CONTRACT_PATH) -> dict[str, Any]:
    contract = load_json(path)
    if contract.get("schema") != "dharma.ci_truth_contract.v1":
        raise CITruthError(f"unsupported CI truth contract schema in {path}")
    for group in ("required", "advisory"):
        if not isinstance(contract.get(group), list):
            raise CITruthError(f"CI truth contract missing {group!r} list")
        for entry in contract[group]:
            if not entry.get("id"):
                raise CITruthError(f"CI truth {group} entry missing id")
            names = entry.get("names")
            if not isinstance(names, list) or not names:
                raise CITruthError(f"CI truth entry {entry.get('id')} missing names")
            if not entry.get("local_command"):
                raise CITruthError(f"CI truth entry {entry.get('id')} missing local_command")
    manifest_ref = contract.get("required_contexts_manifest")
    if not manifest_ref:
        raise CITruthError(
            f"CI truth contract {path} missing required_contexts_manifest; "
            "the parity binding to branch-protection SSOT is mandatory"
        )
    manifest_path = Path(str(manifest_ref))
    if not manifest_path.is_absolute():
        manifest_path = REPO_ROOT / manifest_path
    validate_required_context_parity(contract, load_json(manifest_path))
    return contract


def required_context_names(contract: dict[str, Any]) -> list[str]:
    """Return the canonical merge-blocking context for each required entry.

    ``names[0]`` is the live context; later names are transition aliases that
    may match historical PR rollups but never expand branch-protection
    authority.
    """

    names = [str(entry["names"][0]) for entry in contract.get("required", [])]
    if len(names) != len(set(names)):
        raise CITruthError("CI truth required contexts contain duplicates")
    return names


def manifest_required_context_names(manifest: dict[str, Any]) -> list[str]:
    entries = manifest.get("required_contexts")
    if not isinstance(entries, list) or not entries:
        raise CITruthError("CI parity manifest required_contexts must be non-empty")
    names: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict) or not str(entry.get("context") or ""):
            raise CITruthError("CI parity manifest required context is malformed")
        names.append(str(entry["context"]))
    if len(names) != len(set(names)):
        raise CITruthError("CI parity manifest required contexts contain duplicates")
    return names


def validate_required_context_parity(
    contract: dict[str, Any], manifest: dict[str, Any]
) -> None:
    """Fail closed unless Mike's required set equals branch-protection SSOT."""

    contract_names = set(required_context_names(contract))
    manifest_names = set(manifest_required_context_names(manifest))
    if contract_names == manifest_names:
        return
    missing = sorted(manifest_names - contract_names)
    unexpected = sorted(contract_names - manifest_names)
    raise CITruthError(
        "CI truth required contexts disagree with CI parity manifest: "
        f"missing={missing}, unexpected={unexpected}"
    )


def _check_name(item: dict[str, Any]) -> str:
    return str(item.get("name") or item.get("context") or item.get("workflowName") or "unnamed")


def latest_checks_by_name(rollup: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, tuple[tuple[str, int], dict[str, Any]]] = {}
    for index, item in enumerate(rollup):
        name = _check_name(item)
        timestamp = str(item.get("completedAt") or item.get("startedAt") or "")
        key = (timestamp, index)
        current = latest.get(name)
        if current is None or key > current[0]:
            latest[name] = (key, item)
    return {name: item for name, (_, item) in latest.items()}


def classify_check(item: dict[str, Any] | None) -> str:
    if item is None:
        return "MISSING"
    conclusion = str(item.get("conclusion") or "").upper()
    status = str(item.get("status") or "").upper()
    if conclusion in BAD_CONCLUSIONS:
        return "FAIL"
    if status and status != "COMPLETED":
        return "PENDING"
    if conclusion in PASS_CONCLUSIONS:
        return "PASS"
    if conclusion:
        return "UNKNOWN"
    return "UNKNOWN"


def _match_entry(entry: dict[str, Any], latest: dict[str, dict[str, Any]]) -> tuple[str | None, dict[str, Any] | None]:
    for name in entry.get("names", []):
        if name in latest:
            return name, latest[name]
    return None, None


def evaluate_rollup(rollup: list[dict[str, Any]], contract: dict[str, Any] | None = None) -> dict[str, Any]:
    contract = contract or load_contract()
    latest = latest_checks_by_name(rollup)
    seen_names: set[str] = set()
    merge_blockers: list[str] = []
    warnings: list[str] = []
    required_results: list[dict[str, Any]] = []
    advisory_results: list[dict[str, Any]] = []

    def evaluate_group(group: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for entry in contract.get(group, []):
            matched_name, item = _match_entry(entry, latest)
            if matched_name:
                seen_names.add(matched_name)
            status = classify_check(item)
            result = {
                "id": entry["id"],
                "names": entry["names"],
                "matched_name": matched_name,
                "status": status,
                "owner": entry.get("owner", ""),
                "local_command": entry.get("local_command", ""),
                "failure_category": entry.get("failure_category", ""),
                "autofix": entry.get("autofix", "manual"),
                "conclusion": str((item or {}).get("conclusion") or ""),
                "github_status": str((item or {}).get("status") or ""),
                "details_url": str((item or {}).get("detailsUrl") or (item or {}).get("url") or ""),
            }
            if group == "required" and status != "PASS":
                merge_blockers.append(
                    f"required CI {entry['id']} is {status}; run `{entry.get('local_command', '')}`"
                )
            if group == "advisory" and status != "PASS":
                warnings.append(
                    f"advisory CI {entry['id']} is {status}; repro `{entry.get('local_command', '')}`"
                )
            results.append(result)
        return results

    required_results = evaluate_group("required")
    advisory_results = evaluate_group("advisory")
    unknown_checks = sorted(name for name in latest if name not in seen_names)
    if unknown_checks:
        warnings.append(f"uncontracted GitHub checks observed: {', '.join(unknown_checks)}")

    if merge_blockers:
        verdict = "FAIL"
    elif any(item["status"] != "PASS" for item in advisory_results):
        verdict = "DEGRADED"
    else:
        verdict = "PASS"

    return {
        "schema": "dharma.ci_truth_result.v1",
        "generated_at": utc_now(),
        "contract_version": contract.get("version"),
        "verdict": verdict,
        "merge_blockers": merge_blockers,
        "warnings": warnings,
        "required": required_results,
        "advisory": advisory_results,
        "observed_total": len(latest),
        "raw_total": len(rollup),
        "unknown_checks": unknown_checks,
    }


def fetch_pr_rollup(pr_number: int) -> list[dict[str, Any]]:
    proc = subprocess.run(
        ["gh", "pr", "view", str(pr_number), "--json", "statusCheckRollup"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        raise CITruthError(f"gh pr view failed for PR #{pr_number}: {detail}")
    payload = json.loads(proc.stdout)
    return payload.get("statusCheckRollup") or []


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# CI Truth",
        "",
        f"- Generated: `{result['generated_at']}`",
        f"- Verdict: `{result['verdict']}`",
        f"- Observed checks: `{result['observed_total']}` latest / `{result['raw_total']}` raw",
        "",
        "## Merge Blockers",
        "",
    ]
    if result["merge_blockers"]:
        lines.extend(f"- {item}" for item in result["merge_blockers"])
    else:
        lines.append("- none")
    lines.extend(["", "## Warnings", ""])
    if result["warnings"]:
        lines.extend(f"- {item}" for item in result["warnings"])
    else:
        lines.append("- none")
    for group in ("required", "advisory"):
        lines.extend(["", f"## {group.title()} Checks", ""])
        for item in result[group]:
            matched = item["matched_name"] or "-"
            lines.append(
                f"- `{item['id']}` status=`{item['status']}` matched=`{matched}` "
                f"owner=`{item['owner']}` repro=`{item['local_command']}`"
            )
    return "\n".join(lines) + "\n"


def contract_summary(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "dharma.ci_truth_contract_check.v1",
        "generated_at": utc_now(),
        "contract_version": contract.get("version"),
        "verdict": "PASS",
        "required_count": len(contract.get("required", [])),
        "advisory_count": len(contract.get("advisory", [])),
        "required_ids": [item["id"] for item in contract.get("required", [])],
        "advisory_ids": [item["id"] for item in contract.get("advisory", [])],
    }


def render_contract_summary(summary: dict[str, Any]) -> str:
    lines = [
        "# CI Truth Contract",
        "",
        f"- Generated: `{summary['generated_at']}`",
        f"- Verdict: `{summary['verdict']}`",
        f"- Required checks: `{summary['required_count']}`",
        f"- Advisory checks: `{summary['advisory_count']}`",
        "",
        "## Required IDs",
        "",
    ]
    lines.extend(f"- `{item}`" for item in summary["required_ids"])
    lines.extend(["", "## Advisory IDs", ""])
    lines.extend(f"- `{item}`" for item in summary["advisory_ids"])
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", default=str(DEFAULT_CONTRACT_PATH))
    parser.add_argument("--rollup-json", help="Path to a JSON list or object with statusCheckRollup")
    parser.add_argument("--pr", type=int, help="Fetch statusCheckRollup for this GitHub PR")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        contract = load_contract(args.contract)
        if args.rollup_json:
            payload = load_json(args.rollup_json)
            rollup = payload.get("statusCheckRollup") if isinstance(payload, dict) else payload
        elif args.pr:
            rollup = fetch_pr_rollup(args.pr)
        else:
            summary = contract_summary(contract)
            if args.json:
                print(json.dumps(summary, indent=2, sort_keys=True))
            else:
                print(render_contract_summary(summary), end="")
            return 0
        if not isinstance(rollup, list):
            raise CITruthError("rollup input must be a list or object with statusCheckRollup")
        result = evaluate_rollup(rollup, contract)
    except CITruthError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(render_markdown(result), end="")
    if result["verdict"] == "FAIL":
        return 2
    if result["verdict"] == "DEGRADED":
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
