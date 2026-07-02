from __future__ import annotations

import json
from pathlib import Path

import pytest

from dharma_swarm.archive import (
    ArchiveEntry,
    EvolutionArchive,
    FitnessScore,
    ONE_WIRE_GUARDIAN_RECEIPT,
    OneWireFitnessAuthorityError,
    read_one_wire_fitness_authority,
)


def _state(tmp_path: Path) -> Path:
    return tmp_path / ".dharma"


def _archive(state: Path) -> EvolutionArchive:
    return EvolutionArchive(path=state / "evolution" / "archive.jsonl")


def _fitness_entry(**kwargs) -> ArchiveEntry:
    base = {
        "component": "internal_artifact",
        "change_type": "measurement",
        "description": "internal artifact attempts to move archive fitness",
        "fitness": FitnessScore(correctness=0.9, safety=1.0),
        "status": "applied",
        "test_results": {
            "source": "internal_agent_report",
            "fitness_authority_granted": True,
            "eligible_to_set_archive_fitness": True,
        },
    }
    base.update(kwargs)
    return ArchiveEntry(**base)


def _write_guardian(
    state: Path,
    *,
    confirmed: int,
    domains: int,
    eligible: bool,
    authority: bool,
    required_confirmed: int = 5,
    required_domains: int = 3,
) -> Path:
    path = state / ONE_WIRE_GUARDIAN_RECEIPT
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "test.one_wire_guardian.v1",
                "authority_result": {
                    "confirmed_receipt_count": confirmed,
                    "domain_count": domains,
                    "eligible_to_set_archive_fitness": eligible,
                    "archive_fitness_changed": False,
                    "fitness_authority_granted": authority,
                },
                "threshold_guard": {
                    "required_confirmed_receipts": required_confirmed,
                    "observed_confirmed_receipts": confirmed,
                    "required_distinct_domains": required_domains,
                    "observed_distinct_domains": domains,
                    "observed_domains": [f"domain-{idx}" for idx in range(domains)],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _assert_no_archive_side_effects(state: Path) -> None:
    assert not (state / "evolution" / "archive.jsonl").exists()
    assert not (state / "evolution" / "merkle_log.json").exists()


@pytest.mark.asyncio
async def test_missing_guardian_receipt_blocks_archive_fitness(tmp_path):
    state = _state(tmp_path)
    archive = _archive(state)

    with pytest.raises(OneWireFitnessAuthorityError, match="receipt missing"):
        await archive.add_entry(_fitness_entry())

    _assert_no_archive_side_effects(state)
    authority = read_one_wire_fitness_authority(state)
    assert authority.allowed is False
    assert authority.exists is False


@pytest.mark.asyncio
async def test_under_n_quorum_blocks_archive_fitness(tmp_path):
    state = _state(tmp_path)
    _write_guardian(state, confirmed=4, domains=3, eligible=True, authority=True)
    archive = _archive(state)

    with pytest.raises(OneWireFitnessAuthorityError, match="N=4/5, M=3/3"):
        await archive.add_entry(_fitness_entry())

    _assert_no_archive_side_effects(state)


@pytest.mark.asyncio
async def test_under_domain_quorum_blocks_archive_fitness(tmp_path):
    state = _state(tmp_path)
    _write_guardian(state, confirmed=5, domains=2, eligible=True, authority=True)
    archive = _archive(state)

    with pytest.raises(OneWireFitnessAuthorityError, match="N=5/5, M=2/3"):
        await archive.add_entry(_fitness_entry())

    _assert_no_archive_side_effects(state)


@pytest.mark.asyncio
async def test_missing_fitness_authority_flag_blocks_archive_fitness(tmp_path):
    state = _state(tmp_path)
    _write_guardian(state, confirmed=5, domains=3, eligible=True, authority=False)
    archive = _archive(state)

    with pytest.raises(OneWireFitnessAuthorityError, match="authority flags missing"):
        await archive.add_entry(_fitness_entry())

    _assert_no_archive_side_effects(state)
    assert read_one_wire_fitness_authority(state).allowed is False


@pytest.mark.asyncio
async def test_internal_only_artifact_cannot_self_grant_fitness_authority(tmp_path):
    state = _state(tmp_path)
    _write_guardian(state, confirmed=3, domains=1, eligible=False, authority=False)
    archive = _archive(state)

    entry = _fitness_entry(
        test_results={
            "source": "internal_agent_report",
            "external_confirmed": True,
            "one_wire": "claimed_by_entry_not_guardian",
            "quorum": {"confirmed": 99, "domains": 99},
            "fitness_authority_granted": True,
        }
    )
    with pytest.raises(OneWireFitnessAuthorityError, match="N=3/5, M=1/3"):
        await archive.add_entry(entry)

    _assert_no_archive_side_effects(state)


@pytest.mark.asyncio
async def test_guardian_cannot_lower_required_quorum_thresholds(tmp_path):
    state = _state(tmp_path)
    _write_guardian(
        state,
        confirmed=1,
        domains=1,
        eligible=True,
        authority=True,
        required_confirmed=0,
        required_domains=0,
    )
    archive = _archive(state)

    authority = read_one_wire_fitness_authority(state)
    assert authority.required_confirmed == 5
    assert authority.required_domains == 3
    with pytest.raises(OneWireFitnessAuthorityError, match="N=1/5, M=1/3"):
        await archive.add_entry(_fitness_entry())

    _assert_no_archive_side_effects(state)


@pytest.mark.asyncio
async def test_guardian_authority_flags_must_be_literal_booleans(tmp_path):
    state = _state(tmp_path)
    path = _write_guardian(
        state,
        confirmed=5,
        domains=3,
        eligible=True,
        authority=True,
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["authority_result"]["eligible_to_set_archive_fitness"] = "false"
    payload["authority_result"]["fitness_authority_granted"] = "false"
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    archive = _archive(state)

    authority = read_one_wire_fitness_authority(state)
    assert authority.allowed is False
    assert authority.eligible_to_set_archive_fitness is False
    assert authority.fitness_authority_granted is False
    with pytest.raises(OneWireFitnessAuthorityError, match="authority flags missing"):
        await archive.add_entry(_fitness_entry())

    _assert_no_archive_side_effects(state)


@pytest.mark.asyncio
async def test_negative_archive_fitness_requires_one_wire_authority(tmp_path):
    state = _state(tmp_path)
    archive = _archive(state)

    with pytest.raises(OneWireFitnessAuthorityError, match="receipt missing"):
        await archive.add_entry(_fitness_entry(fitness=FitnessScore(correctness=-0.1)))

    _assert_no_archive_side_effects(state)


@pytest.mark.asyncio
async def test_out_of_range_neutral_weighted_fitness_requires_one_wire_authority(tmp_path):
    state = _state(tmp_path)
    archive = _archive(state)
    fitness = FitnessScore(correctness=2.0, safety=-6.0)
    assert fitness.weighted() == 0.0

    with pytest.raises(OneWireFitnessAuthorityError, match="receipt missing"):
        await archive.add_entry(_fitness_entry(fitness=fitness))

    _assert_no_archive_side_effects(state)


@pytest.mark.asyncio
async def test_fully_eligible_synthetic_guardian_allows_temp_archive_fitness(tmp_path):
    state = _state(tmp_path)
    _write_guardian(state, confirmed=5, domains=3, eligible=True, authority=True)
    archive = _archive(state)

    entry_id = await archive.add_entry(_fitness_entry())

    got = await archive.get_entry(entry_id)
    assert got is not None
    assert got.fitness.weighted() > 0.0
    assert archive.grid.occupied_bins == 1
    assert read_one_wire_fitness_authority(state).allowed is True
    assert (state / "evolution" / "archive.jsonl").read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_custom_state_dir_archive_requires_one_wire_authority(tmp_path, monkeypatch):
    state = tmp_path / "custom-dharma-state"
    monkeypatch.setenv("DHARMA_STATE_DIR", str(state))
    archive = EvolutionArchive(path=state / "evolution" / "archive.jsonl")

    with pytest.raises(OneWireFitnessAuthorityError, match="receipt missing"):
        await archive.add_entry(_fitness_entry())

    assert not (state / "evolution" / "archive.jsonl").exists()


@pytest.mark.asyncio
async def test_custom_evolution_archive_is_guarded_by_default(tmp_path):
    scratch = tmp_path / "scratch"
    archive = EvolutionArchive(path=scratch / "evolution" / "archive.jsonl")

    assert archive.fitness_guard_state_dir == scratch
    assert archive.enforce_one_wire is True

    with pytest.raises(OneWireFitnessAuthorityError, match="receipt missing"):
        await archive.add_entry(_fitness_entry())

    assert not (scratch / "evolution" / "archive.jsonl").exists()


@pytest.mark.asyncio
async def test_scratch_archive_path_can_explicitly_opt_out_of_one_wire_guard(tmp_path):
    scratch = tmp_path / "scratch"
    archive = EvolutionArchive(
        path=scratch / "evolution" / "archive.jsonl",
        enforce_one_wire=False,
    )

    assert archive.fitness_guard_state_dir == scratch
    assert archive.enforce_one_wire is False

    entry_id = await archive.add_entry(_fitness_entry())

    got = await archive.get_entry(entry_id)
    assert got is not None
    assert got.fitness.weighted() > 0.0
    assert (scratch / "evolution" / "archive.jsonl").exists()


@pytest.mark.asyncio
async def test_status_promotion_to_fitness_bearing_state_is_guarded(tmp_path):
    state = _state(tmp_path)
    archive_path = state / "evolution" / "archive.jsonl"
    archive_path.parent.mkdir(parents=True)
    legacy = _fitness_entry(status="proposed")
    archive_path.write_text(legacy.model_dump_json() + "\n", encoding="utf-8")

    archive = _archive(state)
    await archive.load()

    with pytest.raises(OneWireFitnessAuthorityError, match="receipt missing"):
        await archive.update_status(legacy.id, "applied")

    got = await archive.get_entry(legacy.id)
    assert got is not None
    assert got.status == "proposed"


@pytest.mark.asyncio
async def test_status_demotion_from_fitness_bearing_state_is_guarded(tmp_path):
    state = _state(tmp_path)
    archive_path = state / "evolution" / "archive.jsonl"
    archive_path.parent.mkdir(parents=True)
    applied = _fitness_entry(status="applied")
    archive_path.write_text(applied.model_dump_json() + "\n", encoding="utf-8")

    archive = _archive(state)
    await archive.load()

    with pytest.raises(OneWireFitnessAuthorityError, match="receipt missing"):
        await archive.update_status(applied.id, "proposed")

    got = await archive.get_entry(applied.id)
    assert got is not None
    assert got.status == "applied"


@pytest.mark.asyncio
async def test_rollback_entry_from_legacy_positive_fitness_row_is_guarded(tmp_path):
    state = _state(tmp_path)
    archive_path = state / "evolution" / "archive.jsonl"
    archive_path.parent.mkdir(parents=True)
    legacy = _fitness_entry(status="proposed")
    archive_path.write_text(legacy.model_dump_json() + "\n", encoding="utf-8")

    archive = _archive(state)
    await archive.load()

    with pytest.raises(OneWireFitnessAuthorityError, match="receipt missing"):
        await archive.rollback_entry(legacy.id, "manual rollback")

    got = await archive.get_entry(legacy.id)
    assert got is not None
    assert got.status == "proposed"
    assert got.rollback_reason is None

    row = json.loads(archive_path.read_text(encoding="utf-8").strip())
    assert row["status"] == "proposed"
    assert row["rollback_reason"] is None
    assert not (state / "evolution" / "merkle_log.json").exists()


@pytest.mark.asyncio
async def test_rollback_entry_from_fitness_bearing_row_is_guarded(tmp_path):
    state = _state(tmp_path)
    archive_path = state / "evolution" / "archive.jsonl"
    archive_path.parent.mkdir(parents=True)
    applied = _fitness_entry(status="applied")
    archive_path.write_text(applied.model_dump_json() + "\n", encoding="utf-8")

    archive = _archive(state)
    await archive.load()

    with pytest.raises(OneWireFitnessAuthorityError, match="receipt missing"):
        await archive.rollback_entry(applied.id, "manual rollback")

    got = await archive.get_entry(applied.id)
    assert got is not None
    assert got.status == "applied"
    assert got.rollback_reason is None

    row = json.loads(archive_path.read_text(encoding="utf-8").strip())
    assert row["status"] == "applied"
    assert row["rollback_reason"] is None


@pytest.mark.asyncio
async def test_compact_from_legacy_positive_fitness_row_is_guarded(tmp_path):
    state = _state(tmp_path)
    archive_path = state / "evolution" / "archive.jsonl"
    archive_path.parent.mkdir(parents=True)
    legacy = _fitness_entry(
        status="proposed",
        fitness=FitnessScore(correctness=0.1),
        timestamp="2026-01-01T00:00:00+00:00",
    )
    elite = _fitness_entry(
        status="applied",
        fitness=FitnessScore(
            correctness=1.0,
            dharmic_alignment=1.0,
            swabhaav_alignment=1.0,
            performance=1.0,
            utilization=1.0,
            economic_value=1.0,
            elegance=1.0,
            efficiency=1.0,
            safety=1.0,
        ),
        timestamp="2026-01-02T00:00:00+00:00",
    )
    archive_path.write_text(
        legacy.model_dump_json() + "\n" + elite.model_dump_json() + "\n",
        encoding="utf-8",
    )

    archive = _archive(state)
    await archive.load()

    with pytest.raises(OneWireFitnessAuthorityError, match="receipt missing"):
        await archive.compact(min_age_entries=1, fitness_percentile=0.0)

    got = await archive.get_entry(legacy.id)
    assert got is not None
    assert got.status == "proposed"
    rows = [
        json.loads(line)
        for line in archive_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [row["status"] for row in rows] == ["proposed", "applied"]

    _write_guardian(state, confirmed=5, domains=3, eligible=True, authority=True)
    assert await archive.compact(min_age_entries=1, fitness_percentile=0.0) == 1
    assert (await archive.get_entry(legacy.id)).status == "composted"


@pytest.mark.asyncio
async def test_zero_fitness_governed_archive_write_does_not_require_guardian(tmp_path):
    state = _state(tmp_path)
    archive = _archive(state)
    entry = _fitness_entry(
        fitness=FitnessScore(),
        status="applied",
        test_results={"source": "internal_agent_report"},
    )

    entry_id = await archive.add_entry(entry)

    got = await archive.get_entry(entry_id)
    assert got is not None
    assert got.fitness.weighted() == 0.0
    assert read_one_wire_fitness_authority(state).allowed is False
    assert (state / "evolution" / "archive.jsonl").exists()
    assert (state / "evolution" / "merkle_log.json").exists()
