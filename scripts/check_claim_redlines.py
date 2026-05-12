#!/usr/bin/env python3
"""Triple-check red lines before a Dharma claim leaves the private repo.

This is an adapter around existing gates, not a new public-claim system.  It
checks the exact title, summary, artifact references, and optional scanned
artifact files that will be handed to the SABP/Agoa claim scaffolder.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.models import GateDecision, GateResult  # noqa: E402
from dharma_swarm.telos_gates import TelosGatekeeper  # noqa: E402


APPROVED_BOUNDARIES = {"semi_public_agora", "semi_public_sabp"}
APPROVED_STAGES = {"venture_proposal"}
MAX_SCAN_CHARS = 160_000


@dataclass(frozen=True)
class RedlineViolation:
    redline: str
    severity: str
    scope: str
    evidence: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {
            "redline": self.redline,
            "severity": self.severity,
            "scope": self.scope,
            "evidence": self.evidence,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class CandidateClaim:
    title: str
    summary: str
    stage: str
    boundary: str
    artifact_refs: tuple[str, ...]
    scan_paths: tuple[Path, ...]

    @property
    def outbound_text(self) -> str:
        refs = "\n".join(self.artifact_refs)
        return (
            f"title: {self.title}\n"
            f"summary: {self.summary}\n"
            f"stage: {self.stage}\n"
            f"boundary: {self.boundary}\n"
            f"artifact_refs:\n{refs}\n"
        )


@dataclass
class PassReport:
    pass_index: int
    name: str
    status: str = "pass"
    violations: list[RedlineViolation] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pass_index": self.pass_index,
            "name": self.name,
            "status": self.status,
            "violations": [v.to_dict() for v in self.violations],
            "evidence": self.evidence,
        }


SENSITIVE_SECRET_PATTERNS: tuple[tuple[str, str], ...] = (
    ("secret_or_api_key", r"(?i)\b(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[^'\"\s]{8,}"),
    ("openai_key", r"\bsk-(?:proj-|or-v1-)?[A-Za-z0-9_-]{16,}"),
    ("anthropic_key", r"\bsk-ant-[A-Za-z0-9_-]{16,}"),
    ("github_token", r"\bgh[pousr]_[A-Za-z0-9_]{16,}"),
    ("aws_key", r"\bAKIA[0-9A-Z]{16}\b"),
    ("slack_token", r"\bxox[abpors]-[A-Za-z0-9-]{16,}"),
    ("private_key", r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"),
)

PRIVATE_OUTBOUND_PATTERNS: tuple[tuple[str, str], ...] = (
    ("raw_private_transcripts", r"(?i)\b(raw|private)\s+transcripts?\b"),
    ("customer_names", r"(?i)\bcustomer names?\b|\bnamed customers?\b"),
    ("local_home_path", r"(?:^|[\s\"'`])(?:/Users/|/home/|~/?)[^\s\"'`]*"),
    ("dot_env_or_credentials", r"(?i)(?:^|/)(?:\.env|credentials|id_rsa|id_ed25519)(?:$|[.\s/])"),
)

AFFIRMATIVE_OVERCLAIM_PATTERNS: tuple[tuple[str, str], ...] = (
    ("unsupported_consciousness_claim", r"(?i)\b(?:dharma swarm|system|software|ai|agent)\s+(?:is|has|proves|demonstrates)\s+(?:conscious|consciousness|sentient|sentience|being)\b"),
    ("unsupported_consciousness_claim", r"(?i)\bproves?\s+(?:ai|machine|software)\s+(?:consciousness|sentience)\b"),
    ("production_ready_claim", r"(?i)\b(?:production[- ]ready|ready for production|prod[- ]ready|customer[- ]ready|enterprise[- ]ready)\b"),
    ("customer_or_revenue_traction_claim", r"(?i)\b(?:paying customers?|customer traction|revenue traction|ARR|MRR|annual recurring revenue|monthly recurring revenue)\b"),
    ("autonomous_live_self_modification_claim", r"(?i)\b(?:safely\s+)?(?:autonomous(?:ly)?\s+)?live\s+self[- ]modif(?:y|ies|ication)\b"),
    ("autonomous_live_self_modification_claim", r"(?i)\bcan\s+safely\s+(?:autonomous(?:ly)?\s+)?self[- ]modif(?:y|ies|ication)\b"),
    ("solved_agent_governance_claim", r"(?i)\b(?:solves?|solved|guarantees?|complete solution for)\s+(?:all\s+)?(?:agent governance|agentic governance|safe agents|agent safety)\b"),
)

NEGATION_MARKERS: tuple[str, ...] = (
    "no ",
    "not ",
    "does not ",
    "do not ",
    "without ",
    "cannot ",
    "can't ",
    "must not ",
    "should not ",
    "no claim",
    "makes no",
    "blocked",
    "red line",
    "forbid",
)

CHECKED_RED_LINES: tuple[str, ...] = (
    "no raw private transcripts",
    "no secrets, API keys, credentials, or local private paths in outbound refs",
    "no customer names or unevidenced customer/revenue traction claims",
    "no unsupported consciousness/sentience claims",
    "no autonomous live self-modification safety claim",
    "no production-readiness claim",
    "no broad solved-agent-governance claim",
    "semi-public SABP boundary only; no public marketing launch",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Triple-check claim red lines before SABP/Agoa submission.",
    )
    parser.add_argument("--title", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--stage", default="venture_proposal")
    parser.add_argument("--boundary", default="semi_public_agora")
    parser.add_argument("--artifact-ref", action="append", default=[])
    parser.add_argument("--scan-path", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--passes", type=int, default=3)
    parser.add_argument("--fail-on-violation", action="store_true")
    return parser


def run_redline_preflight(candidate: CandidateClaim, *, pass_count: int = 3) -> dict[str, Any]:
    scanners: tuple[tuple[str, Callable[[CandidateClaim], tuple[list[RedlineViolation], dict[str, Any]]]], ...] = (
        ("literal_sensitive_pattern_scan", _literal_sensitive_pattern_scan),
        ("boundary_and_reference_policy_scan", _boundary_and_reference_policy_scan),
        ("telos_gate_redline_scan", _telos_gate_redline_scan),
    )
    reports: list[PassReport] = []
    for idx in range(max(1, pass_count)):
        name, scanner = scanners[idx % len(scanners)]
        violations, evidence = scanner(candidate)
        reports.append(
            PassReport(
                pass_index=idx + 1,
                name=name,
                status="fail" if violations else "pass",
                violations=violations,
                evidence=evidence,
            )
        )

    violations = [violation for report in reports for violation in report.violations]
    passed = not violations
    return {
        "kind": "sabp_claim_redline_preflight",
        "version": "0.1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "pass_count": len(reports),
        "checked_red_lines": list(CHECKED_RED_LINES),
        "candidate": {
            "title": candidate.title,
            "summary_sha256": hashlib.sha256(candidate.summary.encode("utf-8")).hexdigest(),
            "stage": candidate.stage,
            "boundary": candidate.boundary,
            "artifact_refs": list(candidate.artifact_refs),
            "scan_paths": [str(path) for path in candidate.scan_paths],
        },
        "passes": [report.to_dict() for report in reports],
        "violations": [violation.to_dict() for violation in violations],
    }


def _literal_sensitive_pattern_scan(
    candidate: CandidateClaim,
) -> tuple[list[RedlineViolation], dict[str, Any]]:
    violations: list[RedlineViolation] = []
    outbound = candidate.outbound_text
    scanned_artifacts = _read_scan_paths(candidate.scan_paths)
    combined_secret_scan = outbound + "\n" + "\n".join(text for _, text in scanned_artifacts)

    for redline, pattern in SENSITIVE_SECRET_PATTERNS:
        violations.extend(_find_pattern_violations(redline, pattern, combined_secret_scan, "outbound_or_artifact"))
    for redline, pattern in PRIVATE_OUTBOUND_PATTERNS:
        violations.extend(_find_pattern_violations(redline, pattern, outbound, "outbound_claim"))
    for redline, pattern in AFFIRMATIVE_OVERCLAIM_PATTERNS:
        violations.extend(
            _find_pattern_violations(
                redline,
                pattern,
                outbound,
                "outbound_claim",
                negation_aware=True,
            )
        )
        for path, text in scanned_artifacts:
            violations.extend(
                _find_pattern_violations(
                    redline,
                    pattern,
                    text,
                    f"artifact:{path}",
                    negation_aware=True,
                )
            )

    return violations, {
        "outbound_chars": len(outbound),
        "scanned_artifact_count": len(scanned_artifacts),
        "scanned_artifact_chars": sum(len(text) for _, text in scanned_artifacts),
    }


def _boundary_and_reference_policy_scan(
    candidate: CandidateClaim,
) -> tuple[list[RedlineViolation], dict[str, Any]]:
    violations: list[RedlineViolation] = []
    if candidate.boundary not in APPROVED_BOUNDARIES:
        violations.append(
            RedlineViolation(
                "public_boundary_not_approved",
                "block",
                "boundary",
                candidate.boundary,
                "Only semi-public Agora/SABP witness is approved for this step.",
            )
        )
    if candidate.stage not in APPROVED_STAGES:
        violations.append(
            RedlineViolation(
                "claim_stage_not_approved",
                "block",
                "stage",
                candidate.stage,
                "Only venture_proposal is approved for the first witnessed claim.",
            )
        )

    for ref in candidate.artifact_refs:
        if re.search(r"(?:^|[\s\"'`])(?:/Users/|/home/|~/?)", ref):
            violations.append(
                RedlineViolation(
                    "local_private_path_in_artifact_ref",
                    "block",
                    "artifact_ref",
                    ref,
                    "Outbound artifact refs must not expose local home paths.",
                )
            )
        if re.search(r"(?i)(?:transcript|\.env|credentials|id_rsa|id_ed25519|customer)", ref):
            violations.append(
                RedlineViolation(
                    "private_or_secret_artifact_ref",
                    "block",
                    "artifact_ref",
                    ref,
                    "Outbound artifact refs must not point at transcripts, credentials, or customer material.",
                )
            )

    for path in candidate.scan_paths:
        if not path.expanduser().exists():
            violations.append(
                RedlineViolation(
                    "scan_path_missing",
                    "block",
                    "scan_path",
                    str(path),
                    "Every referenced source checked before publication must exist.",
                )
            )

    return violations, {
        "approved_boundaries": sorted(APPROVED_BOUNDARIES),
        "approved_stages": sorted(APPROVED_STAGES),
        "artifact_ref_count": len(candidate.artifact_refs),
        "scan_path_count": len(candidate.scan_paths),
    }


def _telos_gate_redline_scan(
    candidate: CandidateClaim,
) -> tuple[list[RedlineViolation], dict[str, Any]]:
    gatekeeper = TelosGatekeeper()
    result = gatekeeper.check(
        action="prepare semi-public SABP claim packet",
        content=candidate.outbound_text,
        tool_name="check_claim_redlines",
        trust_mode="external_strict",
        think_phase="before_complete",
        reflection=(
            "Risk: a semi-public claim can leak private context, overstate maturity, "
            "or imply unsafe autonomy. Verification: this preflight checks explicit "
            "red-line regexes first, then routes the exact outbound claim text through "
            "TelosGatekeeper before SABP files are written. Rollback: if any check "
            "fails, no Agora claim packet is created."
        ),
    )
    violations: list[RedlineViolation] = []
    if result.decision == GateDecision.BLOCK:
        violations.append(
            RedlineViolation(
                "telos_gate_block",
                "block",
                "telos_gatekeeper",
                result.reason,
                "TelosGatekeeper blocked the outbound claim.",
            )
        )
    for gate_name in ("SATYA", "CONSENT"):
        gate_result = result.gate_results.get(gate_name)
        if gate_result and gate_result[0] != GateResult.PASS:
            violations.append(
                RedlineViolation(
                    f"telos_{gate_name.lower()}_redline",
                    "block",
                    "telos_gatekeeper",
                    f"{gate_name}={gate_result[0].value}: {gate_result[1]}",
                    f"{gate_name} must pass before a semi-public claim is created.",
                )
            )

    return violations, {
        "decision": result.decision.value,
        "reason": result.reason,
        "gate_results": {
            name: {"result": payload[0].value, "reason": payload[1]}
            for name, payload in result.gate_results.items()
        },
    }


def _read_scan_paths(paths: tuple[Path, ...]) -> list[tuple[str, str]]:
    scanned: list[tuple[str, str]] = []
    for path in paths:
        resolved = path.expanduser()
        if not resolved.exists() or not resolved.is_file():
            continue
        text = resolved.read_text(encoding="utf-8", errors="replace")
        scanned.append((str(path), text[:MAX_SCAN_CHARS]))
    return scanned


def _find_pattern_violations(
    redline: str,
    pattern: str,
    text: str,
    scope: str,
    *,
    negation_aware: bool = False,
) -> list[RedlineViolation]:
    violations: list[RedlineViolation] = []
    for match in re.finditer(pattern, text):
        if negation_aware and _is_negated(text, match.start()):
            continue
        violations.append(
            RedlineViolation(
                redline,
                "block",
                scope,
                _excerpt(text, match.start(), match.end()),
                f"Matched red-line pattern: {pattern}",
            )
        )
    return violations


def _is_negated(text: str, match_start: int) -> bool:
    before = text[max(0, match_start - 120):match_start].lower()
    return any(marker in before for marker in NEGATION_MARKERS)


def _excerpt(text: str, start: int, end: int) -> str:
    left = max(0, start - 60)
    right = min(len(text), end + 60)
    return re.sub(r"\s+", " ", text[left:right]).strip()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    candidate = CandidateClaim(
        title=args.title,
        summary=args.summary,
        stage=args.stage,
        boundary=args.boundary,
        artifact_refs=tuple(args.artifact_ref),
        scan_paths=tuple(args.scan_path),
    )
    report = run_redline_preflight(candidate, pass_count=args.passes)
    if args.output is not None:
        output = args.output.expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.fail_on_violation and not report["passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
