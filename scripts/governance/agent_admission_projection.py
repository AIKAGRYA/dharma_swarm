#!/usr/bin/env python3
"""Generate read-only Semantic Commons notes for Obsidian/PKM."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.governance.agent_admission import validate_semantic_commons  # noqa: E402

OBJECTS_PATH = Path("docs/ontology/semantic_objects.yaml")
ALIASES_PATH = Path("docs/ontology/semantic_aliases.yaml")
ORIENTATION_PATH = Path("docs/ontology/session_orientation.yaml")
PROJECTION_PATH = Path("docs/ontology/pkm_projection.yaml")
DEFAULT_VAULT_ROOT = Path("/Users/dhyana/.dharma/knowledge/wiki/semantic-commons")
DEFAULT_MANIFEST = Path("reports/governance/semantic_commons_projection_manifest.json")


@dataclass(frozen=True)
class ProjectionFile:
    path: str
    kind: str
    canonical_object_id: str = ""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML is required for Semantic Commons projection")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _safe_slug(value: str) -> str:
    spaced = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1-\2", value.strip())
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", spaced)
    slug = re.sub(r"[^a-z0-9]+", "-", spaced.lower())
    return slug.strip("-") or "semantic-object"


def _frontmatter(data: dict[str, Any]) -> str:
    if yaml is None:
        raise RuntimeError("PyYAML is required for Semantic Commons projection")
    body = yaml.safe_dump(data, sort_keys=False, allow_unicode=False).strip()
    return f"---\n{body}\n---\n\n"


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _alias_maps(aliases_payload: dict[str, Any]) -> dict[str, list[str]]:
    aliases_by_id: dict[str, list[str]] = {}
    for item in aliases_payload.get("aliases", []):
        if not isinstance(item, dict):
            continue
        canonical_id = str(item.get("canonical_id") or "")
        alias = str(item.get("alias") or "")
        if canonical_id and alias:
            aliases_by_id.setdefault(canonical_id, []).append(alias)
    return {key: sorted(set(values), key=str.lower) for key, values in aliases_by_id.items()}


def _route_layers(orientation_payload: dict[str, Any]) -> dict[str, list[str]]:
    layers_by_route: dict[str, list[str]] = {}
    for route in orientation_payload.get("routes", []):
        if not isinstance(route, dict):
            continue
        route_id = str(route.get("id") or "")
        layers = [str(layer.get("id") or "") for layer in route.get("layers", []) if isinstance(layer, dict)]
        if route_id:
            layers_by_route[route_id] = [layer for layer in layers if layer]
    return layers_by_route


def _duplicate_aliases(aliases_payload: dict[str, Any]) -> dict[str, list[str]]:
    targets_by_alias: dict[str, set[str]] = {}
    for item in aliases_payload.get("aliases", []):
        if not isinstance(item, dict):
            continue
        alias = " ".join(str(item.get("alias") or "").lower().split())
        target = str(item.get("canonical_id") or "")
        if alias and target and str(item.get("status") or "active") != "deprecated":
            targets_by_alias.setdefault(alias, set()).add(target)
    duplicates: dict[str, list[str]] = {}
    for alias, targets in targets_by_alias.items():
        if len(targets) > 1:
            for target in targets:
                duplicates.setdefault(target, []).append(alias)
    return duplicates


def _forbidden_hits(obj: dict[str, Any], aliases: list[str]) -> list[str]:
    active = {" ".join(alias.lower().split()) for alias in aliases}
    hits = []
    for alias in obj.get("forbidden_aliases", []):
        normalized = " ".join(str(alias).lower().split())
        if normalized in active:
            hits.append(str(alias))
    return hits


def _object_note(
    obj: dict[str, Any],
    *,
    aliases: list[str],
    duplicate_aliases: list[str],
    route_layers: list[str],
    generated_at: str,
) -> str:
    canonical_id = str(obj["id"])
    orientation_route = str(obj.get("orientation_route") or "")
    forbidden_hits = _forbidden_hits(obj, aliases)
    frontmatter = {
        "title": str(obj["canonical_name"]),
        "projection_family": "semantic_commons",
        "projection_kind": "semantic_object",
        "projection_of": f"{OBJECTS_PATH.as_posix()}#{canonical_id}",
        "generated": True,
        "generated_at": generated_at,
        "canon": False,
        "canonical_object_id": canonical_id,
        "canonical_name": str(obj["canonical_name"]),
        "api_name": str(obj["api_name"]),
        "source_path": str(obj["source_path"]),
        "aliases": aliases,
        "forbidden_aliases": [str(alias) for alias in obj.get("forbidden_aliases", [])],
        "lifecycle": str(obj["lifecycle"]),
        "owner": str(obj["owner_surface"]),
        "owner_surface": str(obj["owner_surface"]),
        "authority_level": str(obj["authority_level"]),
        "orientation_route": orientation_route,
        "orientation_layers": route_layers,
        "review_state": "generated_unreviewed",
        "missing_owner": not bool(str(obj.get("owner_surface") or "").strip()),
        "stale_object": str(obj.get("lifecycle")) in {"deprecated", "forbidden"},
        "has_duplicate_alias": bool(duplicate_aliases),
        "duplicate_aliases": duplicate_aliases,
        "deprecated_alias_still_used": False,
        "has_forbidden_alias_hit": bool(forbidden_hits),
        "forbidden_alias_hits": forbidden_hits,
        "missing_orientation_route": not bool(orientation_route),
        "tags": ["semantic-commons", "generated-projection"],
    }
    alias_lines = "\n".join(f"- `{alias}`" for alias in aliases) or "- none"
    layer_lines = "\n".join(f"- `{layer}`" for layer in route_layers) or "- none"
    forbidden_lines = "\n".join(f"- `{alias}`" for alias in obj.get("forbidden_aliases", [])) or "- none"
    return (
        _frontmatter(frontmatter)
        + f"# {obj['canonical_name']}\n\n"
        + "Generated read-only projection. Edit the Semantic Commons source files, not this note.\n\n"
        + "## Identity\n\n"
        + f"- canonical object ID: `{canonical_id}`\n"
        + f"- api_name: `{obj['api_name']}`\n"
        + f"- lifecycle: `{obj['lifecycle']}`\n"
        + f"- owner: `{obj['owner_surface']}`\n"
        + f"- source path: `{obj['source_path']}`\n\n"
        + "## Aliases\n\n"
        + alias_lines
        + "\n\n## Forbidden Aliases\n\n"
        + forbidden_lines
        + "\n\n## Orientation Route\n\n"
        + f"- route: `{orientation_route or 'missing'}`\n"
        + layer_lines
        + "\n\n## Projection Boundary\n\n"
        + "- `generated: true`\n"
        + "- `canon: false`\n"
        + "- source of truth: `docs/ontology/semantic_objects.yaml`\n"
    )


def _index_note(objects: list[dict[str, Any]], generated_at: str) -> str:
    links = []
    for obj in objects:
        slug = _safe_slug(str(obj["canonical_name"]))
        links.append(f"- [[objects/{slug}|{obj['canonical_name']}]] (`{obj['id']}`)")
    frontmatter = {
        "title": "Semantic Commons Projection Index",
        "projection_family": "semantic_commons",
        "projection_kind": "index",
        "projection_of": OBJECTS_PATH.as_posix(),
        "generated": True,
        "generated_at": generated_at,
        "canon": False,
        "review_state": "generated_unreviewed",
        "tags": ["semantic-commons", "generated-projection"],
    }
    return (
        _frontmatter(frontmatter)
        + "# Semantic Commons Projection Index\n\n"
        + "Generated read-only index for Obsidian/PKM navigation.\n\n"
        + "## Objects\n\n"
        + "\n".join(links)
        + "\n\n## Dashboards\n\n"
        + "- [[bases/semantic-commons.base|Semantic Commons Base]]\n"
    )


def _base_file() -> str:
    return """# Semantic Commons generated dashboard bundle.
# Source of truth: docs/ontology/*.yaml

filters:
  and:
    - projection_family == "semantic_commons"

views:
  - type: table
    name: Semantic Commons Objects
    filters:
      and:
        - projection_kind == "semantic_object"
    properties:
      - canonical_object_id
      - lifecycle
      - owner
      - authority_level
      - orientation_route
      - review_state
  - type: table
    name: Duplicate Aliases
    filters:
      and:
        - has_duplicate_alias == true
    properties:
      - canonical_object_id
      - duplicate_aliases
      - aliases
  - type: table
    name: Missing Owner
    filters:
      and:
        - missing_owner == true
    properties:
      - canonical_object_id
      - source_path
      - owner
  - type: table
    name: Stale Objects
    filters:
      and:
        - stale_object == true
    properties:
      - canonical_object_id
      - lifecycle
      - source_path
  - type: table
    name: Deprecated Alias Still Used
    filters:
      and:
        - deprecated_alias_still_used == true
    properties:
      - canonical_object_id
      - aliases
      - lifecycle
  - type: table
    name: Forbidden Alias Hit
    filters:
      and:
        - has_forbidden_alias_hit == true
    properties:
      - canonical_object_id
      - forbidden_alias_hits
      - source_path
  - type: table
    name: Missing Orientation Route
    filters:
      and:
        - missing_orientation_route == true
    properties:
      - canonical_object_id
      - source_path
      - orientation_route
  - type: table
    name: Unreviewed Generated Note
    filters:
      and:
        - review_state == "generated_unreviewed"
    properties:
      - canonical_object_id
      - generated_at
      - projection_of
"""


def build_projection(vault_root: Path, *, generated_at: str) -> tuple[dict[str, str], dict[str, Any]]:
    objects_payload = _load_yaml(REPO_ROOT / OBJECTS_PATH)
    aliases_payload = _load_yaml(REPO_ROOT / ALIASES_PATH)
    orientation_payload = _load_yaml(REPO_ROOT / ORIENTATION_PATH)
    projection_payload = _load_yaml(REPO_ROOT / PROJECTION_PATH)
    report = validate_semantic_commons(REPO_ROOT)
    if report["errors"]:
        raise RuntimeError(f"Semantic Commons has {len(report['errors'])} error(s)")

    aliases_by_id = _alias_maps(aliases_payload)
    duplicate_by_id = _duplicate_aliases(aliases_payload)
    layers_by_route = _route_layers(orientation_payload)
    objects = [obj for obj in objects_payload.get("objects", []) if isinstance(obj, dict)]

    files: dict[str, str] = {}
    files["_index.md"] = _index_note(objects, generated_at)
    files["bases/semantic-commons.base"] = _base_file()
    for obj in objects:
        canonical_id = str(obj["id"])
        slug = _safe_slug(str(obj["canonical_name"]))
        route_id = str(obj.get("orientation_route") or "")
        files[f"objects/{slug}.md"] = _object_note(
            obj,
            aliases=aliases_by_id.get(canonical_id, []),
            duplicate_aliases=duplicate_by_id.get(canonical_id, []),
            route_layers=layers_by_route.get(route_id, []),
            generated_at=generated_at,
        )

    manifest = {
        "generated_at": generated_at,
        "repo_root": str(REPO_ROOT),
        "vault_root": str(vault_root),
        "source_files": projection_payload.get("source_files", []),
        "projection_policy": projection_payload.get("projection_policy", {}),
        "object_count": len(objects),
        "file_count": len(files),
        "files": [
            ProjectionFile(
                path=str((vault_root / rel).resolve()),
                kind="base" if rel.endswith(".base") else "markdown",
                canonical_object_id="" if not rel.startswith("objects/") else str(objects_by_slug(objects).get(rel, "")),
            ).__dict__
            for rel in sorted(files)
        ],
    }
    return files, manifest


def objects_by_slug(objects: list[dict[str, Any]]) -> dict[str, str]:
    return {
        f"objects/{_safe_slug(str(obj['canonical_name']))}.md": str(obj["id"])
        for obj in objects
    }


def write_projection(files: dict[str, str], vault_root: Path) -> None:
    for rel, content in files.items():
        path = vault_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault-root", type=Path, default=DEFAULT_VAULT_ROOT)
    parser.add_argument("--manifest", type=Path, default=REPO_ROOT / DEFAULT_MANIFEST)
    parser.add_argument("--generated-at", default="")
    parser.add_argument("--write", action="store_true", help="write projection notes")
    parser.add_argument("--json", action="store_true", help="print manifest JSON")
    args = parser.parse_args(argv)

    generated_at = args.generated_at or _utc_now()
    files, manifest = build_projection(args.vault_root, generated_at=generated_at)
    if args.write:
        write_projection(files, args.vault_root)
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.json or not args.write:
        print(json.dumps(manifest, indent=2, sort_keys=True))
    else:
        print(
            f"projected {manifest['object_count']} Semantic Commons objects "
            f"to {args.vault_root}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
