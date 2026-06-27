#!/usr/bin/env python3
"""Read-only Semantic Commons and agent-admission verifier."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - exercised only in broken envs
    yaml = None  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[2]
OBJECTS_PATH = Path("docs/ontology/semantic_objects.yaml")
ALIASES_PATH = Path("docs/ontology/semantic_aliases.yaml")
ORIENTATION_PATH = Path("docs/ontology/session_orientation.yaml")

ACTIVE_LIFECYCLES = {"seed", "working", "preferred", "canonical"}
ACTIVE_ALIAS_STATUSES = {"active", "seed", "working", "preferred", "canonical"}
BLOCKED_LIFECYCLES = {"deprecated", "forbidden"}
API_NAME_RE = re.compile(r"^dharma\.[a-z][a-z0-9_]*\.[A-Z][A-Za-z0-9]*$")
VERSIONED_NAME_RE = re.compile(r"(?:\.v[0-9]+|_v[0-9]+)$")
AGENT_UID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


@dataclass(frozen=True)
class Finding:
    check: str
    severity: str
    path: str
    detail: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_yaml(path: Path) -> Any:
    if yaml is None:
        raise RuntimeError("PyYAML is required for Semantic Commons checks")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _load_structured(path: Path) -> Any:
    if path.suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    return _load_yaml(path)


def _normalize_alias(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _compact_alias(value: str) -> str:
    return re.sub(r"[-_\s]+", "", _normalize_alias(value))


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _alias_entries(aliases_payload: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for item in _as_list(aliases_payload.get("aliases")):
        if isinstance(item, dict):
            entries.append(item)
    return entries


def _forbidden_aliases(
    objects: list[dict[str, Any]], aliases_payload: dict[str, Any]
) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for obj in objects:
        canonical_id = str(obj.get("id") or "")
        for alias in _as_list(obj.get("forbidden_aliases")):
            key = (_normalize_alias(str(alias)), canonical_id)
            if key not in seen:
                seen.add(key)
                records.append({"alias": str(alias), "canonical_id": canonical_id})
    for item in _as_list(aliases_payload.get("forbidden_aliases")):
        if isinstance(item, dict):
            alias = str(item.get("alias") or "")
            canonical_id = str(item.get("canonical_id") or "")
            key = (_normalize_alias(alias), canonical_id)
            if key not in seen:
                seen.add(key)
                records.append({"alias": alias, "canonical_id": canonical_id})
    return [item for item in records if item["alias"]]


def _source_exists(repo_root: Path, source_path: str) -> bool:
    if not source_path:
        return False
    if "*" in source_path:
        return bool(list(repo_root.glob(source_path)))
    return (repo_root / source_path).exists()


def _identity_files(repo_root: Path) -> list[Path]:
    files = []
    files.extend(repo_root.glob("docs/agents/*/agent.seed.yaml"))
    files.extend(repo_root.glob("examples/agents/*.registration.json"))
    return sorted(path for path in files if path.is_file())


def _a2a_card_files(repo_root: Path) -> list[Path]:
    files = []
    files.extend(repo_root.glob("docs/agents/**/*agent_card*.json"))
    files.extend(repo_root.glob("examples/agents/**/*agent_card*.json"))
    return sorted(path for path in files if path.is_file())


def _agent_uid_occurrences(repo_root: Path) -> list[dict[str, str]]:
    occurrences: list[dict[str, str]] = []
    for path in _identity_files(repo_root):
        try:
            payload = _load_structured(path)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        agent_uid = str(payload.get("agent_uid") or "").strip()
        if agent_uid:
            occurrences.append(
                {
                    "agent_uid": agent_uid,
                    "path": path.relative_to(repo_root).as_posix(),
                    "kind": "active_identity",
                }
            )
    for path in _a2a_card_files(repo_root):
        try:
            payload = _load_structured(path)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            continue
        agent_uid = str(metadata.get("agent_uid") or "").strip()
        if agent_uid:
            occurrences.append(
                {
                    "agent_uid": agent_uid,
                    "path": path.relative_to(repo_root).as_posix(),
                    "kind": "a2a_card",
                }
            )
    return occurrences


def _duplicates(items: list[dict[str, str]], field: str) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for item in items:
        value = item.get(field, "")
        if not value:
            continue
        found.setdefault(value, []).append(item.get("path", "unknown"))
    return {key: paths for key, paths in found.items() if len(paths) > 1}


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(
                min(
                    previous[j] + 1,
                    current[j - 1] + 1,
                    previous[j - 1] + (ca != cb),
                )
            )
        previous = current
    return previous[-1]


def validate_semantic_commons(repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    errors: list[Finding] = []
    warnings: list[Finding] = []
    objects_path = repo_root / OBJECTS_PATH
    aliases_path = repo_root / ALIASES_PATH
    orientation_path = repo_root / ORIENTATION_PATH

    for path in (objects_path, aliases_path, orientation_path):
        if not path.exists():
            errors.append(
                Finding(
                    "required_file",
                    "error",
                    path.relative_to(repo_root).as_posix(),
                    "required Semantic Commons artifact is missing",
                )
            )

    objects_payload: dict[str, Any] = {}
    aliases_payload: dict[str, Any] = {}
    orientation_payload: dict[str, Any] = {}
    try:
        if objects_path.exists():
            objects_payload = _load_yaml(objects_path)
        if aliases_path.exists():
            aliases_payload = _load_yaml(aliases_path)
        if orientation_path.exists():
            orientation_payload = _load_yaml(orientation_path)
    except Exception as exc:
        errors.append(
            Finding(
                "yaml_parse",
                "error",
                "docs/ontology",
                f"failed to parse Semantic Commons YAML: {exc}",
            )
        )

    objects = [item for item in _as_list(objects_payload.get("objects")) if isinstance(item, dict)]
    lifecycle_values = set(_as_list(objects_payload.get("lifecycle_values")))
    object_ids: dict[str, dict[str, Any]] = {}
    duplicate_ids: dict[str, int] = {}
    for obj in objects:
        canonical_id = str(obj.get("id") or "")
        if not canonical_id:
            errors.append(
                Finding(
                    "object_id",
                    "error",
                    OBJECTS_PATH.as_posix(),
                    "object is missing id",
                )
            )
            continue
        if canonical_id in object_ids:
            duplicate_ids[canonical_id] = duplicate_ids.get(canonical_id, 1) + 1
        object_ids[canonical_id] = obj

    for canonical_id, count in duplicate_ids.items():
        errors.append(
            Finding(
                "duplicate_canonical_id",
                "error",
                OBJECTS_PATH.as_posix(),
                f"{canonical_id} appears {count} times",
            )
        )

    required_fields = {
        "id",
        "canonical_name",
        "api_name",
        "lifecycle",
        "owner_surface",
        "authority_level",
        "source_path",
        "aliases",
        "forbidden_aliases",
        "supersedes",
        "superseded_by",
    }
    for obj in objects:
        canonical_id = str(obj.get("id") or "<missing>")
        missing = sorted(field for field in required_fields if field not in obj)
        if missing:
            errors.append(
                Finding(
                    "required_object_fields",
                    "error",
                    OBJECTS_PATH.as_posix(),
                    f"{canonical_id} missing fields: {', '.join(missing)}",
                )
            )
        lifecycle = str(obj.get("lifecycle") or "")
        if lifecycle not in lifecycle_values:
            errors.append(
                Finding(
                    "lifecycle",
                    "error",
                    OBJECTS_PATH.as_posix(),
                    f"{canonical_id} lifecycle {lifecycle!r} is not allowed",
                )
            )
        api_name = str(obj.get("api_name") or "")
        if obj.get("public_ontology", True) and not API_NAME_RE.match(api_name):
            errors.append(
                Finding(
                    "adr_008_api_name",
                    "error",
                    OBJECTS_PATH.as_posix(),
                    f"{canonical_id} api_name {api_name!r} violates ADR-008",
                )
            )
        if VERSIONED_NAME_RE.search(api_name):
            errors.append(
                Finding(
                    "versioned_api_name",
                    "error",
                    OBJECTS_PATH.as_posix(),
                    f"{canonical_id} api_name {api_name!r} has a version suffix",
                )
            )
        if not _source_exists(repo_root, str(obj.get("source_path") or "")):
            warnings.append(
                Finding(
                    "source_path_exists",
                    "warning",
                    OBJECTS_PATH.as_posix(),
                    f"{canonical_id} source_path does not currently resolve",
                )
            )

    alias_entries = _alias_entries(aliases_payload)
    alias_targets: dict[str, set[str]] = {}
    aliases_by_target: dict[str, set[str]] = {}
    for entry in alias_entries:
        alias = str(entry.get("alias") or "")
        canonical_id = str(entry.get("canonical_id") or "")
        if not alias or not canonical_id:
            errors.append(
                Finding(
                    "alias_record",
                    "error",
                    ALIASES_PATH.as_posix(),
                    "alias records require alias and canonical_id",
                )
            )
            continue
        if canonical_id not in object_ids:
            errors.append(
                Finding(
                    "alias_target",
                    "error",
                    ALIASES_PATH.as_posix(),
                    f"alias {alias!r} points at unknown {canonical_id}",
                )
            )
        if str(entry.get("status") or "active") in BLOCKED_LIFECYCLES:
            continue
        norm = _normalize_alias(alias)
        alias_targets.setdefault(norm, set()).add(canonical_id)
        aliases_by_target.setdefault(canonical_id, set()).add(norm)

    for alias, targets in alias_targets.items():
        active_targets = {
            target
            for target in targets
            if str(object_ids.get(target, {}).get("lifecycle") or "") in ACTIVE_LIFECYCLES
        }
        if len(active_targets) > 1:
            errors.append(
                Finding(
                    "alias_collision",
                    "error",
                    ALIASES_PATH.as_posix(),
                    f"alias {alias!r} resolves to {sorted(active_targets)}",
                )
            )

    for obj in objects:
        canonical_id = str(obj.get("id") or "")
        registered = aliases_by_target.get(canonical_id, set())
        for alias in _as_list(obj.get("aliases")):
            norm = _normalize_alias(str(alias))
            if norm not in registered:
                errors.append(
                    Finding(
                        "object_alias_registered",
                        "error",
                        ALIASES_PATH.as_posix(),
                        f"{canonical_id} alias {alias!r} is not in central alias registry",
                    )
                )

    for target, aliases in aliases_by_target.items():
        for alias in aliases:
            if "." in alias or " " in alias:
                continue
            if "-" in alias:
                variant = alias.replace("-", "_")
                if variant not in aliases:
                    errors.append(
                        Finding(
                            "separator_variant_registered",
                            "error",
                            ALIASES_PATH.as_posix(),
                            f"{target} registers {alias!r} without {variant!r}",
                        )
                    )
            if "_" in alias:
                variant = alias.replace("_", "-")
                if variant not in aliases:
                    errors.append(
                        Finding(
                            "separator_variant_registered",
                            "error",
                            ALIASES_PATH.as_posix(),
                            f"{target} registers {alias!r} without {variant!r}",
                        )
                    )

    forbidden = _forbidden_aliases(objects, aliases_payload)
    active_aliases = sorted(alias_targets)
    for item in forbidden:
        alias = _normalize_alias(item["alias"])
        forbidden_target = str(item.get("canonical_id") or "")
        if alias in alias_targets:
            errors.append(
                Finding(
                    "forbidden_alias_registered",
                    "error",
                    ALIASES_PATH.as_posix(),
                    f"forbidden alias {item['alias']!r} is registered as active",
                )
            )
        for active in active_aliases:
            if _compact_alias(alias) == _compact_alias(active):
                continue
            active_targets = alias_targets.get(active, set())
            if active_targets and active_targets <= {forbidden_target}:
                continue
            distance = _levenshtein(_compact_alias(alias), _compact_alias(active))
            if len(alias) >= 5 and distance <= 2:
                warnings.append(
                    Finding(
                        "typo_distance_collision",
                        "warning",
                        ALIASES_PATH.as_posix(),
                        f"forbidden alias {item['alias']!r} is close to active alias {active!r}",
                    )
                )

    routes = [item for item in _as_list(orientation_payload.get("routes")) if isinstance(item, dict)]
    route_ids = {str(route.get("id") or ""): route for route in routes}
    for obj in objects:
        route_id = str(obj.get("orientation_route") or "")
        if route_id and route_id not in route_ids:
            errors.append(
                Finding(
                    "orientation_route_exists",
                    "error",
                    OBJECTS_PATH.as_posix(),
                    f"{obj.get('id')} points at unknown route {route_id}",
                )
            )

    for route_id, route in route_ids.items():
        layers = [layer for layer in _as_list(route.get("layers")) if isinstance(layer, dict)]
        layer_ids = [str(layer.get("id") or "") for layer in layers]
        for required in ("L0", "L1", "L2"):
            if required not in layer_ids:
                errors.append(
                    Finding(
                        "orientation_required_layers",
                        "error",
                        ORIENTATION_PATH.as_posix(),
                        f"{route_id} is missing {required}",
                    )
                )
        if layer_ids and str(layers[0].get("source_kind") or "") == "corpus_search":
            errors.append(
                Finding(
                    "orientation_search_not_first",
                    "error",
                    ORIENTATION_PATH.as_posix(),
                    f"{route_id} starts with corpus search",
                )
            )

    uid_occurrences = _agent_uid_occurrences(repo_root)
    duplicate_uids = _duplicates(
        [item for item in uid_occurrences if item["kind"] == "active_identity"],
        "agent_uid",
    )
    duplicate_cards = _duplicates(
        [item for item in uid_occurrences if item["kind"] == "a2a_card"],
        "agent_uid",
    )
    for agent_uid, paths in duplicate_uids.items():
        errors.append(
            Finding(
                "duplicate_active_agent_uid",
                "error",
                "docs/agents",
                f"{agent_uid} appears in active identity files: {', '.join(paths)}",
            )
        )
    for agent_uid, paths in duplicate_cards.items():
        errors.append(
            Finding(
                "duplicate_a2a_card_agent_uid",
                "error",
                "docs/agents",
                f"{agent_uid} appears in A2A card files: {', '.join(paths)}",
            )
        )

    return {
        "generated_at": _utc_now(),
        "repo_root": str(repo_root),
        "objects_file": OBJECTS_PATH.as_posix(),
        "aliases_file": ALIASES_PATH.as_posix(),
        "orientation_file": ORIENTATION_PATH.as_posix(),
        "object_count": len(objects),
        "alias_count": len(alias_entries),
        "orientation_route_count": len(routes),
        "active_agent_uid_count": len(
            [item for item in uid_occurrences if item["kind"] == "active_identity"]
        ),
        "a2a_card_uid_count": len(
            [item for item in uid_occurrences if item["kind"] == "a2a_card"]
        ),
        "errors": [asdict(item) for item in errors],
        "warnings": [asdict(item) for item in warnings],
        "objects": objects,
        "aliases": alias_entries,
        "routes": routes,
        "agent_uid_occurrences": uid_occurrences,
    }


def validate_candidate(
    report: dict[str, Any],
    *,
    agent_uid: str,
    canonical_id: str,
    orientation_route: str,
    name_drift_receipt: Path | None,
) -> list[Finding]:
    findings: list[Finding] = []
    objects = {
        str(obj.get("id") or ""): obj
        for obj in _as_list(report.get("objects"))
        if isinstance(obj, dict)
    }
    alias_entries = [
        entry for entry in _as_list(report.get("aliases")) if isinstance(entry, dict)
    ]
    route_ids = {
        str(route.get("id") or "")
        for route in _as_list(report.get("routes"))
        if isinstance(route, dict)
    }

    if not AGENT_UID_RE.match(agent_uid):
        findings.append(
            Finding(
                "candidate_agent_uid_shape",
                "error",
                "candidate",
                f"agent_uid {agent_uid!r} must be lowercase alnum with -/_ separators",
            )
        )

    obj = objects.get(canonical_id)
    if not obj:
        findings.append(
            Finding(
                "candidate_canonical_object",
                "error",
                OBJECTS_PATH.as_posix(),
                f"canonical object {canonical_id!r} is not registered",
            )
        )
    elif str(obj.get("lifecycle") or "") not in ACTIVE_LIFECYCLES:
        findings.append(
            Finding(
                "candidate_lifecycle",
                "error",
                OBJECTS_PATH.as_posix(),
                f"{canonical_id} lifecycle {obj.get('lifecycle')!r} is not admissible",
            )
        )

    alias_targets = {
        str(entry.get("canonical_id") or "")
        for entry in alias_entries
        if _normalize_alias(str(entry.get("alias") or "")) == _normalize_alias(agent_uid)
        and str(entry.get("status") or "active") in ACTIVE_ALIAS_STATUSES
    }
    if canonical_id not in alias_targets:
        findings.append(
            Finding(
                "candidate_alias_registered",
                "error",
                ALIASES_PATH.as_posix(),
                f"agent_uid {agent_uid!r} is not an active alias for {canonical_id}",
            )
        )

    route_id = orientation_route or str((obj or {}).get("orientation_route") or "")
    if not route_id:
        findings.append(
            Finding(
                "candidate_orientation_route",
                "error",
                ORIENTATION_PATH.as_posix(),
                "candidate did not declare an orientation route",
            )
        )
    elif route_id not in route_ids:
        findings.append(
            Finding(
                "candidate_orientation_route",
                "error",
                ORIENTATION_PATH.as_posix(),
                f"orientation route {route_id!r} is not registered",
            )
        )
    elif obj and obj.get("orientation_route") and obj.get("orientation_route") != route_id:
        findings.append(
            Finding(
                "candidate_orientation_route",
                "error",
                OBJECTS_PATH.as_posix(),
                f"{canonical_id} declares {obj.get('orientation_route')!r}, not {route_id!r}",
            )
        )

    if name_drift_receipt is None:
        findings.append(
            Finding(
                "candidate_name_drift_receipt",
                "error",
                "candidate",
                "candidate requires --name-drift-receipt",
            )
        )
    elif not name_drift_receipt.exists():
        findings.append(
            Finding(
                "candidate_name_drift_receipt",
                "error",
                str(name_drift_receipt),
                "name-drift preflight receipt does not exist",
            )
        )
    else:
        try:
            receipt = json.loads(name_drift_receipt.read_text(encoding="utf-8"))
            if "hit_count" not in receipt:
                findings.append(
                    Finding(
                        "candidate_name_drift_receipt",
                        "error",
                        str(name_drift_receipt),
                        "receipt is missing hit_count",
                    )
                )
        except Exception as exc:
            findings.append(
                Finding(
                    "candidate_name_drift_receipt",
                    "error",
                    str(name_drift_receipt),
                    f"receipt is not valid JSON: {exc}",
                )
            )

    occurrences = [
        item
        for item in _as_list(report.get("agent_uid_occurrences"))
        if isinstance(item, dict) and item.get("agent_uid") == agent_uid
    ]
    active_paths = [str(item.get("path")) for item in occurrences if item.get("kind") == "active_identity"]
    card_paths = [str(item.get("path")) for item in occurrences if item.get("kind") == "a2a_card"]
    if len(active_paths) > 1:
        findings.append(
            Finding(
                "candidate_duplicate_active_agent_uid",
                "error",
                "docs/agents",
                f"{agent_uid} appears in multiple active identity files: {', '.join(active_paths)}",
            )
        )
    if len(card_paths) > 1:
        findings.append(
            Finding(
                "candidate_duplicate_a2a_card_agent_uid",
                "error",
                "docs/agents",
                f"{agent_uid} appears in multiple A2A card files: {', '.join(card_paths)}",
            )
        )
    return findings


def render_text(report: dict[str, Any]) -> str:
    lines = [
        "Agent Admission Check",
        f"Generated: {report['generated_at']}",
        f"Objects: {report['object_count']}",
        f"Aliases: {report['alias_count']}",
        f"Orientation routes: {report['orientation_route_count']}",
        f"Active agent_uids: {report['active_agent_uid_count']}",
        f"A2A card uids: {report['a2a_card_uid_count']}",
        f"Errors: {len(report['errors'])}",
        f"Warnings: {len(report['warnings'])}",
    ]
    if report["errors"]:
        lines.append("")
        lines.append("Errors:")
        for item in report["errors"]:
            lines.append(f"- [{item['check']}] {item['path']}: {item['detail']}")
    if report["warnings"]:
        lines.append("")
        lines.append("Warnings:")
        for item in report["warnings"]:
            lines.append(f"- [{item['check']}] {item['path']}: {item['detail']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print JSON")
    parser.add_argument("--agent-uid", help="candidate persistent agent uid")
    parser.add_argument("--canonical-id", help="candidate Semantic Commons object id")
    parser.add_argument(
        "--orientation-route",
        default="",
        help="candidate orientation route id; defaults to object route",
    )
    parser.add_argument(
        "--name-drift-receipt",
        type=Path,
        help="JSON receipt from scripts/governance/name_drift_preflight.py",
    )
    args = parser.parse_args(argv)

    report = validate_semantic_commons(REPO_ROOT)
    if args.agent_uid or args.canonical_id or args.name_drift_receipt:
        if not args.agent_uid or not args.canonical_id:
            report["errors"].append(
                asdict(
                    Finding(
                        "candidate_args",
                        "error",
                        "candidate",
                        "--agent-uid and --canonical-id are required together",
                    )
                )
            )
        else:
            candidate_findings = validate_candidate(
                report,
                agent_uid=args.agent_uid,
                canonical_id=args.canonical_id,
                orientation_route=args.orientation_route,
                name_drift_receipt=args.name_drift_receipt,
            )
            report["candidate"] = {
                "agent_uid": args.agent_uid,
                "canonical_id": args.canonical_id,
                "orientation_route": args.orientation_route,
                "name_drift_receipt": str(args.name_drift_receipt or ""),
                "errors": [asdict(item) for item in candidate_findings],
            }
            report["errors"].extend(asdict(item) for item in candidate_findings)

    public_report = dict(report)
    public_report.pop("objects", None)
    public_report.pop("aliases", None)
    public_report.pop("routes", None)
    if args.json:
        print(json.dumps(public_report, indent=2, sort_keys=True))
    else:
        print(render_text(public_report))
    return 1 if public_report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
