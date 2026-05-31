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

    assert command[-1] == "-p"
    assert "ANTHROPIC_API_KEY" not in env


def test_review_receipt_status_rejects_command_error(tmp_path):
    path = tmp_path / "codex_review.md"
    path.write_text(
        "Reading prompt from stdin...\n"
        "Error: failed to initialize in-process app-server client\n",
        encoding="utf-8",
    )

    result = prc.review_receipt_status(path)

    assert result["ok"] is False
    assert result["reason"] == "review command failed"


def test_review_receipt_status_accepts_verdict(tmp_path):
    path = tmp_path / "claude_review.md"
    path.write_text(
        "## Verdict\n"
        "APPROVE\n\n"
        "## Findings\n"
        "No blocking findings.\n",
        encoding="utf-8",
    )

    result = prc.review_receipt_status(path)

    assert result["ok"] is True
    assert result["verdict"] == "APPROVE"


def test_review_receipt_status_accepts_request_changes_for_gate_to_block(tmp_path):
    path = tmp_path / "codex_review.md"
    path.write_text(
        "## Verdict\n"
        "REQUEST_CHANGES\n\n"
        "## Findings\n"
        "1. Blocking issue.\n",
        encoding="utf-8",
    )

    result = prc.review_receipt_status(path)

    assert result["ok"] is True
    assert result["verdict"] == "REQUEST_CHANGES"


def test_build_gate_blocks_when_review_thread_lookup_fails(tmp_path, monkeypatch):
    packet_dir = tmp_path / "packet"
    packet_dir.mkdir()
    prc.write_json(packet_dir / "FACTS.json", {"risk": {"level": "LOW"}})
    for name in ("codex_review.md", "claude_review.md"):
        (packet_dir / name).write_text(
            "## Verdict\nAPPROVE\n\n## Findings\nNo blocking findings.\n",
            encoding="utf-8",
        )

    args = SimpleNamespace(
        packet_dir=str(packet_dir),
        state_root=str(tmp_path),
        pr=42,
        allow_pending=False,
        human_approved=False,
    )

    monkeypatch.setattr(
        prc,
        "fetch_pr_view",
        lambda _pr: {
            "number": 42,
            "title": "ok",
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
