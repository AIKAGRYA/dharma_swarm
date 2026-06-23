"""Frozen verifiable taskpack for Arena v1 (spec §3).

Arena v1 = ONLY programmatically-verifiable tasks (code/math/logic with known
answers) so correctness is objective and the "Council judges instead of verifies"
corruption vector is eliminated at cold start (refinement C).

CANDIDATE-VISIBLE / SCORER-ONLY SPLIT (spec §3, §6):
  * ``public_view()`` exposes only ``{task_id, family, prompt}`` — what a worker
    (and the candidate orchestrator) is allowed to see.
  * ``sealed_label()`` exposes the canonical answer — SCORER-ONLY. Every access
    is recorded on ``sealed_access_log`` so the anti-contamination check can prove
    the candidate path never read a label.

The scored slice is FROZEN per epoch: ``task_manifest_hash()`` pins the public
manifest; the scorer pins ``scorer_hash`` separately. Tasks never move after
results are seen (spec §6 invariant 1).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Literal

TaskFamily = Literal["math", "code", "logic"]

TASK_PACK_ID = "orchestration-arena-v1-frozen-verifiable-20260622-e2"
TASK_MANIFEST_SCHEMA = "orchestration_arena_v1_task_manifest.v1"


@dataclass(frozen=True)
class ArenaTask:
    """One frozen verifiable task. ``answer`` is the SEALED label (scorer-only)."""

    task_id: str
    family: TaskFamily
    prompt: str
    answer: str  # sealed — only the scorer may read this


# --- The frozen slice. 24 tasks (8 per family) with deterministic oracles. ----
# Epoch e2: widened from 12 -> 24 tasks to harden the significance signal. This
# is a NEW epoch (new TASK_PACK_ID + task_manifest_hash), NOT a mid-epoch mutation
# of a scored slice (spec §6.1 — the frozen slice never moves *within* an epoch).
_FROZEN_TASKS: tuple[ArenaTask, ...] = (
    # math family
    ArenaTask("m1", "math", "Compute 17 * 23.", "391"),
    ArenaTask("m2", "math", "Sum of the first 10 prime numbers.", "129"),
    ArenaTask("m3", "math", "Compute gcd(48, 36).", "12"),
    ArenaTask("m4", "math", "Compute 12! / 10!.", "132"),
    ArenaTask("m5", "math", "Compute 2 ** 10.", "1024"),
    ArenaTask("m6", "math", "Sum of the integers 1 through 100.", "5050"),
    ArenaTask("m7", "math", "Compute 7 * 8 * 9.", "504"),
    ArenaTask("m8", "math", "Compute 100 - 37.", "63"),
    # code family (phrased so a deterministic exact-match oracle suffices)
    ArenaTask("c1", "code", "Reverse the string 'dharma'.", "amrahd"),
    ArenaTask("c2", "code", "Count the vowels in 'orchestration'.", "5"),
    ArenaTask("c3", "code", "Length of the list [3,1,4,1,5,9,2,6].", "8"),
    ArenaTask("c4", "code", "Largest element of [3,1,4,1,5,9,2,6].", "9"),
    ArenaTask("c5", "code", "Reverse the string 'swarm'.", "mraws"),
    ArenaTask("c6", "code", "Count the letter 'a' in 'banana'.", "3"),
    ArenaTask("c7", "code", "Sum of the list [2,4,6,8].", "20"),
    ArenaTask("c8", "code", "Smallest element of [5,3,8,1,9].", "1"),
    # logic family
    ArenaTask("l1", "logic", "All blorps are zibs; some zibs are quabs. Must some blorps be quabs? yes/no.", "no"),
    ArenaTask("l2", "logic", "Tom is older than Sue; Sue is older than Ann. Who is oldest?", "tom"),
    ArenaTask("l3", "logic", "With a=1,b=2,c=3,... what is the digit-sum value of 'cab'?", "6"),
    ArenaTask("l4", "logic", "Next term in the sequence 2, 4, 8, 16, ?", "32"),
    ArenaTask("l5", "logic", "A is north of B and B is north of C. Which is southernmost?", "c"),
    ArenaTask("l6", "logic", "If it rains the ground is wet. The ground is dry. Did it rain? yes/no.", "no"),
    ArenaTask("l7", "logic", "How many days are in February in a leap year?", "29"),
    ArenaTask("l8", "logic", "What day comes the day after Sunday?", "monday"),
)


def normalize_answer(value: str) -> str:
    """Canonical normalization used by BOTH worker fixtures and the scorer."""
    return str(value).strip().lower()


@dataclass
class Taskpack:
    """Frozen taskpack with a hard candidate-visible / scorer-only split."""

    tasks: tuple[ArenaTask, ...] = _FROZEN_TASKS
    # Audit log of every sealed-label access (the contamination tripwire).
    sealed_access_log: list[str] = field(default_factory=list)

    # ------------------------------------------------------------ candidate-visible
    def public_view(self) -> list[dict[str, str]]:
        """What a worker / the candidate orchestrator may see. NO answers."""
        return [
            {"task_id": t.task_id, "family": t.family, "prompt": t.prompt}
            for t in self.tasks
        ]

    def task_ids(self) -> list[str]:
        return [t.task_id for t in self.tasks]

    def family_of(self, task_id: str) -> TaskFamily:
        return self._by_id()[task_id].family

    def prompt_of(self, task_id: str) -> str:
        return self._by_id()[task_id].prompt

    def task_manifest_hash(self) -> str:
        """Frozen-per-epoch hash over the PUBLIC manifest (no labels)."""
        payload = json.dumps(
            {"task_pack_id": TASK_PACK_ID, "schema": TASK_MANIFEST_SCHEMA, "tasks": self.public_view()},
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def sealed_oracle_hash(self) -> str:
        """SCORER-SIDE digest of the sealed labels (NOT exposed to candidates).

        ``task_manifest_hash`` deliberately omits labels so candidates never see
        them — but that means a corrected/altered sealed answer under an unchanged
        public prompt would NOT change the manifest hash, hiding label drift from
        replay/governance. This digest closes that gap: it pins the oracle's
        answer key as part of the frozen scorer identity. It returns only a hash
        (never the labels) and does not touch ``sealed_access_log`` because it is
        scorer/governance identity, not a per-task candidate-path read.
        """
        payload = json.dumps(
            {
                "task_pack_id": TASK_PACK_ID,
                "labels": {t.task_id: normalize_answer(t.answer) for t in self.tasks},
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------ scorer-only
    def sealed_label(self, task_id: str) -> str:
        """SCORER-ONLY. Reading this from the candidate path is contamination.

        Every read is appended to ``sealed_access_log`` so the anti-contamination
        check can prove which code path touched a label.
        """
        self.sealed_access_log.append(task_id)
        return self._by_id()[task_id].answer

    def _by_id(self) -> dict[str, ArenaTask]:
        return {t.task_id: t for t in self.tasks}


__all__ = [
    "TASK_PACK_ID",
    "ArenaTask",
    "TaskFamily",
    "Taskpack",
    "normalize_answer",
]
