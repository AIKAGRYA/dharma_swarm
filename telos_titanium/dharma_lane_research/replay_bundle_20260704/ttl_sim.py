# Liveness cost of TTL'd root authority renewed by k-of-n cohort ceremony.
# Even WITH succession: each renewal is a ceremony that can fail
# (coordination failure, key loss, disinterest). Model per-ceremony
# failure prob from real-world root-rotation track record (DNSSEC KSK
# rollover slipped 12 months; root-CA expiries repeatedly shipped broken).
import random
random.seed(42)
def sim(years, ceremony_fail_p, grace_renewals=1, trials=200000):
    dead = 0
    for _ in range(trials):
        misses = 0
        for _ in range(years):
            if random.random() < ceremony_fail_p:
                misses += 1
                if misses > grace_renewals:
                    dead += 1
                    break
            else:
                misses = 0
    return dead/trials

for p in (0.02, 0.05, 0.10):
    print(f"ceremony fail p={p:.0%}: P(root authority lapses within 30y) = {sim(30,p):.1%}")
