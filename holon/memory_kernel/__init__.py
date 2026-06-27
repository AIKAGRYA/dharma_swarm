"""Read-only standalone MemoryKernel facade.

This is intentionally small. It projects local text and JSONL memory files into
budgeted context packs and does not write or promote memory.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class MemoryContextBudget:
    max_candidate_atoms: int = 30
    max_admitted_atoms: int = 6
    max_total_chars: int = 1800
    include_content: bool = True


@dataclass(frozen=True)
class MemoryContextPackItem:
    surface_id: str
    content_ref: str
    content_snippet: str | None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryContextPack:
    items: tuple[MemoryContextPackItem, ...]
    total_chars: int
    truncated: bool = False


@dataclass(frozen=True)
class MemoryKernelConfig:
    memory_paths: tuple[Path, ...] = ()


class MemoryKernel:
    """Read-only context pack builder over local files."""

    def __init__(self, config: MemoryKernelConfig | None = None, *, agents_root: Path | None = None, holon: str | None = None) -> None:
        self.config = config or MemoryKernelConfig()
        self.agents_root = agents_root
        self.holon = holon

    def _paths(self, surface_ids: Iterable[str] | None = None) -> list[Path]:
        paths = list(self.config.memory_paths)
        if self.agents_root is not None and self.holon:
            root = self.agents_root / self.holon
            paths.extend(
                [
                    root / "memory.jsonl",
                    root / "relationship_memory.jsonl",
                    root / "dialogue" / "relationship_memory.jsonl",
                    root / "wake_ledger.jsonl",
                ]
            )
        selected = set(surface_ids or [])
        if selected:
            return [path for path in paths if str(path) in selected or path.name in selected]
        return paths

    def preview_memory_pack(
        self,
        *,
        surface_ids: Iterable[str] | None = None,
        atom_types: object | None = None,
        query: object | None = None,
        budget: MemoryContextBudget | None = None,
    ) -> MemoryContextPack:
        del atom_types, query
        resolved = budget or MemoryContextBudget()
        items: list[MemoryContextPackItem] = []
        total_chars = 0
        truncated = False
        for path in self._paths(surface_ids):
            if len(items) >= resolved.max_admitted_atoms:
                break
            if not path.exists() or not path.is_file():
                continue
            for index, text in enumerate(_iter_text_records(path), start=1):
                if len(items) >= resolved.max_admitted_atoms:
                    break
                remaining = resolved.max_total_chars - total_chars
                if remaining <= 0:
                    truncated = True
                    break
                snippet = _compact(text)[: min(remaining, 500)] if resolved.include_content else None
                total_chars += len(snippet or "")
                items.append(
                    MemoryContextPackItem(
                        surface_id=path.name,
                        content_ref=f"{path}:{index}",
                        content_snippet=snippet,
                        metadata={"path": str(path)},
                    )
                )
        return MemoryContextPack(items=tuple(items), total_chars=total_chars, truncated=truncated)

    def context_eval(self, summary_lines: list[str] | None = None) -> str:
        count = len(summary_lines or [])
        return f"context_pack_lines={count}; evaluator=standalone_read_only"


def _iter_text_records(path: Path) -> Iterable[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    if path.suffix == ".jsonl":
        records: list[str] = []
        for line in text.splitlines()[-20:]:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                records.append(line)
                continue
            if isinstance(data, dict):
                value = data.get("content") or data.get("text") or data.get("summary") or data.get("record")
                records.append(json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else str(value))
            else:
                records.append(str(data))
        return records
    return [text]


def _compact(text: str) -> str:
    return " ".join(str(text).split())


AdapterFactory = object
DEFAULT_REQUIRED_ADAPTER_SURFACE_IDS = ("local.memory", "local.wake_ledger")


def default_adapter_factories(config: object | None = None) -> dict[str, object]:
    del config
    return {}


__all__ = [
    "AdapterFactory",
    "DEFAULT_REQUIRED_ADAPTER_SURFACE_IDS",
    "MemoryContextBudget",
    "MemoryContextPack",
    "MemoryContextPackItem",
    "MemoryKernel",
    "MemoryKernelConfig",
    "default_adapter_factories",
]
