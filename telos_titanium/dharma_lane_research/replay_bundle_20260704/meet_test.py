from functools import reduce

G = ['Bottom','Assumed','Attested','Tested','Proven']
rank = {g:i for i,g in enumerate(G)}
def meet(a,b): return G[min(rank[a],rank[b])]

# --- 1. idempotence => chain-length invariance (reason 1 mechanics)
assert all(meet(g,g)==g for g in G)
print('[R1] meet over 100-link Tested chain ->', reduce(meet, ['Tested']*100))

# --- 2. pomonoid tensor with retention semantics; unit = Proven
r = {'Proven':1.0,'Tested':0.98,'Attested':0.90,'Assumed':0.50,'Bottom':0.0}
def label(x):
    if x >= 1.0: return 'Proven'
    if x >= 0.95: return 'Tested'
    if x >= 0.75: return 'Attested'
    if x > 0.0:  return 'Assumed'
    return 'Bottom'
tensor = lambda a,b: a*b
grid = [0.0,0.5,0.9,0.98,1.0]
assert all(abs(tensor(tensor(a,b),c)-tensor(a,tensor(b,c)))<1e-12 for a in grid for b in grid for c in grid), 'assoc fail'
assert all((not a<=b) or (tensor(a,c)<=tensor(b,c)) for a in grid for b in grid for c in grid), 'monotone fail'
print('[R1] Proven unit idempotent: Proven(x)Proven ->', label(tensor(1.0,1.0)))
for n in [1,2,3,15,100]:
    print(f'[R1] tensor {n}-link Tested chain -> {label(0.98**n)} ({0.98**n:.4f})  | meet says {reduce(meet,["Tested"]*n)}')

# --- 3. reason-2 behavior EXPRESSED WITH MEET (witness as graded operand)
def compose_grade(gf, gg, gw=None):
    return reduce(meet, [gf, gg, gw if gw else 'Attested'])  # absent witness caps at Attested_by
print('[R2] no witness:', compose_grade('Tested','Tested'),
      '| with Tested integration witness:', compose_grade('Tested','Tested','Tested'))

# --- 4. class-blindness applies to the REPLACEMENT tensor too (reason 3 does not discriminate)
required = {'safety_critical':'Proven'}
def admissible(grade, cls): return rank[grade] >= rank[required.get(cls,'Assumed')]
g_meet   = meet('Proven','Tested')
g_tensor = label(tensor(r['Proven'], r['Tested']))
print('[R3] meet(P,T)=',g_meet,'tensor(P,T)=',g_tensor,
      '-> BOTH class-blind; gate rejects both for safety_critical:',
      admissible(g_meet,'safety_critical'), admissible(g_tensor,'safety_critical'))

# --- 5. CEILING COUNTERMODEL: Proven runtime monitor wrapping Assumed component
parts = {'f':'Assumed','monitor':'Proven'}
composite_claim_grade = parts['monitor']   # enforcement: claim "output in P" derived from monitor alone
ceiling = meet(parts['f'], parts['monitor'])
print('[CEIL] monitor(P) o f_assumed: composite grade', composite_claim_grade,
      'vs meet(parts)=', ceiling,
      '->', 'CEILING VIOLATED' if rank[composite_claim_grade]>rank[ceiling] else 'ok')

# --- 6. WCET non-compositional branch (reason 4)
compositional = {'functional':True,'WCET':False}
def compose(cls, gf, gg, gw=None):
    if not compositional[cls]:
        return ('Assumed', 'OBLIGATION: whole-program timing analysis')
    return (compose_grade(gf,gg,gw), None)
print('[R4] WCET Proven o Proven ->', compose('WCET','Proven','Proven'),
      '| raw meet would say', meet('Proven','Proven'))
