#!/usr/bin/env python3
"""Advisory claim-maturity report for ACTIVE_TRACK.yaml.

This is a read-only anti-slop promotion membrane. It does not decide whether a
track passes its declared criteria; ``check_track_status.py`` already owns that.
Instead it asks:

    Does the strength of the criteria match the claim/name being made?

The report is advisory and exits 0 by default. ``--strict`` is for local/operator
experiments only; do not add this to governance-all until it has passed through
the hygiene lifecycle.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

try:
    from check_track_status import (  # type: ignore
        EXISTENCE_KINDS,
        RIGOROUS_KINDS,
        load_active_track,
        normalize_portfolio,
    )
except ModuleNotFoundError:  # pragma: no cover - unusual import path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from check_track_status import (  # type: ignore
        EXISTENCE_KINDS,
        RIGOROUS_KINDS,
        load_active_track,
        normalize_portfolio,
    )


SCHEMA_VERSION = "dharma.track_acceptance_strength.v2"
DEFAULT_ACTIVE_TRACK = Path("docs/governance/ACTIVE_TRACK.yaml")
DEFAULT_JSON_REPORT = Path("reports/governance/track_acceptance_strength.json")
DEFAULT_MD_REPORT = Path("reports/governance/track_acceptance_strength.md")

SUPPORTED_KINDS = frozenset(EXISTENCE_KINDS | RIGOROUS_KINDS)


RUBRIC: dict[int, str] = {
    0: "file present",
    1: "declaration-complete",
    2: "command-receipted",
    3: "behavior-verified",
    4: "adversarial-verified",
    5: "runtime-verified",
    6: "independently-reproduced",
    7: "promoted",
}


EVIDENCE_GRADES_PATH = Path(__file__).resolve().parents[2] / "docs/governance/evidence_grades.yaml"

# Fail-safe copy used ONLY if the single config is missing/malformed (a
# governance gate must not crash on bad config). The authoritative source is
# docs/governance/evidence_grades.yaml::kind_maturity — do not hand-edit these
# to diverge from it; the single-owner invariant test pins them equal.
_FALLBACK_KIND_STRENGTH: dict[str, int] = {
    "file_exists": 0,
    "file_contains": 1,
    "pr_merged": 2,
    "commit_on_main": 2,
    "test_passes": 3,
    "receipt_valid": 5,
    "mutation_score_gte": 4,
}


def _load_kind_strength() -> dict[str, int]:
    """Read the claim-maturity strengths from the SINGLE config
    (evidence_grades.yaml::kind_maturity) so this membrane and the evidence-grade
    gate read ONE source — no second hard-coded ladder that can silently drift
    (the convergence-review defect). Fail-safe to a built-in copy."""
    try:
        raw = load_active_track(EVIDENCE_GRADES_PATH)
        km = raw.get("kind_maturity") if isinstance(raw, dict) else None
        if isinstance(km, dict) and km:
            out: dict[str, int] = {}
            for key, val in km.items():
                try:
                    out[str(key)] = int(val)
                except (TypeError, ValueError):
                    continue
            if out:
                return out
    except OSError:
        return dict(_FALLBACK_KIND_STRENGTH)
    except ValueError:
        return dict(_FALLBACK_KIND_STRENGTH)
    return dict(_FALLBACK_KIND_STRENGTH)


KIND_STRENGTH: dict[str, int] = _load_kind_strength()


ADVERSARIAL_CUE = re.compile(
    r"(block\w*|reject\w*|fail\w*|failure|negative|adversarial|bypass\w*|"
    r"forbid\w*|forbidden|regression|rollback|exploit\w*|poison\w*|drift)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ClaimPattern:
    code: str
    pattern: re.Pattern[str]
    required_floor: int
    reason: str


CLAIM_PATTERNS: tuple[ClaimPattern, ...] = (
    ClaimPattern(
        "closure_scope_claim",
        re.compile(r"\b(loop[-_\s]?closure|closure|closed|closeout|wire all 13|all 13 loops)\b", re.I),
        5,
        "closure language implies an observed runtime path, not only files/prose",
    ),
    ClaimPattern(
        "runtime_scope_claim",
        re.compile(r"\b(runtime|live|dispatch|spine|nats|substrate|persistence|longrun)\b", re.I),
        5,
        "runtime/substrate language should be backed by runtime receipts or equivalent integration evidence",
    ),
    ClaimPattern(
        "platform_scope_claim",
        re.compile(r"\b(platform|system|organism|whole[-_\s]?system)\b", re.I),
        5,
        "platform/system language should not be promoted from weak or partial criteria",
    ),
    ClaimPattern(
        "truth_scope_claim",
        re.compile(r"\b(truth|reconciliation|canonical|invariant)\b", re.I),
        4,
        "truth/canonical language should include behavior plus failure-mode coverage",
    ),
)


@dataclass(frozen=True)
class CriterionStrength:
    id: str
    kind: str
    strength: int
    maturity: str
    supported_by_status_checker: bool
    malformed: bool = False
    reason: str = ""


@dataclass(frozen=True)
class Warning:
    code: str
    severity: str
    message: str
    recommendation: str
    required_floor: int | None = None


@dataclass(frozen=True)
class TrackStrength:
    id: str
    name: str
    workflow_status: str
    criterion_count: int
    strongest_criterion_strength: int | None
    weakest_criterion_strength: int | None
    maturity_floor: int | None
    maturity: str
    thin_criteria: int
    thin_ratio: float
    unsupported_kind_count: int
    claim_scope_warnings: int
    recommended_claim: str
    criteria: list[CriterionStrength] = field(default_factory=list)
    warnings: list[Warning] = field(default_factory=list)


def criterion_text(criterion: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in (
        "id",
        "kind",
        "file",
        "pattern",
        "collection",
        "field",
        "key_field",
        "value_field",
        "value",
        "expected",
        "threshold",
        "mapping",
        "keys",
        "commit",
        "test",
        "pr",
        "requires_keys",
        "what",
        "description",
    ):
        value = criterion.get(key)
        if value is not None:
            parts.append(str(value))
    return " ".join(parts)


def is_malformed_criterion(criterion: dict[str, Any]) -> bool:
    kind = criterion.get("kind")
    if not isinstance(kind, str) or not kind:
        return True
    if kind == "file_exists":
        return not isinstance(criterion.get("file"), str) or not criterion.get("file")
    if kind == "file_contains":
        return (
            not isinstance(criterion.get("file"), str)
            or not criterion.get("file")
            or not isinstance(criterion.get("pattern"), str)
            or not criterion.get("pattern")
        )
    if kind == "json_count_equals":
        return (
            not isinstance(criterion.get("file"), str)
            or not criterion.get("file")
            or not isinstance(criterion.get("collection"), str)
            or not criterion.get("collection")
            or not isinstance(criterion.get("field"), str)
            or not criterion.get("field")
            or "value" not in criterion
            or criterion.get("value") is None
            or "expected" not in criterion
        )
    if kind == "json_count_greater_than":
        return (
            not isinstance(criterion.get("file"), str)
            or not criterion.get("file")
            or not isinstance(criterion.get("collection"), str)
            or not criterion.get("collection")
            or not isinstance(criterion.get("field"), str)
            or not criterion.get("field")
            or "value" not in criterion
            or criterion.get("value") is None
            or "threshold" not in criterion
        )
    if kind == "json_collection_values_match":
        return (
            not isinstance(criterion.get("file"), str)
            or not criterion.get("file")
            or not isinstance(criterion.get("collection"), str)
            or not criterion.get("collection")
            or not isinstance(criterion.get("key_field"), str)
            or not criterion.get("key_field")
            or not isinstance(criterion.get("value_field"), str)
            or not criterion.get("value_field")
            or not isinstance(criterion.get("expected"), dict)
        )
    if kind == "json_mapping_keys_nonempty":
        return (
            not isinstance(criterion.get("file"), str)
            or not criterion.get("file")
            or not isinstance(criterion.get("mapping"), str)
            or not criterion.get("mapping")
            or not isinstance(criterion.get("keys"), list)
        )
    if kind == "commit_on_main":
        return not isinstance(criterion.get("commit"), str) or not criterion.get("commit")
    if kind == "test_passes":
        return not isinstance(criterion.get("test"), str) or not criterion.get("test")
    if kind == "receipt_valid":
        return not isinstance(criterion.get("file"), str) or not criterion.get("file")
    if kind == "pr_merged":
        return criterion.get("pr") is None
    return False


def classify_criterion(raw: Any, index: int) -> CriterionStrength:
    if not isinstance(raw, dict):
        return CriterionStrength(
            id=f"(non-dict-{index})",
            kind="(non-dict)",
            strength=0,
            maturity=RUBRIC[0],
            supported_by_status_checker=False,
            malformed=True,
            reason="criterion is not a mapping; check_track_status cannot evaluate it",
        )

    kind = str(raw.get("kind", "") or "").strip()
    supported = kind in SUPPORTED_KINDS
    malformed = is_malformed_criterion(raw)
    text = criterion_text(raw)

    if not supported:
        strength = 0
    else:
        strength = KIND_STRENGTH.get(kind, 0)
        # Origin/main has one executable behavior kind: test_passes. If the
        # specific test target is named as a failure-mode test, it earns the
        # stronger adversarial-verified maturity without inventing a new kind.
        if kind == "test_passes" and ADVERSARIAL_CUE.search(text):
            strength = max(strength, 4)
        if malformed:
            strength = 0

    return CriterionStrength(
        id=str(raw.get("id") or f"(unnamed-{index})"),
        kind=kind or "(missing)",
        strength=strength,
        maturity=RUBRIC[strength],
        supported_by_status_checker=supported,
        malformed=malformed,
        reason=strength_reason(kind, supported, malformed, text, strength),
    )


def strength_reason(kind: str, supported: bool, malformed: bool, text: str, strength: int) -> str:
    if malformed:
        return "malformed criterion; cannot support promotion claims"
    if not supported:
        return f"unsupported by check_track_status.py: {kind!r}"
    if kind == "file_exists":
        return "presence only; does not verify contents or behavior"
    if kind == "file_contains":
        return "grep/string evidence only; does not execute the claimed path"
    if kind == "commit_on_main":
        return "landed commit evidence; proves inclusion, not behavior by itself"
    if kind == "pr_merged":
        return "merge receipt evidence; proves workflow state, not behavior by itself"
    if kind in {
        "json_count_equals",
        "json_count_greater_than",
        "json_collection_values_match",
        "json_mapping_keys_nonempty",
    }:
        return "structured JSON assertion; stronger than prose grep, weaker than independent execution"
    if kind == "test_passes" and strength >= 4:
        return "passing adversarial/failure-mode pytest target"
    if kind == "test_passes":
        return "passing positive pytest target"
    if kind == "receipt_valid":
        return "valid structured receipt with required keys"
    return f"classified from kind={kind!r} text={text[:80]!r}"


def maturity_for_floor(floor: int | None) -> str:
    if floor is None:
        return "no-declared-criteria"
    return RUBRIC[max(0, min(7, floor))]


def recommended_claim_for(maturity_floor: int | None, warnings: list[Warning]) -> str:
    if maturity_floor is None:
        return "proposed/admitted only: no completion criteria declared"
    if maturity_floor <= 1:
        if any(w.code == "closure_scope_claim" for w in warnings):
            return "declaration-complete only: manifest/prose exists; do not claim closure complete"
        return "declaration-complete only: file/prose-backed criteria"
    if maturity_floor == 2:
        return "command-receipted only: landed/merged evidence still needs behavior proof"
    if maturity_floor == 3:
        return "behavior-verified for positive paths only; do not claim adversarial/runtime coverage"
    if maturity_floor == 4:
        return "adversarial-verified; runtime/platform claims still need receipt-backed path proof"
    if maturity_floor == 5:
        return "runtime-verified only for the exact path covered by the receipt"
    if maturity_floor == 6:
        return "independently-reproduced; still require rollback/caveats before promotion"
    return "promoted language allowed only with owner, rollback, and caveats"


def warnings_for_track(track: dict[str, Any], criteria: list[CriterionStrength], maturity_floor: int | None, thin_ratio: float) -> list[Warning]:
    haystack = " ".join(str(track.get(key, "") or "") for key in ("id", "name", "description", "serves"))
    warnings: list[Warning] = []
    effective_floor = -1 if maturity_floor is None else maturity_floor

    if maturity_floor is None:
        warnings.append(
            Warning(
                code="no_completion_criteria",
                severity="WARN",
                message="track has no completion_criteria to score",
                recommendation="add explicit criteria before any completion/shippable/closed language",
            )
        )

    unsupported = [c for c in criteria if not c.supported_by_status_checker]
    if unsupported:
        kinds = ", ".join(sorted({c.kind for c in unsupported}))
        warnings.append(
            Warning(
                code="unsupported_by_status_checker",
                severity="WARN",
                message=f"criterion kind(s) are not evaluated by check_track_status.py: {kinds}",
                recommendation="replace with file_exists, file_contains, pr_merged, commit_on_main, test_passes, or receipt_valid",
            )
        )

    malformed = [c for c in criteria if c.malformed]
    if malformed:
        warnings.append(
            Warning(
                code="malformed_criteria",
                severity="WARN",
                message=f"{len(malformed)} criterion/criteria are malformed and cannot support maturity claims",
                recommendation="fix criterion fields so check_track_status.py can evaluate them deterministically",
            )
        )

    if thin_ratio >= 0.8 and criteria:
        warnings.append(
            Warning(
                code="thin_declaration_complete",
                severity="WARN",
                message="most/all criteria are file_exists or file_contains checks",
                recommendation="use declaration-complete language until behavior/runtime criteria cover the claim",
                required_floor=3,
            )
        )

    for pattern in CLAIM_PATTERNS:
        if pattern.pattern.search(haystack) and effective_floor < pattern.required_floor:
            warnings.append(
                Warning(
                    code=pattern.code,
                    severity="WARN",
                    message=pattern.reason,
                    recommendation=(
                        f"downgrade claim language until maturity_floor >= {pattern.required_floor} "
                        f"({RUBRIC[pattern.required_floor]})"
                    ),
                    required_floor=pattern.required_floor,
                )
            )
    return warnings


def score_track(track: dict[str, Any]) -> TrackStrength:
    criteria = [classify_criterion(c, i) for i, c in enumerate(track.get("completion_criteria") or [])]
    strengths = [c.strength for c in criteria]
    criterion_count = len(criteria)
    thin_criteria = sum(1 for c in criteria if c.kind in EXISTENCE_KINDS or c.strength <= 1)
    thin_ratio = (thin_criteria / criterion_count) if criterion_count else 0.0
    strongest = max(strengths) if strengths else None
    weakest = min(strengths) if strengths else None
    # Conservative/conjunctive by design: one strong criterion cannot promote a
    # track whose other required criteria remain weak, malformed, or unsupported.
    maturity_floor = weakest
    warnings = warnings_for_track(track, criteria, maturity_floor, thin_ratio)
    claim_scope_warnings = sum(1 for w in warnings if w.code.endswith("_scope_claim"))

    return TrackStrength(
        id=str(track.get("id", "") or "(missing-id)"),
        name=str(track.get("name", "") or ""),
        workflow_status=str(track.get("status", "") or ""),
        criterion_count=criterion_count,
        strongest_criterion_strength=strongest,
        weakest_criterion_strength=weakest,
        maturity_floor=maturity_floor,
        maturity=maturity_for_floor(maturity_floor),
        thin_criteria=thin_criteria,
        thin_ratio=round(thin_ratio, 3),
        unsupported_kind_count=sum(1 for c in criteria if not c.supported_by_status_checker),
        claim_scope_warnings=claim_scope_warnings,
        recommended_claim=recommended_claim_for(maturity_floor, warnings),
        criteria=criteria,
        warnings=warnings,
    )


def build_report(track_path: Path) -> dict[str, Any]:
    raw = load_active_track(track_path)
    portfolio = normalize_portfolio(raw)
    active_tracks = [
        t for t in (portfolio.get("active_tracks", []) or [])
        if isinstance(t, dict) and str(t.get("status", "")).upper() == "ACTIVE"
    ]
    tracks = [score_track(t) for t in active_tracks]
    return {
        "schema_version": SCHEMA_VERSION,
        "source": str(track_path),
        "supported_kinds": sorted(SUPPORTED_KINDS),
        "summary": {
            "active_tracks": len(tracks),
            "declaration_complete_tracks": sum(1 for t in tracks if (t.maturity_floor or 0) <= 1),
            "unsupported_kind_count": sum(t.unsupported_kind_count for t in tracks),
            "claim_scope_warnings": sum(t.claim_scope_warnings for t in tracks),
            "warnings": sum(len(t.warnings) for t in tracks),
            "maturity_counts": _maturity_counts(tracks),
        },
        "rubric": [{"strength": k, "claim_maturity": v} for k, v in RUBRIC.items()],
        "tracks": [asdict(t) for t in tracks],
    }


def _maturity_counts(tracks: list[TrackStrength]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for track in tracks:
        counts[track.maturity] = counts.get(track.maturity, 0) + 1
    return dict(sorted(counts.items()))


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Track Acceptance Strength Report",
        "",
        "Advisory anti-slop membrane: scores claim maturity from active track criteria strength.",
        "",
        "## Summary",
        "",
        f"- Active tracks: **{summary['active_tracks']}**",
        f"- Declaration-complete-or-weaker tracks: **{summary['declaration_complete_tracks']}**",
        f"- Unsupported criterion kinds: **{summary['unsupported_kind_count']}**",
        f"- Claim-scope warnings: **{summary['claim_scope_warnings']}**",
        f"- Total warnings: **{summary['warnings']}**",
        "",
        "## Active tracks",
        "",
        "| Track | Criteria | Strongest | Weakest | Maturity floor | Thin ratio | Unsupported | Claim warnings | Recommendation |",
        "|---|---:|---:|---:|---|---:|---:|---:|---|",
    ]
    for track in report["tracks"]:
        strongest = "none" if track["strongest_criterion_strength"] is None else str(track["strongest_criterion_strength"])
        weakest = "none" if track["weakest_criterion_strength"] is None else str(track["weakest_criterion_strength"])
        lines.append(
            "| {id} | {count} | {strongest} | {weakest} | {maturity} | {thin:.0%} | {unsupported} | {claim_warnings} | {rec} |".format(
                id=track["id"],
                count=track["criterion_count"],
                strongest=strongest,
                weakest=weakest,
                maturity=track["maturity"],
                thin=float(track["thin_ratio"]),
                unsupported=track["unsupported_kind_count"],
                claim_warnings=track["claim_scope_warnings"],
                rec=track["recommended_claim"].replace("|", "/"),
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
        lines.append(f"- **{item['strength']}** — {item['claim_maturity']}")
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
