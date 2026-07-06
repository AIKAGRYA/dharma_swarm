# Walk the claimed mechanism: canonicality transitions arm pre-decided degraded modes.
# Question 1: can the switch fire with ZERO in-loop evaluation? 
# Question 2: under sustained partition, does the transition chain terminate in actuation or silence?

def run(fallback_authority_ttl_bound, mission_ticks=600, ttl_primary=120, ttl_fallback=300, partition_at=100):
    mode = "PRIMARY"; log = []
    for t in range(mission_ticks):
        partitioned = t >= partition_at
        # --- transition DETECTION: this line IS a runtime evaluation of canonicality.
        # Remove it ("never evaluated in-loop", literal reading) and `mode` can never change. 
        primary_canonical = (not partitioned) or (t < ttl_primary)
        fallback_canonical = (not partitioned) or (t < ttl_fallback) or (not fallback_authority_ttl_bound)
        if mode == "PRIMARY" and not primary_canonical:
            mode = "FALLBACK"; log.append((t, "arm fallback"))
        if mode == "FALLBACK" and not fallback_canonical:
            mode = "SILENCE"; log.append((t, "fallback receipt non-canonical -> fail-closed"))
        if mode == "SILENCE":
            return f"ttl_bound_fallback={fallback_authority_ttl_bound}: AIRFRAME LOST at t={t} (fail-to-silence recurred one level down) {log}"
    return f"ttl_bound_fallback={fallback_authority_ttl_bound}: lands safely in mode={mode} {log}"

print(run(True))   # fallback authority still governed by live canonicality predicate
print(run(False))  # fallback authority epoch-pinned at mission start (exempt in-flight)
