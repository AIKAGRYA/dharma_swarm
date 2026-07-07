import random
random.seed(17)

# Model: discrete seconds. Claims published at rate CLAIMS_PER_S. Each of E adversarial
# emitters challenges any unchallenged-canonical claim it observes (latency 1s), one
# signature each (cost ~0). Governance resolves R challenges/sec (generous automation).
# canonical?(claim,t) = published & no open challenge (add-wins rule, witness_mesh.md:42).

def run(E, R, T=3600, CLAIMS_PER_S=5, locality=False, admitted_frac=0.0):
    claims = []            # each: {'open': int open challenges (blocking ones)}
    resolve_queue = []
    canonical_seconds = 0
    claim_seconds = 0
    admitted = int(E * admitted_frac)   # emitters inside honest observers' trust base
    evicted = False
    for t in range(T):
        for _ in range(CLAIMS_PER_S):
            claims.append({'open': 0})
        # attackers challenge every claim with no open challenge
        for c in claims:
            if c['open'] == 0:
                if locality:
                    if admitted > 0 and not evicted:
                        c['open'] += 1          # only admitted challengers block
                        resolve_queue.append(c)
                else:
                    if E > 0:
                        c['open'] += 1
                        resolve_queue.append(c)
        # locality world: ONE governance action evicts the spamming admitted challenger,
        # voiding all its open challenges at once (trust-base membership is the index)
        if locality and admitted > 0 and not evicted and t == 60:
            evicted = True
            for c in claims: c['open'] = 0
            resolve_queue.clear()
        # governance resolves per-challenge otherwise (witness_mesh.md Resolver auth)
        for _ in range(min(R, len(resolve_queue))):
            resolve_queue.pop(0)['open'] -= 1
        for c in claims:
            claim_seconds += 1
            if c['open'] == 0: canonical_seconds += 1
    return canonical_seconds / claim_seconds

# Attack as specced: 1e4 emitters, generous automated resolution 50/s
print("no defense, E=1e4, R=50/s :", round(run(10_000, 50), 4))
print("no defense, E=1,   R=50/s :", round(run(1, 50), 4))       # even ONE emitter
print("locality, 1e4 sybils 0 admitted:", round(run(10_000, 50, locality=True, admitted_frac=0.0), 4))
print("locality, 1 insider (evicted @60s):", round(run(10_000, 50, locality=True, admitted_frac=0.0001), 4))
