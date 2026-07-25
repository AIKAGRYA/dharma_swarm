"""Tests for organism boot integration."""
import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestOrganismBoot:
    """Test that organism boots correctly and integrates with swarm."""

    def test_organism_singleton(self):
        from dharma_swarm.organism import get_organism, set_organism, Organism
        # Initially None
        import dharma_swarm.organism as mod
        old = mod._global_organism
        try:
            mod._global_organism = None
            assert get_organism() is None
            org = Organism()
            set_organism(org)
            assert get_organism() is org
        finally:
            mod._global_organism = old

    def test_organism_boot_diagnostics(self):
        from dharma_swarm.organism import Organism
        org = Organism()
        diag = _run(org.boot())
        assert "booted_at" in diag
        assert "amiros" in diag

    def test_organism_heartbeat(self, tmp_path):
        from dharma_swarm.organism import Organism
        # Isolated state dir: identity sub-metrics default to 0.5 on an empty
        # tree, so a freshly-booted organism heartbeats healthy deterministically.
        # Reading the ambient ~/.dharma makes tcs hover at the health threshold.
        org = Organism(state_dir=tmp_path)
        _run(org.boot())
        pulse = _run(org.heartbeat())
        assert pulse.cycle_number == 1
        assert pulse.is_healthy

    def test_organism_status(self):
        from dharma_swarm.organism import Organism
        org = Organism()
        _run(org.boot())
        status = org.status()
        assert "vsm" in status
        assert "amiros" in status
        assert "palace" in status
        assert "router" in status


class TestOrganismCompositionRoot:
    """Organism as composition root over an existing SwarmManager (D5).

    Wrapping only records the reference — dispatch stays SwarmManager's,
    and the Organism's own lifecycle (boot/heartbeat) is unchanged.
    """

    def test_default_has_no_swarm(self, tmp_path):
        from dharma_swarm.organism import Organism
        org = Organism(state_dir=tmp_path)
        assert org.swarm is None
        assert org.status()["swarm_attached"] is False

    def test_constructor_wraps_existing_swarm(self, tmp_path):
        from dharma_swarm.organism import Organism
        sentinel = object()
        org = Organism(state_dir=tmp_path, swarm=sentinel)
        assert org.swarm is sentinel
        assert org.status()["swarm_attached"] is True

    def test_attach_swarm_after_construction(self, tmp_path):
        from dharma_swarm.organism import Organism
        org = Organism(state_dir=tmp_path)
        sentinel = object()
        org.attach_swarm(sentinel)
        assert org.swarm is sentinel

    def test_wrapping_does_not_change_heartbeat(self, tmp_path):
        from dharma_swarm.organism import Organism
        sentinel = object()
        org = Organism(state_dir=tmp_path, swarm=sentinel)
        _run(org.boot())
        pulse = _run(org.heartbeat())
        assert pulse.cycle_number == 1
        assert pulse.is_healthy

    def test_strange_loop_status_read_only(self, tmp_path):
        from dharma_swarm.organism import Organism
        org = Organism(state_dir=tmp_path)
        status = org.strange_loop_status()
        assert status["available"] is True
        assert status["total_mutations"] == 0
        assert status["pending"] is False

    def test_strange_loop_status_when_unavailable(self, tmp_path):
        from dharma_swarm.organism import Organism
        org = Organism(state_dir=tmp_path)
        org.strange_loop = None
        assert org.strange_loop_status() == {"available": False}


class TestAMIROSPersistence:
    """Test AMIROS JSON persistence."""

    def test_amiros_save_load(self, tmp_path):
        from dharma_swarm.amiros import AMIROSRegistry
        reg = AMIROSRegistry(state_dir=tmp_path)
        reg.harvest(source="test", agent_id="a1", raw_text="hello world")

        # Check file was created
        persist_dir = tmp_path / "amiros"
        assert persist_dir.exists()

        # Create new registry from same path — should load persisted data
        reg2 = AMIROSRegistry(state_dir=tmp_path)
        stats = reg2.stats()
        assert stats.get("harvests", {}).get("total", 0) > 0


class TestContextCompilerPalace:
    """Test Memory Palace integration in context compiler."""

    def test_palace_section_weight_exists(self):
        from dharma_swarm.context_compiler import ContextCompiler
        assert "Memory Palace" in ContextCompiler._SECTION_WEIGHTS


class TestOrganismRouting:
    """Test model routing via organism."""

    def test_router_route_returns_result(self):
        from dharma_swarm.model_routing import OrganismRouter
        router = OrganismRouter()
        result = router.route("Write a Python unit test")
        assert result is not None
        assert hasattr(result, 'model')
