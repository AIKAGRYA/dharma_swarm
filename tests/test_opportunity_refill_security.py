"""Security contracts for identifier-derived revenue-packet paths."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from api.routers import opportunities as opportunities_router
from dharma_swarm.opportunity_refill import (
    OpportunityRefill,
    OpportunityRow,
    RefillResult,
)


@pytest.mark.parametrize(
    "opportunity_id",
    ["a", "packet-test", "opp_1", "opportunity.v1", "a" * 64],
)
def test_opportunity_id_preserves_existing_component_grammar(opportunity_id: str) -> None:
    assert OpportunityRow(id=opportunity_id).id == opportunity_id


@pytest.mark.parametrize(
    "opportunity_id",
    [
        "",
        ".",
        "..",
        "../escape",
        "/absolute",
        "nested/name",
        r"nested\name",
        "bad\rname",
        "bad\nname",
        "bad\x00name",
        "bad\x1fname",
        "bad\x7fname",
        "a" * 65,
    ],
)
def test_opportunity_id_rejects_traversal_and_control_characters(
    opportunity_id: str,
) -> None:
    with pytest.raises(ValidationError):
        OpportunityRow(id=opportunity_id)


@pytest.mark.asyncio
async def test_refill_route_rejects_unsafe_id_before_dispatch(monkeypatch) -> None:
    def unexpected_refill() -> None:
        raise AssertionError("request handler ran for an invalid opportunity id")

    monkeypatch.setattr(opportunities_router, "_get_refill", unexpected_refill)
    app = FastAPI()
    app.include_router(opportunities_router.router)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/opportunities/refill",
            json={"id": "../escape", "title": "Unsafe packet"},
        )

    assert response.status_code == 422


def test_revenue_packet_keeps_valid_filename_stable(tmp_path: Path) -> None:
    output_dir = tmp_path / "packets"
    refill = OpportunityRefill(dispatcher=object(), output_dir=output_dir)
    row = OpportunityRow(id="opp.A-1_test", title="Safe packet")
    result = RefillResult(
        opportunity_id=row.id,
        opportunity_type=row.type,
        success=True,
    )

    packet_path = refill._write_revenue_packet(row, result)

    assert packet_path == output_dir.resolve() / "revenue_packet_opp.A-1_test.md"
    assert packet_path.is_file()


def test_revenue_packet_rejects_existing_symlink_escape(tmp_path: Path) -> None:
    output_dir = tmp_path / "packets"
    outside = tmp_path / "outside.md"
    outside.write_text("sentinel", encoding="utf-8")
    refill = OpportunityRefill(dispatcher=object(), output_dir=output_dir)
    row = OpportunityRow(id="safe", title="Safe packet")
    result = RefillResult(
        opportunity_id=row.id,
        opportunity_type=row.type,
        success=True,
    )
    (output_dir / "revenue_packet_safe.md").symlink_to(outside)

    with pytest.raises(ValueError, match="escapes"):
        refill._write_revenue_packet(row, result)

    assert outside.read_text(encoding="utf-8") == "sentinel"


def test_write_boundary_revalidates_constructed_model(tmp_path: Path) -> None:
    refill = OpportunityRefill(dispatcher=object(), output_dir=tmp_path / "packets")
    unsafe_row = OpportunityRow.model_construct(id="../escape", title="Unsafe packet")
    result = RefillResult(
        opportunity_id=unsafe_row.id,
        opportunity_type=unsafe_row.type,
        success=True,
    )

    with pytest.raises(ValueError, match="canonical"):
        refill._write_revenue_packet(unsafe_row, result)

    assert not (tmp_path / "escape.md").exists()
