"""Fresh private code-repair taskbed for the first Forge production contract."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


SCHEMA_VERSION = "forge_prod_contracts.private_code_repair_taskbed.v1"
DEFAULT_SEED = "forge-prod-contracts-20260701"
CONTAMINATION_STATE = "fresh_private_local_generated"
EXTERNALITY_LEVEL = "local_private_fixture"


@dataclass(frozen=True, slots=True)
class ExecutionGrade:
    """Execution-grade result for one candidate source."""

    passed: bool
    score: float
    command: tuple[str, ...]
    stdout: str
    stderr: str
    returncode: int

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "score": self.score,
            "command": list(self.command),
            "stdout": self.stdout,
            "stderr": self.stderr,
            "returncode": self.returncode,
        }


@dataclass(frozen=True, slots=True)
class PrivateRepairTask:
    """One locally generated, hidden-test code-repair task."""

    task_id: str
    seed: str
    title: str
    source_filename: str
    buggy_source: str
    visible_prompt: str
    hidden_test: str
    repair_family: str
    contamination_state: str = CONTAMINATION_STATE
    externality_level: str = EXTERNALITY_LEVEL

    @property
    def hidden_test_sha256(self) -> str:
        return stable_text_hash(self.hidden_test)

    @property
    def buggy_source_sha256(self) -> str:
        return stable_text_hash(self.buggy_source)

    def visible_manifest_entry(self) -> dict[str, object]:
        """Return the task metadata safe for candidate arms to see."""

        return {
            "task_id": self.task_id,
            "seed": self.seed,
            "title": self.title,
            "source_filename": self.source_filename,
            "visible_prompt": self.visible_prompt,
            "buggy_source": self.buggy_source,
            "buggy_source_sha256": self.buggy_source_sha256,
            "hidden_test_sha256": self.hidden_test_sha256,
            "repair_family": self.repair_family,
            "contamination_state": self.contamination_state,
            "externality_level": self.externality_level,
        }

    def to_private_dict(self) -> dict[str, object]:
        payload = self.visible_manifest_entry()
        payload["hidden_test"] = self.hidden_test
        return payload


def stable_text_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def stable_payload_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def default_private_code_repair_tasks(
    seed: str = DEFAULT_SEED,
) -> tuple[PrivateRepairTask, ...]:
    """Return deterministic private repair tasks derived from ``seed``.

    The templates are local fixtures, but task ids are seed-derived and the
    hidden tests are withheld from candidate arm manifests. This makes the suite
    suitable for a hermetic first production contract without making any public
    benchmark claim.
    """

    templates = (
        _invoice_tax_rounding(seed),
        _retry_backoff(seed),
        _order_preserving_dedupe(seed),
    )
    return tuple(templates)


def visible_task_manifest(tasks: tuple[PrivateRepairTask, ...]) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "task_count": len(tasks),
        "contamination_state": CONTAMINATION_STATE,
        "externality_level": EXTERNALITY_LEVEL,
        "hidden_tests_withheld": True,
        "tasks": [task.visible_manifest_entry() for task in tasks],
    }


def grade_candidate_source(
    task: PrivateRepairTask, candidate_source: str
) -> ExecutionGrade:
    """Run a candidate against the task's hidden test in a temporary sandbox."""

    with tempfile.TemporaryDirectory(prefix="forge-private-repair-") as raw_dir:
        sandbox = Path(raw_dir)
        solution_path = sandbox / task.source_filename
        test_path = sandbox / "test_hidden.py"
        solution_path.write_text(candidate_source, encoding="utf-8")
        test_path.write_text(task.hidden_test, encoding="utf-8")
        command = (sys.executable, str(test_path))
        proc = subprocess.run(
            command,
            cwd=sandbox,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    passed = proc.returncode == 0
    return ExecutionGrade(
        passed=passed,
        score=1.0 if passed else 0.0,
        command=command,
        stdout=proc.stdout[-4000:],
        stderr=proc.stderr[-4000:],
        returncode=proc.returncode,
    )


def _task_id(seed: str, slug: str) -> str:
    digest = hashlib.sha256(f"{seed}:{slug}".encode("utf-8")).hexdigest()[:12]
    return f"private-repair-{slug}-{digest}"


def _invoice_tax_rounding(seed: str) -> PrivateRepairTask:
    buggy_source = '''def invoice_total_cents(items_cents, tax_bps):
    """Return invoice total in cents for line items and tax basis points."""
    subtotal = sum(items_cents)
    return subtotal + int(subtotal * tax_bps / 1000)
'''
    hidden_test = """import unittest
from solution import invoice_total_cents


class InvoiceTotalHiddenTest(unittest.TestCase):
    def test_uses_basis_points_denominator(self):
        self.assertEqual(invoice_total_cents([1000, 2500], 875), 3806)

    def test_zero_tax_keeps_subtotal(self):
        self.assertEqual(invoice_total_cents([1999, 1], 0), 2000)


if __name__ == "__main__":
    unittest.main()
"""
    return PrivateRepairTask(
        task_id=_task_id(seed, "invoice-tax-bps"),
        seed=seed,
        title="Invoice tax basis-point repair",
        source_filename="solution.py",
        buggy_source=buggy_source,
        visible_prompt=(
            "Repair invoice_total_cents. tax_bps is expressed in basis points, "
            "so 875 means 8.75%. Keep integer cent output."
        ),
        hidden_test=hidden_test,
        repair_family="arithmetic_contract",
    )


def _retry_backoff(seed: str) -> PrivateRepairTask:
    buggy_source = '''def retry_delays_ms(base_ms, attempts):
    """Return linear retry delays for attempts numbered from one."""
    return [base_ms * attempt for attempt in range(attempts)]
'''
    hidden_test = """import unittest
from solution import retry_delays_ms


class RetryDelayHiddenTest(unittest.TestCase):
    def test_first_retry_is_not_zero(self):
        self.assertEqual(retry_delays_ms(250, 4), [250, 500, 750, 1000])

    def test_no_attempts_returns_empty_list(self):
        self.assertEqual(retry_delays_ms(100, 0), [])


if __name__ == "__main__":
    unittest.main()
"""
    return PrivateRepairTask(
        task_id=_task_id(seed, "retry-backoff-one-indexed"),
        seed=seed,
        title="Retry delay one-index repair",
        source_filename="solution.py",
        buggy_source=buggy_source,
        visible_prompt=(
            "Repair retry_delays_ms. Attempts are numbered from one; the first "
            "retry delay should be base_ms, not zero."
        ),
        hidden_test=hidden_test,
        repair_family="boundary_indexing",
    )


def _order_preserving_dedupe(seed: str) -> PrivateRepairTask:
    buggy_source = '''def dedupe_event_ids(event_ids):
    """Return unique event ids in first-seen order."""
    return list(set(event_ids))
'''
    hidden_test = """import unittest
from solution import dedupe_event_ids


class DedupeHiddenTest(unittest.TestCase):
    def test_preserves_first_seen_order(self):
        self.assertEqual(dedupe_event_ids([2, 1, 2, 3, 1]), [2, 1, 3])

    def test_empty_input(self):
        self.assertEqual(dedupe_event_ids([]), [])


if __name__ == "__main__":
    unittest.main()
"""
    return PrivateRepairTask(
        task_id=_task_id(seed, "order-preserving-dedupe"),
        seed=seed,
        title="Order-preserving event dedupe repair",
        source_filename="solution.py",
        buggy_source=buggy_source,
        visible_prompt=(
            "Repair dedupe_event_ids. The function must remove duplicates while "
            "preserving first-seen order."
        ),
        hidden_test=hidden_test,
        repair_family="stateful_collection_semantics",
    )
