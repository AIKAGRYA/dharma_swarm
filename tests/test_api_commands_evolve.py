"""Contract test for POST /api/commands/evolve.

The endpoint historically called ``Swarm.evolve(component=..., generations=...)``,
but ``Swarm.evolve`` has no ``generations`` parameter and requires
``change_type``/``description`` (dharma_swarm/swarm.py). Every request therefore
raised ``TypeError`` that was caught and returned as a generic error string — a
permanently-broken endpoint that looked like a transient failure.

This pins the truthful contract: the endpoint must report, deterministically,
that evolve is not wired via HTTP — never leak a ``TypeError`` about
``generations``, and never attempt to construct or drive the swarm/evolution
engine from an unauthenticated request.
"""

from __future__ import annotations

import asyncio

from api.models import EvolveRequest
from api.routers.commands import trigger_evolve


def test_evolve_endpoint_reports_not_wired_and_never_leaks_typeerror():
    resp = asyncio.run(trigger_evolve(EvolveRequest()))
    assert resp.status == "error"
    # Truthful contract, not a swallowed exception.
    assert "not wired" in resp.error.lower()
    # The old broken behavior leaked the method-signature TypeError; it must not.
    assert "generations" not in resp.error.lower()
    assert "unexpected keyword" not in resp.error.lower()
    assert "traceback" not in resp.error.lower()
