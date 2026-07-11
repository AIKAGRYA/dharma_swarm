from dharma_swarm.forge_v1.forge_v2.runner_slots import _slot_for_id
from dharma_swarm.models import ProviderType


def test_slot_for_id_routes_moonshot_prefix_to_moonshot_provider():
    slot = _slot_for_id("moonshot:kimi-k2.7-code")

    assert slot is not None
    assert slot.provider == ProviderType.MOONSHOT
    assert slot.model_id == "kimi-k2.7-code"
    assert slot.tier == "frontier"
