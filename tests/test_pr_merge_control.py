from types import SimpleNamespace

from scripts.runtime import pr_merge_control as prc


def test_classify_pr_blocks_failing_checks():
    pr = {
        "number": 1,
        "title": "bad",
        "isDraft": False,
        "mergeable": "MERGEABLE",
        "reviewDecision": "APPROVED",
        "statusCheckRollup": [
            {"name": "tests", "status": "COMPLETED", "conclusion": "FAILURE"},
        ],
    }

    result = prc.classify_pr(pr)

    assert result["status"] == "BLOCKED_CHECKS"
    assert result["checks"]["failing"] == ["tests"]


def test_classify_pr_requires_packet_when_github_green():
    pr = {
        "number": 2,
        "title": "good",
        "isDraft": False,
        "mergeable": "MERGEABLE",
        "reviewDecision": "APPROVED",
        "statusCheckRollup": [
            {"name": "tests", "status": "COMPLETED", "conclusion": "SUCCESS"},
        ],
    }

    result = prc.classify_pr(pr)

    assert result["status"] == "GITHUB_GREEN_NEEDS_PACKET"
    assert result["checks"]["passing"] == ["tests"]


def test_classify_pr_blocks_unknown_non_success_conclusion():
    pr = {
        "number": 3,
        "title": "startup failed",
        "isDraft": False,
        "mergeable": "MERGEABLE",
        "reviewDecision": "APPROVED",
        "statusCheckRollup": [
            {"name": "CodeQL", "status": "COMPLETED", "conclusion": "STARTUP_FAILURE"},
        ],
    }

    result = prc.classify_pr(pr)

    assert result["status"] == "BLOCKED_CHECKS"
    assert result["checks"]["failing"] == ["CodeQL"]


def test_classify_pr_blocks_unrecognized_completed_conclusion():
    pr = {
        "number": 4,
        "title": "weird",
        "isDraft": False,
        "mergeable": "MERGEABLE",
        "reviewDecision": "APPROVED",
        "statusCheckRollup": [
            {"name": "custom", "status": "COMPLETED", "conclusion": "BOGUS"},
        ],
    }

    result = prc.classify_pr(pr)

    assert result["status"] == "BLOCKED_CHECKS"
    assert result["checks"]["failing"] == ["custom:BOGUS"]


def test_classify_pr_blocks_empty_check_rollup():
    pr = {
        "number": 5,
        "title": "no checks",
        "isDraft": False,
        "mergeable": "MERGEABLE",
        "reviewDecision": "APPROVED",
        "statusCheckRollup": [],
    }

    result = prc.classify_pr(pr)

    assert result["status"] == "BLOCKED_CHECKS"
    assert result["checks"]["unknown"] == ["no status checks reported"]


def test_classify_pr_ignores_superseded_cancelled_duplicate_check():
    pr = {
        "number": 6,
        "title": "rerun",
        "isDraft": False,
        "mergeable": "MERGEABLE",
        "reviewDecision": "APPROVED",
        "statusCheckRollup": [
            {
                "name": "Coherence Delta PR body",
                "status": "COMPLETED",
                "conclusion": "CANCELLED",
                "startedAt": "2026-05-31T12:13:36Z",
                "completedAt": "2026-05-31T12:13:41Z",
            },
            {
                "name": "Coherence Delta PR body",
                "status": "COMPLETED",
                "conclusion": "SUCCESS",
                "startedAt": "2026-05-31T12:13:44Z",
                "completedAt": "2026-05-31T12:13:51Z",
            },
        ],
    }

    result = prc.classify_pr(pr)

    assert result["status"] == "GITHUB_GREEN_NEEDS_PACKET"
    assert result["checks"]["failing"] == []
    assert result["checks"]["passing"] == ["Coherence Delta PR body"]


def test_classify_pr_blocks_latest_duplicate_check_failure():
    pr = {
        "number": 7,
        "title": "rerun failed",
        "isDraft": False,
        "mergeable": "MERGEABLE",
        "reviewDecision": "APPROVED",
        "statusCheckRollup": [
            {
                "name": "DocOps integrity gate",
                "status": "COMPLETED",
                "conclusion": "SUCCESS",
                "startedAt": "2026-05-31T12:13:36Z",
                "completedAt": "2026-05-31T12:13:41Z",
            },
            {
                "name": "DocOps integrity gate",
                "status": "COMPLETED",
                "conclusion": "FAILURE",
                "startedAt": "2026-05-31T12:13:44Z",
                "completedAt": "2026-05-31T12:13:51Z",
            },
        ],
    }

    result = prc.classify_pr(pr)

    assert result["status"] == "BLOCKED_CHECKS"
    assert result["checks"]["failing"] == ["DocOps integrity gate"]


def test_coherence_results_rejects_placeholder_field():
    body = """
- Organ touched: docs/governance
- Declared-vs-actual gap closed: TODO
- Proof that re-reads the map: read COHERENCE_DELTA.md
- New drift introduced: none
"""

    result = prc.coherence_results(body)

    assert result["ok"] is False
    assert result["fields"]["Declared-vs-actual gap closed"]["ok"] is False


def test_coherence_results_rejects_bold_placeholder_without_swallowing_next_field():
    body = """
- **Organ touched:** docs/governance
- **Declared-vs-actual gap closed:** TODO
- **Proof that re-reads the map:** checked the generated inventory.
- **New drift introduced:** None
"""

    result = prc.coherence_results(body)

    assert result["ok"] is False
    assert result["fields"]["Declared-vs-actual gap closed"]["value"] == "TODO"


def test_coherence_results_accepts_substantive_fields():
    body = """
- Organ touched: `scripts/runtime/pr_merge_control.py` (operator review lane)
- Declared-vs-actual gap closed: makes PR review receipts explicit before merge.
- Proof that re-reads the map: checked COHERENCE_DELTA.md and AgentOps boundary.
- New drift introduced: no runtime authority change; merge command stays confirmation-gated.
"""

    result = prc.coherence_results(body)

    assert result["ok"] is True


def test_coherence_results_accepts_bold_field_with_colon_inside_bold():
    body = """
- **Organ touched:** `inter_agent/devin/outbound/` additive rendezvous surface.
- **Declared-vs-actual gap closed:** merged outbound response now exists.
- **Proof that re-reads the map:** rechecked spine imports and loop map.
- **New drift introduced:** two markdown receipts; no runtime path changed.
"""

    result = prc.coherence_results(body)

    assert result["ok"] is True


def test_coherence_results_accepts_no_new_drift_statement():
    body = """
- Organ touched: governance / docs / state
- Declared-vs-actual gap closed: stale operational surfaces are refreshed.
- Proof that re-reads the map: `make docops-integrity` passes.
- New drift introduced: None
"""

    result = prc.coherence_results(body)

    assert result["ok"] is True


def test_risk_from_files_flags_hot_paths():
    files = [
        {"filename": "dharma_swarm/telos_gates.py", "additions": 3, "deletions": 1},
        {"filename": "tests/test_telos.py", "additions": 5, "deletions": 0},
    ]

    result = prc.risk_from_files(files)

    assert result["level"] == "CRITICAL"
    assert "dharma_swarm/telos_gates.py" in result["hot_paths"]


def test_claude_review_env_scrubs_anthropic_api_key_by_default():
    command, env = prc.review_command_and_env(
        "claude",
        {
            "ANTHROPIC_API_KEY": "depleted",
            "PATH": "/usr/bin",
        },
    )

    assert "-p" in command
    assert "--max-turns" in command
    assert "ANTHROPIC_API_KEY" not in env


def test_codex_review_defaults_to_bounded_reasoning():
    command, _ = prc.review_command_and_env("codex", {"PATH": "/usr/bin"})

    assert command[:2] == ["codex", "exec"]
    assert "--ephemeral" in command
    assert "model_reasoning_effort=\"medium\"" in command


def test_review_receipt_status_rejects_command_error(tmp_path):
    path = tmp_path / "codex_review.md"
    path.write_text(
        "Reading prompt from stdin...\n"
        "Error: failed to initialize in-process app-server client\n",
        encoding="utf-8",
    )
    prc.write_json(path.with_name("codex_review_receipt.json"), {"exit_code": 0, "reviewed_head_sha": "abc"})

    result = prc.review_receipt_status(path, expected_head_sha="abc")

    assert result["ok"] is False
    assert result["reason"] == "review command failed"


def test_review_receipt_status_accepts_verdict(tmp_path):
    path = tmp_path / "claude_review.md"
    path.write_text(
        "## Verdict\n"
        "APPROVE\n\n"
        "## Findings\n"
        "No blocking findings after checking `scripts/runtime/pr_merge_control.py` "
        "and `tests/test_pr_merge_control.py` for gate behavior.\n\n"
        "## Missing Tests Or Proof\n"
        "No missing proof for this bounded change; `tests/test_pr_merge_control.py` "
        "covers the receipt path.\n\n"
        "## Merge Conditions\n"
        "Merge only after CI is green and the reviewed head SHA still matches.",
        encoding="utf-8",
    )
    prc.write_json(path.with_name("claude_review_receipt.json"), {"exit_code": 0, "reviewed_head_sha": "abc"})

    result = prc.review_receipt_status(path, expected_head_sha="abc")

    assert result["ok"] is True
    assert result["verdict"] == "APPROVE"


def test_review_receipt_status_accepts_request_changes_for_gate_to_block(tmp_path):
    path = tmp_path / "codex_review.md"
    path.write_text(
        "## Verdict\n"
        "REQUEST_CHANGES\n\n"
        "## Findings\n"
        "1. HIGH - `scripts/runtime/pr_merge_control.py` still accepts a shallow "
        "review receipt, so the merge gate can be bypassed.\n\n"
        "## Missing Tests Or Proof\n"
        "`tests/test_pr_merge_control.py` needs a negative test for shallow approvals.\n\n"
        "## Merge Conditions\n"
        "Add the negative test and rerun `pytest -q tests/test_pr_merge_control.py`.",
        encoding="utf-8",
    )
    prc.write_json(path.with_name("codex_review_receipt.json"), {"exit_code": 0, "reviewed_head_sha": "abc"})

    result = prc.review_receipt_status(path, expected_head_sha="abc")

    assert result["ok"] is True
    assert result["verdict"] == "REQUEST_CHANGES"


def test_review_receipt_status_rejects_unedited_verdict_template(tmp_path):
    path = tmp_path / "codex_review.md"
    path.write_text(
        "## Verdict\n"
        "APPROVE | REQUEST_CHANGES | BLOCKED | NEEDS_HUMAN\n\n"
        "## Findings\n"
        "Template was not edited.\n",
        encoding="utf-8",
    )
    prc.write_json(path.with_name("codex_review_receipt.json"), {"exit_code": 0, "reviewed_head_sha": "abc"})

    result = prc.review_receipt_status(path, expected_head_sha="abc")

    assert result["ok"] is False
    assert result["reason"] == "invalid verdict"


def test_review_receipt_status_rejects_nonzero_exit(tmp_path):
    path = tmp_path / "codex_review.md"
    path.write_text(
        "## Verdict\nAPPROVE\n\n"
        "## Findings\nNo blocking findings after reading `scripts/runtime/pr_merge_control.py`.\n\n"
        "## Missing Tests Or Proof\nNo missing local proof for this bounded check.\n\n"
        "## Merge Conditions\nCI must stay green and the reviewed head must match.\n",
        encoding="utf-8",
    )
    prc.write_json(path.with_name("codex_review_receipt.json"), {"exit_code": 1, "reviewed_head_sha": "abc"})

    result = prc.review_receipt_status(path, expected_head_sha="abc")

    assert result["ok"] is False
    assert result["reason"] == "review command exited 1"


def test_review_receipt_status_rejects_stale_head(tmp_path):
    path = tmp_path / "claude_review.md"
    path.write_text(
        "## Verdict\nAPPROVE\n\n"
        "## Findings\nNo blocking findings after reading `scripts/runtime/pr_merge_control.py`.\n\n"
        "## Missing Tests Or Proof\nNo missing local proof for this bounded check.\n\n"
        "## Merge Conditions\nCI must stay green and the reviewed head must match.\n",
        encoding="utf-8",
    )
    prc.write_json(path.with_name("claude_review_receipt.json"), {"exit_code": 0, "reviewed_head_sha": "old"})

    result = prc.review_receipt_status(path, expected_head_sha="new")

    assert result["ok"] is False
    assert result["reason"] == "reviewed head SHA mismatch"


def test_build_gate_blocks_when_review_thread_lookup_fails(tmp_path, monkeypatch):
    packet_dir = tmp_path / "packet"
    packet_dir.mkdir()
    prc.write_json(packet_dir / "FACTS.json", {"risk": {"level": "LOW"}})
    for name in ("codex_review.md", "claude_review.md"):
        (packet_dir / name).write_text(
            "## Verdict\nAPPROVE\n\n"
            "## Findings\nNo blocking findings after reading `scripts/runtime/pr_merge_control.py`.\n\n"
            "## Missing Tests Or Proof\nNo missing local proof for this bounded check.\n\n"
            "## Merge Conditions\nCI must stay green and the reviewed head must match.\n",
            encoding="utf-8",
        )
        prc.write_json(
            packet_dir / name.replace(".md", "_receipt.json"),
            {"exit_code": 0, "reviewed_head_sha": "abc"},
        )

    args = SimpleNamespace(
        packet_dir=str(packet_dir),
        state_root=str(tmp_path),
        pr=42,
        allow_pending=False,
        human_approved=False,
        human_approval_note="",
    )

    monkeypatch.setattr(
        prc,
        "fetch_pr_view",
        lambda _pr: {
            "number": 42,
            "title": "ok",
            "headRefOid": "abc",
            "body": """
- Organ touched: docs
- Declared-vs-actual gap closed: reviewer proof is now strict.
- Proof that re-reads the map: packet and gate both load.
- New drift introduced: None
""",
            "isDraft": False,
            "mergeable": "MERGEABLE",
            "reviewDecision": "APPROVED",
            "statusCheckRollup": [{"name": "tests", "status": "COMPLETED", "conclusion": "SUCCESS"}],
        },
    )
    monkeypatch.setattr(prc, "repo_name", lambda: "owner/repo")
    monkeypatch.setattr(
        prc,
        "fetch_review_threads",
        lambda _pr, _repo: {"ok": False, "error": "rate limited", "unresolved_count": None},
    )

    gate = prc.build_gate(args)

    assert gate["decision"] == "BLOCKED"
    assert "could not verify review threads: rate limited" in gate["blockers"]


def test_build_gate_blocks_when_head_changed_after_packet(tmp_path, monkeypatch):
    packet_dir = tmp_path / "packet"
    packet_dir.mkdir()
    prc.write_json(packet_dir / "FACTS.json", {"risk": {"level": "LOW"}, "pr": {"headRefOid": "old"}})
    for name in ("codex_review.md", "claude_review.md"):
        (packet_dir / name).write_text(
            "## Verdict\nAPPROVE\n\n"
            "## Findings\nNo blocking findings after reading `scripts/runtime/pr_merge_control.py`.\n\n"
            "## Missing Tests Or Proof\nNo missing local proof for this bounded check.\n\n"
            "## Merge Conditions\nCI must stay green and the reviewed head must match.\n",
            encoding="utf-8",
        )
        prc.write_json(
            packet_dir / name.replace(".md", "_receipt.json"),
            {"exit_code": 0, "reviewed_head_sha": "old"},
        )

    args = SimpleNamespace(
        packet_dir=str(packet_dir),
        state_root=str(tmp_path),
        pr=42,
        allow_pending=False,
        human_approved=False,
        human_approval_note="",
    )

    monkeypatch.setattr(
        prc,
        "fetch_pr_view",
        lambda _pr: {
            "number": 42,
            "title": "changed",
            "headRefOid": "new",
            "body": """
- Organ touched: docs
- Declared-vs-actual gap closed: reviewer proof is now strict.
- Proof that re-reads the map: packet and gate both load.
- New drift introduced: None
""",
            "isDraft": False,
            "mergeable": "MERGEABLE",
            "reviewDecision": "APPROVED",
            "statusCheckRollup": [{"name": "tests", "status": "COMPLETED", "conclusion": "SUCCESS"}],
        },
    )
    monkeypatch.setattr(prc, "repo_name", lambda: "owner/repo")
    monkeypatch.setattr(prc, "fetch_review_threads", lambda _pr, _repo: {"ok": True, "unresolved_count": 0})

    gate = prc.build_gate(args)

    assert gate["decision"] == "BLOCKED"
    assert "PR head changed since packet generation" in gate["blockers"]


def test_build_gate_requires_note_for_high_risk_human_approval(tmp_path, monkeypatch):
    packet_dir = tmp_path / "packet"
    packet_dir.mkdir()
    prc.write_json(packet_dir / "FACTS.json", {"risk": {"level": "HIGH"}, "pr": {"headRefOid": "abc"}})
    for name in ("codex_review.md", "claude_review.md"):
        (packet_dir / name).write_text(
            "## Verdict\nAPPROVE\n\n"
            "## Findings\nNo blocking findings after reading `scripts/runtime/pr_merge_control.py`.\n\n"
            "## Missing Tests Or Proof\nNo missing local proof for this bounded check.\n\n"
            "## Merge Conditions\nCI must stay green and the reviewed head must match.\n",
            encoding="utf-8",
        )
        prc.write_json(
            packet_dir / name.replace(".md", "_receipt.json"),
            {"exit_code": 0, "reviewed_head_sha": "abc"},
        )

    args = SimpleNamespace(
        packet_dir=str(packet_dir),
        state_root=str(tmp_path),
        pr=42,
        allow_pending=False,
        human_approved=True,
        human_approval_note="",
    )
    monkeypatch.setattr(
        prc,
        "fetch_pr_view",
        lambda _pr: {
            "number": 42,
            "title": "high",
            "headRefOid": "abc",
            "body": """
- Organ touched: scripts/runtime
- Declared-vs-actual gap closed: high risk merge proof is receipt backed.
- Proof that re-reads the map: packet and gate both load.
- New drift introduced: None
""",
            "isDraft": False,
            "mergeable": "MERGEABLE",
            "reviewDecision": "APPROVED",
            "statusCheckRollup": [{"name": "tests", "status": "COMPLETED", "conclusion": "SUCCESS"}],
        },
    )
    monkeypatch.setattr(prc, "repo_name", lambda: "owner/repo")
    monkeypatch.setattr(prc, "fetch_review_threads", lambda _pr, _repo: {"ok": True, "unresolved_count": 0})

    gate = prc.build_gate(args)

    assert gate["decision"] == "BLOCKED"
    assert "HIGH risk requires --human-approval-note" in gate["blockers"]


def test_render_github_comment_blocks_when_gate_missing():
    packet = {
        "pr": {"number": 42},
        "classification": {"status": "GITHUB_GREEN_NEEDS_PACKET", "mergeable": "MERGEABLE"},
        "risk": {"level": "LOW", "files_changed": 1, "additions": 1, "deletions": 0},
        "coherence": {"ok": True},
    }

    comment = prc.render_github_comment(packet, None)

    assert "Decision: `GATE_MISSING`" in comment
    assert "merge gate output missing or gate execution failed" in comment


def test_claude_review_env_can_opt_into_api_key():
    _, env = prc.review_command_and_env(
        "claude",
        {
            "ANTHROPIC_API_KEY": "funded",
            "DHARMA_CLAUDE_REVIEW_USE_API_KEY": "1",
            "PATH": "/usr/bin",
        },
    )

    assert env["ANTHROPIC_API_KEY"] == "funded"


def test_review_timeout_seconds_defaults_and_validates():
    assert prc.review_timeout_seconds("codex", {}) == 600
    assert prc.review_timeout_seconds("claude", {"CLAUDE_REVIEW_TIMEOUT_SECONDS": "90"}) == 90


def test_review_timeout_seconds_rejects_too_short():
    try:
        prc.review_timeout_seconds("codex", {"CODEX_REVIEW_TIMEOUT_SECONDS": "5"})
    except prc.PRControlError as exc:
        assert "at least 30 seconds" in str(exc)
    else:
        raise AssertionError("expected PRControlError")


def test_review_receipt_status_rejects_shallow_approval(tmp_path):
    path = tmp_path / "codex_review.md"
    path.write_text(
        "## Verdict\n"
        "APPROVE\n\n"
        "## Findings\n"
        "No blocking findings.\n\n"
        "## Missing Tests Or Proof\n"
        "None.\n\n"
        "## Merge Conditions\n"
        "Ready.\n",
        encoding="utf-8",
    )
    prc.write_json(path.with_name("codex_review_receipt.json"), {"exit_code": 0, "reviewed_head_sha": "abc"})

    result = prc.review_receipt_status(path, expected_head_sha="abc")

    assert result["ok"] is False
    assert result["reason"] in {
        "Findings section is too thin",
        "Missing Tests Or Proof section is too thin",
        "Merge Conditions section is too thin",
        "review lacks concrete file/path evidence",
    }


def test_review_receipt_status_rejects_missing_review_sections(tmp_path):
    path = tmp_path / "codex_review.md"
    path.write_text(
        "## Verdict\n"
        "APPROVE\n\n"
        "## Findings\n"
        "No blocking findings after reading `scripts/runtime/pr_merge_control.py`.\n",
        encoding="utf-8",
    )
    prc.write_json(path.with_name("codex_review_receipt.json"), {"exit_code": 0, "reviewed_head_sha": "abc"})

    result = prc.review_receipt_status(path, expected_head_sha="abc")

    assert result["ok"] is False
    assert result["reason"].startswith("missing review sections:")
