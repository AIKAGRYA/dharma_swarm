"""L1 — the real-model adapter. Behind the SAME propose(task, sample_idx) ->
Candidate interface the stubs use, so swapping a stub for a real frontier model
is a one-line change in a SwarmConfig (use LiveModel instead of QualityModel).

LiveModel: build a repair prompt from the task's buggy file -> call a Completion
backend -> parse the patched file out of the response -> Candidate(patch, tokens).

Backends:
- FakeCompletion: returns canned text (tests the prompt->parse plumbing offline).
- PoolCompletion: the LIVE swap-in (gpt-5.5 / opus-4.8 via dharma_swarm's pool).
  It raises a clear error rather than ever silently faking a live call — wire its
  body to runtime_provider when going live (that's when it starts costing tokens).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .harness import Candidate, RepairTask

_PATCH_RE = re.compile(r"```(?:python)?\n(.*?)```", re.DOTALL)


class FakeCompletion:
    """Offline backend: cycles through canned responses. complete(prompt) ->
    (text, tokens). Used to validate the prompt-build / patch-parse plumbing
    without any live call."""

    def __init__(self, responses: list[str]):
        self.responses = responses
        self.i = 0

    def complete(self, prompt: str) -> tuple[str, int]:
        text = self.responses[self.i % len(self.responses)]
        self.i += 1
        tokens = max(1, len(prompt) // 4 + len(text) // 4)
        return text, tokens


class PoolCompletion:
    """LIVE backend (the flip). Calls the real dharma_swarm model pool. Kept as an
    explicit, honest stub: it refuses to pretend to be live so an offline run can
    never silently spend money. Wire `complete` to runtime_provider /
    model_pool when going live."""

    def __init__(self, model_id: str = "gpt-5.5"):
        self.model_id = model_id

    def complete(self, prompt: str) -> tuple[str, int]:
        try:
            from dharma_swarm import runtime_provider  # noqa: F401  (presence check)
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                f"PoolCompletion(model={self.model_id}) is the live swap-in but "
                f"dharma_swarm.runtime_provider is not importable here: {exc}"
            )
        raise NotImplementedError(
            "PoolCompletion is the documented LIVE swap-in. Wire its body to the "
            f"real pool call for {self.model_id} (this is where real tokens are "
            "spent). Offline runs use FakeCompletion / QualityModel."
        )


@dataclass
class LiveModel:
    """Real-model adapter: prompt -> completion -> parse -> Candidate. Same
    interface as the stubs; drops straight into a SwarmConfig. Single-file tasks."""

    completion: object
    name: str = "live"

    def _filename(self, task: RepairTask) -> str:
        return next(iter(task.files))

    def _prompt(self, task: RepairTask) -> str:
        fn = self._filename(task)
        return (
            f"Fix the bug in `{fn}`. Return ONLY the full corrected file in a "
            f"single python code block.\n\n```python\n{task.files[fn]}```\n"
        )

    def propose(self, task: RepairTask, sample_idx: int) -> Candidate:
        text, tokens = self.completion.complete(self._prompt(task))
        match = _PATCH_RE.search(text or "")
        content = match.group(1) if match else (text or "")
        return Candidate(patch={self._filename(task): content}, tokens=tokens)
