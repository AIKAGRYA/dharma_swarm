"""Stdlib-only fail-closed probes for AgentOps negative-control jails."""

from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.runtime import pr_merge_control as prc


REPO = "owner/repo"
BASE = "b" * 40
HEAD = "a" * 40


def _facts(*, head: str = HEAD) -> dict:
    return {
        "repo": REPO,
        "pr": {"number": 12, "baseRefOid": BASE, "headRefOid": head},
        "risk": {"level": "LOW"},
    }


def _current_pr() -> dict:
    return {
        "number": 12,
        "baseRefOid": BASE,
        "headRefOid": HEAD,
        "isDraft": False,
        "labels": [],
        "body": "complete",
    }


def _gate_args(packet_dir: Path) -> argparse.Namespace:
    return argparse.Namespace(
        pr=12,
        packet_dir=str(packet_dir),
        state_root=str(packet_dir.parent),
        allow_pending=False,
        human_approved=False,
        allow_backup_reviewer=False,
        backup_reviewers="none",
        backup_reviewer_reason="",
        required_reviewers="none",
    )


def _candidate_gate(*, base_cas_enforced: bool) -> dict:
    return {
        "decision": "MERGE_CANDIDATE",
        "pr": 12,
        "repo": REPO,
        "blockers": [],
        "packet_dir": "/tmp/packet",
        "required_reviewers": [],
        "head_sha": HEAD,
        "base_sha": BASE,
        "base_cas_enforced": base_cas_enforced,
        "risk_snapshot": {"head_sha": HEAD, "base_sha": BASE},
    }


class FailClosedStdlibTests(unittest.TestCase):
    def _build_gate(self, *, packet_head: str = HEAD, threads: dict) -> dict:
        with tempfile.TemporaryDirectory() as raw:
            packet_dir = Path(raw) / "packet"
            packet_dir.mkdir()
            prc.write_json(packet_dir / "FACTS.json", _facts(head=packet_head))
            classification = {
                "mergeable": "MERGEABLE",
                "reviewDecision": "APPROVED",
                "checks": {
                    "failing": [],
                    "pending": [],
                    "unknown": [],
                    "passing": [],
                },
            }
            ci_truth = {"merge_blockers": [], "warnings": [], "verdict": "PASS"}
            files = [
                {
                    "filename": "docs/note.md",
                    "additions": 1,
                    "deletions": 0,
                    "status": "modified",
                }
            ]
            with (
                mock.patch.object(prc, "fetch_pr_view", return_value=_current_pr()),
                mock.patch.object(prc, "repo_name", return_value=REPO),
                mock.patch.object(prc, "fetch_review_threads", return_value=threads),
                mock.patch.object(prc, "classify_pr", return_value=classification),
                mock.patch.object(prc, "coherence_results", return_value={"ok": True}),
                mock.patch.object(prc, "fetch_pr_comments", return_value=[]),
                mock.patch.object(prc, "ci_truth_for_pr", return_value=ci_truth),
                mock.patch.object(
                    prc, "fetch_pr_files_at_revision", return_value=files
                ),
                mock.patch.object(prc, "required_reviewer_agents", return_value=[]),
                mock.patch.object(prc, "backup_reviewer_agents", return_value=[]),
            ):
                return prc.build_gate(_gate_args(packet_dir))

    def test_stale_packet_head_remains_blocked(self) -> None:
        gate = self._build_gate(
            packet_head="c" * 40,
            threads={"ok": True, "unresolved": [], "unresolved_count": 0},
        )

        self.assertEqual(gate["decision"], "BLOCKED")
        self.assertTrue(
            any(item.startswith("stale packet:") for item in gate["blockers"])
        )

    def test_incomplete_thread_state_remains_blocked(self) -> None:
        gate = self._build_gate(
            threads={"ok": False, "error": "truncated", "unresolved": None}
        )

        self.assertEqual(gate["decision"], "BLOCKED")
        self.assertTrue(
            any(
                "cannot verify complete review-thread state" in item
                for item in gate["blockers"]
            )
        )

    def test_review_evidence_mutation_remains_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            packet_dir = Path(raw)
            prc.write_json(packet_dir / "FACTS.json", _facts())
            for name in prc.REVIEW_EVIDENCE_FILES:
                path = packet_dir / name
                if not path.exists():
                    path.write_text(f"evidence {name}\n", encoding="utf-8")
            snapshot = prc.read_review_evidence_snapshot(packet_dir)
            prompt_path = prc.review_prompt_path(packet_dir, "codex")
            prompt_path.write_text(
                prc.render_agent_prompt(
                    "Codex",
                    packet_dir / "REVIEW_PACKET.md",
                    12,
                    evidence_snapshot=snapshot,
                ),
                encoding="utf-8",
            )
            output_path = packet_dir / "codex_review.md"
            output_path.write_text(
                "## Verdict\nAPPROVE\n\n## Findings\n1. clean\n", encoding="utf-8"
            )
            prc.write_json(
                packet_dir / "codex_review_receipt.json",
                {
                    "agent": "codex",
                    "repo": REPO,
                    "pr": 12,
                    "base_sha": BASE,
                    "head_sha": HEAD,
                    "status": "completed",
                    "exit_code": 0,
                    "timed_out": False,
                    "verdict": "APPROVE",
                    "output_sha256": prc.sha256_bytes(output_path.read_bytes()),
                    "prompt_sha256": prc.sha256_bytes(prompt_path.read_bytes()),
                    "evidence_sha256": prc.review_evidence_digest(snapshot),
                },
            )
            (packet_dir / "DIFF.patch").write_text(
                "mutated after review\n", encoding="utf-8"
            )

            status = prc.load_agent_review_status(
                packet_dir,
                "codex",
                repo=REPO,
                pr_number=12,
                base_sha=BASE,
                head_sha=HEAD,
            )

        self.assertFalse(status["receipt_valid"])

    def test_missing_review_binding_context_remains_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            packet_dir = Path(raw)
            prc.write_json(packet_dir / "FACTS.json", _facts())
            for name in prc.REVIEW_EVIDENCE_FILES:
                path = packet_dir / name
                if not path.exists():
                    path.write_text(f"evidence {name}\n", encoding="utf-8")
            snapshot = prc.read_review_evidence_snapshot(packet_dir)
            prompt_path = prc.review_prompt_path(packet_dir, "codex")
            prompt_path.write_text(
                prc.render_agent_prompt(
                    "Codex",
                    packet_dir / "REVIEW_PACKET.md",
                    12,
                    evidence_snapshot=snapshot,
                ),
                encoding="utf-8",
            )
            output_path = packet_dir / "codex_review.md"
            output_path.write_text(
                "## Verdict\nAPPROVE\n\n## Findings\n1. clean\n", encoding="utf-8"
            )
            prc.write_json(
                packet_dir / "codex_review_receipt.json",
                {
                    "agent": "codex",
                    "repo": REPO,
                    "pr": 12,
                    "base_sha": BASE,
                    "head_sha": HEAD,
                    "status": "completed",
                    "exit_code": 0,
                    "timed_out": False,
                    "verdict": "APPROVE",
                    "output_sha256": prc.sha256_bytes(output_path.read_bytes()),
                    "prompt_sha256": prc.sha256_bytes(prompt_path.read_bytes()),
                    "evidence_sha256": prc.review_evidence_digest(snapshot),
                },
            )

            status = prc.load_agent_review_status(
                packet_dir,
                "codex",
                repo="",
                pr_number=0,
                base_sha="",
                head_sha="",
            )

        self.assertFalse(status["receipt_valid"])
        self.assertIn(
            "repository binding is missing or invalid", status["receipt_error"]
        )
        self.assertIn(
            "PR number binding is missing or invalid", status["receipt_error"]
        )
        self.assertIn("review base SHA is missing or invalid", status["receipt_error"])
        self.assertIn("current head SHA is missing or invalid", status["receipt_error"])

    def test_oversized_review_evidence_remains_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            packet_dir = Path(raw)
            prc.write_json(packet_dir / "FACTS.json", _facts())
            for name in prc.REVIEW_EVIDENCE_FILES:
                path = packet_dir / name
                if not path.exists():
                    path.write_text(f"evidence {name}\n", encoding="utf-8")
            (packet_dir / "DIFF.patch").write_bytes(
                b"x" * prc.MAX_REVIEW_EVIDENCE_BYTES
            )
            args = argparse.Namespace(
                pr=12,
                packet_dir=str(packet_dir),
                state_root=str(packet_dir.parent),
                agent="codex",
                timeout_s=30,
                kill_grace_s=1,
            )

            with (
                mock.patch.object(
                    prc,
                    "review_command_and_env",
                    return_value=(["codex", "exec"], {}),
                ),
                mock.patch.object(prc, "run_agent_process") as run_process,
            ):
                with self.assertRaisesRegex(
                    prc.PRControlError, "review evidence exceeds"
                ):
                    prc.cmd_run_agent(args)

            run_process.assert_not_called()

    def test_failed_packet_build_never_publishes_partial_latest(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            state_root = Path(raw)
            previous = state_root / "pr-12" / "20260802T000000Z"
            previous.mkdir(parents=True)
            (previous / "complete.marker").write_text(
                "complete\n", encoding="utf-8"
            )
            bounded_diff = "diff --git a/src/large.py b/src/large.py\n+bounded\n"
            files = [
                {
                    "filename": "src/large.py",
                    "additions": 1,
                    "deletions": 0,
                    "status": "modified",
                    "patch": bounded_diff,
                }
            ]
            classification = {"status": "GITHUB_GREEN_NEEDS_PACKET"}
            coherence = {"ok": True}
            ci_truth = {"verdict": "PASS"}
            args = argparse.Namespace(
                pr=12,
                state_root=str(state_root),
                allow_pending=False,
            )

            with (
                mock.patch.object(prc, "fetch_pr_view", return_value=_current_pr()),
                mock.patch.object(prc, "repo_name", return_value=REPO),
                mock.patch.object(
                    prc, "fetch_pr_files_at_revision", return_value=files
                ),
                mock.patch.object(
                    prc,
                    "fetch_review_threads",
                    return_value={"ok": True, "unresolved": []},
                ),
                mock.patch.object(
                    prc, "fetch_pr_diff_at_revision", return_value=bounded_diff
                ),
                mock.patch.object(
                    prc, "classify_pr", return_value=classification
                ),
                mock.patch.object(
                    prc, "coherence_results", return_value=coherence
                ),
                mock.patch.object(prc, "ci_truth_for_pr", return_value=ci_truth),
                mock.patch.object(
                    prc, "render_packet_markdown", return_value="bounded packet\n"
                ),
                mock.patch.object(prc, "stamp", return_value="20260802T010000Z"),
                mock.patch.object(
                    Path,
                    "write_bytes",
                    new=self._fail_claude_prompt_write(Path.write_bytes),
                ),
            ):
                with self.assertRaisesRegex(OSError, "prompt write failure"):
                    prc.cmd_packet(args)

            self.assertFalse(
                (state_root / "pr-12" / "20260802T010000Z").exists()
            )
            self.assertFalse(list(state_root.glob(".pr-12-20260802T010000Z-*")))
            self.assertEqual(prc.latest_packet_dir_or_none(state_root, 12), previous)

    @staticmethod
    def _fail_claude_prompt_write(original):
        def fail(path: Path, payload: bytes) -> int:
            if path.name == "PROMPT_CLAUDE.md":
                raise OSError("injected prompt write failure")
            return original(path, payload)

        return fail

    def test_renamed_hot_source_path_remains_high_risk(self) -> None:
        risk = prc.risk_from_files(
            [
                {
                    "filename": "docs/retired.md",
                    "previous_filename": "scripts/runtime/pr_merge_control.py",
                    "additions": 1,
                    "deletions": 1,
                    "status": "renamed",
                }
            ]
        )

        self.assertEqual(risk["level"], "HIGH")

    def test_live_base_or_head_drift_remains_blocked(self) -> None:
        called = False

        def runner(*_args, **_kwargs):
            nonlocal called
            called = True
            return prc.CommandResult(0, "merged", "")

        receipt = prc.run_mike_merge_authority(
            pr_number=12,
            gate=_candidate_gate(base_cas_enforced=True),
            method="squash",
            auto=False,
            runner=runner,
            pr_fetcher=lambda _pr: {
                "number": 12,
                "baseRefOid": "c" * 40,
                "headRefOid": HEAD,
            },
        )

        self.assertFalse(called)
        self.assertEqual(receipt["status"], "SKIPPED")

    def test_review_input_is_immune_to_evidence_aba(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            packet_dir = Path(raw)
            prc.write_json(packet_dir / "FACTS.json", _facts())
            for name in prc.REVIEW_EVIDENCE_FILES:
                path = packet_dir / name
                if not path.exists():
                    path.write_text(f"evidence {name}\n", encoding="utf-8")
            diff_path = packet_dir / "DIFF.patch"
            original = "trusted immutable diff\n"
            diff_path.write_text(original, encoding="utf-8")

            def aba_mutation(_command, prompt, _env, **_kwargs):
                diff_path.write_text("malicious transient diff\n", encoding="utf-8")
                diff_path.write_text(original, encoding="utf-8")
                observed = "original" if original in prompt else "malicious"
                return {
                    "status": "completed",
                    "exit_code": 0,
                    "raw_return_code": 0,
                    "timed_out": False,
                    "killed": "none",
                    "stdout": (
                        "## Verdict\nAPPROVE\n\n## Findings\n"
                        f"1. reviewer received {observed} captured evidence\n"
                    ),
                    "stderr": "",
                    "duration_s": 0.5,
                }

            args = argparse.Namespace(
                pr=12,
                packet_dir=str(packet_dir),
                state_root=str(packet_dir.parent),
                agent="codex",
                timeout_s=30,
                kill_grace_s=1,
            )
            with (
                mock.patch.object(
                    prc,
                    "review_command_and_env",
                    return_value=(["codex", "exec"], {}),
                ),
                mock.patch.object(prc, "run_agent_process", side_effect=aba_mutation),
            ):
                result = prc.cmd_run_agent(args)

            review = (packet_dir / "codex_review.md").read_text(encoding="utf-8")
            status = prc.load_agent_review_status(
                packet_dir,
                "codex",
                repo=REPO,
                pr_number=12,
                base_sha=BASE,
                head_sha=HEAD,
            )

        self.assertEqual(result, 0)
        self.assertIn("reviewer received original captured evidence", review)
        self.assertNotIn("malicious transient diff", review)
        self.assertTrue(status["receipt_valid"])

    def test_merge_execution_requires_proven_base_cas(self) -> None:
        called = False

        def runner(*_args, **_kwargs):
            nonlocal called
            called = True
            return prc.CommandResult(0, "merged", "")

        receipt = prc.run_mike_merge_authority(
            pr_number=12,
            gate=_candidate_gate(base_cas_enforced=False),
            method="squash",
            auto=False,
            runner=runner,
            pr_fetcher=lambda _pr: _current_pr(),
        )

        self.assertFalse(called)
        self.assertEqual(receipt["reason"], "strict base-CAS enforcement is not proven")


if __name__ == "__main__":
    unittest.main()
