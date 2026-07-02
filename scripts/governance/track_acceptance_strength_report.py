#!/usr/bin/env python3
"""Advisory acceptance-strength report for ACTIVE_TRACK.yaml.

This is a read-only anti-slop promotion membrane. It does not decide whether a
track passes its declared criteria; `check_track_status.py` already owns that.
Instead it asks a narrower question:

    How strong is the *kind of evidence* required by those criteria?

The first version is intentionally advisory and exits 0 by default. Use
`--strict` only when experimenting locally; do not wire it as a hard gate until
the warning set has gone through the hygiene lifecycle.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# Reuse the existing ACTIVE_TRACK parser/normalizer instead of creating a
# parallel YAML loader or portfolio model.
try:
    from check_track_status import load_active_track, normalize_portfolio  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - defensive for unusual import paths
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from check_track_status import load_active_track, normalize_portfolio  # type: ignore


SCHEMA_VERSION = "dharma.track_acceptance_strength.v1"
DEFAULT_ACTIVE_TRACK = Path("docs/governance/ACTIVE_TRACK.yaml")
DEFAULT_JSON_REPORT = Path("reports/governance/track_acceptance_strength.json")
DEFAULT_MD_REPORT = Path("reports/governance/track_acceptance_strength.md")


RUBRIC: dict[int, str] = {
    0: "file exists",
    1: "file contains required structured fields",
    2: "command exits 0 with receipt",
    3: "test proves positive behavior",
    4: "negative/adversarial test proves failure mode",
    5: "integration/runtime receipt proves path",
    6: "independent reproduction",
    7: "clean promotion with rollback and caveats",
}


STATE_BY_STRENGTH: list[tuple[int, str]] = [
    (7, "promoted"),
    (6, "independently-reproduced"),
    (5, "system-shippable"),
    (4, "behavior-shippable"),
    (3, "behavior-shippable-positive"),
    (2, "command-receipted"),
    (1, "declared-shippable"),
    (0, "file-present"),
]


KIND_STRENGTH: dict[str, int] = {
    "file_exists": 0,
    "file_contains": 1,
    "pr_merged": 2,
    "command": 2,
    "command_receipt": 2,
    "test": 3,
    "pytest": 3,
    "negative_test": 4,
    "adversarial_test": 4,
    "integration_test": 5,
    "runtime": 5,
    "runtime_receipt": 5,
    "e2e": 5,
    "independent_reproduction": 6,
    "external_reproduction": 6,
    "promotion": 7,
    "rollback": 7,
    "closed_with_caveats": 7,
}


ADVERSARIAL_CUE = re.compile(
    r"(block\w*|reject\w*|fail\w*|failure|negative|adversarial|bypass\w*|"
    r"forbid\w*|forbidden|regression|rollback|exploit\w*|poison\w*|drift)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ClaimPattern:
    code: str
    pattern: re.Pattern[str]
    required_strength: int
    reason: str


CLAIM_PATTERNS: tuple[ClaimPattern, ...] = (
    ClaimPattern(
        "system_scope_closure",
        re.compile(r"\b(loop[-_\s]?closure|closure|closed|closeout|wire all 13|all 13 loops)\b", re.I),
        5,
        "closure language implies an observed runtime path, not only files/prose",
    ),
    ClaimPattern(
        "runtime_scope_claim",
        re.compile(r"\b(runtime|live|dispatch|spine|nats|substrate|persistence|longrun)\b", re.I),
        5,
        "runtime/substrate language should be backed by integration or runtime receipts",
    ),
    ClaimPattern(
        "platform_scope_claim",
        re.compile(r"\b(platform|system|organism|whole[-_\s]?system)\b", re.I),
        5,
        "platform/system language should not be promoted from thin file criteria alone",
    ),
    ClaimPattern(
        "truth_scope_claim",
        re.compile(r"\b(truth|reconciliation|canonical|invariant)\b", re.I),
        4,
        "truth/canonical language should be backed by behavior plus negative/adversarial checks",
    ),
)


@dataclass(frozen=True)
class CriterionStrength:
    id: str
    kind: str
    strength: int
    label: str
    reason: str


@dataclass(frozen=True)
class Warning:
    code: str
    severity: str
    message: str
    recommendation: str
    required_strength: int | None = None


@dataclass(frozen=True)
class TrackStrength:
    id: str
    name: str
    status: str
    criterion_count: int
    min_strength: int | None
    max_strength: int | None
    average_strength: float | None
    thin_criteria: int
    thin_ratio: float
    evidence_state: str
    recommended_claim: str
    criteria: list[CriterionStrength] = field(default_factory=list)
    warnings: list[Warning] = field(default_factory=list)


def criterion_text(criterion: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("id", "kind", "file", "pattern", "command", "test", "what", "description"):
        value = criterion.get(key)
        if value is not None:
            parts.append(str(value))
    return " ".join(parts)


def classify_criterion(criterion: dict[str, Any]) -> CriterionStrength:
    kind = str(criterion.get("kind", "") or "").strip().lower()
    text = criterion_text(criterion)
    strength = KIND_STRENGTH.get(kind, 1)

    if kind in {"test", "pytest"} and ADVERSARIAL_CUE.search(text):
        strength = max(strength, 4)
    if kind in {"command", "command_receipt"} and re.search(r"\breceipt\b", text, re.I):
        strength = max(strength, 2)

    strength = max(0, min(7, int(strength)))
    return CriterionStrength(
        id=str(criterion.get("id", "") or "(unnamed)"),
        kind=kind or "(missing)",
        strength=strength,
        label=RUBRIC[strength],
        reason=_strength_reason(kind, text, strength),
    )


def _strength_reason(kind: str, text: str, strength: int) -> str:
    if kind == "file_exists":
        return "checks presence only; does not verify contents or behavior"
    if kind == "file_contains":
        return "checks a string/pattern exists; does not execute the claimed path"
    if strength >= 5:
        return "requires integration/runtime evidence"
    if strength == 4:
        return "requires a failure-mode or adversarial check"
    if strength == 3:
        return "requires a positive behavior test"
    if strength == 2:
        return "requires a command or merge receipt"
    return f"classified from kind={kind!r} text={text[:80]!r}"


def state_for_strength(max_strength: int | None) -> str:
    if max_strength is None:
        return "no-declared-criteria"
    for floor, state in STATE_BY_STRENGTH:
        if max_strength >= floor:
            return state
    return "unknown"


def recommended_claim_for(max_strength: int | None, warnings: list[Warning]) -> str:
    if max_strength is None:
        return "proposed/admitted only; no completion criteria declared"
    if max_strength <= 1:
        if any(w.code == "system_scope_closure" for w in warnings):
            return (
                "declared-shippable only: criteria prove named files/patterns exist; "
                "do not claim loop/system closure complete"
            )
        return "declared-shippable only: criteria are file/prose backed"
    if max_strength < 5:
        return "behavior-shippable only if the named tests/commands have fresh receipts"
    if max_strength == 5:
        return "system-shippable only for the runtime path actually covered by the receipt"
    if max_strength == 6:
        return "independently reproduced; still require rollback/caveats before promotion"
    return "eligible for promoted language only with named rollback and caveats"


def warnings_for_track(track: dict[str, Any], max_strength: int | None, thin_ratio: float) -> list[Warning]:
    haystack = " ".join(
        str(track.get(key, "") or "")
        for key in ("id", "name", "description", "serves")
    )
    warnings: list[Warning] = []
    effective_strength = -1 if max_strength is None else max_strength

    if max_strength is None:
        warnings.append(
            Warning(
                code="no_completion_criteria",
                severity="WARN",
                message="track has no completion_criteria to score",
                recommendation="add explicit criteria before using any shippable/closed language",
            )
        )

    if thin_ratio >= 0.8 and (max_strength is not None and max_strength <= 1):
        warnings.append(
            Warning(
                code="thin_declared_shippable",
                severity="WARN",
                message="most/all criteria are file_exists or file_contains checks",
                recommendation="prefer declared-shippable; add command/test/runtime criteria before stronger claims",
                required_strength=3,
            )
        )

    for pattern in CLAIM_PATTERNS:
        if pattern.pattern.search(haystack) and effective_strength < pattern.required_strength:
            warnings.append(
                Warning(
                    code=pattern.code,
                    severity="WARN",
                    message=pattern.reason,
                    recommendation=(
                        f"downgrade claim language until at least strength {pattern.required_strength} "
                        f"({RUBRIC[pattern.required_strength]}) is present"
                    ),
                    required_strength=pattern.required_strength,
                )
            )
    return warnings


def score_track(track: dict[str, Any]) -> TrackStrength:
    criteria = [classify_criterion(c) for c in (track.get("completion_criteria") or []) if isinstance(c, dict)]
    strengths = [c.strength for c in criteria]
    criterion_count = len(criteria)
    thin_criteria = sum(1 for s in strengths if s <= 1)
    thin_ratio = (thin_criteria / criterion_count) if criterion_count else 0.0
    min_strength = min(strengths) if strengths else None
    max_strength = max(strengths) if strengths else None
    average_strength = round(sum(strengths) / criterion_count, 2) if criterion_count else None

    warnings = warnings_for_track(track, max_strength, thin_ratio)
    return TrackStrength(
        id=str(track.get("id", "") or "(missing-id)"),
        name=str(track.get("name", "") or ""),
        status=str(track.get("status", "") or ""),
        criterion_count=criterion_count,
        min_strength=min_strength,
        max_strength=max_strength,
        average_strength=average_strength,
        thin_criteria=thin_criteria,
        thin_ratio=round(thin_ratio, 3),
        evidence_state=state_for_strength(max_strength),
        recommended_claim=recommended_claim_for(max_strength, warnings),
        criteria=criteria,
        warnings=warnings,
    )


def build_report(track_path: Path) -> dict[str, Any]:
    raw = load_active_track(track_path)
    portfolio = normalize_portfolio(raw)
    active_tracks = [t for t in portfolio.get("active_tracks", []) if isinstance(t, dict)]
    tracks = [score_track(t) for t in active_tracks]
    thin_declared = [
        t.id
        for t in tracks
        if t.criterion_count and (t.max_strength or 0) <= 1 and t.thin_ratio >= 0.8
    ]
    warnings = sum(len(t.warnings) for t in tracks)
    return {
        "schema_version": SCHEMA_VERSION,
        "source": str(track_path),
        "summary": {
            "active_tracks": len(tracks),
            "thin_declared_tracks": len(thin_declared),
            "thin_declared_track_ids": thin_declared,
            "warnings": warnings,
            "max_strength_counts": _max_strength_counts(tracks),
        },
        "rubric": [{"strength": k, "label": v} for k, v in RUBRIC.items()],
        "tracks": [asdict(t) for t in tracks],
    }


def _max_strength_counts(tracks: list[TrackStrength]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for track in tracks:
        key = "none" if track.max_strength is None else str(track.max_strength)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Track Acceptance Strength Report",
        "",
        "Advisory anti-slop membrane: this scores the *strength of evidence required* by active track criteria.",
        "",
        "## Summary",
        "",
        f"- Active tracks: **{summary['active_tracks']}**",
        f"- Thin declared tracks: **{summary['thin_declared_tracks']}**",
        f"- Warnings: **{summary['warnings']}**",
        "",
        "## Active tracks",
        "",
        "| Track | Criteria | Max strength | Thin ratio | Evidence state | Recommendation | Warnings |",
        "|---|---:|---:|---:|---|---|---:|",
    ]
    for track in report["tracks"]:
        max_strength = "none" if track["max_strength"] is None else str(track["max_strength"])
        lines.append(
            "| {id} | {count} | {maxs} | {thin:.0%} | {state} | {rec} | {warnings} |".format(
                id=track["id"],
                count=track["criterion_count"],
                maxs=max_strength,
                thin=float(track["thin_ratio"]),
                state=track["evidence_state"],
                rec=track["recommended_claim"].replace("|", "/"),
                warnings=len(track["warnings"]),
            )
        )
    lines.extend(["", "## Warning details", ""])
    for track in report["tracks"]:
        if not track["warnings"]:
            continue
        lines.append(f"### `{track['id']}`")
        for warning in track["warnings"]:
            lines.append(
                f"- **{warning['code']}** ({warning['severity']}): {warning['message']} "
                f"→ {warning['recommendation']}"
            )
        lines.append("")
    lines.extend(["## Rubric", ""])
    for item in report["rubric"]:
        lines.append(f"- **{item['strength']}** — {item['label']}")
    return "\n".join(lines).rstrip() + "\n"


def write_reports(report: dict[str, Any], json_path: Path, md_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--track-file", type=Path, default=DEFAULT_ACTIVE_TRACK)
    parser.add_argument("--json", action="store_true", help="Emit JSON to stdout instead of markdown")
    parser.add_argument("--write", action="store_true", help="Write JSON and Markdown reports under reports/governance/")
    parser.add_argument("--json-report", type=Path, default=DEFAULT_JSON_REPORT)
    parser.add_argument("--md-report", type=Path, default=DEFAULT_MD_REPORT)
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when advisory warnings are present")
    args = parser.parse_args(argv)

    report = build_report(args.track_file)
    if args.write:
        write_reports(report, args.json_report, args.md_report)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_markdown(report), end="")
    if args.strict and report["summary"]["warnings"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
