from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from dharma_swarm.chetana import safe_write as safe_write_module
from dharma_swarm.chetana import wiki_compiler as wiki_compiler_module
from dharma_swarm.chetana.wiki_compiler import (
    IntegrationPlanError,
    compile_integration_plan,
)
from dharma_swarm.chetana.wiki_log import append_wiki_log


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_plan(
    path: Path,
    *,
    source: Path,
    pages: list[dict[str, object]],
    authority: str = "canonical-ledger",
) -> Path:
    normalized_pages: list[dict[str, object]] = []
    for page in pages:
        normalized_operations: list[dict[str, object]] = []
        for raw_operation in page["operations"]:  # type: ignore[index]
            operation = dict(raw_operation)  # type: ignore[arg-type]
            claim_id = operation.pop("claim_id", None)
            if "claim_bindings" not in operation:
                operation["claim_bindings"] = (
                    [{"evidence_id": "ledger", "claim_id": claim_id}]
                    if claim_id
                    else []
                )
            normalized_operations.append(operation)
        normalized_pages.append(page | {"operations": normalized_operations})
    claim_ids = sorted(
        {
            str(binding["claim_id"])
            for page in normalized_pages
            for operation in page["operations"]  # type: ignore[index]
            for binding in operation.get("claim_bindings", [])  # type: ignore[union-attr]
            if binding["evidence_id"] == "ledger"
        }
    )
    source_text = source.read_text(encoding="utf-8")

    def locator_for(claim_id: str) -> str:
        matching_lines = [line for line in source_text.splitlines() if claim_id in line]
        return matching_lines[0] if len(matching_lines) == 1 else claim_id

    payload = {
        "schema_version": "chetana.integration.v2",
        "plan_id": "mi-c05-m024",
        "sources": [
            {
                "evidence_id": "ledger",
                "path": str(source),
                "sha256": _sha256(source),
                "observed_at": "2025-01-01T01:00:00+09:00",
                "declared_authority": authority,
                "declared_verifier": "sha256 + exact replacement preconditions",
                "claims": [
                    {"claim_id": claim_id, "locator": locator_for(claim_id)}
                    for claim_id in claim_ids
                ],
            }
        ],
        "rationale": "Propagate the canonical R_V correction into every affected page.",
        "pages": normalized_pages,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def _configured_authority_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CHETANA_CANONICAL_LEDGER_ROOTS", str(tmp_path))
    monkeypatch.setenv("CHETANA_AUDITED_SOURCE_ROOTS", str(tmp_path))


def test_dry_run_plans_multi_page_correction_without_writing(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    source = _write(
        tmp_path / "ledger.md",
        ("C05: AUROC 0.904\nM024: distributed L0-L5 source; L27 is a late readout\n"),
    )
    metric = _write(
        wiki / "concepts" / "r-v-metric.md",
        "# R_V\n\nAUROC = 0.909. Causal validation at L27 confirms geometry is upstream of behavior.\n",
    )
    paper = _write(
        wiki / "concepts" / "r-v-paper.md",
        "# Paper\n\nThe reported AUROC is 0.909.\n",
    )
    before = {metric: metric.read_text(), paper: paper.read_text()}
    plan = _write_plan(
        tmp_path / "plan.json",
        source=source,
        pages=[
            {
                "path": "concepts/r-v-metric.md",
                "expected_sha256": _sha256(metric),
                "operations": [
                    {
                        "mode": "correct",
                        "claim_id": "C05",
                        "old": "AUROC = 0.909",
                        "new": "AUROC = 0.904",
                        "expected_count": 1,
                    },
                    {
                        "mode": "correct",
                        "claim_id": "M024",
                        "old": "Causal validation at L27 confirms geometry is upstream of behavior.",
                        "new": (
                            "Path patching finds a distributed L0-L5 source; R_V at L27 "
                            "is a downstream readout, not the mechanism."
                        ),
                        "expected_count": 1,
                    },
                ],
            },
            {
                "path": "concepts/r-v-paper.md",
                "expected_sha256": _sha256(paper),
                "operations": [
                    {
                        "mode": "correct",
                        "claim_id": "C05",
                        "old": "AUROC is 0.909",
                        "new": "AUROC is 0.904",
                        "expected_count": 1,
                    }
                ],
            },
        ],
    )

    result = compile_integration_plan(plan, wiki_root=wiki)

    assert not result.applied
    assert [change.path for change in result.changes] == [metric, paper]
    assert "-AUROC = 0.909" in result.diff
    assert "+AUROC = 0.904" in result.diff
    assert {path: path.read_text() for path in before} == before
    assert not (wiki / "log.md").exists()


def test_apply_is_atomic_preserves_source_and_records_typed_receipt(
    tmp_path: Path,
) -> None:
    wiki = tmp_path / "wiki"
    source = _write(tmp_path / "ledger.md", "C05: AUROC 0.904\n")
    first = _write(wiki / "concepts" / "first.md", "AUROC 0.909\n")
    second = _write(wiki / "mocs" / "second.md", "Headline AUROC 0.909\n")
    source_before = source.read_bytes()
    plan = _write_plan(
        tmp_path / "plan.json",
        source=source,
        pages=[
            {
                "path": "concepts/first.md",
                "expected_sha256": _sha256(first),
                "operations": [
                    {
                        "mode": "correct",
                        "claim_id": "C05",
                        "old": "0.909",
                        "new": "0.904",
                        "expected_count": 1,
                    }
                ],
            },
            {
                "path": "mocs/second.md",
                "expected_sha256": _sha256(second),
                "operations": [
                    {
                        "mode": "correct",
                        "claim_id": "C05",
                        "old": "0.909",
                        "new": "0.904",
                        "expected_count": 1,
                    }
                ],
            },
        ],
    )

    result = compile_integration_plan(
        plan, wiki_root=wiki, apply=True, reviewer="operator"
    )

    assert result.applied
    assert all("0.904" in path.read_text() for path in (first, second))
    assert source.read_bytes() == source_before
    log = (wiki / "log.md").read_text(encoding="utf-8")
    assert "compile | mi-c05-m024" in log
    assert "evidence: ledger:canonical-ledger:" in log
    assert "claim_ids: C05" in log
    assert f"plan_sha256: {_sha256(plan)}" in log
    assert "targets: concepts/first.md, mocs/second.md" in log
    assert "operation_bindings:" in log
    assert '"claim_bindings":[{"claim_id":"C05","evidence_id":"ledger"}]' in log
    assert '"mode":"correct"' in log
    assert f'"before_sha256":"{_sha256(first)}"' not in log
    assert result.changes[0].before_sha256 in log
    assert result.changes[0].after_sha256 in log
    assert "reviewer: operator" in log


def test_sequential_operations_cannot_cancel_to_a_false_applied_change(
    tmp_path: Path,
) -> None:
    wiki = tmp_path / "wiki"
    source = _write(tmp_path / "ledger.md", "C05: canonical claim\n")
    page = _write(wiki / "concepts" / "metric.md", "A\n")
    plan = _write_plan(
        tmp_path / "plan.json",
        source=source,
        pages=[
            {
                "path": "concepts/metric.md",
                "expected_sha256": _sha256(page),
                "operations": [
                    {
                        "mode": "correct",
                        "claim_id": "C05",
                        "old": "A",
                        "new": "B",
                    },
                    {
                        "mode": "correct",
                        "claim_id": "C05",
                        "old": "B",
                        "new": "A",
                    },
                ],
            }
        ],
    )

    with pytest.raises(IntegrationPlanError, match="cancel to a no-op"):
        compile_integration_plan(plan, wiki_root=wiki, apply=True, reviewer="operator")

    assert page.read_text(encoding="utf-8") == "A\n"
    assert not (wiki / "log.md").exists()


def test_apply_rolls_back_written_pages_after_later_write_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wiki = tmp_path / "wiki"
    source = _write(tmp_path / "ledger.md", "C05: AUROC 0.904\n")
    first = _write(wiki / "concepts" / "first.md", "AUROC 0.909\n")
    second = _write(wiki / "concepts" / "second.md", "AUROC 0.909\n")
    before = {path: path.read_bytes() for path in (first, second)}
    plan = _write_plan(
        tmp_path / "plan.json",
        source=source,
        pages=[
            {
                "path": f"concepts/{path.name}",
                "expected_sha256": _sha256(path),
                "operations": [
                    {
                        "mode": "correct",
                        "claim_id": "C05",
                        "old": "0.909",
                        "new": "0.904",
                        "expected_count": 1,
                    }
                ],
            }
            for path in (first, second)
        ],
    )
    real_replace = safe_write_module.os.replace
    calls = 0

    def fail_second_write(
        source: str,
        target: str,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
    ) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected write failure")
        real_replace(
            source,
            target,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
        )

    monkeypatch.setattr(safe_write_module.os, "replace", fail_second_write)

    with pytest.raises(IntegrationPlanError, match="integration apply failed"):
        compile_integration_plan(plan, wiki_root=wiki, apply=True, reviewer="operator")

    assert {path: path.read_bytes() for path in before} == before
    assert not (wiki / "log.md").exists()


def test_apply_requires_a_named_reviewer(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    source = _write(tmp_path / "ledger.md", "C05: AUROC 0.904\n")
    page = _write(wiki / "concepts" / "metric.md", "AUROC 0.909\n")
    plan = _write_plan(
        tmp_path / "plan.json",
        source=source,
        pages=[
            {
                "path": "concepts/metric.md",
                "expected_sha256": _sha256(page),
                "operations": [
                    {
                        "mode": "correct",
                        "claim_id": "C05",
                        "old": "0.909",
                        "new": "0.904",
                        "expected_count": 1,
                    }
                ],
            }
        ],
    )

    with pytest.raises(IntegrationPlanError, match="named reviewer"):
        compile_integration_plan(plan, wiki_root=wiki, apply=True)
    assert page.read_text(encoding="utf-8") == "AUROC 0.909\n"


def test_apply_refuses_to_invalidate_active_trust_manifest(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    source = _write(tmp_path / "ledger.md", "C05: AUROC 0.904\n")
    page = _write(wiki / "concepts" / "metric.md", "AUROC 0.909\n")
    _write(wiki / "concepts" / "MANIFEST.jsonl", "{}\n")
    plan = _write_plan(
        tmp_path / "plan.json",
        source=source,
        pages=[
            {
                "path": "concepts/metric.md",
                "expected_sha256": _sha256(page),
                "operations": [
                    {
                        "mode": "correct",
                        "claim_id": "C05",
                        "old": "0.909",
                        "new": "0.904",
                        "expected_count": 1,
                    }
                ],
            }
        ],
    )

    with pytest.raises(IntegrationPlanError, match="page-plus-manifest"):
        compile_integration_plan(plan, wiki_root=wiki, apply=True, reviewer="operator")
    assert page.read_text(encoding="utf-8") == "AUROC 0.909\n"


def test_environment_selected_manifest_also_blocks_compiler_apply(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wiki = tmp_path / "wiki"
    source = _write(tmp_path / "ledger.md", "C05: AUROC 0.904\n")
    page = _write(wiki / "concepts" / "metric.md", "AUROC 0.909\n")
    manifest = wiki / "signed-trust-projection.jsonl"
    _write(manifest, "{}\n")
    monkeypatch.setenv("DHARMA_WIKI_MANIFEST", str(manifest))
    plan = _write_plan(
        tmp_path / "plan.json",
        source=source,
        pages=[
            {
                "path": "concepts/metric.md",
                "expected_sha256": _sha256(page),
                "operations": [
                    {
                        "mode": "correct",
                        "claim_id": "C05",
                        "old": "0.909",
                        "new": "0.904",
                    }
                ],
            }
        ],
    )

    with pytest.raises(IntegrationPlanError, match="page-plus-manifest"):
        compile_integration_plan(plan, wiki_root=wiki, apply=True, reviewer="operator")

    assert page.read_text(encoding="utf-8") == "AUROC 0.909\n"


def test_declared_ledger_outside_operator_authority_root_is_not_authoritative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    trusted = tmp_path / "trusted-ledgers"
    trusted.mkdir()
    monkeypatch.setenv("CHETANA_CANONICAL_LEDGER_ROOTS", str(trusted))
    wiki = tmp_path / "wiki"
    source = _write(tmp_path / "FAKE_LEDGER.md", "C05: arbitrary assertion\n")
    page = _write(wiki / "concepts" / "metric.md", "original\n")
    plan = _write_plan(
        tmp_path / "plan.json",
        source=source,
        pages=[
            {
                "path": "concepts/metric.md",
                "expected_sha256": _sha256(page),
                "operations": [
                    {
                        "mode": "correct",
                        "claim_id": "C05",
                        "old": "original",
                        "new": "unrelated rewrite",
                    }
                ],
            }
        ],
    )

    with pytest.raises(IntegrationPlanError, match="outside configured authority"):
        compile_integration_plan(plan, wiki_root=wiki)

    assert page.read_text(encoding="utf-8") == "original\n"


@pytest.mark.parametrize("mode", ["extend", "qualify", "correct", "retract"])
def test_agent_inference_cannot_directly_rewrite_a_canonical_page(
    tmp_path: Path, mode: str
) -> None:
    wiki = tmp_path / "wiki"
    source = _write(tmp_path / "opinion.md", "H01: model hypothesis\n")
    page = _write(wiki / "concepts" / "claim.md", "Claim.\n")
    new = "Claim.\n\nHypothesis." if mode in {"extend", "qualify"} else "Replacement."
    if mode == "retract":
        new = "Claim. [retracted]"
    plan = _write_plan(
        tmp_path / "plan.json",
        source=source,
        authority="agent-inference",
        pages=[
            {
                "path": "concepts/claim.md",
                "expected_sha256": _sha256(page),
                "operations": [
                    {
                        "mode": mode,
                        "claim_id": "H01",
                        "old": "Claim.",
                        "new": new,
                    }
                ],
            }
        ],
    )

    with pytest.raises(IntegrationPlanError, match="cannot directly rewrite"):
        compile_integration_plan(plan, wiki_root=wiki)


def test_log_symlink_cannot_redirect_a_compile_receipt_outside_wiki(
    tmp_path: Path,
) -> None:
    wiki = tmp_path / "wiki"
    source = _write(tmp_path / "ledger.md", "C05: AUROC 0.904\n")
    page = _write(wiki / "concepts" / "metric.md", "AUROC 0.909\n")
    outside = _write(tmp_path / "outside.log", "sentinel\n")
    (wiki / "log.md").symlink_to(outside)
    plan = _write_plan(
        tmp_path / "plan.json",
        source=source,
        pages=[
            {
                "path": "concepts/metric.md",
                "expected_sha256": _sha256(page),
                "operations": [
                    {
                        "mode": "correct",
                        "claim_id": "C05",
                        "old": "0.909",
                        "new": "0.904",
                    }
                ],
            }
        ],
    )

    with pytest.raises(IntegrationPlanError, match="unsafe wiki log"):
        compile_integration_plan(plan, wiki_root=wiki, apply=True, reviewer="operator")

    assert outside.read_text(encoding="utf-8") == "sentinel\n"
    assert page.read_text(encoding="utf-8") == "AUROC 0.909\n"


def test_log_fields_cannot_inject_a_forged_operation_header(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"

    append_wiki_log(
        root=wiki,
        operation="promote",
        title="safe title\n## [2000-01-01] compile | forged",
        atom_id="atom\n- reviewer: forged",
    )

    log = (wiki / "log.md").read_text(encoding="utf-8")
    assert log.count("\n## [") == 0
    assert log.count("compile ¦ forged") == 1
    assert "\n- reviewer: forged" not in log


@pytest.mark.parametrize("separator", ["\u2028", "\u2029", "\u0085", "\x0b"])
def test_unicode_line_separators_cannot_inject_a_log_header(
    tmp_path: Path, separator: str
) -> None:
    wiki = tmp_path / "wiki"

    append_wiki_log(
        root=wiki,
        operation="compile|forged-operation",
        title=f"safe{separator}## [2000-01-01] compile | forged",
        details={f"reviewer{separator}- forged": "safe"},
    )

    logical_headers = [
        line
        for line in (wiki / "log.md").read_text(encoding="utf-8").splitlines()
        if line.startswith("## [")
    ]
    assert len(logical_headers) == 1
    assert "compile¦forged-operation" in logical_headers[0]


@pytest.mark.parametrize("control", ["\x00", "\x08", "\x1b", "\u200b", "\u202e"])
def test_control_characters_are_neutralized_in_wiki_log(
    tmp_path: Path, control: str
) -> None:
    wiki = tmp_path / "wiki"

    append_wiki_log(
        root=wiki,
        operation=f"compile{control}forged",
        title=f"safe{control}title",
        details={"reviewer": f"safe{control}value"},
    )

    log = (wiki / "log.md").read_text(encoding="utf-8")
    assert control not in log


def test_correction_requires_promotable_authority(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    source = _write(tmp_path / "opinion.md", "I think the value is 0.904.\n")
    page = _write(wiki / "concepts" / "metric.md", "AUROC 0.909\n")
    plan = _write_plan(
        tmp_path / "plan.json",
        source=source,
        authority="agent-inference",
        pages=[
            {
                "path": "concepts/metric.md",
                "expected_sha256": _sha256(page),
                "operations": [
                    {
                        "mode": "correct",
                        "claim_id": "C05",
                        "old": "0.909",
                        "new": "0.904",
                        "expected_count": 1,
                    }
                ],
            }
        ],
    )

    with pytest.raises(IntegrationPlanError, match="agent-inference.*cannot directly"):
        compile_integration_plan(plan, wiki_root=wiki)
    assert page.read_text() == "AUROC 0.909\n"


def test_correction_claim_must_be_bound_to_canonical_ledger(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    source = _write(tmp_path / "ledger.md", "C05: AUROC 0.904\n")
    page = _write(wiki / "concepts" / "metric.md", "AUROC 0.909\n")
    plan = _write_plan(
        tmp_path / "plan.json",
        source=source,
        pages=[
            {
                "path": "concepts/metric.md",
                "expected_sha256": _sha256(page),
                "operations": [
                    {
                        "mode": "correct",
                        "claim_id": "C99",
                        "old": "0.909",
                        "new": "0.904",
                        "expected_count": 1,
                    }
                ],
            }
        ],
    )
    payload = json.loads(plan.read_text(encoding="utf-8"))
    payload["sources"][0]["claims"] = [{"claim_id": "C05", "locator": "C05"}]
    plan.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(IntegrationPlanError, match="not declared"):
        compile_integration_plan(plan, wiki_root=wiki)
    assert page.read_text(encoding="utf-8") == "AUROC 0.909\n"


def test_claim_id_requires_an_exact_token_in_hashed_evidence(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    source = _write(tmp_path / "ledger.md", "C050: unrelated claim\n")
    page = _write(wiki / "concepts" / "metric.md", "AUROC 0.909\n")
    plan = _write_plan(
        tmp_path / "plan.json",
        source=source,
        pages=[
            {
                "path": "concepts/metric.md",
                "expected_sha256": _sha256(page),
                "operations": [
                    {
                        "mode": "correct",
                        "claim_id": "C05",
                        "old": "0.909",
                        "new": "0.904",
                        "expected_count": 1,
                    }
                ],
            }
        ],
    )

    with pytest.raises(IntegrationPlanError, match="exact claim ID C05: ledger"):
        compile_integration_plan(plan, wiki_root=wiki)


def test_verified_runtime_cannot_correct_a_canonical_claim(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    source = _write(tmp_path / "runtime.py", "# C05\nVALUE = 0.904\n")
    page = _write(wiki / "concepts" / "metric.md", "AUROC 0.909\n")
    plan = _write_plan(
        tmp_path / "plan.json",
        source=source,
        authority="verified-runtime",
        pages=[
            {
                "path": "concepts/metric.md",
                "expected_sha256": _sha256(page),
                "operations": [
                    {
                        "mode": "correct",
                        "claim_id": "C05",
                        "old": "0.909",
                        "new": "0.904",
                        "expected_count": 1,
                    }
                ],
            }
        ],
    )

    with pytest.raises(IntegrationPlanError, match="verified-runtime.*cannot directly"):
        compile_integration_plan(plan, wiki_root=wiki)


def test_each_operation_binds_all_claims_to_named_evidence_sources(
    tmp_path: Path,
) -> None:
    wiki = tmp_path / "wiki"
    contradictions = _write(tmp_path / "contradictions-register.md", "C05: 0.904\n")
    master = _write(tmp_path / "master-ledger.md", "M015: n=196, hook_v only\n")
    page = _write(
        wiki / "concepts" / "metric.md",
        "AUROC 0.909 establishes a universal diagnostic.\n",
    )
    plan = _write_plan(
        tmp_path / "plan.json",
        source=contradictions,
        pages=[
            {
                "path": "concepts/metric.md",
                "expected_sha256": _sha256(page),
                "operations": [
                    {
                        "mode": "correct",
                        "claim_id": "C05",
                        "old": "AUROC 0.909 establishes a universal diagnostic.",
                        "new": "AUROC 0.904 is scoped to n=196 Mistral hook_v rows.",
                        "expected_count": 1,
                    }
                ],
            }
        ],
    )
    payload = json.loads(plan.read_text(encoding="utf-8"))
    payload["sources"].append(
        {
            "evidence_id": "master",
            "path": str(master),
            "sha256": _sha256(master),
            "observed_at": "2025-01-01T01:00:00+09:00",
            "declared_authority": "canonical-ledger",
            "declared_verifier": "sha256 + exact replacement preconditions",
            "claims": [{"claim_id": "M015", "locator": "M015"}],
        }
    )
    operation = payload["pages"][0]["operations"][0]
    operation["claim_bindings"] = [
        {"evidence_id": "ledger", "claim_id": "C05"},
        {"evidence_id": "master", "claim_id": "M015"},
    ]
    plan.write_text(json.dumps(payload), encoding="utf-8")

    result = compile_integration_plan(plan, wiki_root=wiki)

    assert [item.evidence_id for item in result.evidence] == ["ledger", "master"]
    assert "n=196 Mistral hook_v" in result.changes[0].after

    operation["claim_bindings"] = [
        {"evidence_id": "ledger", "claim_id": "C05"},
        {"evidence_id": "ledger", "claim_id": "M015"},
    ]
    plan.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(IntegrationPlanError, match="not declared.*ledger:M015"):
        compile_integration_plan(plan, wiki_root=wiki)


@pytest.mark.parametrize(
    "observed_at",
    [
        "2025-01-01T01:00:00",
        (datetime.now().astimezone() + timedelta(days=1)).isoformat(),
    ],
)
def test_evidence_time_must_be_zoned_and_not_future(
    tmp_path: Path, observed_at: str
) -> None:
    wiki = tmp_path / "wiki"
    source = _write(tmp_path / "ledger.md", "C05: AUROC 0.904\n")
    page = _write(wiki / "concepts" / "metric.md", "AUROC 0.909\n")
    plan = _write_plan(
        tmp_path / "plan.json",
        source=source,
        pages=[
            {
                "path": "concepts/metric.md",
                "expected_sha256": _sha256(page),
                "operations": [
                    {
                        "mode": "correct",
                        "claim_id": "C05",
                        "old": "0.909",
                        "new": "0.904",
                        "expected_count": 1,
                    }
                ],
            }
        ],
    )
    payload = json.loads(plan.read_text(encoding="utf-8"))
    payload["sources"][0]["observed_at"] = observed_at
    plan.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(IntegrationPlanError, match="observed_at"):
        compile_integration_plan(plan, wiki_root=wiki)


def test_all_preconditions_are_checked_before_any_write(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    source = _write(tmp_path / "ledger.md", "C05: AUROC 0.904\n")
    first = _write(wiki / "concepts" / "first.md", "AUROC 0.909\n")
    second = _write(wiki / "concepts" / "second.md", "Already corrected 0.904\n")
    plan = _write_plan(
        tmp_path / "plan.json",
        source=source,
        pages=[
            {
                "path": "concepts/first.md",
                "expected_sha256": _sha256(first),
                "operations": [
                    {
                        "mode": "correct",
                        "claim_id": "C05",
                        "old": "0.909",
                        "new": "0.904",
                        "expected_count": 1,
                    }
                ],
            },
            {
                "path": "concepts/second.md",
                "expected_sha256": _sha256(second),
                "operations": [
                    {
                        "mode": "correct",
                        "claim_id": "C05",
                        "old": "0.909",
                        "new": "0.904",
                        "expected_count": 1,
                    }
                ],
            },
        ],
    )

    with pytest.raises(IntegrationPlanError, match="replacement count"):
        compile_integration_plan(plan, wiki_root=wiki, apply=True, reviewer="operator")
    assert first.read_text() == "AUROC 0.909\n"
    assert second.read_text() == "Already corrected 0.904\n"
    assert not (wiki / "log.md").exists()


@pytest.mark.parametrize(
    "target",
    ["../outside.md", "raw/source.md", "_meta/integrity-report.md", "/tmp/outside.md"],
)
def test_target_write_set_is_bounded(tmp_path: Path, target: str) -> None:
    wiki = tmp_path / "wiki"
    source = _write(tmp_path / "ledger.md", "C05: AUROC 0.904\n")
    plan = _write_plan(
        tmp_path / "plan.json",
        source=source,
        pages=[
            {
                "path": target,
                "expected_sha256": "a" * 64,
                "operations": [
                    {
                        "mode": "correct",
                        "claim_id": "C05",
                        "old": "0.909",
                        "new": "0.904",
                        "expected_count": 1,
                    }
                ],
            }
        ],
    )

    with pytest.raises(IntegrationPlanError, match="target path"):
        compile_integration_plan(plan, wiki_root=wiki)


def test_target_symlink_cannot_escape_an_allowed_content_layer(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    source = _write(tmp_path / "ledger.md", "C05: AUROC 0.904\n")
    protected = _write(wiki / "raw" / "protected.md", "AUROC 0.909\n")
    alias = wiki / "concepts" / "alias.md"
    alias.parent.mkdir(parents=True)
    alias.symlink_to(Path("../raw/protected.md"))
    plan = _write_plan(
        tmp_path / "plan.json",
        source=source,
        pages=[
            {
                "path": "concepts/alias.md",
                "expected_sha256": _sha256(protected),
                "operations": [
                    {
                        "mode": "correct",
                        "claim_id": "C05",
                        "old": "0.909",
                        "new": "0.904",
                        "expected_count": 1,
                    }
                ],
            }
        ],
    )

    with pytest.raises(IntegrationPlanError, match="symlink"):
        compile_integration_plan(plan, wiki_root=wiki)

    assert protected.read_text(encoding="utf-8") == "AUROC 0.909\n"


def test_source_and_target_hash_drift_fail_closed(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    source = _write(tmp_path / "ledger.md", "C05: AUROC 0.904\n")
    page = _write(wiki / "concepts" / "metric.md", "AUROC 0.909\n")
    plan = _write_plan(
        tmp_path / "plan.json",
        source=source,
        pages=[
            {
                "path": "concepts/metric.md",
                "expected_sha256": _sha256(page),
                "operations": [
                    {
                        "mode": "correct",
                        "claim_id": "C05",
                        "old": "0.909",
                        "new": "0.904",
                        "expected_count": 1,
                    }
                ],
            }
        ],
    )
    page.write_text("operator changed this page\n", encoding="utf-8")

    with pytest.raises(IntegrationPlanError, match="target hash mismatch"):
        compile_integration_plan(plan, wiki_root=wiki, apply=True, reviewer="operator")

    page.write_text("AUROC 0.909\n", encoding="utf-8")
    source.write_text("ledger changed after planning\n", encoding="utf-8")
    with pytest.raises(IntegrationPlanError, match="source hash mismatch"):
        compile_integration_plan(plan, wiki_root=wiki, apply=True, reviewer="operator")


def test_directory_swap_cannot_redirect_compiler_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wiki = tmp_path / "wiki"
    source = _write(tmp_path / "ledger.md", "C05: AUROC 0.904\n")
    page = _write(wiki / "concepts" / "metric.md", "AUROC 0.909\n")
    outside = tmp_path / "outside"
    _write(outside / "metric.md", page.read_text(encoding="utf-8"))
    detached = wiki / "concepts-detached"
    plan = _write_plan(
        tmp_path / "plan.json",
        source=source,
        pages=[
            {
                "path": "concepts/metric.md",
                "expected_sha256": _sha256(page),
                "operations": [
                    {
                        "mode": "correct",
                        "claim_id": "C05",
                        "old": "0.909",
                        "new": "0.904",
                    }
                ],
            }
        ],
    )
    real_stage = safe_write_module._stage_text
    swapped = False

    def stage_then_swap(parent_fd: int, filename: str, text: str, *, mode: int) -> str:
        nonlocal swapped
        temporary = real_stage(parent_fd, filename, text, mode=mode)
        if not swapped:
            swapped = True
            (wiki / "concepts").rename(detached)
            (wiki / "concepts").symlink_to(outside, target_is_directory=True)
        return temporary

    monkeypatch.setattr(safe_write_module, "_stage_text", stage_then_swap)

    with pytest.raises(IntegrationPlanError, match="integration apply failed"):
        compile_integration_plan(plan, wiki_root=wiki, apply=True, reviewer="operator")

    assert (outside / "metric.md").read_text(encoding="utf-8") == "AUROC 0.909\n"
    assert (detached / "metric.md").read_text(encoding="utf-8") == "AUROC 0.909\n"


def test_post_replace_directory_swap_cannot_report_false_compile_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wiki = tmp_path / "wiki"
    concepts = wiki / "concepts"
    source = _write(tmp_path / "ledger.md", "C05: AUROC 0.904\n")
    page = _write(concepts / "metric.md", "AUROC 0.909\n")
    log = _write(wiki / "log.md", "prior receipt\n")
    detached = wiki / "concepts-detached"
    plan = _write_plan(
        tmp_path / "plan.json",
        source=source,
        pages=[
            {
                "path": "concepts/metric.md",
                "expected_sha256": _sha256(page),
                "operations": [
                    {
                        "mode": "correct",
                        "claim_id": "C05",
                        "old": "0.909",
                        "new": "0.904",
                    }
                ],
            }
        ],
    )
    real_replace = safe_write_module.os.replace
    calls = 0

    def replace_then_swap(
        source_name: str,
        target_name: str,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
    ) -> None:
        nonlocal calls
        calls += 1
        real_replace(
            source_name,
            target_name,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
        )
        if calls == 1:
            concepts.rename(detached)
            concepts.mkdir()
            _write(concepts / "metric.md", "AUROC 0.909\n")

    monkeypatch.setattr(safe_write_module.os, "replace", replace_then_swap)

    with pytest.raises(IntegrationPlanError, match="integration apply failed"):
        compile_integration_plan(plan, wiki_root=wiki, apply=True, reviewer="operator")

    assert page.read_text(encoding="utf-8") == "AUROC 0.909\n"
    assert (detached / "metric.md").read_text(encoding="utf-8") == "AUROC 0.909\n"
    assert log.read_text(encoding="utf-8") == "prior receipt\n"


def test_preopen_root_swap_cannot_redirect_compiler_transaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wiki = tmp_path / "wiki"
    source = _write(tmp_path / "ledger.md", "C05: AUROC 0.904\n")
    page = _write(wiki / "concepts" / "metric.md", "AUROC 0.909\n")
    _write(wiki / "log.md", "prior receipt\n")
    detached = tmp_path / "wiki-detached"
    outside = tmp_path / "outside"
    outside_page = _write(outside / "concepts" / "metric.md", "AUROC 0.909\n")
    outside_log = _write(outside / "log.md", "prior receipt\n")
    plan = _write_plan(
        tmp_path / "plan.json",
        source=source,
        pages=[
            {
                "path": "concepts/metric.md",
                "expected_sha256": _sha256(page),
                "operations": [
                    {
                        "mode": "correct",
                        "claim_id": "C05",
                        "old": "0.909",
                        "new": "0.904",
                    }
                ],
            }
        ],
    )
    real_apply = safe_write_module.apply_anchored_text_changes
    swapped = False

    def swap_then_apply(*args, **kwargs) -> None:
        nonlocal swapped
        if not swapped:
            swapped = True
            wiki.rename(detached)
            wiki.symlink_to(outside, target_is_directory=True)
        real_apply(*args, **kwargs)

    monkeypatch.setattr(
        wiki_compiler_module, "apply_anchored_text_changes", swap_then_apply
    )

    with pytest.raises(IntegrationPlanError, match="integration apply failed"):
        compile_integration_plan(plan, wiki_root=wiki, apply=True, reviewer="operator")

    assert (detached / "concepts" / "metric.md").read_text() == "AUROC 0.909\n"
    assert (detached / "log.md").read_text() == "prior receipt\n"
    assert outside_page.read_text() == "AUROC 0.909\n"
    assert outside_log.read_text() == "prior receipt\n"


def test_temporarily_hidden_manifest_is_an_anchored_compile_precondition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wiki = tmp_path / "wiki"
    source = _write(tmp_path / "ledger.md", "C05: AUROC 0.904\n")
    page = _write(wiki / "concepts" / "metric.md", "AUROC 0.909\n")
    _write(wiki / "log.md", "prior receipt\n")
    plan = _write_plan(
        tmp_path / "plan.json",
        source=source,
        pages=[
            {
                "path": "concepts/metric.md",
                "expected_sha256": _sha256(page),
                "operations": [
                    {
                        "mode": "correct",
                        "claim_id": "C05",
                        "old": "0.909",
                        "new": "0.904",
                    }
                ],
            }
        ],
    )
    manifest = wiki / "MANIFEST.jsonl"
    manifest.write_text("{}\n", encoding="utf-8")
    hidden = wiki / "MANIFEST.hidden"
    real_governing = wiki_compiler_module.governing_manifest_paths

    def hide_during_check(roots):
        manifest.rename(hidden)
        try:
            return real_governing(roots)
        finally:
            hidden.rename(manifest)

    monkeypatch.setattr(
        wiki_compiler_module, "governing_manifest_paths", hide_during_check
    )

    with pytest.raises(IntegrationPlanError, match="integration apply failed"):
        compile_integration_plan(plan, wiki_root=wiki, apply=True, reviewer="operator")

    assert page.read_text() == "AUROC 0.909\n"
    assert (wiki / "log.md").read_text() == "prior receipt\n"
    assert manifest.exists()


def test_evidence_change_during_page_replace_rolls_back_pages_and_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wiki = tmp_path / "wiki"
    source = _write(tmp_path / "ledger.md", "C05: AUROC 0.904\n")
    page = _write(wiki / "concepts" / "metric.md", "AUROC 0.909\n")
    log = _write(wiki / "log.md", "prior receipt\n")
    plan = _write_plan(
        tmp_path / "plan.json",
        source=source,
        pages=[
            {
                "path": "concepts/metric.md",
                "expected_sha256": _sha256(page),
                "operations": [
                    {
                        "mode": "correct",
                        "claim_id": "C05",
                        "old": "0.909",
                        "new": "0.904",
                    }
                ],
            }
        ],
    )
    real_replace = safe_write_module.os.replace
    calls = 0

    def replace_then_change_evidence(
        source_name,
        target_name,
        *,
        src_dir_fd=None,
        dst_dir_fd=None,
    ):
        nonlocal calls
        calls += 1
        real_replace(
            source_name,
            target_name,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
        )
        if calls == 1:
            source.write_text("C05: attacker replacement\n", encoding="utf-8")

    monkeypatch.setattr(safe_write_module.os, "replace", replace_then_change_evidence)

    with pytest.raises(IntegrationPlanError, match="integration apply failed"):
        compile_integration_plan(plan, wiki_root=wiki, apply=True, reviewer="operator")

    assert page.read_text(encoding="utf-8") == "AUROC 0.909\n"
    assert log.read_text(encoding="utf-8") == "prior receipt\n"


def test_evidence_cannot_alias_the_implicit_wiki_log_output(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    source = _write(wiki / "log.md", "## Audited\n\nC05: AUROC 0.904\n")
    page = _write(wiki / "concepts" / "metric.md", "AUROC 0.909\n")
    plan = _write_plan(
        tmp_path / "plan.json",
        source=source,
        authority="audited-source",
        pages=[
            {
                "path": "concepts/metric.md",
                "expected_sha256": _sha256(page),
                "operations": [
                    {
                        "mode": "correct",
                        "claim_id": "C05",
                        "old": "0.909",
                        "new": "0.904",
                    }
                ],
            }
        ],
    )

    with pytest.raises(IntegrationPlanError, match="implicit write targets"):
        compile_integration_plan(plan, wiki_root=wiki)

    assert source.read_text(encoding="utf-8").startswith("## Audited")
    assert page.read_text(encoding="utf-8") == "AUROC 0.909\n"


def test_receipt_and_pages_rollback_together_after_post_replace_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    wiki = tmp_path / "wiki"
    source = _write(tmp_path / "ledger.md", "C05: AUROC 0.904\n")
    page = _write(wiki / "concepts" / "metric.md", "AUROC 0.909\n")
    log = _write(wiki / "log.md", "prior receipt\n")
    plan = _write_plan(
        tmp_path / "plan.json",
        source=source,
        pages=[
            {
                "path": "concepts/metric.md",
                "expected_sha256": _sha256(page),
                "operations": [
                    {
                        "mode": "correct",
                        "claim_id": "C05",
                        "old": "0.909",
                        "new": "0.904",
                    }
                ],
            }
        ],
    )
    real_replace = safe_write_module.os.replace
    calls = 0

    def replace_log_then_raise(
        source_name: str,
        target_name: str,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
    ) -> None:
        nonlocal calls
        calls += 1
        real_replace(
            source_name,
            target_name,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
        )
        if calls == 2:
            raise OSError("post-log-replace failure")

    monkeypatch.setattr(safe_write_module.os, "replace", replace_log_then_raise)

    with pytest.raises(IntegrationPlanError, match="integration apply failed"):
        compile_integration_plan(plan, wiki_root=wiki, apply=True, reviewer="operator")

    assert page.read_text(encoding="utf-8") == "AUROC 0.909\n"
    assert log.read_text(encoding="utf-8") == "prior receipt\n"
