"""Hash-chained per-agent learning ledger store.

The single durable, tamper-evident write surface that all metabolism execution
and the autonomy LEARN executor depend on. It is a standalone store mirroring
``KernelRunStore.append_proof_entry``'s hash-chain (``ledger_sequence`` +
``previous_entry_hash`` + blanked-``entry_hash`` payload hash). It does NOT wire
into the kernel, expose a tool, or import persistent-agent runtimes; it is a
pure filesystem store + verifier over the kernel's hash helpers so the metabolism
tools and the LEARN executor can build on a frozen API.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from dharma_swarm.operator_core.living_agent_kernel import DEFAULT_KERNEL_RUN_DIR
from dharma_swarm.operator_core.runtime_truth import stable_payload_hash, utc_now

LESSONS_DIRNAME = "lessons"


class EmptyLessonDeltaError(ValueError):
    """Raised when append_lesson is given empty/whitespace delta_text."""


class KernelLessonReceipt(BaseModel):
    agent_uid: str
    namespace: str
    run_id: str = ""
    delta_text: str
    delta_hash: str
    provenance: dict[str, Any] = Field(default_factory=dict)
    ledger_sequence: int = 0
    previous_entry_hash: str = ""
    entry_hash: str = ""
    created_at: str = Field(default_factory=utc_now)


def _lesson_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _append_lesson_row(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n")


def safe_namespace_filename(namespace: str) -> str:
    """Map an arbitrary namespace to one deterministic, traversal-safe filename.

    A short content digest is appended so distinct namespaces that sanitize to the
    same slug still resolve to distinct files within ``base_dir/lessons/``.
    """
    digest = hashlib.sha256(namespace.encode("utf-8")).hexdigest()[:16]
    slug_chars = [c if (c.isalnum() or c in ("-", "_")) else "_" for c in namespace]
    slug = "".join(slug_chars).strip("_") or "ns"
    slug = slug[:80]
    return f"{slug}.{digest}.jsonl"


class KernelLessonStore:
    def __init__(self, base_dir: Path | str | None = None) -> None:
        self.base_dir = Path(base_dir or DEFAULT_KERNEL_RUN_DIR).expanduser()
        self.lessons_dir = self.base_dir / LESSONS_DIRNAME
        self.lessons_dir.mkdir(parents=True, exist_ok=True)

    def namespace_path(self, namespace: str) -> Path:
        path = (self.lessons_dir / safe_namespace_filename(namespace)).resolve()
        lessons_root = self.lessons_dir.resolve()
        if lessons_root != path.parent:
            raise ValueError(f"namespace escapes lessons dir: {namespace!r}")
        return path

    def append_lesson(
        self,
        agent_uid: str,
        namespace: str,
        delta_text: str,
        *,
        run_id: str = "",
        provenance: dict[str, Any] | None = None,
    ) -> KernelLessonReceipt:
        if not delta_text or not delta_text.strip():
            raise EmptyLessonDeltaError("delta_text must be non-empty and non-whitespace")
        path = self.namespace_path(namespace)
        rows = _lesson_rows(path)
        receipt = KernelLessonReceipt(
            agent_uid=agent_uid,
            namespace=namespace,
            run_id=run_id,
            delta_text=delta_text,
            delta_hash=stable_payload_hash(delta_text),
            provenance=dict(provenance or {}),
        )
        row = receipt.model_dump(mode="json")
        row["ledger_sequence"] = len(rows) + 1
        row["previous_entry_hash"] = str(rows[-1].get("entry_hash") or "") if rows else ""
        row["entry_hash"] = ""
        row["entry_hash"] = stable_payload_hash(row)
        _append_lesson_row(path, row)
        return KernelLessonReceipt.model_validate(row)

    def lessons(self, namespace: str) -> list[KernelLessonReceipt]:
        return [KernelLessonReceipt.model_validate(row) for row in _lesson_rows(self.namespace_path(namespace))]

    def verify_lesson_ledger(self, namespace: str) -> tuple[bool, list[str]]:
        rows = _lesson_rows(self.namespace_path(namespace))
        if not rows:
            return (True, [])
        errors: list[str] = []
        previous_hash = ""
        for index, row in enumerate(rows, start=1):
            if int(row.get("ledger_sequence") or 0) != index:
                errors.append(f"line {index}: ledger_sequence mismatch")
            if str(row.get("previous_entry_hash") or "") != previous_hash:
                errors.append(f"line {index}: previous_entry_hash mismatch")
            observed_hash = str(row.get("entry_hash") or "")
            material = dict(row)
            material["entry_hash"] = ""
            if observed_hash != stable_payload_hash(material):
                errors.append(f"line {index}: entry_hash mismatch")
            previous_hash = observed_hash
        return (len(errors) == 0, errors)
