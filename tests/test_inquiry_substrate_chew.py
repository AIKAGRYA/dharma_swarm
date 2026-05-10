import json
from pathlib import Path

import pytest

from dharma_swarm.lineage import LineageGraph
from dharma_swarm.models import (
    GateCheckResult,
    GateDecision,
    GateResult,
    LLMRequest,
    LLMResponse,
    ProviderType,
)
from dharma_swarm.ontology import OntologyRegistry
from dharma_swarm.telic_seam import TelicSeam
from dharma_swarm.inquiry_substrate_chew import (
    ChewConfig,
    build_prompt,
    resolve_provider_config,
    run_chew,
    select_seed_chunk,
)


class FakeProvider:
    def __init__(self, content: str = "Substrate Signal\nThe seed is chewable.") -> None:
        self.content = content
        self.requests: list[LLMRequest] = []

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(content=self.content, model=request.model, provider="fake")


class FailingProvider:
    async def complete(self, request: LLMRequest) -> LLMResponse:
        raise AssertionError("blocked gate should not call provider")


class FakeGatekeeper:
    def __init__(self, decision: GateDecision = GateDecision.ALLOW) -> None:
        self.decision = decision

    def check(
        self,
        action: str,
        content: str = "",
        tool_name: str = "",
        trust_mode: str | None = None,
        think_phase: str | None = None,
        reflection: str = "",
    ) -> GateCheckResult:
        result = GateResult.PASS if self.decision != GateDecision.BLOCK else GateResult.FAIL
        return GateCheckResult(
            decision=self.decision,
            reason=f"fake {self.decision.value}",
            gate_results={"AHIMSA": (result, "")},
        )


@pytest.fixture
def seed_files(tmp_path: Path) -> tuple[Path, Path]:
    seed = tmp_path / "seed.md"
    inlet = tmp_path / "INLET.md"
    seed.write_text("---\nstatus: raw\n---\n\nThis is a seed.", encoding="utf-8")
    inlet.write_text("# Inlet\n\nChew seeds without editing them.", encoding="utf-8")
    return seed, inlet


@pytest.fixture
def seam(tmp_path: Path) -> TelicSeam:
    registry = OntologyRegistry.create_dharma_registry()
    lineage = LineageGraph(db_path=tmp_path / "lineage.db")
    return TelicSeam(registry=registry, lineage=lineage)


def test_build_prompt_truncates_without_claiming_full_read(seed_files: tuple[Path, Path]) -> None:
    seed, inlet = seed_files
    system, prompt = build_prompt(
        inlet_text=inlet.read_text(encoding="utf-8"),
        seed_text="abcdef",
        seed_path=seed,
        max_seed_chars=3,
    )

    assert "read-only resident inquiry organ" in system
    assert "abc" in prompt
    assert "def" not in prompt
    assert "TRUNCATED FOR CONTEXT BUDGET" in prompt


def test_blind_calibration_prompt_uses_json_labeling_contract(seed_files: tuple[Path, Path]) -> None:
    seed, inlet = seed_files
    _, prompt = build_prompt(
        inlet_text=inlet.read_text(encoding="utf-8"),
        seed_text="### E01\n\n**Passage**:\n> Mechanism words only.",
        seed_path=seed,
        prompt_class="blind_calibration_label",
    )

    assert "Return only a JSON array" in prompt
    assert "Substrate Signal" not in prompt
    assert '"id": "E01"' in prompt
    assert "Use every example id present in the seed exactly once" in prompt


def test_select_seed_chunk_preserves_frontmatter_and_example_boundaries() -> None:
    seed_text = (
        "---\nstatus: blind\n---\n"
        "\nIntro text not part of examples.\n"
        "\n### E01\n\nOne\n"
        "\n### E02\n\nTwo\n"
        "\n### E03\n\nThree\n"
    )

    chunk, label = select_seed_chunk(seed_text, chunk_size=2, chunk_index=2)

    assert chunk.startswith("---\nstatus: blind\n---\n")
    assert label == "chunk 2/2: E03"
    assert "### E03" in chunk
    assert "### E01" not in chunk
    assert "### E02" not in chunk


def test_select_seed_chunk_rejects_out_of_range_index() -> None:
    seed_text = "### E01\n\nOne\n\n### E02\n\nTwo\n"

    with pytest.raises(ValueError, match="chunk_index must be between 1 and 2"):
        select_seed_chunk(seed_text, chunk_size=1, chunk_index=3)


@pytest.mark.asyncio
async def test_run_chew_records_full_metabolic_chain(
    tmp_path: Path,
    seed_files: tuple[Path, Path],
    seam: TelicSeam,
) -> None:
    seed, inlet = seed_files
    config = ChewConfig(
        seed_path=seed,
        inlet_path=inlet,
        output_dir=tmp_path / "chews",
        witness_path=tmp_path / "witness.jsonl",
    )

    result = await run_chew(
        config,
        provider=FakeProvider(),
        provider_label="fake:model",
        seam=seam,
        gatekeeper=FakeGatekeeper(),
    )

    assert result.success is True
    assert result.blocked is False
    assert result.proposal_id is not None
    assert result.gate_decision_id is not None
    assert result.outcome_id is not None
    assert result.value_event_id is not None
    assert result.contribution_id is not None
    assert result.output_path is not None
    assert result.output_path.exists()

    proposal = seam.registry.get_object(result.proposal_id)
    gate = seam.registry.get_object(result.gate_decision_id)
    outcome = seam.registry.get_object(result.outcome_id)
    value = seam.registry.get_object(result.value_event_id)
    contribution = seam.registry.get_object(result.contribution_id)
    assert proposal is not None
    assert gate is not None
    assert outcome is not None
    assert value is not None
    assert contribution is not None
    assert proposal.type_name == "ActionProposal"
    assert gate.type_name == "GateDecisionRecord"
    assert outcome.type_name == "Outcome"
    assert value.type_name == "ValueEvent"
    assert contribution.type_name == "Contribution"

    witness_row = json.loads((tmp_path / "witness.jsonl").read_text(encoding="utf-8"))
    assert witness_row["source"] == "inquiry_substrate_chew"
    assert witness_row["prompt_class"] == "seed_chew"
    assert witness_row["chunk_size"] == 0
    assert witness_row["success"] is True
    assert witness_row["proposal_id"] == result.proposal_id
    assert witness_row["artifact_sha256"] == result.artifact_sha256


@pytest.mark.asyncio
async def test_blocked_gate_records_failed_outcome_without_provider_call(
    tmp_path: Path,
    seed_files: tuple[Path, Path],
    seam: TelicSeam,
) -> None:
    seed, inlet = seed_files
    config = ChewConfig(
        seed_path=seed,
        inlet_path=inlet,
        output_dir=tmp_path / "chews",
        witness_path=tmp_path / "witness.jsonl",
    )

    result = await run_chew(
        config,
        provider=FailingProvider(),
        provider_label="fake:model",
        seam=seam,
        gatekeeper=FakeGatekeeper(GateDecision.BLOCK),
    )

    assert result.success is False
    assert result.blocked is True
    assert result.output_path is None
    assert result.outcome_id is not None
    outcome = seam.registry.get_object(result.outcome_id)
    assert outcome is not None
    assert outcome.properties["success"] is False
    assert "fake block" in outcome.properties["error"]


def test_cli_providers_are_rejected() -> None:
    config = ChewConfig(provider_type=ProviderType.CODEX)

    with pytest.raises(ValueError, match="CLI provider"):
        resolve_provider_config(config)
