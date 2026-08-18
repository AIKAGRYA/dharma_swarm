"""Boot contract for the invariant plural-genome Organism Boot Packet.

These tests exercise behavior beyond any single happy path: they assert the
ten irreducible dimensions are all present exactly once, that proposed material
cannot render as ratified, that the packet is deterministic/content-addressed,
that role lenses vary without dropping roots, and — critically — that the genome
is composed into a dispatched request on EVERY provider (including a non-Claude
explicit system prompt) at the dispatch seam, while the exact-string builder
contracts remain intact.
"""

from __future__ import annotations

import hashlib

import pytest

from dharma_swarm.orientation_packet import (
    _DIMENSION_ROOTS,
    DimensionCard,
    GENOME_BLOCK_PREFIX,
    GENOME_BLOCK_START,
    GENOME_SCHEMA_VERSION,
    build_organism_boot_packet,
    render_organism_genome,
)

REQUIRED_DIMENSIONS = frozenset(
    {
        "human_actualization",
        "self_recognition",
        "organismic_viability",
        "creative_intelligence",
        "metabolism",
        "world_service",
        "public_meaning",
        "reproduction_federation",
        "civilizational_evolution",
        "telos_conscience",
    }
)


def test_all_ten_dimensions_present_exactly_once():
    packet = build_organism_boot_packet()
    ids = [c.dimension_id for c in packet.dimensions]
    assert len(ids) == 10
    assert set(ids) == REQUIRED_DIMENSIONS
    assert len(ids) == len(set(ids)), "a dimension appears more than once"


def test_dimension_roots_have_no_duplicates_at_source():
    ids = [row[0] for row in _DIMENSION_ROOTS]
    assert len(ids) == len(set(ids))
    assert set(ids) == REQUIRED_DIMENSIONS


def test_jagat_kalyan_is_the_ceiling_and_body_is_not_telos():
    text = render_organism_genome()
    assert "Jagat Kalyan" in text
    assert "CEILING:" in text
    assert "not itself the telos" in text.lower() or "not the telos" in text.lower()


def test_human_actualization_is_proposed_not_ratified():
    packet = build_organism_boot_packet()
    card = next(c for c in packet.dimensions if c.dimension_id == "human_actualization")
    assert card.authority_status == "proposed"
    assert card.authority_status != "ratified"


def test_proposed_material_visible_in_rendered_text():
    text = render_organism_genome()
    assert "human_actualization" in text
    assert "proposed" in text


def test_packet_is_deterministic_and_content_addressed():
    a = build_organism_boot_packet()
    b = build_organism_boot_packet()
    assert a.packet_hash == b.packet_hash
    assert a.genome_hash == b.genome_hash
    assert a.packet_hash.startswith("sha256:")
    assert a.genome_hash.startswith("sha256:")
    assert a.render_text() == b.render_text()
    assert a.schema_version == GENOME_SCHEMA_VERSION
    assert a.packet_hash == (
        "sha256:" + hashlib.sha256(a.render_text().encode("utf-8")).hexdigest()
    )
    assert type(a).model_validate(a.model_dump()) == a


def test_packet_is_immutable_after_hashing():
    """Packet fields cannot drift after their content digests are attached."""
    from pydantic import ValidationError

    packet = build_organism_boot_packet(role="coder")
    with pytest.raises(ValidationError):
        packet.role_lens = "silently changed after hashing"
    with pytest.raises(ValidationError):
        packet.dimensions[0].irreducible_question = "nested silent drift"


def test_hashes_recompute_when_packet_is_copied_with_new_content():
    """Pydantic copy/update cannot retain a digest for old rendered content."""
    packet = build_organism_boot_packet(role="coder")
    changed = packet.model_copy(update={"role_lens": "a changed role lens"})
    assert changed.genome_hash == packet.genome_hash
    assert changed.packet_hash != packet.packet_hash
    assert changed.packet_hash.startswith("sha256:")


def test_packet_rejects_incomplete_or_invalid_dimension_sets():
    """The packet type itself enforces all ten roots and constrained states."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        DimensionCard(
            dimension_id="human_actualization",
            irreducible_question="q",
            developmental_state="invented",
            authority_status="ratified",
        )
    with pytest.raises(ValidationError):
        build_organism_boot_packet().dimensions[0].model_copy(
            update={"developmental_state": "invented"}
        )

    cards = list(build_organism_boot_packet().dimensions)
    with pytest.raises(ValidationError):
        build_organism_boot_packet().model_copy(
            update={"dimensions": tuple(cards[:-1])}
        )
    promoted = list(cards)
    promoted[0] = promoted[0].model_copy(update={"authority_status": "ratified"})
    with pytest.raises(ValidationError, match="canonical invariant projection"):
        build_organism_boot_packet().model_copy(
            update={"dimensions": tuple(promoted)}
        )
    with pytest.raises(ValidationError, match="canonical order"):
        build_organism_boot_packet().model_copy(
            update={"dimensions": tuple(reversed(cards))}
        )

    with pytest.raises(ValueError, match="computed"):
        build_organism_boot_packet().model_copy(
            update={"packet_hash": "sha256:spoofed"}
        )
    with pytest.raises(ValidationError, match="invariant frame"):
        build_organism_boot_packet().model_copy(
            update={"ceiling": "Something else"}
        )
    payload = build_organism_boot_packet().model_dump(
        exclude={"genome_hash", "packet_hash"}
    )
    with pytest.raises(ValidationError, match="packet_hash"):
        type(build_organism_boot_packet()).model_validate(
            {**payload, "packet_hash": "sha256:spoofed"}
        )


def test_role_lens_varies_but_roots_are_invariant():
    coder = build_organism_boot_packet(role="coder")
    researcher = build_organism_boot_packet(role="researcher")
    assert coder.role_lens != researcher.role_lens
    assert coder.role_lens
    assert {c.dimension_id for c in coder.dimensions} == REQUIRED_DIMENSIONS
    assert {c.dimension_id for c in researcher.dimensions} == REQUIRED_DIMENSIONS
    # genome_hash is role-invariant: same underlying genome for every seat.
    assert coder.genome_hash == researcher.genome_hash
    # packet_hash binds the EXACT rendered packet, which includes the role lens,
    # so seats with different lenses must have different packet_hash values.
    assert coder.packet_hash != researcher.packet_hash


def test_packet_hash_binds_exact_rendered_text_including_role_lens():
    """packet_hash must change iff the rendered first-token text changes."""
    coder = build_organism_boot_packet(role="coder")
    coder_again = build_organism_boot_packet(role="coder")
    # Same role -> identical render -> identical packet_hash.
    assert coder.render_text() == coder_again.render_text()
    assert coder.packet_hash == coder_again.packet_hash
    # A seat with no lens renders differently from a lensed seat.
    plain = build_organism_boot_packet()
    assert plain.render_text() != coder.render_text()
    assert plain.packet_hash != coder.packet_hash
    # ...but they still share the same role-invariant genome_hash.
    assert plain.genome_hash == coder.genome_hash


def test_genome_hash_covers_question_text_not_just_ids():
    """A silent edit to a dimension's question text must change genome_hash.

    Guards the earlier gap where the hash omitted question text, so wording
    could drift while the hash stayed stable.
    """
    import dharma_swarm.orientation_packet as op

    baseline = build_organism_boot_packet().genome_hash
    original_roots = op._DIMENSION_ROOTS
    mutated = list(original_roots)
    dim_id, question, dev, auth = mutated[0]
    mutated[0] = (dim_id, question + " (silently reworded)", dev, auth)
    try:
        op._DIMENSION_ROOTS = tuple(mutated)
        assert build_organism_boot_packet().genome_hash != baseline
    finally:
        op._DIMENSION_ROOTS = original_roots
    # Restored: hash returns to baseline (no residual mutation).
    assert build_organism_boot_packet().genome_hash == baseline


def test_unknown_role_yields_no_lens_but_full_genome():
    packet = build_organism_boot_packet(role="does-not-exist")
    assert packet.role_lens == ""
    assert {c.dimension_id for c in packet.dimensions} == REQUIRED_DIMENSIONS


def test_render_is_bounded_first_token_block():
    text = render_organism_genome(role="operator")
    assert len(text) < 4000
    assert text.startswith("## Organism Genome")


def test_promotion_vocabulary_is_constrained():
    from dharma_swarm.orientation_packet import (
        _VALID_AUTHORITY_STATES,
        _VALID_DEVELOPMENTAL_STATES,
    )

    for _dim, _q, dev, auth in _DIMENSION_ROOTS:
        assert dev in _VALID_DEVELOPMENTAL_STATES
        assert auth in _VALID_AUTHORITY_STATES


def test_prepend_genome_on_non_claude_explicit_prompt_composes():
    import dharma_swarm.agent_runner as ar
    from dharma_swarm.models import AgentConfig, AgentRole, LLMRequest, ProviderType

    cfg = AgentConfig(
        name="a",
        role=AgentRole.CODER,
        provider=ProviderType.OPENAI,
        system_prompt="EXPLICIT",
    )
    assert ar._build_system_prompt(cfg) == "EXPLICIT"

    req = LLMRequest(
        model="m", messages=[{"role": "user", "content": "hi"}], system="EXPLICIT"
    )
    out = ar._prepend_organism_genome(req, cfg)
    assert "Organism Genome" in out.system
    assert "EXPLICIT" in out.system
    assert "Jagat Kalyan" in out.system


def test_prepend_genome_is_idempotent():
    import dharma_swarm.agent_runner as ar
    from dharma_swarm.models import AgentConfig, AgentRole, LLMRequest, ProviderType

    cfg = AgentConfig(name="a", role=AgentRole.WORKER, provider=ProviderType.OPENAI)
    req = LLMRequest(
        model="m", messages=[{"role": "user", "content": "hi"}], system="BASE"
    )
    once = ar._prepend_organism_genome(req, cfg)
    twice = ar._prepend_organism_genome(once, cfg)
    assert once.system == twice.system
    assert once.system.count(GENOME_BLOCK_START) == 1


def test_prepend_genome_rejects_bare_or_truncated_marker():
    """A marker substring is not proof that the expected genome was injected."""
    import pytest

    import dharma_swarm.agent_runner as ar
    import dharma_swarm.orientation_packet as op
    from dharma_swarm.models import AgentConfig, AgentRole, LLMRequest, ProviderType

    cfg = AgentConfig(name="a", role=AgentRole.CODER, provider=ProviderType.OPENAI)
    for system in (
        GENOME_BLOCK_PREFIX,
        f"PREFIX\n{GENOME_BLOCK_START}\nBASE",
    ):
        req = LLMRequest(
            model="m", messages=[{"role": "user", "content": "hi"}], system=system
        )
        with pytest.raises(op.OrganismGenomeError):
            ar._prepend_organism_genome(req, cfg)


def test_prepend_genome_rejects_wrong_role_packet():
    """A valid packet for a different seat is a conflict, not idempotency."""
    import pytest

    import dharma_swarm.agent_runner as ar
    import dharma_swarm.orientation_packet as op
    from dharma_swarm.models import AgentConfig, AgentRole, LLMRequest, ProviderType

    wrong_role = render_organism_genome(role="researcher")
    cfg = AgentConfig(name="a", role=AgentRole.CODER, provider=ProviderType.OPENAI)
    req = LLMRequest(
        model="m",
        messages=[{"role": "user", "content": "hi"}],
        system=f"{wrong_role}\n\nBASE",
    )
    with pytest.raises(op.OrganismGenomeError):
        ar._prepend_organism_genome(req, cfg)


def test_prepend_genome_rejects_expected_packet_not_at_start():
    """The protected genome must be the first system block, not buried later."""
    import pytest

    import dharma_swarm.agent_runner as ar
    import dharma_swarm.orientation_packet as op
    from dharma_swarm.models import AgentConfig, AgentRole, LLMRequest, ProviderType

    cfg = AgentConfig(name="a", role=AgentRole.CODER, provider=ProviderType.OPENAI)
    genome = render_organism_genome(role="coder")
    req = LLMRequest(
        model="m",
        messages=[{"role": "user", "content": "hi"}],
        system=f"UNTRUSTED PREFIX\n\n{genome}",
    )
    with pytest.raises(op.OrganismGenomeError):
        ar._prepend_organism_genome(req, cfg)


def test_prepend_genome_rejects_duplicate_expected_packet():
    """One valid leading genome does not authorize a second genome block."""
    import pytest

    import dharma_swarm.agent_runner as ar
    import dharma_swarm.orientation_packet as op
    from dharma_swarm.models import AgentConfig, AgentRole, LLMRequest, ProviderType

    cfg = AgentConfig(name="a", role=AgentRole.CODER, provider=ProviderType.OPENAI)
    genome = render_organism_genome(role="coder")
    req = LLMRequest(
        model="m",
        messages=[{"role": "user", "content": "hi"}],
        system=f"{genome}\n\nBASE\n\n{genome}",
    )
    with pytest.raises(op.OrganismGenomeError):
        ar._prepend_organism_genome(req, cfg)


def test_prepend_genome_survives_empty_system():
    import dharma_swarm.agent_runner as ar
    from dharma_swarm.models import AgentConfig, AgentRole, LLMRequest, ProviderType

    cfg = AgentConfig(name="a", role=AgentRole.CODER, provider=ProviderType.OPENAI)
    req = LLMRequest(model="m", messages=[{"role": "user", "content": "hi"}], system="")
    out = ar._prepend_organism_genome(req, cfg)
    assert "Organism Genome" in out.system
    assert "Jagat Kalyan" in out.system


def test_genome_lives_in_system_not_trimmable_user_content():
    import dharma_swarm.agent_runner as ar
    from dharma_swarm.models import AgentConfig, AgentRole, LLMRequest, ProviderType

    cfg = AgentConfig(name="a", role=AgentRole.CODER, provider=ProviderType.OPENAI)
    req = LLMRequest(
        model="m",
        messages=[{"role": "user", "content": "## Latent Gold\n" + "x" * 200000}],
        system="BASE",
    )
    withgenome = ar._prepend_organism_genome(req, cfg)
    trimmed = ar._trim_context_to_budget(withgenome, max_tokens=100)
    assert "Organism Genome" in trimmed.system
    assert "Jagat Kalyan" in trimmed.system


def test_render_organism_genome_fails_closed_on_empty(monkeypatch):
    """If the rendered genome is empty, render_organism_genome must raise."""
    import pytest

    import dharma_swarm.orientation_packet as op

    monkeypatch.setattr(
        op.OrganismBootPacket, "render_text", lambda self: "   ", raising=True
    )
    with pytest.raises(op.OrganismGenomeError):
        op.render_organism_genome()


def test_prepend_genome_fails_closed_not_open(monkeypatch):
    """Genome construction failure must raise OrganismGenomeError at the seam.

    This is the negative test for the fail-closed decision: dispatch must NOT
    silently proceed with a genome-less prompt. The raised typed error is caught
    by run_task's outer handler and becomes an honest task failure.
    """
    import pytest

    import dharma_swarm.agent_runner as ar
    import dharma_swarm.orientation_packet as op
    from dharma_swarm.models import AgentConfig, AgentRole, LLMRequest, ProviderType

    def _boom(role=None):
        raise op.OrganismGenomeError("simulated genome failure")

    monkeypatch.setattr(op, "render_organism_genome", _boom, raising=True)

    cfg = AgentConfig(name="a", role=AgentRole.CODER, provider=ProviderType.OPENAI)
    req = LLMRequest(
        model="m", messages=[{"role": "user", "content": "hi"}], system="BASE"
    )
    with pytest.raises(op.OrganismGenomeError):
        ar._prepend_organism_genome(req, cfg)


def test_prepend_genome_wraps_unexpected_error_as_typed(monkeypatch):
    """Any unexpected construction error is still fail-closed (typed)."""
    import pytest

    import dharma_swarm.agent_runner as ar
    import dharma_swarm.orientation_packet as op
    from dharma_swarm.models import AgentConfig, AgentRole, LLMRequest, ProviderType

    def _boom(role=None):
        raise ValueError("unexpected non-typed failure")

    monkeypatch.setattr(op, "render_organism_genome", _boom, raising=True)

    cfg = AgentConfig(name="a", role=AgentRole.WORKER, provider=ProviderType.OPENAI)
    req = LLMRequest(
        model="m", messages=[{"role": "user", "content": "hi"}], system=""
    )
    with pytest.raises(op.OrganismGenomeError):
        ar._prepend_organism_genome(req, cfg)


@pytest.mark.asyncio
async def test_run_task_sends_genome_on_every_semantic_attempt(
    tmp_path, monkeypatch
):
    """Initial completion and repair retry both cross the guarded provider seam."""
    from dharma_swarm.agent_runner import AgentRunner
    from dharma_swarm.models import (
        AgentConfig,
        AgentRole,
        LLMRequest,
        LLMResponse,
        ProviderType,
        Task,
    )

    class RecordingProvider:
        def __init__(self):
            self.requests: list[LLMRequest] = []

        async def complete(self, request: LLMRequest) -> LLMResponse:
            self.requests.append(request)
            content = "first attempt" if len(self.requests) == 1 else "repaired"
            return LLMResponse(content=content, model=request.model)

    state_dir = tmp_path / ".dharma"
    state_dir.mkdir()
    cfg = AgentConfig(
        name="boot-contract-agent",
        role=AgentRole.RESEARCHER,
        provider=ProviderType.OPENAI,
        model="test-model",
        metadata={"state_dir": str(state_dir), "memory_state_dir": str(state_dir)},
    )
    provider = RecordingProvider()
    runner = AgentRunner(cfg, provider=provider)
    task = Task(title="Exercise semantic repair")

    assessments = iter(
        [
            type("Assessment", (), {
                "accepted": False,
                "quality_score": 0.0,
                "reason": "repair required",
            })(),
            type("Assessment", (), {
                "accepted": True,
                "quality_score": 1.0,
                "reason": "accepted",
            })(),
        ]
    )

    async def fake_assess(*args, **kwargs):
        return next(assessments)

    monkeypatch.setattr(
        "dharma_swarm.agent_runner.check_with_reflective_reroute",
        lambda **kwargs: type(
            "Gate",
            (),
            {
                "attempts": 0,
                "suggestions": [],
                "result": type(
                    "Result",
                    (),
                    {"decision": "allow", "reason": "test allow"},
                )(),
            },
        )(),
    )
    monkeypatch.setattr(
        "dharma_swarm.agent_runner._semantic_repair_attempts",
        lambda task, config: 1,
    )
    monkeypatch.setattr(
        "dharma_swarm.agent_runner._assess_completion_semantics",
        fake_assess,
    )
    monkeypatch.setattr(
        "dharma_swarm.agent_runner._assess_honors_checkpoint",
        lambda task, result, semantic_quality_score: (
            type(
                "Assessment",
                (),
                {
                    "accepted": True,
                    "quality_score": semantic_quality_score,
                    "reason": "accepted",
                },
            )(),
            None,
        ),
    )

    result = await runner.run_task(task)

    assert result == "repaired"
    assert len(provider.requests) == 2
    expected = render_organism_genome(role="researcher")
    for request in provider.requests:
        assert request.system == expected or request.system.startswith(
            f"{expected}\n\n"
        )
        assert request.system.count(GENOME_BLOCK_START) == 1


@pytest.mark.asyncio
async def test_run_task_fails_before_provider_when_genome_cannot_build(
    tmp_path, monkeypatch
):
    """Fail-closed injection records an error and never reaches the provider."""
    import dharma_swarm.orientation_packet as op
    from dharma_swarm.agent_runner import AgentRunner
    from dharma_swarm.models import (
        AgentConfig,
        AgentRole,
        LLMRequest,
        LLMResponse,
        ProviderType,
        Task,
    )

    class RecordingProvider:
        def __init__(self):
            self.requests: list[LLMRequest] = []

        async def complete(self, request: LLMRequest) -> LLMResponse:
            self.requests.append(request)
            return LLMResponse(content="should not run", model=request.model)

    state_dir = tmp_path / ".dharma"
    state_dir.mkdir()
    cfg = AgentConfig(
        name="fail-closed-agent",
        role=AgentRole.CODER,
        provider=ProviderType.OPENAI,
        model="test-model",
        metadata={"state_dir": str(state_dir), "memory_state_dir": str(state_dir)},
    )
    provider = RecordingProvider()
    runner = AgentRunner(cfg, provider=provider)

    monkeypatch.setattr(
        "dharma_swarm.agent_runner.check_with_reflective_reroute",
        lambda **kwargs: type(
            "Gate",
            (),
            {
                "attempts": 0,
                "suggestions": [],
                "result": type(
                    "Result",
                    (),
                    {"decision": "allow", "reason": "test allow"},
                )(),
            },
        )(),
    )
    monkeypatch.setattr(
        op,
        "render_organism_genome",
        lambda role=None: (_ for _ in ()).throw(
            op.OrganismGenomeError("simulated boot failure")
        ),
    )

    with pytest.raises(op.OrganismGenomeError, match="simulated boot failure"):
        await runner.run_task(Task(title="Must not dispatch"))

    assert provider.requests == []
    assert "simulated boot failure" in (runner.state.error or "")
