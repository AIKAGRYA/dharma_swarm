"""Deterministic, no-network fixtures for the ingest lifecycle.

Each fixture is a fully specified fired-in input across the five source lanes
the spec calls out (note, local transcript-shaped text, URL metadata, Go
receipt, idea shard). They use a fixed ``captured_at`` so every derived id and
receipt is reproducible. Public-web fixtures (URL, Go receipt) deliberately
carry non-ownable source rights so the source-rights enforcement is exercised:
no raw content is retained, only a hash + summary/link policy.
"""

from __future__ import annotations

from dataclasses import dataclass

from .schemas import RedactionPolicy, SourceKind, SourceRights
from .store import build_operator_input_receipt
from .schemas import OperatorInputReceipt

FIXED_CAPTURED_AT = "2026-06-26T00:00:00Z"
FIXED_CAPTURED_BY = "operator"


@dataclass(frozen=True)
class IngestFixture:
    """A reproducible fired-in input plus the content used to hash it."""

    name: str
    source_kind: SourceKind
    source_ref: str
    content: str
    source_rights: SourceRights
    captured_by: str = FIXED_CAPTURED_BY
    expected_redaction: RedactionPolicy | None = None

    def build_receipt(self, captured_at: str = FIXED_CAPTURED_AT) -> OperatorInputReceipt:
        return build_operator_input_receipt(
            source_kind=self.source_kind,
            source_ref=self.source_ref,
            content=self.content,
            source_rights=self.source_rights,
            captured_by=self.captured_by,
            captured_at=captured_at,
        )


NOTE_FIXTURE = IngestFixture(
    name="operator_note",
    source_kind="note",
    source_ref="operator://note/memory-kernel-retrieval",
    content=(
        "Operator idea: the memory kernel retrieval path should expose a "
        "deterministic agent runtime tool that surfaces governed memory "
        "context to the orchestration layer. This is an infrastructure and "
        "tooling improvement with a clear open-source benchmark."
    ),
    source_rights="operator_supplied",
    expected_redaction="none",
)

TRANSCRIPT_FIXTURE = IngestFixture(
    name="local_transcript",
    source_kind="transcript",
    source_ref="file:///fixtures/transcripts/agent_runtime_dialogue.txt",
    content=(
        "Speaker A: We keep losing operator ideas between capture and action.\n"
        "Speaker B: Right — we need one correlation id from the fired-in input "
        "through Chetana staging, the memory kernel receipt, and the task "
        "board.\n"
        "Speaker A: And a deterministic runtime tool so retrieval works without "
        "a network call. Agent evaluation and governance benchmarks would "
        "prove it."
    ),
    source_rights="operator_supplied",
    expected_redaction="none",
)

URL_FIXTURE = IngestFixture(
    name="url_metadata",
    source_kind="url",
    source_ref="https://example.com/posts/agent-runtime-memory",
    # Only an operator-written summary/excerpt — never the full page body.
    content=(
        "Summary (operator): public post argues agent runtimes need a governed "
        "memory tool with deterministic retrieval; relevant to our research and "
        "infrastructure tooling."
    ),
    source_rights="public_excerpt",
    expected_redaction="summary_only",
)

GO_RECEIPT_FIXTURE = IngestFixture(
    name="go_receipt",
    source_kind="go_receipt",
    source_ref="go_evidence_receipt.v0:world_signal:7f3a1c",
    content=(
        "World radar Go receipt: open-source agent runtime release with "
        "benchmark and public github repository; tooling and infrastructure "
        "signal."
    ),
    source_rights="public_excerpt",
    expected_redaction="summary_only",
)

IDEA_SHARD_FIXTURE = IngestFixture(
    name="idea_shard",
    source_kind="idea_shard",
    source_ref="shd_fixturedeadbeefcafe0001",
    content=(
        "Latent idea shard: prototype a memory kernel retrieval tool for the "
        "agent runtime so governed context is one deterministic call away."
    ),
    source_rights="operator_supplied",
    expected_redaction="none",
)

ALL_FIXTURES: tuple[IngestFixture, ...] = (
    NOTE_FIXTURE,
    TRANSCRIPT_FIXTURE,
    URL_FIXTURE,
    GO_RECEIPT_FIXTURE,
    IDEA_SHARD_FIXTURE,
)


def all_fixture_receipts(captured_at: str = FIXED_CAPTURED_AT) -> list[OperatorInputReceipt]:
    return [fixture.build_receipt(captured_at) for fixture in ALL_FIXTURES]
