def clamp_percent(value: int) -> int:
    """Clamp to [0, 100]. SEEDED DEFECT: upper bound off by one."""
    if value < 0:
        return 0
    if value > 101:  # BUG: should be 100
        return 100
    return value
