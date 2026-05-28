# spine: reads EvidenceReceipt
"""RoutingDecision — one canonical value object for every routing choice.

Replaces scattered implicit decisions across 7 routers with one shared shape.
See docs/reports/CONVERGED_SEAM_AUDIT_RUNTIME_TRUTH_SPINE.md §7 Fix 3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    """One canonical routing decision object.

    Today these choices are made implicitly across 7 routers.
    This object gives them a shared shape so future PRs can converge.
    """

    decision_id: UUID = field(default_factory=uuid4)
    agent_id: str = ""
    provider: str = ""
    model: str = ""
    reason: str = ""
    scores: dict[str, float] = field(default_factory=dict)
    fallback_plan: list[tuple[str, str]] = field(default_factory=list)
    router_name: str = ""
    context_id: str = ""
    task_id: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    attributes: dict[str, Any] = field(default_factory=dict)
