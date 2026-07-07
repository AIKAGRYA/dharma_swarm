import sys, json
sys.path.insert(0, "/Users/dhyana/dharma_swarm/.claude/worktrees/verifier-ranker-v0-spike/scripts/governance/hygiene")
from ratchet_counters import COUNTERS, Direction
from ratchet import Comparison, tighten

# 1. Shipped counter set: dimension + directions
downs = [c.name for c in COUNTERS if c.direction is Direction.DOWN]
ups   = [c.name for c in COUNTERS if c.direction is Direction.UP]
print(f"counters={len(COUNTERS)} down={len(downs)} up={len(ups)} up_names={ups}")

# 2. Stutter admissible: value == baseline stays green forever (no strict descent required)
c = Comparison(name="x", direction=Direction.DOWN, baseline=6, value=6, end_target=0, evidence=())
print("stutter verdict:", c.verdict, "| regressed:", c.regressed)

# 3. Legal infinite alternation 6,5,6,5,... under dV<=0-or-reviewed-edit
log = []
baseline = 6
for i in range(4):
    imp = Comparison("x", Direction.DOWN, baseline, 5, 0, ())          # improve 6->5
    assert not imp.regressed and imp.improved
    baseline = tighten({"x": baseline}, [imp])["x"]                     # --tighten adopts 5
    log.append(("improve->5, tightened baseline", baseline))
    baseline = 6                                                        # reviewed manual edit loosens (coercion)
    stut = Comparison("x", Direction.DOWN, baseline, 6, 0, ())
    assert stut.verdict == "OK"                                         # 6 is green again
    log.append(("reviewed loosen->6, verdict", stut.verdict))
print("alternation legal, no convergence:", log)

# 4. Local descent does not compose across a semilattice join:
# V_o = |unresolved obligations visible in o's projection|. Both nodes strictly descend locally; join raises A's V.
A = {"obl1"}            # A resolved obl1 -> V_A: 1 -> 0
A_resolved = {"obl1"}
V_A_before = len(A - A_resolved)                       # 0 (descended)
B = {"obl2", "obl3", "obl4"}                           # B descended 4->3 locally, 3 unresolved remain
joined_A = (A | B) - A_resolved                        # CRDT join: union of events
print(f"V_A after own descent = {V_A_before}; V_A after mesh join = {len(joined_A)} (rose 0 -> {len(joined_A)})")
