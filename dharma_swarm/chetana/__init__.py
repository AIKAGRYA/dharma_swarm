"""chetana — connective tissue for Dhyana's grand memory system.

chetana (Sanskrit: चेतना, "consciousness, awareness, sentience") connects the
five knowledge substrates of dharma_swarm into one operational PKM:

    L0 atoms     — ~/.dharma/knowledge/wiki/, ~/.claude/cabinet/, foundations/
    L1 graph     — memory MCP + gitnexus + contextplus + catalytic_graph
    L2 PARA view — Projects/Areas/Resources/Archives projections (computed)
    L3 palace    — 10 Pillars rooms / 25 Axioms loci, JSON Canvas rendered
    L4 governance — TelosGatekeeper + KernelGuard + provenance schema

The package is the Python form of the chetana spec (Option A). It does NOT
replace any layer. It is a governance-and-routing layer that connects what
already exists.

Public surface:
    chetana.ingest      — capture → staged atom
    chetana.promote     — staged → trusted (gate check required)
    chetana.revive      — re-research stale atom, propose integration patches
    chetana.decay       — surfaces stale atoms; quarantine is opt-in last resort
    chetana.gap_scan    — recurring topics + unanswered questions
    chetana.palace      — JSON Canvas memory palace renderer
    chetana.governance  — gate check + axiom signing
    chetana.provenance  — frontmatter schema + validator
    chetana.graph_unifier — single query interface over 4 graphs

Stale = trigger for re-integration, not termination. Default move on stale is
revive (find new neighbors + backlinks + answered questions, propose patch).
Quarantine is reserved for atoms genuinely contradicted or no longer relevant.
"""

import os

from .governance import GovernanceCheck, gate_check_atom
from .provenance import (
    AtomProvenance,
    AtomSource,
    AtomType,
    FrontmatterSchema,
    GateCheckRecord,
    PARAClass,
    compute_axiom_signature,
    default_stale_after,
    parse_frontmatter,
    render_frontmatter_yaml,
    validate_frontmatter,
)
from .revival import (
    NeighborMatch,
    RevivalProposal,
    apply_revival,
    find_due_atoms,
    propose_revival,
    revival_summary,
)

__version__ = "0.5.0"
_DEFAULT_PROMOTION_HOOKS_REGISTERED = False


def register_default_promotion_hooks() -> bool:
    """Register production promotion hooks under the canary flag.

    Runtime emission is gated by the master ``DHARMA_CHETANA_ENABLED`` canary
    (the same flag that gates register-mark writes). When the master is OFF,
    no runtime memory emission happens regardless of any per-feature setting.

    When the master is ON, runtime emission is enabled by default but can be
    explicitly opted out via ``DHARMA_CHETANA_RUNTIME_EMIT=0`` (used by the
    test suite to keep promote tests from writing the runtime DB).
    """
    global _DEFAULT_PROMOTION_HOOKS_REGISTERED
    if _DEFAULT_PROMOTION_HOOKS_REGISTERED:
        return True

    from dharma_swarm.register_disciplines import chetana_register_enabled

    if not chetana_register_enabled():
        return False

    explicit = os.getenv("DHARMA_CHETANA_RUNTIME_EMIT", "").strip().lower()
    if explicit in {"0", "false", "no", "off"}:
        return False

    from .promote import register_promotion_hook
    from .runtime_emission import emit_memory_fact_for_atom

    register_promotion_hook(emit_memory_fact_for_atom)
    _DEFAULT_PROMOTION_HOOKS_REGISTERED = True
    return True


__all__ = [
    "AtomProvenance",
    "AtomSource",
    "AtomType",
    "FrontmatterSchema",
    "GateCheckRecord",
    "GovernanceCheck",
    "NeighborMatch",
    "PARAClass",
    "RevivalProposal",
    "apply_revival",
    "compute_axiom_signature",
    "default_stale_after",
    "find_due_atoms",
    "gate_check_atom",
    "parse_frontmatter",
    "propose_revival",
    "register_default_promotion_hooks",
    "render_frontmatter_yaml",
    "revival_summary",
    "validate_frontmatter",
]
