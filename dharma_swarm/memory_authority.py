"""Memory authority review for census outputs.

The census measures surfaces. This module checks whether the hot surfaces
have explicit authority decisions before later retrieval or retention code
trusts them.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from dharma_swarm.memory_census import build_inventory, scan

MANIFEST_VERSION = 1


@dataclass(frozen=True)
class AuthorityFinding:
    category: str
    severity: str
    authority_id: str
    surface_name: str
    message: str
    surface_id: str = ""


@dataclass(frozen=True)
class AuthorityReview:
    approved: list[AuthorityFinding] = field(default_factory=list)
    needs_owner: list[AuthorityFinding] = field(default_factory=list)
    misclassified: list[AuthorityFinding] = field(default_factory=list)
    dangerous_context_source: list[AuthorityFinding] = field(default_factory=list)
    warnings: list[AuthorityFinding] = field(default_factory=list)

    @property
    def failed(self) -> bool:
        return bool(self.needs_owner or self.misclassified or self.dangerous_context_source)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def default_manifest_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path(__file__).resolve().parents[1]
    return root / "docs" / "governance" / "memory_authority_manifest.json"


def load_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    version = int(payload.get("version", 0))
    if version != MANIFEST_VERSION:
        raise ValueError(f"Unsupported memory authority manifest version: {version}")
    if not isinstance(payload.get("surfaces"), list):
        raise ValueError("Manifest must contain a 'surfaces' list")
    return payload


def load_census(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        payload = json.loads(text)
        return list(payload.get("surfaces", []))
    surfaces: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if "surface_id" in row:
            surfaces.append(row)
    return surfaces


def _matches(entry: dict[str, Any], surface: dict[str, Any]) -> bool:
    surface_ids = set(entry.get("surface_ids") or [])
    if surface_ids and surface.get("surface_id") in surface_ids:
        return True
    match = dict(entry.get("match") or {})
    names = set(match.get("names") or [])
    substrates = set(match.get("substrates") or [])
    path_contains = list(match.get("path_contains") or [])
    if names and surface.get("name") not in names:
        return False
    if substrates and surface.get("substrate") not in substrates:
        return False
    paths = " ".join(surface.get("paths") or [])
    if path_contains and not all(fragment in paths for fragment in path_contains):
        return False
    return bool(names or substrates or path_contains)


def _finding(
    category: str,
    severity: str,
    entry: dict[str, Any],
    surface: dict[str, Any] | None,
    message: str,
) -> AuthorityFinding:
    return AuthorityFinding(
        category=category,
        severity=severity,
        authority_id=str(entry.get("authority_id", "unmanifested")),
        surface_name=str(surface.get("name", "") if surface else ""),
        surface_id=str(surface.get("surface_id", "") if surface else ""),
        message=message,
    )


def _index_manifest(
    manifest: dict[str, Any],
    surfaces: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], set[str]]:
    matches: dict[str, list[dict[str, Any]]] = {}
    covered: set[str] = set()
    for entry in manifest.get("surfaces", []):
        authority_id = str(entry.get("authority_id", ""))
        found = [surface for surface in surfaces if _matches(entry, surface)]
        matches[authority_id] = found
        covered.update(str(surface.get("surface_id", "")) for surface in found)
    return matches, covered


def review_authority(
    surfaces: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> AuthorityReview:
    approved: list[AuthorityFinding] = []
    needs_owner: list[AuthorityFinding] = []
    misclassified: list[AuthorityFinding] = []
    dangerous: list[AuthorityFinding] = []
    warnings: list[AuthorityFinding] = []

    matches, covered_ids = _index_manifest(manifest, surfaces)

    for entry in manifest.get("surfaces", []):
        authority_id = str(entry.get("authority_id", ""))
        found = matches.get(authority_id, [])
        if not found:
            warnings.append(
                _finding("warnings", "WARN", entry, None, "manifest entry matched no census surface")
            )
            continue

        for surface in found:
            expected_role = entry.get("expected_surface_role")
            authority_role = entry.get("authority_role")
            session_policy = entry.get("session_start_context")
            truth_authority = bool(entry.get("truth_authority", False))
            owner = str(entry.get("owner", "")).strip()
            status = str(entry.get("status", "active"))
            allowed_writers = list(entry.get("allowed_writers") or [])

            if not owner:
                needs_owner.append(
                    _finding("needs_owner", "FAIL", entry, surface, "authority entry has no owner")
                )
                continue

            fixed_roles = {
                "lancedb": "projection_index",
                "conversation_log": "raw_exhaust_audit",
                "smriti": "operator_session_memory",
                "cabinet": "human_curated_high_trust",
            }
            required_authority_role = fixed_roles.get(authority_id)
            if required_authority_role and authority_role != required_authority_role:
                misclassified.append(
                    _finding(
                        "misclassified",
                        "FAIL",
                        entry,
                        surface,
                        f"{authority_id} authority_role must be {required_authority_role!r}",
                    )
                )
                continue

            if expected_role and surface.get("role") != expected_role:
                misclassified.append(
                    _finding(
                        "misclassified",
                        "FAIL",
                        entry,
                        surface,
                        f"surface role is {surface.get('role')!r}; expected {expected_role!r}",
                    )
                )
                continue

            if status == "planned_future" and surface.get("role") != "dormant_promise":
                misclassified.append(
                    _finding(
                        "misclassified",
                        "FAIL",
                        entry,
                        surface,
                        "planned future surface has runtime authority evidence",
                    )
                )
                continue

            if surface.get("role") == "dormant_promise" and status != "planned_future":
                warnings.append(
                    _finding(
                        "warnings",
                        "WARN",
                        entry,
                        surface,
                        "dormant promise is not marked planned_future",
                    )
                )

            if authority_role in {"projection_index", "raw_exhaust_audit", "planned_future"}:
                if session_policy not in {"deny", "allow_operator_only"}:
                    dangerous.append(
                        _finding(
                            "dangerous_context_source",
                            "FAIL",
                            entry,
                            surface,
                            f"{authority_role} cannot be direct SessionStart context",
                        )
                    )
                    continue
                if truth_authority:
                    dangerous.append(
                        _finding(
                            "dangerous_context_source",
                            "FAIL",
                            entry,
                            surface,
                            f"{authority_role} cannot be a truth authority",
                        )
                    )
                    continue

            if authority_role == "human_curated_high_trust" and allowed_writers:
                dangerous.append(
                    _finding(
                        "dangerous_context_source",
                        "FAIL",
                        entry,
                        surface,
                        "human-curated Cabinet cannot list autonomous writers",
                    )
                )
                continue

            if authority_role == "operator_session_memory" and truth_authority:
                dangerous.append(
                    _finding(
                        "dangerous_context_source",
                        "FAIL",
                        entry,
                        surface,
                        "Smriti/operator memory cannot be canonical swarm truth",
                    )
                )
                continue

            approved.append(
                _finding("approved", "PASS", entry, surface, "authority decision covers surface")
            )

    for surface in surfaces:
        surface_id = str(surface.get("surface_id", ""))
        if surface_id in covered_ids:
            continue
        if surface.get("risk") == "critical" and surface.get("verification_status") == "needs_owner":
            needs_owner.append(
                AuthorityFinding(
                    category="needs_owner",
                    severity="FAIL",
                    authority_id="unmanifested",
                    surface_name=str(surface.get("name", "")),
                    surface_id=surface_id,
                    message="critical needs-owner surface is not covered by manifest",
                )
            )

    return AuthorityReview(
        approved=approved,
        needs_owner=needs_owner,
        misclassified=misclassified,
        dangerous_context_source=dangerous,
        warnings=warnings,
    )


def render_review(review: AuthorityReview) -> str:
    lines = ["# Memory Authority Review", ""]
    sections = (
        ("Approved", review.approved),
        ("Needs Owner", review.needs_owner),
        ("Misclassified", review.misclassified),
        ("Dangerous Context Source", review.dangerous_context_source),
        ("Warnings", review.warnings),
    )
    for title, findings in sections:
        lines.extend([f"## {title} ({len(findings)})", ""])
        if not findings:
            lines.append("- none")
        for finding in findings:
            label = finding.surface_name or finding.authority_id
            lines.append(
                f"- {finding.severity}: {label} [{finding.authority_id}] - {finding.message}"
            )
        lines.append("")
    lines.append(f"Verdict: {'FAIL' if review.failed else 'PASS'}")
    return "\n".join(lines)


def _load_or_scan(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.census:
        return load_census(Path(args.census).resolve())
    repo_root = Path(args.repo).resolve() if args.repo else None
    home = Path(args.home).resolve() if args.home else None
    return build_inventory(scan(repo_root=repo_root, home=home))["surfaces"]


def _cmd_review(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo).resolve() if args.repo else None
    manifest_path = Path(args.manifest).resolve() if args.manifest else default_manifest_path(repo_root)
    surfaces = _load_or_scan(args)
    manifest = load_manifest(manifest_path)
    review = review_authority(surfaces, manifest)
    if args.json:
        print(json.dumps(review.to_dict(), indent=2, sort_keys=True))
    else:
        print(render_review(review))
    if review.failed:
        return 1
    if args.fail_on_warnings and review.warnings:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="memory_authority")
    sub = parser.add_subparsers(dest="cmd", required=True)

    review = sub.add_parser("review", help="Review memory census against authority manifest.")
    review.add_argument("--census", default=None)
    review.add_argument("--manifest", default=None)
    review.add_argument("--repo", default=None)
    review.add_argument("--home", default=None)
    review.add_argument("--json", action="store_true")
    review.add_argument("--fail-on-warnings", action="store_true")
    review.set_defaults(func=_cmd_review)

    ns = parser.parse_args(argv)
    return ns.func(ns)


if __name__ == "__main__":
    sys.exit(main())
