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

__version__ = "0.3.0"
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
    "render_frontmatter_yaml",
    "revival_summary",
    "validate_frontmatter",
]
