M5 = ['P', 'T', 'W', 'A', 'C']
ROWS = {
    'deductive':     {'P'},
    'empirical':     {'T', 'W'},
    'differential':  {'T', 'P'},
    'observational': {'W'},
    'attested':      {'A'},
}

# --- Part 1: could Challenged_by be modeled as a bottom GRADE instead of a veto?
# Grade semantics: admissible iff receipt's best modality is in the row's up-set.
# core.md semantics (line 75/97): unresolved Challenged_by BLOCKS canonization
# regardless of other admissible evidence (separate conjunct no_unresolved_challenge).
# Countercase receipt: deductive claim with evidence {Proven_by(pass), Challenged_by(unresolved)}.
def canonical_grade_model(claim, evidence):
    return any(m in ROWS[claim] for m in evidence)          # C is bottom: never in a row, just ignored
def canonical_core_md(claim, evidence):
    return any(m in ROWS[claim] for m in evidence - {'C'}) and 'C' not in evidence
ev = {'P', 'C'}
print("receipt: deductive claim, evidence {Proven_by, unresolved Challenged_by}")
print("  C-as-bottom-grade model canonical? ->", canonical_grade_model('deductive', ev))
print("  core.md veto semantics  canonical? ->", canonical_core_md('deductive', ev))

# --- Part 2: concrete behavior divergence, prompt-chain vs matrix (C1: is it decoration?)
# Prompt chain (PROMPT line 44): Proven_by <: Tested_by <: Attested_by <: Assumed  (W absent)
# Threshold reading: modality admissible for a claim iff <= the class ceiling... the natural
# chain semantics: stronger discharges whatever weaker does; P is strongest, discharges all.
chain_rank = {'P': 0, 'T': 1, 'A': 2}   # lower = stronger; W unrepresentable
def admissible_chain(claim, m, ceiling):
    if m not in chain_rank: return None  # Witnessed_by has no rank: unrepresentable
    return chain_rank[m] <= chain_rank[ceiling]
def admissible_matrix(claim, m):
    return m in ROWS[claim]

cases = [
    ('observational', 'W', 'A'),   # replayable runtime witness of an observational claim
    ('observational', 'P', 'A'),   # static proof offered for "this event was observed"
    ('deductive',     'W', 'P'),   # runtime witness offered for deductive safety
]
for claim, m, ceil in cases:
    print(f"claim={claim:14s} modality={m}:  chain-model={admissible_chain(claim, m, ceil)}   core.md-matrix={admissible_matrix(claim, m)}")
