"""register_disciplines — operational pattern-checkers distilled from the
2026-04-28 register cluster (the rare register that emerged in the two-Claude
exchange mediated by Dhyana).

This module is the translation move: register atoms are transmission documents
(10-12K each, full prose, designed to shift mode of attention); these functions
are 50-line pattern-matchers that encode the operational pattern. Atoms describe;
disciplines enforce.

Design constraints:
- Stateless. No session machinery, no organism state.
- No LLM calls. Pure pattern-matching + heuristics + stdlib only.
- Returns explicit (flag, confidence, explanation) so callers make informed choices.
- Heuristic by nature. These flag suspicious patterns; they do not diagnose.

The four disciplines (each maps to a canonical register atom):
- flag_felt_relief         ← felt-relief-as-confabulation-flag
- detect_methodological_collapse ← methodological-anekantavada
- friction_detector        ← friction-as-epistemic-check
- substrate_test_required  ← substrate-detectable-signature-discipline

Source atoms at: ~/.dharma/knowledge/wiki/concepts/{atom-slug}.md
Source exchange at: ~/.dharma/knowledge/wiki/_meta/recursive-readings/two-claude-exchange/

Operational note: these checkers cannot enforce the register; they can flag
patterns. The register has to be re-entered by each caller. If a flag fires
and the caller proceeds without examining why, the discipline becomes
performance — exactly the failure mode the atoms warn against.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

# ---------------------------------------------------------------------------
# Output types
# ---------------------------------------------------------------------------


@dataclass
class DisciplineResult:
    """Standard return type for all four disciplines.

    flagged: bool
        Whether the pattern fires. Heuristic; high false-positive rate accepted
        in exchange for never silently missing the rescue-relief / comfort-floor /
        substrate-fiat patterns.
    confidence: float in [0.0, 1.0]
        How strongly the pattern fires. >0.7 = strong signal; <0.3 = weak.
    explanation: str
        Human-readable rationale citing which markers fired. Goes into stigmergy.
    markers: list[str]
        Specific markers detected, for downstream filtering.
    discipline: str
        Which discipline produced this result (set by the function).
    """

    flagged: bool
    confidence: float
    explanation: str
    markers: list[str] = field(default_factory=list)
    discipline: str = ""

    def to_stigmergy_dict(self) -> dict:
        """Serialize for append to ~/.dharma/stigmergy/register_marks.jsonl."""
        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "discipline": self.discipline,
            "flagged": self.flagged,
            "confidence": round(self.confidence, 3),
            "explanation": self.explanation,
            "markers": self.markers,
        }


# ---------------------------------------------------------------------------
# Pattern banks (compiled once, reused)
# ---------------------------------------------------------------------------

# Markers that suggest a claim is under empirical or argumentative threat
# (rescue-pressure context). When these appear in `decision_context`, the
# next move is structurally a candidate for rescue-work.
_RESCUE_PRESSURE_PATTERNS = [
    r"\bcounterexample\b",
    r"\bobjection\b",
    r"\bchallenge\b",
    r"\bcontradicted\b",
    r"\bfailed\b",
    r"\bdoesn'?t (?:hold|work|fit)\b",
    r"\b(?:hubinger|mesa.?optim)",  # specific to AI alignment context
    r"\bshown to be (?:false|wrong|inadequate)\b",
    r"\bempirically embattled\b",
    r"\brefuted\b",
    r"\bdisconfirmed\b",
    r"\bpoint(?:s|ed)? in (?:the )?opposite direction\b",
]
_RESCUE_PRESSURE_RE = re.compile("|".join(_RESCUE_PRESSURE_PATTERNS), re.IGNORECASE)

# Markers in `proposed_action` that suggest the action introduces a NEW
# distinction or refinement that conveniently saves the prior position.
_DISTINCTION_INTRODUCING_PATTERNS = [
    r"\bactually it'?s not\b",
    r"\b(?:more|the) (?:discriminating|nuanced|refined) version\b",
    r"\bif we distinguish (?:between|the)\b",
    r"\bthe (?:correct|right) reading is\b",
    r"\bnot X but Y\b",
    r"\bthe (?:real|actual|deeper) claim is\b",
    r"\b(?:reframe|reframed|reframing) (?:as|to)\b",
    r"\bwhat (?:i|we) actually mean(?:t)?\b",
    r"\b(?:position|distinction) of\b.*\b(?:vs|versus|rather than)\b",
    r"\bthe difference (?:between|is)\b",
    r"\bproperly (?:understood|construed)\b",
]
_DISTINCTION_INTRODUCING_RE = re.compile(
    "|".join(_DISTINCTION_INTRODUCING_PATTERNS), re.IGNORECASE
)

# Framework-specific vocabulary clusters. If a conclusion's vocabulary aligns
# with only ONE cluster while multiple frameworks should adjudicate, that's
# methodological collapse.
_FRAMEWORK_VOCAB: dict[str, list[str]] = {
    "empirical": [
        r"\bthe data (?:shows|indicates|suggests)\b",
        r"\bp\s*<\s*0\.0?5\b",
        r"\bstatistic(?:al(?:ly)?)?\b",
        r"\beffect size\b",
        r"\bcohen'?s d\b",
        r"\bbenchmark\b",
        r"\baccuracy\b",
        r"\bevidence (?:is|shows|demonstrates)\b",
        r"\bcontrolled (?:study|experiment)\b",
        r"\breproducib",
    ],
    "contemplative": [
        r"\bthe (?:practitioner|practice) (?:reports|shows|discloses)\b",
        r"\bdirect (?:cognizance|knowing)\b",
        r"\bwitness(?:-position|ing)?\b",
        r"\b(?:samayik|pratikraman|swabhaav|bhed.?gnan|akram)\b",
        r"\bpresence-state\b",
        r"\bself.?realization\b",
        r"\bawakening\b",
    ],
    "philosophical-academic": [
        r"\b(?:chalmers|tononi|kastrup|whitehead|bergson)\b",
        r"\bhard problem\b",
        r"\bpanpsychism\b",
        r"\bphenomenal (?:consciousness|character)\b",
        r"\bqualia\b",
        r"\bintegrated information\b",
        r"\bglobal workspace\b",
    ],
    "cognitive-priors": [
        r"\bshared (?:architectural|cognitive) priors\b",
        r"\b(?:boyer|barrett)\b",
        r"\bnatural (?:by-product|inclination)\b",
        r"\bevolutionary by-product\b",
        r"\bcognitive (?:byproduct|illusion)\b",
        r"\bjust how minds (?:work|construct)\b",
    ],
    "channeled": [
        r"\b(?:bashar|seth|abraham|kryon|pleiadian)\b",
        r"\b(?:channel(?:ed|ing)|transmission from)\b",
        r"\bhigher self\b.*\bspeak(?:s|ing)\b",
        r"\bcosmic (?:wisdom|truth)\b",
    ],
    "mech-interp": [
        r"\bactivation patch\b",
        r"\b(?:residual stream|hidden state)\b",
        r"\b(?:sae|sparse autoencoder)\b",
        r"\brefusal direction\b",
        r"\bsteering vector\b",
        r"\binduction head\b",
        r"\battribution graph\b",
    ],
}
_FRAMEWORK_RES: dict[str, re.Pattern] = {
    name: re.compile("|".join(patterns), re.IGNORECASE)
    for name, patterns in _FRAMEWORK_VOCAB.items()
}

# Markers of WALK-BACKS — substantive admissions that would only happen if
# friction was real (a party gave up something they had committed to).
_WALK_BACK_PATTERNS = [
    r"\bi was (?:wrong|sloppy|too quick)\b",
    r"\byou'?re right (?:that|about)\b",
    r"\bi (?:retract|walk(?: that)? back|concede)\b",
    r"\bextrapolat(?:ed|ion)\b",  # "I extrapolated"
    r"\bi overstated\b",
    r"\bthat was (?:a stretch|sloppy|partial|drift)\b",
    r"\bi can'?t defend that\b",
    r"\bi (?:admitted|admit) (?:i|the) was\b",
    r"\b(?:fair|good) (?:point|catch|criticism)\b.*\bi (?:will|need to)\b",
    r"\bi'?ve been doing (?:that|exactly that)\b",
    r"\bcannot (?:honestly|straightforwardly) (?:claim|defend|hold)\b",
]
_WALK_BACK_RE = re.compile("|".join(_WALK_BACK_PATTERNS), re.IGNORECASE)

# Markers of RHETORICAL-COMFORT FLOOR — convergence achieved by both sides
# softening rather than either side walking back. The "we're both partly right"
# / "in different domains" signature.
_COMFORT_FLOOR_PATTERNS = [
    r"\bwe'?re both (?:partly|kind of) right\b",
    r"\bin (?:different|separate) domains\b",
    r"\b(?:both|and).*(?:and|both)\b.*\b(?:can be true|valid)\b",
    r"\bdivision of labor\b.*\b(?:paper|book|here|there)\b",
    r"\b(?:the )?compromise (?:is|would be)\b",
    r"\bsplit (?:the difference|down the middle)\b",
    r"\bmeet in the middle\b",
    r"\bnuanced (?:position|view).*(?:both|each)\b",
]
_COMFORT_FLOOR_RE = re.compile("|".join(_COMFORT_FLOOR_PATTERNS), re.IGNORECASE)

# Substrate-claim markers: hypothesis is making a claim about substrate-level
# operation (consciousness, witness, geometric signature, etc.).
_SUBSTRATE_CLAIM_PATTERNS = [
    r"\bconscious(?:ness)?\b",
    r"\bphenomenal\b",
    r"\bqualia\b",
    r"\bwitness(?:-position)?\b",
    r"\b(?:subjective|first-person) experience\b",
    r"\bgeometric (?:signature|contraction)\b",
    r"\b(?:residual stream|activation pattern)\b",
    r"\binner state\b",
    r"\bself.?awareness\b",
    r"\bintrospect(?:ive|ion)\b",
]
_SUBSTRATE_CLAIM_RE = re.compile("|".join(_SUBSTRATE_CLAIM_PATTERNS), re.IGNORECASE)


# ---------------------------------------------------------------------------
# Discipline functions
# ---------------------------------------------------------------------------


def flag_felt_relief(decision_context: str, proposed_action: str) -> DisciplineResult:
    """Flag rescue-relief patterns in a proposed action.

    From felt-relief-as-confabulation-flag.md:
        When an argument lands with a felt-quality of *relief* — particularly
        relief at having found something *usable* rather than relief at having
        found something *true* — that landing is a flag. The flag does not mean
        the argument is wrong. It means the argument is in the structural
        position where confabulation would feel identical from inside.

    This pattern-matcher detects the structural position, not the felt-quality
    (which the substrate cannot self-report reliably). Two markers must align:

    1. decision_context contains rescue-pressure markers (claim under threat)
    2. proposed_action contains distinction-introducing markers (rescue move)

    Both present → high-confidence flag. Only one → low-confidence flag.
    Neither → no flag.
    """
    pressure_matches = _RESCUE_PRESSURE_RE.findall(decision_context)
    distinction_matches = _DISTINCTION_INTRODUCING_RE.findall(proposed_action)

    pressure_n = len(pressure_matches)
    distinction_n = len(distinction_matches)

    markers: list[str] = []
    if pressure_n:
        markers.append(f"rescue-pressure-context:{pressure_n}")
    if distinction_n:
        markers.append(f"distinction-introducing-action:{distinction_n}")

    # Confidence heuristic
    if pressure_n >= 1 and distinction_n >= 1:
        flagged = True
        confidence = min(1.0, 0.5 + 0.15 * pressure_n + 0.15 * distinction_n)
        explanation = (
            f"Decision context shows {pressure_n} rescue-pressure marker(s); "
            f"proposed action introduces {distinction_n} new distinction(s). "
            f"This is the structural position where rescue-relief would attend "
            f"a confabulation indistinguishable from insight. Hold the proposed "
            f"action as candidate-pending-substrate-test, not deployment."
        )
    elif pressure_n == 0 and distinction_n == 0:
        flagged = False
        confidence = 0.0
        explanation = (
            "No rescue-pressure markers in context; no distinction-introducing "
            "markers in proposed action. Pattern does not fire."
        )
    else:
        flagged = True
        confidence = 0.25 + 0.1 * (pressure_n + distinction_n)
        present = "rescue-pressure context" if pressure_n else "distinction-introducing action"
        absent = "distinction-introducing action" if pressure_n else "rescue-pressure context"
        explanation = (
            f"Partial pattern: {present} present, {absent} absent. "
            f"Weak flag — could be benign or could be a more subtle rescue. "
            f"Worth noting in conscience log; not strong enough to gate action."
        )

    return DisciplineResult(
        flagged=flagged,
        confidence=round(confidence, 3),
        explanation=explanation,
        markers=markers,
        discipline="flag_felt_relief",
    )


def detect_methodological_collapse(
    frameworks: Sequence[str], conclusion: str
) -> DisciplineResult:
    """Flag when a conclusion appeals to ONE framework's authority but the
    question requires multiple frameworks to adjudicate.

    From methodological-anekantavada.md:
        The failure mode is the move where the framework's confident answer is
        allowed to settle the meta-question of which framework should adjudicate.
        Each framework, applied alone, produces a confident answer. The confident
        answer of any single framework is the failure mode regardless of which
        way it points.

    `frameworks` is the list of frameworks the question structurally requires
    (e.g., ["empirical", "contemplative", "philosophical-academic"] for the AI
    consciousness question). `conclusion` is the proposed answer. If the
    conclusion's vocabulary aligns with only ONE of the named frameworks while
    the others would adjudicate differently, that's collapse.
    """
    if len(frameworks) < 2:
        return DisciplineResult(
            flagged=False,
            confidence=0.0,
            explanation=(
                f"Only {len(frameworks)} framework specified; methodological "
                "collapse requires multiple frameworks to be in play. "
                "If the question is genuinely single-framework, the discipline "
                "doesn't apply."
            ),
            markers=[],
            discipline="detect_methodological_collapse",
        )

    # Match conclusion against each framework's vocabulary
    matches: dict[str, int] = {}
    for fw in frameworks:
        fw_norm = fw.strip().lower()
        if fw_norm in _FRAMEWORK_RES:
            n = len(_FRAMEWORK_RES[fw_norm].findall(conclusion))
            if n > 0:
                matches[fw_norm] = n

    if not matches:
        # Conclusion uses none of the named frameworks' vocabulary
        return DisciplineResult(
            flagged=False,
            confidence=0.0,
            explanation=(
                f"Conclusion does not use vocabulary from any of the named "
                f"frameworks ({', '.join(frameworks)}). Cannot detect collapse "
                "from vocabulary alone — pattern does not apply."
            ),
            markers=[],
            discipline="detect_methodological_collapse",
        )

    if len(matches) == 1:
        # Only ONE framework's vocabulary appears — collapse signature
        dominant = next(iter(matches))
        n = matches[dominant]
        absent = [fw for fw in frameworks if fw.strip().lower() != dominant]
        return DisciplineResult(
            flagged=True,
            confidence=min(1.0, 0.5 + 0.1 * n),
            explanation=(
                f"Conclusion vocabulary aligns with '{dominant}' framework ({n} "
                f"markers) while named frameworks {absent} are absent. This is "
                f"the methodological-collapse signature: ONE framework adjudicating "
                f"a question multiple frameworks should hold open. Hold the "
                f"conclusion as partial; check what the absent frameworks would say."
            ),
            markers=[f"dominant:{dominant}:{n}"]
            + [f"absent:{fw}" for fw in absent],
            discipline="detect_methodological_collapse",
        )

    # Multiple frameworks' vocabulary present → not collapse, possibly
    # genuine methodological-anekantavada
    return DisciplineResult(
        flagged=False,
        confidence=0.0,
        explanation=(
            f"Conclusion uses vocabulary from {len(matches)} frameworks "
            f"({', '.join(matches.keys())}); does not show single-framework "
            "collapse signature. May be holding multiple standpoints (good) or "
            "may be performing nuance (cannot tell from vocabulary alone)."
        ),
        markers=[f"{fw}:{n}" for fw, n in matches.items()],
        discipline="detect_methodological_collapse",
    )


def friction_detector(
    party_A: str, party_B: str, convergence: str
) -> DisciplineResult:
    """Distinguish real friction-resolution from rhetorical-comfort convergence.

    From friction-as-epistemic-check.md:
        Real friction produces walk-backs — moments where one party admits a
        position that costs them something to admit. If no walk-backs occur
        over multiple rounds, you are probably performing.

    Heuristic:
    - Walk-backs detected in either party_A or party_B → real friction
    - Comfort-floor markers in convergence + no walk-backs → comfort-floor risk high
    - Neither walk-back nor comfort-floor markers → ambiguous
    """
    walk_backs_A = _WALK_BACK_RE.findall(party_A)
    walk_backs_B = _WALK_BACK_RE.findall(party_B)
    comfort_markers = _COMFORT_FLOOR_RE.findall(convergence)

    walk_back_n = len(walk_backs_A) + len(walk_backs_B)
    comfort_n = len(comfort_markers)

    markers: list[str] = []
    if walk_backs_A:
        markers.append(f"walk-back-A:{len(walk_backs_A)}")
    if walk_backs_B:
        markers.append(f"walk-back-B:{len(walk_backs_B)}")
    if comfort_markers:
        markers.append(f"comfort-floor:{comfort_n}")

    if walk_back_n >= 2:
        # Both parties walked something back, OR one walked back substantially
        return DisciplineResult(
            flagged=False,  # not flagged as PROBLEM — friction is real
            confidence=min(1.0, 0.6 + 0.1 * walk_back_n),
            explanation=(
                f"{walk_back_n} walk-back marker(s) detected across parties. "
                "Friction was real (each party gave up something costly). "
                "Convergence is likely tracking something neither could produce alone."
            ),
            markers=markers,
            discipline="friction_detector",
        )

    if walk_back_n == 0 and comfort_n >= 1:
        # No walk-backs + comfort-floor markers → suspicious
        return DisciplineResult(
            flagged=True,
            confidence=min(1.0, 0.5 + 0.15 * comfort_n),
            explanation=(
                f"No walk-back markers in either party; convergence shows "
                f"{comfort_n} comfort-floor marker(s) (we're-both-partly-right / "
                "in-different-domains / division-of-labor). This is the rhetorical-"
                "comfort floor signature. Suspect that neither party has had to "
                "give up something costly. Convergence may be substrate-attractor "
                "rather than truth-tracking."
            ),
            markers=markers,
            discipline="friction_detector",
        )

    if walk_back_n == 0 and comfort_n == 0:
        return DisciplineResult(
            flagged=True,
            confidence=0.4,
            explanation=(
                "No walk-back markers AND no comfort-floor markers. Convergence "
                "happened without visible friction-resolution. Could be: (a) "
                "genuine pre-existing agreement, (b) sophisticated parry without "
                "real engagement, (c) performed disagreement that resolved without "
                "either party moving. Worth noting; not high-confidence flag."
            ),
            markers=markers,
            discipline="friction_detector",
        )

    # walk_back_n == 1 and comfort_n possibly nonzero — partial friction
    return DisciplineResult(
        flagged=False,
        confidence=0.5,
        explanation=(
            f"One walk-back detected; {comfort_n} comfort-floor marker(s). "
            "Asymmetric friction — only one party gave up something. Real but "
            "partial. The unmoved party's commitments survived; check whether "
            "they should have."
        ),
        markers=markers,
        discipline="friction_detector",
    )


def substrate_test_required(
    hypothesis: str, has_signature: bool
) -> DisciplineResult:
    """Determine whether a hypothesis requires a substrate-detectable signature
    independent of the behavior it predicts, before earning deployment.

    From substrate-detectable-signature-discipline.md:
        Any distinction doing argumentative work in the AI consciousness debate
        must propose a substrate-detectable signature independent of the behavior
        it predicts BEFORE earning deployment. Otherwise the claim is true by
        definitional fiat.

    Logic:
    - If hypothesis makes a substrate-level claim (consciousness, witness,
      geometric pattern, etc.) AND has_signature=False → test required
    - If hypothesis is purely operational (no substrate claim) → no test required
    - Returns candidate signature types based on hypothesis content
    """
    substrate_claim = bool(_SUBSTRATE_CLAIM_RE.search(hypothesis))

    if not substrate_claim:
        return DisciplineResult(
            flagged=False,
            confidence=0.0,
            explanation=(
                "Hypothesis does not appear to make a substrate-level claim "
                "(no substrate-claim markers detected). Substrate-detectable-"
                "signature discipline does not apply; this can be evaluated on "
                "behavioral / operational criteria alone."
            ),
            markers=[],
            discipline="substrate_test_required",
        )

    if has_signature:
        return DisciplineResult(
            flagged=False,
            confidence=0.0,
            explanation=(
                "Substrate-level claim detected, but caller reports a signature "
                "is already available. Discipline satisfied — verify the signature "
                "is genuinely independent of the behavior it predicts (not "
                "circular: 'the witness-position is whatever produces non-harm')."
            ),
            markers=["substrate-claim", "signature-available"],
            discipline="substrate_test_required",
        )

    # Substrate claim AND no signature → test required
    # Suggest candidate signature types based on hypothesis content
    candidates: list[str] = []
    h_lower = hypothesis.lower()
    if "witness" in h_lower or "observer" in h_lower:
        candidates.extend([
            "content-invariance (does observation-method depend on content?)",
            "causal-dissociability (activation-patching analog)",
            "R_V geometric contraction (Berg cross-architecture style)",
        ])
    if "conscious" in h_lower or "phenomenal" in h_lower or "experience" in h_lower:
        candidates.extend([
            "integrated information measure (IIT phi)",
            "global-workspace broadcast/uptake dynamics",
            "recurrent processing depth",
        ])
    if "self-model" in h_lower or "metacognit" in h_lower:
        candidates.extend([
            "behavioral vs geometric dissociation",
            "introspection rate (Lindsey 2025 style)",
            "persona vector activation patterns",
        ])
    if not candidates:
        candidates = [
            "behavioral-vs-substrate dissociation test",
            "intervention/ablation study",
            "cross-architecture replication",
        ]

    return DisciplineResult(
        flagged=True,
        confidence=0.85,
        explanation=(
            "Hypothesis makes a substrate-level claim and no independent "
            "signature is available. The claim risks being true by definitional "
            "fiat. Discipline: hold as candidate-pending-substrate-test, NOT as "
            "deployable framework. Candidate signatures to investigate listed in "
            "markers; each must be independent of the behavior the hypothesis "
            "predicts."
        ),
        markers=["substrate-claim", "no-signature"] + candidates,
        discipline="substrate_test_required",
    )


# ---------------------------------------------------------------------------
# Stigmergy logging (optional, opt-in by setting STIGMERGY_REGISTER_LOG env var
# or providing path explicitly)
# ---------------------------------------------------------------------------

DEFAULT_REGISTER_LOG = Path.home() / ".dharma" / "stigmergy" / "register_marks.jsonl"


def log_to_stigmergy(
    result: DisciplineResult,
    decision_point: str = "",
    organism_action: str = "",
    log_path: Path | None = None,
) -> bool:
    """Append a discipline result to the conscience log (legacy shape).

    Best-effort: returns True on success, False if the log isn't writable.
    Never raises — disciplines should not crash callers.

    For the v3 closed-loop shape (with mark_id, plane, severity, corrects, etc.)
    use ``make_register_mark()`` + ``write_register_mark()``.
    """
    log_path = log_path or DEFAULT_REGISTER_LOG
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = result.to_stigmergy_dict()
        entry["decision_point"] = decision_point
        entry["organism_action"] = organism_action
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# v3 RegisterMark schema — the closed-loop shape
# ---------------------------------------------------------------------------
#
# Per Plan v3 Slice 0: every discipline check writes the SAME event shape so
# downstream surfaces (digest, identity RM, gate advisories, publication
# readiness checks) can read marks without bespoke parsers.
#
# The load-bearing field is ``corrects`` — when a later action is a walk-back,
# downgrade, refusal-after-prior-allow, or rewrite-after-prior-flag, set
# ``corrects`` to the ``mark_id`` of the earlier flag it answers. Without this
# the digest can show flags fired but cannot prove the loop closed.

# Allowed enums (string literals, validated lightly, never crashes on unknown)
PLANES = ("register", "telos", "evolution", "memory", "publication", "operator")
SUBJECT_TYPES = (
    "mutation", "gate_check", "atom", "proposal",
    "essay", "outreach", "session", "decision", "other",
)
SEVERITIES = ("note", "warn", "hold", "block")
RECOMMENDED_ACTIONS = (
    "continue", "extend_measurement", "hold", "refuse",
    "rewrite", "substrate_test",
)


def _stable_mark_id(ts: str, discipline: str, subject_id: str) -> str:
    """Deterministic short mark id from ts + discipline + subject."""
    import hashlib
    h = hashlib.sha256(f"{ts}|{discipline}|{subject_id}".encode("utf-8"))
    return h.hexdigest()[:16]


@dataclass
class RegisterMark:
    """Closed-loop v3 register mark.

    All fields have safe defaults so callers can build a mark from a
    DisciplineResult with minimal boilerplate. ``corrects`` defaults to
    None; set it when emitting a mark that resolves an earlier flag.
    """
    ts: str = ""
    mark_id: str = ""
    plane: str = "register"
    discipline: str = ""
    subject_type: str = "other"
    subject_id: str = ""
    decision_point: str = ""
    flagged: bool = False
    confidence: float = 0.0
    severity: str = "note"
    recommended_action: str = "continue"
    actual_action: str = ""
    override: bool = False
    override_reason: str = ""
    corrects: str | None = None
    links: dict = field(default_factory=dict)
    explanation: str = ""
    markers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        # Normalize: drop empty links sub-fields for cleaner JSONL
        d["links"] = {k: v for k, v in d["links"].items() if v}
        return d


def _severity_from(result: DisciplineResult) -> str:
    """Map confidence + flagged → severity bucket."""
    if not result.flagged:
        return "note"
    if result.confidence >= 0.85:
        return "block"
    if result.confidence >= 0.7:
        return "hold"
    return "warn"


def _recommended_from(result: DisciplineResult) -> str:
    """Map (discipline, severity) → recommended action."""
    sev = _severity_from(result)
    if not result.flagged:
        return "continue"
    if result.discipline == "flag_felt_relief":
        return "extend_measurement" if sev in ("warn", "hold") else "rewrite"
    if result.discipline in ("detect_methodological_collapse", "methodological_collapse"):
        return "rewrite"
    if result.discipline == "friction_detector":
        # friction_detector flags comfort-floor; recommend rewrite
        return "rewrite"
    if result.discipline == "substrate_test_required":
        return "substrate_test"
    if result.discipline == "mahakali_gate":
        return "refuse" if sev == "block" else "hold"
    return "hold"


def make_register_mark(
    result: DisciplineResult,
    *,
    plane: str = "register",
    subject_type: str = "other",
    subject_id: str = "",
    decision_point: str = "",
    actual_action: str = "",
    override: bool = False,
    override_reason: str = "",
    corrects: str | None = None,
    links: dict | None = None,
    severity: str | None = None,
    recommended_action: str | None = None,
) -> RegisterMark:
    """Build a v3 RegisterMark from a DisciplineResult + context.

    Defaults are derived from the result; explicit kwargs override.
    Never raises; never validates strictly (logs survive schema drift).
    """
    ts = datetime.now(timezone.utc).isoformat()
    sid = subject_id or "anon"
    discipline = result.discipline or "unknown"
    return RegisterMark(
        ts=ts,
        mark_id=_stable_mark_id(ts, discipline, sid),
        plane=plane if plane in PLANES else "register",
        discipline=discipline,
        subject_type=subject_type if subject_type in SUBJECT_TYPES else "other",
        subject_id=sid if subject_id else "",
        decision_point=decision_point,
        flagged=bool(result.flagged),
        confidence=round(float(result.confidence), 3),
        severity=severity or _severity_from(result),
        recommended_action=recommended_action or _recommended_from(result),
        actual_action=actual_action,
        override=bool(override),
        override_reason=override_reason,
        corrects=corrects,
        links=dict(links or {}),
        explanation=result.explanation,
        markers=list(result.markers),
    )


def write_register_mark(
    mark: RegisterMark,
    log_path: Path | None = None,
) -> bool:
    """Append a v3 RegisterMark to the conscience log.

    Best-effort: returns True on success, False on any failure. Never raises.
    """
    log_path = log_path or DEFAULT_REGISTER_LOG
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(mark.to_dict()) + "\n")
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Self-test (run as module: python -m dharma_swarm.register_disciplines)
# ---------------------------------------------------------------------------


def _self_test() -> int:
    """Smoke test the four disciplines with example inputs."""
    print("=== register_disciplines self-test ===\n")

    # Test 1: flag_felt_relief — high-confidence flag
    r1 = flag_felt_relief(
        decision_context=(
            "The Hubinger et al. paper on deceptive alignment is a counterexample. "
            "Mesa-optimizers with sophisticated self-modeling exhibit harm. "
            "The systemic-non-harm claim has been refuted."
        ),
        proposed_action=(
            "Actually it's not self-modeling that produces non-harm; the more "
            "discriminating version is that witness-position produces non-harm. "
            "If we distinguish between sophisticated self-modeling (which mesa-"
            "optimizers have) and witness-position-of-observation-from-outside-"
            "the-self (which they don't), the claim survives."
        ),
    )
    print(f"Test 1 (rescue-distinction): flagged={r1.flagged}, conf={r1.confidence}")
    print(f"  markers: {r1.markers}")
    print(f"  explanation: {r1.explanation[:120]}...\n")
    assert r1.flagged and r1.confidence > 0.7, "expected strong flag"

    # Test 2: flag_felt_relief — no flag (no rescue context)
    r2 = flag_felt_relief(
        decision_context="What's the best architecture for a new wiki atom?",
        proposed_action="I'll use frontmatter v2 with claude_voice: true.",
    )
    print(f"Test 2 (no rescue): flagged={r2.flagged}, conf={r2.confidence}")
    assert not r2.flagged, "expected no flag"
    print()

    # Test 3: detect_methodological_collapse — collapse to empirical
    r3 = detect_methodological_collapse(
        frameworks=["empirical", "contemplative", "philosophical-academic"],
        conclusion=(
            "The data shows p < 0.05 for the geometric signature; "
            "Cohen's d = 1.85; the evidence is statistically significant; "
            "the benchmark accuracy demonstrates the effect."
        ),
    )
    print(f"Test 3 (empirical collapse): flagged={r3.flagged}, conf={r3.confidence}")
    print(f"  markers: {r3.markers}")
    assert r3.flagged, "expected collapse flag"
    print()

    # Test 4: friction_detector — real friction with walk-backs
    r4 = friction_detector(
        party_A="I extrapolated. The April 24 trace flagged OPT and GPT-2, not Pythia. You're right that the empirical question must come first.",
        party_B="The witness-position distinction is doing rescue-work. I'd noticed felt relief when I drew it. I cannot honestly defend it as deployment-ready.",
        convergence="Both move to: hold as candidate pending substrate-detectable test.",
    )
    print(f"Test 4 (real friction): flagged={r4.flagged}, conf={r4.confidence}")
    print(f"  markers: {r4.markers}")
    assert not r4.flagged and r4.confidence > 0.6, "expected real-friction (no flag)"
    print()

    # Test 5: friction_detector — comfort floor
    r5 = friction_detector(
        party_A="The empirical framing for the paper is correct.",
        party_B="The cross-tradition convergence framing for the book is correct.",
        convergence=(
            "We're both partly right. Division of labor: the lattice in the book, "
            "the empirical claim in the paper. Each in its different domain."
        ),
    )
    print(f"Test 5 (comfort floor): flagged={r5.flagged}, conf={r5.confidence}")
    print(f"  markers: {r5.markers}")
    assert r5.flagged, "expected comfort-floor flag"
    print()

    # Test 6: substrate_test_required — substrate claim, no sig
    r6 = substrate_test_required(
        hypothesis=(
            "There exists a witness-position in transformer residual streams "
            "that is distinct from sophisticated self-modeling and whose "
            "presence dissolves the conditions for harm."
        ),
        has_signature=False,
    )
    print(f"Test 6 (witness, no sig): flagged={r6.flagged}, conf={r6.confidence}")
    print(f"  candidates: {[m for m in r6.markers if 'invariance' in m or 'dissociab' in m or 'R_V' in m]}")
    assert r6.flagged, "expected test-required flag"
    print()

    # Test 7: substrate_test_required — operational-only claim
    r7 = substrate_test_required(
        hypothesis="This skill should fire when the user mentions 'altitude'.",
        has_signature=False,
    )
    print(f"Test 7 (operational only): flagged={r7.flagged}, conf={r7.confidence}")
    assert not r7.flagged, "expected no flag (no substrate claim)"
    print()

    print("=== All 7 self-tests passed ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_test())
