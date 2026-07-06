"""Receipt schema + append-only ledger (contract invariants 2 & receipts list).

AttemptReceipt = one (task, arm, replicate). RunReceipt = the campaign decision
record. Ledger = append-only JSONL score store (the autoresearch memory).
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


def scaffold_parity_hash(*prompt_templates: str) -> str:
    """Hash of the per-arm prompt scaffolding so arm-engineering parity (F4) is
    auditable: if two arms claim parity their non-arm-specific template parts hash
    equal. Stored on every receipt."""
    h = hashlib.sha256()
    for t in prompt_templates:
        h.update((t or "").encode("utf-8", "ignore"))
    return h.hexdigest()[:16]


@dataclass
class AttemptReceipt:
    task_id: str
    mission_class: str
    split: str                      # explore | confirm
    arm: str
    class_null: str                 # what this arm is contrasted against
    replicate: int
    generator: str                  # the pinned generator model (same across arms)
    verifier: str | None            # cross-family verifier, if any
    selection_reasons: str          # why these models (roster reasons)
    scaffold_parity_hash: str
    contamination_state: dict
    budget: dict                    # Budget.to_dict()
    resolved: bool                  # Docker grade (final, single grade)
    grade_seconds: float
    grade_error: str | None = None
    patch_len: int = 0
    invalid: bool = False
    invalid_reason: str | None = None


@dataclass
class RunReceipt:
    kind: str = "forge_v2_run"
    mission_class: str = ""
    arm: str = ""
    class_null: str = ""
    timestamp: int = 0
    n_pairs: int = 0
    comparisons_count: int = 1
    contrast_vs_class_null: dict = field(default_factory=dict)   # paired bootstrap CI
    split_contrasts: dict = field(default_factory=dict)
    replicate_variance: dict = field(default_factory=dict)
    critic_verdict: dict = field(default_factory=dict)
    contamination_state: dict = field(default_factory=dict)
    budget_matched_proof: dict = field(default_factory=dict)
    closeout: str = ""
    next_experiment: str = ""
    artifact_dir: str = ""
    ledger_row_ids: list = field(default_factory=list)
    attempts: list = field(default_factory=list)


class Ledger:
    """Append-only JSONL score store. Every AttemptReceipt is one row; the
    campaign RunReceipt is one row tagged kind=forge_v2_run."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, obj) -> str:
        rec = asdict(obj) if hasattr(obj, "__dataclass_fields__") else dict(obj)
        row_id = hashlib.sha256(
            (json.dumps(rec, sort_keys=True, default=str) + str(time.time())).encode()
        ).hexdigest()[:16]
        rec["_row_id"] = row_id
        if rec.get("kind") == "forge_v2_run" and not rec.get("ledger_row_ids"):
            rec["ledger_row_ids"] = [row_id]
        with self.path.open("a") as f:
            f.write(json.dumps(rec, default=str) + "\n")
        return row_id
