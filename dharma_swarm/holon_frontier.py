"""holon_frontier.py — the BEYOND-HERMES sovereign target tier for the holon harness.

The 16 axes in ``holon_grade`` answer "is this a holon, and how far up the always-on ladder?"
— a hermes-PARITY bar. These five dimensions are what make a holon a *sovereign* seat that
SURPASSES hermes/Nous rather than merely matching it. They come from the verified 2026-07-13
frontier research (``~/.dharma/agents/fable_composer/beyond_hermes_research_20260713/
CAPABILITY_LADDER.md`` — 6 web lanes, adversarially fact-checked, corrections applied).

They live IN CODE, not in a report, because the operator asked for the harness to be clear in
code. None is built anywhere in the estate yet — they are the climb, named so the harness can
prescribe it, not only grade the past. Chassis-before-capability: a holon that is smarter
without these five is a faster worker that can still lie, drift, and grab ambient power. Build
the trustworthy sovereign chassis first; plug memory/runtime rungs (ladder tiers A5/A7/A8) in
after.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FrontierDimension:
    id: str
    name: str
    question: str            # the yes/no a mature sovereign holon must answer YES
    beyond_hermes: str       # the specific hermes ceiling it defeats
    builds_on: str           # ladder rungs (see CAPABILITY_LADDER.md)
    feasibility: str         # ship-now | weeks | months | research
    marker: str              # filesystem marker (under the agent home) that would evidence it


BEYOND_HERMES: list[FrontierDimension] = [
    FrontierDimension(
        "F1_durable_signed_session_identity",
        "Durable session-as-signed-object identity",
        "Can a fresh brain reconstruct this holon's exact state from an external append-only "
        "replay log and PROVE it — never depending on a context window it can lose?",
        "hermes's context window IS its working memory; a crash is a cold cron restart.",
        "A1 (session-as-external-durable-object) + A3 (signed session)",
        "weeks", "session_log/signed_events.jsonl"),
    FrontierDimension(
        "F2_sovereign_execution_verifier",
        "Sovereign execution-grounded verifier as the promotion ceiling",
        "Is 'done' defined by a tiered grounded verifier (formal > execution > judge), "
        "worker != judge, never by self-report?",
        "hermes's static/refusing LLM arbiter = the estate's 0-promotions-ever root cause.",
        "A2 (execution-grounded verifier tier)",
        "weeks", "verifier/execution_gate.json"),
    FrontierDimension(
        "F3_signed_evolution_receipts",
        "Signed evolution-loop receipts (off-agent signer + witness log)",
        "Can a stranger verify this holon's authorization, actions, refusals, and every "
        "promotion it accepted — WITHOUT trusting the holon?",
        "hermes declined receipts (#487); no receipt vendor signs the RSI/promotion decision.",
        "A3 + A6 (receiver-side/off-agent signer + witness-cosigned transparency log)",
        "weeks", "receipts/signer.pub"),
    FrontierDimension(
        "F4_portable_identity_attenuated_authority",
        "Portable cryptographic identity + attenuated capability tokens",
        "Does authority flow across delegation hops as unforgeable, NARROWING-only capability "
        "— not ambient trust?",
        "hermes has no crypto agent identity, only bearer tokens; delegations carry ambient authority.",
        "B4 (attenuated capability tokens) + B5 (portable attested identity, A2A Agent Cards)",
        "weeks-months", "identity/attested_svid.json"),
    FrontierDimension(
        "F5_external_reversibility_gate",
        "Out-of-process, reversibility-tiered gate outside the mutable surface",
        "Is the governance gate un-reachable and un-editable by the agent it gates, and does it "
        "route by undoability rather than a static tool allowlist?",
        "hermes's in-process hook fuses decision+enforcement in one context-influenceable boolean.",
        "B1 (out-of-process PEP/PDP) + B6 (reversibility-tiered) + C2 (gate outside mutable surface)",
        "weeks-months", "gate/external_pep.sock"),
]

# The completeness-critic named seven frontiers the incumbent-facing research under-covered.
# These are the estate's binding realities RIGHT NOW; carried as code-visible notes so the harness
# never pretends the ladder is the whole map. (See CAPABILITY_LADDER.md § completeness-critic.)
BEYOND_HERMES_BLIND_SPOTS: dict[str, str] = {
    "async_sparse_operator_protocol": "The operator is phone-first/low-bandwidth (walking Japan, "
        "~15% interaction). What a holon may do autonomously between rare touches — batch-decision "
        "queues, algedonic push, decision-page compression — is the single most task-relevant gap.",
    "measurement_sovereignty": "Own the yardstick, not just the model: a private held-out eval "
        "harness. A signed receipt spine is worthless if the benchmark is rented.",
    "introspective_self_attestation": "The estate's own R_V / J-space / witness frontier: a holon "
        "whose receipts carry an INTERNAL attestation, not only a behavioral one. Its deepest moat.",
    "local_compute_sovereignty": "Running real open-weight models on the M5 128GB — the quiet "
        "hardware floor under weight-editing RSI, latent memory, and TEE receipts.",
    "revenue_as_fitness": "The holon EARNING (ARTHA): revenue/cost-metabolism as a first-class "
        "selection signal, not money treated only as a thing to sign.",
}


def frontier_targets(home: Path | None) -> list[dict[str, Any]]:
    """The five sovereign dimensions, each with its current build status for an agent home.

    Status is checked by a filesystem marker under the agent home: none exists yet anywhere in
    the estate, so every one reads ABSENT. That is the honest climb, in code.
    """
    out = []
    for f in BEYOND_HERMES:
        built = bool(home and (home / f.marker).exists())
        out.append({
            "id": f.id, "name": f.name, "question": f.question,
            "beyond_hermes": f.beyond_hermes, "builds_on": f.builds_on,
            "feasibility": f.feasibility, "status": "BUILT" if built else "ABSENT",
        })
    return out


def prescribe_climb(weak_axis_points: dict[str, int]) -> list[str]:
    """Map a graded holon's weakest axes to the frontier dimension that would raise them.

    Turns the harness from a scorer into a guide: given where a holon is weak (axis id -> points
    for axes scoring <2), which sovereign rung to build next. Advisory ordering; the operator /
    track owns sequencing.
    """
    weak = weak_axis_points
    rx: list[str] = []
    if weak.get("H7_receipts_verification", 2) < 2 or weak.get("H1_identity_honest_liveness", 2) < 2:
        rx.append("F1/F3: durable signed session identity + signed evolution receipts — the seat's "
                  "own O9 key custody is the one live-durable axis; extend it from key-proof to a "
                  "signed session+receipt spine.")
    if weak.get("H3_wake_metabolism", 2) < 2 or weak.get("O6_governed_self_improvement", 2) < 2:
        rx.append("F2: a sovereign execution-grounded verifier as the promotion ceiling — this "
                  "unblocks the wake/evolution loop the way it unblocks the estate's 0-promotions.")
    if weak.get("H4_authority_envelope", 2) < 2:
        rx.append("F4/F5: portable attenuated authority + an out-of-process reversibility gate — "
                  "replace the theater lease-string check with an un-editable external PEP.")
    return rx
