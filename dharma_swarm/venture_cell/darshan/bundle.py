"""Bundle creation and validation for Darshan artifacts."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from dharma_swarm.venture_cell.darshan.schema import (
    AttentionLedger,
    BundleManifest,
    ClaimLedger,
    CounterframeLedger,
    DecisionDelta,
    GateDecisionLedger,
    PolsiaHandoff,
    SourcePack,
    new_id,
)


REQUIRED_BUNDLE_FILES = (
    "article.md",
    "source_pack.json",
    "claim_ledger.json",
    "counterframes.json",
    "attention_ledger.json",
    "gate_decisions.json",
    "decision_delta.json",
    "bundle_manifest.json",
    "polsia_handoff.json",
)


@dataclass(frozen=True)
class BundleValidationResult:
    bundle_path: Path
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    manifest: BundleManifest | None = None


def default_artifact_root() -> Path:
    return Path.home() / ".dharma" / "artifacts" / "venture_cell" / "DARSHAN"


def safe_slug(value: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return base or "untitled"


def create_bundle(
    *,
    title: str,
    slug: str | None = None,
    root: Path | None = None,
    bundle_date: date | None = None,
    artifact_id: str | None = None,
    overwrite: bool = False,
) -> Path:
    artifact_id = artifact_id or new_id("darshan")
    resolved_slug = safe_slug(slug or title)
    day = (bundle_date or date.today()).isoformat()
    bundle_path = (root or default_artifact_root()) / day / resolved_slug
    if bundle_path.exists() and not overwrite:
        raise FileExistsError(f"Darshan bundle already exists: {bundle_path}")
    bundle_path.mkdir(parents=True, exist_ok=True)

    files: dict[str, str] = {
        "article.md": _article_template(title, artifact_id),
        "source_pack.json": _json(SourcePack(artifact_id=artifact_id)),
        "claim_ledger.json": _json(ClaimLedger(artifact_id=artifact_id)),
        "counterframes.json": _json(CounterframeLedger(artifact_id=artifact_id)),
        "attention_ledger.json": _json(_default_attention(artifact_id)),
        "gate_decisions.json": _json(GateDecisionLedger(artifact_id=artifact_id)),
        "decision_delta.json": _json(DecisionDelta(artifact_id=artifact_id)),
        "polsia_handoff.json": _json(_default_handoff(artifact_id)),
    }
    for name, content in files.items():
        path = bundle_path / name
        if overwrite or not path.exists():
            path.write_text(content, encoding="utf-8")

    manifest = BundleManifest(
        artifact_id=artifact_id,
        title=title,
        slug=resolved_slug,
        bundle_path=str(bundle_path),
        required_files=list(REQUIRED_BUNDLE_FILES),
        content_hashes=_content_hashes(bundle_path),
    )
    (bundle_path / "bundle_manifest.json").write_text(_json(manifest), encoding="utf-8")
    return bundle_path


def validate_bundle(bundle_path: Path) -> BundleValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    bundle_path = bundle_path.expanduser().resolve()
    if not bundle_path.exists():
        return BundleValidationResult(
            bundle_path=bundle_path,
            valid=False,
            errors=[f"bundle path does not exist: {bundle_path}"],
        )
    for name in REQUIRED_BUNDLE_FILES:
        if not (bundle_path / name).exists():
            errors.append(f"missing required file: {name}")
    if errors:
        return BundleValidationResult(bundle_path=bundle_path, valid=False, errors=errors)

    manifest = _load_model(bundle_path / "bundle_manifest.json", BundleManifest, errors)
    _load_model(bundle_path / "source_pack.json", SourcePack, errors)
    _load_model(bundle_path / "claim_ledger.json", ClaimLedger, errors)
    _load_model(bundle_path / "counterframes.json", CounterframeLedger, errors)
    _load_model(bundle_path / "attention_ledger.json", AttentionLedger, errors)
    _load_model(bundle_path / "gate_decisions.json", GateDecisionLedger, errors)
    _load_model(bundle_path / "decision_delta.json", DecisionDelta, errors)
    _load_model(bundle_path / "polsia_handoff.json", PolsiaHandoff, errors)

    article = bundle_path / "article.md"
    if not article.read_text(encoding="utf-8").strip():
        errors.append("article.md is empty")
    if manifest is not None:
        _validate_manifest_hashes(bundle_path, manifest, warnings)
    return BundleValidationResult(
        bundle_path=bundle_path,
        valid=not errors,
        errors=errors,
        warnings=warnings,
        manifest=manifest,
    )


def validate_bundle_for_done(bundle_path: Path) -> BundleValidationResult:
    result = validate_bundle(bundle_path)
    if not result.valid:
        return result
    from dharma_swarm.venture_cell.darshan.external_reader_gate import (
        validate_external_reader_gate,
    )

    gate = validate_external_reader_gate(result.bundle_path)
    errors = list(result.errors)
    warnings = list(result.warnings)
    warnings.extend(gate.warnings)
    if not gate.pass_gate:
        errors.extend(gate.errors or ["external_reader_gate_failed"])
    return BundleValidationResult(
        bundle_path=result.bundle_path,
        valid=not errors,
        errors=errors,
        warnings=warnings,
        manifest=result.manifest,
    )


def refresh_manifest(bundle_path: Path) -> BundleManifest:
    result = validate_bundle(bundle_path)
    if not result.valid:
        raise ValueError("; ".join(result.errors))
    manifest = result.manifest
    if manifest is None:
        raise ValueError("bundle manifest missing")
    updated = manifest.model_copy(
        update={"content_hashes": _content_hashes(result.bundle_path)}
    )
    (result.bundle_path / "bundle_manifest.json").write_text(_json(updated), encoding="utf-8")
    return updated


def _json(model: Any) -> str:
    if hasattr(model, "model_dump"):
        payload = model.model_dump(mode="json")
    else:
        payload = model
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _article_template(title: str, artifact_id: str) -> str:
    return (
        f"# {title}\n\n"
        f"Artifact: `{artifact_id}`\n\n"
        "## Seeing\n\n"
        "Draft the public clarity artifact here.\n\n"
        "## What Would Change This\n\n"
        "Name the evidence that would change the reading.\n"
    )


def _default_attention(artifact_id: str) -> AttentionLedger:
    return AttentionLedger(
        artifact_id=artifact_id,
        reading_modes_supported=["scan", "orient", "deep_read", "evaluate", "reflect", "act"],
        anti_feed_design_choices=[
            "finite artifact",
            "source pack separated from main attentional line",
            "no engagement trap",
        ],
    )


def _default_handoff(artifact_id: str) -> PolsiaHandoff:
    return PolsiaHandoff(
        artifact_id=artifact_id,
        handoff_summary="Operate the Season 0 shell without owning final editorial judgment.",
        allowed_scope=[
            "calendar",
            "checklists",
            "ops board",
            "outreach list",
            "weekly review",
        ],
        forbidden_scope=[
            "final claims",
            "final voice",
            "source trust",
            "public publishing",
            "corrections",
            "refusals",
        ],
        requested_outputs=[
            "30-day operating calendar",
            "artifact bundle checklist",
            "weekly operating review template",
        ],
    )


def _content_hashes(bundle_path: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for name in REQUIRED_BUNDLE_FILES:
        if name == "bundle_manifest.json":
            continue
        path = bundle_path / name
        if path.exists():
            hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def _load_model(path: Path, model_type: type[Any], errors: list[str]) -> Any | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return model_type.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        errors.append(f"{path.name} invalid: {exc}")
        return None


def _validate_manifest_hashes(
    bundle_path: Path,
    manifest: BundleManifest,
    warnings: list[str],
) -> None:
    current = _content_hashes(bundle_path)
    for name, recorded in manifest.content_hashes.items():
        if name not in current:
            continue
        if current[name] != recorded:
            warnings.append(f"content hash changed since manifest write: {name}")
