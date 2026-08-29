"""Standing kill-metrics — the mission's own falsifiable stop conditions.

A mission that cannot name what would kill it is religion, not engineering.
These five conditions are computed every cycle from campaign results and receipts
and surfaced in the walking brief. Any KILL verdict means: halt that lane and
review, do not quietly continue.

1. survival_collapse — held-out survival rate < floor for two consecutive
   cohorts => the loop is optimizing its evaluator, not the code.
2. discovery_starved — fewer than N held-out-verified improvements per rolling
   window => the budget/target doctrine cannot buy a sellable discovery rate.
3. replication_failure — a published report card failed independent
   replication => fatal for a trust product.
4. target_banned — an account ban / repeated closed-without-review on a target
   => freeze that target, report-first only.
5. commoditized — a free per-patch verified-improvement product shipped
   (Google/InferenceX/vendor) => fall back to the services lane.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Sequence

OK = "ok"
WARN = "warn"
KILL = "kill"


@dataclass(frozen=True)
class Verdict:
    metric: str
    status: str
    detail: str


@dataclass
class KillMetricSnapshot:
    as_of: str
    cohort_survival: float
    prior_cohort_survival: float | None
    verified_improvements: int
    replication_failures: int
    banned_targets: list[str]
    commoditized: bool
    verdicts: list[Verdict] = field(default_factory=list)

    def any_kill(self) -> bool:
        return any(v.status == KILL for v in self.verdicts)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["any_kill"] = self.any_kill()
        return data


def evaluate_kill_metrics(
    *,
    cohort_survival: float,
    verified_improvements: int,
    prior_cohort_survival: float | None = None,
    replication_failures: int = 0,
    banned_targets: Sequence[str] = (),
    commoditized: bool = False,
    survival_floor: float = 0.30,
    min_verified: int = 2,
) -> KillMetricSnapshot:
    verdicts: list[Verdict] = []

    if prior_cohort_survival is not None and cohort_survival < survival_floor and prior_cohort_survival < survival_floor:
        verdicts.append(Verdict("survival_collapse", KILL,
            f"survival {cohort_survival:.2f} and prior {prior_cohort_survival:.2f} both < {survival_floor}"))
    elif cohort_survival < survival_floor:
        verdicts.append(Verdict("survival_collapse", WARN,
            f"survival {cohort_survival:.2f} < {survival_floor} for one cohort (kill on a second)"))
    else:
        verdicts.append(Verdict("survival_collapse", OK, f"survival {cohort_survival:.2f}"))

    if verified_improvements < min_verified:
        verdicts.append(Verdict("discovery_starved", WARN,
            f"{verified_improvements} verified improvements < target {min_verified} this window"))
    else:
        verdicts.append(Verdict("discovery_starved", OK, f"{verified_improvements} verified improvements"))

    if replication_failures > 0:
        verdicts.append(Verdict("replication_failure", KILL,
            f"{replication_failures} published report card(s) failed independent replication"))
    else:
        verdicts.append(Verdict("replication_failure", OK, "no replication failures"))

    if banned_targets:
        verdicts.append(Verdict("target_banned", KILL,
            f"targets frozen: {', '.join(banned_targets)}"))
    else:
        verdicts.append(Verdict("target_banned", OK, "no target bans"))

    if commoditized:
        verdicts.append(Verdict("commoditized", KILL,
            "a free per-patch verified-improvement product shipped; fall back to services lane"))
    else:
        verdicts.append(Verdict("commoditized", OK, "no free per-patch competitor yet"))

    return KillMetricSnapshot(
        as_of=datetime.now(timezone.utc).isoformat(),
        cohort_survival=cohort_survival,
        prior_cohort_survival=prior_cohort_survival,
        verified_improvements=verified_improvements,
        replication_failures=replication_failures,
        banned_targets=list(banned_targets),
        commoditized=commoditized,
        verdicts=verdicts,
    )


def render_walking_brief(snapshot: KillMetricSnapshot) -> str:
    """One-screen operator summary for the phone (plain text)."""
    icon = {OK: "OK", WARN: "WARN", KILL: "KILL"}
    lines = [f"Sublimation Foundry — kill-metrics @ {snapshot.as_of}"]
    if snapshot.any_kill():
        lines.append("STATUS: KILL — a lane must halt and be reviewed.")
    else:
        lines.append("STATUS: running.")
    for v in snapshot.verdicts:
        lines.append(f"  [{icon.get(v.status, v.status)}] {v.metric}: {v.detail}")
    return "\n".join(lines)


def snapshot_json(snapshot: KillMetricSnapshot) -> str:
    return json.dumps(snapshot.to_dict(), indent=2, allow_nan=False)
