"""E4 discrimination receipt for full-CONFIRM scaffold comparisons.

E4 is the kill-gate for the RSI Lab: a candidate scaffold is not promotable
just because it has a positive point estimate.  It must separate from a
deliberately-bad or baseline scaffold on adequate paired CONFIRM data, with
non-overlapping confidence intervals and a pre-registered effect target.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .signals import canonical_sha256

SCHEMA_VERSION = "forge_v2.e4_discrimination_receipt.v1"
MIN_CONFIRM_N = 500
MIN_EFFECT = 0.05
DEFAULT_PREREGISTERED_MDE = 0.056


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


def ci_half_width(ci: dict[str, Any]) -> float:
    return max(0.0, (safe_float(ci.get("upper")) - safe_float(ci.get("lower"))) / 2.0)


def confirm_ci(record: dict[str, Any]) -> dict[str, Any]:
    """Extract a confirm CI from common Forge signal/report shapes."""
    candidates = [
        record.get("confirm_ci"),
        record.get("paired_bootstrap_ci"),
        (record.get("run_report") or {}).get("paired_bootstrap_ci")
        if isinstance(record.get("run_report"), dict)
        else None,
        ((record.get("split_contrasts") or {}).get("confirm"))
        if isinstance(record.get("split_contrasts"), dict)
        else None,
        ((record.get("by_split") or {}).get("confirm"))
        if isinstance(record.get("by_split"), dict)
        else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, dict) and candidate:
            out = dict(candidate)
            if out.get("n") is None and record.get("task_count") is not None:
                out["n"] = record.get("task_count")
            return out
    return {}


def evaluate_discrimination(
    good: dict[str, Any],
    bad: dict[str, Any],
    *,
    good_id: str = "candidate",
    bad_id: str = "baseline",
    min_confirm_n: int = MIN_CONFIRM_N,
    min_effect: float = MIN_EFFECT,
    pre_registered_mde: float = DEFAULT_PREREGISTERED_MDE,
) -> dict[str, Any]:
    good_ci = confirm_ci(good)
    bad_ci = confirm_ci(bad)
    blockers: list[str] = []

    if not good_ci:
        blockers.append("missing_good_confirm_ci")
    if not bad_ci:
        blockers.append("missing_bad_confirm_ci")

    good_n = safe_int(good_ci.get("n"))
    bad_n = safe_int(bad_ci.get("n"))
    good_mean = safe_float(good_ci.get("mean"))
    bad_mean = safe_float(bad_ci.get("mean"))
    good_lower = safe_float(good_ci.get("lower"))
    good_upper = safe_float(good_ci.get("upper"))
    bad_lower = safe_float(bad_ci.get("lower"))
    bad_upper = safe_float(bad_ci.get("upper"))
    good_half_width = ci_half_width(good_ci)
    bad_half_width = ci_half_width(bad_ci)
    delta_mean = good_mean - bad_mean
    ci_gap = good_lower - bad_upper

    if good_n < min_confirm_n:
        blockers.append(f"good_confirm_n<{min_confirm_n}")
    if bad_n < min_confirm_n:
        blockers.append(f"bad_confirm_n<{min_confirm_n}")
    if good_half_width > pre_registered_mde:
        blockers.append("good_ci_half_width>mde")
    if bad_half_width > pre_registered_mde:
        blockers.append("bad_ci_half_width>mde")
    if delta_mean < min_effect:
        blockers.append("delta_mean<min_effect")
    if ci_gap <= 0:
        blockers.append("confirm_cis_overlap")

    passed = not blockers
    receipt = {
        "schema": SCHEMA_VERSION,
        "decision": "pass" if passed else "refused",
        "promotion_gate_satisfied": passed,
        "good_id": good_id,
        "bad_id": bad_id,
        "min_confirm_n": min_confirm_n,
        "min_effect": min_effect,
        "pre_registered_mde": pre_registered_mde,
        "good": {
            "n": good_n,
            "mean": good_mean,
            "lower": good_lower,
            "upper": good_upper,
            "ci_half_width": good_half_width,
        },
        "bad": {
            "n": bad_n,
            "mean": bad_mean,
            "lower": bad_lower,
            "upper": bad_upper,
            "ci_half_width": bad_half_width,
        },
        "delta_mean": delta_mean,
        "ci_gap": ci_gap,
        "blockers": sorted(set(blockers)),
    }
    receipt["payload_sha256"] = canonical_sha256(receipt)
    return receipt


def read_json_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.expanduser().read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate the RSI Lab E4 discrimination gate")
    parser.add_argument("--good", required=True, help="JSON file for the good/candidate scaffold evidence")
    parser.add_argument("--bad", required=True, help="JSON file for the bad/baseline scaffold evidence")
    parser.add_argument("--good-id", default="candidate")
    parser.add_argument("--bad-id", default="baseline")
    parser.add_argument("--min-confirm-n", type=int, default=MIN_CONFIRM_N)
    parser.add_argument("--min-effect", type=float, default=MIN_EFFECT)
    parser.add_argument("--pre-registered-mde", type=float, default=DEFAULT_PREREGISTERED_MDE)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    receipt = evaluate_discrimination(
        read_json_object(Path(args.good)),
        read_json_object(Path(args.bad)),
        good_id=args.good_id,
        bad_id=args.bad_id,
        min_confirm_n=args.min_confirm_n,
        min_effect=args.min_effect,
        pre_registered_mde=args.pre_registered_mde,
    )
    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=True))
    else:
        print(
            "FORGE_E4_DISCRIMINATION "
            f"decision={receipt['decision']} delta={receipt['delta_mean']:.6f} "
            f"ci_gap={receipt['ci_gap']:.6f}"
        )
    return 0 if receipt["promotion_gate_satisfied"] else 1


__all__ = [
    "DEFAULT_PREREGISTERED_MDE",
    "MIN_CONFIRM_N",
    "MIN_EFFECT",
    "SCHEMA_VERSION",
    "ci_half_width",
    "confirm_ci",
    "evaluate_discrimination",
]
