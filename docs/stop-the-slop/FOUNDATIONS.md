# FOUNDATIONS — the canon Stop the Slop stands on

Every prompt cites its **lineage**: the result in computer or cognitive science
that makes its analysis *correct* rather than merely plausible. This file is the
shared canon. The point is not erudition — it is that a finding rooted in a
theorem outranks a finding rooted in a vibe, and a vibe coder armed with the
theorem stops shipping slop.

The recurring meta-principle, stated three ways across 80 years:

- **Dijkstra (1972), *The Humble Programmer*** — "Testing shows the presence,
  not the absence, of bugs." → *Absence of a finding is never proof of safety;
  route to a tool that can actually witness the property.*
- **Thompson (1984), *Reflections on Trusting Trust*** — you cannot trust code
  you did not totally create yourself. → *Every dependency is unverified until a
  ground-truth check says otherwise.*
- **Hofstadter (1979), *GEB*** — strange loops and tangled hierarchies; meaning
  is not in the symbol but in the system that interprets it. → *A report's
  structure will seduce you into filling it; the discipline is to let the
  evidence, not the template, decide what exists.*

## Canon by theme

| Lineage | Result | What it licenses in a prompt |
|---|---|---|
| **Dijkstra** (1968, *Go To Considered Harmful*; THE system) | structured control flow; layered systems with a strict ordering | acyclic layering; a cycle is a defect, not a style |
| **Parnas** (1972, *On the Criteria…*) | information hiding; modules decomposed by secrets, not flowcharts | boundaries are contracts; coupling across them is the risk surface |
| **Tarjan** (1972) | strongly-connected components in linear time | *the* algorithm for finding dependency cycles — not regex on imports |
| **Kahn** (1962) | topological sort | a healthy module graph is a DAG; topo-order is the proof |
| **Hoare** (1969, axiomatic basis; CSP) | pre/postconditions; communicating processes | invariants and contracts are checkable, not aspirational |
| **Meyer** (Design by Contract) | obligations/benefits at interfaces | every boundary should state what it promises and requires |
| **Shannon** (1948) | entropy; information as surprise | drift/duplication is measurable entropy, not taste |
| **Saltzer & Schroeder** (1975) | least privilege; economy of mechanism; fail-safe defaults | security findings ranked by reachable privilege, not by scariness |
| **Thompson** (1984) | trusting-trust attack | supply-chain trust must be earned by evidence each time |
| **Lamport** (1978) | happens-before; ordering in distributed systems | concurrency/resilience reasoning about causality, not vibes |
| **Lehman** (laws of software evolution) | systems must be continually adapted or they rot | drift/entropy control is a law, hence a ratchet, not a nag |
| **Knuth** (literate programming; *Art of…*) | rigor + readability as one act | "altitude"/readability findings have a discipline behind them |

## How a prompt uses its lineage

1. **Name the invariant** the lineage establishes (e.g. "the import graph must be
   a DAG" ← Dijkstra/Parnas/Tarjan).
2. **Route to the mechanized form** of that result (e.g. Tarjan SCC over a real
   AST import graph — not "look for `A imports B` patterns").
3. **Rank by the property the theory says matters** (load-time reachability for
   cycles; exploitable privilege for security) — never by a cosmetic proxy.
4. **Return clean** when the property holds. Dijkstra's razor cuts both ways: if
   the witness finds nothing, report nothing — and say what you checked.

New prompts extend this table with the result they descend from. If a prompt
can't name its lineage, it isn't ready — it's a vibe with formatting.
