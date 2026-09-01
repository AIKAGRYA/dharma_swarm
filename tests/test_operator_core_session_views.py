from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dharma_swarm.operator_core.session_views import build_session_catalog, build_session_detail
from dharma_swarm.operator_core.permission_payloads import build_permission_decision_payload, build_permission_resolution_payload
from dharma_swarm.operator_core.session_store import SessionStore
from dharma_swarm.tui.engine.events import (
    ContextReceipt,
    PermissionDecisionEvent,
    PermissionResolutionEvent,
    SessionEnd,
    SessionStart,
    TextDelta,
    ToolCallComplete,
    ToolResult,
    UserPrompt,
    UsageReport,
)


class OperatorCoreSessionViewTests(unittest.TestCase):
    def test_build_session_catalog_and_detail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = SessionStore(root=Path(temp_dir))
            session_id = store.create_session(
                session_id="sess-1",
                provider_id="codex",
                model_id="gpt-5.4",
                cwd="/repo",
                title="overnight build",
            )
            store.append_event(
                session_id,
                UserPrompt(
                    session_id=session_id,
                    provider_id="codex",
                    content="read README.md",
                ),
            )
            store.append_event(session_id, SessionStart(session_id=session_id, provider_id="codex", model="gpt-5.4"))
            store.append_event(session_id, TextDelta(session_id=session_id, provider_id="codex", content="thinking..."))
            store.append_event(
                session_id,
                ToolCallComplete(
                    session_id=session_id,
                    provider_id="codex",
                    tool_call_id="tool-1",
                    tool_name="Read",
                    arguments='{"file_path":"README.md"}',
                ),
            )
            store.append_event(
                session_id,
                ToolResult(
                    session_id=session_id,
                    provider_id="codex",
                    tool_call_id="tool-1",
                    tool_name="Read",
                    content="ok",
                ),
            )
            store.append_event(session_id, UsageReport(session_id=session_id, provider_id="codex", total_cost_usd=1.5))
            store.append_event(session_id, SessionEnd(session_id=session_id, provider_id="codex", success=True))
            store.finalize_session(session_id, status="completed", total_cost_usd=1.5, total_turns=1)
            decision = build_permission_decision_payload(
                ToolCallComplete(
                    session_id=session_id,
                    provider_id="codex",
                    tool_call_id="tool-approval-1",
                    tool_name="Bash",
                    arguments="git status",
                    provider_options={"requires_confirmation": True},
                )
            )
            resolution = build_permission_resolution_payload(
                action_id=decision["action_id"],
                resolution="approved",
                metadata={"session_id": session_id},
            )
            store.append_event(
                session_id,
                PermissionDecisionEvent(
                    session_id=session_id,
                    provider_id="codex",
                    action_id=str(decision["action_id"]),
                    tool_name=str(decision["tool_name"]),
                    risk=str(decision["risk"]),
                    decision=str(decision["decision"]),
                    rationale=str(decision["rationale"]),
                    policy_source=str(decision["policy_source"]),
                    requires_confirmation=bool(decision["requires_confirmation"]),
                    command_prefix=str(decision["command_prefix"] or "") or None,
                    metadata=dict(decision["metadata"]),
                ),
            )
            store.append_event(
                session_id,
                PermissionResolutionEvent(
                    session_id=session_id,
                    provider_id="codex",
                    action_id=str(resolution["action_id"]),
                    resolution=str(resolution["resolution"]),
                    resolved_at=str(resolution["resolved_at"]),
                    actor=str(resolution["actor"]),
                    summary=str(resolution["summary"]),
                    note=str(resolution["note"] or "") or None,
                    enforcement_state=str(resolution["enforcement_state"]),
                    metadata=dict(resolution["metadata"]),
                ),
            )

            catalog = build_session_catalog(store, cwd="/repo")
            json.dumps(catalog)
            self.assertEqual(catalog["version"], "v1")
            self.assertEqual(catalog["domain"], "session_catalog")
            self.assertEqual(catalog["count"], 1)
            self.assertEqual(catalog["returned_count"], 1)
            self.assertEqual(catalog["limit"], 20)
            self.assertFalse(catalog["has_more"])
            self.assertTrue(catalog["sessions"][0]["replay_ok"])
            self.assertEqual(catalog["sessions"][0]["session"]["session_id"], "sess-1")
            self.assertEqual(catalog["sessions"][0]["total_turns"], 1)
            self.assertEqual(catalog["sessions"][0]["total_cost_usd"], 1.5)
            self.assertEqual(catalog["sessions"][0]["session"]["metadata"]["total_turns"], 1)

            detail = build_session_detail(store, session_id)
            json.dumps(detail)
            self.assertEqual(detail["version"], "v1")
            self.assertEqual(detail["domain"], "session_detail")
            self.assertEqual(detail["session"]["session_id"], "sess-1")
            self.assertEqual(detail["compaction_preview"]["protected_event_types"][0], "user_prompt")
            self.assertEqual(detail["recent_events"][-1]["event_type"], "permission_resolution")
            self.assertIn("session_end", detail["compaction_preview"]["recent_event_types"])
            self.assertEqual(detail["approval_history"]["count"], 1)
            self.assertEqual(detail["approval_history"]["entries"][0]["status"], "approved")

    def test_build_session_catalog_reports_total_separately_from_page_size(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = SessionStore(root=Path(temp_dir))
            for index in range(3):
                session_id = store.create_session(
                    session_id=f"sess-{index}",
                    provider_id="codex",
                    model_id="gpt-5.4",
                    cwd="/repo",
                )
                store.finalize_session(session_id, status="completed", total_turns=0)

            catalog = build_session_catalog(store, cwd="/repo", limit=2)

            self.assertEqual(catalog["count"], 3)
            self.assertEqual(catalog["returned_count"], 2)
            self.assertEqual(catalog["limit"], 2)
            self.assertTrue(catalog["has_more"])
            self.assertEqual(len(catalog["sessions"]), 2)

    def test_session_detail_reserves_context_receipt_outside_recent_tail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = SessionStore(root=Path(temp_dir))
            session_id = store.create_session(
                session_id="sess-long-context",
                provider_id="claude",
                model_id="claude-sonnet-5",
                cwd="/repo",
            )
            store.append_event(
                session_id,
                UserPrompt(session_id=session_id, content="bounded context"),
            )
            store.append_event(
                session_id,
                ContextReceipt(
                    session_id=session_id,
                    provider_id="claude",
                    model_id="claude-sonnet-5",
                    source_epoch="sha256:epoch",
                    context_digest="sha256:digest",
                    disposition="attached_redacted",
                    lane_outcome="completed",
                ),
            )
            store.append_event(
                session_id,
                SessionStart(
                    session_id=session_id,
                    provider_id="claude",
                    model="claude-sonnet-5",
                ),
            )
            for index in range(100):
                store.append_event(
                    session_id,
                    TextDelta(
                        session_id=session_id,
                        provider_id="claude",
                        content=f"chunk-{index}",
                    ),
                )
            store.append_event(
                session_id,
                SessionEnd(
                    session_id=session_id,
                    provider_id="claude",
                    success=True,
                ),
            )

            detail = build_session_detail(store, session_id, transcript_limit=80)

            self.assertEqual(detail["compaction_preview"]["event_count"], 104)
            self.assertIn(
                "context_receipt",
                detail["compaction_preview"]["protected_event_types"],
            )
            self.assertEqual(len(detail["recent_events"]), 80)
            visible_types = [event["event_type"] for event in detail["recent_events"]]
            self.assertEqual(visible_types[:3], [
                "user_prompt",
                "context_receipt",
                "session_start",
            ])
            self.assertEqual(visible_types[-1], "session_end")

    def test_build_session_catalog_matches_normalized_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = SessionStore(root=Path(temp_dir))
            session_id = store.create_session(
                session_id="sess-1",
                provider_id="codex",
                model_id="gpt-5.4",
                cwd=f"{temp_dir}/repo/..",
                title="normalized path",
            )
            store.finalize_session(session_id, status="completed", total_turns=0)

            catalog = build_session_catalog(store, cwd=temp_dir)

            self.assertEqual(catalog["count"], 1)
            self.assertEqual(catalog["sessions"][0]["session"]["session_id"], "sess-1")

    def test_build_session_detail_surfaces_replay_degradation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = SessionStore(root=root)
            session_id = store.create_session(
                session_id="sess-1",
                provider_id="codex",
                model_id="gpt-5.4",
                cwd="/repo",
                title="replay degraded",
            )
            snapshots_path = root / session_id / "snapshots.jsonl"
            snapshots_path.unlink()

            detail = build_session_detail(store, session_id)

            self.assertFalse(detail["replay_ok"])
            self.assertEqual(
                detail["replay_issues"],
                ["snapshot log missing", "transcript_empty"],
            )
            self.assertEqual(detail["compaction_preview"]["event_count"], 0)
            self.assertEqual(detail["recent_events"], [])

    def test_replay_promotion_requires_correlated_terminal_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = SessionStore(root=Path(temp_dir))
            session_id = store.create_session(
                session_id="sess-1",
                provider_id="primary",
                model_id="provisional",
                cwd="/repo",
            )
            self.assertEqual(
                store.verify_session_replay(session_id),
                (False, ["transcript_empty"]),
            )

            store.append_event(
                session_id,
                UserPrompt(
                    session_id=session_id,
                    provider_id="winner",
                    content="keep going",
                ),
            )
            store.append_event(
                session_id,
                SessionStart(
                    session_id=session_id,
                    provider_id="winner",
                    model="actual-model",
                ),
            )
            store.append_event(
                session_id,
                SessionEnd(
                    session_id=session_id,
                    provider_id="winner",
                    success=True,
                ),
            )
            store.update_session_route(
                session_id,
                provider_id="winner",
                model_id="actual-model",
            )

            ok, issues = store.verify_session_replay(session_id)
            self.assertFalse(ok)
            self.assertEqual(
                issues,
                ["metadata_status_mismatch:running!=completed"],
            )

            store.finalize_session(session_id, status="completed", total_turns=1)
            self.assertEqual(
                store.verify_session_replay(session_id),
                (True, ["replay_unproven_pre_receipt_era"]),
            )
            meta = store.load_meta(session_id)
            self.assertEqual(
                (meta["provider_id"], meta["model_id"]),
                ("winner", "actual-model"),
            )


if __name__ == "__main__":
    unittest.main()
