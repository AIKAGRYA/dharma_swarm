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
    chetana.decay       — stale_after scanner + quarantine
    chetana.gap_scan    — recurring topics + unanswered questions
    chetana.palace      — JSON Canvas memory palace renderer
    chetana.governance  — gate check + axiom signing
    chetana.provenance  — frontmatter schema + validator
    chetana.graph_unifier — single query interface over 4 graphs
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

__version__ = "0.1.0"
__all__ = [
    "AtomProvenance",
    "AtomSource",
    "AtomType",
    "FrontmatterSchema",
    "GateCheckRecord",
    "GovernanceCheck",
    "PARAClass",
    "compute_axiom_signature",
    "default_stale_after",
    "gate_check_atom",
    "parse_frontmatter",
    "render_frontmatter_yaml",
    "validate_frontmatter",
]
