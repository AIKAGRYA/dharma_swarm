#!/usr/bin/env python3
"""Record and read human-authoritative YDS quality ratings.

This CLI writes an append-only local JSONL ledger. It does not run git, does
not call network services, and does not assign ratings without an explicit
human-provided ``--rating`` value.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_LEDGER_PATH = Path.home() / ".dharma" / "yds" / "human_quality_ratings.jsonl"
SCHEMA_VERSION = "human_yds_rating.v1"
DEFAULT_OPERATOR_ID = "dhyana"
KNOWN_URI_SCHEMES = (
    "repo://",
    "git://",
    "pr://",
    "agentops://",
    "kaizen://",
    "external://",
)
VALID_ARTIFACT_KINDS = {
    "agentops_report",
    "kaizen_review",
    "commit",
    "pull_request",
    "file",
    "daily_brief",
    "operator_artifact",
    "external_artifact",
}
_YDS_RE = re.compile(r"^5\.(6|7|8|9|10|11|12|13|14|15)([abcd])?$")


class HumanYdsLedgerError(RuntimeError):
    """Raised when a human YDS ledger operation fails closed."""


@dataclass(frozen=True)
class ArtifactRef:
    kind: str
    uri: str
    title: str

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "uri": self.uri, "title": self.title}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_rating_value(value: str) -> str:
    rating = str(value or "").strip()
    if not _YDS_RE.fullmatch(rating):
        raise HumanYdsLedgerError(
            "rating must be a YDS value from 5.6 through 5.15, "
            "optionally suffixed with a/b/c/d"
        )
    return rating


def validate_artifact_kind(kind: str) -> str:
    normalized = str(kind or "").strip()
    if normalized not in VALID_ARTIFACT_KINDS:
        allowed = ", ".join(sorted(VALID_ARTIFACT_KINDS))
        raise HumanYdsLedgerError(f"artifact kind must be one of: {allowed}")
    return normalized


def require_note(note: str) -> str:
    normalized = str(note or "").strip()
    if not normalized:
        raise HumanYdsLedgerError("human note is required")
    return normalized


def normalize_artifact_uri(raw: str, *, repo_root: Path | None = None) -> str:
    value = str(raw or "").strip()
    if not value:
        raise HumanYdsLedgerError("artifact is required")
    if value.startswith(KNOWN_URI_SCHEMES):
        return value
    path = Path(value).expanduser()
    root = (repo_root or Path.cwd()).resolve()
    if path.is_absolute():
        try:
            rel = path.resolve().relative_to(root)
        except ValueError:
            return "external://" + path.as_posix()
    else:
        rel = path
    normalized = rel.as_posix().lstrip("./")
    if not normalized or normalized == "." or normalized.startswith("../"):
        raise HumanYdsLedgerError("artifact path must be inside the repo or use a URI scheme")
    return "repo://" + normalized


def normalize_evidence_refs(values: list[str], *, repo_root: Path | None = None) -> list[str]:
    refs = [normalize_artifact_uri(value, repo_root=repo_root) for value in values]
    return sorted(dict.fromkeys(refs))


def make_rating_id(record_seed: dict[str, Any]) -> str:
    created_at = str(record_seed.get("created_at") or utc_now_iso())
    stamp = (
        created_at.replace("-", "")
        .replace(":", "")
        .replace("+00:00", "Z")
        .replace(".", "")
    )
    digest = hashlib.blake2s(
        json.dumps(record_seed, sort_keys=True, ensure_ascii=True).encode("utf-8"),
        digest_size=4,
    ).hexdigest()
    return f"yds_{stamp}_{digest}"


def build_rating_record(
    *,
    artifact: str,
    kind: str,
    rating: str,
    note: str,
    operator_id: str = DEFAULT_OPERATOR_ID,
    title: str = "",
    evidence_refs: list[str] | None = None,
    tags: list[str] | None = None,
    supersedes_rating_id: str | None = None,
    private_note: str = "",
    created_at: str | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    created = created_at or utc_now_iso()
    artifact_ref = ArtifactRef(
        kind=validate_artifact_kind(kind),
        uri=normalize_artifact_uri(artifact, repo_root=repo_root),
        title=str(title or "").strip(),
    )
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "rating_id": "",
        "created_at": created,
        "operator_id": str(operator_id or DEFAULT_OPERATOR_ID).strip() or DEFAULT_OPERATOR_ID,
        "rating_scale": "YDS",
        "rating_value": validate_rating_value(rating),
        "artifact": artifact_ref.to_dict(),
        "human_note": require_note(note),
        "evidence_refs": normalize_evidence_refs(evidence_refs or [], repo_root=repo_root),
        "context": {"source": "operator_cli"},
        "supersedes_rating_id": str(supersedes_rating_id).strip() if supersedes_rating_id else None,
    }
    clean_tags = sorted(
        {str(tag).strip() for tag in tags or [] if str(tag).strip()}
    )
    if clean_tags:
        record["tags"] = clean_tags
    if private_note.strip():
        record["private_note"] = private_note.strip()
    record["rating_id"] = make_rating_id(record)
    return record


def public_rating(record: dict[str, Any]) -> dict[str, Any]:
    exported = dict(record)
    exported.pop("private_note", None)
    return exported


def append_rating(ledger_path: Path, record: dict[str, Any]) -> dict[str, Any]:
    ledger_path.expanduser().parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.expanduser().open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, ensure_ascii=True) + "\n")
    return record


def read_ratings(ledger_path: Path) -> list[dict[str, Any]]:
    path = ledger_path.expanduser()
    if not path.exists():
        return []
    ratings: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            raw = line.strip()
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise HumanYdsLedgerError(
                    f"invalid JSON in {path} line {line_no}: {exc}"
                ) from exc
            if not isinstance(data, dict):
                raise HumanYdsLedgerError(f"rating line {line_no} is not an object")
            ratings.append(data)
    return ratings


def active_ratings(ratings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    superseded = {
        str(record.get("supersedes_rating_id"))
        for record in ratings
        if record.get("supersedes_rating_id")
    }
    return [
        record for record in ratings
        if str(record.get("rating_id") or "") not in superseded
    ]


def artifact_uri_for_record(record: dict[str, Any]) -> str:
    artifact = record.get("artifact")
    if not isinstance(artifact, dict):
        return ""
    return str(artifact.get("uri") or "").strip()


def latest_rating_for_artifact(
    ratings: list[dict[str, Any]],
    artifact: str,
    *,
    repo_root: Path | None = None,
) -> dict[str, Any] | None:
    target = normalize_artifact_uri(artifact, repo_root=repo_root)
    matches = [
        record for record in active_ratings(ratings)
        if artifact_uri_for_record(record) == target
    ]
    if not matches:
        return None
    return sorted(
        matches,
        key=lambda record: (
            str(record.get("created_at") or ""),
            str(record.get("rating_id") or ""),
        ),
    )[-1]


def print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ledger",
        type=Path,
        default=DEFAULT_LEDGER_PATH,
        help="Path to the append-only human YDS ledger JSONL file",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    rate = sub.add_parser("rate", help="Append one human YDS rating")
    rate.add_argument("--artifact", required=True)
    rate.add_argument("--kind", required=True)
    rate.add_argument("--rating", required=True)
    rate.add_argument("--note", required=True)
    rate.add_argument("--operator", default=DEFAULT_OPERATOR_ID)
    rate.add_argument("--title", default="")
    rate.add_argument("--evidence", action="append", default=[])
    rate.add_argument("--tag", action="append", default=[])
    rate.add_argument("--supersedes", default=None)
    rate.add_argument("--private-note", default="")

    list_cmd = sub.add_parser("list", help="List public ratings")
    list_cmd.add_argument("--include-superseded", action="store_true")

    show = sub.add_parser("show", help="Show all active public ratings for an artifact")
    show.add_argument("--artifact", required=True)

    latest = sub.add_parser("latest", help="Show latest active public rating for an artifact")
    latest.add_argument("--artifact", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "rate":
            record = build_rating_record(
                artifact=args.artifact,
                kind=args.kind,
                rating=args.rating,
                note=args.note,
                operator_id=args.operator,
                title=args.title,
                evidence_refs=args.evidence,
                tags=args.tag,
                supersedes_rating_id=args.supersedes,
                private_note=args.private_note,
            )
            append_rating(args.ledger, record)
            print_json(public_rating(record))
            return 0

        ratings = read_ratings(args.ledger)
        if args.command == "list":
            selected = ratings if args.include_superseded else active_ratings(ratings)
            print_json([public_rating(record) for record in selected])
            return 0

        if args.command == "show":
            target = normalize_artifact_uri(args.artifact)
            selected = [
                public_rating(record) for record in active_ratings(ratings)
                if artifact_uri_for_record(record) == target
            ]
            print_json(selected)
            return 0

        if args.command == "latest":
            latest_record = latest_rating_for_artifact(ratings, args.artifact)
            print_json(public_rating(latest_record) if latest_record else None)
            return 0
    except HumanYdsLedgerError as exc:
        print(f"Human YDS ledger error: {exc}")
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
